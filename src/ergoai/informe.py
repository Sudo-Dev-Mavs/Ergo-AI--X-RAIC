"""Informe del estudio de evaluación ergonómica (HTML autocontenido + CSV formato 00014)."""

from __future__ import annotations

import base64
import csv
import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .config import RebaConfig
from .recomendaciones import ETIQUETA_JERARQUIA, JERARQUIAS
from .residual import calcular_residual
from .validacion import bloqueos_aprobacion, cargar, verificar_bitacora

COLOR_RIESGO = {"Inapreciable": "#3c8d5a", "Bajo": "#5aa469", "Medio": "#d9a400", "Alto": "#e06c00", "Muy alto": "#c62828", None: "#888"}
ETIQUETA_ESTADO = {"propuesta": "Propuesta (sin validar)", "aprobada": "Aprobada", "rechazada": "Rechazada", "obsoleta": "Obsoleta"}
NOMBRE_MEDIDA = {
    "tronco_flexion": "Tronco · flexión", "tronco_torsion": "Tronco · torsión", "tronco_inclinacion_lateral": "Tronco · inclinación lateral",
    "cuello_flexion": "Cuello · flexión", "cuello_inclinacion_rotacion": "Cuello · inclinación/giro",
    "brazo_flexion": "Brazo · flexión", "brazo_abduccion": "Brazo · abducción", "codo_flexion": "Codo (antebrazo)",
    "muneca_flexion_extension": "Muñeca · flexión/extensión", "rodilla_flexion": "Rodilla · flexión",
    "apoyo_piernas_unilateral": "Apoyo unilateral (1 = sí)",
}
NOMBRE_TAREA = {"levantamiento": "Levantamiento", "transporte_con_auxiliar": "Transporte con auxiliar",
                "transporte_sin_auxiliar": "Transporte sin auxiliar", "otro": "Otra tarea"}


def cargar_estado(carpeta: Path, config: RebaConfig) -> dict[str, Any]:
    """Reúne resultado, validación y riesgo residual vigente de un caso."""

    resultado = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
    validacion = cargar(carpeta) or {"estado_informe": "borrador", "recomendaciones": resultado.get("recomendaciones", []), "bitacora": []}
    residual = calcular_residual(resultado.get("mediciones_reba", {}), resultado.get("contexto", {}), validacion["recomendaciones"], config)
    return {"resultado": resultado, "validacion": validacion, "residual": residual}


def _insignia(nivel: str | None, puntaje: Any) -> str:
    color = COLOR_RIESGO.get(nivel, "#888")
    return f'<span class="insignia" style="background:{color}">REBA {escape(str(puntaje if puntaje is not None else "—"))} · {escape(nivel or "Pendiente")}</span>'


def _imagenes(carpeta: Path) -> str:
    partes = []
    for vista in ("costado", "frente", "aerea"):
        ruta = carpeta / f"{vista}_angulos.png"
        if ruta.is_file():
            datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
            partes.append(f'<figure><img src="data:image/png;base64,{datos}" alt="Vista {vista}"><figcaption>Vista {vista}</figcaption></figure>')
    return "".join(partes) or "<p class='nota'>Sin imágenes anotadas.</p>"


def _tabla_angulos(resultado: dict[str, Any]) -> str:
    filas = []
    for angulo in resultado.get("angulos", []):
        valor = angulo.get("valor_deg")
        nombre = NOMBRE_MEDIDA.get(angulo["medida"], angulo["medida"])
        lado = {"L": "Izq.", "R": "Der."}.get(angulo.get("lado") or "", "")
        fuente = "Especialista" if angulo.get("fuente") == "especialista" else "Automática"
        banderas = ", ".join(angulo.get("banderas") or []) or ""
        unidad = "" if angulo["medida"] == "apoyo_piernas_unilateral" else "°"
        texto_valor = "—" if valor is None else f"{valor:.0f}" if not unidad else f"{valor:.1f}°"
        filas.append(
            f"<tr><td>{escape(nombre)}</td><td>{lado}</td><td class='num'>{texto_valor}</td>"
            f"<td class='num'>{escape(str(angulo.get('banda_reba') or '—'))}</td><td>{escape(angulo.get('vista') or '')}</td>"
            f"<td>{fuente}</td><td class='chico'>{escape(banderas)}</td></tr>"
        )
    return ("<table><thead><tr><th>Segmento</th><th>Lado</th><th>Ángulo</th><th>Banda REBA</th><th>Vista</th><th>Fuente</th><th>Banderas</th></tr></thead>"
            f"<tbody>{''.join(filas)}</tbody></table>")


def _tabla_bandas(residual: dict[str, Any]) -> str:
    nombres = {"tronco": "Tronco", "cuello": "Cuello", "piernas": "Piernas", "carga": "Carga/fuerza", "actividad": "Actividad",
               "brazo_L": "Brazo izq.", "brazo_R": "Brazo der.", "antebrazo_L": "Antebrazo izq.", "antebrazo_R": "Antebrazo der.",
               "muneca_L": "Muñeca izq.", "muneca_R": "Muñeca der.", "agarre_L": "Agarre"}
    filas = []
    for clave, nombre in nombres.items():
        antes, despues = residual["inicial"]["bandas"].get(clave), residual["residual"]["bandas"].get(clave)
        clase = " class='mejora'" if antes is not None and despues is not None and despues < antes else ""
        filas.append(f"<tr{clase}><td>{nombre}</td><td class='num'>{'—' if antes is None else antes}</td><td class='num'>{'—' if despues is None else despues}</td></tr>")
    return f"<table class='compacta'><thead><tr><th>Componente</th><th>Inicial</th><th>Residual</th></tr></thead><tbody>{''.join(filas)}</tbody></table>"


def _tabla_recomendaciones(recs: list[dict[str, Any]], aprobado: bool) -> str:
    bloques = []
    for jerarquia in JERARQUIAS:
        grupo = [rec for rec in recs if rec.get("jerarquia") == jerarquia and rec.get("estado") != "obsoleta"]
        if not grupo:
            continue
        filas = []
        for rec in grupo:
            estado = rec.get("estado", "propuesta")
            delta = rec.get("delta_reba")
            refs = "<br>".join(escape(ref) for ref in rec.get("referencias", []))
            filas.append(
                f"<tr class='estado-{estado}'><td><b>{escape(rec['id'])}</b><br><span class='chico'>{escape(rec.get('prioridad', ''))}</span></td>"
                f"<td>{escape(rec['problema'])}</td><td>{escape(rec['solucion'])}<div class='refs'>{refs}</div></td>"
                f"<td class='num'>{'—' if delta is None else f'−{delta}' if delta > 0 else '0'}</td>"
                f"<td>{escape(ETIQUETA_ESTADO.get(estado, estado))}{'<br><i>' + escape(rec['comentario']) + '</i>' if rec.get('comentario') else ''}</td>"
                f"<td>{escape(rec.get('responsable') or '—')}<br><span class='chico'>{escape(rec.get('fecha_compromiso') or '')}</span></td></tr>"
            )
        bloques.append(
            f"<h3>{len(bloques) + 1}. {ETIQUETA_JERARQUIA[jerarquia]}</h3>"
            "<table><thead><tr><th>ID</th><th>Problema detectado</th><th>Recomendación y fundamento</th><th>Δ REBA</th><th>Validación</th><th>Responsable / fecha</th></tr></thead>"
            f"<tbody>{''.join(filas)}</tbody></table>"
        )
    if not bloques:
        return "<p>No se detectaron factores que requieran recomendación.</p>"
    aviso = "" if aprobado else "<p class='aviso'>Propuestas del agente: <b>no son acciones de piso</b> hasta que el especialista las apruebe.</p>"
    return aviso + "".join(bloques)


def _bitacora(validacion: dict[str, Any]) -> str:
    filas = []
    for entrada in validacion.get("bitacora", []):
        cambios = "; ".join(f"{campo}: «{escape(str(v.get('antes')))}» → «{escape(str(v.get('despues')))}»" for campo, v in entrada.get("cambios", {}).items())
        filas.append(f"<tr><td class='num'>{entrada['n']}</td><td class='chico'>{escape(entrada['fecha'])}</td><td>{escape(entrada['usuario'])}</td>"
                     f"<td>{escape(entrada['accion'])}</td><td>{escape(entrada.get('rec_id') or '')}</td><td class='chico'>{cambios}</td>"
                     f"<td class='chico'>{escape(entrada.get('comentario') or '')}</td></tr>")
    integridad = "íntegra (cadena SHA-256 verificada)" if verificar_bitacora(validacion) else "⚠ ALTERADA: la cadena de hashes no coincide"
    return (f"<p class='chico'>Integridad de la bitácora: <b>{integridad}</b></p><table><thead><tr><th>#</th><th>Fecha</th><th>Usuario</th><th>Acción</th>"
            f"<th>Rec.</th><th>Cambios</th><th>Comentario</th></tr></thead><tbody>{''.join(filas)}</tbody></table>")


def _minutos_validacion(validacion: dict[str, Any]) -> float | None:
    try:
        inicio = datetime.fromisoformat(validacion["generado_en"])
        fin = datetime.fromisoformat(validacion["aprobado_en"])
    except (KeyError, TypeError, ValueError):
        return None
    return round((fin - inicio).total_seconds() / 60, 1)


def generar_csv_00014(carpeta: Path, estado: dict[str, Any]) -> Path:
    """Acciones con las columnas de la hoja «OBSERVACIONES Y MEJORAS» del formato 00014."""

    ruta = carpeta / "acciones_00014.csv"
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["# Evaluación", "Identificador", "Problema", "Solución - Mejoras", "Jerarquía", "Responsable", "Fecha compromiso", "Estado"])
        for rec in estado["validacion"]["recomendaciones"]:
            if rec.get("estado") in ("aprobada", "propuesta"):
                escritor.writerow([estado["resultado"].get("caso_id"), rec["id"], rec["problema"], rec["solucion"],
                                   ETIQUETA_JERARQUIA.get(rec.get("jerarquia"), rec.get("jerarquia")), rec.get("responsable", ""),
                                   rec.get("fecha_compromiso", ""), rec.get("estado")])
    return ruta


def generar_informe(carpeta: Path, config: RebaConfig) -> Path:
    """Escribe ``informe.html`` y ``acciones_00014.csv`` con el estado vigente del caso."""

    estado = cargar_estado(carpeta, config)
    resultado, validacion, residual = estado["resultado"], estado["validacion"], estado["residual"]
    contexto = resultado.get("contexto", {})
    reba = resultado.get("reba", {})
    aprobado = validacion.get("estado_informe") == "aprobado"
    ini, res = residual["inicial"], residual["residual"]
    reduccion = residual.get("reduccion_puntos")
    tiempo = (resultado.get("tiempos_s") or {}).get("analisis_total")
    minutos_validacion = _minutos_validacion(validacion)
    bloqueos = [] if aprobado else bloqueos_aprobacion(validacion, reba.get("nivel_accion"))
    pendientes = resultado.get("pendientes_manuales", [])
    sello = (f"<div class='sello ok'>APROBADO por {escape(validacion.get('aprobado_por') or '')} · {escape(validacion.get('aprobado_en') or '')}</div>"
             if aprobado else "<div class='sello borrador'>BORRADOR · pendiente de validación del especialista</div>")
    actividad = contexto.get("actividad") or {}
    datos_contexto = [
        ("Caso", resultado.get("caso_id")), ("Tipo de tarea", NOMBRE_TAREA.get(contexto.get("tipo_tarea") or "otro")),
        ("Postura", contexto.get("postura")), ("Carga", f"{contexto.get('carga_kg')} kg"), ("Agarre", contexto.get("agarre")),
        ("Actividad", ", ".join(k.replace("_", " ") for k, v in actividad.items() if v) or "sin ajustes"),
        ("Realizado por", contexto.get("realizado_por") or "—"), ("Fecha de análisis", resultado.get("fecha_analisis") or "—"),
    ]
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe ergonómico · {escape(str(resultado.get('caso_id')))}</title>
<style>
:root {{ --tinta:#1d2430; --suave:#5b6573; --linea:#d9dee5; --fondo:#ffffff; --panel:#f5f7fa; }}
* {{ box-sizing:border-box; }}
body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color:var(--tinta); background:var(--fondo); margin:0; padding:24px; line-height:1.45; }}
main {{ max-width: 1050px; margin:0 auto; }}
h1 {{ font-size:1.6rem; margin:0 0 4px; }} h2 {{ font-size:1.2rem; border-bottom:2px solid var(--linea); padding-bottom:4px; margin-top:28px; }}
h3 {{ font-size:1rem; margin:18px 0 6px; }}
.sub {{ color:var(--suave); margin:0 0 12px; }}
.sello {{ display:inline-block; padding:6px 12px; border-radius:6px; font-weight:600; margin:8px 0; }}
.sello.borrador {{ background:#fff4d6; color:#7a5600; border:1px solid #e8c766; }} .sello.ok {{ background:#e3f4e8; color:#1f6b38; border:1px solid #8cc9a0; }}
.tarjetas {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin:12px 0; }}
.tarjeta {{ background:var(--panel); border:1px solid var(--linea); border-radius:8px; padding:12px; }}
.tarjeta .titulo {{ color:var(--suave); font-size:.85rem; }} .tarjeta .valor {{ font-size:1.25rem; font-weight:700; margin-top:4px; }}
.insignia {{ color:#fff; padding:3px 10px; border-radius:999px; font-weight:700; font-size:.95rem; white-space:nowrap; }}
table {{ width:100%; border-collapse:collapse; font-size:.88rem; margin:6px 0; }}
th, td {{ border:1px solid var(--linea); padding:6px 8px; text-align:left; vertical-align:top; }}
th {{ background:var(--panel); }} td.num {{ text-align:center; white-space:nowrap; }}
table.compacta {{ max-width:420px; }} tr.mejora td {{ background:#eef8f0; }}
tr.estado-rechazada td {{ color:#999; text-decoration:line-through; }} tr.estado-aprobada td:first-child {{ border-left:4px solid #3c8d5a; }}
tr.estado-propuesta td:first-child {{ border-left:4px solid #d9a400; }}
.refs {{ color:var(--suave); font-size:.78rem; margin-top:4px; }} .chico {{ font-size:.78rem; color:var(--suave); }}
.aviso {{ background:#fff4d6; border-left:4px solid #d9a400; padding:8px 12px; }} .nota {{ color:var(--suave); font-size:.85rem; }}
dl {{ display:grid; grid-template-columns: max-content 1fr; gap:4px 16px; margin:0; }} dt {{ color:var(--suave); }} dd {{ margin:0; }}
.imagenes {{ display:flex; flex-wrap:wrap; gap:12px; }} figure {{ margin:0; flex:1 1 300px; }} figure img {{ width:100%; border:1px solid var(--linea); border-radius:6px; }}
figcaption {{ font-size:.8rem; color:var(--suave); }}
@media print {{ body {{ padding:0; }} h2 {{ break-after:avoid; }} table, figure {{ break-inside:avoid; }} }}
</style></head><body><main>
<h1>Estudio de evaluación ergonómica</h1>
<p class="sub">ErgoAI · método REBA con recomendaciones basadas en la NOM-036-1-STPS-2018 y lineamientos Jabil · procesado localmente</p>
{sello}
<section class="tarjetas">
  <div class="tarjeta"><div class="titulo">Riesgo inicial</div><div class="valor">{_insignia(ini['nivel_riesgo'], ini['reba'])}</div><div class="chico">Nivel de acción {ini['nivel_accion'] if ini['nivel_accion'] is not None else '—'}</div></div>
  <div class="tarjeta"><div class="titulo">Riesgo residual esperado</div><div class="valor">{_insignia(res['nivel_riesgo'], res['reba'])}</div><div class="chico">con {len(residual['recomendaciones_aplicadas'])} {'control vigente' if len(residual['recomendaciones_aplicadas']) == 1 else 'controles vigentes'}</div></div>
  <div class="tarjeta"><div class="titulo">Reducción</div><div class="valor">{'—' if reduccion is None else f"{'−' if reduccion > 0 else ''}{reduccion} pts ({residual['reduccion_pct']} %)"}</div></div>
  <div class="tarjeta"><div class="titulo">Tiempo del agente</div><div class="valor">{'—' if tiempo is None else f'{tiempo:.1f} s'}</div><div class="chico">{'Validación humana: ' + str(minutos_validacion) + ' min' if minutos_validacion is not None else 'análisis + borrador del informe'}</div></div>
</section>

<h2>1. Datos del caso</h2>
<dl>{''.join(f'<dt>{escape(k)}</dt><dd>{escape(str(v))}</dd>' for k, v in datos_contexto)}</dl>

<h2>2. Postura evaluada</h2>
<div class="imagenes">{_imagenes(carpeta)}</div>
{_tabla_angulos(resultado)}

<h2>3. Puntuación REBA</h2>
<p>Grupo A (tronco {reba.get('grupo_a', {}).get('tronco')}, cuello {reba.get('grupo_a', {}).get('cuello')}, piernas {reba.get('grupo_a', {}).get('piernas')}) → Tabla A {reba.get('grupo_a', {}).get('tabla_a')} + carga {reba.get('grupo_a', {}).get('carga')} = <b>{reba.get('grupo_a', {}).get('puntaje_a')}</b>.
Lado reportado: {escape(str(reba.get('final', {}).get('lado')))} (izq. {reba.get('final', {}).get('L')}, der. {reba.get('final', {}).get('R')}); actividad +{reba.get('actividad')}.
Resultado: {_insignia(reba.get('nivel_riesgo'), reba.get('final', {}).get('reportado'))}</p>
{('<p class="aviso">Datos pendientes de revisión manual: ' + escape(', '.join(sorted({p.get('medida', '') for p in pendientes}))) + '</p>') if pendientes else ''}

<h2>4. Recomendaciones jerarquizadas</h2>
<p class="nota">Orden de prioridad: controles de ingeniería → rediseño de estación → medidas administrativas. Δ REBA = puntos que reduce cada recomendación por sí sola.</p>
{_tabla_recomendaciones(validacion['recomendaciones'], aprobado)}

<h2>5. Riesgo residual</h2>
<p>REBA inicial <b>{ini['reba'] if ini['reba'] is not None else '—'}</b> ({escape(ini['nivel_riesgo'] or 'pendiente')}) → residual esperado <b>{res['reba'] if res['reba'] is not None else '—'}</b> ({escape(res['nivel_riesgo'] or 'pendiente')}),
recalculado con el mismo método REBA aplicando los controles vigentes: {escape(', '.join(residual['recomendaciones_aplicadas']) or 'ninguno')}.</p>
{_tabla_bandas(residual)}
<p class="nota">{escape(residual['nota'])} Las medidas administrativas no se cuentan en el residual.</p>

<h2>6. Validación del especialista</h2>
{('<p class="aviso">Para aprobar falta: ' + escape('; '.join(bloqueos)) + '</p>') if bloqueos else ''}
{_bitacora(validacion)}

<h2>7. Alcance y limitaciones</h2>
<p class="nota">ErgoAI es una ayuda para el especialista y no lo sustituye. Los ángulos se estiman con visión por computadora (MediaPipe) sobre fotografías 2D;
los valores marcados con banderas o pendientes deben confirmarse en piso. Las imágenes y resultados se procesan y guardan solo en este equipo.</p>
</main></body></html>"""
    ruta = carpeta / "informe.html"
    ruta.write_text(html, encoding="utf-8")
    generar_csv_00014(carpeta, estado)
    return ruta
