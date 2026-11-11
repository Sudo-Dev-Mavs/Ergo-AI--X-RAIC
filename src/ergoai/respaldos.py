"""Respaldo entre vistas y 3D para las medidas que la vista primaria no pudo sostener.

Sigue la tabla de la especificación (§7.3): cuando una medida REBA falta o no es utilizable en su
vista primaria, se intenta con la vista de respaldo (2D) y después con la pose 3D de MediaPipe
(``pose_world_landmarks``, en metros, con el origen en las caderas y el eje y hacia abajo). Toda
medida obtenida así lleva la bandera ``vista_respaldo``; las que solo dan la magnitud (sin saber si
es flexión o extensión) llevan además ``baja_confianza_metodo``.

Los planos 3D se definen con el cuerpo, no con la cámara: el eje lateral es la línea de caderas, el
vertical es el «arriba» de la cámara (vistas de frente y costado, no aérea), el plano sagital es
perpendicular al eje lateral y el frontal contiene ambos.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from .angulos import MedicionAngulo, _banderas, _mapa, construir_vectores, corregir_inclinacion_camara
from .config import Configuracion
from .geometria import angulo_entre
from .modelos import VistaPose, WorldLandmark

Vec3 = tuple[float, float, float]
LADOS = (("L", 11, 13, 15, 23, 25, 27), ("R", 12, 14, 16, 24, 26, 28))
ARRIBA: Vec3 = (0.0, -1.0, 0.0)


def _resta(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _punto_3d(mapa: dict[int, WorldLandmark], *indices: int) -> Vec3 | None:
    if not all(i in mapa for i in indices):
        return None
    n = len(indices)
    return (sum(mapa[i].x for i in indices) / n, sum(mapa[i].y for i in indices) / n, sum(mapa[i].z for i in indices) / n)


def _unit(v: Vec3) -> Vec3 | None:
    largo = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5
    return None if largo < 1e-9 else (v[0] / largo, v[1] / largo, v[2] / largo)


def _proyectar(v: Vec3, normal: Vec3) -> Vec3:
    d = v[0] * normal[0] + v[1] * normal[1] + v[2] * normal[2]
    return (v[0] - d * normal[0], v[1] - d * normal[1], v[2] - d * normal[2])


def _cruz(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class Cuerpo3D:
    """Ejes corporales a partir de los landmarks 3D de una vista de frente o costado."""

    def __init__(self, vista: VistaPose, vis_min: float) -> None:
        self.vista = vista.nombre
        self.mapa = {p.indice: p for p in vista.world_landmarks if max(p.visibility, p.presence) >= vis_min}
        hombros, caderas = _punto_3d(self.mapa, 11, 12), _punto_3d(self.mapa, 23, 24)
        lateral = None if 23 not in self.mapa or 24 not in self.mapa else _unit(_resta(_punto_3d(self.mapa, 24), _punto_3d(self.mapa, 23)))  # type: ignore[arg-type]
        self.tronco = _resta(hombros, caderas) if hombros and caderas else None
        self.lateral = lateral
        frente = _unit(_cruz(lateral, ARRIBA)) if lateral else None
        self.frontal_normal = frente  # normal del plano frontal (hacia delante o atrás, da igual para magnitudes)

    def valido(self) -> bool:
        return self.tronco is not None and self.lateral is not None and self.frontal_normal is not None

    def confianza(self, *indices: int) -> float | None:
        valores = [self.mapa[i].visibility for i in indices if i in self.mapa]
        return min(valores) if len(valores) == len(indices) else None

    def angulo_en_plano(self, u: Vec3, v: Vec3, normal: Vec3) -> float | None:
        return angulo_entre(_proyectar(u, normal), _proyectar(v, normal))


def _cuerpo(vistas: dict[str, VistaPose], vis_min: float) -> Cuerpo3D | None:
    """Pose 3D de costado o, si no, de frente (la aérea no sirve: su «arriba» no es la vertical)."""

    for nombre in ("costado", "frente"):
        vista = vistas.get(nombre)
        if vista is not None and vista.detectado and vista.world_landmarks:
            cuerpo = Cuerpo3D(vista, vis_min)
            if cuerpo.valido():
                return cuerpo
    return None


def _limites(medida: str, config: Configuracion) -> tuple[float, ...]:
    r = config.reba
    return {
        "tronco_flexion": (r.tronco.leve, r.tronco.moderado), "cuello_flexion": (r.cuello.flexion,),
        "brazo_flexion": (r.brazo.neutro, r.brazo.medio, r.brazo.alto), "codo_flexion": (r.antebrazo.min, r.antebrazo.max),
        "rodilla_flexion": (r.rodilla.leve, r.rodilla.alta), "tronco_torsion": (r.umbral_torsion_tronco_deg,),
        "tronco_inclinacion_lateral": (r.umbral_inclinacion_lateral_tronco_deg,), "brazo_abduccion": (r.umbral_abduccion_brazo_deg,),
        "cuello_inclinacion_rotacion": (r.umbral_cuello_lateral_rotacion_deg,), "apoyo_piernas_unilateral": (1.0,),
    }.get(medida, ())


def _clave(medida: str, lado: str | None) -> tuple[str, str | None]:
    return (medida, None if medida == "cuello_flexion" or lado not in ("L", "R") else lado)


REQUERIDAS: list[tuple[str, str | None]] = [
    ("tronco_flexion", None), ("cuello_flexion", None), ("tronco_torsion", None), ("tronco_inclinacion_lateral", None),
    ("cuello_inclinacion_rotacion", None), ("apoyo_piernas_unilateral", None),
    *[(medida, lado) for lado in ("L", "R") for medida in ("brazo_flexion", "codo_flexion", "rodilla_flexion", "brazo_abduccion")],
]


def completar_con_respaldos(medidas: list[MedicionAngulo], vistas: dict[str, VistaPose], contexto: dict[str, Any],
                            config: Configuracion) -> list[MedicionAngulo]:
    """Devuelve las medidas con los faltantes completados por respaldo cuando es posible."""

    vis_min = config.pose.vis_min
    corregidas = {n: corregir_inclinacion_camara(v, contexto) for n, v in vistas.items() if v.detectado}
    cuerpo = _cuerpo(corregidas, vis_min)
    resultado = list(medidas)
    posicion = {_clave(m.medida, m.lado): i for i, m in enumerate(resultado)}

    def nueva(medida: str, lado: str | None, valor: float, vista: str, metodo: str, confianza: float | None, extra: list[str]) -> MedicionAngulo:
        banderas = _banderas(confianza, config.pose.vis_confiable, valor, _limites(medida, config), config.angulos.margen_umbral_deg)
        return MedicionAngulo(medida, lado, valor, vista, metodo, confianza, banderas=["vista_respaldo", *banderas, *extra])

    def frente_2d(medida: str, lado: str) -> MedicionAngulo | None:
        vista = corregidas.get("frente")
        if vista is None:
            return None
        vectores, mapa = construir_vectores(vista, vis_min), _mapa(vista.landmarks, vis_min)
        _, hombro, codo, muneca, cadera, rodilla, tobillo = next(t for t in LADOS if t[0] == lado)
        if medida == "codo_flexion" and f"v_brazo_{lado}" in vectores and f"v_antebrazo_{lado}" in vectores:
            valor = angulo_entre(vectores[f"v_brazo_{lado}"].px, vectores[f"v_antebrazo_{lado}"].px)
            indices = (hombro, codo, muneca)
        elif medida == "rodilla_flexion" and f"v_muslo_{lado}" in vectores and f"v_pierna_{lado}" in vectores:
            valor = angulo_entre(vectores[f"v_muslo_{lado}"].px, vectores[f"v_pierna_{lado}"].px)
            indices = (cadera, rodilla, tobillo)
        else:
            return None
        if valor is None:
            return None
        confianza = min(mapa[i].visibility for i in indices)
        return nueva(medida, lado, valor, "frente", "respaldo 2D de frente: angulo_entre", confianza, ["posible_escorzo"])

    def desde_3d(medida: str, lado: str | None) -> MedicionAngulo | None:
        if cuerpo is None:
            return None
        c, t = cuerpo, cuerpo.tronco
        assert t is not None and c.lateral is not None and c.frontal_normal is not None
        abajo: Vec3 = (-t[0], -t[1], -t[2])
        valor: float | None = None
        indices: tuple[int, ...] = ()
        magnitud = False
        if medida == "tronco_flexion":
            valor, indices, magnitud = c.angulo_en_plano(t, ARRIBA, c.lateral), (11, 12, 23, 24), True
        elif medida == "tronco_inclinacion_lateral":
            valor, indices = c.angulo_en_plano(t, ARRIBA, c.frontal_normal), (11, 12, 23, 24)
        elif medida == "tronco_torsion":
            hombros = _resta(_punto_3d(c.mapa, 12), _punto_3d(c.mapa, 11)) if 11 in c.mapa and 12 in c.mapa else None  # type: ignore[arg-type]
            caderas = _resta(_punto_3d(c.mapa, 24), _punto_3d(c.mapa, 23))  # type: ignore[arg-type]
            if hombros is not None:
                bruto = c.angulo_en_plano(hombros, caderas, ARRIBA)
                valor, indices = (None if bruto is None else min(bruto, 180.0 - bruto)), (11, 12, 23, 24)
        elif medida == "cuello_flexion":
            orejas, hombros = _punto_3d(c.mapa, 7, 8), _punto_3d(c.mapa, 11, 12)
            if orejas and hombros:
                valor, indices, magnitud = c.angulo_en_plano(_resta(orejas, hombros), t, c.lateral), (7, 8, 11, 12), True
        elif medida == "cuello_inclinacion_rotacion":
            nariz, hombros = _punto_3d(c.mapa, 0), _punto_3d(c.mapa, 11, 12)
            if nariz and hombros:
                valor, indices = c.angulo_en_plano(_resta(nariz, hombros), t, c.frontal_normal), (0, 11, 12)
        elif lado in ("L", "R"):
            _, hombro, codo, muneca, cadera, rodilla, tobillo = next(x for x in LADOS if x[0] == lado)
            p = lambda *i: _punto_3d(c.mapa, *i)  # noqa: E731
            if medida in ("brazo_flexion", "brazo_abduccion") and p(hombro) and p(codo):
                brazo = _resta(p(codo), p(hombro))  # type: ignore[arg-type]
                plano = c.lateral if medida == "brazo_flexion" else c.frontal_normal
                valor, indices, magnitud = c.angulo_en_plano(brazo, abajo, plano), (hombro, codo), medida == "brazo_flexion"
            elif medida == "codo_flexion" and p(hombro) and p(codo) and p(muneca):
                valor, indices = angulo_entre(_resta(p(codo), p(hombro)), _resta(p(muneca), p(codo))), (hombro, codo, muneca)  # type: ignore[arg-type]
            elif medida == "rodilla_flexion" and p(cadera) and p(rodilla) and p(tobillo):
                valor, indices = angulo_entre(_resta(p(rodilla), p(cadera)), _resta(p(tobillo), p(rodilla))), (cadera, rodilla, tobillo)  # type: ignore[arg-type]
        if valor is None:
            return None
        extra = ["baja_confianza_metodo"] if magnitud else []
        metodo = f"respaldo 3D (pose de {c.vista})" + (": solo magnitud, se asume flexión" if magnitud else "")
        # La torsión es medida primaria de la aérea: si el caso tiene foto cenital,
        # etiquétala ahí (aunque la pose cenital haya fallado) para no saturar el costado.
        vista_etiqueta = "aerea" if medida == "tronco_torsion" and "aerea" in vistas else c.vista
        return nueva(medida, lado, valor, vista_etiqueta, metodo, c.confianza(*indices), extra)

    def apoyo() -> MedicionAngulo | None:
        # Altura de los tobillos en la pose 3D (metros, eje y vertical de la cámara). No se usa la foto de
        # costado en 2D: por perspectiva, el pie más alejado de la cámara aparece más arriba aunque esté apoyado.
        if cuerpo is not None:
            m = cuerpo.mapa
            lados = [(23, 25, 27), (24, 26, 28)]
            if all(i in m for i in (27, 28)) and any(all(i in m for i in t) for t in lados):
                cadera, rodilla, tobillo = next(t for t in lados if all(i in m for i in t))
                largo = abs(m[cadera].y - m[rodilla].y) + abs(m[rodilla].y - m[tobillo].y)
                if largo > 1e-6:
                    valor = float(abs(m[27].y - m[28].y) > config.angulos.umbral_pie_levantado * largo)
                    return nueva("apoyo_piernas_unilateral", None, valor, cuerpo.vista,
                                 "respaldo 3D (pose de " + cuerpo.vista + "): altura de tobillos", cuerpo.confianza(27, 28), [])
        if contexto.get("postura") == "sentado":
            return MedicionAngulo("apoyo_piernas_unilateral", None, 0.0, "contexto", "respaldo: postura sentado declarada", None,
                                  banderas=["vista_respaldo"])
        return None

    respaldos: dict[str, list[Callable[[str, str | None], MedicionAngulo | None]]] = {
        "codo_flexion": [lambda m, l: frente_2d(m, l) if l else None, desde_3d],
        "rodilla_flexion": [lambda m, l: frente_2d(m, l) if l else None, desde_3d],
        "apoyo_piernas_unilateral": [lambda m, l: apoyo()],
    }
    for medida, lado in REQUERIDAS:
        indice = posicion.get((medida, lado))
        if indice is not None and resultado[indice].valor_deg is not None:
            continue
        for intento in respaldos.get(medida, [desde_3d]):
            medicion = intento(medida, lado)
            if medicion is not None:
                if indice is None:
                    resultado.append(medicion)
                    posicion[(medida, lado)] = len(resultado) - 1
                else:
                    # Conserva «aerea» como vista de la torsión para que la foto cenital
                    # reciba la etiqueta aunque el valor venga de pose 3D de otra cámara.
                    if medida == "tronco_torsion" and resultado[indice].vista == "aerea":
                        medicion = replace(medicion, vista="aerea")
                    resultado[indice] = medicion
                break
    return resultado
