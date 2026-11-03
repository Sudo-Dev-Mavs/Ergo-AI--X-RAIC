"""Recálculo de riesgo residual con el mismo motor REBA (R7)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config import RebaConfig
from .reba import ResultadoReba, calcular_reba
from .recomendaciones import Recomendacion


def aplicar_cambios(
    mediciones: dict[str, float | None],
    contexto: dict[str, Any],
    cambios: dict[str, Any],
) -> tuple[dict[str, float | None], dict[str, Any], list[str]]:
    """Aplica cambios calculables. No inventa reducciones sin dato."""

    nuevas_med = dict(mediciones)
    nuevo_ctx = deepcopy(contexto)
    supuestos: list[str] = []
    for clave, valor in cambios.items():
        if clave == "carga_kg":
            nuevo_ctx["carga_kg"] = float(valor)
            supuestos.append(f"carga_kg → {valor}")
        elif clave == "agarre":
            nuevo_ctx["agarre"] = str(valor)
            supuestos.append(f"agarre → {valor}")
        elif clave == "actividad" and isinstance(valor, dict):
            nuevo_ctx["actividad"] = dict(valor)
            supuestos.append("actividad ajustada (estática/repetitiva)")
        elif clave in nuevas_med or clave.endswith(("_L", "_R")) or clave in {
            "tronco_flexion",
            "cuello_flexion",
            "tronco_torsion",
            "tronco_inclinacion_lateral",
            "cuello_inclinacion_rotacion",
            "apoyo_piernas_unilateral",
        }:
            nuevas_med[clave] = None if valor is None else float(valor)
            supuestos.append(f"{clave} → {valor}")
        else:
            supuestos.append(f"cambio no aplicado (clave desconocida): {clave}")
    return nuevas_med, nuevo_ctx, supuestos


def consolidar_cambios(recomendaciones: list[Recomendacion], solo_estados: set[str] | None = None) -> dict[str, Any]:
    """Une cambios esperados de recomendaciones seleccionadas."""

    estados = solo_estados or {"propuesta", "en_revision", "editada", "aprobada"}
    consolidado: dict[str, Any] = {}
    for item in recomendaciones:
        if item.estado not in estados:
            continue
        for clave, valor in item.cambio_esperado.items():
            consolidado[clave] = valor
    return consolidado


def recalcular_residual(
    mediciones: dict[str, float | None],
    contexto: dict[str, Any],
    config: RebaConfig,
    recomendaciones: list[Recomendacion],
    inicial: ResultadoReba | None = None,
) -> dict[str, Any]:
    """REBA inicial vs residual con supuestos explícitos."""

    base = inicial or calcular_reba(mediciones, contexto, config)
    cambios = consolidar_cambios(recomendaciones)
    if not cambios:
        return {
            "puntaje_inicial": (base.final or {}).get("reportado"),
            "nivel_inicial": base.nivel_riesgo,
            "puntaje_residual": (base.final or {}).get("reportado"),
            "nivel_residual": base.nivel_riesgo,
            "delta": 0,
            "supuestos": ["Sin cambios calculables aplicados."],
            "cambios_aplicados": {},
            "reba_residual": base.a_diccionario(),
        }

    nuevas_med, nuevo_ctx, supuestos = aplicar_cambios(mediciones, contexto, cambios)
    residual = calcular_reba(nuevas_med, nuevo_ctx, config)
    inicial_n = (base.final or {}).get("reportado")
    residual_n = (residual.final or {}).get("reportado")
    delta = None if inicial_n is None or residual_n is None else int(residual_n) - int(inicial_n)
    return {
        "puntaje_inicial": inicial_n,
        "nivel_inicial": base.nivel_riesgo,
        "puntaje_residual": residual_n,
        "nivel_residual": residual.nivel_riesgo,
        "delta": delta,
        "supuestos": supuestos,
        "cambios_aplicados": cambios,
        "reba_residual": residual.a_diccionario(),
    }
