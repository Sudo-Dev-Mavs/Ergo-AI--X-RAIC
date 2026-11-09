"""Parches tras el caso de prueba con fotos reales: apoyo de piernas en 3D, rango REBA y texto del cuello."""

import pytest

from ergoai.modelos import Landmark, VistaPose, WorldLandmark
from ergoai.reba import calcular_reba
from ergoai.recomendaciones import generar_recomendaciones
from ergoai.respaldos import completar_con_respaldos

# Mediciones del caso «prueba-ensamble-01» (fotos reales), sin la muñeca izquierda.
CASO = {
    "tronco_flexion": 13.9, "cuello_flexion": 13.1, "tronco_torsion": 0.7, "tronco_inclinacion_lateral": 3.2,
    "cuello_inclinacion_rotacion": 33.6, "apoyo_piernas_unilateral": 0.0, "rodilla_flexion_L": 15.5, "rodilla_flexion_R": 21.0,
    "brazo_flexion_L": 62.2, "brazo_flexion_R": 63.9, "codo_flexion_L": 16.7, "codo_flexion_R": 35.0,
    "muneca_flexion_extension_L": None, "muneca_flexion_extension_R": 10.6, "brazo_abduccion_L": 38.8, "brazo_abduccion_R": 15.8,
}
CONTEXTO = {
    "postura": "de_pie", "carga_kg": 3, "agarre": "bueno", "actividad": {},
    "hombro_elevado": {"izquierdo": False, "derecho": False}, "brazo_apoyado": {"izquierdo": False, "derecho": False},
    "muneca_desviada_o_torcida": {"izquierdo": False, "derecho": False},
}


def test_con_un_dato_faltante_el_rango_contiene_todos_los_resultados_posibles(configuracion) -> None:
    reba = calcular_reba(CASO, CONTEXTO, configuracion.reba).a_diccionario()
    assert reba["final"]["reportado"] is None and reba["nivel_riesgo"] is None  # el puntaje sigue pendiente
    rango = reba["final"]["rango"]
    assert rango is not None and rango["min"] <= rango["max"]
    posibles = set()
    for muneca in range(-60, 61, 5):
        for desviada in (False, True):
            contexto = {**CONTEXTO, "muneca_desviada_o_torcida": {"izquierdo": desviada, "derecho": False}}
            posibles.add(calcular_reba({**CASO, "muneca_flexion_extension_L": float(muneca)}, contexto, configuracion.reba).final["reportado"])
    assert min(posibles) >= rango["min"] and max(posibles) <= rango["max"]
    assert rango["nivel"] == "Medio" and rango["nivel_accion"] == 2  # 4–7: el nivel ya está determinado


def test_rango_amplio_no_inventa_un_nivel(configuracion) -> None:
    faltan = {k: (None if k.startswith(("tronco_flexion", "brazo_flexion")) else v) for k, v in CASO.items()}
    rango = calcular_reba(faltan, CONTEXTO, configuracion.reba).final["rango"]
    assert rango["max"] - rango["min"] >= 3 and rango["nivel"] is None


def test_sin_datos_faltantes_no_hay_rango(configuracion) -> None:
    completo = {**CASO, "muneca_flexion_extension_L": 5.0}
    final = calcular_reba(completo, CONTEXTO, configuracion.reba).final
    assert final["reportado"] is not None and final["rango"] is None


def test_prioridad_usa_el_nivel_del_rango(configuracion) -> None:
    reba = calcular_reba(CASO, CONTEXTO, configuracion.reba).a_diccionario()
    recs = generar_recomendaciones(CASO, CONTEXTO, reba, configuracion.reba)
    assert recs and all(rec.prioridad == "alta" for rec in recs)  # nivel Medio conocido, no «revisar»


def test_cuello_nombra_la_causa_real(configuracion) -> None:
    reba = calcular_reba(CASO, CONTEXTO, configuracion.reba).a_diccionario()
    cuello = next(r for r in generar_recomendaciones(CASO, CONTEXTO, reba, configuracion.reba) if r.id == "R-CUELLO-RED")
    assert "giro o inclinación lateral de 34°" in cuello.problema and "flexión" not in cuello.problema
    assert "al frente del operador" in cuello.solucion and "línea de visión" not in cuello.solucion
    flexionado = {**CASO, "cuello_flexion": 30.0, "cuello_inclinacion_rotacion": 0.0}
    reba = calcular_reba(flexionado, CONTEXTO, configuracion.reba).a_diccionario()
    cuello = next(r for r in generar_recomendaciones(flexionado, CONTEXTO, reba, configuracion.reba) if r.id == "R-CUELLO-RED")
    assert cuello.problema == "Cuello con flexión de 30° (más de 20°)." and "línea de visión" in cuello.solucion


def _costado(tobillo_l_y: float, tobillo_r_y: float) -> VistaPose:
    """Persona de pie: en 2D el pie trasero aparece más arriba (perspectiva); en 3D los tobillos están a la altura indicada."""

    mundo = {11: (-0.18, -0.5, 0), 12: (0.18, -0.5, 0), 23: (-0.1, 0, 0), 24: (0.1, 0, 0), 25: (-0.1, 0.45, 0), 26: (0.1, 0.45, 0),
             27: (-0.1, tobillo_l_y, 0.15), 28: (0.1, tobillo_r_y, -0.15)}
    plano = {11: (300, 120), 12: (305, 125), 23: (300, 260), 24: (305, 262), 25: (310, 360), 26: (315, 362), 27: (290, 400), 28: (330, 440)}
    return VistaPose("costado", 640, 480, True, 1, persona_indice=0,
                     landmarks=[Landmark(i, str(i), x, y, 0.0, 0.95, 0.95) for i, (x, y) in plano.items()],
                     world_landmarks=[WorldLandmark(i, str(i), *xyz, 0.95, 0.95) for i, xyz in mundo.items()])


@pytest.mark.parametrize(("tobillo_r", "esperado"), [(0.90, 0.0), (0.70, 1.0)])
def test_apoyo_de_piernas_usa_tobillos_en_3d_y_no_la_perspectiva(configuracion, tobillo_r: float, esperado: float) -> None:
    medidas = completar_con_respaldos([], {"costado": _costado(0.90, tobillo_r)}, CONTEXTO, configuracion)
    apoyo = next(m for m in medidas if m.medida == "apoyo_piernas_unilateral")
    assert apoyo.valor_deg == esperado and apoyo.metodo.startswith("respaldo 3D") and "vista_respaldo" in apoyo.banderas


def test_informe_muestra_rango_en_lugar_de_guion() -> None:
    from ergoai.informe import _cifra_riesgo

    rango = {"min": 4, "max": 6, "nivel": "Medio", "nivel_accion": 2}
    assert _cifra_riesgo({"reba": None, "nivel_riesgo": None, "rango": rango}) == "<b>4–6</b> (Medio, estimado)"
    amplio = {"min": 6, "max": 9, "nivel": None, "nivel_accion": None}
    assert _cifra_riesgo({"reba": None, "nivel_riesgo": None, "rango": amplio}) == "<b>6–9</b> (nivel por confirmar)"
    assert _cifra_riesgo({"reba": 3, "nivel_riesgo": "Bajo", "rango": None}) == "<b>3</b> (Bajo)"
