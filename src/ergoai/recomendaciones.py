"""Motor de reglas que propone recomendaciones jerarquizadas (NOM-036-1 + lineamientos Jabil).

El agente solo *propone*: cada recomendación nace en estado ``propuesta`` y no se
presenta como acción de piso hasta que el especialista la aprueba (ver ``validacion``).
Cada regla declara además su ``efecto`` esperado sobre las mediciones o el contexto,
que ``residual`` usa para recalcular el REBA después de aplicar los cambios.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config import RebaConfig

JERARQUIAS = ("ingenieria", "rediseno", "administrativa")
ETIQUETA_JERARQUIA = {
    "ingenieria": "Control de ingeniería",
    "rediseno": "Rediseño de estación",
    "administrativa": "Medida administrativa",
}
TIPOS_TAREA = ("levantamiento", "transporte_con_auxiliar", "transporte_sin_auxiliar", "otro")
TIPOS_TRABAJO = ("precision", "ligero", "pesado")

LIMITE_CARGA_JABIL_KG = 14.0
ALTURA_TRABAJO_CM = {"precision": "95–120 cm", "ligero": "85–110 cm", "pesado": "65–95 cm"}

# Referencias citadas en el informe. Sin numerales de la NOM para no citar un inciso
# equivocado: el especialista puede precisarlos al validar.
REF = {
    "reba": "REBA (Hignett y McAtamney, 2000)",
    "nom_control": "NOM-036-1-STPS-2018: medidas de prevención y control (ingeniería antes que administrativas)",
    "nom_ap1": "NOM-036-1-STPS-2018, Apéndice I (levantamiento y transporte manual de cargas)",
    "nom_ap2": "NOM-036-1-STPS-2018, Apéndice II (empuje y arrastre con y sin equipo auxiliar)",
    "nom_tabla1": "NOM-036-1-STPS-2018, masa máxima por sexo y edad",
    "nom_capacitacion": "NOM-036-1-STPS-2018: capacitación y vigilancia a la salud",
    "jabil_641": "Jabil 16-PE30-6500-00023 §6.4.1 (límite de 14 kg por persona)",
    "jabil_642": "Jabil 16-PE30-6500-00023 §6.4.2 (levantamiento en equipo solo como contención)",
    "jabil_643": "Jabil 16-PE30-6500-00023 §6.4.3 (60 cm libres para levantar)",
    "jabil_644": "Jabil 16-PE30-6500-00023 §6.4.4 (evitar piso/sobre cabeza; máx. 1.7 m rack, 1.6 m carro)",
    "jabil_silla": "Jabil 16-PE30-6500-00023 §7.2.2 (Ley silla: alternar de pie/sentado)",
    "jabil_conveyor": "Jabil 16-PE30-6500-00023 (conveyors: altura 0.5–1.4 m; gravedad ≤ 3 m)",
    "f00014_b": "Formato Jabil 16-PE80-6500-00014, sección B (área de trabajo y alturas)",
    "f00014_f": "Formato Jabil 16-PE80-6500-00014, sección F (ayuda visual a 1,400–1,600 mm)",
    "f00014_g": "Formato Jabil 16-PE80-6500-00014, sección G (iluminación por actividad)",
}


@dataclass
class Recomendacion:
    """Recomendación propuesta por el agente o agregada por el especialista."""

    id: str
    factor: str
    problema: str
    solucion: str
    jerarquia: str
    referencias: list[str]
    efecto: dict[str, dict[str, Any]] = field(default_factory=dict)
    prioridad: str = "normal"
    estado: str = "propuesta"
    responsable: str = ""
    fecha_compromiso: str = ""
    comentario: str = ""
    origen: str = "agente"
    delta_reba: int | None = None

    def a_diccionario(self) -> dict[str, Any]:
        return asdict(self)


def _maximo(mediciones: dict[str, float | None], base: str) -> float | None:
    valores = [mediciones.get(f"{base}_{lado}") for lado in ("L", "R")]
    validos = [valor for valor in valores if valor is not None]
    return max(validos, key=abs) if validos else None


def _fuera_rango(mediciones: dict[str, float | None], base: str, minimo: float, maximo: float) -> float | None:
    for lado in ("L", "R"):
        valor = mediciones.get(f"{base}_{lado}")
        if valor is not None and not minimo <= valor <= maximo:
            return valor
    return None


def _lados(base: str, valor: Any) -> dict[str, Any]:
    return {f"{base}_L": valor, f"{base}_R": valor}


def _prioridad(nivel_accion: int | None) -> str:
    if nivel_accion is None:
        return "revisar"
    return "urgente" if nivel_accion >= 3 else "alta" if nivel_accion == 2 else "normal"


def generar_recomendaciones(
    mediciones: dict[str, float | None], contexto: dict[str, Any], reba: dict[str, Any], config: RebaConfig,
) -> list[Recomendacion]:
    """Aplica las reglas y devuelve recomendaciones ordenadas por jerarquía de control."""

    recs: list[Recomendacion] = []
    # Si el puntaje está pendiente pero todo su rango cae en un nivel, ese nivel ya sirve para priorizar.
    nivel_conocido = reba.get("nivel_accion")
    if nivel_conocido is None:
        nivel_conocido = ((reba.get("final") or {}).get("rango") or {}).get("nivel_accion")
    prioridad = _prioridad(nivel_conocido)
    tipo_tarea = contexto.get("tipo_tarea") or "otro"
    tipo_trabajo = contexto.get("tipo_trabajo") if contexto.get("tipo_trabajo") in TIPOS_TRABAJO else None
    sentado = contexto.get("postura") == "sentado"
    carga = contexto.get("carga_kg")
    actividad = contexto.get("actividad") or {}

    def agregar(id_: str, factor: str, problema: str, solucion: str, jerarquia: str, refs: list[str], efecto: dict[str, dict[str, Any]] | None = None) -> None:
        recs.append(Recomendacion(id_, factor, problema, solucion, jerarquia, [REF[r] for r in refs], efecto or {}, prioridad))

    # --- Carga y tipo de tarea --------------------------------------------------------
    if isinstance(carga, (int, float)) and carga > LIMITE_CARGA_JABIL_KG:
        agregar(
            "R-CARGA-ING", "carga",
            f"Carga manual de {carga:g} kg: supera el límite de {LIMITE_CARGA_JABIL_KG:g} kg por persona de Jabil Chihuahua.",
            "Eliminar el manejo manual con asistencia mecánica: polipasto o lifter con sujetador, manipulador neumático "
            "o mesa elevadora; el operador solo guía la carga. Verificar además la masa máxima de la NOM-036-1 según sexo y edad.",
            "ingenieria", ["jabil_641", "nom_ap1", "nom_tabla1"],
            {"contexto": {"carga_kg": 0, "fuerza_brusca": False}},
        )
        agregar(
            "R-CARGA-ADM", "carga",
            "No hay asistencia mecánica instalada para una carga mayor al límite.",
            "Solo como contención temporal, levantar entre dos o más personas según las tablas de §6.4.2, "
            "con evaluación 16-PE80-6500-00014 y MOC, hasta instalar el equipo.",
            "administrativa", ["jabil_642"],
        )
    elif isinstance(carga, (int, float)) and carga >= config.carga_kg.baja and not tipo_tarea.startswith("transporte"):
        agregar(
            "R-CARGA-RED", "carga",
            f"Carga de {carga:g} kg sostenida con los brazos (≥ {config.carga_kg.baja:g} kg suma puntos en REBA).",
            f"Reducir la masa por manipulación a menos de {config.carga_kg.baja:g} kg (contenedores más pequeños) o apoyar la carga "
            "en mesa elevadora/carro para que no se sostenga. Confirmar que la nueva frecuencia no vuelva repetitiva la tarea.",
            "rediseno", ["nom_ap1", "reba"],
            {"contexto": {"carga_kg": max(0.0, config.carga_kg.baja - 1)}},
        )

    if tipo_tarea == "transporte_sin_auxiliar" and isinstance(carga, (int, float)) and carga > 0:
        agregar(
            "R-TRANSP-ING", "transporte",
            f"Transporte manual de {carga:g} kg sin equipo auxiliar.",
            "Sustituir el acarreo por un auxiliar de transporte: carro de ruedas de baja resistencia con manijas a la altura "
            "de los codos, conveyor de rodillos (0.5–1.4 m de altura; por gravedad máximo 3 m) o AMR en rutas fijas.",
            "ingenieria", ["nom_ap2", "jabil_conveyor"],
            {"contexto": {"carga_kg": 0}},
        )
    if tipo_tarea == "transporte_con_auxiliar":
        agregar(
            "R-AUX-RED", "transporte",
            "Empuje/arrastre con equipo auxiliar: la fuerza depende del estado del equipo y de la ruta.",
            "Programar mantenimiento de ruedas y frenos, colocar manijas verticales entre cadera y codo, "
            "nivelar pisos y retirar obstáculos y desniveles de la ruta.",
            "rediseno", ["nom_ap2"],
            {"contexto": {"fuerza_brusca": False, "actividad.cambios_bruscos_o_base_inestable": False}},
        )
    if tipo_tarea == "levantamiento":
        agregar(
            "R-LEV-RED", "levantamiento",
            "Levantamiento manual: el origen o destino puede quedar fuera de la zona entre nudillos y hombros.",
            "Ubicar origen y destino entre la altura de nudillos y hombros; no levantar desde el piso ni sobre la cabeza "
            "(máximo 1.7 m en racks estáticos y 1.6 m en tarimas o carros) y dejar 60 cm libres alrededor del operador.",
            "rediseno", ["jabil_644", "jabil_643", "nom_ap1"],
            {"mediciones": {"tronco_flexion": config.tronco.leve, **_lados("rodilla_flexion", 0)}},
        )

    # --- Segmentos corporales (REBA) --------------------------------------------------
    tronco = mediciones.get("tronco_flexion")
    if tronco is not None and tronco > config.tronco.leve:
        severidad = "severa" if tronco > config.tronco.moderado else "moderada"
        rango = ALTURA_TRABAJO_CM.get(tipo_trabajo or "", "a la altura de los codos")
        agregar(
            "R-TRONCO-ING", "tronco",
            f"Flexión de tronco {severidad} de {tronco:.0f}° (REBA > {config.tronco.leve:g}°).",
            f"Llevar el punto de toma y la superficie de trabajo a {rango}: mesa de altura ajustable, elevador de tarimas "
            "o carro de tijera autonivelante que mantenga el material siempre a la misma altura.",
            "ingenieria", ["f00014_b", "jabil_644", "reba"],
            {"mediciones": {"tronco_flexion": 10.0}},
        )
    torsion, lateral = mediciones.get("tronco_torsion"), mediciones.get("tronco_inclinacion_lateral")
    if (torsion is not None and torsion > config.umbral_torsion_tronco_deg) or (lateral is not None and lateral > config.umbral_inclinacion_lateral_tronco_deg):
        partes = []
        if torsion is not None and torsion > config.umbral_torsion_tronco_deg:
            partes.append(f"torsión de {torsion:.0f}°")
        if lateral is not None and lateral > config.umbral_inclinacion_lateral_tronco_deg:
            partes.append(f"inclinación lateral de {lateral:.0f}°")
        agregar(
            "R-TORSION-RED", "tronco",
            f"Tronco con {' e '.join(partes)}.",
            "Reacomodar material, herramienta y destino al frente del operador dentro del área de alcance; usar tornamesa "
            "o rampa de alimentación frontal para eliminar giros e inclinaciones laterales.",
            "rediseno", ["nom_ap1", "reba"],
            {"mediciones": {"tronco_torsion": 0.0, "tronco_inclinacion_lateral": 0.0}},
        )
    cuello, cuello_lat = mediciones.get("cuello_flexion"), mediciones.get("cuello_inclinacion_rotacion")
    flexion = cuello is not None and cuello > config.cuello.flexion
    extension = cuello is not None and cuello < -config.tolerancia_neutro_deg
    giro = cuello_lat is not None and cuello_lat > config.umbral_cuello_lateral_rotacion_deg
    if flexion or extension or giro:
        causas = []
        if flexion:
            causas.append(f"flexión de {cuello:.0f}° (más de {config.cuello.flexion:g}°)")
        if extension:
            causas.append(f"extensión de {abs(cuello):.0f}°")
        if giro:
            causas.append(f"giro o inclinación lateral de {cuello_lat:.0f}° (más de {config.umbral_cuello_lateral_rotacion_deg:g}°)")
        solucion = []
        if flexion or extension:
            solucion.append("Acercar la pieza a la línea de visión con un posicionador o soporte inclinable; colocar ayudas visuales "
                            "a 1,400–1,600 mm y asegurar iluminación adecuada a la actividad (500 lx ensamble, 750 lx precisión).")
        if giro:
            solucion.append("Colocar la pieza, la herramienta y las ayudas visuales al frente del operador para que no tenga que "
                            "girar ni inclinar la cabeza hacia un lado.")
        agregar(
            "R-CUELLO-RED", "cuello",
            f"Cuello con {' y '.join(causas)}.",
            " ".join(solucion),
            "rediseno", ["f00014_f", "f00014_g", "reba"],
            {"mediciones": {"cuello_flexion": 10.0, "cuello_inclinacion_rotacion": 0.0}},
        )
    rodilla = _maximo(mediciones, "rodilla_flexion")
    apoyo = mediciones.get("apoyo_piernas_unilateral")
    if (rodilla is not None and rodilla >= config.rodilla.leve and not sentado) or (apoyo and not sentado):
        detalle = f"flexión de rodilla de {rodilla:.0f}°" if rodilla is not None and rodilla >= config.rodilla.leve else "apoyo en una sola pierna"
        agregar(
            "R-PIERNAS-RED", "piernas",
            f"Piernas con {detalle}.",
            "Eliminar el trabajo por debajo de la rodilla elevando el material; dejar espacio para los pies ≥ 15 cm bajo la "
            "estación y tapete antifatiga si la tarea es de pie prolongada.",
            "rediseno", ["f00014_b", "reba"],
            {"mediciones": {**_lados("rodilla_flexion", 0.0), "apoyo_piernas_unilateral": 0.0}},
        )
    brazo, abduccion = _maximo(mediciones, "brazo_flexion"), _maximo(mediciones, "brazo_abduccion")
    hombros = contexto.get("hombro_elevado") or {}
    hombro_elevado = isinstance(hombros, dict) and any(hombros.values())
    if (brazo is not None and brazo > config.brazo.medio) or (abduccion is not None and abduccion > config.umbral_abduccion_brazo_deg) or hombro_elevado:
        partes = []
        if brazo is not None and brazo > config.brazo.medio:
            partes.append(f"flexión de brazo de {brazo:.0f}°")
        if abduccion is not None and abduccion > config.umbral_abduccion_brazo_deg:
            partes.append(f"abducción de {abduccion:.0f}°")
        if hombro_elevado:
            partes.append("hombro elevado")
        agregar(
            "R-BRAZO-RED", "brazos",
            f"Brazos con {', '.join(partes)}.",
            "Bajar y acercar material y herramienta a la zona de alcance primaria (debajo del hombro y cerca del cuerpo): "
            "dispensadores inclinados por gravedad, balanceador para herramienta suspendida y menor profundidad de mesa.",
            "rediseno", ["f00014_b", "reba"],
            {"mediciones": {**_lados("brazo_flexion", 15.0), **_lados("brazo_abduccion", 0.0)},
             "contexto": {"hombro_elevado.izquierdo": False, "hombro_elevado.derecho": False}},
        )
    codo = _fuera_rango(mediciones, "codo_flexion", config.antebrazo.min, config.antebrazo.max)
    if codo is not None:
        agregar(
            "R-ANTEBRAZO-RED", "antebrazos",
            f"Codo a {codo:.0f}°, fuera del rango REBA {config.antebrazo.min:g}–{config.antebrazo.max:g}°.",
            "Ajustar la altura de trabajo o la posición de la pieza para que el codo trabaje cerca de 90°.",
            "rediseno", ["f00014_b", "reba"],
            {"mediciones": _lados("codo_flexion", 90.0)},
        )
    muneca = _maximo(mediciones, "muneca_flexion_extension")
    desviaciones = contexto.get("muneca_desviada_o_torcida") or {}
    desviada = isinstance(desviaciones, dict) and any(desviaciones.values())
    if (muneca is not None and abs(muneca) > config.muneca.flexion) or desviada:
        detalle = f"muñeca a {abs(muneca):.0f}° de flexión/extensión" if muneca is not None and abs(muneca) > config.muneca.flexion else "muñeca desviada o torcida"
        agregar(
            "R-MUNECA-ING", "munecas",
            f"{detalle.capitalize()}.",
            "Cambiar a una herramienta con la geometría de la superficie (mango de pistola en superficies verticales, "
            "en línea en horizontales) o usar un posicionador/fixture que mantenga la muñeca neutra.",
            "ingenieria", ["reba", "nom_control"],
            {"mediciones": _lados("muneca_flexion_extension", 0.0),
             "contexto": {"muneca_desviada_o_torcida.izquierdo": False, "muneca_desviada_o_torcida.derecho": False}},
        )
    agarre = contexto.get("agarre")
    if agarre in ("regular", "malo", "inaceptable"):
        agregar(
            "R-AGARRE-RED", "agarre",
            f"Acoplamiento mano-carga {agarre}.",
            "Rediseñar el acoplamiento: contenedores con asas o ranuras de agarre, ganchos o ventosas, para lograr un "
            "acoplamiento bueno.",
            "rediseno", ["nom_ap1", "reba"],
            {"contexto": {"agarre": "bueno"}},
        )

    # --- Actividad --------------------------------------------------------------------
    if actividad.get("repetitiva_mas_4_por_min"):
        agregar(
            "R-REPET-ING", "actividad",
            "Acción repetida más de 4 veces por minuto.",
            "Automatizar o semiautomatizar el paso repetitivo: alimentadores, fixtures de cierre rápido o atornillado automático.",
            "ingenieria", ["nom_control", "reba"],
            {"contexto": {"actividad.repetitiva_mas_4_por_min": False}},
        )
        agregar(
            "R-REPET-ADM", "actividad",
            "Exposición repetitiva acumulada durante el turno.",
            "Rotar a tareas que usen otros grupos musculares y programar pausas activas.",
            "administrativa", ["nom_control"],
        )
    if actividad.get("cambios_bruscos_o_base_inestable") and tipo_tarea != "transporte_con_auxiliar":
        agregar(
            "R-BASE-RED", "actividad",
            "Cambios bruscos de postura o base inestable.",
            "Nivelar el piso, usar superficie antideslizante y eliminar escalones o desniveles en la zona de trabajo.",
            "rediseno", ["nom_ap1", "reba"],
            {"contexto": {"actividad.cambios_bruscos_o_base_inestable": False}},
        )
    if actividad.get("estatica_mas_1min") or (contexto.get("postura") == "de_pie" and (nivel_conocido or 0) >= 2):
        agregar(
            "R-SILLA-RED", "postura",
            "Postura mantenida (estática o de pie prolongado).",
            "Estación convertible de pie/sentado (silla alta con reposapiés de 21–37 cm) para alternar la postura; "
            "si no es viable, rotar entre estaciones de pie y sentado (Ley silla). Reduce exposición acumulada; "
            "no cambia el REBA de la postura fotografiada.",
            "rediseno", ["jabil_silla", "f00014_b"],
        )

    # Nivel conocido: el del puntaje o, si está pendiente, el de su rango cuando cae en un solo nivel.
    nivel = nivel_conocido
    puntaje = _puntaje_reportado(reba)
    riesgo_alto = _es_riesgo_alto(puntaje, nivel)

    if (nivel is not None and nivel >= 2) or tipo_tarea != "otro":
        agregar(
            "R-CAPAC-ADM", "general",
            "Personal expuesto a factores de riesgo ergonómico identificados.",
            "Capacitar al personal en manejo manual de cargas y en los riesgos detectados; incluir a los expuestos en la "
            "vigilancia a la salud. Complementa, no sustituye, los controles de ingeniería.",
            "administrativa", ["nom_capacitacion"],
        )

    # NOM-036 / rúbrica Track 4: con REBA ≥ 8 está prohibido dejar solo medidas administrativas
    # (rotación, pausas, capacitación). Se exige al menos un control de ingeniería o rediseño con efecto.
    if riesgo_alto and not any(rec.jerarquia in ("ingenieria", "rediseno") and rec.efecto for rec in recs):
        agregar(
            "R-ESTACION-ING", "general",
            f"REBA {puntaje if puntaje is not None else '≥ 8'}: riesgo alto/muy alto sin control de ingeniería medible.",
            "Instalar mesa de altura ajustable, polipasto/lifter o rediseño de alcances para eliminar la postura forzada; "
            "la rotación de personal y las pausas activas quedan solo como contención temporal hasta el rediseño.",
            "ingenieria", ["nom_control", "f00014_b", "reba"],
            {"mediciones": {"tronco_flexion": 10.0, **_lados("brazo_flexion", 15.0), **_lados("rodilla_flexion", 0.0)},
             "contexto": {"carga_kg": 0, "actividad.repetitiva_mas_4_por_min": False}},
        )

    if riesgo_alto:
        _marcar_admin_como_complemento(recs)

    if nivel is None:
        for rec in recs:
            rec.prioridad = "revisar"
    return ordenar(recs)


def _puntaje_reportado(reba: dict[str, Any]) -> int | None:
    final = reba.get("final") or {}
    reportado = final.get("reportado") if isinstance(final, dict) else None
    return int(reportado) if isinstance(reportado, (int, float)) else None


def _es_riesgo_alto(puntaje: int | None, nivel_accion: int | None) -> bool:
    """REBA ≥ 8 (Alto / Muy alto) o nivel de acción ≥ 3."""

    if puntaje is not None and puntaje >= 8:
        return True
    return nivel_accion is not None and nivel_accion >= 3


def _marcar_admin_como_complemento(recs: list[Recomendacion]) -> None:
    """En riesgo alto, las administrativas no pueden presentarse como solución principal."""

    for rec in recs:
        if rec.jerarquia != "administrativa":
            continue
        if "Complementa" not in rec.solucion and "contención" not in rec.solucion.lower():
            rec.solucion = (
                f"{rec.solucion.rstrip('.')} — solo como complemento; no sustituye el control de ingeniería "
                "exigido por NOM-036-1-STPS-2018 ante riesgo alto/muy alto."
            )
        rec.prioridad = "urgente"


def solo_administrativas(recs: list[Recomendacion] | list[dict[str, Any]]) -> bool:
    """True si el paquete vigente no incluye ingeniería ni rediseño (falla de cumplimiento NOM-036)."""

    vigentes = []
    for rec in recs:
        jerarquia = rec.jerarquia if isinstance(rec, Recomendacion) else rec.get("jerarquia")
        estado = rec.estado if isinstance(rec, Recomendacion) else rec.get("estado", "propuesta")
        if estado not in ("rechazada", "obsoleta"):
            vigentes.append(jerarquia)
    return bool(vigentes) and all(j == "administrativa" for j in vigentes)


def cumple_jerarquia_nom036(reba: dict[str, Any], recs: list[Recomendacion] | list[dict[str, Any]]) -> bool:
    """Con REBA ≥ 8 debe existir al menos un control de ingeniería/rediseño vigente."""

    if not _es_riesgo_alto(_puntaje_reportado(reba), reba.get("nivel_accion")):
        return True
    return not solo_administrativas(recs)


def ordenar(recs: list[Recomendacion]) -> list[Recomendacion]:
    """Ordena por jerarquía de control y, dentro de cada nivel, por mayor reducción del REBA."""

    return sorted(recs, key=lambda rec: (JERARQUIAS.index(rec.jerarquia) if rec.jerarquia in JERARQUIAS else 9, -(rec.delta_reba or 0), rec.id))
