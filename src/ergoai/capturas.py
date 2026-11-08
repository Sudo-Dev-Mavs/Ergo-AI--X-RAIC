"""Capturas temporales de cámara por evaluación.

Cada disparo del temporizador es una *toma*: las vistas (frente, costado, aérea) capturadas en el
mismo instante. Las tomas viven en ``<raiz>/capturas/<borrador>/<toma>/<vista>.jpg`` mientras el
operador prepara la evaluación; al analizar se copia la toma elegida al caso. Se conservan como
máximo ``MAX_TOMAS`` por borrador y se borran solas después de ``RETENCION_HORAS``.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

VISTAS = ("frente", "costado", "aerea")
MAX_TOMAS = 120
RETENCION_HORAS = 24
MAX_BYTES = 15 * 1024 * 1024
PATRON_TOMA = re.compile(r"^\d{8}-\d{6}-\d{3}(-\d+)?$")


def carpeta(raiz: Path) -> Path:
    return raiz / "capturas"


def _id_toma(destino: Path) -> str:
    ahora = datetime.now()
    base = ahora.strftime("%Y%m%d-%H%M%S-") + f"{ahora.microsecond // 1000:03d}"
    candidato, n = base, 1
    while (destino / candidato).exists():
        n += 1
        candidato = f"{base}-{n}"
    return candidato


def validar_imagen(contenido: bytes, vista: str) -> None:
    if len(contenido) > MAX_BYTES:
        raise ValueError(f"La captura {vista} supera 15 MB.")
    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            if imagen.format not in ("JPEG", "PNG"):
                raise ValueError(f"La captura {vista} debe ser JPEG o PNG.")
            imagen.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"La captura {vista} no es una imagen válida.") from exc


def guardar_toma(raiz: Path, borrador: str, imagenes: dict[str, bytes], poses: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Guarda una toma (ya difuminada) con la pose detectada antes de difuminar, y aplica el tope."""

    if not imagenes:
        raise ValueError("La toma no trae ninguna vista.")
    for vista, contenido in imagenes.items():
        if vista not in VISTAS:
            raise ValueError(f"Vista desconocida: {vista}")
        validar_imagen(contenido, vista)
    destino = carpeta(raiz) / borrador
    destino.mkdir(parents=True, exist_ok=True)
    toma = _id_toma(destino)
    temporal = destino / f".{toma}.tmp"
    temporal.mkdir()
    for vista, contenido in imagenes.items():
        with Image.open(io.BytesIO(contenido)) as imagen:
            extension = ".jpg" if imagen.format == "JPEG" else ".png"
        (temporal / f"{vista}{extension}").write_bytes(contenido)
        if poses and vista in poses:
            (temporal / f"{vista}.pose.json").write_text(json.dumps(poses[vista], ensure_ascii=False), encoding="utf-8")
    temporal.rename(destino / toma)
    for sobrante in listar_tomas(raiz, borrador)[MAX_TOMAS:]:
        shutil.rmtree(destino / sobrante["id"], ignore_errors=True)
    return describir_toma(destino / toma)


def describir_toma(ruta: Path) -> dict[str, Any]:
    vistas = sorted(archivo.stem for archivo in ruta.iterdir() if archivo.stem in VISTAS)
    fecha = datetime.strptime(ruta.name[:19], "%Y%m%d-%H%M%S-%f").astimezone().isoformat(timespec="milliseconds")
    privacidad: dict[str, Any] = {}
    for vista in vistas:
        try:
            privacidad[vista] = json.loads((ruta / f"{vista}.pose.json").read_text(encoding="utf-8"))["privacidad"]
        except (OSError, ValueError, KeyError):
            privacidad[vista] = {"rostros": None, "metodo": None}
    return {"id": ruta.name, "fecha": fecha, "vistas": vistas, "privacidad": privacidad}


def listar_tomas(raiz: Path, borrador: str) -> list[dict[str, Any]]:
    """Tomas del borrador, la más reciente primero."""

    destino = carpeta(raiz) / borrador
    if not destino.is_dir():
        return []
    tomas = [describir_toma(ruta) for ruta in destino.iterdir() if ruta.is_dir() and PATRON_TOMA.match(ruta.name)]
    return sorted(tomas, key=lambda toma: toma["id"], reverse=True)


def archivo_vista(raiz: Path, borrador: str, toma: str, vista: str) -> Path | None:
    if not PATRON_TOMA.match(toma) or vista not in VISTAS:
        return None
    base = carpeta(raiz) / borrador / toma
    return next((base / f"{vista}{ext}" for ext in (".jpg", ".png") if (base / f"{vista}{ext}").is_file()), None)


def archivo_pose(raiz: Path, borrador: str, toma: str, vista: str) -> Path | None:
    if not PATRON_TOMA.match(toma) or vista not in VISTAS:
        return None
    ruta = carpeta(raiz) / borrador / toma / f"{vista}.pose.json"
    return ruta if ruta.is_file() else None


def descartar(raiz: Path, borrador: str) -> None:
    shutil.rmtree(carpeta(raiz) / borrador, ignore_errors=True)


def purgar_vencidas(raiz: Path, horas: float = RETENCION_HORAS) -> int:
    """Borra los borradores sin actividad en las últimas ``horas``; devuelve cuántos borró."""

    base = carpeta(raiz)
    if not base.is_dir():
        return 0
    limite = time.time() - horas * 3600
    borrados = 0
    for borrador in base.iterdir():
        if not borrador.is_dir():
            continue
        ultima = max([borrador.stat().st_mtime, *(hijo.stat().st_mtime for hijo in borrador.iterdir())])
        if ultima < limite:
            shutil.rmtree(borrador, ignore_errors=True)
            borrados += 1
    return borrados
