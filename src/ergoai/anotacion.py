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


def _bgr(color_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Convierte un color RGB para OpenCV sin cambiar el lienzo RGB de Pillow."""

    return color_rgb[2], color_rgb[1], color_rgb[0]


def _punto(mapa: dict[int, Landmark], *indices: int) -> tuple[float, float] | None:
    if not all(i in mapa for i in indices):
        return None
    return (sum(mapa[i].x_px for i in indices) / len(indices), sum(mapa[i].y_px for i in indices) / len(indices))


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


def anotar_angulos(image_rgb: np.ndarray, landmarks: list[Landmark], vis_min: float,
                   medidas: Sequence["MedicionAngulo"], bandas: Sequence[int | None]) -> Image.Image:
    """Esqueleto sin cara, flechas de los vectores y cada ángulo junto a su articulación."""

    alto, ancho = image_rgb.shape[:2]
    escala = min(ancho, alto)
    grosor = max(2, round(escala / 320))
    lienzo = np.ascontiguousarray(image_rgb.copy())
    mapa = {p.indice: p for p in landmarks if p.visibility >= vis_min}

    for inicio, fin in CONEXIONES_CUERPO:  # esqueleto neutro con contorno para leerse sobre cualquier fondo
        if inicio in mapa and fin in mapa and inicio not in INDICES_CARA and fin not in INDICES_CARA:
            a = (round(mapa[inicio].x_px), round(mapa[inicio].y_px))
            b = (round(mapa[fin].x_px), round(mapa[fin].y_px))
            cv2.line(lienzo, a, b, _bgr(TINTA), grosor + 2, cv2.LINE_AA)
            cv2.line(lienzo, a, b, _bgr((235, 238, 242)), grosor, cv2.LINE_AA)

    anotaciones = []
    for medida, banda in zip(medidas, bandas, strict=True):
        if medida.valor_deg is None:
            continue
        ancla, flechas = _segmentos(medida, mapa)
        color = _color(banda)
        for origen, destino in flechas:
            a, b = (round(origen[0]), round(origen[1])), (round(destino[0]), round(destino[1]))
            cv2.arrowedLine(lienzo, a, b, _bgr(TINTA), grosor + 3, cv2.LINE_AA, tipLength=0.18)
            cv2.arrowedLine(lienzo, a, b, _bgr(color), grosor + 1, cv2.LINE_AA, tipLength=0.18)
        anotaciones.append((medida, color, banda, ancla))

    imagen = Image.fromarray(lienzo).convert("RGBA")
    capa = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    fuente = _fuente(max(13, min(40, round(escala * 0.026))))
    relleno = max(4, round(escala * 0.006))
    centro_x = (_punto(mapa, 23, 24) or (ancho / 2, 0))[0]
    ocupadas: list[tuple[float, float, float, float]] = []
    sin_ancla_y = relleno * 2

    for medida, color, banda, ancla in anotaciones:
        texto = _texto(medida)
        x0, y0, x1, y1 = dibujo.textbbox((0, 0), texto, font=fuente)
        w, h = x1 - x0 + 2 * relleno, y1 - y0 + 2 * relleno
        if ancla is None:
            caja = (relleno * 2, sin_ancla_y, relleno * 2 + w, sin_ancla_y + h)
            sin_ancla_y += h + relleno
        else:
            separacion = escala * 0.03
            derecha = ancla[0] >= centro_x
            izquierda = ancla[0] + separacion if derecha else ancla[0] - separacion - w
            arriba = ancla[1] - h / 2
            for intento in range(16):
                desplazamiento = (intento + 1) // 2 * (h + relleno) * (1 if intento % 2 else -1)
                caja = (izquierda, arriba + desplazamiento, izquierda + w, arriba + desplazamiento + h)
                caja = (min(max(caja[0], 0), ancho - w), min(max(caja[1], 0), alto - h), 0, 0)
                caja = (caja[0], caja[1], caja[0] + w, caja[1] + h)
                if not any(_solapa(caja, otra) for otra in ocupadas):
                    break
            borde_x = caja[0] if derecha else caja[2]
            dibujo.line([ancla, (borde_x, (caja[1] + caja[3]) / 2)], fill=(*color, 255), width=max(1, grosor - 1))
            r = grosor + 2
            dibujo.ellipse([ancla[0] - r, ancla[1] - r, ancla[0] + r, ancla[1] + r], fill=(*color, 255), outline=(*TINTA, 255))
        ocupadas.append(caja)
        dibujo.rounded_rectangle(caja, radius=relleno * 1.5, fill=(*color, 235), outline=(*TINTA, 255), width=1)
        tinta_texto = TINTA if banda == 2 else (255, 255, 255)
        dibujo.text((caja[0] + relleno - x0, caja[1] + relleno - y0), texto, font=fuente, fill=(*tinta_texto, 255))

    # Leyenda
    fuente_leyenda = _fuente(max(11, round(escala * 0.02)))
    etiquetas = [("1", COLOR_BANDA[1]), ("2", COLOR_BANDA[2]), ("3", COLOR_BANDA[3]), ("4+", COLOR_BANDA[4])]
    titulo, nota = "Banda REBA", "?  revisar"
    alto_l = dibujo.textbbox((0, 0), titulo, font=fuente_leyenda)[3] + relleno * 2
    ancho_t = dibujo.textbbox((0, 0), titulo, font=fuente_leyenda)[2]
    muestra = alto_l
    ancho_n = dibujo.textbbox((0, 0), nota, font=fuente_leyenda)[2]
    ancho_l = relleno * 3 + ancho_t + len(etiquetas) * (muestra + relleno) + ancho_n + relleno * 2
    x, y = relleno * 2, alto - alto_l - relleno * 2
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
                    medidas: Sequence["MedicionAngulo"], bandas: Sequence[int | None]) -> None:
    """Guarda la imagen anotada de una vista como PNG."""

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        anotar_angulos(image_rgb, landmarks, vis_min, medidas, bandas).save(destino, format="PNG")
    except OSError as exc:
        raise OSError(f"No se pudo guardar la imagen anotada: {destino}") from exc
