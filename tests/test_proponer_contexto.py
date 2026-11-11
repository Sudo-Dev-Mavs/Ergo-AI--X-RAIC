from ergoai.modelos import Landmark, VistaPose
from ergoai.proponer_contexto import proponer_desde_vistas


def _vista(nombre: str, puntos: dict[int, tuple[float, float]]) -> VistaPose:
    landmarks = [Landmark(i, str(i), x, y, 0.0, 0.95, 0.95) for i, (x, y) in puntos.items()]
    return VistaPose(nombre, 640, 480, True, 1, persona_indice=0, landmarks=landmarks, world_landmarks=[])


def test_propone_trabajo_y_hombro_cuando_hay_pose(configuracion) -> None:
    # Hombros casi a la altura de las orejas → hombro elevado.
    costado = _vista("costado", {
        7: (300, 80), 8: (340, 80),
        11: (300, 100), 12: (340, 100),
        13: (280, 180), 14: (360, 180),
        15: (270, 250), 16: (370, 250),
        17: (265, 260), 19: (275, 260), 18: (375, 260), 20: (365, 260),
        23: (310, 260), 24: (330, 260),
        25: (300, 360), 26: (340, 360),
        27: (300, 450), 28: (340, 450),
    })
    frente = _vista("frente", {
        7: (300, 90), 8: (340, 90),
        11: (300, 105), 12: (340, 105),
        13: (280, 180), 14: (360, 180),
        23: (310, 260), 24: (330, 260),
        25: (300, 360), 26: (340, 360),
        27: (300, 450), 28: (340, 450),
        0: (320, 70),
    })
    out = proponer_desde_vistas({"costado": costado, "frente": frente}, configuracion, {"carga_kg": 12})
    assert out["ok"] is True
    s = out["sugerencias"]
    assert s["tipo_trabajo"] == "pesado"
    assert s["actividad"]["estatica_mas_1min"] is False
    assert s["fuerza_brusca"] is False
    assert s["hombro_elevado"]["izquierdo"] or s["hombro_elevado"]["derecho"]
    assert out["motivos"]


def test_sin_pose_devuelve_ok_false(configuracion) -> None:
    vacia = VistaPose("costado", 640, 480, False, 0, motivo="sin detección")
    out = proponer_desde_vistas({"costado": vacia}, configuracion, {})
    assert out["ok"] is False
    assert out["sugerencias"] == {}
