"""Riesgo residual: recalcula REBA con los efectos esperados de las recomendaciones vigentes."""

from __future__ import annotations

import copy
from typing import Any, Iterable

from .config import RebaConfig
from .reba import calcular_reba, nivel_riesgo

ESTADOS_EXCLUIDOS = ("rechazada", "obsoleta")
# Medidas cuyo objetivo es un valor dentro de un rango (no "menos es mejor").
_FIJAR = ("codo_flexion",)


def _aplicar_medicion(mediciones: dict[str, float | None], clave: str, objetivo: float) -> None:
    actual = mediciones.get(clave)
    if actual is None:
        return  # no se inventa una medición ausente
    if clave.startswith(_FIJAR):
        mediciones[clave] = objetivo
    elif abs(actual) > abs(objetivo):
        mediciones[clave] = objetivo


def _aplicar_contexto(contexto: dict[str, Any], ruta: str, valor: Any) -> None:
    destino = contexto
    *padres, hoja = ruta.split(".")
    for padre in padres:
        siguiente = destino.get(padre)
        if not isinstance(siguiente, dict):
            siguiente = {}
            destino[padre] = siguiente
        destino = siguiente
    actual = destino.get(hoja)
    if hoja == "carga_kg" and isinstance(actual, (int, float)) and isinstance(valor, (int, float)):
        destino[hoja] = min(actual, valor)
    else:
        destino[hoja] = valor


def aplicar_efectos(mediciones: dict[str, float | None], contexto: dict[str, Any], recomendaciones: Iterable[dict[str, Any]]) -> tuple[dict[str, float | None], dict[str, Any]]:
    """Devuelve copias de mediciones/contexto con los efectos de las recomendaciones aplicados."""

    nuevas = dict(mediciones)
    nuevo_contexto = copy.deepcopy(contexto)
    for rec in recomendaciones:
        efecto = rec.get("efecto") or {}
        for clave, objetivo in (efecto.get("mediciones") or {}).items():
            _aplicar_medicion(nuevas, clave, float(objetivo))
        for ruta, valor in (efecto.get("contexto") or {}).items():
            _aplicar_contexto(nuevo_contexto, ruta, valor)
    return nuevas, nuevo_contexto


def cuenta_para_residual(rec: dict[str, Any]) -> bool:
    """Solo controles de ingeniería/rediseño no rechazados y con efecto medible."""

    return rec.get("estado") not in ESTADOS_EXCLUIDOS and rec.get("jerarquia") != "administrativa" and bool(rec.get("efecto"))


def _resumen(reba: dict[str, Any]) -> dict[str, Any]:
    return {
        "reba": reba["final"]["reportado"], "nivel_riesgo": reba["nivel_riesgo"], "nivel_accion": reba["nivel_accion"],
        "bandas": {**{k: reba["grupo_a"][k] for k in ("tronco", "cuello", "piernas", "carga")},
                   **{f"{k}_{lado}": reba["grupo_b"][lado][k] for lado in ("L", "R") for k in ("brazo", "antebrazo", "muneca", "agarre")},
                   "actividad": reba["actividad"]},
    }


def calcular_residual(
    mediciones: dict[str, float | None], contexto: dict[str, Any], recomendaciones: list[dict[str, Any]], config: RebaConfig,
    override_residual: int | None = None,
) -> dict[str, Any]:
    """Compara el REBA inicial contra el esperado tras aplicar las recomendaciones vigentes.

    Si ``override_residual`` viene del especialista, reemplaza el residual del agente y deja
    ambos valores visibles para el comparador Antes/Después.
    """

    inicial = calcular_reba(mediciones, contexto, config).a_diccionario()
    aplicadas = [rec for rec in recomendaciones if cuenta_para_residual(rec)]
    nuevas, nuevo_contexto = aplicar_efectos(mediciones, contexto, aplicadas)
    residual = calcular_reba(nuevas, nuevo_contexto, config).a_diccionario()
    agente = _resumen(residual)
    origen = "agente"
    if override_residual is not None:
        if not 1 <= override_residual <= 15:
            raise ValueError("El residual proyectado debe estar entre 1 y 15.")
        nivel = nivel_riesgo(override_residual)
        residual_resumen = {
            "reba": override_residual,
            "nivel_riesgo": nivel.nombre,
            "nivel_accion": nivel.nivel_accion,
            "bandas": agente["bandas"],
        }
        origen = "especialista"
    else:
        residual_resumen = agente
    antes, despues = inicial["final"]["reportado"], residual_resumen["reba"]
    return {
        "inicial": _resumen(inicial),
        "residual": residual_resumen,
        "residual_agente": agente,
        "origen_residual": origen,
        "reduccion_puntos": antes - despues if antes is not None and despues is not None else None,
        "reduccion_pct": round(100 * (antes - despues) / antes, 1) if antes and despues is not None else None,
        "recomendaciones_aplicadas": [rec["id"] for rec in aplicadas],
        "nota": "Estimación: supone que cada control lleva el segmento al valor objetivo declarado en su efecto; "
                "el especialista debe confirmarlo con una nueva fotografía después de implementar."
                + (" Residual ajustado manualmente por el especialista." if origen == "especialista" else ""),
    }


def delta_individual(
    mediciones: dict[str, float | None], contexto: dict[str, Any], rec: dict[str, Any], config: RebaConfig,
) -> int | None:
    """Puntos REBA que reduciría esta recomendación aplicada por sí sola."""

    if not rec.get("efecto"):
        return None
    antes = calcular_reba(mediciones, contexto, config).final["reportado"]
    nuevas, nuevo_contexto = aplicar_efectos(mediciones, contexto, [rec])
    despues = calcular_reba(nuevas, nuevo_contexto, config).final["reportado"]
    return antes - despues if antes is not None and despues is not None else None
