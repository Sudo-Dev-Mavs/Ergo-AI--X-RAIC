"""Textos y colores de la interfaz. No calcula puntajes."""

from __future__ import annotations

from typing import Any, Iterable

VISTAS = ("frente", "costado", "aerea")
ETIQUETAS_VISTA = {"frente": "Frente", "costado": "Costado", "aerea": "Aérea"}
AYUDA_VISTA = {
    "frente": "Arrastra, recorta o zoom · frente, sin rostro",
    "costado": "Arrastra, recorta o zoom · de lado",
    "aerea": "Desde arriba: recorta centrando torso/hombros",
}
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ETIQUETAS_POSTURA = {"de_pie": "De pie", "sentado": "Sentado", "alternada": "Alternada"}
ETIQUETAS_AGARRE = {
    "bueno": "Bueno",
    "regular": "Regular",
    "malo": "Malo",
    "inaceptable": "Inaceptable",
}
ETIQUETAS_ORIENTACION = {"auto": "Automático", "derecha": "Derecha", "izquierda": "Izquierda"}
ETIQUETAS_SEGMENTO = {
    "tronco_flexion": "Tronco",
    "tronco_torsion": "Torsión de tronco",
    "tronco_inclinacion_lateral": "Inclinación lateral",
    "cuello_flexion": "Cuello",
    "cuello_inclinacion_rotacion": "Cuello (giro/lateral)",
    "rodilla_flexion": "Rodilla",
    "apoyo_piernas_unilateral": "Apoyo en una pierna",
    "brazo_flexion": "Brazo",
    "brazo_abduccion": "Abducción de brazo",
    "codo_flexion": "Antebrazo",
    "muneca_flexion_extension": "Muñeca",
    "alcance_horizontal": "Alcance (aérea)",
    "alcance_asimetria": "Asimetría de alcance",
}
COLORES_RIESGO = {
    "Inapreciable": {"fg": "#0F6B3C", "bg": "#D9F2E4", "barra": "#1B7A4E"},
    "Bajo": {"fg": "#0F6B3C", "bg": "#D9F2E4", "barra": "#1B7A4E"},
    "Medio": {"fg": "#9A3B00", "bg": "#FFE6CC", "barra": "#E65100"},
    "Alto": {"fg": "#8E1B1B", "bg": "#F8D4D4", "barra": "#C62828"},
    "Muy alto": {"fg": "#4A148C", "bg": "#EBD6F5", "barra": "#6A1B9A"},
    "Pendiente": {"fg": "#3D4A57", "bg": "#E6EAEF", "barra": "#5B6775"},
}


def clave_desde_etiqueta(mapa: dict[str, str], etiqueta: str) -> str:
    """Traduce la etiqueta visible de la interfaz al valor del motor."""

    invertido = {valor: clave for clave, valor in mapa.items()}
    if etiqueta in invertido:
        return invertido[etiqueta]
    if etiqueta in mapa:
        return etiqueta
    raise ValueError(f"Valor no reconocido: {etiqueta}")


def color_riesgo(nombre: str | None) -> dict[str, str]:
    """Devuelve la paleta de un nivel REBA. No altera el puntaje."""

    return COLORES_RIESGO.get(nombre or "Pendiente", COLORES_RIESGO["Pendiente"])


def etiqueta_segmento(medida: str) -> str:
    """Nombre corto de un segmento para la tabla de ángulos."""

    return ETIQUETAS_SEGMENTO.get(medida, medida.replace("_", " "))


def formatear_angulo(valor: float | None) -> str:
    """Ángulo en grados, o raya si no se pudo medir."""

    return "—" if valor is None else f"{valor:.1f}°"


def formatear_confianza(valor: float | None, banderas: Iterable[str] | None = None) -> str:
    """Confianza legible; marca revisión si hay banderas."""

    marcas = [bandera for bandera in (banderas or []) if bandera]
    if valor is None:
        texto = "Sin dato"
    elif 0 <= valor <= 1:
        texto = f"{valor:.0%}"
    else:
        texto = f"{valor:.2f}"
    if marcas:
        return f"{texto} · revisar"
    return texto


def aviso_vistas_faltantes(vistas_presentes: Iterable[str]) -> str | None:
    """Avisa vistas ausentes. No inventa la foto ni baja el puntaje aquí."""

    presentes = {vista for vista in vistas_presentes if vista in VISTAS}
    faltan = [ETIQUETAS_VISTA[vista] for vista in VISTAS if vista not in presentes]
    if not faltan:
        return None
    if len(faltan) == 3:
        return "Faltan las tres vistas. Se necesita al menos una fotografía para evaluar."
    lista = " y ".join(faltan) if len(faltan) == 1 else f"{', '.join(faltan[:-1])} y {faltan[-1]}"
    return f"Falta vista de {lista}. Se avisa y baja la confianza; no se inventa esa pose."


def filas_angulos(angulos: list[dict[str, Any]]) -> list[tuple[str, str, str, str, str, str]]:
    """Prepara filas de la tabla: segmento, lado, ángulo, rango, vista, confianza."""

    filas: list[tuple[str, str, str, str, str, str]] = []
    for angulo in angulos:
        lado = angulo.get("lado") or "—"
        rango = angulo.get("banda_reba")
        filas.append(
            (
                etiqueta_segmento(str(angulo.get("medida", ""))),
                str(lado),
                formatear_angulo(angulo.get("valor_deg")),
                "—" if rango is None else str(rango),
                ETIQUETAS_VISTA.get(str(angulo.get("vista") or ""), str(angulo.get("vista") or "—")),
                formatear_confianza(angulo.get("confianza"), angulo.get("banderas") or []),
            )
        )
    return filas


def texto_tiempo(segundos: float) -> str:
    """Tiempo de evaluación para R8, en español."""

    if segundos < 10:
        return f"{segundos:.1f} s"
    return f"{segundos:.0f} s"
