"""Carga local y segura de fotografías."""

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

# Tope de resolución antes de decodificar. Una imagen pequeña en bytes puede declarar cientos de
# megapíxeles («bomba de descompresión») y agotar la memoria al decodificarla; 50 MP cubre las
# cámaras de 48 MP de los teléfonos actuales.
MAX_MEGAPIXELES = 50
MAX_PIXELES = MAX_MEGAPIXELES * 1_000_000
# Pillow avisa por encima de este valor y rechaza por encima del doble: así nunca llega a decodificar
# más de lo que admitimos aunque alguien llame a Image.open directamente.
Image.MAX_IMAGE_PIXELS = MAX_PIXELES

_ERRORES_LECTURA = (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError)


@dataclass(frozen=True)
class ImagenRGB:
    """Imagen corregida por EXIF lista para MediaPipe y OpenCV."""

    pixeles: np.ndarray
    ancho: int
    alto: int


def _revisar_tamano(imagen: Image.Image, etiqueta: str) -> None:
    ancho, alto = imagen.size
    if ancho * alto > MAX_PIXELES:
        raise ValueError(f"{etiqueta} mide {ancho}×{alto} px ({ancho * alto / 1e6:.0f} MP); el máximo es {MAX_MEGAPIXELES} MP.")


def validar_foto(contenido: bytes, etiqueta: str, max_bytes: int) -> str:
    """Revisa peso, formato y resolución sin decodificar la imagen; devuelve la extensión (.jpg o .png).

    ``etiqueta`` encabeza los mensajes, p. ej. «La foto costado» o «La captura frente».
    """

    if len(contenido) > max_bytes:
        raise ValueError(f"{etiqueta} supera {max_bytes // (1024 * 1024)} MB.")
    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            formato = imagen.format
            _revisar_tamano(imagen, etiqueta)
            imagen.verify()
    except ValueError as exc:
        if str(exc).startswith(etiqueta):
            raise
        raise ValueError(f"{etiqueta} no es una imagen JPG o PNG válida.") from exc
    except Image.DecompressionBombError as exc:
        raise ValueError(f"{etiqueta} supera el máximo de {MAX_MEGAPIXELES} MP.") from exc
    except _ERRORES_LECTURA as exc:
        raise ValueError(f"{etiqueta} no es una imagen JPG o PNG válida.") from exc
    if formato not in ("JPEG", "PNG"):
        raise ValueError(f"{etiqueta} debe ser JPG o PNG.")
    return ".jpg" if formato == "JPEG" else ".png"


def abrir_rgb(origen: str | Path | io.BytesIO, etiqueta: str = "La imagen") -> np.ndarray:
    """Decodifica con EXIF corregido a RGB uint8, rechazando lo ilegible o demasiado grande."""

    try:
        with Image.open(origen) as original:
            _revisar_tamano(original, etiqueta)
            return np.asarray(ImageOps.exif_transpose(original).convert("RGB"), dtype=np.uint8).copy()
    except ValueError:
        raise
    except Image.DecompressionBombError as exc:
        raise ValueError(f"{etiqueta} supera el máximo de {MAX_MEGAPIXELES} MP.") from exc
    except _ERRORES_LECTURA as exc:
        raise ValueError(f"{etiqueta} no es una imagen JPG o PNG válida.") from exc


def cargar_imagen(ruta: str | Path) -> ImagenRGB:
    """Corrige EXIF, convierte a RGB y devuelve píxeles uint8."""

    pixeles = abrir_rgb(ruta, f"La imagen {Path(ruta).name}")
    alto, ancho = pixeles.shape[:2]
    return ImagenRGB(pixeles=pixeles, ancho=ancho, alto=alto)
