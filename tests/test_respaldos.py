from math import cos, radians, sin

import numpy as np
import pytest

from ergoai.anotacion import COLOR_BANDA, anotar_angulos
from ergoai.angulos import MedicionAngulo
from ergoai.modelos import Landmark, VistaPose, WorldLandmark
from ergoai.reba import banda_medida
from ergoai.respaldos import completar_con_respaldos


def _mundo(puntos: dict[int, tuple[float, float, float]]) -> list[WorldLandmark]:
    return [WorldLandmark(i, str(i), *xyz, 0.95, 0.95) for i, xyz in puntos.items()]


def _cuerpo_3d(flexion=0.0, torsion=0.0, abduccion=0.0) -> list[WorldLandmark]:
    """Persona de frente a la cámara (y hacia abajo, z hacia la cámara) con ángulos conocidos."""

    f, t, a = radians(flexion), radians(torsion), radians(abduccion)
    hombro_medio = (0.0, -0.5 * cos(f), -0.5 * sin(f))  # se inclina hacia delante (-z)
    medio_ancho = 0.18
    hombro_l = (hombro_medio[0] - medio_ancho * cos(t), hombro_medio[1], hombro_medio[2] - medio_ancho * sin(t))
    hombro_r = (hombro_medio[0] + medio_ancho * cos(t), hombro_medio[1], hombro_medio[2] + medio_ancho * sin(t))
    codo_l = (hombro_l[0] - 0.3 * sin(a), hombro_l[1] + 0.3 * cos(a), hombro_l[2])
    codo_r = (hombro_r[0] + 0.3 * sin(a), hombro_r[1] + 0.3 * cos(a), hombro_r[2])
    return _mundo({
        0: (0.0, hombro_medio[1] - 0.22, hombro_medio[2] - 0.05), 7: (-0.07, hombro_medio[1] - 0.2, hombro_medio[2]),
        8: (0.07, hombro_medio[1] - 0.2, hombro_medio[2]), 11: hombro_l, 12: hombro_r, 13: codo_l, 14: codo_r,
        15: (codo_l[0], codo_l[1] + 0.25, codo_l[2]), 16: (codo_r[0], codo_r[1] + 0.25, codo_r[2]),
        23: (-0.1, 0.0, 0.0), 24: (0.1, 0.0, 0.0), 25: (-0.1, 0.45, 0.0), 26: (0.1, 0.45, 0.0), 27: (-0.1, 0.9, 0.0), 28: (0.1, 0.9, 0.0),
    })


def _vista(nombre: str, mundo: list[WorldLandmark] | None = None, puntos: dict[int, tuple[float, float]] | None = None) -> VistaPose:
    landmarks = [Landmark(i, str(i), x, y, 0.0, 0.95, 0.95) for i, (x, y) in (puntos or {}).items()]
    return VistaPose(nombre, 640, 480, True, 1, persona_indice=0, landmarks=landmarks, world_landmarks=mundo or [])


def _valor(medidas: list[MedicionAngulo], medida: str, lado: str | None = None) -> MedicionAngulo:
    return next(m for m in medidas if m.medida == medida and (lado is None or m.lado == lado))


def test_sin_frente_ni_aerea_la_pose_3d_cubre_tronco_torsion_y_abduccion(configuracion) -> None:
    vistas = {"costado": _vista("costado", _cuerpo_3d(flexion=35, torsion=25, abduccion=40))}
    medidas = completar_con_respaldos([], vistas, {}, configuracion)
    assert _valor(medidas, "tronco_flexion").valor_deg == pytest.approx(35, abs=0.5)
    assert _valor(medidas, "tronco_torsion").valor_deg == pytest.approx(25, abs=0.5)
    assert _valor(medidas, "brazo_abduccion", "L").valor_deg == pytest.approx(40, abs=1)
    assert _valor(medidas, "tronco_inclinacion_lateral").valor_deg == pytest.approx(0, abs=0.5)
    for medida in medidas:
        assert "vista_respaldo" in medida.banderas and medida.vista == "costado" and medida.metodo.startswith("respaldo 3D")
    assert "baja_confianza_metodo" in _valor(medidas, "tronco_flexion").banderas  # solo magnitud


def test_la_vista_primaria_valida_no_se_reemplaza(configuracion) -> None:
    primaria = MedicionAngulo("tronco_flexion", None, 12.0, "costado", "theta_arriba(v_tronco)", 0.9)
    medidas = completar_con_respaldos([primaria], {"costado": _vista("costado", _cuerpo_3d(flexion=50))}, {}, configuracion)
    assert _valor(medidas, "tronco_flexion") is primaria


def test_codo_ilegible_de_costado_se_mide_de_frente(configuracion) -> None:
    faltante = MedicionAngulo("codo_flexion", "L", None, "costado", "angulo_entre", None, motivo="landmarks requeridos no utilizables")
    frente = _vista("frente", puntos={11: (300, 100), 12: (360, 100), 13: (300, 180), 15: (380, 180), 23: (310, 260), 24: (350, 260)})
    medidas = completar_con_respaldos([faltante], {"frente": frente}, {}, configuracion)
    codo = _valor(medidas, "codo_flexion", "L")
    assert codo.valor_deg == pytest.approx(90) and codo.vista == "frente"
    assert {"vista_respaldo", "posible_escorzo"} <= set(codo.banderas)
    assert sum(1 for m in medidas if m.medida == "codo_flexion" and m.lado == "L") == 1  # reemplaza, no duplica


def test_apoyo_de_piernas_por_contexto_sentado(configuracion) -> None:
    medidas = completar_con_respaldos([], {}, {"postura": "sentado"}, configuracion)
    apoyo = _valor(medidas, "apoyo_piernas_unilateral")
    assert apoyo.valor_deg == 0.0 and apoyo.vista == "contexto" and "vista_respaldo" in apoyo.banderas
    assert not any(m.medida == "apoyo_piernas_unilateral" for m in completar_con_respaldos([], {}, {"postura": "de_pie"}, configuracion))


def test_banda_por_medida(configuracion) -> None:
    r = configuracion.reba
    assert banda_medida("tronco_flexion", 3, r) == 1 and banda_medida("tronco_flexion", 45, r) == 3 and banda_medida("tronco_flexion", 70, r) == 4
    assert banda_medida("brazo_flexion", 100, r) == 4 and banda_medida("codo_flexion", 80, r) == 1 and banda_medida("codo_flexion", 40, r) == 2
    assert banda_medida("rodilla_flexion", 45, r) == 2 and banda_medida("rodilla_flexion", 70, r) == 3
    assert banda_medida("tronco_torsion", 30, r) == 2 and banda_medida("tronco_torsion", 5, r) == 1
    assert banda_medida("tronco_flexion", None, r) is None


def test_imagen_anotada_colorea_por_banda(configuracion) -> None:
    puntos = {11: (300, 120), 12: (340, 120), 13: (300, 200), 14: (340, 200), 15: (330, 260), 16: (370, 260),
              23: (305, 260), 24: (335, 260), 25: (305, 360), 26: (335, 360), 27: (305, 450), 28: (335, 450)}
    landmarks = [Landmark(i, str(i), x, y, 0.0, 0.95, 0.95) for i, (x, y) in puntos.items()]
    medidas = [MedicionAngulo("tronco_flexion", None, 70.0, "costado", "theta", 0.9),
               MedicionAngulo("codo_flexion", "L", 40.0, "costado", "angulo_entre", 0.9, banderas=["cerca_de_umbral"])]
    imagen = np.asarray(anotar_angulos(np.full((480, 640, 3), 128, np.uint8), landmarks, 0.5, medidas, [4, 2]))
    assert imagen.shape == (480, 640, 3)
    colores = {tuple(c) for c in imagen.reshape(-1, 3)}
    assert COLOR_BANDA[4] in colores and COLOR_BANDA[2] in colores  # flechas/etiquetas en el color de su banda
