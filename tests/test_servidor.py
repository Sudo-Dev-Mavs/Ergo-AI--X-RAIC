import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ergoai.modelos import PoseResult
from ergoai.servidor import crear_app
from test_informe_validacion import CONTEXTO, MEDICIONES
from test_pipeline import _landmarks_sinteticos


class _Backend:
    def detect(self, image):
        return [PoseResult(_landmarks_sinteticos(), [])]


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "umbrales.yaml").write_text((Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return TestClient(crear_app(tmp_path, _Backend()))


def _png() -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (300, 400)).save(salida, format="PNG")
    return salida.getvalue()


def _crear(cliente: TestClient, caso_id: str = "caso01", **extra) -> dict:
    contexto = {**CONTEXTO, "caso_id": caso_id, "orientacion_costado": "derecha", "overrides": MEDICIONES}
    respuesta = cliente.post("/api/casos", data={"contexto": json.dumps(contexto), **extra},
                             files={"costado": ("c.png", _png(), "image/png"), "frente": ("f.png", _png(), "image/png")})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_crear_listar_y_servir_archivos(cliente: TestClient) -> None:
    datos = _crear(cliente)
    assert datos["resultado"]["reba"]["nivel_accion"] >= 3  # sin vista aérea la torsión queda pendiente
    assert datos["residual"]["reduccion_puntos"] > 0
    assert "costado" in datos["imagenes"] and "costado" in datos["fotos"]
    assert all("clave_override" in angulo for angulo in datos["resultado"]["angulos"])
    casos = cliente.get("/api/casos").json()
    assert casos[0]["caso_id"] == "caso01" and casos[0]["por_validar"] > 0
    assert cliente.get("/api/casos/caso01/archivos/informe.html").status_code == 200
    assert cliente.get("/api/casos/caso01/archivos/costado_angulos.png").headers["content-type"] == "image/png"
    assert cliente.get("/api/casos/caso01/fotos/costado").status_code == 200
    assert cliente.get("/api/casos/caso01/fotos/costado").headers["content-type"] == "image/jpeg"
    assert datos["resultado"]["contexto"]["privacidad"]["fotos_subidas"]["costado"]["metodo"] == "pose"
    assert cliente.get("/api/casos/caso01/archivos/resultado.json").status_code == 404
    assert cliente.get("/api/casos/caso01/archivos/..%2F..%2Fconfig%2Fumbrales.yaml").status_code == 404


def test_rechaza_ids_invalidos_duplicados_y_sin_fotos(cliente: TestClient) -> None:
    _crear(cliente)
    duplicado = cliente.post("/api/casos", data={"contexto": json.dumps({**CONTEXTO, "caso_id": "caso01"})}, files={"costado": ("c.png", _png(), "image/png")})
    assert duplicado.status_code == 409
    assert cliente.post("/api/casos", data={"contexto": json.dumps({"caso_id": "../x"})}).status_code == 400
    assert cliente.post("/api/casos", data={"contexto": json.dumps({"caso_id": "vacio"})}).status_code == 400
    assert cliente.get("/api/casos/no-existe").status_code == 404
    _crear(cliente, reemplazar="true")


def test_validacion_y_correccion_quedan_en_bitacora(cliente: TestClient) -> None:
    datos = _crear(cliente)
    rec_id = datos["validacion"]["recomendaciones"][0]["id"]
    sin_usuario = cliente.post("/api/casos/caso01/validacion", json={"usuario": "", "accion": "aprobar", "rec_id": rec_id})
    assert sin_usuario.status_code == 422
    rechazo = cliente.post("/api/casos/caso01/validacion", json={"usuario": "Ing. Pérez", "accion": "rechazar", "rec_id": rec_id})
    assert rechazo.status_code == 400 and "motivo" in rechazo.json()["detail"]
    aprobado = cliente.post("/api/casos/caso01/validacion", json={"usuario": "Ing. Pérez", "accion": "aprobar", "rec_id": rec_id}).json()
    assert next(rec for rec in aprobado["validacion"]["recomendaciones"] if rec["id"] == rec_id)["estado"] == "aprobada"
    assert aprobado["bitacora_integra"]

    corregido = cliente.post("/api/casos/caso01/correcciones", json={"usuario": "Ing. Pérez", "overrides": {"tronco_flexion": 5.0}, "comentario": "medido en piso"}).json()
    ultima = corregido["validacion"]["bitacora"][-1]
    assert ultima["accion"] == "corregir_angulo" and ultima["cambios"]["tronco_flexion"]["despues"] == 5.0
    assert corregido["resultado"]["mediciones_reba"]["tronco_flexion"] == 5.0
    assert "R-TRONCO-ING" not in {rec["id"] for rec in corregido["validacion"]["recomendaciones"] if rec["estado"] != "obsoleta"}
    assert cliente.post("/api/casos/caso01/correcciones", json={"usuario": "x", "overrides": {"inventada": 1}}).status_code == 400


def test_sirve_la_interfaz_y_no_tapa_rutas_de_api(cliente: TestClient) -> None:
    raiz = cliente.get("/")
    assert raiz.status_code in (200, 503)  # 503 solo si la interfaz no está compilada
    if raiz.status_code == 200:
        assert "<div id=\"root\">" in raiz.text
        assert cliente.get("/caso/x").status_code == 200  # rutas del SPA
    assert cliente.get("/api/no-existe").status_code == 404
