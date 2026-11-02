import pytest

from ergoai.eaws import calcular_eaws
from ergoai.muneca import medir_muneca_con_mano
from ergoai.nom036 import empuje_arrastre, levantamiento_distancia, torsion_lateral
from ergoai.rula import banda_antebrazo, banda_brazo, banda_cuello, banda_muneca, calcular_rula, puntaje_actividad, puntaje_carga, puntaje_tabla_a, puntaje_tabla_b


def test_rula_tablas_bandas_y_resultado(configuracion) -> None:
    config = configuracion.rula
    assert banda_brazo(45, False, False, False, config) == 2
    assert banda_antebrazo(60, config) == 1
    assert banda_muneca(15, False, config) == 2
    assert puntaje_tabla_a(1, 1, 1, 1) == 1
    assert puntaje_tabla_a(6, 3, 4, 2) == 9
    assert puntaje_tabla_b(1, 1, 1) == 1
    assert puntaje_tabla_b(6, 6, 2) == 9
    resultado = calcular_rula(1, 1, 1, 1, 1, 1, 1)
    assert resultado.final == 1
    assert resultado.nivel_accion == 1
    assert puntaje_actividad(True, False) == 1
    assert puntaje_carga(11, True, False, config) == 3


def test_eaws_y_sugerencias_nom(configuracion) -> None:
    resultado = calcular_eaws(60, 1, 4, 10, 0, False, False, 8, 10, configuracion.eaws)
    assert resultado.postura == 1
    assert resultado.fuerza == 1
    assert resultado.nivel in {"Bajo", "Medio", "Alto"}
    assert levantamiento_distancia(True, True).puntaje_visual == 6
    assert torsion_lateral(True, False).puntaje_visual == 1
    assert empuje_arrastre(True, False).nivel == "rojo"


def test_muneca_con_hand_landmarks() -> None:
    mano = [(0.0, 0.0)] * 21
    mano[5], mano[17] = (1.0, 1.0), (-1.0, 1.0)
    resultado = medir_muneca_con_mano((0.0, 1.0), mano, 0.9)
    assert resultado.valor_deg == pytest.approx(0)
    assert resultado.confianza == 0.9
    assert medir_muneca_con_mano((0.0, 1.0), []).valor_deg is None


def test_rula_banda_cuello(configuracion) -> None:
    config = configuracion.rula
    assert banda_cuello(-10, False, False, config) == 4
    assert banda_cuello(5, False, False, config) == 1
    assert banda_cuello(25, True, True, config) == 5
