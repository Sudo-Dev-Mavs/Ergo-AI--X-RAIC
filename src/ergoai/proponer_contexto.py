"""Propone valores de contexto / ajustes REBA a partir de la pose (editable por el especialista).

No usa nube ni LLM: solo landmarks de MediaPipe ya disponibles en el equipo.
Lo que una foto estática no puede saber (estática >1 min, repetición, golpe, kg exactos)
se deja apagado y se documenta en ``motivos``.
"""

from __future__ import annotations

from typing import Any

from .angulos import MedicionAngulo, _mapa, _medio, _punto, medir_vista
from .config import Configuracion
from .modelos import VistaPose

Lados = dict[str, bool]


def _lado_vacio() -> Lados:
    return {"izquierdo": False, "derecho": False}


def _medicion(medidas: list[MedicionAngulo], nombre: str, lado: str | None = None) -> MedicionAngulo | None:
    for m in medidas:
        if m.medida != nombre:
            continue
        if lado is None or m.lado == lado:
            return m
    return None


def _hombro_elevado(vista: VistaPose, vis_min: float, lado: str) -> tuple[bool, str | None]:
    """Hombro cerca de la oreja (elevado) respecto a la altura del tronco."""

    if not vista.detectado:
        return False, None
    mapa = _mapa(vista.landmarks, vis_min)
    hombro_i, oreja_i = (11, 7) if lado == "L" else (12, 8)
    hombro, oreja = _punto(mapa, hombro_i), _punto(mapa, oreja_i)
    cadera = _medio(mapa, (23, 24))
    if hombro is None or oreja is None or cadera is None:
        return False, None
    alto_tronco = abs(hombro[1] - cadera[1])
    if alto_tronco < 1:
        return False, None
    # En imagen, y crece hacia abajo: oreja suele estar por encima (menor y) del hombro.
    separacion = abs(hombro[1] - oreja[1]) / alto_tronco
    if separacion <= 0.18:
        etiqueta = "izquierdo" if lado == "L" else "derecho"
        return True, f"Hombro {etiqueta}: muy cerca de la oreja en la foto (posible elevación)."
    return False, None


def _postura_desde_rodillas(medidas: list[MedicionAngulo]) -> tuple[str | None, str | None]:
    rodillas = [
        m.valor_deg for m in medidas
        if m.medida == "rodilla_flexion" and m.valor_deg is not None
    ]
    if not rodillas:
        return None, None
    media = sum(rodillas) / len(rodillas)
    if media >= 55:
        return "sentado", f"Rodillas ~{media:.0f}°: sugiere postura sentada."
    if media <= 25:
        return "de_pie", f"Rodillas ~{media:.0f}°: sugiere postura de pie."
    return None, f"Rodillas ~{media:.0f}°: ambigua (ni claramente de pie ni sentado)."


def _muneca_sospechosa(medidas: list[MedicionAngulo], umbral: float, lado: str) -> tuple[bool, str | None]:
    """La foto mide flexión/extensión, no desviación radial/cubital: solo una sospecha editable."""

    m = _medicion(medidas, "muneca_flexion_extension", lado)
    if m is None or m.valor_deg is None:
        return False, None
    if m.valor_deg >= umbral:
        etiqueta = "izquierdo" if lado == "L" else "derecho"
        return True, (
            f"Muñeca {etiqueta}: flexión/extensión {m.valor_deg:.0f}° (≥{umbral:.0f}°). "
            "Revisa en piso si también está desviada o torcida."
        )
    return False, None


def _brazo_alto(medidas: list[MedicionAngulo], umbral_alto: float, lado: str) -> str | None:
    m = _medicion(medidas, "brazo_flexion", lado)
    if m is None or m.valor_deg is None:
        return None
    if m.valor_deg >= umbral_alto:
        etiqueta = "izquierdo" if lado == "L" else "derecho"
        return f"Brazo {etiqueta} ~{m.valor_deg:.0f}°: brazo alto (no equivale a «brazo apoyado»)."
    return None


def proponer_desde_vistas(
    vistas: dict[str, VistaPose],
    configuracion: Configuracion,
    contexto_parcial: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Devuelve sugerencias listas para rellenar el formulario de Nueva evaluación."""

    contexto_parcial = contexto_parcial or {}
    medidas: list[MedicionAngulo] = []
    for vista in vistas.values():
        if not vista.detectado:
            continue
        _, meds, _ = medir_vista(vista, configuracion, contexto_parcial)
        medidas.extend(meds)

    motivos: list[str] = []
    advertencias: list[str] = [
        "Propuesta automática desde la pose (MediaPipe local). El especialista debe confirmarla.",
        "Una foto no prueba estática >1 min, repetición, base inestable ni fuerza de golpe: esas quedan apagadas.",
        "La carga en kg y el agarre no se estiman con fiabilidad desde la foto: no se cambian.",
    ]

    detectadas = [n for n, v in vistas.items() if v.detectado]
    if not detectadas:
        return {
            "ok": False,
            "motivos": ["No se detectó pose en ninguna vista. Revisa las fotos o captura de nuevo."],
            "advertencias": advertencias,
            "sugerencias": {},
        }

    motivos.append(f"Pose detectada en: {', '.join(detectadas)}.")

    postura, motivo_postura = _postura_desde_rodillas(medidas)
    if motivo_postura:
        motivos.append(motivo_postura)

    hombro = _lado_vacio()
    for letra, clave in (("L", "izquierdo"), ("R", "derecho")):
        # Preferir frente; si no, costado.
        for nombre in ("frente", "costado", "aerea"):
            vista = vistas.get(nombre)
            if vista is None:
                continue
            ok, motivo = _hombro_elevado(vista, configuracion.pose.vis_min, letra)
            if ok:
                hombro[clave] = True
                if motivo:
                    motivos.append(motivo)
                break

    muneca = _lado_vacio()
    umbral_m = float(configuracion.reba.muneca.flexion)
    for letra, clave in (("L", "izquierdo"), ("R", "derecho")):
        ok, motivo = _muneca_sospechosa(medidas, umbral_m, letra)
        if ok:
            muneca[clave] = True
            if motivo:
                motivos.append(motivo)

    umbral_brazo = float(configuracion.reba.brazo.alto)
    for letra in ("L", "R"):
        nota = _brazo_alto(medidas, umbral_brazo, letra)
        if nota:
            motivos.append(nota)

    # Tipo de trabajo: solo si el consultor ya puso carga; no inventamos kg.
    trabajo: str | None = None
    carga = contexto_parcial.get("carga_kg")
    try:
        carga_f = float(carga) if carga is not None else None
    except (TypeError, ValueError):
        carga_f = None
    if carga_f is not None:
        if carga_f >= 10:
            trabajo = "pesado"
            motivos.append(f"Carga declarada {carga_f:g} kg → se sugiere trabajo pesado.")
        elif carga_f > 0:
            trabajo = "ligero"
            motivos.append(f"Carga declarada {carga_f:g} kg → se sugiere trabajo ligero.")
        else:
            trabajo = "precision"
            motivos.append("Sin carga (0 kg) → se sugiere trabajo de precisión/ligero de manos.")

    sugerencias: dict[str, Any] = {
        "postura": postura,
        "tipo_trabajo": trabajo,
        # No tocamos tipo_tarea / agarre / carga_kg (declarativos o no fiables en foto).
        "fuerza_brusca": False,
        "actividad": {
            "estatica_mas_1min": False,
            "repetitiva_mas_4_por_min": False,
            "cambios_bruscos_o_base_inestable": False,
        },
        "hombro_elevado": hombro,
        "brazo_apoyado": _lado_vacio(),  # no inferible con foto estática
        "muneca_desviada_o_torcida": muneca,
    }

    return {
        "ok": True,
        "motivos": motivos,
        "advertencias": advertencias,
        "sugerencias": sugerencias,
        "vistas_detectadas": detectadas,
    }


def _vis(mapa: dict[int, Any], indice: int) -> float:
    p = mapa.get(indice)
    return float(p.visibility) if p is not None else 0.0


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def puntuaciones_vista(pose: VistaPose, nombre_archivo: str = "") -> dict[str, float]:
    """Puntúa costado / frente / aérea (0–1+) según pose y nombre de archivo."""

    scores = {"costado": 0.15, "frente": 0.15, "aerea": 0.1}
    nombre = (nombre_archivo or "").lower()
    if any(t in nombre for t in ("costado", "lado", "side", "perfil", "lateral")):
        scores["costado"] += 0.55
    if any(t in nombre for t in ("frente", "front", "frontal")):
        scores["frente"] += 0.55
    if any(t in nombre for t in ("aerea", "aérea", "aerial", "overhead", "cenital", "top", "arriba")):
        scores["aerea"] += 0.55

    if not pose.detectado or not pose.landmarks:
        return scores

    # Umbral bajo: solo para clasificar la cámara/ángulo, no para REBA.
    mapa = {p.indice: p for p in pose.landmarks if p.visibility >= 0.25}
    h_l, h_r = _punto(mapa, 11), _punto(mapa, 12)
    c_l, c_r = _punto(mapa, 23), _punto(mapa, 24)
    nariz = _punto(mapa, 0)
    vis_hl, vis_hr = _vis(mapa, 11), _vis(mapa, 12)

    if h_l and h_r:
        ancho = _dist(h_l, h_r)
        asimetria = abs(vis_hl - vis_hr)
        scores["costado"] += min(0.45, asimetria * 0.7)
        scores["frente"] += min(0.45, (1.0 - asimetria) * 0.45)
        if nariz and ancho > 1:
            medio_x = (h_l[0] + h_r[0]) / 2
            centrado = 1.0 - min(1.0, abs(nariz[0] - medio_x) / (ancho * 0.6))
            scores["frente"] += centrado * 0.35
            scores["costado"] += (1.0 - centrado) * 0.25

        caderas = _medio(mapa, (23, 24)) if c_l and c_r else None
        hombros = ((h_l[0] + h_r[0]) / 2, (h_l[1] + h_r[1]) / 2)
        if caderas and ancho > 1:
            alto = _dist(hombros, caderas)
            ratio = alto / ancho
            # Cenital: tronco “aplastado” (poco alto vs ancho de hombros).
            if ratio < 0.95:
                scores["aerea"] += min(0.55, (0.95 - ratio) * 1.2)
            if ratio > 1.15:
                scores["aerea"] -= 0.15
                scores["costado"] += 0.08
                scores["frente"] += 0.08

    return scores


def clasificar_y_asignar(
    candidatas: list[tuple[str, VistaPose, str]],
) -> dict[str, Any]:
    """Asigna cada imagen a una vista distinta maximizando la puntuación.

    ``candidatas``: lista de (id, pose, nombre_archivo).
    """

    if not candidatas:
        return {"ok": False, "asignaciones": [], "motivos": ["No hay imágenes para clasificar."]}

    vistas = ("costado", "frente", "aerea")
    tabla = []
    for cid, pose, nombre in candidatas:
        pts = puntuaciones_vista(pose, nombre)
        tabla.append({"id": cid, "nombre": nombre, "scores": pts, "detectado": pose.detectado})

    # Emparejamiento voraz por mejor score libre.
    usadas_img: set[str] = set()
    usadas_vista: set[str] = set()
    pares: list[tuple[str, str, float]] = []
    opciones = [
        (fila["id"], vista, fila["scores"][vista])
        for fila in tabla
        for vista in vistas
    ]
    opciones.sort(key=lambda t: -t[2])
    for cid, vista, score in opciones:
        if cid in usadas_img or vista in usadas_vista:
            continue
        usadas_img.add(cid)
        usadas_vista.add(vista)
        pares.append((cid, vista, score))
        if len(pares) >= min(len(candidatas), 3):
            break

    # Imágenes sobrantes → primera vista libre (por si hay más de 3 no aplica; si hay <3 ok).
    libres = [v for v in vistas if v not in usadas_vista]
    for fila in tabla:
        if fila["id"] in usadas_img:
            continue
        if not libres:
            break
        vista = libres.pop(0)
        pares.append((fila["id"], vista, fila["scores"][vista]))
        usadas_img.add(fila["id"])

    asignaciones = []
    motivos = []
    for cid, vista, score in pares:
        fila = next(f for f in tabla if f["id"] == cid)
        asignaciones.append({
            "id": cid,
            "vista": vista,
            "confianza": round(float(score), 3),
            "nombre": fila["nombre"],
            "detectado": fila["detectado"],
        })
        etiqueta = "Aérea" if vista == "aerea" else vista.capitalize()
        motivos.append(f"{fila['nombre'] or cid} → {etiqueta} (confianza {score:.2f})")

    return {"ok": True, "asignaciones": asignaciones, "motivos": motivos}
