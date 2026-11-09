"""Regresiones de la revisión de seguridad: DNS rebinding, CSRF, cabeceras, imágenes hostiles,
difuminado de fotos subidas y firma de la bitácora."""

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ergoai import privacidad
from ergoai import validacion as val
from ergoai.io_imagenes import MAX_PIXELES, validar_foto
from ergoai.modelos import PoseResult
from ergoai.servidor import crear_app
from test_informe_validacion import CONTEXTO, MEDICIONES
from test_pipeline import _landmarks_sinteticos

LOCAL = "http://127.0.0.1:8765"


class _Backend:
    def detect(self, image):
        return [PoseResult(_landmarks_sinteticos(), [])]


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "umbrales.yaml").write_text((Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


@pytest.fixture
def cliente(raiz: Path) -> TestClient:
    return TestClient(crear_app(raiz, _Backend()), base_url=LOCAL)


def _jpg(semilla: int = 3, ancho: int = 320, alto: int = 400) -> bytes:
    pixeles = np.random.default_rng(semilla).integers(0, 255, (alto, ancho, 3), dtype=np.uint8)
    salida = io.BytesIO()
    Image.fromarray(pixeles).save(salida, format="JPEG", quality=95)
    return salida.getvalue()


def _png_gigante(lado: int) -> bytes:
    salida = io.BytesIO()
    Image.new("L", (lado, lado), 0).save(salida, format="PNG", optimize=True)
    return salida.getvalue()


def _crear(cliente: TestClient, caso_id: str = "seguro", cabeceras: dict | None = None, foto: bytes | None = None, **extra):
    contexto = {**CONTEXTO, "caso_id": caso_id, "orientacion_costado": "derecha", "overrides": MEDICIONES}
    return cliente.post("/api/casos", headers=cabeceras or {}, data={"contexto": json.dumps(contexto), **extra},
                        files={"costado": ("c.jpg", foto or _jpg(), "image/jpeg")})


# --------------------------------------------------------------------------- DNS rebinding
@pytest.mark.parametrize("host", ["evil.example", "evil.example:8765", "127.0.0.1.evil.example", "attacker.test:80"])
def test_rechaza_host_ajeno(cliente: TestClient, host: str) -> None:
    respuesta = cliente.get("/api/casos", headers={"Host": host})
    assert respuesta.status_code == 400 and "Host no permitido" in respuesta.json()["detail"]


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "LOCALHOST"])
def test_acepta_hosts_locales(cliente: TestClient, host: str) -> None:
    assert cliente.get("/api/salud", headers={"Host": host}).status_code == 200


# --------------------------------------------------------------------------- CSRF
def test_rechaza_formularios_de_otro_origen_sin_tocar_el_disco(cliente: TestClient, raiz: Path) -> None:
    respuesta = _crear(cliente, "csrf", {"Origin": "https://evil.example"})
    assert respuesta.status_code == 403
    assert not (raiz / "data" / "casos" / "csrf").exists()
    captura = cliente.post("/api/capturas/b1", headers={"Origin": "null"}, files={"costado": ("c.jpg", _jpg(), "image/jpeg")})
    assert captura.status_code == 403 and not (raiz / "capturas" / "b1").exists()
    entre_sitios = _crear(cliente, "csrf2", {"Sec-Fetch-Site": "cross-site"})
    assert entre_sitios.status_code == 403


def test_acepta_el_mismo_origen_y_clientes_sin_origen(cliente: TestClient) -> None:
    assert _crear(cliente, "mismo", {"Origin": LOCAL, "Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert _crear(cliente, "cli").status_code == 200  # CLI, pruebas: sin Origin
    # Un origen local en otro puerto no es el mismo origen.
    assert _crear(cliente, "otro-puerto", {"Origin": "http://127.0.0.1:9999"}).status_code == 403


def test_las_lecturas_desde_otro_origen_no_se_bloquean_pero_no_traen_cors(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/casos", headers={"Origin": "https://evil.example"})
    assert respuesta.status_code == 200 and "access-control-allow-origin" not in respuesta.headers


# --------------------------------------------------------------------------- Cabeceras
@pytest.mark.parametrize("ruta", ["/api/salud", "/api/casos", "/api/docs"])
def test_cabeceras_de_seguridad(cliente: TestClient, ruta: str) -> None:
    cabeceras = cliente.get(ruta).headers
    assert cabeceras["x-content-type-options"] == "nosniff"
    assert cabeceras["x-frame-options"] == "SAMEORIGIN"
    assert cabeceras["cross-origin-resource-policy"] == "same-origin"
    assert cabeceras["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'self'" in cabeceras["content-security-policy"]


# --------------------------------------------------------------------------- Imágenes hostiles
def test_bomba_de_descompresion_se_rechaza_sin_decodificar(cliente: TestClient, raiz: Path) -> None:
    bomba = _png_gigante(12000)  # 144 MP en ~140 KB
    assert len(bomba) < 300_000
    respuesta = _crear(cliente, "bomba", foto=bomba)
    assert respuesta.status_code == 400 and "MP" in respuesta.json()["detail"]
    assert not (raiz / "data" / "casos" / "bomba").exists()
    captura = cliente.post("/api/capturas/b2", files={"costado": ("c.png", bomba, "image/png")})
    assert captura.status_code == 400


def test_archivo_que_no_es_imagen_no_se_guarda_ni_rompe_el_caso(cliente: TestClient, raiz: Path) -> None:
    assert _crear(cliente, "intacto").status_code == 200
    antes = sorted(p.name for p in (raiz / "data" / "casos" / "intacto").iterdir())
    html = b"<html><script>alert(1)</script></html>"
    respuesta = _crear(cliente, "intacto", foto=html, reemplazar="true")
    assert respuesta.status_code == 400 and "no es una imagen" in respuesta.json()["detail"]
    assert sorted(p.name for p in (raiz / "data" / "casos" / "intacto").iterdir()) == antes


def test_validar_foto_respeta_el_tope_y_el_formato() -> None:
    assert validar_foto(_jpg(), "La foto", 10_000_000) == ".jpg"
    with pytest.raises(ValueError, match="supera"):
        validar_foto(_jpg(), "La foto", 100)
    salida = io.BytesIO()
    Image.new("RGB", (8, 8)).save(salida, format="GIF")
    with pytest.raises(ValueError, match="JPG o PNG"):
        validar_foto(salida.getvalue(), "La foto", 10_000_000)
    assert MAX_PIXELES == 50_000_000


# --------------------------------------------------------------------------- Privacidad de fotos subidas
def test_la_foto_subida_se_guarda_difuminada_con_su_pose(cliente: TestClient, raiz: Path) -> None:
    original = _jpg(semilla=11)
    assert _crear(cliente, "subida", foto=original).status_code == 200
    carpeta = raiz / "data" / "casos" / "subida"
    assert sorted(p.name for p in carpeta.glob("costado*")) == ["costado.jpg", "costado.pose.json"]
    guardada = np.asarray(Image.open(carpeta / "costado.jpg").convert("RGB"), dtype=np.int16)
    decodificada = np.asarray(Image.open(io.BytesIO(original)).convert("RGB"), dtype=np.int16)
    [(x0, y0, x1, y1)] = privacidad.cajas_desde_pose([PoseResult(_landmarks_sinteticos(), [])], 320, 400)
    assert np.abs(guardada[y0:y1, x0:x1] - decodificada[y0:y1, x0:x1]).mean() > 40, "la cabeza debe quedar difuminada"
    cache = json.loads((carpeta / "costado.pose.json").read_text(encoding="utf-8"))
    assert cache["sha256"] == hashlib.sha256((carpeta / "costado.jpg").read_bytes()).hexdigest()
    servida = cliente.get("/api/casos/subida/fotos/costado")
    assert servida.status_code == 200 and servida.content == (carpeta / "costado.jpg").read_bytes()


def test_si_no_se_puede_difuminar_la_foto_subida_no_se_guarda(raiz: Path) -> None:
    class _Roto:
        def detect(self, image):
            raise RuntimeError("detector caído")

    cliente = TestClient(crear_app(raiz, _Roto()), base_url=LOCAL)
    respuesta = _crear(cliente, "sin-detector")
    assert respuesta.status_code == 503 and "difuminar" in respuesta.json()["detail"]
    assert not any((raiz / "data" / "casos" / "sin-detector").glob("costado*"))


# --------------------------------------------------------------------------- Bitácora firmada
def test_bitacora_firmada_detecta_cadena_recalculada(tmp_path: Path) -> None:
    val.usar_clave(tmp_path)
    assert (tmp_path / ".clave_bitacora").stat().st_mode & 0o077 == 0, "la clave solo la lee el usuario"
    validacion: dict = {"bitacora": []}
    val.registrar(validacion, "Ing. Real", "rechazar", "R-1", {}, "no aplica")
    val.registrar(validacion, "Ing. Real", "aprobar", "R-2")
    assert val.estado_bitacora(validacion) == "firmada"

    # Falsificación: cambiar quién decidió y recalcular toda la cadena sin la clave.
    validacion["bitacora"][0]["usuario"] = "Otra persona"
    previo = "0" * 64
    for entrada in validacion["bitacora"]:
        entrada["hash_previo"] = previo
        contenido = json.dumps({k: v for k, v in entrada.items() if k not in ("hash", "firma")}, ensure_ascii=False, sort_keys=True)
        entrada["hash"] = previo = hashlib.sha256((previo + contenido).encode("utf-8")).hexdigest()
    assert val.estado_bitacora(validacion) == "alterada"
    assert not val.verificar_bitacora(validacion)

    # Quitar las firmas no la vuelve «firmada»: queda como no comprobable.
    for entrada in validacion["bitacora"]:
        entrada.pop("firma")
    assert val.estado_bitacora(validacion) == "sin_firma"


def test_bitacora_de_otra_instalacion_no_se_marca_como_alterada(tmp_path: Path) -> None:
    val.usar_clave(tmp_path / "equipo-a")
    validacion: dict = {"bitacora": []}
    val.registrar(validacion, "Ing. A", "aprobar", "R-1")
    assert val.estado_bitacora(validacion) == "firmada"
    val.usar_clave(tmp_path / "equipo-b")
    assert val.estado_bitacora(validacion) == "sin_firma"
    val.usar_clave(tmp_path / "equipo-a")
    assert val.estado_bitacora(validacion) == "firmada"


def test_el_tiempo_del_agente_incluye_la_deteccion_al_difuminar(cliente: TestClient) -> None:
    datos = _crear(cliente, "tiempos").json()
    tiempos = datos["resultado"]["tiempos_s"]
    assert "deteccion_y_difuminado" in tiempos
    assert tiempos["analisis_total"] >= tiempos["deteccion_y_difuminado"]
