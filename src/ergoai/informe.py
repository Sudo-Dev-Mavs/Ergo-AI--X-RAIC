"""Generador de informe por caso. No inventa puntajes ni reducciones."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .presentacion import ETIQUETAS_VISTA, formatear_angulo, formatear_confianza, etiqueta_segmento


def _md_escape(texto: str) -> str:
    return str(texto).replace("|", "\\|")


def construir_markdown(
    datos: dict[str, Any],
    *,
    tiempo_evaluacion_s: float | None = None,
    tiempo_redaccion_s: float | None = None,
) -> str:
    """Arma el informe en español (México) según secciones de la spec."""

    reba = datos.get("reba") or {}
    final = (reba.get("final") or {}).get("reportado")
    nivel = reba.get("nivel_riesgo") or "Pendiente"
    residual = datos.get("riesgo_residual") or {}
    recomendaciones = datos.get("recomendaciones") or []
    pendientes = datos.get("pendientes_manuales") or []
    angulos = datos.get("angulos") or []
    caso = datos.get("caso_id", "sin_caso")
    lineas: list[str] = [
        f"# Informe ErgoAI · caso `{caso}`",
        "",
        "> El agente propone; el especialista decide. Ninguna recomendación es acción de piso hasta estar **aprobada**.",
        "",
        "## 1. Datos del caso",
        "",
        f"- Identificador: `{caso}`",
        f"- Método principal: REBA (Hignett y McAtamney, 2000)",
        f"- Modelo de pose: {datos.get('version_modelo', 'local')}",
        f"- Tiempo de evaluación: {tiempo_evaluacion_s:.1f} s" if tiempo_evaluacion_s is not None else "- Tiempo de evaluación: no instrumentado",
        f"- Tiempo de redacción del informe: {tiempo_redaccion_s:.2f} s" if tiempo_redaccion_s is not None else "- Tiempo de redacción: no instrumentado",
        "",
        "## 2. Fotos usadas",
        "",
    ]
    vistas = sorted({str(a.get("vista")) for a in angulos if a.get("vista")})
    if vistas:
        for vista in vistas:
            lineas.append(f"- {ETIQUETAS_VISTA.get(vista, vista)}")
    else:
        lineas.append("- Sin vistas registradas en ángulos.")
    lineas.extend(["", "Las fotografías se procesan en local y no se incluyen rostros de forma intencional en la anotación.", ""])

    lineas.extend(
        [
            "## 3. Ángulos por segmento",
            "",
            "| Segmento | Lado | Ángulo | Rango REBA | Vista | Confianza |",
            "|---|---|---|---|---|---|",
        ]
    )
    for angulo in angulos:
        lineas.append(
            "| {seg} | {lado} | {ang} | {rango} | {vista} | {conf} |".format(
                seg=_md_escape(etiqueta_segmento(str(angulo.get("medida", "")))),
                lado=angulo.get("lado") or "—",
                ang=formatear_angulo(angulo.get("valor_deg")),
                rango="—" if angulo.get("banda_reba") is None else angulo.get("banda_reba"),
                vista=ETIQUETAS_VISTA.get(str(angulo.get("vista") or ""), angulo.get("vista") or "—"),
                conf=formatear_confianza(angulo.get("confianza"), angulo.get("banderas") or []),
            )
        )

    lineas.extend(
        [
            "",
            "## 4. Puntaje REBA",
            "",
            f"- **REBA reportado:** {final if final is not None else 'Pendiente'}",
            f"- **Nivel de riesgo:** {nivel}",
            f"- **Nivel de acción:** {reba.get('nivel_accion')}",
            f"- **Lado reportado:** {(reba.get('final') or {}).get('lado')}",
            "",
            "### Grupo A",
            "",
            "```json",
            str(reba.get("grupo_a") or {}),
            "```",
            "",
            "### Grupo B",
            "",
            "```json",
            str(reba.get("grupo_b") or {}),
            "```",
            "",
        ]
    )

    lineas.extend(["## 5. Recomendaciones (propuestas)", ""])
    if not recomendaciones:
        lineas.append("Sin recomendaciones automáticas. Revisar pendientes y contexto.")
    else:
        lineas.append("| # | Inciso | Segmento | Control | Estado | Problema | Solución | Fuente |")
        lineas.append("|---|---|---|---|---|---|---|---|")
        for item in recomendaciones:
            lineas.append(
                "| {id} | {inc} | {seg} | {ctrl} | {est} | {prob} | {sol} | {fue} |".format(
                    id=item.get("id"),
                    inc=item.get("identificador"),
                    seg=_md_escape(item.get("segmento", "")),
                    ctrl=item.get("tipo_control"),
                    est=item.get("estado"),
                    prob=_md_escape(item.get("problema", "")),
                    sol=_md_escape(item.get("solucion", "")),
                    fue=_md_escape(item.get("fuente", "")),
                )
            )
        lineas.append("")
        lineas.append("Solo las recomendaciones en estado **aprobada** pueden mostrarse como acción de piso.")

    lineas.extend(
        [
            "",
            "## 6. Riesgo residual",
            "",
            f"- Puntaje inicial: {residual.get('puntaje_inicial')}",
            f"- Nivel inicial: {residual.get('nivel_inicial')}",
            f"- Puntaje residual: {residual.get('puntaje_residual')}",
            f"- Nivel residual: {residual.get('nivel_residual')}",
            f"- Delta: {residual.get('delta')}",
            "",
            "Supuestos:",
            "",
        ]
    )
    for supuesto in residual.get("supuestos") or ["Sin supuestos declarados."]:
        lineas.append(f"- {supuesto}")

    lineas.extend(["", "## 7. Pendientes y límites", ""])
    if pendientes:
        for pendiente in pendientes[:20]:
            lineas.append(f"- {pendiente.get('medida')}: {pendiente.get('motivo', 'revisar')}")
    else:
        lineas.append("- Sin pendientes automáticos.")
    lineas.extend(
        [
            "",
            "Límites conocidos: la estimación de pose depende de la calidad de las fotos y de las vistas disponibles;",
            "si falta una vista o hay baja visibilidad, el sistema marca pendiente y no inventa el ángulo.",
            "REBA es ayuda a la evaluación; no sustituye al especialista.",
            "",
            "## 8. Validación",
            "",
            "Consulte `bitacora.jsonl` en la carpeta del caso para el registro de cambios (quién, cuándo, valor anterior, valor nuevo, motivo).",
            "",
        ]
    )
    return "\n".join(lineas) + "\n"


def guardar_informe(
    datos: dict[str, Any],
    carpeta: Path,
    *,
    tiempo_evaluacion_s: float | None = None,
) -> tuple[Path, float]:
    """Escribe `informe.md` y devuelve la ruta y el tiempo de redacción (R8)."""

    inicio = time.perf_counter()
    # Primer paso: construir sin tiempo de redacción; luego reescribir con el valor medido.
    borrador = construir_markdown(datos, tiempo_evaluacion_s=tiempo_evaluacion_s, tiempo_redaccion_s=None)
    tiempo = time.perf_counter() - inicio
    texto = construir_markdown(datos, tiempo_evaluacion_s=tiempo_evaluacion_s, tiempo_redaccion_s=tiempo)
    ruta = carpeta / "informe.md"
    ruta.write_text(texto, encoding="utf-8")
    # Evitar warning de variable no usada si se optimiza el borrador.
    _ = len(borrador)
    return ruta, tiempo
