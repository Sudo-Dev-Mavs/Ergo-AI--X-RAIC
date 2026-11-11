"""Imágenes anotadas: esqueleto sin rostro, vectores medidos y ángulos coloreados por banda REBA."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .landmarks import CONEXIONES_CUERPO, INDICES_CARA
from .modelos import Landmark

if TYPE_CHECKING:
    from .angulos import MedicionAngulo

# Mismos colores de riesgo que la interfaz (RGB): banda 1 verde, 2 amarillo, 3 naranja, 4+ rojo.
COLOR_BANDA = {1: (47, 143, 91), 2: (217, 154, 0), 3: (224, 97, 14), 4: (196, 43, 28)}
GRIS = (138, 153, 173)
TINTA = (19, 35, 59)
NOMBRE_CORTO = {
    "tronco_flexion": "Tronco", "tronco_inclinacion_lateral": "Incl. lateral", "tronco_torsion": "Torsión",
    "cuello_flexion": "Cuello", "cuello_inclinacion_rotacion": "Giro cuello", "brazo_flexion": "Brazo",
    "brazo_abduccion": "Abducción", "codo_flexion": "Codo", "muneca_flexion_extension": "Muñeca",
    "rodilla_flexion": "Rodilla", "apoyo_piernas_unilateral": "Apoyo",
}
LADO = {"L": " izq.", "R": " der."}
# Por lado: hombro, codo, muñeca, (meñique, índice), cadera, rodilla, tobillo
INDICES = {"L": (11, 13, 15, (17, 19), 23, 25, 27), "R": (12, 14, 16, (18, 20), 24, 26, 28)}
# Umbral más permisivo solo al dibujar (cenital / escorzo): no afecta la medición REBA.
VIS_DIBUJO_MIN = 0.28


def dibujar_esqueleto(image_rgb: np.ndarray, landmarks: list[Landmark], vis_min: float) -> np.ndarray:
    """Dibuja únicamente el cuerpo (BGR); los landmarks faciales nunca se representan."""

    imagen = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    puntos = {punto.indice: punto for punto in landmarks if punto.visibility >= vis_min}
    for inicio, fin in CONEXIONES_CUERPO:
        if inicio in puntos and fin in puntos:
            a, b = puntos[inicio], puntos[fin]
            cv2.line(imagen, (round(a.x_px), round(a.y_px)), (round(b.x_px), round(b.y_px)), (0, 220, 0), 2)
    for indice, punto in puntos.items():
        if indice not in INDICES_CARA:
            cv2.circle(imagen, (round(punto.x_px), round(punto.y_px)), 3, (255, 170, 0), -1)
    return imagen


def guardar_esqueleto(ruta: str | Path, image_rgb: np.ndarray, landmarks: list[Landmark], vis_min: float) -> None:
    """Guarda la anotación como PNG, creando sus carpetas si hacen falta."""

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destino), dibujar_esqueleto(image_rgb, landmarks, vis_min)):
        raise OSError(f"No se pudo guardar la imagen anotada: {destino}")


@lru_cache(maxsize=8)
def _fuente(tamano: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """DejaVu Sans (incluida en matplotlib) para que se vean «°», «ñ» y acentos."""

    try:
        import matplotlib

        return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"), tamano)
    except (ImportError, OSError):
        return ImageFont.load_default(tamano)


def _color(banda: int | None) -> tuple[int, int, int]:
    return GRIS if banda is None else COLOR_BANDA[min(4, max(1, banda))]


def _punto(mapa: dict[int, Landmark], *indices: int) -> tuple[float, float] | None:
    if not all(i in mapa for i in indices):
        return None
    return (sum(mapa[i].x_px for i in indices) / len(indices), sum(mapa[i].y_px for i in indices) / len(indices))


def _bbox_cuerpo(mapa: dict[int, Landmark]) -> tuple[float, float, float, float] | None:
    """Caja del torso/extremidades visibles (sin cara), para escalar etiquetas al sujeto."""

    xs = [p.x_px for i, p in mapa.items() if i not in INDICES_CARA]
    ys = [p.y_px for i, p in mapa.items() if i not in INDICES_CARA]
    if len(xs) < 2:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _escala_etiquetas(ancho: int, alto: int, mapa: dict[int, Landmark], n_etiquetas: int) -> tuple[int, int, float]:
    """Fuente/relleno/separación según tamaño de la persona, no solo de la foto.

    Evita que en fotos chicas o con el sujeto lejos las cajas tapen el cuerpo
    (como pasa al escalar solo con min(ancho, alto)).
    """

    escala_img = float(min(ancho, alto))
    caja = _bbox_cuerpo(mapa)
    if caja is not None:
        alto_p = max(1.0, caja[3] - caja[1])
        ancho_p = max(1.0, caja[2] - caja[0])
        ref = max(alto_p, ancho_p * 0.65)
        # Suelo: no usar un sujeto minúsculo como referencia (texto ilegible).
        ref = max(ref, escala_img * 0.18)
    else:
        ref = escala_img * 0.42

    tam = int(round(ref * 0.032))
    tam = max(9, min(22, tam))
    # Techo duro respecto a la imagen (fotos pequeñas / recortes).
    tam = min(tam, max(9, int(round(escala_img * 0.022))))
    if n_etiquetas >= 6:
        tam = max(9, tam - 1)
    if n_etiquetas >= 8:
        tam = max(8, tam - 2)
    if n_etiquetas >= 11:
        tam = max(8, tam - 1)

    relleno = max(2, int(round(tam * 0.22)))
    # Más separación cuando hay muchas etiquetas → menos montón sobre el cuerpo.
    factor_sep = 1.0 + min(0.8, max(0, n_etiquetas - 4) * 0.12)
    separacion = max(ref * 0.045, tam * 1.4) * factor_sep
    return tam, relleno, separacion


def _segmentos(medida: "MedicionAngulo", mapa: dict[int, Landmark]) -> tuple[tuple[float, float] | None, list[tuple[tuple[float, float], tuple[float, float]]]]:
    """Articulación donde va la etiqueta y vectores (origen, destino) que usa la medida."""

    m, lado = medida.medida, medida.lado
    caderas, hombros = _punto(mapa, 23, 24), _punto(mapa, 11, 12)
    flechas: list[tuple[tuple[float, float] | None, tuple[float, float] | None]] = []
    ancla = None
    if m in ("tronco_flexion", "tronco_inclinacion_lateral"):
        ancla, flechas = caderas, [(caderas, hombros)]
    elif m == "tronco_torsion":
        ancla, flechas = hombros, [(_punto(mapa, 11), _punto(mapa, 12)), (_punto(mapa, 23), _punto(mapa, 24))]
    elif m == "cuello_flexion":
        hombro = _punto(mapa, 11) if lado == "L" else _punto(mapa, 12) if lado == "R" else hombros
        oreja = _punto(mapa, 7) if lado == "L" else _punto(mapa, 8) if lado == "R" else _punto(mapa, 7, 8)
        ancla, flechas = hombro, [(hombro, oreja)]
    elif m == "cuello_inclinacion_rotacion":
        ancla, flechas = hombros, [(hombros, _punto(mapa, 0))]
    elif m == "apoyo_piernas_unilateral":
        ancla = _punto(mapa, 27, 28)
    elif lado in INDICES:
        hombro, codo, muneca, mano, cadera, rodilla, tobillo = INDICES[lado]
        if m in ("brazo_flexion", "brazo_abduccion"):
            ancla, flechas = _punto(mapa, hombro), [(_punto(mapa, hombro), _punto(mapa, codo))]
        elif m == "codo_flexion":
            ancla, flechas = _punto(mapa, codo), [(_punto(mapa, codo), _punto(mapa, muneca))]
        elif m == "muneca_flexion_extension":
            ancla, flechas = _punto(mapa, muneca), [(_punto(mapa, muneca), _punto(mapa, *mano))]
        elif m == "rodilla_flexion":
            ancla, flechas = _punto(mapa, rodilla), [(_punto(mapa, cadera), _punto(mapa, rodilla)), (_punto(mapa, rodilla), _punto(mapa, tobillo))]
    if medida.metodo.startswith("respaldo 3D"):
        flechas = []  # el valor viene de la pose 3D: una flecha 2D no lo representaría
    return ancla, [(a, b) for a, b in flechas if a is not None and b is not None]


def _texto(medida: "MedicionAngulo") -> str:
    nombre = NOMBRE_CORTO.get(medida.medida, medida.medida) + LADO.get(medida.lado or "", "") if medida.medida != "cuello_flexion" else "Cuello"
    if medida.medida == "apoyo_piernas_unilateral":
        valor = "una pierna" if medida.valor_deg else "dos piernas"
    else:
        valor = f"{medida.valor_deg:.0f}°"
    return f"{nombre} {valor}{' ?' if medida.banderas else ''}"


def _solapa(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _dentro(caja: tuple[float, float, float, float], zona: tuple[float, float, float, float] | None) -> bool:
    if zona is None:
        return False
    cx = (caja[0] + caja[2]) / 2
    cy = (caja[1] + caja[3]) / 2
    return zona[0] <= cx <= zona[2] and zona[1] <= cy <= zona[3]


def _candidatos_caja(
    ancla: tuple[float, float],
    w: float,
    h: float,
    ancho: int,
    alto: int,
    separacion: float,
    relleno: int,
    centro_x: float,
) -> list[tuple[float, float, float, float]]:
    """Posiciones candidatas: ambos lados del ancla, arriba/abajo, con desplazamientos anti-solape."""

    preferir_derecha = ancla[0] >= centro_x
    lados = (1, -1) if preferir_derecha else (-1, 1)
    candidatos: list[tuple[float, float, float, float]] = []
    for radio in (1.0, 1.45, 1.9):
        sep = separacion * radio
        for signo in lados:
            for intento in range(16):
                desplazamiento = (intento + 1) // 2 * (h + relleno) * (1 if intento % 2 else -1)
                if signo > 0:
                    izq = ancla[0] + sep
                else:
                    izq = ancla[0] - sep - w
                arriba = ancla[1] - h / 2 + desplazamiento
                izq = min(max(izq, 0), max(0, ancho - w))
                arriba = min(max(arriba, 0), max(0, alto - h))
                candidatos.append((izq, arriba, izq + w, arriba + h))
    # Arriba / abajo del ancla (útil cuando el cuerpo está apretado al centro).
    for dy_signo in (-1, 1):
        for radio in (1.0, 1.5):
            izq = min(max(ancla[0] - w / 2, 0), max(0, ancho - w))
            arriba = ancla[1] + dy_signo * (separacion * radio + h / 2) - h / 2
            arriba = min(max(arriba, 0), max(0, alto - h))
            candidatos.append((izq, arriba, izq + w, arriba + h))
    return candidatos


def _elegir_caja(
    ancla: tuple[float, float] | None,
    w: float,
    h: float,
    ancho: int,
    alto: int,
    separacion: float,
    relleno: int,
    centro_x: float,
    ocupadas: list[tuple[float, float, float, float]],
    zona_cuerpo: tuple[float, float, float, float] | None,
    sin_ancla_y: float,
) -> tuple[tuple[float, float, float, float], float]:
    if ancla is None:
        caja = (relleno * 2, sin_ancla_y, relleno * 2 + w, sin_ancla_y + h)
        return caja, sin_ancla_y + h + relleno

    mejor: tuple[float, float, float, float] | None = None
    mejor_score = float("inf")
    for caja in _candidatos_caja(ancla, w, h, ancho, alto, separacion, relleno, centro_x):
        solapes = sum(1 for otra in ocupadas if _solapa(caja, otra))
        tapa_cuerpo = 1 if _dentro(caja, zona_cuerpo) else 0
        # Distancia al ancla: preferir cerca pero fuera del cuerpo.
        cx, cy = (caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2
        dist = abs(cx - ancla[0]) + abs(cy - ancla[1])
        score = solapes * 1000 + tapa_cuerpo * 80 + dist * 0.02
        if score < mejor_score:
            mejor_score = score
            mejor = caja
            if solapes == 0 and tapa_cuerpo == 0:
                break
    assert mejor is not None
    return mejor, sin_ancla_y


def anotar_angulos(image_rgb: np.ndarray, landmarks: list[Landmark], vis_min: float,
                   medidas: Sequence["MedicionAngulo"], bandas: Sequence[int | None],
                   *, vis_dibujo: float | None = None) -> Image.Image:
    """Esqueleto sin cara, flechas de los vectores y cada ángulo junto a su articulación.

    ``vis_dibujo`` puede ser más bajo que ``vis_min`` (p. ej. aérea) para que el
    esqueleto/anclas se vean aunque MediaPipe marque poca confianza; no cambia el REBA.
    """

    alto, ancho = image_rgb.shape[:2]
    # Un poco más permisivo al dibujar que al medir (cenital / escorzo).
    umbral = vis_dibujo if vis_dibujo is not None else max(VIS_DIBUJO_MIN, min(vis_min, vis_min * 0.75))

    grosor = max(2, round(min(ancho, alto) / 320))
    lienzo = np.ascontiguousarray(image_rgb.copy())
    mapa = {p.indice: p for p in landmarks if p.visibility >= umbral}

    for inicio, fin in CONEXIONES_CUERPO:  # esqueleto neutro con contorno para leerse sobre cualquier fondo
        if inicio in mapa and fin in mapa and inicio not in INDICES_CARA and fin not in INDICES_CARA:
            a = (round(mapa[inicio].x_px), round(mapa[inicio].y_px))
            b = (round(mapa[fin].x_px), round(mapa[fin].y_px))
            cv2.line(lienzo, a, b, TINTA, grosor + 2, cv2.LINE_AA)
            cv2.line(lienzo, a, b, (235, 238, 242), grosor, cv2.LINE_AA)

    anotaciones = []
    for medida, banda in zip(medidas, bandas, strict=True):
        if medida.valor_deg is None:
            continue
        ancla, flechas = _segmentos(medida, mapa)
        color = _color(banda)
        for origen, destino in flechas:
            a, b = (round(origen[0]), round(origen[1])), (round(destino[0]), round(destino[1]))
            cv2.arrowedLine(lienzo, a, b, TINTA, grosor + 3, cv2.LINE_AA, tipLength=0.18)
            cv2.arrowedLine(lienzo, a, b, color, grosor + 1, cv2.LINE_AA, tipLength=0.18)
        anotaciones.append((medida, color, banda, ancla))

    imagen = Image.fromarray(lienzo).convert("RGBA")
    capa = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    tam_fuente, relleno, separacion = _escala_etiquetas(ancho, alto, mapa, len(anotaciones))
    fuente = _fuente(tam_fuente)
    zona_cuerpo = _bbox_cuerpo(mapa)
    centro_x = (_punto(mapa, 23, 24) or _punto(mapa, 11, 12) or (ancho / 2, 0))[0]

    # La leyenda se mide antes de colocar etiquetas y su caja cuenta como ocupada,
    # para que ninguna etiqueta quede debajo de ella (abajo a la izquierda).
    fuente_leyenda = _fuente(max(10, min(tam_fuente - 1, round(min(ancho, alto) * 0.018))))
    etiquetas = [("1", COLOR_BANDA[1]), ("2", COLOR_BANDA[2]), ("3", COLOR_BANDA[3]), ("4+", COLOR_BANDA[4])]
    titulo, nota = "Banda REBA", "?  revisar"
    alto_l = dibujo.textbbox((0, 0), titulo, font=fuente_leyenda)[3] + relleno * 2
    ancho_t = dibujo.textbbox((0, 0), titulo, font=fuente_leyenda)[2]
    muestra = alto_l
    ancho_n = dibujo.textbbox((0, 0), nota, font=fuente_leyenda)[2]
    ancho_l = relleno * 3 + ancho_t + len(etiquetas) * (muestra + relleno) + ancho_n + relleno * 2
    x, y = relleno * 2, alto - alto_l - relleno * 2
    caja_leyenda = (float(x), float(y), float(x + ancho_l), float(y + alto_l))

    ocupadas: list[tuple[float, float, float, float]] = [caja_leyenda]
    sin_ancla_y = float(relleno * 2)

    # Primero riesgo alto; a igualdad, de arriba a abajo para repartir mejor el espacio.
    anotaciones.sort(key=lambda item: (-(item[2] or 0), (item[3] or (0, 0))[1]))

    for medida, color, banda, ancla in anotaciones:
        texto = _texto(medida)
        x0, y0, x1, y1 = dibujo.textbbox((0, 0), texto, font=fuente)
        w, h = x1 - x0 + 2 * relleno, y1 - y0 + 2 * relleno
        caja, sin_ancla_y = _elegir_caja(
            ancla, w, h, ancho, alto, separacion, relleno, centro_x, ocupadas, zona_cuerpo, sin_ancla_y,
        )
        if ancla is not None:
            derecha = (caja[0] + caja[2]) / 2 >= ancla[0]
            borde_x = caja[0] if derecha else caja[2]
            dibujo.line([ancla, (borde_x, (caja[1] + caja[3]) / 2)], fill=(*color, 255), width=max(1, grosor - 1))
            r = max(2, grosor + 1)
            dibujo.ellipse([ancla[0] - r, ancla[1] - r, ancla[0] + r, ancla[1] + r], fill=(*color, 255), outline=(*TINTA, 255))
        ocupadas.append(caja)
        # Un poco más transparentes para que el cuerpo se lea detrás.
        dibujo.rounded_rectangle(caja, radius=max(3, relleno), fill=(*color, 210), outline=(*TINTA, 255), width=1)
        tinta_texto = TINTA if banda == 2 else (255, 255, 255)
        dibujo.text((caja[0] + relleno - x0, caja[1] + relleno - y0), texto, font=fuente, fill=(*tinta_texto, 255))

    # Leyenda (medida arriba, antes de colocar las etiquetas)
    dibujo.rounded_rectangle((x, y, x + ancho_l, y + alto_l), radius=relleno, fill=(246, 248, 249, 225), outline=(*TINTA, 255))
    cursor = x + relleno * 1.5
    dibujo.text((cursor, y + relleno), titulo, font=fuente_leyenda, fill=(*TINTA, 255))
    cursor += ancho_t + relleno * 1.5
    for etiqueta, color in etiquetas:
        dibujo.rounded_rectangle((cursor, y + 2, cursor + muestra, y + alto_l - 2), radius=relleno, fill=(*color, 255))
        caja_t = dibujo.textbbox((0, 0), etiqueta, font=fuente_leyenda)
        dibujo.text((cursor + (muestra - caja_t[2]) / 2, y + relleno), etiqueta, font=fuente_leyenda,
                    fill=(*(TINTA if color == COLOR_BANDA[2] else (255, 255, 255)), 255))
        cursor += muestra + relleno
    dibujo.text((cursor + relleno / 2, y + relleno), nota, font=fuente_leyenda, fill=(*TINTA, 255))

    return Image.alpha_composite(imagen, capa).convert("RGB")


def guardar_angulos(ruta: str | Path, image_rgb: np.ndarray, landmarks: list[Landmark], vis_min: float,
                    medidas: Sequence["MedicionAngulo"], bandas: Sequence[int | None],
                    *, vis_dibujo: float | None = None) -> None:
    """Guarda la imagen anotada de una vista como PNG."""

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        anotar_angulos(image_rgb, landmarks, vis_min, medidas, bandas, vis_dibujo=vis_dibujo).save(destino, format="PNG")
    except OSError as exc:
        raise OSError(f"No se pudo guardar la imagen anotada: {destino}") from exc
