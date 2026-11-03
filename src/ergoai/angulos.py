"""Construcción de vectores y ángulos ergonómicos sin puntuar REBA todavía."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from math import atan2, degrees
from typing import Any, Iterable

from .config import Configuracion
from .geometria import (
    Vector2, angulo_entre, normalizar_angulo, punto_medio, restar, theta_abajo,
    theta_arriba, unitario, rotacion_para_vertical, rotar,
)
from .modelos import Landmark, VistaPose, WorldLandmark

LADOS = ("izquierdo", "derecho")
INDICE_LADO = {"izquierdo": "L", "derecho": "R"}


@dataclass(frozen=True)
class VectorSegmento:
    """Vector 2D en píxeles y su dirección normalizada."""

    px: Vector2
    unitario: Vector2 | None

    def a_diccionario(self) -> dict[str, list[float] | None]:
        """Devuelve una representación JSON estable."""

        return {"px": list(self.px), "unitario": list(self.unitario) if self.unitario else None}


@dataclass
class MedicionAngulo:
    """Una medida trazable de un ángulo, incluida su incertidumbre."""

    medida: str
    lado: str | None
    valor_deg: float | None
    vista: str | None
    metodo: str
    confianza: float | None
    valor_3d_deg: float | None = None
    fuente: str = "automatico"
    banderas: list[str] = field(default_factory=list)
    motivo: str | None = None

    def a_diccionario(self) -> dict[str, Any]:
        """Convierte la medición a JSON."""

        return asdict(self)


def _mapa(landmarks: Iterable[Landmark], vis_min: float) -> dict[int, Landmark]:
    return {punto.indice: punto for punto in landmarks if punto.visibility >= vis_min}


def _mapa_aereo(landmarks: Iterable[Landmark], vis_min: float, presence_min: float = 0.55) -> dict[int, Landmark]:
    """Vista aérea: MediaPipe suele bajar visibility; usa presence como respaldo trazable."""

    return {
        punto.indice: punto
        for punto in landmarks
        if punto.visibility >= vis_min or punto.presence >= presence_min
    }


def _punto(mapa: dict[int, Landmark], indice: int) -> Vector2 | None:
    punto = mapa.get(indice)
    return None if punto is None else (punto.x_px, punto.y_px)


def _medio(mapa: dict[int, Landmark], indices: tuple[int, ...]) -> Vector2 | None:
    puntos = [_punto(mapa, indice) for indice in indices]
    return None if any(punto is None for punto in puntos) else punto_medio(*puntos)  # type: ignore[arg-type]


def _vector(origen: Vector2 | None, destino: Vector2 | None) -> VectorSegmento | None:
    if origen is None or destino is None:
        return None
    resultado = restar(destino, origen)
    direccion = unitario(resultado)
    return None if direccion is None else VectorSegmento(resultado, direccion)


def lado_cercano(vista: VistaPose, vis_min: float) -> str | None:
    """Escoge el lado con mayor visibilidad articular en una vista lateral."""

    mapa_completo = {punto.indice: punto for punto in vista.landmarks}
    promedios: dict[str, float] = {}
    for lado, indices in (("izquierdo", (11, 13, 15, 23, 25)), ("derecho", (12, 14, 16, 24, 26))):
        valores = [mapa_completo[indice].visibility for indice in indices if indice in mapa_completo]
        if valores:
            promedios[lado] = sum(valores) / len(valores)
    candidatas = [lado for lado, valor in promedios.items() if valor >= vis_min]
    return max(candidatas, key=lambda lado: promedios[lado]) if candidatas else None


def construir_vectores_desde_mapa(mapa: dict[int, Landmark], lado_preferido: str | None = None) -> dict[str, VectorSegmento]:
    """Arma vectores a partir de un mapa de landmarks ya filtrado."""

    hombro_medio, cadera_media = _medio(mapa, (11, 12)), _medio(mapa, (23, 24))
    vectores: dict[str, VectorSegmento] = {}

    def agregar(nombre: str, origen: Vector2 | None, destino: Vector2 | None) -> None:
        vector = _vector(origen, destino)
        if vector is not None:
            vectores[nombre] = vector

    agregar("v_tronco", cadera_media, hombro_medio)
    agregar("linea_hombros", _punto(mapa, 11), _punto(mapa, 12))
    agregar("linea_caderas", _punto(mapa, 23), _punto(mapa, 24))
    for lado, hombro, codo, muneca, menique, indice, cadera, rodilla, tobillo in (
        ("L", 11, 13, 15, 17, 19, 23, 25, 27),
        ("R", 12, 14, 16, 18, 20, 24, 26, 28),
    ):
        mano = _medio(mapa, (menique, indice))
        agregar(f"v_brazo_{lado}", _punto(mapa, hombro), _punto(mapa, codo))
        agregar(f"v_antebrazo_{lado}", _punto(mapa, codo), _punto(mapa, muneca))
        agregar(f"v_mano_{lado}", _punto(mapa, muneca), mano)
        agregar(f"v_muslo_{lado}", _punto(mapa, cadera), _punto(mapa, rodilla))
        agregar(f"v_pierna_{lado}", _punto(mapa, rodilla), _punto(mapa, tobillo))
    if lado_preferido == "izquierdo":
        agregar("v_cuello", _punto(mapa, 11), _punto(mapa, 7))
    elif lado_preferido == "derecho":
        agregar("v_cuello", _punto(mapa, 12), _punto(mapa, 8))
    else:
        agregar("v_cuello", hombro_medio, _medio(mapa, (7, 8)))
    return vectores


def construir_vectores(vista: VistaPose, vis_min: float) -> dict[str, VectorSegmento]:
    """Construye todos los vectores medibles de una vista en píxeles."""

    mapa = _mapa(vista.landmarks, vis_min)
    return construir_vectores_desde_mapa(mapa, lado_cercano(vista, vis_min))


def determinar_orientacion(vista: VistaPose, contexto: dict[str, Any], vis_min: float) -> tuple[int | None, str]:
    """Determina el sentido de la mirada lateral según la jerarquía acordada."""

    declarada = contexto.get("orientacion_costado")
    if declarada == "derecha":
        return 1, "contexto"
    if declarada == "izquierda":
        return -1, "contexto"
    mapa = _mapa(vista.landmarks, vis_min)
    diferencias = []
    for punta, talon in ((31, 29), (32, 30)):
        p_punta, p_talon = _punto(mapa, punta), _punto(mapa, talon)
        if p_punta and p_talon:
            diferencias.append(p_punta[0] - p_talon[0])
    if diferencias and sum(diferencias) != 0:
        return (1 if sum(diferencias) > 0 else -1), "pies"
    nariz, orejas = _punto(mapa, 0), _medio(mapa, (7, 8))
    if nariz and orejas and nariz[0] != orejas[0]:
        return (1 if nariz[0] > orejas[0] else -1), "nariz_orejas"
    return None, "indeterminada"


def corregir_inclinacion_camara(vista: VistaPose, contexto: dict[str, Any]) -> VistaPose:
    """Rota landmarks según una vertical real anotada, sin modificar el original."""

    referencias = contexto.get("vertical_referencia", {})
    referencia = referencias.get(vista.nombre) if isinstance(referencias, dict) else None
    if not (isinstance(referencia, list) and len(referencia) == 2 and all(isinstance(punto, list) and len(punto) == 2 for punto in referencia)):
        return vista
    try:
        inicio = float(referencia[0][0]), float(referencia[0][1])
        fin = float(referencia[1][0]), float(referencia[1][1])
    except (TypeError, ValueError):
        return vista
    grados = rotacion_para_vertical((inicio, fin))
    landmarks = [replace(punto, x_px=rotar((punto.x_px, punto.y_px), inicio, grados)[0], y_px=rotar((punto.x_px, punto.y_px), inicio, grados)[1]) for punto in vista.landmarks]
    return replace(vista, landmarks=landmarks)


def _confianza(mapa: dict[int, Landmark], indices: tuple[int, ...]) -> tuple[float | None, list[str]]:
    puntos = [mapa.get(indice) for indice in indices]
    if any(punto is None for punto in puntos):
        return None, []
    valores = [punto.visibility for punto in puntos if punto is not None]
    return min(valores), []


def _world_mapa(puntos: list[WorldLandmark]) -> dict[int, WorldLandmark]:
    return {punto.indice: punto for punto in puntos}


def _angulo_3d(puntos: list[WorldLandmark], a: int, b: int, c: int) -> float | None:
    mapa = _world_mapa(puntos)
    if not all(indice in mapa for indice in (a, b, c)):
        return None
    origen, medio, destino = mapa[a], mapa[b], mapa[c]
    return angulo_entre(
        (medio.x - origen.x, medio.y - origen.y, medio.z - origen.z),
        (destino.x - medio.x, destino.y - medio.y, destino.z - medio.z),
    )


def _tronco_3d(puntos: list[WorldLandmark]) -> float | None:
    """Estima la magnitud de flexión 3D del tronco respecto de la vertical."""

    mapa = _world_mapa(puntos)
    if not all(indice in mapa for indice in (11, 12, 23, 24)):
        return None
    hombros = ((mapa[11].x + mapa[12].x) / 2, (mapa[11].y + mapa[12].y) / 2, (mapa[11].z + mapa[12].z) / 2)
    caderas = ((mapa[23].x + mapa[24].x) / 2, (mapa[23].y + mapa[24].y) / 2, (mapa[23].z + mapa[24].z) / 2)
    return angulo_entre((hombros[0] - caderas[0], hombros[1] - caderas[1], hombros[2] - caderas[2]), (0.0, -1.0, 0.0))


def _banderas(confianza: float | None, vis_confiable: float, valor: float | None, limites: tuple[float, ...], margen: float) -> list[str]:
    banderas: list[str] = []
    if confianza is not None and confianza < vis_confiable:
        banderas.append("baja_visibilidad")
    if valor is not None and any(abs(abs(valor) - limite) <= margen for limite in limites):
        banderas.append("cerca_de_umbral")
    return banderas


def _medicion(
    medida: str, lado: str | None, vista: VistaPose, mapa: dict[int, Landmark], indices: tuple[int, ...],
    valor: float | None, metodo: str, configuracion: Configuracion, limites: tuple[float, ...],
    valor_3d: float | None = None, extra: list[str] | None = None,
) -> MedicionAngulo:
    confianza, _ = _confianza(mapa, indices)
    banderas = _banderas(confianza, configuracion.pose.vis_confiable, valor, limites, configuracion.angulos.margen_umbral_deg)
    if extra:
        banderas.extend(extra)
    if valor is not None and valor_3d is not None and abs(abs(valor) - valor_3d) > configuracion.angulos.umbral_discrepancia_3d_deg:
        banderas.append("posible_escorzo")
    motivo = None if valor is not None else "landmarks requeridos no utilizables"
    return MedicionAngulo(medida, lado, valor, vista.nombre, metodo, confianza, valor_3d, banderas=banderas, motivo=motivo)


def medir_vista(vista: VistaPose, configuracion: Configuracion, contexto: dict[str, Any]) -> tuple[dict[str, VectorSegmento], list[MedicionAngulo], dict[str, Any]]:
    """Mide los ángulos que la vista puede sostener sin completar datos faltantes."""

    if not vista.detectado:
        return {}, [], {}
    vista = corregir_inclinacion_camara(vista, contexto)
    mapa = _mapa(vista.landmarks, configuracion.pose.vis_min)
    vectores = construir_vectores(vista, configuracion.pose.vis_min)
    medidas: list[MedicionAngulo] = []
    meta: dict[str, Any] = {}
    reba = configuracion.reba
    if vista.nombre == "costado":
        sentido, metodo_sentido = determinar_orientacion(vista, contexto, configuracion.pose.vis_min)
        meta = {"orientacion": {"s": sentido, "metodo": metodo_sentido}, "lado_cercano": lado_cercano(vista, configuracion.pose.vis_min)}
        tronco = vectores.get("v_tronco")
        valor_tronco = theta_arriba(tronco.px, sentido) if tronco and sentido else None
        medidas.append(_medicion("tronco_flexion", None, vista, mapa, (11, 12, 23, 24), valor_tronco, "theta_arriba(v_tronco)", configuracion, (reba.tronco.leve, reba.tronco.moderado), _tronco_3d(vista.world_landmarks)))
        cuello = vectores.get("v_cuello")
        cuello_valor = None
        if cuello and tronco and sentido:
            ang_cuello, ang_tronco = theta_arriba(cuello.px, sentido), theta_arriba(tronco.px, sentido)
            cuello_valor = None if ang_cuello is None or ang_tronco is None else normalizar_angulo(ang_cuello - ang_tronco - configuracion.angulos.cuello_offset_neutro_deg)
        lado_cuello = lado_cercano(vista, configuracion.pose.vis_min)
        indices_cuello = (11, 7) if lado_cuello == "izquierdo" else (12, 8) if lado_cuello == "derecho" else (11, 12, 7, 8)
        medidas.append(_medicion("cuello_flexion", INDICE_LADO.get(lado_cuello) if lado_cuello else None, vista, mapa, indices_cuello, cuello_valor, "theta_arriba(v_cuello)-theta_arriba(v_tronco)-offset", configuracion, (reba.cuello.flexion,), extra=["baja_confianza_metodo"] if cuello_valor is not None and lado_cuello is None else None))
        for lado, letra, hombro, codo, muneca, cadera, rodilla, tobillo in (
            ("izquierdo", "L", 11, 13, 15, 23, 25, 27), ("derecho", "R", 12, 14, 16, 24, 26, 28)
        ):
            brazo, antebrazo, mano, muslo, pierna = (vectores.get(f"v_{nombre}_{letra}") for nombre in ("brazo", "antebrazo", "mano", "muslo", "pierna"))
            brazo_valor = None
            if brazo and tronco and sentido:
                primero, segundo = theta_abajo(brazo.px, sentido), theta_abajo((-tronco.px[0], -tronco.px[1]), sentido)
                brazo_valor = None if primero is None or segundo is None else normalizar_angulo(primero - segundo)
            medidas.append(_medicion("brazo_flexion", letra, vista, mapa, (hombro, codo, 11, 12, 23, 24), brazo_valor, "theta_abajo(v_brazo)-theta_abajo(-v_tronco)", configuracion, (reba.brazo.neutro, reba.brazo.medio, reba.brazo.alto)))
            codo_valor = angulo_entre(brazo.px, antebrazo.px) if brazo and antebrazo else None
            medidas.append(_medicion("codo_flexion", letra, vista, mapa, (hombro, codo, muneca), codo_valor, "angulo_entre(v_brazo,v_antebrazo)", configuracion, (reba.antebrazo.min, reba.antebrazo.max), _angulo_3d(vista.world_landmarks, hombro, codo, muneca)))
            muneca_valor = angulo_entre(antebrazo.px, mano.px) if antebrazo and mano else None
            medidas.append(_medicion("muneca_flexion_extension", letra, vista, mapa, (codo, muneca, 17 if letra == "L" else 18, 19 if letra == "L" else 20), muneca_valor, "angulo_entre(v_antebrazo,v_mano)", configuracion, (reba.muneca.flexion,), extra=["baja_confianza_metodo"]))
            rodilla_valor = angulo_entre(muslo.px, pierna.px) if muslo and pierna else None
            medidas.append(_medicion("rodilla_flexion", letra, vista, mapa, (cadera, rodilla, tobillo), rodilla_valor, "angulo_entre(v_muslo,v_pierna)", configuracion, (reba.rodilla.leve, reba.rodilla.alta), _angulo_3d(vista.world_landmarks, cadera, rodilla, tobillo)))
    elif vista.nombre == "frente":
        tronco = vectores.get("v_tronco")
        lateral = None if tronco is None else abs(degrees(atan2(tronco.px[0], -tronco.px[1])))
        medidas.append(_medicion("tronco_inclinacion_lateral", None, vista, mapa, (11, 12, 23, 24), lateral, "abs(atan2(v_tronco.x,-v_tronco.y))", configuracion, (reba.umbral_inclinacion_lateral_tronco_deg,)))
        for letra, hombro, codo in (("L", 11, 13), ("R", 12, 14)):
            brazo = vectores.get(f"v_brazo_{letra}")
            if brazo is None or tronco is None:
                valor = None
            else:
                phi_brazo = degrees(atan2(brazo.px[0], brazo.px[1]))
                phi_tronco = degrees(atan2(-tronco.px[0], -tronco.px[1]))
                valor = abs(normalizar_angulo(phi_brazo - phi_tronco))
            medidas.append(_medicion("brazo_abduccion", letra, vista, mapa, (hombro, codo, 11, 12, 23, 24), valor, "abs(normalizar(phi(v_brazo)-phi(-v_tronco)))", configuracion, (reba.umbral_abduccion_brazo_deg,)))
        cabeza = _punto(mapa, 0) or _medio(mapa, (2, 5))
        hombros = _medio(mapa, (11, 12))
        v_cabeza = _vector(hombros, cabeza)
        cuello_lateral = angulo_entre(v_cabeza.px, tronco.px) if v_cabeza and tronco else None
        medidas.append(_medicion("cuello_inclinacion_rotacion", None, vista, mapa, (0, 11, 12, 23, 24), cuello_lateral, "angulo_entre(v_cabeza,v_tronco)", configuracion, (reba.umbral_cuello_lateral_rotacion_deg,)))
        tobillo_l, tobillo_r = _punto(mapa, 27), _punto(mapa, 28)
        cadera_l, rodilla_l = _punto(mapa, 23), _punto(mapa, 25)
        largo_pierna = None if cadera_l is None or rodilla_l is None or tobillo_l is None else abs(cadera_l[1] - rodilla_l[1]) + abs(rodilla_l[1] - tobillo_l[1])
        apoyo = None if tobillo_l is None or tobillo_r is None or not largo_pierna else float(abs(tobillo_l[1] - tobillo_r[1]) > configuracion.angulos.umbral_pie_levantado * largo_pierna)
        medidas.append(_medicion("apoyo_piernas_unilateral", None, vista, mapa, (23, 25, 27, 28), apoyo, "abs(y_tobillo_L-y_tobillo_R)>umbral×largo_pierna", configuracion, (1.0,)))
    elif vista.nombre == "aerea":
        # Top-down suele reportar visibility baja; umbral más permisivo + presence, siempre con bandera.
        vis_aerea = max(0.28, configuracion.pose.vis_min * 0.6)  # SUPUESTO: confirmar con Jabil
        mapa_a = _mapa_aereo(vista.landmarks, vis_aerea)
        vectores_a = construir_vectores_desde_mapa(mapa_a)
        meta["vis_min_aerea"] = vis_aerea
        meta["aporte_aerea"] = "torsión de tronco y asimetría de alcance (plano horizontal)"
        hombros, caderas = vectores_a.get("linea_hombros"), vectores_a.get("linea_caderas")
        bruto = angulo_entre(hombros.px, caderas.px) if hombros and caderas else None
        torsion = None if bruto is None else min(bruto, 180.0 - bruto)
        medidas.append(
            _medicion(
                "tronco_torsion", None, vista, mapa_a, (11, 12, 23, 24), torsion,
                "min(angulo(linea_hombros,linea_caderas),180-angulo)", configuracion,
                (reba.umbral_torsion_tronco_deg,),
                extra=["vista_aerea", "baja_visibilidad"] if torsion is not None else ["vista_aerea"],
            )
        )
        alcances: dict[str, float] = {}
        for letra, hombro, muneca in (("L", 11, 15), ("R", 12, 16)):
            origen, destino = _punto(mapa_a, hombro), _punto(mapa_a, muneca)
            if origen is None or destino is None or hombros is None:
                valor = None
            else:
                alcance = _vector(origen, destino)
                valor = angulo_entre(hombros.px, alcance.px) if alcance else None
                if valor is not None:
                    valor = min(valor, 180.0 - valor)
                    alcances[letra] = valor
            medidas.append(
                _medicion(
                    "alcance_horizontal", letra, vista, mapa_a, (11, 12, hombro, muneca), valor,
                    "min(angulo(linea_hombros,hombro→muñeca),180-angulo)", configuracion,
                    (20.0, 45.0),
                    extra=["vista_aerea"],
                )
            )
        if "L" in alcances and "R" in alcances:
            asimetria = abs(alcances["L"] - alcances["R"])
        else:
            asimetria = None
        medidas.append(
            _medicion(
                "alcance_asimetria", None, vista, mapa_a, (11, 12, 15, 16), asimetria,
                "abs(alcance_L-alcance_R)", configuracion, (15.0, 30.0),
                extra=["vista_aerea"],
            )
        )
        # Sustituye vectores reportados por los de umbral aéreo para trazabilidad.
        vectores = vectores_a
        mapa = mapa_a
    return vectores, medidas, meta
