"""Servidor local (solo 127.0.0.1) que expone el pipeline de ErgoAI a la interfaz web.

Las fotografías y resultados nunca salen del equipo: el servidor escucha únicamente en
la interfaz de loopback y sirve la interfaz compilada desde ``src/ergoai/web/dist``.

Escuchar en loopback no basta: cualquier página abierta en el navegador puede enviar peticiones a
127.0.0.1. Por eso el servidor solo acepta el Host local (contra DNS rebinding), rechaza las
peticiones que cambian datos si vienen de otro origen (contra CSRF) y envía cabeceras que impiden
incrustar la app o sus imágenes en otros sitios.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from . import capturas, privacidad
from . import validacion as val
from .cli import EXTENSIONES_IMAGEN, VISTAS, elegir_persona, ejecutar_evaluar, ejecutar_validacion
from .config import cargar_configuracion
from .informe import cargar_estado, generar_informe
from .io_imagenes import cargar_imagen, validar_foto
from .modelos import VistaPose
from .pose import PoseBackend
from .pose_aislada import DetectorAislado
from .proponer_contexto import clasificar_y_asignar, proponer_desde_vistas
from .privacidad import personas_desde_dict

PATRON_CASO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
ARCHIVOS_SALIDA = re.compile(r"^((frente|costado|aerea)_(angulos|pose)\.png|informe\.html|acciones_00014\.csv)$")
WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
MAX_FOTO_BYTES = 25 * 1024 * 1024
HOSTS_LOCALES = frozenset({"127.0.0.1", "localhost", "[::1]"})
METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
CABECERAS_SEGURIDAD = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",  # el informe se previsualiza en un iframe del mismo origen
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",  # otras páginas no pueden incrustar fotos ni informes
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=(), usb=(), payment=()",
}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "media-src 'self' blob: mediastream:; font-src 'self' data:; connect-src 'self'; object-src 'none'; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'self'")
CSP_DOCS = "frame-ancestors 'self'; object-src 'none'; base-uri 'self'"  # Swagger UI carga recursos de su CDN


def _host_sin_puerto(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host[: host.find("]") + 1] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def _rechazo_origen(request: Request, host: str) -> str | None:
    """Motivo para rechazar una petición que cambia datos desde otro origen; None si es del mismo."""

    if request.method in METODOS_SEGUROS:
        return None
    origen = request.headers.get("origin")
    if origen is not None:
        partes = urlsplit(origen)
        if origen == "null" or partes.scheme not in ("http", "https") or partes.netloc.lower() != host.lower():
            return f"Origen no permitido: {origen}"
        return None
    sitio = request.headers.get("sec-fetch-site")
    if sitio is not None and sitio not in ("same-origin", "none"):
        return f"Petición entre sitios rechazada ({sitio})"
    return None  # sin Origin ni Sec-Fetch-Site: clientes locales como la CLI o las pruebas


class SolicitudValidacion(BaseModel):
    usuario: str = Field(min_length=1)
    accion: str
    rec_id: str | None = None
    valores: dict[str, str] = Field(default_factory=dict)
    comentario: str = ""


class SolicitudCorreccion(BaseModel):
    usuario: str = Field(min_length=1)
    overrides: dict[str, float | None]
    comentario: str = ""


class SolicitudEliminarCaso(BaseModel):
    usuario: str = Field(min_length=1)
    confirmacion: str = Field(min_length=1, description="Debe coincidir con el caso_id.")


def _clave_override(angulo: dict[str, Any]) -> str:
    medida, lado = angulo["medida"], angulo.get("lado")
    return f"{medida}_{lado}" if lado and medida != "cuello_flexion" else medida


def crear_app(raiz: Path, backend: PoseBackend | None = None) -> FastAPI:
    """Construye la aplicación; ``backend`` permite inyectar un detector falso en pruebas."""

    app = FastAPI(title="ErgoAI", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    candado = threading.Lock()  # MediaPipe y la escritura de archivos no deben correr en paralelo
    candado_capturas = threading.Lock()
    capturas.purgar_vencidas(raiz)
    val.usar_clave(raiz)  # firma HMAC de la bitácora con la clave de esta instalación

    @app.middleware("http")
    async def proteger_origen(request: Request, call_next):
        host = request.headers.get("host", "")
        if _host_sin_puerto(host) not in HOSTS_LOCALES:
            return JSONResponse({"detail": "Host no permitido: ErgoAI solo atiende a 127.0.0.1 o localhost."}, status_code=400)
        motivo = _rechazo_origen(request, host)
        if motivo:
            return JSONResponse({"detail": motivo}, status_code=403)
        respuesta = await call_next(request)
        for nombre, valor in CABECERAS_SEGURIDAD.items():
            respuesta.headers.setdefault(nombre, valor)
        respuesta.headers.setdefault("Content-Security-Policy", CSP_DOCS if request.url.path.startswith("/api/docs") else CSP)
        return respuesta

    def config_reba():
        return cargar_configuracion(raiz / "config" / "umbrales.yaml").reba

    def validar_id(caso_id: str) -> str:
        if not PATRON_CASO.match(caso_id) or caso_id in (".", ".."):
            raise HTTPException(400, "El identificador solo admite letras, números, punto, guion y guion bajo (máx. 64).")
        return caso_id

    def carpeta_salida(caso_id: str) -> Path:
        carpeta = raiz / "out" / validar_id(caso_id)
        if not (carpeta / "resultado.json").is_file():
            raise HTTPException(404, f"No existe una evaluación para el caso «{caso_id}».")
        return carpeta

    detector_local: list[PoseBackend] = []

    def detector_pose() -> PoseBackend:
        """El detector inyectado o, si no hay, MediaPipe en este proceso."""

        if backend is not None:
            return backend
        if not detector_local:
            from .pose import MediaPipeBackend

            detector_local.append(MediaPipeBackend(cargar_configuracion(raiz / "config" / "umbrales.yaml").pose, raiz))
        return detector_local[0]

    def carpeta_entrada(caso_id: str) -> Path:
        return raiz / "data" / "casos" / validar_id(caso_id)

    def estado(caso_id: str) -> dict[str, Any]:
        carpeta = carpeta_salida(caso_id)
        datos = cargar_estado(carpeta, config_reba())
        resultado, validacion = datos["resultado"], datos["validacion"]
        for angulo in resultado.get("angulos", []):
            angulo["clave_override"] = _clave_override(angulo)
        resultado.pop("vectores", None)
        entrada = carpeta_entrada(caso_id)
        return {
            **datos,
            "bloqueos": [] if validacion.get("estado_informe") == "aprobado" else val.bloqueos_aprobacion(
                validacion,
                resultado.get("reba", {}).get("nivel_accion"),
                (resultado.get("reba", {}).get("final") or {}).get("reportado"),
            ),
            "bitacora_integra": val.verificar_bitacora(validacion),
            "bitacora_estado": val.estado_bitacora(validacion),
            "imagenes": [vista for vista in VISTAS if (carpeta / f"{vista}_angulos.png").is_file()],
            "fotos": [vista for vista in VISTAS if any((entrada / f"{vista}{ext}").is_file() for ext in EXTENSIONES_IMAGEN)],
        }

    @app.get("/api/salud")
    def salud() -> dict[str, Any]:
        return {"ok": True, "version": __version__}

    @app.get("/api/casos")
    def listar_casos() -> list[dict[str, Any]]:
        filas = []
        for ruta in sorted((raiz / "out").glob("*/resultado.json")):
            try:
                datos = cargar_estado(ruta.parent, config_reba())
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            resultado, validacion, residual = datos["resultado"], datos["validacion"], datos["residual"]
            reba, contexto = resultado.get("reba", {}), resultado.get("contexto", {})
            vigentes = [rec for rec in validacion["recomendaciones"] if rec.get("estado") != "obsoleta"]
            filas.append({
                "caso_id": resultado.get("caso_id", ruta.parent.name),
                "tipo_tarea": contexto.get("tipo_tarea") or "otro", "carga_kg": contexto.get("carga_kg"),
                "realizado_por": contexto.get("realizado_por"), "fecha_analisis": resultado.get("fecha_analisis"),
                "reba": reba.get("final", {}).get("reportado"), "nivel_riesgo": reba.get("nivel_riesgo"), "nivel_accion": reba.get("nivel_accion"),
                "residual": residual["residual"]["reba"], "nivel_residual": residual["residual"]["nivel_riesgo"],
                "reba_rango": reba.get("final", {}).get("rango"),
                "residual_rango": residual["residual"].get("rango"),
                "origen_residual": residual.get("origen_residual", "agente"),
                "estado_validacion": val.estado_validacion_caso(validacion),
                "por_validar": sum(1 for rec in vigentes if rec.get("estado") == "propuesta"),
                "recomendaciones": len(vigentes), "estado_informe": validacion.get("estado_informe", "borrador"),
                "pendientes_manuales": len(resultado.get("pendientes_manuales", [])),
                "miniatura": next((vista for vista in VISTAS if (ruta.parent / f"{vista}_angulos.png").is_file()), None),
            })
        return sorted(filas, key=lambda fila: (-(fila["nivel_accion"] if fila["nivel_accion"] is not None else -1), -fila["por_validar"], fila["caso_id"]))

    @app.get("/api/casos/{caso_id}")
    def obtener_caso(caso_id: str) -> dict[str, Any]:
        return estado(caso_id)

    @app.post("/api/casos/{caso_id}/eliminar")
    def eliminar_caso(caso_id: str, solicitud: SolicitudEliminarCaso) -> dict[str, Any]:
        """Borra del equipo las carpetas de entrada y salida del caso (fotos, análisis, informe)."""

        caso = validar_id(caso_id)
        if solicitud.confirmacion.strip() != caso:
            raise HTTPException(400, f"Para eliminar escribe exactamente el identificador «{caso}».")
        entrada = carpeta_entrada(caso)
        salida = raiz / "out" / caso
        if not entrada.is_dir() and not (salida / "resultado.json").is_file() and not salida.is_dir():
            raise HTTPException(404, f"No existe el caso «{caso}».")
        with candado:
            if salida.is_dir():
                shutil.rmtree(salida)
            if entrada.is_dir():
                shutil.rmtree(entrada)
        return {"ok": True, "caso_id": caso, "eliminado_por": solicitud.usuario.strip()}

    @app.post("/api/casos")
    def crear_caso(
        contexto: str = Form(...), reemplazar: bool = Form(False),
        frente: UploadFile | None = File(None), costado: UploadFile | None = File(None), aerea: UploadFile | None = File(None),
        borrador: str | None = Form(None), toma: str | None = Form(None), vistas_toma: str | None = Form(None),
    ) -> dict[str, Any]:
        """Crea o reanaliza un caso con fotos subidas y/o las vistas de una toma de cámara."""

        try:
            datos = json.loads(contexto)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "El contexto no es JSON válido.") from exc
        if not isinstance(datos, dict):
            raise HTTPException(400, "El contexto debe ser un objeto.")
        caso_id = validar_id(str(datos.get("caso_id", "")).strip())
        datos["caso_id"] = caso_id
        fotos = {nombre: archivo for nombre, archivo in (("frente", frente), ("costado", costado), ("aerea", aerea)) if archivo is not None and archivo.filename}
        desde_toma: dict[str, Path] = {}
        if toma:
            if not borrador:
                raise HTTPException(400, "Falta el borrador de la toma.")
            validar_id(borrador)
            permitidas = set(vistas_toma.split(",")) if vistas_toma else set(VISTAS)
            desde_toma = {vista: ruta for vista in VISTAS
                          if vista in permitidas and vista not in fotos and (ruta := capturas.archivo_vista(raiz, borrador, toma, vista))}
            if not desde_toma and not fotos:
                raise HTTPException(400, "La toma elegida ya no existe: se descartó o venció. Elige otra o captura de nuevo.")
            datos["capturas"] = {"borrador": borrador, "toma": toma, "vistas": sorted(desde_toma)}
        destino = carpeta_entrada(caso_id)
        existentes = [vista for vista in VISTAS if any((destino / f"{vista}{ext}").is_file() for ext in EXTENSIONES_IMAGEN)]
        if not fotos and not desde_toma and not existentes:
            raise HTTPException(400, "Agrega al menos una fotografía: frente, costado o aérea.")
        if (raiz / "out" / caso_id / "resultado.json").is_file() and not reemplazar:
            raise HTTPException(409, f"El caso «{caso_id}» ya existe. Usa otro identificador o confirma que quieres reemplazarlo.")
        with candado:
            # Cada foto subida se valida y se difumina antes de modificar el caso: si algo falla, el caso queda intacto.
            protegidas: dict[str, privacidad.ImagenProtegida] = {}
            inicio_difuminado = time.perf_counter()
            for vista, archivo in fotos.items():
                contenido = archivo.file.read(MAX_FOTO_BYTES + 1)
                detector = detector_pose()
                try:
                    validar_foto(contenido, f"La foto {vista}", MAX_FOTO_BYTES)
                    protegidas[vista] = privacidad.proteger(contenido, detector.detect, getattr(detector, "detectar_rostros", None))
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                except RuntimeError as exc:  # sin detector no se puede difuminar: no se guarda nada
                    raise HTTPException(503, f"No se guardó la foto {vista} porque no se pudo difuminar el rostro. {exc}") from exc
            segundos_difuminado = time.perf_counter() - inicio_difuminado if protegidas else 0.0
            destino.mkdir(parents=True, exist_ok=True)
            anterior = destino / "contexto.json"
            if anterior.is_file() and "overrides" not in datos:
                try:
                    datos["overrides"] = json.loads(anterior.read_text(encoding="utf-8")).get("overrides", {})
                except (json.JSONDecodeError, AttributeError):
                    datos["overrides"] = {}
            nuevas = set(fotos) | set(desde_toma)
            if nuevas:  # un juego nuevo de vistas reemplaza por completo al anterior
                for vista in VISTAS:
                    if vista not in nuevas:
                        for ext in EXTENSIONES_IMAGEN:
                            (destino / f"{vista}{ext}").unlink(missing_ok=True)
                        (destino / f"{vista}.pose.json").unlink(missing_ok=True)
            for vista, ruta in desde_toma.items():
                for ext in EXTENSIONES_IMAGEN:
                    (destino / f"{vista}{ext}").unlink(missing_ok=True)
                shutil.copy2(ruta, destino / f"{vista}{ruta.suffix}")
                pose = capturas.archivo_pose(raiz, str(borrador), str(toma), vista)
                if pose is not None:  # pose detectada antes de difuminar el rostro
                    shutil.copy2(pose, destino / f"{vista}.pose.json")
                else:
                    (destino / f"{vista}.pose.json").unlink(missing_ok=True)
            for vista, protegida in protegidas.items():
                for ext in EXTENSIONES_IMAGEN:
                    (destino / f"{vista}{ext}").unlink(missing_ok=True)
                (destino / f"{vista}.jpg").write_bytes(protegida.jpeg)  # solo la versión difuminada llega al disco
                (destino / f"{vista}.pose.json").write_text(json.dumps(protegida.cache(), ensure_ascii=False), encoding="utf-8")
            anterior.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                ejecutar_evaluar(destino, raiz, backend, segundos_previos=segundos_difuminado)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except RuntimeError as exc:  # el detector aislado se cerró: el servidor sigue disponible
                raise HTTPException(503, str(exc)) from exc
        return estado(caso_id)

    @app.post("/api/proponer-contexto")
    def proponer_contexto(
        carga_kg: str | None = Form(None),
        frente: UploadFile | None = File(None), costado: UploadFile | None = File(None), aerea: UploadFile | None = File(None),
        borrador: str | None = Form(None), toma: str | None = Form(None), vistas_toma: str | None = Form(None),
    ) -> dict[str, Any]:
        """Sugiere postura y ajustes REBA a partir de las fotos (sin crear el caso). Editable."""

        fotos = {nombre: archivo for nombre, archivo in (("frente", frente), ("costado", costado), ("aerea", aerea)) if archivo is not None and archivo.filename}
        desde_toma: dict[str, Path] = {}
        if toma:
            if not borrador:
                raise HTTPException(400, "Falta el borrador de la toma.")
            validar_id(borrador)
            permitidas = set(vistas_toma.split(",")) if vistas_toma else set(VISTAS)
            desde_toma = {vista: ruta for vista in VISTAS
                          if vista in permitidas and vista not in fotos and (ruta := capturas.archivo_vista(raiz, borrador, toma, vista))}
        if not fotos and not desde_toma:
            raise HTTPException(400, "Agrega al menos una fotografía para proponer el contexto.")

        parcial: dict[str, Any] = {}
        if carga_kg is not None and str(carga_kg).strip() != "":
            try:
                parcial["carga_kg"] = float(str(carga_kg).replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "carga_kg debe ser un número.") from exc

        configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
        vistas: dict[str, VistaPose] = {}
        with candado:
            detector = detector_pose()
            for vista, archivo in fotos.items():
                contenido = archivo.file.read(MAX_FOTO_BYTES + 1)
                try:
                    validar_foto(contenido, f"La foto {vista}", MAX_FOTO_BYTES)
                    protegida = privacidad.proteger(contenido, detector.detect, getattr(detector, "detectar_rostros", None))
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                except RuntimeError as exc:
                    raise HTTPException(503, str(exc)) from exc
                indice, persona = elegir_persona(protegida.personas, configuracion.pose.vis_min, None)
                if persona is None:
                    vistas[vista] = VistaPose(vista, protegida.ancho, protegida.alto, False, len(protegida.personas), motivo="sin detección de pose")
                else:
                    vistas[vista] = VistaPose(
                        vista, protegida.ancho, protegida.alto, True, len(protegida.personas),
                        persona_indice=indice, landmarks=persona.landmarks, world_landmarks=persona.world_landmarks,
                    )
            for vista, ruta in desde_toma.items():
                imagen = cargar_imagen(ruta)
                personas = None
                pose = capturas.archivo_pose(raiz, str(borrador), str(toma), vista)
                if pose is not None:
                    try:
                        datos = json.loads(pose.read_text(encoding="utf-8"))
                        personas = personas_desde_dict(datos.get("personas", []))
                    except (OSError, ValueError, KeyError, TypeError):
                        personas = None
                if personas is None:
                    try:
                        personas = detector.detect(imagen.pixeles)
                    except RuntimeError as exc:
                        raise HTTPException(503, str(exc)) from exc
                indice, persona = elegir_persona(personas, configuracion.pose.vis_min, None)
                if persona is None:
                    vistas[vista] = VistaPose(vista, imagen.ancho, imagen.alto, False, len(personas), motivo="sin detección de pose")
                else:
                    vistas[vista] = VistaPose(
                        vista, imagen.ancho, imagen.alto, True, len(personas),
                        persona_indice=indice, landmarks=persona.landmarks, world_landmarks=persona.world_landmarks,
                    )
            return proponer_desde_vistas(vistas, configuracion, parcial)

    @app.post("/api/clasificar-vistas")
    def clasificar_vistas_endpoint(
        frente: UploadFile | None = File(None), costado: UploadFile | None = File(None), aerea: UploadFile | None = File(None),
        imagen_0: UploadFile | None = File(None), imagen_1: UploadFile | None = File(None), imagen_2: UploadFile | None = File(None),
        borrador: str | None = Form(None), toma: str | None = Form(None), vistas_toma: str | None = Form(None),
        aplicar_toma: str | None = Form(None),
    ) -> dict[str, Any]:
        """Clasifica fotos/capturas y las coloca en costado / frente / aérea (pose + nombre)."""

        fotos = {
            clave: archivo
            for clave, archivo in (
                ("costado", costado), ("frente", frente), ("aerea", aerea),
                ("imagen_0", imagen_0), ("imagen_1", imagen_1), ("imagen_2", imagen_2),
            )
            if archivo is not None and archivo.filename
        }
        desde_toma: dict[str, Path] = {}
        if toma:
            if not borrador:
                raise HTTPException(400, "Falta el borrador de la toma.")
            validar_id(borrador)
            permitidas = set(vistas_toma.split(",")) if vistas_toma else set(VISTAS)
            desde_toma = {
                vista: ruta for vista in VISTAS
                if vista in permitidas and vista not in fotos and (ruta := capturas.archivo_vista(raiz, borrador, toma, vista))
            }
        if not fotos and not desde_toma:
            raise HTTPException(400, "Agrega al menos una fotografía o captura para clasificar.")

        configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
        candidatas: list[tuple[str, VistaPose, str]] = []
        with candado:
            detector = detector_pose()
            for cid, archivo in fotos.items():
                contenido = archivo.file.read(MAX_FOTO_BYTES + 1)
                try:
                    validar_foto(contenido, f"La foto {cid}", MAX_FOTO_BYTES)
                    protegida = privacidad.proteger(contenido, detector.detect, getattr(detector, "detectar_rostros", None))
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                except RuntimeError as exc:
                    raise HTTPException(503, str(exc)) from exc
                indice, persona = elegir_persona(protegida.personas, configuracion.pose.vis_min, None)
                if persona is None:
                    pose = VistaPose(cid, protegida.ancho, protegida.alto, False, len(protegida.personas), motivo="sin detección")
                else:
                    pose = VistaPose(
                        cid, protegida.ancho, protegida.alto, True, len(protegida.personas),
                        persona_indice=indice, landmarks=persona.landmarks, world_landmarks=persona.world_landmarks,
                    )
                candidatas.append((cid, pose, archivo.filename or cid))

            for vista, ruta in desde_toma.items():
                imagen = cargar_imagen(ruta)
                personas = None
                cache = capturas.archivo_pose(raiz, str(borrador), str(toma), vista)
                if cache is not None:
                    try:
                        datos = json.loads(cache.read_text(encoding="utf-8"))
                        personas = personas_desde_dict(datos.get("personas", []))
                    except (OSError, ValueError, KeyError, TypeError):
                        personas = None
                if personas is None:
                    try:
                        personas = detector.detect(imagen.pixeles)
                    except RuntimeError as exc:
                        raise HTTPException(503, str(exc)) from exc
                indice, persona = elegir_persona(personas, configuracion.pose.vis_min, None)
                if persona is None:
                    pose = VistaPose(vista, imagen.ancho, imagen.alto, False, len(personas), motivo="sin detección")
                else:
                    pose = VistaPose(
                        vista, imagen.ancho, imagen.alto, True, len(personas),
                        persona_indice=indice, landmarks=persona.landmarks, world_landmarks=persona.world_landmarks,
                    )
                candidatas.append((vista, pose, ruta.name))

            resultado = clasificar_y_asignar(candidatas)
            if desde_toma and borrador and toma and str(aplicar_toma or "").strip().lower() in {"1", "true", "si", "sí", "yes"}:
                mapa = {
                    a["id"]: a["vista"]
                    for a in resultado.get("asignaciones", [])
                    if a.get("id") in desde_toma
                }
                try:
                    movidos = capturas.reordenar_vistas_toma(raiz, str(borrador), str(toma), mapa)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                if movidos:
                    resultado["motivos"] = [f"Captura reordenada: {', '.join(movidos)}."] + list(resultado.get("motivos") or [])
                    resultado["toma_reordenada"] = movidos
            return resultado

    @app.post("/api/casos/{caso_id}/correcciones")
    def corregir_angulos(caso_id: str, solicitud: SolicitudCorreccion) -> dict[str, Any]:
        """El especialista corrige ángulos medidos; se reevalúa y queda en la bitácora."""

        carpeta = carpeta_salida(caso_id)
        entrada = carpeta_entrada(caso_id)
        ruta_contexto = entrada / "contexto.json"
        if not ruta_contexto.is_file():
            raise HTTPException(404, "No se encontró el contexto original del caso.")
        resultado = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
        validas = {_clave_override(angulo) for angulo in resultado.get("angulos", [])}
        desconocidas = sorted(set(solicitud.overrides) - validas)
        if desconocidas:
            raise HTTPException(400, f"Medidas desconocidas: {', '.join(desconocidas)}")
        with candado:
            contexto = json.loads(ruta_contexto.read_text(encoding="utf-8"))
            overrides = dict(contexto.get("overrides") or {})
            cambios: dict[str, dict[str, Any]] = {}
            antes = resultado.get("mediciones_reba", {})
            for clave, valor in solicitud.overrides.items():
                if valor is None:
                    if clave in overrides:
                        cambios[clave] = {"antes": overrides.pop(clave), "despues": "medición automática"}
                elif overrides.get(clave) != valor:
                    cambios[clave] = {"antes": antes.get(clave), "despues": valor}
                    overrides[clave] = valor
            if not cambios:
                return estado(caso_id)
            contexto["overrides"] = overrides
            ruta_contexto.write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                ejecutar_evaluar(entrada, raiz, backend)
                validacion = val.cargar(carpeta)
                if validacion is not None:
                    val.registrar(validacion, solicitud.usuario, "corregir_angulo", cambios=cambios, comentario=solicitud.comentario)
                    if validacion.get("estado_informe") == "aprobado":
                        validacion.update({"estado_informe": "borrador", "aprobado_por": None, "aprobado_en": None})
                        val.registrar(validacion, solicitud.usuario, "reabrir_informe", comentario="corrección de ángulos")
                    val.guardar(carpeta, validacion)
                    generar_informe(carpeta, config_reba())
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from exc
        return estado(caso_id)

    @app.post("/api/casos/{caso_id}/validacion")
    def validar(caso_id: str, solicitud: SolicitudValidacion) -> dict[str, Any]:
        carpeta = carpeta_salida(caso_id)
        with candado:
            try:
                ejecutar_validacion(carpeta, raiz, solicitud.usuario, solicitud.accion, solicitud.rec_id, solicitud.valores, solicitud.comentario)
            except KeyError as exc:
                raise HTTPException(404, str(exc).strip("'\"")) from exc
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        return estado(caso_id)

    @app.get("/api/casos/{caso_id}/archivos/{nombre}")
    def archivo_salida(caso_id: str, nombre: str) -> FileResponse:
        if not ARCHIVOS_SALIDA.match(nombre):
            raise HTTPException(404, "Archivo no disponible.")
        ruta = carpeta_salida(caso_id) / nombre
        if not ruta.is_file():
            raise HTTPException(404, "Archivo no disponible.")
        descarga = {"filename": f"{caso_id}_{nombre}"} if nombre.endswith(".csv") else {}
        return FileResponse(ruta, headers={"Cache-Control": "no-store"}, **descarga)

    @app.post("/api/capturas/{borrador}")
    def capturar(
        borrador: str, frente: UploadFile | None = File(None), costado: UploadFile | None = File(None), aerea: UploadFile | None = File(None),
    ) -> dict[str, Any]:
        """Guarda una toma (las vistas capturadas en el mismo instante) de forma temporal."""

        validar_id(borrador)
        imagenes = {vista: archivo.file.read(capturas.MAX_BYTES + 1) for vista, archivo in (("frente", frente), ("costado", costado), ("aerea", aerea)) if archivo is not None}
        if not imagenes:
            raise HTTPException(400, "La toma no trae ninguna vista.")
        protegidas: dict[str, bytes] = {}
        poses: dict[str, dict[str, Any]] = {}
        detector = detector_pose()
        for vista, contenido in imagenes.items():
            try:
                capturas.validar_imagen(contenido, vista)
                protegida = privacidad.proteger(contenido, detector.detect, getattr(detector, "detectar_rostros", None))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            except RuntimeError as exc:  # sin detector no se puede difuminar: no se guarda nada
                raise HTTPException(503, f"No se guardó la toma porque no se pudo difuminar el rostro. {exc}") from exc
            protegidas[vista], poses[vista] = protegida.jpeg, protegida.cache()
        with candado_capturas:
            try:
                nueva = capturas.guardar_toma(raiz, borrador, protegidas, poses)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            capturas.purgar_vencidas(raiz)
            return {"toma": nueva, "tomas": capturas.listar_tomas(raiz, borrador)}

    @app.get("/api/capturas/{borrador}")
    def listar_capturas(borrador: str) -> dict[str, Any]:
        validar_id(borrador)
        return {"tomas": capturas.listar_tomas(raiz, borrador), "max_tomas": capturas.MAX_TOMAS, "retencion_horas": capturas.RETENCION_HORAS}

    @app.get("/api/capturas/{borrador}/{toma}/{vista}")
    def imagen_captura(borrador: str, toma: str, vista: str) -> FileResponse:
        ruta = capturas.archivo_vista(raiz, validar_id(borrador), toma, vista)
        if ruta is None:
            raise HTTPException(404, "Captura no disponible.")
        return FileResponse(ruta, headers={"Cache-Control": "private, max-age=86400"})

    @app.delete("/api/capturas/{borrador}")
    def descartar_capturas(borrador: str) -> dict[str, Any]:
        with candado_capturas:
            capturas.descartar(raiz, validar_id(borrador))
        return {"tomas": []}

    @app.get("/api/casos/{caso_id}/fotos/{vista}")
    def foto_original(caso_id: str, vista: str) -> FileResponse:
        if vista not in VISTAS:
            raise HTTPException(404, "Vista no disponible.")
        entrada = carpeta_entrada(caso_id)
        ruta = next((entrada / f"{vista}{ext}" for ext in EXTENSIONES_IMAGEN if (entrada / f"{vista}{ext}").is_file()), None)
        if ruta is None:
            raise HTTPException(404, "Vista no disponible.")
        return FileResponse(ruta, headers={"Cache-Control": "no-store"})

    if (WEB_DIST / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{ruta:path}", include_in_schema=False)
        def interfaz(ruta: str) -> FileResponse:
            if ruta == "api" or ruta.startswith("api/"):
                raise HTTPException(404, "Ruta de API inexistente.")
            archivo = (WEB_DIST / ruta).resolve()
            if ruta and archivo.is_file() and WEB_DIST in archivo.parents:
                return FileResponse(archivo)
            return FileResponse(WEB_DIST / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def sin_interfaz() -> HTMLResponse:
            return HTMLResponse("<p>La interfaz no está compilada. Ejecuta <code>npm install && npm run build</code> en <code>web/</code>.</p>", 503)

    return app


def puerto_libre(preferido: int) -> int:
    """Devuelve el puerto preferido si está libre en 127.0.0.1; si no, uno asignado por el sistema."""

    for puerto in (preferido, 0):
        with socket.socket() as prueba:
            try:
                prueba.bind(("127.0.0.1", puerto))
                return prueba.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("No hay puertos locales disponibles.")


def crear_app_produccion(raiz: Path) -> tuple[FastAPI, DetectorAislado]:
    """App con MediaPipe en un proceso hijo, para la interfaz y el ejecutable."""

    detector = DetectorAislado(cargar_configuracion(raiz / "config" / "umbrales.yaml").pose, raiz)
    return crear_app(raiz, detector), detector


def main() -> None:
    """Inicia el servidor local y abre la interfaz en el navegador."""

    import uvicorn

    parser = argparse.ArgumentParser(description="ErgoAI · interfaz web local")
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador automáticamente")
    argumentos = parser.parse_args()
    raiz = Path(__file__).resolve().parents[2]
    puerto = puerto_libre(argumentos.puerto)
    url = f"http://127.0.0.1:{puerto}/"
    print(f"ErgoAI disponible en {url} (solo este equipo). Ctrl+C para detener.")
    if not argumentos.sin_navegador:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app, detector = crear_app_produccion(raiz)
    try:
        uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")
    finally:
        detector.cerrar()


if __name__ == "__main__":
    main()
