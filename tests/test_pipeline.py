import json
from pathlib import Path

import pytest
from PIL import Image

from ergoai.cli import ejecutar_evaluar
from ergoai.modelos import Landmark, PoseResult


def _landmarks_sinteticos() -> list[Landmark]:
    """Cuerpo completo artificial para probar el pipeline sin MediaPipe."""

    coordenadas = {indice: (20.0 + indice * 3, 30.0 + indice * 4) for indice in range(33)}
    coordenadas.update({
        0: (100, 55), 7: (96, 70), 8: (104, 70),
        11: (100, 100), 12: (110, 100), 13: (130, 152), 14: (140, 152),
        15: (150, 206), 16: (160, 206), 17: (145, 216), 18: (155, 216),
        19: (155, 216), 20: (165, 216), 23: (50, 186.6), 24: (60, 186.6),
        25: (55, 250), 26: (65, 250), 27: (60, 310), 28: (70, 310),
        29: (40, 310), 30: (50, 310), 31: (60, 310), 32: (70, 310),
    })
    return [Landmark(indice, str(indice), *coordenadas[indice], 0.0, 0.95, 0.95) for indice in range(33)]


class BackendSintetico:
    def detect(self, image):
        return [PoseResult(_landmarks_sinteticos(), [])]


def _overrides_completos() -> dict[str, float]:
    overrides = {"tronco_flexion": 30, "cuello_flexion": 25, "tronco_torsion": 0, "tronco_inclinacion_lateral": 0, "cuello_inclinacion_rotacion": 0, "apoyo_piernas_unilateral": 1}
    for lado in ("L", "R"):
        overrides.update({f"rodilla_flexion_{lado}": 0, f"brazo_flexion_{lado}": 60, f"codo_flexion_{lado}": 50, f"muneca_flexion_extension_{lado}": 20, f"brazo_abduccion_{lado}": 0})
    return overrides


def _evaluar(tmp_path: Path, overrides: dict, vistas=("frente", "costado", "aerea")) -> dict:
    raiz = tmp_path / "proyecto"
    (raiz / "config").mkdir(parents=True)
    (raiz / "config" / "umbrales.yaml").write_text(
        (Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    caso = tmp_path / "caso"
    caso.mkdir()
    for vista in vistas:
        Image.new("RGB", (300, 400)).save(caso / f"{vista}.png")
    contexto = {
        "caso_id": "sintetico", "orientacion_costado": "derecha", "postura": "de_pie",
        "carga_kg": 8, "agarre": "regular", "actividad": {"estatica_mas_1min": True},
        "hombro_elevado": {"izquierdo": False, "derecho": False},
        "brazo_apoyado": {"izquierdo": False, "derecho": False},
        "muneca_desviada_o_torcida": {"izquierdo": False, "derecho": False}, "overrides": overrides,
    }
    (caso / "contexto.json").write_text(json.dumps(contexto), encoding="utf-8")
    salida = ejecutar_evaluar(caso, raiz, BackendSintetico())
    return json.loads(salida.read_text(encoding="utf-8"))


def _angulo(resultado: dict, medida: str, lado: str | None = None) -> dict:
    return next(angulo for angulo in resultado["angulos"] if angulo["medida"] == medida and angulo.get("lado") == lado)


def test_pipeline_sintetico_sin_mediapipe_produce_reba_esperado(tmp_path: Path) -> None:
    resultado = _evaluar(tmp_path, _overrides_completos())
    assert resultado["reba"]["final"]["reportado"] == 9, resultado["reba"]
    assert resultado["reba"]["nivel_riesgo"] == "Alto"
    assert resultado["reba"]["nivel_accion"] == 3


def test_override_sobre_angulo_medido_conserva_valor_automatico(tmp_path: Path) -> None:
    resultado = _evaluar(tmp_path, _overrides_completos())
    tronco = _angulo(resultado, "tronco_flexion")
    assert tronco["valor_deg"] == 30.0
    assert tronco["fuente"] == "especialista"
    assert isinstance(tronco["valor_medido_deg"], float) and tronco["valor_medido_deg"] != 30.0
    assert resultado["reba"]["grupo_a"]["tronco"] == 3


def test_override_completa_torsion_sin_foto_aerea(tmp_path: Path) -> None:
    resultado = _evaluar(tmp_path, {**_overrides_completos(), "tronco_torsion": 25}, vistas=("frente", "costado"))
    torsion = _angulo(resultado, "tronco_torsion")
    assert torsion["valor_deg"] == 25.0
    assert torsion["fuente"] == "especialista"
    assert torsion["valor_medido_deg"] is None
    assert torsion["vista"] is None
    assert torsion["metodo"] == "override_especialista"
    assert all(pendiente["medida"] != "tronco_torsion" for pendiente in resultado["pendientes_manuales"])
    assert resultado["reba"]["grupo_a"]["tronco"] == 4


def test_override_por_lado_sin_foto_de_frente(tmp_path: Path) -> None:
    resultado = _evaluar(tmp_path, {**_overrides_completos(), "brazo_abduccion_L": 30}, vistas=("costado", "aerea"))
    assert _angulo(resultado, "brazo_abduccion", "L")["valor_deg"] == 30.0
    assert resultado["reba"]["grupo_b"]["L"]["brazo"] == 4
    assert resultado["reba"]["grupo_b"]["R"]["brazo"] == 3
    assert resultado["pendientes_manuales"] == []


def test_override_por_lado_tiene_prioridad_sobre_generico(tmp_path: Path) -> None:
    overrides = {clave: valor for clave, valor in _overrides_completos().items() if not clave.startswith("codo_flexion")}
    resultado = _evaluar(tmp_path, {**overrides, "codo_flexion": 80, "codo_flexion_R": 50})
    assert _angulo(resultado, "codo_flexion", "L")["valor_deg"] == 80.0
    assert _angulo(resultado, "codo_flexion", "R")["valor_deg"] == 50.0


def test_override_con_clave_desconocida_se_rechaza(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tronco_flexon") as error:
        _evaluar(tmp_path, {"tronco_flexon": 30})
    assert "tronco_flexion" in str(error.value) and "codo_flexion_R" in str(error.value)


@pytest.mark.parametrize("valor", ["30", True])
def test_override_no_numerico_se_rechaza(tmp_path: Path, valor) -> None:
    with pytest.raises(ValueError, match="tronco_flexion"):
        _evaluar(tmp_path, {"tronco_flexion": valor})
