"""Reporte de precisión de la beta contra referencias de Jabil (criterios 1 y 2 de la rúbrica).

Estructura de un caso de validación (``data/validacion/<caso>/``):

- ``frente.jpg``, ``costado.jpg``, ``aerea.jpg`` (las disponibles) y ``contexto.json`` como en un caso normal.
- ``referencia.json`` con al menos una de estas fuentes:
  - ``"reba": {"puntaje": 9, "nivel": "Alto"}``: el resultado REBA de la referencia de Jabil (criterio 1).
  - ``"angulos": [{"medida": "tronco_flexion", "lado": null, "valor_deg": 35}, ...]``: ángulos medidos por
    el especialista (goniómetro o estudio de Jabil).
  - ``"vistas": {...}``: landmarks anotados a mano con ``scripts/anotar_manual.py``; los ángulos se calculan
    con las mismas fórmulas del sistema.

El criterio 2 compara cada ángulo por su banda REBA propia (``reba.banda_medida``), igual para el sistema y
la referencia. Una medida que la referencia tiene y el sistema no estimó cuenta como fallo.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from html import escape
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from .config import Configuracion, cargar_configuracion
from .precision import angulos_desde_landmarks_referencia
from .reba import banda_medida, nivel_riesgo

PRINCIPALES = ("tronco_flexion", "cuello_flexion", "brazo_flexion", "codo_flexion", "muneca_flexion_extension", "rodilla_flexion")
AJUSTES = ("tronco_torsion", "tronco_inclinacion_lateral", "brazo_abduccion", "cuello_inclinacion_rotacion", "apoyo_piernas_unilateral")
NOMBRES = {
    "tronco_flexion": "Flexión de tronco", "cuello_flexion": "Flexión de cuello", "brazo_flexion": "Flexión de brazo",
    "codo_flexion": "Ángulo de codo", "muneca_flexion_extension": "Flexión de muñeca", "rodilla_flexion": "Flexión de rodilla",
    "tronco_torsion": "Torsión de tronco", "tronco_inclinacion_lateral": "Inclinación lateral", "brazo_abduccion": "Abducción de brazo",
    "cuello_inclinacion_rotacion": "Giro de cuello", "apoyo_piernas_unilateral": "Apoyo en una pierna",
}

PLANTILLA = {
    "caso_id": "",
    "fuente": "Estudio ergonómico de Jabil (completar)",
    "reba": {"puntaje": None, "nivel": None},
    "angulos": [{"medida": medida, "lado": lado, "valor_deg": None}
                for medida in PRINCIPALES for lado in ((None,) if medida in ("tronco_flexion", "cuello_flexion") else ("L", "R"))],
}


def _clave(medida: str, lado: str | None) -> tuple[str, str | None]:
    return medida, None if medida == "cuello_flexion" or lado not in ("L", "R") else lado


def cargar_referencia(carpeta: Path, configuracion: Configuracion) -> dict[str, Any]:
    """Normaliza ``referencia.json`` a {reba: {puntaje, nivel}, angulos: [...], fuente}."""

    datos = json.loads((carpeta / "referencia.json").read_text(encoding="utf-8"))
    angulos = [a for a in datos.get("angulos", []) if a.get("valor_deg") is not None]
    reba = dict(datos.get("reba") or {})
    fuente = datos.get("fuente") or ("angulos" if angulos else "")
    if not angulos and datos.get("vistas"):
        ruta_contexto = carpeta / "contexto.json"
        contexto = json.loads(ruta_contexto.read_text(encoding="utf-8")) if ruta_contexto.is_file() else {}
        calculada = angulos_desde_landmarks_referencia(datos, contexto, configuracion)
        angulos = [a for a in calculada["angulos"] if a.get("valor_deg") is not None]
        if reba.get("puntaje") is None:
            final = calculada["reba"]["final"]["reportado"]
            reba = {"puntaje": final, "nivel": calculada["reba"]["nivel_riesgo"]}
        fuente = fuente or "landmarks anotados a mano"
    if reba.get("puntaje") is not None and not reba.get("nivel"):
        reba["nivel"] = nivel_riesgo(int(reba["puntaje"])).nombre
    return {"reba": {"puntaje": reba.get("puntaje"), "nivel": reba.get("nivel")}, "angulos": angulos, "fuente": fuente}


def comparar_caso(caso_id: str, resultado: dict[str, Any], referencia: dict[str, Any], configuracion: Configuracion) -> dict[str, Any]:
    """Filas por ángulo (misma banda REBA, error) y coincidencia del REBA del caso."""

    cfg = configuracion.reba
    automaticos = {_clave(a["medida"], a.get("lado")): a for a in resultado.get("angulos", [])}
    filas = []
    for ref in referencia["angulos"]:
        medida, lado = _clave(ref["medida"], ref.get("lado"))
        auto = automaticos.get((medida, lado))
        valor_auto = None if auto is None else auto.get("valor_deg")
        valor_ref = float(ref["valor_deg"])
        banda_ref = banda_medida(medida, valor_ref, cfg)
        banda_auto = banda_medida(medida, valor_auto, cfg)
        filas.append({
            "caso_id": caso_id, "medida": medida, "lado": lado, "tipo": "principal" if medida in PRINCIPALES else "ajuste",
            "valor_sistema": valor_auto, "valor_referencia": valor_ref,
            "error_deg": None if valor_auto is None or medida == "apoyo_piernas_unilateral" else abs(float(valor_auto) - valor_ref),
            "banda_sistema": banda_auto, "banda_referencia": banda_ref,
            "misma_banda": banda_auto is not None and banda_auto == banda_ref,
            "estimado": valor_auto is not None,
            "vista": None if auto is None else auto.get("vista"),
            "respaldo": bool(auto and "vista_respaldo" in auto.get("banderas", [])),
            "banderas": [] if auto is None else auto.get("banderas", []),
        })
    reba = resultado.get("reba", {})
    puntaje, nivel = reba.get("final", {}).get("reportado"), reba.get("nivel_riesgo")
    ref_puntaje, ref_nivel = referencia["reba"]["puntaje"], referencia["reba"]["nivel"]
    comparable = ref_puntaje is not None
    return {
        "caso_id": caso_id, "fuente": referencia["fuente"], "filas": filas,
        "reba_sistema": puntaje, "nivel_sistema": nivel, "reba_referencia": ref_puntaje, "nivel_referencia": ref_nivel,
        "reba_comparable": comparable,
        "reba_coincide": comparable and puntaje is not None and int(puntaje) == int(ref_puntaje) and nivel == ref_nivel,
        "pendientes": len(resultado.get("pendientes_manuales", [])),
    }


def _rubrica_c1(coinciden: int, total: int) -> str:
    if total == 0:
        return "sin referencias REBA"
    faltan = max(0, 6 - total)
    nota = f" (con {total} de 6 casos)" if faltan else ""
    return ("Excelente (19-20)" if coinciden >= 6 else "Bueno (15-18)" if coinciden == 5 else "Suficiente (11-14)" if coinciden == 4 else "Insuficiente (0-10)") + nota


def _rubrica_c2(porcentaje: float | None) -> str:
    if porcentaje is None:
        return "sin ángulos de referencia"
    return "Excelente (14-15)" if porcentaje >= 90 else "Bueno (11-13)" if porcentaje >= 75 else "Suficiente (8-10)" if porcentaje >= 60 else "Insuficiente (0-7)"


def resumir(casos: list[dict[str, Any]]) -> dict[str, Any]:
    filas = [f for c in casos for f in c["filas"]]
    principales = [f for f in filas if f["tipo"] == "principal"]
    estimadas = [f for f in principales if f["estimado"]]
    pct = (lambda grupo: None if not grupo else round(100 * sum(f["misma_banda"] for f in grupo) / len(grupo), 1))
    comparables = [c for c in casos if c["reba_comparable"]]
    coinciden = sum(c["reba_coincide"] for c in comparables)
    por_medida: dict[str, dict[str, Any]] = {}
    for medida in (*PRINCIPALES, *AJUSTES):
        grupo = [f for f in filas if f["medida"] == medida]
        if not grupo:
            continue
        errores = [f["error_deg"] for f in grupo if f["error_deg"] is not None]
        por_medida[medida] = {
            "n": len(grupo), "misma_banda_pct": pct(grupo), "sin_estimar": sum(not f["estimado"] for f in grupo),
            "error_medio_deg": round(mean(errores), 1) if errores else None, "error_max_deg": round(max(errores), 1) if errores else None,
            "con_respaldo": sum(f["respaldo"] for f in grupo),
        }
    por_vista: dict[str, Any] = {}
    for vista in sorted({f["vista"] for f in filas if f["vista"]}):
        grupo = [f for f in filas if f["vista"] == vista]
        por_vista[vista] = {"n": len(grupo), "misma_banda_pct": pct(grupo)}
    c2 = pct(principales)
    return {
        "generado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "casos": len(casos),
        "criterio_1": {"coinciden": coinciden, "comparables": len(comparables), "rubrica": _rubrica_c1(coinciden, len(comparables))},
        "criterio_2": {"misma_banda_pct": c2, "solo_estimadas_pct": pct(estimadas), "segmentos": len(principales),
                       "sin_estimar": len(principales) - len(estimadas), "rubrica": _rubrica_c2(c2)},
        "ajustes_misma_banda_pct": pct([f for f in filas if f["tipo"] == "ajuste"]),
        "por_medida": por_medida, "por_vista": por_vista,
    }


def _html(resumen: dict[str, Any], casos: list[dict[str, Any]]) -> str:
    c1, c2 = resumen["criterio_1"], resumen["criterio_2"]
    fmt = (lambda v, suf="": "—" if v is None else f"{v}{suf}")
    filas_casos = "".join(
        f"<tr><td>{escape(c['caso_id'])}</td><td class='n'>{fmt(c['reba_sistema'])}</td><td>{escape(c['nivel_sistema'] or 'Pendiente')}</td>"
        f"<td class='n'>{fmt(c['reba_referencia'])}</td><td>{escape(c['nivel_referencia'] or '—')}</td>"
        f"<td class='{'ok' if c['reba_coincide'] else 'mal' if c['reba_comparable'] else ''}'>{'Sí' if c['reba_coincide'] else 'No' if c['reba_comparable'] else 'Sin referencia'}</td>"
        f"<td class='n'>{sum(f['misma_banda'] for f in c['filas'] if f['tipo'] == 'principal')}/{sum(f['tipo'] == 'principal' for f in c['filas'])}</td>"
        f"<td>{escape(c['fuente'])}</td></tr>" for c in casos)
    filas_medidas = "".join(
        f"<tr><td>{escape(NOMBRES.get(m, m))}</td><td class='n'>{d['n']}</td><td class='n'>{fmt(d['misma_banda_pct'], ' %')}</td>"
        f"<td class='n'>{fmt(d['error_medio_deg'], '°')}</td><td class='n'>{fmt(d['error_max_deg'], '°')}</td><td class='n'>{d['sin_estimar']}</td><td class='n'>{d['con_respaldo']}</td></tr>"
        for m, d in resumen["por_medida"].items())
    fallos = [f for c in casos for f in c["filas"] if not f["misma_banda"]]
    filas_fallos = "".join(
        f"<tr><td>{escape(f['caso_id'])}</td><td>{escape(NOMBRES.get(f['medida'], f['medida']))}{' ' + f['lado'] if f['lado'] else ''}</td>"
        f"<td class='n'>{fmt(None if f['valor_sistema'] is None else round(f['valor_sistema'], 1), '°')}</td><td class='n'>{f['valor_referencia']:.1f}°</td>"
        f"<td class='n'>{fmt(f['banda_sistema'])} / {fmt(f['banda_referencia'])}</td><td>{escape(f['vista'] or 'sin estimar')}</td>"
        f"<td class='chico'>{escape(', '.join(f['banderas']))}</td></tr>" for f in sorted(fallos, key=lambda f: -(f['error_deg'] or 999)))
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Precisión de ErgoAI</title><style>
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#13233b;background:#fff;margin:0;padding:24px;line-height:1.45}}
main{{max-width:1050px;margin:0 auto}} h1{{font-size:1.6rem;margin:0}} h2{{font-size:1.15rem;border-bottom:2px solid #d9dee5;padding-bottom:4px;margin-top:28px}}
.sub{{color:#5b6573;margin:4px 0 16px}} .tarjetas{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
.tarjeta{{background:#f5f7fa;border:1px solid #d9dee5;border-radius:8px;padding:14px}} .tarjeta .v{{font-size:1.8rem;font-weight:700}}
.tarjeta .t{{color:#5b6573;font-size:.85rem}} table{{width:100%;border-collapse:collapse;font-size:.88rem;margin:8px 0}}
th,td{{border:1px solid #d9dee5;padding:6px 8px;text-align:left;vertical-align:top}} th{{background:#f5f7fa}} td.n{{text-align:center;white-space:nowrap}}
td.ok{{color:#1f6b38;font-weight:600}} td.mal{{color:#b42318;font-weight:600}} .chico{{font-size:.78rem;color:#5b6573}} .nota{{color:#5b6573;font-size:.85rem}}
</style></head><body><main>
<h1>Precisión de ErgoAI contra la referencia</h1>
<p class="sub">{resumen['casos']} casos de validación. Generado {escape(resumen['generado'])}. Criterios 1 y 2 de la rúbrica del Track 4.</p>
<section class="tarjetas">
<div class="tarjeta"><div class="t">Criterio 1: REBA y nivel coinciden</div><div class="v">{c1['coinciden']} de {c1['comparables']}</div><div class="t">{escape(c1['rubrica'])}</div></div>
<div class="tarjeta"><div class="t">Criterio 2: segmentos en la misma banda REBA</div><div class="v">{fmt(c2['misma_banda_pct'], ' %')}</div><div class="t">{escape(c2['rubrica'])}; {c2['segmentos']} segmentos, {c2['sin_estimar']} sin estimar</div></div>
<div class="tarjeta"><div class="t">Solo segmentos estimados</div><div class="v">{fmt(c2['solo_estimadas_pct'], ' %')}</div><div class="t">Ajustes (torsión, inclinación, abducción…): {fmt(resumen['ajustes_misma_banda_pct'], ' %')}</div></div>
</section>
<h2>Casos</h2>
<table><thead><tr><th>Caso</th><th>REBA sistema</th><th>Nivel</th><th>REBA referencia</th><th>Nivel</th><th>Coincide</th><th>Segmentos en banda</th><th>Fuente de la referencia</th></tr></thead><tbody>{filas_casos}</tbody></table>
<h2>Por segmento</h2>
<table><thead><tr><th>Medida</th><th>n</th><th>Misma banda</th><th>Error medio</th><th>Error máx.</th><th>Sin estimar</th><th>Con respaldo</th></tr></thead><tbody>{filas_medidas}</tbody></table>
<h2>Segmentos fuera de banda o sin estimar</h2>
{'<p>Ninguno.</p>' if not fallos else f'<table><thead><tr><th>Caso</th><th>Medida</th><th>Sistema</th><th>Referencia</th><th>Banda sistema / ref.</th><th>Vista</th><th>Banderas</th></tr></thead><tbody>{filas_fallos}</tbody></table>'}
<p class="nota">El criterio 2 compara la banda REBA propia de cada ángulo, calculada igual para el sistema y la referencia; una medida sin estimar cuenta como fuera de banda.
Los ajustes (torsión, inclinación lateral, abducción, giro de cuello, apoyo) se reportan aparte. Protocolo: docs/PROTOCOLO_VALIDACION.md.</p>
</main></body></html>"""


def generar_reporte(validacion: Path, raiz: Path, salida: Path, reusar: bool = False,
                    evaluar: Callable[[Path, Path, Path], Path] | None = None) -> dict[str, Any]:
    """Evalúa cada caso de ``validacion`` en ``salida`` y escribe reporte.html, precision.csv y resumen.json."""

    from .cli import ejecutar_evaluar

    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    evaluar = evaluar or (lambda caso, r, destino: ejecutar_evaluar(caso, r, None, destino))
    salida.mkdir(parents=True, exist_ok=True)
    casos = []
    for carpeta in sorted(p for p in validacion.iterdir() if (p / "referencia.json").is_file()):
        contexto = json.loads((carpeta / "contexto.json").read_text(encoding="utf-8")) if (carpeta / "contexto.json").is_file() else {}
        caso_id = str(contexto.get("caso_id", carpeta.name))
        resultado_ruta = salida / caso_id / "resultado.json"
        if not (reusar and resultado_ruta.is_file()):
            resultado_ruta = evaluar(carpeta, raiz, salida)
        resultado = json.loads(resultado_ruta.read_text(encoding="utf-8"))
        casos.append(comparar_caso(caso_id, resultado, cargar_referencia(carpeta, configuracion), configuracion))
    resumen = resumir(casos)
    (salida / "resumen.json").write_text(json.dumps({**resumen, "detalle": casos}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (salida / "precision.csv").open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["caso_id", "medida", "lado", "tipo", "valor_sistema", "valor_referencia", "error_deg", "banda_sistema", "banda_referencia", "misma_banda", "vista", "respaldo", "banderas"])
        for caso in casos:
            for f in caso["filas"]:
                escritor.writerow([f["caso_id"], f["medida"], f["lado"] or "", f["tipo"], f["valor_sistema"], f["valor_referencia"], f["error_deg"],
                                   f["banda_sistema"], f["banda_referencia"], f["misma_banda"], f["vista"] or "", f["respaldo"], ";".join(f["banderas"])])
    (salida / "reporte.html").write_text(_html(resumen, casos), encoding="utf-8")
    return resumen


def crear_plantilla(carpeta: Path) -> Path:
    """Crea ``referencia.json`` para completar a mano (no sobrescribe uno existente)."""

    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "referencia.json"
    if ruta.exists():
        raise FileExistsError(f"Ya existe {ruta}; edítalo en lugar de crear uno nuevo.")
    ruta.write_text(json.dumps({**PLANTILLA, "caso_id": carpeta.name}, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta
