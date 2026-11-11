"""Cambios de José (8804acf): pendientes sin duplicados, torsión en la vista aérea y etiquetas legibles."""

import numpy as np

from ergoai.anotacion import anotar_angulos
from ergoai.angulos import MedicionAngulo
from ergoai.cli import _compactar_pendientes, _medidas_para_anotar
from ergoai.modelos import Landmark, VistaPose
from ergoai.respaldos import completar_con_respaldos
from test_respaldos import _cuerpo_3d, _vista


def test_pendientes_sin_duplicados_ni_avisos_ya_resueltos() -> None:
    pendientes = [
        # Ángulos y REBA avisan por separado de la misma muñeca (caso real de ensamble).
        {"medida": "muneca_flexion_extension", "lado": "L", "motivo": "landmarks requeridos no utilizables"},
        {"medida": "muneca_flexion_extension_L", "motivo": "medición ausente o no utilizable"},
        # El codo derecho no se midió en su vista, pero un respaldo o el especialista ya le dio valor.
        {"medida": "codo_flexion", "lado": "R", "motivo": "landmarks requeridos no utilizables"},
        # Lo que el contexto no declara sigue pendiente aunque no sea un ángulo.
        {"medida": "hombro_elevado_L", "motivo": "ajuste de hombro no declarado"},
        {"medida": "cuello_flexion", "lado": "L", "motivo": "medición ausente o no utilizable"},
    ]
    mediciones = {"muneca_flexion_extension_L": None, "codo_flexion_R": 95.0, "cuello_flexion": None}
    compactos = _compactar_pendientes(pendientes, mediciones)
    assert [p["medida"] for p in compactos] == ["muneca_flexion_extension", "hombro_elevado_L", "cuello_flexion"]


def test_torsion_3d_se_etiqueta_en_la_aerea_aunque_su_pose_fallara(configuracion) -> None:
    aerea_sin_pose = VistaPose("aerea", 640, 480, False, 0, motivo="sin persona")
    vistas = {"costado": _vista("costado", _cuerpo_3d(torsion=25)), "aerea": aerea_sin_pose}
    torsion = next(m for m in completar_con_respaldos([], vistas, {}, configuracion) if m.medida == "tronco_torsion")
    assert torsion.vista == "aerea"
    # El origen real no se pierde: método y bandera dicen que vino del 3D del costado.
    assert torsion.metodo.startswith("respaldo 3D (pose de costado)") and "vista_respaldo" in torsion.banderas


def test_la_aerea_siempre_dibuja_la_torsion_si_existe() -> None:
    torsion = MedicionAngulo("tronco_torsion", None, 25.0, "costado", "respaldo 3D", 0.9)
    tronco = MedicionAngulo("tronco_flexion", None, 30.0, "costado", "theta", 0.9)
    pendiente = MedicionAngulo("tronco_inclinacion_lateral", None, None, "aerea", "", None)
    assert _medidas_para_anotar([torsion, tronco, pendiente], "aerea") == [torsion]
    assert _medidas_para_anotar([torsion, tronco], "costado") == [torsion, tronco]


def test_umbral_de_dibujo_mas_bajo_muestra_el_esqueleto_de_la_aerea() -> None:
    puntos = {11: (300, 120), 12: (340, 120), 23: (305, 260), 24: (335, 260), 13: (290, 190), 14: (350, 190)}
    # Desde arriba MediaPipe da poca visibilidad (0.3): con el umbral de medición (0.5) no se dibuja nada.
    landmarks = [Landmark(i, str(i), x, y, 0.0, 0.3, 0.3) for i, (x, y) in puntos.items()]
    fondo = np.full((480, 640, 3), 128, np.uint8)

    def pintados(vis_dibujo):
        imagen = np.asarray(anotar_angulos(fondo, landmarks, 0.5, [], [], vis_dibujo=vis_dibujo))
        return int(np.count_nonzero(np.any(imagen != 128, axis=2)))

    sin_umbral, con_umbral = pintados(None), pintados(0.22)
    assert con_umbral > sin_umbral, "el esqueleto con poca visibilidad debe dibujarse en la aérea"


def test_ninguna_etiqueta_queda_bajo_la_leyenda(monkeypatch) -> None:
    from ergoai import anotacion

    cajas: list[tuple[float, float, float, float]] = []
    original = anotacion._elegir_caja

    def espiar(*args, **kwargs):
        caja, siguiente = original(*args, **kwargs)
        cajas.append(caja)
        leyenda = args[8][0]  # «ocupadas» empieza con la caja de la leyenda
        assert not anotacion._solapa(caja, leyenda), "la etiqueta quedó debajo de la leyenda"
        return caja, siguiente

    monkeypatch.setattr(anotacion, "_elegir_caja", espiar)
    # Rodilla y tobillo pegados a la esquina inferior izquierda, donde va la leyenda.
    puntos = {11: (60, 200), 12: (90, 200), 23: (62, 330), 24: (88, 330), 25: (40, 420), 26: (70, 420), 27: (35, 470), 28: (65, 470)}
    landmarks = [Landmark(i, str(i), x, y, 0.0, 0.95, 0.95) for i, (x, y) in puntos.items()]
    medidas = [MedicionAngulo("rodilla_flexion", lado, 21.0, "costado", "angulo_entre", 0.9) for lado in ("L", "R")]
    anotar_angulos(np.full((480, 640, 3), 128, np.uint8), landmarks, 0.5, medidas, [1, 1])
    assert len(cajas) == 2
