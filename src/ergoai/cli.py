"""Interfaz de línea de comandos de las fases 0 y 1."""

import argparse
import json
from pathlib import Path
from typing import Any

import time

from .angulos import MedicionAngulo, medir_vista
from .anotacion import guardar_angulos, guardar_esqueleto
from .bitacora import registrar
from .config import Configuracion, cargar_configuracion
from .informe import guardar_informe
from .io_imagenes import ImagenRGB, cargar_imagen
from .modelos import Landmark, PoseResult, VistaPose, WorldLandmark
from .pose import MediaPipeBackend, PoseBackend
from .reba import calcular_reba
from .recomendaciones import generar_recomendaciones, hay_ingenieria_en_riesgo_alto
from .residual import recalcular_residual

VISTAS = ("frente", "costado", "aerea")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")


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


def _mejorar_para_aerea(pixeles):
    """Contraste local y escala mínima para ayudar a MediaPipe en top-down."""

    import cv2
    import numpy as np

    rgb = np.asarray(pixeles)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l_canal, a_canal, b_canal = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    l_canal = clahe.apply(l_canal)
    mejorada = cv2.cvtColor(cv2.merge((l_canal, a_canal, b_canal)), cv2.COLOR_LAB2RGB)
    alto, ancho = mejorada.shape[:2]
    if max(alto, ancho) < 960:
        escala = 960 / max(alto, ancho)
        mejorada = cv2.resize(mejorada, (int(ancho * escala), int(alto * escala)), interpolation=cv2.INTER_CUBIC)
    return mejorada


def procesar_vista(
    nombre: str,
    imagen: ImagenRGB,
    backend: PoseBackend,
    configuracion: Configuracion,
    persona_indice: int | None = None,
) -> VistaPose:
    """Ejecuta el backend y conserva una vista sin detección como resultado válido."""

    def _detectar(pixeles, **kwargs):
        try:
            return backend.detect(pixeles, **kwargs) if kwargs else backend.detect(pixeles)
        except TypeError:
            # Backends de prueba sin kwargs opcionales.
            return backend.detect(pixeles) if not kwargs else []

    personas = _detectar(imagen.pixeles)
    intentos = ["base"]
    if not personas and nombre == "aerea":
        # Reintento específico aérea: umbrales más bajos + realce (no inventa landmarks).
        intentos.append("umbrales_bajos")
        personas = _detectar(
            imagen.pixeles,
            min_pose_detection_confidence=0.22,
            min_pose_presence_confidence=0.22,
        )
        if not personas:
            intentos.append("clahe")
            mejorada = _mejorar_para_aerea(imagen.pixeles)
            personas = _detectar(
                mejorada,
                min_pose_detection_confidence=0.18,
                min_pose_presence_confidence=0.18,
            )
            if personas:
                # Remapea a tamaño original si se escaló.
                alto_o, ancho_o = imagen.alto, imagen.ancho
                alto_n, ancho_n = mejorada.shape[:2]
                sx, sy = ancho_o / ancho_n, alto_o / alto_n
                remapeadas = []
                for persona in personas:
                    landmarks = [
                        type(punto)(
                            punto.indice, punto.nombre, punto.x_px * sx, punto.y_px * sy,
                            punto.z, punto.visibility, punto.presence,
                        )
                        for punto in persona.landmarks
                    ]
                    remapeadas.append(type(persona)(landmarks=landmarks, world_landmarks=persona.world_landmarks))
                personas = remapeadas
    indice, persona = elegir_persona(personas, configuracion.pose.vis_min, persona_indice)
    if persona is None:
        motivo = (
            f"persona_indice={persona_indice} fuera de rango; se detectaron {len(personas)} personas"
            if personas and persona_indice is not None
            else f"sin detección de pose ({'/'.join(intentos)})"
        )
        return VistaPose(nombre, imagen.ancho, imagen.alto, False, len(personas), motivo=motivo)
    return VistaPose(
        nombre=nombre, ancho=imagen.ancho, alto=imagen.alto, detectado=True,
        personas_detectadas=len(personas), persona_indice=indice,
        landmarks=persona.landmarks, world_landmarks=persona.world_landmarks,
        motivo=None if intentos == ["base"] else f"aerea:{'/'.join(intentos)}",
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
    with ruta.open(encoding="utf-8-sig") as archivo:
        contenido = json.load(archivo)
    if not isinstance(contenido, dict):
        raise ValueError(f"{ruta} debe contener un objeto JSON.")
    return contenido


def ejecutar_pose(caso: Path, raiz: Path, backend: PoseBackend | None = None) -> Path:
    """Procesa todas las vistas disponibles y escribe `out/<caso>/pose.json`."""

    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    contexto = _cargar_contexto(caso)
    indices = contexto.get("persona_indice", {})
    if not isinstance(indices, dict):
        raise ValueError("contexto.json: persona_indice debe ser un objeto por vista.")
    detector = backend or MediaPipeBackend(configuracion.pose, raiz)
    destino = raiz / "out" / str(contexto.get("caso_id", caso.name))
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
        vista = procesar_vista(nombre, imagen, detector, configuracion, indice)
        vistas[nombre] = vista.a_diccionario(configuracion.pose.vis_min)
        guardar_esqueleto(destino / f"{nombre}_pose.png", imagen.pixeles, vista.landmarks, configuracion.pose.vis_min)
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


def _etiquetas(medidas: list[MedicionAngulo]) -> list[str]:
    """Crea etiquetas compactas para la imagen anotada de una vista."""

    resultado: list[str] = []
    for medida in medidas:
        lado = f" {medida.lado}" if medida.lado else ""
        valor = "?" if medida.valor_deg is None else f"{medida.valor_deg:.1f}°"
        banderas = " ?" if medida.banderas else ""
        resultado.append(f"{medida.medida}{lado}: {valor}{banderas}")
    return resultado


def ejecutar_angulos(caso: Path, raiz: Path, backend: PoseBackend | None = None) -> Path:
    """Genera vectores, ángulos y anotaciones de la Fase 2 para un caso."""

    ruta_pose = ejecutar_pose(caso, raiz, backend)
    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    contexto = _cargar_contexto(caso)
    pose = json.loads(ruta_pose.read_text(encoding="utf-8"))
    destino = ruta_pose.parent
    vectores_salida: dict[str, Any] = {}
    angulos: list[MedicionAngulo] = []
    pendientes: list[dict[str, str | None]] = []
    for nombre, datos in pose["vistas"].items():
        vista = _vista_desde_diccionario(datos)
        vectores, medidas, metadatos = medir_vista(vista, configuracion, contexto)
        datos.update(metadatos)
        vectores_salida[nombre] = {clave: vector.a_diccionario() for clave, vector in vectores.items()}
        angulos.extend(medidas)
        for medida in medidas:
            if medida.valor_deg is None:
                pendientes.append({"medida": medida.medida, "lado": medida.lado, "motivo": medida.motivo})
        ruta_imagen = _ruta_vista(caso, nombre)
        if ruta_imagen is not None:
            imagen = cargar_imagen(ruta_imagen)
            guardar_angulos(destino / f"{nombre}_angulos.png", imagen.pixeles, vista.landmarks, configuracion.pose.vis_min, _etiquetas(medidas))
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


def ejecutar_evaluar(caso: Path, raiz: Path, backend: PoseBackend | None = None) -> Path:
    """Ejecuta pose/ángulos/REBA, recomendaciones, residual e informe local."""

    inicio = time.perf_counter()
    ruta_angulos = ejecutar_angulos(caso, raiz, backend)
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
    recomendaciones = generar_recomendaciones(reba.a_diccionario(), mediciones, contexto)
    if not hay_ingenieria_en_riesgo_alto(recomendaciones, reba.nivel_riesgo):
        raise RuntimeError("R3: riesgo alto/muy alto sin control de ingeniería; revisar el motor de recomendaciones.")
    residual = recalcular_residual(mediciones, contexto, configuracion.reba, recomendaciones, inicial=reba)
    tiempo_evaluacion = time.perf_counter() - inicio
    salida["reba"] = reba.a_diccionario()
    salida["pendientes_manuales"].extend(reba.pendientes_manuales)
    salida["recomendaciones"] = [item.a_diccionario() for item in recomendaciones]
    salida["riesgo_residual"] = residual
    salida["tiempos"] = {"evaluacion_s": round(tiempo_evaluacion, 3)}
    destino = ruta_angulos.parent
    ruta_salida = destino / "resultado.json"
    ruta_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_informe, tiempo_redaccion = guardar_informe(salida, destino, tiempo_evaluacion_s=tiempo_evaluacion)
    salida["tiempos"]["redaccion_informe_s"] = round(tiempo_redaccion, 3)
    salida["informe"] = str(ruta_informe)
    ruta_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    registrar(
        destino,
        usuario="sistema",
        accion="evaluacion_generada",
        campo="resultado",
        valor_anterior=None,
        valor_nuevo={"reba": (reba.final or {}).get("reportado"), "recomendaciones": len(recomendaciones)},
        motivo="Evaluación automática local; pendiente de validación humana.",
    )
    return ruta_salida


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


if __name__ == "__main__":
    main()
