from ergoai.modelos import Landmark, VistaPose
from ergoai.proponer_contexto import clasificar_y_asignar, proponer_desde_vistas, puntuaciones_vista


def _vista(nombre: str, puntos: dict[int, tuple[float, float]]) -> VistaPose:
    landmarks = [Landmark(i, str(i), x, y, 0.0, 0.95, 0.95) for i, (x, y) in puntos.items()]
    return VistaPose(nombre, 640, 480, True, 1, persona_indice=0, landmarks=landmarks, world_landmarks=[])


def _vista_frente() -> VistaPose:
    # Hombros simétricos, nariz centrada, tronco alto → frente.
    return _vista("frente", {
        0: (320, 60),
        11: (260, 120), 12: (380, 120),
        23: (280, 280), 24: (360, 280),
    })


def _vista_costado() -> VistaPose:
    # Un hombro mucho más visible que el otro → costado.
    landmarks = [
        Landmark(0, "0", 300, 60, 0.0, 0.4, 0.4),
        Landmark(11, "11", 310, 120, 0.0, 0.95, 0.95),
        Landmark(12, "12", 330, 125, 0.0, 0.2, 0.2),
        Landmark(23, "23", 315, 280, 0.0, 0.9, 0.9),
        Landmark(24, "24", 325, 282, 0.0, 0.25, 0.25),
    ]
    return VistaPose("costado", 640, 480, True, 1, persona_indice=0, landmarks=landmarks, world_landmarks=[])


def _vista_aerea() -> VistaPose:
    # Hombros anchos y tronco “aplastado”.
    return _vista("aerea", {
        0: (320, 200),
        11: (200, 220), 12: (440, 220),
        23: (240, 260), 24: (400, 260),
    })


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


def test_puntuaciones_prefieren_nombre_de_archivo() -> None:
    vacia = VistaPose("x", 640, 480, False, 0, motivo="sin detección")
    pts = puntuaciones_vista(vacia, "foto_aerea_linea3.jpg")
    assert pts["aerea"] > pts["costado"]
    assert pts["aerea"] > pts["frente"]


def test_clasificar_asigna_vistas_distintas() -> None:
    out = clasificar_y_asignar([
        ("a", _vista_costado(), "lado.jpg"),
        ("b", _vista_frente(), "front.jpg"),
        ("c", _vista_aerea(), "overhead.jpg"),
    ])
    assert out["ok"] is True
    vistas = {a["vista"] for a in out["asignaciones"]}
    assert vistas == {"costado", "frente", "aerea"}
    por_id = {a["id"]: a["vista"] for a in out["asignaciones"]}
    assert por_id["a"] == "costado"
    assert por_id["b"] == "frente"
    assert por_id["c"] == "aerea"
