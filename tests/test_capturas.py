import io
import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from ergoai import capturas
from test_informe_validacion import CONTEXTO, MEDICIONES
from test_servidor import cliente  # noqa: F401  (fixture con detector sintético)


def _jpg(color=(120, 130, 140)) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(salida, format="JPEG")
    return salida.getvalue()


def _tomar(cliente: TestClient, borrador: str = "borrador-1", vistas=("costado", "frente")):
    return cliente.post(f"/api/capturas/{borrador}", files={v: (f"{v}.jpg", _jpg(), "image/jpeg") for v in vistas})


def test_guardar_listar_servir_y_descartar_tomas(cliente: TestClient) -> None:  # noqa: F811
    primera = _tomar(cliente).json()["toma"]
    segunda = _tomar(cliente, vistas=("aerea",)).json()
    assert primera["vistas"] == ["costado", "frente"]
    assert [t["id"] for t in segunda["tomas"]] == [segunda["toma"]["id"], primera["id"]]  # más reciente primero
    listado = cliente.get("/api/capturas/borrador-1").json()
    assert listado["max_tomas"] == capturas.MAX_TOMAS and len(listado["tomas"]) == 2
    imagen = cliente.get(f"/api/capturas/borrador-1/{primera['id']}/costado")
    assert imagen.status_code == 200 and imagen.headers["content-type"] == "image/jpeg"
    assert cliente.get(f"/api/capturas/borrador-1/{primera['id']}/aerea").status_code == 404
    assert cliente.get("/api/capturas/borrador-1/../../config/costado").status_code == 404
    assert cliente.delete("/api/capturas/borrador-1").json() == {"tomas": []}
    assert cliente.get("/api/capturas/borrador-1").json()["tomas"] == []


def test_rechaza_imagenes_invalidas_e_ids_peligrosos(cliente: TestClient) -> None:  # noqa: F811
    falsa = cliente.post("/api/capturas/b1", files={"costado": ("c.jpg", b"no es imagen", "image/jpeg")})
    assert falsa.status_code == 400 and "no es una imagen" in falsa.json()["detail"]
    assert cliente.post("/api/capturas/b1").status_code == 400
    assert cliente.post("/api/capturas/..%2Fx", files={"costado": ("c.jpg", _jpg(), "image/jpeg")}).status_code in (400, 404, 405)
    assert cliente.post("/api/capturas/-oculto", files={"costado": ("c.jpg", _jpg(), "image/jpeg")}).status_code == 400


def test_tope_de_tomas_y_purga_por_antiguedad(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(capturas, "MAX_TOMAS", 3)
    for _ in range(5):
        capturas.guardar_toma(tmp_path, "b", {"costado": _jpg()})
    assert len(capturas.listar_tomas(tmp_path, "b")) == 3
    viejo = time.time() - 30 * 3600
    for ruta in [tmp_path / "capturas" / "b", *(tmp_path / "capturas" / "b").iterdir()]:
        os.utime(ruta, (viejo, viejo))
    capturas.guardar_toma(tmp_path, "reciente", {"frente": _jpg()})
    assert capturas.purgar_vencidas(tmp_path) == 1
    assert not (tmp_path / "capturas" / "b").exists() and (tmp_path / "capturas" / "reciente").exists()


def test_analizar_con_una_toma_copia_sus_vistas_y_lo_registra(cliente: TestClient) -> None:  # noqa: F811
    toma = _tomar(cliente, "borrador-2", ("costado", "frente", "aerea")).json()["toma"]["id"]
    contexto = {**CONTEXTO, "caso_id": "desde-camara", "orientacion_costado": "derecha", "overrides": MEDICIONES}
    respuesta = cliente.post("/api/casos", data={"contexto": json.dumps(contexto), "borrador": "borrador-2", "toma": toma})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert set(datos["fotos"]) == {"costado", "frente", "aerea"}
    assert datos["resultado"]["contexto"]["capturas"] == {"borrador": "borrador-2", "toma": toma, "vistas": ["aerea", "costado", "frente"]}

    # Reanálisis con una toma de solo costado: las vistas viejas no se mezclan con la nueva.
    otra = _tomar(cliente, "borrador-2", ("costado",)).json()["toma"]["id"]
    datos = cliente.post("/api/casos", data={"contexto": json.dumps(contexto), "borrador": "borrador-2", "toma": otra, "reemplazar": "true"}).json()
    assert datos["fotos"] == ["costado"]

    vencida = cliente.post("/api/casos", data={"contexto": json.dumps({**contexto, "caso_id": "otro"}), "borrador": "borrador-2", "toma": "20200101-000000-000"})
    assert vencida.status_code == 400 and "ya no existe" in vencida.json()["detail"]


def test_solo_usa_las_vistas_asignadas_a_camara(cliente: TestClient) -> None:  # noqa: F811
    toma = _tomar(cliente, "borrador-3", ("costado", "frente")).json()["toma"]["id"]
    contexto = {**CONTEXTO, "caso_id": "mixto", "orientacion_costado": "derecha", "overrides": MEDICIONES}
    datos = cliente.post("/api/casos", data={"contexto": json.dumps(contexto), "borrador": "borrador-3", "toma": toma, "vistas_toma": "costado"},
                         files={"aerea": ("a.jpg", _jpg(), "image/jpeg")}).json()
    assert datos["fotos"] == ["costado", "aerea"]
    assert datos["resultado"]["contexto"]["capturas"]["vistas"] == ["costado"]
