import csv
import json
from pathlib import Path

import pytest
from PIL import Image

from ergoai.cli import ejecutar_evaluar
from ergoai.modelos import PoseResult
from ergoai.reporte_precision import crear_plantilla, generar_reporte
from test_informe_validacion import CONTEXTO, MEDICIONES
from test_pipeline import _landmarks_sinteticos


class _Backend:
    def detect(self, image):
        return [PoseResult(_landmarks_sinteticos(), [])]


def _caso(validacion: Path, caso_id: str, referencia: dict) -> None:
    carpeta = validacion / caso_id
    carpeta.mkdir(parents=True)
    for vista in ("costado", "frente", "aerea"):
        Image.new("RGB", (300, 400)).save(carpeta / f"{vista}.png")
    (carpeta / "contexto.json").write_text(json.dumps({**CONTEXTO, "caso_id": caso_id, "orientacion_costado": "derecha", "overrides": MEDICIONES}), encoding="utf-8")
    (carpeta / "referencia.json").write_text(json.dumps(referencia), encoding="utf-8")


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "umbrales.yaml").write_text((Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_reporte_mide_criterios_1_y_2(raiz: Path, tmp_path: Path) -> None:
    validacion, salida = tmp_path / "validacion", tmp_path / "salida"
    # Mismo REBA y ángulos dentro de banda (45° y 50° están en la banda 3 del tronco)
    _caso(validacion, "v1", {"reba": {"puntaje": 11}, "angulos": [
        {"medida": "tronco_flexion", "lado": None, "valor_deg": 50}, {"medida": "codo_flexion", "lado": "L", "valor_deg": 55},
        {"medida": "brazo_flexion", "lado": "R", "valor_deg": 50}]})
    # REBA distinto y un ángulo fuera de banda (25° = banda 2 del cuello vs 10° = banda 1)
    _caso(validacion, "v2", {"reba": {"puntaje": 7, "nivel": "Medio"}, "angulos": [
        {"medida": "cuello_flexion", "lado": None, "valor_deg": 10}, {"medida": "tronco_torsion", "lado": None, "valor_deg": 30}]})
    evaluar = lambda caso, r, destino: ejecutar_evaluar(caso, r, _Backend(), destino)  # noqa: E731
    resumen = generar_reporte(validacion, raiz, salida, evaluar=evaluar)

    assert resumen["casos"] == 2
    assert resumen["criterio_1"]["coinciden"] == 1 and resumen["criterio_1"]["comparables"] == 2
    assert resumen["criterio_2"]["segmentos"] == 4 and resumen["criterio_2"]["misma_banda_pct"] == 75.0
    assert resumen["por_medida"]["tronco_flexion"]["error_medio_deg"] == 5.0
    assert resumen["ajustes_misma_banda_pct"] == 100.0
    assert "Bueno (11-13)" in resumen["criterio_2"]["rubrica"]
    assert not (raiz / "out").exists(), "la validación no debe mezclarse con los casos de la interfaz"
    html = (salida / "reporte.html").read_text(encoding="utf-8")
    assert "1 de 2" in html and "75.0 %" in html and "Flexión de cuello" in html
    with (salida / "precision.csv").open(encoding="utf-8-sig") as archivo:
        assert len(list(csv.DictReader(archivo))) == 5


def test_medida_sin_estimar_cuenta_como_fallo(raiz: Path, tmp_path: Path) -> None:
    validacion = tmp_path / "validacion"
    _caso(validacion, "v3", {"angulos": [{"medida": "rodilla_flexion", "lado": "L", "valor_deg": 40},
                                         {"medida": "inventada_flexion", "lado": None, "valor_deg": 10}]})
    resumen = generar_reporte(validacion, raiz, tmp_path / "s", evaluar=lambda c, r, d: ejecutar_evaluar(c, r, _Backend(), d))
    assert resumen["criterio_1"]["comparables"] == 0 and "sin referencias REBA" in resumen["criterio_1"]["rubrica"]


def test_plantilla_de_referencia(tmp_path: Path) -> None:
    ruta = crear_plantilla(tmp_path / "caso09")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["caso_id"] == "caso09" and datos["reba"] == {"puntaje": None, "nivel": None}
    assert {"medida": "codo_flexion", "lado": "R", "valor_deg": None} in datos["angulos"]
    with pytest.raises(FileExistsError):
        crear_plantilla(tmp_path / "caso09")
