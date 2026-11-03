import json
from pathlib import Path

import pytest
from PIL import Image

from ergoai.angulos import construir_vectores, determinar_orientacion, medir_vista
from ergoai.cli import ejecutar_angulos
from ergoai.modelos import Landmark, PoseResult, VistaPose


def _punto(indice: int, x: float, y: float) -> Landmark:
    return Landmark(indice, str(indice), x, y, 0.0, 0.95, 0.95)


def _vista_costado() -> VistaPose:
    # Persona mirando a la derecha, con el tronco a 30° hacia adelante.
    puntos = [
        _punto(11, 100, 100), _punto(12, 100, 100), _punto(23, 50, 186.6), _punto(24, 50, 186.6),
        _punto(13, 100, 160), _punto(14, 100, 160), _punto(15, 100, 220), _punto(16, 100, 220),
        _punto(17, 95, 230), _punto(18, 95, 230), _punto(19, 105, 230), _punto(20, 105, 230),
        _punto(7, 100, 70), _punto(8, 100, 70), _punto(29, 40, 300), _punto(31, 60, 300),
        _punto(30, 40, 300), _punto(32, 60, 300),
    ]
    return VistaPose("costado", 300, 400, True, 1, landmarks=puntos)


def test_vectores_y_orientacion(configuracion) -> None:
    vista = _vista_costado()
    vectores = construir_vectores(vista, configuracion.pose.vis_min)
    assert vectores["v_tronco"].px == pytest.approx((50, -86.6))
    assert determinar_orientacion(vista, {}, configuracion.pose.vis_min) == (1, "pies")


def test_mide_tronco_y_reporta_landmarks_faltantes(configuracion) -> None:
    _, medidas, metadatos = medir_vista(_vista_costado(), configuracion, {})
    tronco = next(medida for medida in medidas if medida.medida == "tronco_flexion")
    cuello = next(medida for medida in medidas if medida.medida == "cuello_flexion")
    assert metadatos["orientacion"]["s"] == 1
    assert tronco.valor_deg == pytest.approx(30, abs=0.1)
    assert cuello.valor_deg is not None
    assert any(medida.valor_deg is None for medida in medidas if medida.medida == "rodilla_flexion")


def _vista_aerea() -> VistaPose:
    # Hombros horizontales, caderas rotadas ~30°, alcance asimétrico.
    puntos = [
        _punto(11, 80, 120), _punto(12, 140, 120),
        _punto(23, 95, 200), _punto(24, 145, 180),
        _punto(13, 60, 150), _punto(14, 170, 130),
        _punto(15, 40, 170), _punto(16, 200, 125),
        _punto(17, 38, 172), _punto(18, 202, 125),
        _punto(19, 42, 172), _punto(20, 198, 125),
    ]
    return VistaPose("aerea", 300, 300, True, 1, landmarks=puntos)


def test_vista_aerea_mide_torsion_y_asimetria(configuracion) -> None:
    vectores, medidas, meta = medir_vista(_vista_aerea(), configuracion, {})
    assert "aporte_aerea" in meta
    assert vectores.get("linea_hombros") is not None
    torsion = next(m for m in medidas if m.medida == "tronco_torsion")
    asimetria = next(m for m in medidas if m.medida == "alcance_asimetria")
    assert torsion.valor_deg is not None and torsion.valor_deg > 0
    assert asimetria.valor_deg is not None
    assert "vista_aerea" in (torsion.banderas or [])


def test_pipeline_de_angulos_escribe_json_y_anotacion(tmp_path, configuracion) -> None:
    raiz = tmp_path / "proyecto"
    (raiz / "config").mkdir(parents=True)
    (raiz / "config" / "umbrales.yaml").write_text(
        (Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    caso = tmp_path / "caso01"
    caso.mkdir()
    Image.new("RGB", (300, 400)).save(caso / "costado.png")
    (caso / "contexto.json").write_text('{"caso_id": "caso01", "orientacion_costado": "derecha"}', encoding="utf-8")

    class Backend:
        def detect(self, image):
            vista = _vista_costado()
            return [PoseResult(vista.landmarks, [])]

    salida = ejecutar_angulos(caso, raiz, Backend())
    contenido = json.loads(salida.read_text(encoding="utf-8"))
    assert salida.name == "angulos.json"
    assert contenido["vectores"]["costado"]["v_tronco"]["px"] == pytest.approx([50.0, -86.6])
    assert (salida.parent / "costado_angulos.png").is_file()
