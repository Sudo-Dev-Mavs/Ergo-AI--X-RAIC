"""RULA independiente de REBA, basado en McAtamney y Corlett (1993)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import RulaConfig

# Filas brazo 1–6 × antebrazo 1–3; columnas muñeca 1–4 × giro 1–2.
TABLA_A = (
    (1,2,2,2,2,3,3,3), (2,2,2,2,3,3,3,3), (2,3,3,3,3,3,4,4),
    (2,3,3,3,3,4,4,4), (3,3,3,3,3,4,4,4), (3,4,4,4,4,4,5,5),
    (3,3,4,4,4,4,5,5), (3,4,4,4,4,4,5,5), (4,4,4,4,4,5,5,5),
    (4,4,4,4,4,5,5,5), (4,4,4,4,4,5,5,5), (4,4,4,5,5,5,6,6),
    (5,5,5,5,5,6,6,7), (5,6,6,6,6,7,7,7), (6,6,6,7,7,7,7,8),
    (7,7,7,7,7,8,8,9), (8,8,8,8,8,9,9,9), (9,9,9,9,9,9,9,9),
)
# Filas cuello 1–6; columnas tronco 1–6 × piernas 1–2.
TABLA_B = (
    (1,3,2,3,3,4,5,5,6,6,7,7), (2,3,2,3,4,5,5,5,6,7,7,7),
    (3,3,3,4,4,5,5,6,6,7,7,7), (5,5,5,6,6,7,7,7,7,7,8,8),
    (7,7,7,7,7,8,8,8,8,8,8,8), (8,8,8,8,8,8,9,9,9,9,9,9),
)
TABLA_C = (
    (1,2,3,3,4,5,5), (2,2,3,4,4,5,5), (3,3,3,4,4,5,6), (3,3,3,4,5,6,6),
    (4,4,4,5,6,7,7), (4,4,5,6,6,7,7), (5,5,6,6,7,7,7), (5,5,6,7,7,7,7),
)


@dataclass(frozen=True)
class ResultadoRula:
    """Desglose de RULA; no altera ni reutiliza el resultado REBA."""

    brazo: int
    antebrazo: int
    muneca: int
    giro_muneca: int
    cuello: int
    tronco: int
    piernas: int
    tabla_a: int
    tabla_b: int
    puntaje_c: int
    puntaje_d: int
    final: int
    nivel_accion: int

    def a_diccionario(self) -> dict[str, Any]:
        return asdict(self)


def banda_brazo(valor: float, elevado: bool, abducido: bool, apoyado: bool, config: RulaConfig) -> int:
    """Puntúa brazo RULA según su flexión/extensión y ajustes."""

    if -config.brazo.neutro <= valor <= config.brazo.neutro:
        puntuacion = 1
    elif valor < -config.brazo.neutro or valor <= config.brazo.medio:
        puntuacion = 2
    elif valor <= config.brazo.alto:
        puntuacion = 3
    else:
        puntuacion = 4
    return max(1, min(6, puntuacion + int(elevado) + int(abducido) - int(apoyado)))


def banda_antebrazo(valor: float, config: RulaConfig, cruza_linea_media: bool = False) -> int:
    """Puntúa antebrazo RULA; la salida del cuerpo/linea media ajusta +1."""

    return (1 if config.antebrazo.min <= valor <= config.antebrazo.max else 2) + int(cruza_linea_media)


def banda_muneca(valor: float, desviada: bool, config: RulaConfig) -> int:
    """Puntúa muñeca RULA."""

    absoluto = abs(valor)
    if absoluto <= config.muneca.neutro:
        puntuacion = 1
    elif absoluto <= config.muneca.flexion:
        puntuacion = 2
    else:
        puntuacion = 3
    return min(4, puntuacion + int(desviada))


def banda_cuello(valor: float, rotado: bool, inclinado: bool, config: RulaConfig) -> int:
    """Puntúa cuello RULA."""

    if valor < 0:
        puntuacion = 4
    elif valor <= config.cuello.neutro:
        puntuacion = 1
    elif valor <= config.cuello.medio:
        puntuacion = 2
    else:
        puntuacion = 3
    return min(6, puntuacion + int(rotado) + int(inclinado))


def banda_tronco(valor: float, torsion: bool, lateral: bool, config: RulaConfig) -> int:
    """Puntúa tronco RULA."""

    absoluto = abs(valor)
    if absoluto <= config.tronco.neutro:
        puntuacion = 1
    elif absoluto <= config.tronco.leve:
        puntuacion = 2
    elif absoluto <= config.tronco.moderado:
        puntuacion = 3
    else:
        puntuacion = 4
    return min(6, puntuacion + int(torsion) + int(lateral))


def puntaje_tabla_a(brazo: int, antebrazo: int, muneca: int, giro: int) -> int:
    """Consulta Tabla A de RULA."""

    if not (1 <= brazo <= 6 and 1 <= antebrazo <= 3 and 1 <= muneca <= 4 and 1 <= giro <= 2):
        raise ValueError("Tabla A RULA: puntajes fuera de rango.")
    return TABLA_A[(brazo - 1) * 3 + antebrazo - 1][(muneca - 1) * 2 + giro - 1]


def puntaje_tabla_b(cuello: int, tronco: int, piernas: int) -> int:
    """Consulta Tabla B de RULA."""

    if not (1 <= cuello <= 6 and 1 <= tronco <= 6 and 1 <= piernas <= 2):
        raise ValueError("Tabla B RULA: puntajes fuera de rango.")
    return TABLA_B[cuello - 1][(tronco - 1) * 2 + piernas - 1]


def nivel_accion(puntaje: int) -> int:
    """Nivel de acción RULA para un puntaje final de 1 a 7."""

    return 1 if puntaje <= 2 else 2 if puntaje <= 4 else 3 if puntaje <= 6 else 4


def puntaje_actividad(estatica_mas_1min: bool, repetitiva_mas_4_por_min: bool) -> int:
    """Ajuste muscular RULA: una actividad sostenida o repetitiva suma uno."""

    return int(estatica_mas_1min or repetitiva_mas_4_por_min)


def puntaje_carga(carga_kg: float, estatica_o_repetitiva: bool, fuerza_brusca: bool, config: RulaConfig) -> int:
    """Ajuste de carga RULA según peso, duración y golpes/fuerza brusca."""

    if fuerza_brusca or (carga_kg > config.carga_kg.alta and estatica_o_repetitiva):
        return 3
    if carga_kg > config.carga_kg.alta or (carga_kg >= config.carga_kg.baja and estatica_o_repetitiva):
        return 2
    if carga_kg >= config.carga_kg.baja:
        return 1
    return 0


def calcular_rula(
    brazo: int, antebrazo: int, muneca: int, giro_muneca: int, cuello: int, tronco: int,
    piernas: int, actividad: int = 0, carga: int = 0,
) -> ResultadoRula:
    """Calcula RULA a partir de bandas previamente trazables."""

    tabla_a = puntaje_tabla_a(brazo, antebrazo, muneca, giro_muneca)
    tabla_b = puntaje_tabla_b(cuello, tronco, piernas)
    puntaje_c, puntaje_d = min(8, tabla_a + actividad + carga), min(7, tabla_b + actividad + carga)
    final = TABLA_C[puntaje_c - 1][puntaje_d - 1]
    return ResultadoRula(brazo, antebrazo, muneca, giro_muneca, cuello, tronco, piernas, tabla_a, tabla_b, puntaje_c, puntaje_d, final, nivel_accion(final))
