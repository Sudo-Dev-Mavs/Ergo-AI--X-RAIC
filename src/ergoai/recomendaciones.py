"""Motor de recomendaciones NOM-036 / Jabil. No calcula puntajes REBA."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ESTADOS = ("propuesta", "en_revision", "editada", "aprobada", "rechazada")
ORDEN_CONTROL = {"eliminacion": 0, "ingenieria": 1, "administrativo": 2}
ORDEN_RIESGO = {"Muy alto": 0, "Alto": 1, "Medio": 2, "Bajo": 3, "Inapreciable": 4, None: 5}


@dataclass
class Recomendacion:
    """Propuesta para el especialista; nunca es acción de piso por sí sola."""

    id: str
    identificador: str
    segmento: str
    problema: str
    solucion: str
    tipo_control: str
    prioridad: int
    fuente: str
    estado: str = "propuesta"
    riesgo_origen: str | None = None
    cambio_esperado: dict[str, Any] = field(default_factory=dict)
    responsable: str = "IE / especialista ergonómico"
    historial: list[dict[str, Any]] = field(default_factory=list)

    def a_diccionario(self) -> dict[str, Any]:
        return asdict(self)


def _valor(mediciones: dict[str, float | None], *claves: str) -> float | None:
    for clave in claves:
        valor = mediciones.get(clave)
        if valor is not None:
            return float(valor)
    return None


def _peor_lado(mediciones: dict[str, float | None], base: str) -> tuple[str | None, float | None]:
    izq = mediciones.get(f"{base}_L")
    der = mediciones.get(f"{base}_R")
    if izq is None and der is None:
        return None, None
    if izq is None:
        return "R", der
    if der is None:
        return "L", izq
    return ("L", izq) if abs(izq) >= abs(der) else ("R", der)


def generar_recomendaciones(
    reba: dict[str, Any],
    mediciones: dict[str, float | None],
    contexto: dict[str, Any],
) -> list[Recomendacion]:
    """Reglas deterministas. Ingeniería antes que administrativas en riesgo alto."""

    nivel = reba.get("nivel_riesgo")
    final = (reba.get("final") or {}).get("reportado")
    propuestas: list[Recomendacion] = []
    contador = 1

    def agregar(**kwargs: Any) -> None:
        nonlocal contador
        propuestas.append(
            Recomendacion(
                id=f"REC-{contador:02d}",
                identificador=kwargs.pop("identificador"),
                prioridad=kwargs.pop("prioridad", contador),
                riesgo_origen=nivel,
                **kwargs,
            )
        )
        contador += 1

    torsion = _valor(mediciones, "tronco_torsion")
    if torsion is not None and torsion > 20:
        agregar(
            identificador="H",
            segmento="tronco_torsion",
            problema=f"Torsión de tronco {torsion:.1f}° detectada en vista aérea.",
            solucion="Reorientar la pieza o la estación para que el operador enfrente el trabajo; evitar girar el torso con carga.",
            tipo_control="ingenieria",
            fuente="NOM-036-1-STPS-2018; REBA torsión; vista aérea",
            prioridad=1,
            cambio_esperado={"tronco_torsion": 8.0},
        )

    asimetria = _valor(mediciones, "alcance_asimetria")
    if asimetria is not None and asimetria > 20:
        agregar(
            identificador="I",
            segmento="alcance",
            problema=f"Asimetría de alcance {asimetria:.1f}° entre lados (vista aérea).",
            solucion="Centrar el material frente al operador o acercar contenedores al lado de trabajo dominante.",
            tipo_control="ingenieria",
            fuente="NOM-036-1-STPS-2018; J-7.2.2.2 zonas de alcance",
            prioridad=2,
            cambio_esperado={},
        )

    tronco = _valor(mediciones, "tronco_flexion")
    if tronco is not None and abs(tronco) > 20:
        agregar(
            identificador="A",
            segmento="tronco",
            problema=f"Flexión de tronco {tronco:.1f}° fuera de la zona preferente.",
            solucion="Ajustar altura de área de trabajo a 96–120 cm (rango estricto Excel; layouts 95–125 cm) o acercar la pieza al cuerpo.",
            tipo_control="ingenieria",
            fuente="NOM-036-1-STPS-2018; J-7.2.3 / C2",
            prioridad=1,
            cambio_esperado={"tronco_flexion": 10.0},
        )

    cuello = _valor(mediciones, "cuello_flexion")
    if cuello is not None and abs(cuello) > 20:
        agregar(
            identificador="B",
            segmento="cuello",
            problema=f"Cuello en {cuello:.1f}°; mantiene flexión/extensión elevada.",
            solucion="Elevar la ayuda visual o la pieza a 140–160 cm y distancia mínima 40 cm; evitar mirar por debajo de la mesa.",
            tipo_control="ingenieria",
            fuente="NOM-036-1-STPS-2018; Excel Mov / J-7.3.3",
            prioridad=2,
            cambio_esperado={"cuello_flexion": 10.0},
        )

    lado_brazo, brazo = _peor_lado(mediciones, "brazo_flexion")
    if brazo is not None and brazo > 45:
        lado_txt = "izquierdo" if lado_brazo == "L" else "derecho"
        agregar(
            identificador="C",
            segmento=f"brazo_{lado_txt}",
            problema=f"Brazo {lado_txt} a {brazo:.1f}°; trabajo por encima de zona cómoda.",
            solucion="Reubicar material de uso regular a zonas de alcance 1–2; bajar puntos de toma o usar soporte de brazo.",
            tipo_control="ingenieria",
            fuente="NOM-036-1-STPS-2018; J-7.2.2.2",
            prioridad=2,
            cambio_esperado={f"brazo_flexion_{lado_brazo}": 20.0},
        )

    carga = contexto.get("carga_kg")
    if isinstance(carga, (int, float)) and carga > 14:
        agregar(
            identificador="D",
            segmento="carga",
            problema=f"Carga manual de {carga:g} kg supera el límite de 14 kg por persona.",
            solucion="Usar asistencia mecánica (lifter/grúa/carrito). Levantamiento en equipo solo como contención temporal.",
            tipo_control="ingenieria",
            fuente="J-6.4.1; NOM-036-1-STPS-2018",
            prioridad=1,
            cambio_esperado={"carga_kg": min(float(carga), 10.0)},
        )
    elif isinstance(carga, (int, float)) and carga > 10:
        agregar(
            identificador="D",
            segmento="carga",
            problema=f"Carga de {carga:g} kg en banda alta de REBA.",
            solucion="Reducir peso por pieza, fraccionar carga o acercar el contenedor al operador.",
            tipo_control="ingenieria",
            fuente="REBA carga; NOM-036-1-STPS-2018",
            prioridad=2,
            cambio_esperado={"carga_kg": 8.0},
        )

    agarre = contexto.get("agarre")
    if agarre in {"malo", "inaceptable"}:
        agregar(
            identificador="E",
            segmento="agarre",
            problema=f"Agarre declarado «{agarre}»; aumenta el puntaje del Grupo B.",
            solucion="Mejorar acoplamiento mano-carga: asas, textura antideslizante o contenedor con agarre definido.",
            tipo_control="ingenieria",
            fuente="NOM-036-1-STPS-2018; Excel Levantamiento factor f",
            prioridad=2,
            cambio_esperado={"agarre": "bueno"},
        )

    actividad = contexto.get("actividad") or {}
    if actividad.get("estatica_mas_1min") or actividad.get("repetitiva_mas_4_por_min"):
        # Solo como complemento; si el riesgo es alto se acompañará de ingeniería arriba.
        agregar(
            identificador="F",
            segmento="actividad",
            problema="Tarea estática >1 min y/o repetitiva >4/min.",
            solucion="Rotar con estación que permita cambiar postura; pausas activas de 5 min (baño no cuenta). No usar como única medida si el riesgo es alto.",
            tipo_control="administrativo",
            fuente="NOM-036-1-STPS-2018; J-7.2.2 ley silla",
            prioridad=4,
            cambio_esperado={
                "actividad": {
                    "estatica_mas_1min": False,
                    "repetitiva_mas_4_por_min": False,
                    "cambios_bruscos_o_base_inestable": bool(actividad.get("cambios_bruscos_o_base_inestable")),
                }
            },
        )

    if nivel in {"Alto", "Muy alto"} and not any(item.tipo_control in {"ingenieria", "eliminacion"} for item in propuestas):
        agregar(
            identificador="G",
            segmento="estacion",
            problema=f"REBA {final} ({nivel}) sin control de ingeniería detectado automáticamente.",
            solucion="Rediseñar la estación: altura, alcance y ayudas mecánicas antes de medidas administrativas.",
            tipo_control="ingenieria",
            fuente="R3; NOM-036-1-STPS-2018 jerarquía de controles",
            prioridad=1,
            cambio_esperado={"tronco_flexion": 10.0, "cuello_flexion": 10.0},
        )

    propuestas.sort(key=lambda item: (ORDEN_RIESGO.get(item.riesgo_origen, 5), ORDEN_CONTROL.get(item.tipo_control, 9), item.prioridad, item.id))
    for indice, item in enumerate(propuestas, start=1):
        item.prioridad = indice
    return propuestas


def hay_ingenieria_en_riesgo_alto(recomendaciones: list[Recomendacion], nivel: str | None) -> bool:
    """R3: en Alto/Muy alto debe existir al menos un control de ingeniería o eliminación."""

    if nivel not in {"Alto", "Muy alto"}:
        return True
    return any(item.tipo_control in {"ingenieria", "eliminacion"} for item in recomendaciones)
