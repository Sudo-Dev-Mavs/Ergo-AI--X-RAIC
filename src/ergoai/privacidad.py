"""Difuminado automático de rostros en las tomas de cámara y en las fotos subidas por la interfaz.

La pose se detecta sobre la imagen original y la cabeza se ubica con los puntos de la cara
(nariz, ojos, orejas, boca), con un margen proporcional al ancho de hombros. Si no hay pose, se
usa el detector de rostros de MediaPipe como respaldo. En disco solo se guarda la imagen
difuminada; la pose detectada antes de difuminar se guarda aparte, ligada a la imagen por su
SHA-256, para que el análisis REBA no pierda precisión en el cuello.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image

from .io_imagenes import abrir_rgb
from .modelos import Landmark, PoseResult, WorldLandmark

Caja = tuple[int, int, int, int]  # x0, y0, x1, y1 en píxeles
PUNTOS_CARA = tuple(range(0, 11))
VIS_MIN_CARA = 0.3


@dataclass
class ImagenProtegida:
    jpeg: bytes
    ancho: int
    alto: int
    personas: list[PoseResult]
    cajas: list[Caja]
    metodo: str | None  # "pose", "rostro" o None si no se encontró a quién difuminar
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        self.sha256 = hashlib.sha256(self.jpeg).hexdigest()

    def cache(self) -> dict[str, Any]:
        """Contenido de ``<vista>.pose.json``."""

        return {
            "sha256": self.sha256, "ancho": self.ancho, "alto": self.alto,
            "privacidad": {"rostros": len(self.cajas), "metodo": self.metodo},
            "personas": [personas_a_dict(p) for p in self.personas],
        }


def personas_a_dict(persona: PoseResult) -> dict[str, Any]:
    return {"landmarks": [asdict(p) for p in persona.landmarks], "world_landmarks": [asdict(p) for p in persona.world_landmarks]}


def personas_desde_dict(datos: list[dict[str, Any]]) -> list[PoseResult]:
    return [PoseResult([Landmark(**p) for p in persona["landmarks"]], [WorldLandmark(**p) for p in persona["world_landmarks"]]) for persona in datos]


def _recortar(x0: float, y0: float, x1: float, y1: float, ancho: int, alto: int) -> Caja | None:
    caja = (max(0, int(x0)), max(0, int(y0)), min(ancho, int(np.ceil(x1))), min(alto, int(np.ceil(y1))))
    return caja if caja[2] - caja[0] >= 2 and caja[3] - caja[1] >= 2 else None


def cajas_desde_pose(personas: list[PoseResult], ancho: int, alto: int) -> list[Caja]:
    """Una caja por persona que cubre toda la cabeza, aunque esté de perfil o inclinada."""

    cajas: list[Caja] = []
    for persona in personas:
        mapa = {p.indice: p for p in persona.landmarks}
        cara = [mapa[i] for i in PUNTOS_CARA if i in mapa and max(mapa[i].visibility, mapa[i].presence) >= VIS_MIN_CARA]
        if not cara:
            continue
        xs, ys = [p.x_px for p in cara], [p.y_px for p in cara]
        extension = max(max(xs) - min(xs), max(ys) - min(ys))
        hombros = float(np.hypot(mapa[11].x_px - mapa[12].x_px, mapa[11].y_px - mapa[12].y_px)) if 11 in mapa and 12 in mapa else 0.0
        # De perfil, oreja-nariz cubre ~60 % de la cabeza: 2.2× la deja completa; los hombros dan un mínimo.
        lado = max(extension * 2.2, 0.45 * hombros, 0.04 * min(ancho, alto))
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        caja = _recortar(cx - lado * 0.6, cy - lado * 0.7, cx + lado * 0.6, cy + lado * 0.55, ancho, alto)
        if caja:
            cajas.append(caja)
    return cajas


def ampliar(cajas: list[tuple[float, float, float, float]], ancho: int, alto: int, factor: float = 1.5) -> list[Caja]:
    """Convierte cajas (x, y, w, h) de un detector de rostros en cajas amplias que cubren la cabeza."""

    salida = []
    for x, y, w, h in cajas:
        cx, cy, lado = x + w / 2, y + h / 2, max(w, h) * factor
        if caja := _recortar(cx - lado / 2, cy - lado * 0.6, cx + lado / 2, cy + lado * 0.5, ancho, alto):
            salida.append(caja)
    return salida


def difuminar(imagen: np.ndarray, cajas: list[Caja]) -> np.ndarray:
    """Mosaico grueso más desenfoque: no se puede revertir para reconocer a la persona."""

    salida = imagen.copy()
    for x0, y0, x1, y1 in cajas:
        region = salida[y0:y1, x0:x1]
        alto, ancho = region.shape[:2]
        if not alto or not ancho:
            continue
        bloque = max(6, min(ancho, alto) // 8)
        pequena = cv2.resize(region, (max(1, ancho // bloque), max(1, alto // bloque)), interpolation=cv2.INTER_AREA)
        mosaico = cv2.resize(pequena, (ancho, alto), interpolation=cv2.INTER_NEAREST)
        salida[y0:y1, x0:x1] = cv2.GaussianBlur(mosaico, (0, 0), sigmaX=bloque / 2)
    return salida


def decodificar(contenido: bytes) -> np.ndarray:
    """Igual que ``io_imagenes.cargar_imagen``: corrige EXIF, convierte a RGB y respeta el tope de megapíxeles."""

    return abrir_rgb(io.BytesIO(contenido))


def codificar(imagen: np.ndarray) -> bytes:
    salida = io.BytesIO()
    Image.fromarray(imagen).save(salida, format="JPEG", quality=92)
    return salida.getvalue()


def proteger(contenido: bytes, detectar_pose: Callable[[np.ndarray], list[PoseResult]],
             detectar_rostros: Callable[[np.ndarray], list[tuple[float, float, float, float]]] | None = None) -> ImagenProtegida:
    """Detecta la pose en el original, difumina la cabeza y devuelve solo la versión protegida."""

    imagen = decodificar(contenido)
    alto, ancho = imagen.shape[:2]
    personas = detectar_pose(imagen)
    cajas, metodo = cajas_desde_pose(personas, ancho, alto), "pose"
    if not cajas and detectar_rostros is not None:
        cajas, metodo = ampliar(detectar_rostros(imagen), ancho, alto), "rostro"
    if not cajas:
        metodo = None
    return ImagenProtegida(codificar(difuminar(imagen, cajas)), ancho, alto, personas, cajas, metodo)
