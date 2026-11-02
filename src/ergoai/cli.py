"""Interfaz de línea de comandos de las fases 0 y 1."""

import argparse
import json
from pathlib import Path
from typing import Any

from .angulos import MedicionAngulo, medir_vista
from .anotacion import guardar_angulos, guardar_esqueleto
from .config import Configuracion, cargar_configuracion
from .io_imagenes import ImagenRGB, cargar_imagen
from .modelos import Landmark, PoseResult, VistaPose, WorldLandmark
from .pose import MediaPipeBackend, PoseBackend
from .reba import MEDIDAS_REBA_POR_LADO, MEDIDAS_REBA_UNICAS, calcular_reba, clave_reba

VISTAS = ("frente", "costado", "aerea")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")


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


def imagenes_de_vista(caso: Path, vista: str) -> list[Path]:
    """Imágenes del caso para una vista, sin distinguir mayúsculas en nombre ni extensión."""

    if not caso.is_dir():
        return []
    return sorted(
        ruta for ruta in caso.iterdir()
        if ruta.is_file() and ruta.stem.lower() == vista and ruta.suffix.lower() in EXTENSIONES_IMAGEN
    )


def _ruta_vista(caso: Path, vista: str) -> Path | None:
    imagenes = imagenes_de_vista(caso, vista)
    if len(imagenes) > 1:
        raise ValueError(f"{caso}: hay más de una imagen para la vista {vista} ({', '.join(ruta.name for ruta in imagenes)}); deja solo una.")
    return imagenes[0] if imagenes else None


def _cargar_contexto(caso: Path) -> dict[str, Any]:
    ruta = caso / "contexto.json"
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as archivo:
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


def _override(overrides: dict[str, Any], medida: str, lado: str | None) -> float | None:
    """Valor del especialista; la clave con lado tiene prioridad sobre la genérica."""

    for candidato in (clave_reba(medida, lado), medida):
        if candidato in overrides:
            return float(overrides[candidato])
    return None


def _validar_overrides(overrides: dict[str, Any]) -> None:
    """Rechaza claves que REBA no consume y valores no numéricos (bool no cuenta)."""

    validas = [*MEDIDAS_REBA_UNICAS, *MEDIDAS_REBA_POR_LADO, *(f"{medida}_{lado}" for medida in MEDIDAS_REBA_POR_LADO for lado in ("L", "R"))]
    for clave, valor in overrides.items():
        if clave not in validas:
            raise ValueError(f"contexto.json: override desconocido '{clave}'. Claves válidas: {', '.join(validas)}.")
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise ValueError(f"contexto.json: el override '{clave}' debe ser un número, no {valor!r}.")


def _mediciones_para_reba(salida: dict[str, Any], overrides: dict[str, Any]) -> dict[str, float | None]:
    """Aplica overrides a `salida`, completa medidas sin vista y devuelve las mediciones REBA."""

    _validar_overrides(overrides)
    mediciones: dict[str, float | None] = {}
    for angulo in salida["angulos"]:
        override = _override(overrides, angulo["medida"], angulo.get("lado"))
        if override is not None:
            angulo["valor_medido_deg"] = angulo.get("valor_deg")
            angulo["valor_deg"] = override
            angulo["fuente"] = "especialista"
        mediciones[clave_reba(angulo["medida"], angulo.get("lado"))] = angulo.get("valor_deg")
    esperadas = [(medida, None) for medida in MEDIDAS_REBA_UNICAS] + [(medida, lado) for medida in MEDIDAS_REBA_POR_LADO for lado in ("L", "R")]
    for medida, lado in esperadas:
        override = _override(overrides, medida, lado)
        if clave_reba(medida, lado) in mediciones or override is None:
            continue
        sintetica = MedicionAngulo(medida, lado, override, None, "override_especialista", None, fuente="especialista").a_diccionario()
        salida["angulos"].append({**sintetica, "valor_medido_deg": None})
        mediciones[clave_reba(medida, lado)] = override
    salida["pendientes_manuales"] = [
        pendiente for pendiente in salida["pendientes_manuales"]
        if mediciones.get(clave_reba(pendiente["medida"], pendiente.get("lado"))) is None
    ]
    return mediciones


def ejecutar_evaluar(caso: Path, raiz: Path, backend: PoseBackend | None = None) -> Path:
    """Ejecuta las fases de pose/ángulos y calcula el REBA trazable."""

    ruta_angulos = ejecutar_angulos(caso, raiz, backend)
    configuracion = cargar_configuracion(raiz / "config" / "umbrales.yaml")
    contexto = _cargar_contexto(caso)
    salida = json.loads(ruta_angulos.read_text(encoding="utf-8"))
    overrides = contexto.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("contexto.json: overrides debe ser un objeto.")
    mediciones = _mediciones_para_reba(salida, overrides)
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
    ruta_salida = ruta_angulos.parent / "resultado.json"
    ruta_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
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
