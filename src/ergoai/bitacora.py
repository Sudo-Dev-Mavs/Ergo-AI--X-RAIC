"""Bitácora append-only por sesión/caso. No es un catálogo de personas (D4/C6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ruta_bitacora(carpeta_salida: Path) -> Path:
    return carpeta_salida / "bitacora.jsonl"


def _ahora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def registrar(
    carpeta_salida: Path,
    *,
    usuario: str,
    accion: str,
    campo: str,
    valor_anterior: Any,
    valor_nuevo: Any,
    motivo: str,
    recomendacion_id: str | None = None,
) -> dict[str, Any]:
    """Agrega una línea JSONL con el registro de cambio (R6)."""

    evento = {
        "fecha_hora": _ahora(),
        "usuario": usuario,
        "accion": accion,
        "recomendacion_id": recomendacion_id,
        "campo": campo,
        "valor_anterior": valor_anterior,
        "valor_nuevo": valor_nuevo,
        "motivo": motivo,
    }
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    with ruta_bitacora(carpeta_salida).open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
    return evento


def leer(carpeta_salida: Path) -> list[dict[str, Any]]:
    ruta = ruta_bitacora(carpeta_salida)
    if not ruta.is_file():
        return []
    eventos: list[dict[str, Any]] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            eventos.append(json.loads(linea))
    return eventos


def actualizar_estado_recomendacion(
    recomendaciones: list[dict[str, Any]],
    recomendacion_id: str,
    nuevo_estado: str,
    *,
    usuario: str,
    motivo: str,
    carpeta_salida: Path,
    solucion_nueva: str | None = None,
) -> list[dict[str, Any]]:
    """Cambia estado/solución y deja rastro en bitácora + historial local."""

    actualizadas: list[dict[str, Any]] = []
    for item in recomendaciones:
        copia = dict(item)
        if copia.get("id") != recomendacion_id:
            actualizadas.append(copia)
            continue
        anterior_estado = copia.get("estado")
        copia["estado"] = nuevo_estado
        historial = list(copia.get("historial") or [])
        cambio = {
            "fecha_hora": _ahora(),
            "usuario": usuario,
            "campo": "estado",
            "valor_anterior": anterior_estado,
            "valor_nuevo": nuevo_estado,
            "motivo": motivo,
        }
        historial.append(cambio)
        registrar(
            carpeta_salida,
            usuario=usuario,
            accion="cambiar_estado",
            campo="estado",
            valor_anterior=anterior_estado,
            valor_nuevo=nuevo_estado,
            motivo=motivo,
            recomendacion_id=recomendacion_id,
        )
        if solucion_nueva is not None and solucion_nueva != copia.get("solucion"):
            historial.append(
                {
                    "fecha_hora": _ahora(),
                    "usuario": usuario,
                    "campo": "solucion",
                    "valor_anterior": copia.get("solucion"),
                    "valor_nuevo": solucion_nueva,
                    "motivo": motivo,
                }
            )
            registrar(
                carpeta_salida,
                usuario=usuario,
                accion="editar_solucion",
                campo="solucion",
                valor_anterior=copia.get("solucion"),
                valor_nuevo=solucion_nueva,
                motivo=motivo,
                recomendacion_id=recomendacion_id,
            )
            copia["solucion"] = solucion_nueva
            if nuevo_estado == "propuesta":
                copia["estado"] = "editada"
        copia["historial"] = historial
        actualizadas.append(copia)
    return actualizadas
