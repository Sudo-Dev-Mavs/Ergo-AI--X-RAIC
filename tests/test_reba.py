import pytest

from ergoai.reba import (
    MEDIDAS_REBA_POR_LADO, MEDIDAS_REBA_UNICAS,
    banda_antebrazo, banda_brazo, banda_muneca, banda_tronco, calcular_reba,
    nivel_riesgo, puntaje_tabla_a, puntaje_tabla_b, puntaje_tabla_c,
)


def test_caso_completo_calculado_a_mano(configuracion) -> None:
    medidas = {
        "tronco_flexion": 30, "cuello_flexion": 25, "tronco_torsion": 0,
        "tronco_inclinacion_lateral": 0, "cuello_inclinacion_rotacion": 0,
        "apoyo_piernas_unilateral": 1, "rodilla_flexion_L": 0, "rodilla_flexion_R": 0,
    }
    for lado in ("L", "R"):
        medidas.update({f"brazo_flexion_{lado}": 60, f"codo_flexion_{lado}": 50, f"muneca_flexion_extension_{lado}": 20, f"brazo_abduccion_{lado}": 0})
    contexto = {
        "carga_kg": 8, "fuerza_brusca": False, "agarre": "regular", "postura": "de_pie",
        "actividad": {"estatica_mas_1min": True},
        "hombro_elevado": {"izquierdo": False, "derecho": False},
        "brazo_apoyado": {"izquierdo": False, "derecho": False},
        "muneca_desviada_o_torcida": {"izquierdo": False, "derecho": False},
    }
    resultado = calcular_reba(medidas, contexto, configuracion.reba)
    assert resultado.grupo_a == {"tronco": 3, "cuello": 2, "piernas": 2, "tabla_a": 5, "carga": 1, "puntaje_a": 6}
    assert resultado.grupo_b["R"]["tabla_b"] == 5
    assert resultado.grupo_b["R"]["puntaje_b"] == 6
    assert resultado.final["reportado"] == 9
    assert resultado.nivel_riesgo == "Alto"
    assert resultado.nivel_accion == 3


def test_esquinas_de_tablas() -> None:
    assert puntaje_tabla_a(1, 1, 1) == 1
    assert puntaje_tabla_a(5, 3, 4) == 9
    assert puntaje_tabla_b(1, 1, 1) == 1
    assert puntaje_tabla_b(6, 2, 3) == 9
    assert puntaje_tabla_c(1, 1) == 1
    assert puntaje_tabla_c(12, 12) == 12
    assert nivel_riesgo(1).nombre == "Inapreciable"
    assert nivel_riesgo(15).nivel_accion == 4


def test_limites_configurados_de_bandas(configuracion) -> None:
    config = configuracion.reba
    assert banda_tronco(19.9, None, None, config) == 2
    assert banda_tronco(20, None, None, config) == 2
    assert banda_tronco(20.1, None, None, config) == 3
    assert banda_brazo(45, None, False, False, config) == 2
    assert banda_brazo(45.1, None, False, False, config) == 3
    assert banda_brazo(90, None, False, False, config) == 3
    assert banda_brazo(90.1, None, False, False, config) == 4
    assert banda_antebrazo(60, config) == 1
    assert banda_antebrazo(100, config) == 1
    assert banda_antebrazo(100.1, config) == 2
    assert banda_muneca(15, False, config) == 1
    assert banda_muneca(15.1, False, config) == 2


def test_reba_incompleto_no_inventa_valores(configuracion) -> None:
    resultado = calcular_reba({}, {}, configuracion.reba)
    assert resultado.final["reportado"] is None
    assert resultado.pendientes_manuales


def test_medidas_reba_declaradas_cubren_calcular_reba(configuracion) -> None:
    mediciones = {medida: 0.0 for medida in MEDIDAS_REBA_UNICAS}
    mediciones.update({f"{medida}_{lado}": 0.0 for medida in MEDIDAS_REBA_POR_LADO for lado in ("L", "R")})
    resultado = calcular_reba(mediciones, {}, configuracion.reba)
    assert [p for p in resultado.pendientes_manuales if p["motivo"] == "medición ausente o no utilizable"] == []
