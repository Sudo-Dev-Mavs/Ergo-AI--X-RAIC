"""Interfaz de línea de comandos de las fases 0 y 1."""

import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .angulos import MedicionAngulo, medir_vista
from .anotacion import guardar_angulos, guardar_esqueleto
from .config import Configuracion, cargar_configuracion
from .io_imagenes import ImagenRGB, cargar_imagen
from .modelos import Landmark, PoseResult, VistaPose, WorldLandmark
from .pose import MediaPipeBackend, PoseBackend
from .privacidad import personas_desde_dict
from .informe import generar_informe
from .reba import banda_medida, calcular_reba
from .respaldos import completar_con_respaldos
from .recomendaciones import generar_recomendaciones, ordenar
from .residual import calcular_residual, delta_individual
from . import validacion as val

VISTAS = ("frente", "costado", "aerea")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
# Umbral de visibilidad solo para DIBUJAR la vista aérea (desde arriba MediaPipe da poca confianza);
# la medición REBA sigue usando ``pose.vis_min``.
VIS_DIBUJO_AEREA = 0.22


def _medidas_para_anotar(angulos: list[MedicionAngulo], vista: str) -> list[MedicionAngulo]:
    """Medidas a dibujar en una foto. La aérea siempre muestra torsión si existe valor,
    aunque el respaldo 3D la haya etiquetado en costado/frente."""

    propias = [m for m in angulos if m.vista == vista and m.valor_deg is not None]
    if vista != "aerea":
        return propias
    if any(m.medida == "tronco_torsion" for m in propias):
        return propias
    torsion = next((m for m in angulos if m.medida == "tronco_torsion" and m.valor_deg is not None), None)
    return [*propias, torsion] if torsion is not None else propias


def _area_visible(persona: PoseResult, vis_min: float) -> float:
    """Devuelve el área de la caja de landmarks utilizables de una persona."""

    puntos = [punto for punto in persona.landmarks if punto.visibility >= vis_min]
    if len(puntos) < 2:
        return 0.0
    xs = [punto.x_px for punto in puntos]
    ys = [punto.y_px for punto in puntos]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def elegir_persona(personas: list[PoseResult], vis_min: float, persona_indice: int | None) -> tuple[int | None, PoseResult | None]:
    """Respeta el índice explícito o elige la caja visible más grande."""

    if not personas:
        return None, None
    if persona_indice is not None:
        if 0 <= persona_indice < len(personas):
            return persona_indice, personas[persona_indice]
        return None, None
    indice = max(range(len(personas)), key=lambda actual: _area_visible(personas[actual], vis_min))
    return indice, personas[indice]


def procesar_vista(
    nombre: str,
    imagen: ImagenRGB,
    backend: PoseBackend,
    configuracion: Configuracion,
    persona_indice: int | None = None,
) -> VistaPose:
    """Ejecuta el backend y conserva una vista sin detección como resultado válido."""

    personas = backend.detect(imagen.pixeles)
    indice, persona = elegir_persona(personas, configuracion.pose.vis_min, persona_indice)
    if persona is None:
        motivo = (
            f"persona_indice={persona_indice} fuera de rango; se detectaron {len(personas)} personas"
            if personas and persona_indice is not None
            else "sin detección de pose"
        )
        return VistaPose(nombre, imagen.ancho, imagen.alto, False, len(personas), motivo=motivo)
    return VistaPose(
        nombre=nombre, ancho=imagen.ancho, alto=imagen.alto, detectado=True,
        personas_detectadas=len(personas), persona_indice=indice,
        landmarks=persona.landmarks, world_landmarks=persona.world_landmarks,
    )


def _ruta_vista(caso: Path, vista: str) -> Path | None:
    for extension in EXTENSIONES_IMAGEN:
        candidata = caso / f"{vista}{extension}"
        if candidata.is_file():
            return candidata
    return None


def _cargar_contexto(caso: Path) -> dict[str, Any]:
    ruta = caso / "contexto.json"
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as archivo:
        contenido = json.load(archivo)
    if not isinstance(contenido, dict):
        raise ValueError(f"{ruta} debe contener un objeto JSON.")
    return contenido


class _PosesFijas:
    """Backend que devuelve una pose ya detectada (la de la toma original, antes de difuminar)."""

    def __init__(self, personas: list[PoseResult]) -> None:
        self.personas = personas

    def detect(self, image: Any) -> list[PoseResult]:
        return self.personas


def _pose_cacheada(caso: Path, nombre: str, ruta_imagen: Path, imagen: ImagenRGB) -> list[PoseResult] | None:
    """Pose guardada junto a una toma de cámara, solo si corresponde exactamente a esta imagen."""

    ruta = caso / f"{nombre}.pose.json"
    if not ruta.is_file():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if datos.get("sha256") != hashlib.sha256(ruta_imagen.read_bytes()).hexdigest():
            return None
        if (datos.get("ancho"), datos.get("alto")) != (imagen.ancho, imagen.alto):
            return None
        return personas_desde_dict(datos.get("personas", []))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def ejecutar_pose(caso: Path, raiz: Path, backend: PoseBackend | None = None, carpeta_salida: Path | None = None) -> Path:
    """Procesa todas las vistas disponibles y escribe `out/<caso>/pose.json`."""

    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    contexto = _cargar_contexto(caso)
    indices = contexto.get("persona_indice", {})
    if not isinstance(indices, dict):
        raise ValueError("contexto.json: persona_indice debe ser un objeto por vista.")
    detector = backend or MediaPipeBackend(configuracion.pose, raiz)
    destino = (carpeta_salida or raiz / "out") / str(contexto.get("caso_id", caso.name))
    destino.mkdir(parents=True, exist_ok=True)
    vistas: dict[str, dict[str, Any]] = {}
    advertencias: list[str] = []
    for nombre in VISTAS:
        ruta_imagen = _ruta_vista(caso, nombre)
        if ruta_imagen is None:
            continue
        imagen = cargar_imagen(ruta_imagen)
        indice = indices.get(nombre)
        if indice is not None and (not isinstance(indice, int) or isinstance(indice, bool)):
            raise ValueError(f"contexto.json: persona_indice.{nombre} debe ser entero o null.")
        cacheadas = _pose_cacheada(caso, nombre, ruta_imagen, imagen)
        vista = procesar_vista(nombre, imagen, _PosesFijas(cacheadas) if cacheadas is not None else detector, configuracion, indice)
        vistas[nombre] = vista.a_diccionario(configuracion.pose.vis_min)
        if cacheadas is not None:
            vistas[nombre]["fuente_pose"] = "pose detectada antes de difuminar el rostro"
        # Aérea: MediaPipe suele marcar poca visibilidad desde arriba; bajamos solo el umbral de dibujo.
        vis_esqueleto = VIS_DIBUJO_AEREA if nombre == "aerea" else configuracion.pose.vis_min
        guardar_esqueleto(destino / f"{nombre}_pose.png", imagen.pixeles, vista.landmarks, vis_esqueleto)
        if not vista.detectado:
            advertencias.append(f"vista {nombre}: {vista.motivo}")
    if not vistas:
        raise ValueError(f"No se encontraron imágenes frente/costado/aerea en {caso}.")
    salida = {
        "caso_id": contexto.get("caso_id", caso.name),
        "version_modelo": "pose_landmarker_heavy / mediapipe 1.1.1",
        "vistas": vistas,
        "pendientes_manuales": [],
        "advertencias": advertencias,
    }
    ruta_salida = destino / "pose.json"
    ruta_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta_salida


def _vista_desde_diccionario(datos: dict[str, Any]) -> VistaPose:
    """Reconstruye una vista serializada para medir ángulos sin redetectarla."""

    campos = ("nombre", "ancho", "alto", "detectado", "personas_detectadas", "motivo", "persona_indice")
    argumentos = {campo: datos.get(campo) for campo in campos}
    argumentos["landmarks"] = [
        Landmark(**{campo: punto[campo] for campo in ("indice", "nombre", "x_px", "y_px", "z", "visibility", "presence")})
        for punto in datos.get("landmarks", [])
    ]
    argumentos["world_landmarks"] = [WorldLandmark(**punto) for punto in datos.get("world_landmarks", [])]
    return VistaPose(**argumentos)


def ejecutar_angulos(caso: Path, raiz: Path, backend: PoseBackend | None = None, carpeta_salida: Path | None = None) -> Path:
    """Genera vectores, ángulos y anotaciones de la Fase 2 para un caso."""

    ruta_pose = ejecutar_pose(caso, raiz, backend, carpeta_salida)
    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    contexto = _cargar_contexto(caso)
    pose = json.loads(ruta_pose.read_text(encoding="utf-8"))
    destino = ruta_pose.parent
    vectores_salida: dict[str, Any] = {}
    angulos: list[MedicionAngulo] = []
    pendientes: list[dict[str, str | None]] = []
    vistas_pose: dict[str, VistaPose] = {}
    for nombre, datos in pose["vistas"].items():
        vista = _vista_desde_diccionario(datos)
        vistas_pose[nombre] = vista
        vectores, medidas, metadatos = medir_vista(vista, configuracion, contexto)
        datos.update(metadatos)
        vectores_salida[nombre] = {clave: vector.a_diccionario() for clave, vector in vectores.items()}
        angulos.extend(medidas)
    # Lo que la vista primaria no pudo medir se intenta con la vista de respaldo y con la pose 3D.
    angulos = completar_con_respaldos(angulos, vistas_pose, contexto, configuracion)
    for medida in angulos:
        if medida.valor_deg is None:
            pendientes.append({"medida": medida.medida, "lado": medida.lado, "motivo": medida.motivo})
    for nombre, vista in vistas_pose.items():
        ruta_imagen = _ruta_vista(caso, nombre)
        if ruta_imagen is not None:
            imagen = cargar_imagen(ruta_imagen)
            de_vista = _medidas_para_anotar(angulos, nombre)
            bandas = [banda_medida(m.medida, m.valor_deg, configuracion.reba) for m in de_vista]
            # Aérea: MediaPipe suele marcar poca visibilidad; bajamos solo el umbral de dibujo.
            vis_dibujo = VIS_DIBUJO_AEREA if nombre == "aerea" else None
            guardar_angulos(
                destino / f"{nombre}_angulos.png", imagen.pixeles, vista.landmarks,
                configuracion.pose.vis_min, de_vista, bandas, vis_dibujo=vis_dibujo,
            )
    salida = {
        "caso_id": pose["caso_id"], "version_modelo": pose["version_modelo"],
        "vistas": pose["vistas"], "vectores": vectores_salida,
        "angulos": [medida.a_diccionario() for medida in angulos],
        "pendientes_manuales": pendientes, "advertencias": pose["advertencias"],
    }
    ruta_salida = destino / "angulos.json"
    ruta_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta_salida


def _mediciones_para_reba(angulos: list[dict[str, Any]], overrides: dict[str, Any]) -> dict[str, float | None]:
    """Extrae medidas de la salida y registra overrides de especialista."""

    mediciones: dict[str, float | None] = {}
    for angulo in angulos:
        medida, lado = angulo["medida"], angulo.get("lado")
        clave = f"{medida}_{lado}" if lado and medida != "cuello_flexion" else medida
        candidatos = [clave, medida]
        override = next((overrides[candidato] for candidato in candidatos if isinstance(overrides.get(candidato), (int, float)) and not isinstance(overrides[candidato], bool)), None)
        if override is not None:
            angulo["valor_medido_deg"] = angulo.get("valor_deg")
            angulo["valor_deg"] = float(override)
            angulo["fuente"] = "especialista"
        mediciones[clave] = angulo.get("valor_deg")
    return mediciones


def _clave_pendiente(pendiente: dict[str, Any]) -> str:
    """Clave de ``mediciones_reba`` para un pendiente: «codo_flexion» + lado L → «codo_flexion_L»."""

    medida = str(pendiente.get("medida") or "")
    lado = pendiente.get("lado")
    if lado in ("L", "R") and not medida.endswith(("_L", "_R")) and medida != "cuello_flexion":
        return f"{medida}_{lado}"
    return medida


def _compactar_pendientes(pendientes: list[dict[str, Any]], mediciones: dict[str, float | None]) -> list[dict[str, Any]]:
    """Una entrada por medida y lado; quita los avisos de «no medible» de lo que ya tiene valor usable.

    Ángulos y REBA avisan por separado de la misma medida, y un respaldo o una corrección del
    especialista puede dar valor a una medida que la vista primaria no logró medir.
    """

    vistos: set[str] = set()
    salida: list[dict[str, Any]] = []
    for pendiente in pendientes:
        clave = _clave_pendiente(pendiente)
        motivo = str(pendiente.get("motivo") or "").lower()
        falta_medicion = any(texto in motivo for texto in ("landmark", "ausente", "no utilizable"))
        if (falta_medicion and mediciones.get(clave) is not None) or clave in vistos:
            continue
        vistos.add(clave)
        salida.append(pendiente)
    return salida


def ejecutar_evaluar(caso: Path, raiz: Path, backend: PoseBackend | None = None, carpeta_salida: Path | None = None,
                     segundos_previos: float = 0.0) -> Path:
    """Ejecuta pose, ángulos, REBA, recomendaciones, riesgo residual e informe borrador.

    ``segundos_previos`` suma el trabajo del agente hecho antes de llamar aquí (la detección de pose
    al difuminar las fotos subidas), para que ``analisis_total`` siga midiendo todo el análisis.
    """

    val.usar_clave(raiz)
    inicio = time.perf_counter()
    ruta_angulos = ejecutar_angulos(caso, raiz, backend, carpeta_salida)
    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    contexto = _cargar_contexto(caso)
    salida = json.loads(ruta_angulos.read_text(encoding="utf-8"))
    overrides = contexto.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("contexto.json: overrides debe ser un objeto.")
    mediciones = _mediciones_para_reba(salida["angulos"], overrides)
    reba = calcular_reba(mediciones, contexto, configuracion.reba)
    for angulo in salida["angulos"]:
        lado = angulo.get("lado")
        if angulo["medida"] == "tronco_flexion":
            angulo["banda_reba"] = reba.grupo_a["tronco"]
        elif angulo["medida"] == "cuello_flexion":
            angulo["banda_reba"] = reba.grupo_a["cuello"]
        elif angulo["medida"] == "rodilla_flexion":
            angulo["banda_reba"] = reba.grupo_a["piernas"]
        elif lado in ("L", "R"):
            campo = {"brazo_flexion": "brazo", "codo_flexion": "antebrazo", "muneca_flexion_extension": "muneca"}.get(angulo["medida"])
            if campo:
                angulo["banda_reba"] = reba.grupo_b[lado][campo]
    salida["reba"] = reba.a_diccionario()
    salida["pendientes_manuales"].extend(reba.pendientes_manuales)
    salida["pendientes_manuales"] = _compactar_pendientes(salida["pendientes_manuales"], mediciones)
    salida["contexto"] = contexto
    salida["mediciones_reba"] = mediciones
    salida["fecha_analisis"] = datetime.now().astimezone().isoformat(timespec="seconds")
    recomendaciones = generar_recomendaciones(mediciones, contexto, salida["reba"], configuracion.reba)
    for recomendacion in recomendaciones:
        recomendacion.delta_reba = delta_individual(mediciones, contexto, recomendacion.a_diccionario(), configuracion.reba)
    salida["recomendaciones"] = [recomendacion.a_diccionario() for recomendacion in ordenar(recomendaciones)]
    salida["riesgo_residual"] = calcular_residual(mediciones, contexto, salida["recomendaciones"], configuracion.reba)
    salida["tiempos_s"] = {"analisis_total": round(time.perf_counter() - inicio + segundos_previos, 2)}
    if segundos_previos:
        salida["tiempos_s"]["deteccion_y_difuminado"] = round(segundos_previos, 2)
    ruta_salida = ruta_angulos.parent / "resultado.json"
    ruta_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    val.sincronizar(ruta_salida.parent, salida)
    generar_informe(ruta_salida.parent, configuracion.reba)
    return ruta_salida


def carpeta_resultado(ruta: Path, raiz: Path) -> Path:
    """Acepta la carpeta de salida o la del caso de entrada y devuelve `out/<caso>`."""

    if (ruta / "resultado.json").is_file():
        return ruta
    contexto = _cargar_contexto(ruta) if ruta.is_dir() else {}
    candidata = raiz / "out" / str(contexto.get("caso_id", ruta.name))
    if not (candidata / "resultado.json").is_file():
        raise ValueError(f"No hay resultado.json para {ruta}; ejecuta primero `evaluar`.")
    return candidata


def ejecutar_validacion(carpeta: Path, raiz: Path, usuario: str, accion: str, rec_id: str | None = None,
                        valores: dict[str, str] | None = None, comentario: str = "") -> Path:
    """Aplica una decisión del especialista, la registra y regenera el informe."""

    val.usar_clave(raiz)
    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    resultado = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
    validacion = val.cargar(carpeta) or val.sincronizar(carpeta, resultado)
    if accion in ("aprobar", "rechazar", "reabrir", "eliminar"):
        if not rec_id:
            raise ValueError("Indica la recomendación con --rec.")
        val.decidir(validacion, rec_id, usuario, accion, comentario)
    elif accion == "editar":
        if not rec_id:
            raise ValueError("Indica la recomendación con --rec.")
        val.editar(validacion, rec_id, usuario, valores or {}, comentario)
    elif accion == "agregar":
        datos = valores or {}
        val.agregar(validacion, usuario, datos.get("problema", ""), datos.get("solucion", ""), datos.get("jerarquia", "rediseno"),
                    datos.get("responsable", ""), datos.get("fecha_compromiso", ""))
    elif accion == "ajustar_residual":
        datos = valores or {}
        if "riesgo_residual_proyectado" not in datos:
            raise ValueError("Indica riesgo_residual_proyectado (1–15) en --campo.")
        val.ajustar_residual(validacion, usuario, int(datos["riesgo_residual_proyectado"]), comentario)
    elif accion == "limpiar_residual":
        val.limpiar_residual(validacion, usuario, comentario)
    elif accion == "aprobar_informe":
        reba = resultado.get("reba") or {}
        val.aprobar_informe(
            validacion, usuario, reba.get("nivel_accion"), comentario,
            puntaje_reba=(reba.get("final") or {}).get("reportado"),
        )
    else:
        raise ValueError(f"Acción desconocida: {accion}")
    val.guardar(carpeta, validacion)
    return generar_informe(carpeta, configuracion.reba)


def main() -> None:
    """Punto de entrada para `python -m ergoai.cli pose <caso>`."""

    parser = argparse.ArgumentParser(description="ErgoAI: detección local de pose")
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    pose = subcomandos.add_parser("pose", help="extrae landmarks y dibuja el esqueleto corporal")
    pose.add_argument("caso", type=Path, help="carpeta de un caso con frente/costado/aerea")
    angulos = subcomandos.add_parser("angulos", help="mide ángulos y genera sus anotaciones")
    angulos.add_argument("caso", type=Path, help="carpeta de un caso con frente/costado/aerea")
    evaluar = subcomandos.add_parser("evaluar", help="calcula REBA y genera resultado.json")
    evaluar.add_argument("caso", type=Path, help="carpeta de un caso con frente/costado/aerea")
    informe = subcomandos.add_parser("informe", help="regenera informe.html con el estado de validación vigente")
    informe.add_argument("caso", type=Path, help="carpeta del caso o de out/<caso>")
    validar = subcomandos.add_parser("validar", help="registra una decisión del especialista en la bitácora")
    validar.add_argument("caso", type=Path, help="carpeta del caso o de out/<caso>")
    validar.add_argument("accion", choices=("aprobar", "rechazar", "reabrir", "eliminar", "editar", "agregar", "ajustar_residual", "limpiar_residual", "aprobar_informe"))
    validar.add_argument("--usuario", required=True, help="nombre del especialista")
    validar.add_argument("--rec", help="ID de la recomendación, p. ej. R-TRONCO-ING")
    validar.add_argument("--campo", action="append", default=[], metavar="CAMPO=VALOR", help="campo a editar/agregar (repetible)")
    validar.add_argument("--comentario", default="")
    argumentos = parser.parse_args()
    if argumentos.comando == "pose":
        raiz = Path(__file__).resolve().parents[2]
        salida = ejecutar_pose(argumentos.caso.resolve(), raiz)
        print(f"Pose guardada en {salida}")
    if argumentos.comando == "angulos":
        raiz = Path(__file__).resolve().parents[2]
        salida = ejecutar_angulos(argumentos.caso.resolve(), raiz)
        print(f"Ángulos guardados en {salida}")
    if argumentos.comando == "evaluar":
        raiz = Path(__file__).resolve().parents[2]
        salida = ejecutar_evaluar(argumentos.caso.resolve(), raiz)
        print(f"Resultado REBA guardado en {salida}")
        print(f"Informe borrador: {salida.parent / 'informe.html'}")
    if argumentos.comando in ("informe", "validar"):
        raiz = Path(__file__).resolve().parents[2]
        carpeta = carpeta_resultado(argumentos.caso.resolve(), raiz)
        if argumentos.comando == "informe":
            val.usar_clave(raiz)
            configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
            print(f"Informe: {generar_informe(carpeta, configuracion.reba)}")
        else:
            valores = dict(par.split("=", 1) for par in argumentos.campo)
            ruta = ejecutar_validacion(carpeta, raiz, argumentos.usuario, argumentos.accion, argumentos.rec, valores, argumentos.comentario)
            print(f"Cambio registrado. Informe: {ruta}")


if __name__ == "__main__":
    main()
