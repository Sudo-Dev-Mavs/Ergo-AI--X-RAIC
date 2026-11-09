import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ergoai import privacidad
from ergoai.modelos import PoseResult
from ergoai.servidor import crear_app
from test_informe_validacion import CONTEXTO, MEDICIONES
from test_pipeline import _landmarks_sinteticos


def _ruido(ancho=320, alto=400, semilla=7) -> np.ndarray:
    return np.random.default_rng(semilla).integers(0, 255, (alto, ancho, 3), dtype=np.uint8)


def _jpg(imagen: np.ndarray) -> bytes:
    salida = io.BytesIO()
    Image.fromarray(imagen).save(salida, format="JPEG", quality=95)
    return salida.getvalue()


def test_caja_de_cabeza_cubre_los_puntos_de_la_cara_y_queda_dentro_de_la_imagen() -> None:
    persona = PoseResult(_landmarks_sinteticos(), [])
    [(x0, y0, x1, y1)] = privacidad.cajas_desde_pose([persona], 320, 400)
    for punto in persona.landmarks[:11]:
        assert x0 <= punto.x_px <= x1 and y0 <= punto.y_px <= y1
    assert 0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 400


def test_difuminar_solo_cambia_la_region_indicada() -> None:
    imagen = _ruido()
    caja = (50, 40, 150, 140)
    salida = privacidad.difuminar(imagen, [caja])
    assert not np.array_equal(salida[40:140, 50:150], imagen[40:140, 50:150])
    assert np.array_equal(salida[200:, :], imagen[200:, :]) and np.array_equal(salida[:, 200:], imagen[:, 200:])
    # el mosaico elimina el detalle: la varianza local cae drásticamente
    assert salida[40:140, 50:150].std() < imagen[40:140, 50:150].std() * 0.5


def test_respaldo_con_detector_de_rostros_cuando_no_hay_pose() -> None:
    protegida = privacidad.proteger(_jpg(_ruido()), lambda imagen: [], lambda imagen: [(100.0, 100.0, 40.0, 50.0)])
    assert protegida.metodo == "rostro" and len(protegida.cajas) == 1
    sin_nada = privacidad.proteger(_jpg(_ruido()), lambda imagen: [])
    assert sin_nada.metodo is None and sin_nada.cajas == []


class _Contador:
    def __init__(self) -> None:
        self.llamadas = 0

    def detect(self, image):
        self.llamadas += 1
        return [PoseResult(_landmarks_sinteticos(), [])]


@pytest.fixture
def entorno(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "umbrales.yaml").write_text((Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    detector = _Contador()
    return TestClient(crear_app(tmp_path, detector), base_url="http://127.0.0.1:8765"), detector, tmp_path


def test_la_toma_se_guarda_difuminada_con_la_pose_del_original(entorno) -> None:
    cliente, detector, raiz = entorno
    original = _ruido()
    respuesta = cliente.post("/api/capturas/b1", files={"costado": ("c.jpg", _jpg(original), "image/jpeg")})
    assert respuesta.status_code == 200, respuesta.text
    toma = respuesta.json()["toma"]
    assert toma["privacidad"]["costado"] == {"rostros": 1, "metodo": "pose"}
    carpeta = raiz / "capturas" / "b1" / toma["id"]
    guardada = np.asarray(Image.open(carpeta / "costado.jpg").convert("RGB"), dtype=np.int16)
    [(x0, y0, x1, y1)] = privacidad.cajas_desde_pose([PoseResult(_landmarks_sinteticos(), [])], 320, 400)
    cabeza_original = original[y0:y1, x0:x1].astype(np.int16)
    assert np.abs(guardada[y0:y1, x0:x1] - cabeza_original).mean() > 40  # la cara ya no es la original
    cache = json.loads((carpeta / "costado.pose.json").read_text(encoding="utf-8"))
    assert cache["sha256"] == hashlib.sha256((carpeta / "costado.jpg").read_bytes()).hexdigest()
    assert len(cache["personas"]) == 1 and detector.llamadas == 1


def test_el_analisis_usa_la_pose_previa_al_difuminado(entorno) -> None:
    cliente, detector, raiz = entorno
    toma = cliente.post("/api/capturas/b2", files={v: (f"{v}.jpg", _jpg(_ruido(semilla=i)), "image/jpeg") for i, v in enumerate(("costado", "frente"))}).json()["toma"]["id"]
    antes = detector.llamadas
    contexto = {**CONTEXTO, "caso_id": "privado", "orientacion_costado": "derecha", "overrides": MEDICIONES}
    datos = cliente.post("/api/casos", data={"contexto": json.dumps(contexto), "borrador": "b2", "toma": toma}).json()
    assert detector.llamadas == antes, "no debe volver a detectar sobre la imagen difuminada"
    pose = json.loads((raiz / "out" / "privado" / "pose.json").read_text(encoding="utf-8"))
    assert pose["vistas"]["costado"]["fuente_pose"] == "pose detectada antes de difuminar el rostro"
    assert datos["resultado"]["reba"]["final"]["reportado"] is not None

    # Una foto subida para esa vista reemplaza la pose guardada por la de la foto nueva, también difuminada.
    cliente.post("/api/casos", data={"contexto": json.dumps(contexto), "reemplazar": "true"},
                 files={"costado": ("c.jpg", _jpg(_ruido(semilla=9)), "image/jpeg")})
    carpeta = raiz / "data" / "casos" / "privado"
    cache = json.loads((carpeta / "costado.pose.json").read_text(encoding="utf-8"))
    assert cache["sha256"] == hashlib.sha256((carpeta / "costado.jpg").read_bytes()).hexdigest()
    assert detector.llamadas == antes + 1, "se detecta una vez, antes de difuminar, y el análisis reutiliza esa pose"


def test_si_no_se_puede_difuminar_no_se_guarda_nada(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "umbrales.yaml").write_text((Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    class _Roto:
        def detect(self, image):
            raise RuntimeError("detector caído")

    cliente = TestClient(crear_app(tmp_path, _Roto()), base_url="http://127.0.0.1:8765")
    respuesta = cliente.post("/api/capturas/b3", files={"costado": ("c.jpg", _jpg(_ruido()), "image/jpeg")})
    assert respuesta.status_code == 503 and "difuminar" in respuesta.json()["detail"]
    assert not (tmp_path / "capturas" / "b3").exists()
