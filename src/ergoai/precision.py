"""Comparación determinista entre resultados automáticos y referencias manuales."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

from .angulos import medir_vista
from .config import Configuracion
from .modelos import Landmark, VistaPose, WorldLandmark
from .reba import calcular_reba, clave_reba


@dataclass(frozen=True)
class FilaPrecision:
    caso_id: str
    medida: str
    lado: str | None
    error_absoluto_deg: float
    misma_banda_reba: bool | None
    vista: str | None
    banderas: str


def angulos_desde_landmarks_referencia(referencia: dict[str, Any], contexto: dict[str, Any], configuracion: Configuracion) -> dict[str, Any]:
    """Calcula las referencias con las mismas fórmulas de Fase 2 y 3."""

    angulos: list[dict[str, Any]] = []
    for nombre, datos in referencia.get("vistas", {}).items():
        landmarks = [Landmark(**punto) for punto in datos.get("landmarks", [])]
        mundo = [WorldLandmark(**punto) for punto in datos.get("world_landmarks", [])]
        vista = VistaPose(nombre, int(datos.get("ancho") or 0), int(datos.get("alto") or 0), True, 1, landmarks=landmarks, world_landmarks=mundo)
        _, mediciones, _ = medir_vista(vista, configuracion, contexto)
        for medicion in mediciones:
            dato = medicion.a_diccionario()
            dato["fuente"] = "manual"
            angulos.append(dato)
    mediciones_reba: dict[str, float | None] = {}
    for angulo in angulos:
        mediciones_reba[clave_reba(angulo["medida"], angulo.get("lado"))] = angulo["valor_deg"]
    reba = calcular_reba(mediciones_reba, contexto, configuracion.reba)
    for angulo in angulos:
        lado = angulo.get("lado")
        if angulo["medida"] == "tronco_flexion":
            angulo["banda_reba"] = reba.grupo_a["tronco"]
        elif angulo["medida"] == "cuello_flexion":
            angulo["banda_reba"] = reba.grupo_a["cuello"]
        elif angulo["medida"] == "rodilla_flexion":
            angulo["banda_reba"] = reba.grupo_a["piernas"]
        elif lado in ("L", "R"):
            campo = {"brazo_flexion": "brazo", "codo_flexion": "antebrazo", "muneca_flexion_extension": "muneca"}.get(angulo["medida"])
            if campo:
                angulo["banda_reba"] = reba.grupo_b[lado][campo]
    return {"caso_id": referencia.get("caso_id"), "angulos": angulos, "reba": reba.a_diccionario()}


def comparar_angulos(caso_id: str, automaticos: list[dict[str, Any]], referencias: list[dict[str, Any]]) -> list[FilaPrecision]:
    """Compara ángulos por medida/lado, sin mezclar valores no medibles."""

    indice = {(angulo.get("medida"), angulo.get("lado")): angulo for angulo in referencias}
    filas: list[FilaPrecision] = []
    for automatico in automaticos:
        referencia = indice.get((automatico.get("medida"), automatico.get("lado")))
        if referencia is None or automatico.get("valor_deg") is None or referencia.get("valor_deg") is None:
            continue
        banda_auto, banda_referencia = automatico.get("banda_reba"), referencia.get("banda_reba")
        misma_banda = None if banda_auto is None or banda_referencia is None else banda_auto == banda_referencia
        filas.append(FilaPrecision(
            caso_id, str(automatico["medida"]), automatico.get("lado"),
            abs(float(automatico["valor_deg"]) - float(referencia["valor_deg"])), misma_banda,
            automatico.get("vista"), ",".join(automatico.get("banderas", [])),
        ))
    return filas


def resumir_precision(filas: list[FilaPrecision], casos: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """Calcula métricas de la Fase 4 y conserva el detalle de fallos."""

    por_medida: dict[str, list[float]] = defaultdict(list)
    for fila in filas:
        por_medida[fila.medida].append(fila.error_absoluto_deg)
    segmentos_banda = [fila for fila in filas if fila.misma_banda_reba is not None]
    coincidencias = 0
    comparables = 0
    for automatico, referencia in casos:
        a, r = automatico.get("reba", {}), referencia.get("reba", {})
        if a.get("final", {}).get("reportado") is None or r.get("final", {}).get("reportado") is None:
            continue
        comparables += 1
        if a["final"]["reportado"] == r["final"]["reportado"] and a.get("nivel_riesgo") == r.get("nivel_riesgo"):
            coincidencias += 1
    return {
        "error_por_segmento": {medida: {"media": mean(errores), "maximo": max(errores)} for medida, errores in sorted(por_medida.items())},
        "porcentaje_misma_banda_reba": None if not segmentos_banda else 100 * sum(bool(fila.misma_banda_reba) for fila in segmentos_banda) / len(segmentos_banda),
        "porcentaje_mismo_reba_y_nivel": None if not comparables else 100 * coincidencias / comparables,
        "fallos": [fila for fila in sorted(filas, key=lambda fila: fila.error_absoluto_deg, reverse=True)],
    }
