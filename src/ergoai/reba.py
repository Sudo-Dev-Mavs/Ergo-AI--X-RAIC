"""Bandas y puntuación REBA según Hignett y McAtamney (2000)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config import RebaConfig

TABLA_A = (
    ((1, 2, 3, 4), (1, 2, 3, 4), (3, 3, 5, 6)),
    ((2, 3, 4, 5), (3, 4, 5, 6), (4, 5, 6, 7)),
    ((2, 4, 5, 6), (4, 5, 6, 7), (5, 6, 7, 8)),
    ((3, 5, 6, 7), (5, 6, 7, 8), (6, 7, 8, 9)),
    ((4, 6, 7, 8), (6, 7, 8, 9), (7, 8, 9, 9)),
)
TABLA_B = (
    ((1, 2, 2), (1, 2, 3)),
    ((1, 2, 3), (2, 3, 4)),
    ((3, 4, 5), (4, 5, 5)),
    ((4, 5, 5), (5, 6, 7)),
    ((6, 7, 8), (7, 8, 8)),
    ((7, 8, 8), (8, 9, 9)),
)
TABLA_C = (
    (1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7),
    (1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8),
    (2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8),
    (3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9),
    (4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9, 9),
    (6, 6, 6, 7, 8, 8, 9, 9, 10, 10, 10, 10),
    (7, 7, 7, 8, 9, 9, 9, 10, 10, 11, 11, 11),
    (8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11),
    (9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12),
    (10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12),
    (11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12),
    (12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12),
)


@dataclass(frozen=True)
class NivelRiesgo:
    """Interpretación final del puntaje REBA."""

    nombre: str
    nivel_accion: int


@dataclass
class ResultadoReba:
    """Desglose completo de un puntaje REBA o de sus pendientes."""

    grupo_a: dict[str, int | None]
    grupo_b: dict[str, dict[str, int | None]]
    tabla_c: dict[str, int | None]
    actividad: int
    final: dict[str, int | str | None]
    nivel_riesgo: str | None
    nivel_accion: int | None
    pendientes_manuales: list[dict[str, str]] = field(default_factory=list)

    def a_diccionario(self) -> dict[str, Any]:
        """Produce una estructura directamente serializable a JSON."""

        return asdict(self)


def _incluye(valor: float, limite: float, inclusivo: bool) -> bool:
    return valor <= limite if inclusivo else valor < limite


def banda_tronco(valor: float, torsion: float | None, lateral: float | None, config: RebaConfig) -> int:
    """Puntúa tronco incluyendo torsión e inclinación lateral."""

    absoluto = abs(valor)
    if absoluto <= config.tolerancia_neutro_deg:
        puntaje = 1
    elif _incluye(absoluto, config.tronco.leve, config.limite_superior_inclusivo):
        puntaje = 2
    elif valor > config.tronco.leve and _incluye(valor, config.tronco.moderado, config.limite_superior_inclusivo):
        puntaje = 3
    else:
        puntaje = 4 if valor > config.tronco.moderado else 3
    if (torsion is not None and torsion > config.umbral_torsion_tronco_deg) or (lateral is not None and lateral > config.umbral_inclinacion_lateral_tronco_deg):
        puntaje += 1
    return min(puntaje, 5)


def banda_cuello(valor: float, lateral_rotacion: float | None, config: RebaConfig) -> int:
    """Puntúa flexión/extensión de cuello y su ajuste lateral."""

    puntaje = 1 if -config.tolerancia_neutro_deg <= valor <= config.cuello.flexion else 2
    if lateral_rotacion is not None and lateral_rotacion > config.umbral_cuello_lateral_rotacion_deg:
        puntaje += 1
    return min(puntaje, 3)


def banda_piernas(unilateral: bool, rodilla: float | None, sentado: bool, config: RebaConfig) -> int:
    """Puntúa apoyo de piernas y flexión de rodilla."""

    puntaje = 1 if sentado or not unilateral else 2
    if not sentado and rodilla is not None:
        if rodilla > config.rodilla.alta:
            puntaje += 2
        elif rodilla >= config.rodilla.leve:
            puntaje += 1
    return min(puntaje, 4)


def banda_brazo(valor: float, abduccion: float | None, hombro_elevado: bool, apoyado: bool, config: RebaConfig) -> int:
    """Puntúa brazo superior y sus ajustes."""

    if -config.brazo.neutro <= valor <= config.brazo.neutro:
        puntaje = 1
    elif valor < -config.brazo.neutro or valor <= config.brazo.medio:
        puntaje = 2
    elif valor <= config.brazo.alto:
        puntaje = 3
    else:
        puntaje = 4
    if abduccion is not None and abduccion > config.umbral_abduccion_brazo_deg:
        puntaje += 1
    if hombro_elevado:
        puntaje += 1
    if apoyado:
        puntaje -= 1
    return min(6, max(1, puntaje))


def banda_antebrazo(valor: float, config: RebaConfig) -> int:
    """Puntúa antebrazo por el ángulo de codo."""

    return 1 if config.antebrazo.min <= valor <= config.antebrazo.max else 2


def banda_muneca(valor: float, desviada: bool, config: RebaConfig) -> int:
    """Puntúa muñeca y desviación/rotación declarada en el contexto."""

    puntaje = 1 if abs(valor) <= config.muneca.flexion else 2
    return min(3, puntaje + int(desviada))


def banda_medida(medida: str, valor: float | None, config: RebaConfig) -> int | None:
    """Puntaje REBA que aporta un ángulo por sí solo (sin ajustes de otros segmentos).

    Se usa para colorear las anotaciones: 1 verde, 2 amarillo, 3 naranja, 4 o más rojo. Los ajustes
    (torsión, inclinación lateral, abducción, giro de cuello, apoyo) valen 1 si no aplican y 2 si suman.
    """

    if valor is None:
        return None
    if medida == "tronco_flexion":
        return banda_tronco(valor, None, None, config)
    if medida == "cuello_flexion":
        return banda_cuello(valor, None, config)
    if medida == "brazo_flexion":
        return banda_brazo(valor, None, False, False, config)
    if medida == "codo_flexion":
        return banda_antebrazo(valor, config)
    if medida == "muneca_flexion_extension":
        return banda_muneca(valor, False, config)
    if medida == "rodilla_flexion":
        return 1 + (2 if valor > config.rodilla.alta else 1 if valor >= config.rodilla.leve else 0)
    umbrales = {
        "tronco_torsion": config.umbral_torsion_tronco_deg, "tronco_inclinacion_lateral": config.umbral_inclinacion_lateral_tronco_deg,
        "brazo_abduccion": config.umbral_abduccion_brazo_deg, "cuello_inclinacion_rotacion": config.umbral_cuello_lateral_rotacion_deg,
        "apoyo_piernas_unilateral": 0.5,
    }
    if medida in umbrales:
        return 2 if valor > umbrales[medida] else 1
    return None


def puntaje_tabla_a(tronco: int, cuello: int, piernas: int) -> int:
    """Consulta la Tabla A REBA, validando cada rango."""

    if not 1 <= tronco <= 5 or not 1 <= cuello <= 3 or not 1 <= piernas <= 4:
        raise ValueError("Tabla A: tronco debe ser 1–5, cuello 1–3 y piernas 1–4.")
    return TABLA_A[tronco - 1][cuello - 1][piernas - 1]


def puntaje_tabla_b(brazo: int, antebrazo: int, muneca: int) -> int:
    """Consulta la Tabla B REBA, validando cada rango."""

    if not 1 <= brazo <= 6 or not 1 <= antebrazo <= 2 or not 1 <= muneca <= 3:
        raise ValueError("Tabla B: brazo debe ser 1–6, antebrazo 1–2 y muñeca 1–3.")
    return TABLA_B[brazo - 1][antebrazo - 1][muneca - 1]


def puntaje_tabla_c(puntaje_a: int, puntaje_b: int) -> int:
    """Consulta la Tabla C REBA, validando cada rango."""

    if not 1 <= puntaje_a <= 12 or not 1 <= puntaje_b <= 12:
        raise ValueError("Tabla C: los puntajes A y B deben estar entre 1 y 12.")
    return TABLA_C[puntaje_a - 1][puntaje_b - 1]


def puntaje_carga(carga_kg: float | None, fuerza_brusca: bool, config: RebaConfig) -> int | None:
    """Puntúa carga/fuerza, sin inventar la carga ausente."""

    if carga_kg is None:
        return None
    if carga_kg < config.carga_kg.baja:
        puntaje = 0
    elif carga_kg <= config.carga_kg.alta:
        puntaje = 1
    else:
        puntaje = 2
    return puntaje + int(fuerza_brusca)


def puntaje_agarre(agarre: str | None) -> int | None:
    """Traduce la calidad de agarre declarada a la escala REBA."""

    return {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 3}.get(agarre)


def puntaje_actividad(actividad: dict[str, Any] | None) -> int:
    """Suma los tres ajustes de actividad REBA declarados."""

    actividad = actividad or {}
    return sum(bool(actividad.get(clave, False)) for clave in ("estatica_mas_1min", "repetitiva_mas_4_por_min", "cambios_bruscos_o_base_inestable"))


def nivel_riesgo(puntaje: int) -> NivelRiesgo:
    """Convierte el REBA final a riesgo y nivel de acción."""

    if puntaje == 1:
        return NivelRiesgo("Inapreciable", 0)
    if puntaje <= 3:
        return NivelRiesgo("Bajo", 1)
    if puntaje <= 7:
        return NivelRiesgo("Medio", 2)
    if puntaje <= 10:
        return NivelRiesgo("Alto", 3)
    return NivelRiesgo("Muy alto", 4)


def calcular_reba(mediciones: dict[str, float | None], contexto: dict[str, Any], config: RebaConfig) -> ResultadoReba:
    """Calcula REBA completo; ante datos faltantes conserva los pendientes."""

    pendientes: list[dict[str, str]] = []

    def dato(nombre: str) -> float | None:
        valor = mediciones.get(nombre)
        if valor is None:
            pendientes.append({"medida": nombre, "motivo": "medición ausente o no utilizable"})
        return valor

    tronco_v, cuello_v = dato("tronco_flexion"), dato("cuello_flexion")
    torsion, lateral = dato("tronco_torsion"), dato("tronco_inclinacion_lateral")
    apoyo = dato("apoyo_piernas_unilateral")
    rodillas = [dato("rodilla_flexion_L"), dato("rodilla_flexion_R")]
    sentado = contexto.get("postura") == "sentado"
    tronco = banda_tronco(tronco_v, torsion, lateral, config) if tronco_v is not None else None
    cuello_lateral = dato("cuello_inclinacion_rotacion")
    cuello = banda_cuello(cuello_v, cuello_lateral, config) if cuello_v is not None else None
    piernas = banda_piernas(bool(apoyo), max(valor for valor in rodillas if valor is not None), sentado, config) if apoyo is not None and all(valor is not None for valor in rodillas) else None
    carga = puntaje_carga(contexto.get("carga_kg"), bool(contexto.get("fuerza_brusca", False)), config)
    if carga is None:
        pendientes.append({"medida": "carga_kg", "motivo": "carga no declarada"})
    tabla_a = puntaje_tabla_a(tronco, cuello, piernas) if None not in (tronco, cuello, piernas) else None
    puntaje_a = tabla_a + carga if tabla_a is not None and carga is not None else None

    grupo_b: dict[str, dict[str, int | None]] = {}
    tabla_c: dict[str, int | None] = {}
    finales: dict[str, int | None] = {}
    agarre = puntaje_agarre(contexto.get("agarre"))
    if agarre is None:
        pendientes.append({"medida": "agarre", "motivo": "agarre ausente o inválido"})
    hombros = contexto.get("hombro_elevado", {})
    apoyos = contexto.get("brazo_apoyado", {})
    desviaciones = contexto.get("muneca_desviada_o_torcida", {})
    for lado, letra in (("izquierdo", "L"), ("derecho", "R")):
        brazo_v, antebrazo_v, muneca_v, abduccion = (dato(f"{nombre}_{letra}") for nombre in ("brazo_flexion", "codo_flexion", "muneca_flexion_extension", "brazo_abduccion"))
        elevado = hombros.get(lado) if isinstance(hombros, dict) else None
        desviada = desviaciones.get(lado) if isinstance(desviaciones, dict) else None
        apoyado = apoyos.get(lado, False) if isinstance(apoyos, dict) else False
        if elevado is None:
            pendientes.append({"medida": f"hombro_elevado_{letra}", "motivo": "ajuste de hombro no declarado"})
        if desviada is None:
            pendientes.append({"medida": f"muneca_desviada_o_torcida_{letra}", "motivo": "ajuste de muñeca no declarado"})
        brazo = banda_brazo(brazo_v, abduccion, bool(elevado), bool(apoyado), config) if brazo_v is not None and abduccion is not None and elevado is not None else None
        antebrazo = banda_antebrazo(antebrazo_v, config) if antebrazo_v is not None else None
        muneca = banda_muneca(muneca_v, bool(desviada), config) if muneca_v is not None and desviada is not None else None
        tabla_b = puntaje_tabla_b(brazo, antebrazo, muneca) if None not in (brazo, antebrazo, muneca) else None
        puntaje_b = tabla_b + agarre if tabla_b is not None and agarre is not None else None
        grupo_b[letra] = {"brazo": brazo, "antebrazo": antebrazo, "muneca": muneca, "tabla_b": tabla_b, "agarre": agarre, "puntaje_b": puntaje_b}
        tabla_c[letra] = puntaje_tabla_c(puntaje_a, puntaje_b) if puntaje_a is not None and puntaje_b is not None else None
        finales[letra] = tabla_c[letra] + puntaje_actividad(contexto.get("actividad")) if tabla_c[letra] is not None else None

    actividad = puntaje_actividad(contexto.get("actividad"))
    lado_configurado = config.lado_reportado
    if lado_configurado == "izquierdo":
        lado = "L"
    elif lado_configurado == "derecho":
        lado = "R"
    elif finales["L"] is not None and finales["R"] is not None:
        lado = "L" if finales["L"] >= finales["R"] else "R"
    else:
        lado = None
    reportado = finales[lado] if lado is not None else None
    nivel = nivel_riesgo(reportado) if reportado is not None else None
    grupo_a = {"tronco": tronco, "cuello": cuello, "piernas": piernas, "tabla_a": tabla_a, "carga": carga, "puntaje_a": puntaje_a}
    return ResultadoReba(grupo_a, grupo_b, tabla_c, actividad, {"L": finales["L"], "R": finales["R"], "reportado": reportado, "lado": lado}, nivel.nombre if nivel else None, nivel.nivel_accion if nivel else None, pendientes)
