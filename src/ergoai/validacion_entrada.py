"""Filtros de entrada: imagen usable, carga creíble y ángulos sensatos.

Cada rechazo lanza ``ValueError`` con un motivo en español listo para mostrar al operador.
Los umbrales viven aquí (y en ``config/umbrales.yaml`` → ``entrada``) para poder afinarlos.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .modelos import PoseResult

# --- Imagen -----------------------------------------------------------------
MIN_LADO_PX = 240
LUMINANCIA_MIN = 12.0
LUMINANCIA_MAX = 248.0
CONTRASTE_MIN = 6.0  # desviación estándar del gris
NITIDEZ_MIN = 12.0  # varianza del Laplaciano

# --- Carga (kg) · manejo manual en estación ---------------------------------
CARGA_KG_MIN = 0.0
CARGA_KG_MAX = 100.0  # por encima no es creíble como carga manual en este flujo
CARGA_KG_AVISO_JABIL = 14.0

# --- Ángulos (°) ------------------------------------------------------------
ANGULO_MIN = -5.0
ANGULO_MAX = 185.0
MEDIDAS_BINARIAS = frozenset({"apoyo_piernas_unilateral"})


def _gris(pixeles: np.ndarray) -> np.ndarray:
    if pixeles.ndim == 2:
        return pixeles.astype(np.float32)
    return cv2.cvtColor(pixeles, cv2.COLOR_RGB2GRAY).astype(np.float32)


def validar_calidad_imagen(pixeles: np.ndarray, etiqueta: str = "La foto") -> None:
    """Rechaza negras, blancas planas, muy chicas o demasiado borrosas."""

    if pixeles.ndim not in (2, 3) or pixeles.size == 0:
        raise ValueError(f"{etiqueta} no se pudo interpretar como imagen.")
    alto, ancho = pixeles.shape[:2]
    if min(alto, ancho) < MIN_LADO_PX:
        raise ValueError(
            f"{etiqueta} es demasiado pequeña ({ancho}×{alto} px). "
            f"Se necesita al menos {MIN_LADO_PX} px por lado para medir la postura."
        )

    gris = _gris(pixeles)
    media = float(np.mean(gris))
    contraste = float(np.std(gris))
    if media < LUMINANCIA_MIN and contraste < CONTRASTE_MIN:
        raise ValueError(
            f"{etiqueta} parece casi negra o sin contenido (luminancia {media:.0f}/255). "
            "Usa una foto iluminada donde se vea a la persona."
        )
    if media > LUMINANCIA_MAX and contraste < CONTRASTE_MIN:
        raise ValueError(
            f"{etiqueta} parece casi blanca o quemada (luminancia {media:.0f}/255). "
            "Baja la exposición o vuelve a capturar."
        )
    if contraste < CONTRASTE_MIN:
        raise ValueError(
            f"{etiqueta} no tiene detalle suficiente (contraste {contraste:.1f}). "
            "Puede ser un color plano, un archivo corrupto o una captura fallida."
        )

    nitidez = float(cv2.Laplacian(gris, cv2.CV_32F).var())
    if nitidez < NITIDEZ_MIN:
        raise ValueError(
            f"{etiqueta} está demasiado borrosa (nitidez {nitidez:.1f}). "
            "Acerca la cámara, enfoca o usa mejor iluminación."
        )


def validar_persona_en_pose(
    personas: list[PoseResult],
    etiqueta: str = "La foto",
    *,
    requerida: bool = True,
) -> None:
    """Exige al menos una pose detectada (persona en la imagen).

    En vista aérea MediaPipe suele fallar por el foreshortening: pasar ``requerida=False``
    para no bloquear la foto (sigue valiendo la calidad de imagen).
    """

    if not requerida:
        return
    if not personas:
        raise ValueError(
            f"{etiqueta} no muestra una persona detectable. "
            "Centra al operador de cuerpo (o torso) completo, con buena iluminación, y vuelve a intentar."
        )


def persona_requerida_en_vista(vista: str) -> bool:
    """Costado/frente exigen pose; aérea solo calidad (MediaPipe casi no ve desde arriba)."""

    return vista.strip().lower() != "aerea"


def validar_carga_kg(valor: Any) -> float:
    """Normaliza y valida la carga declarada en kg."""

    try:
        carga = float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("La carga debe ser un número en kilogramos (ej. 0, 5 o 12.5).") from exc
    if not np.isfinite(carga):
        raise ValueError("La carga no es un número válido.")
    if carga < CARGA_KG_MIN:
        raise ValueError(f"La carga no puede ser negativa ({carga:g} kg).")
    if carga > CARGA_KG_MAX:
        raise ValueError(
            f"La carga {carga:g} kg no es creíble para manejo manual en esta evaluación "
            f"(máximo admitido: {CARGA_KG_MAX:g} kg). Si es carga asistida, declara el peso "
            "que sostiene la persona o 0 kg si no hay carga en manos."
        )
    return carga


def validar_angulo_override(clave: str, valor: float | None) -> None:
    """Valida un override del especialista; ``None`` = volver a la medición automática."""

    if valor is None:
        return
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        raise ValueError(f"{clave}: el valor debe ser numérico.")
    if not np.isfinite(float(valor)):
        raise ValueError(f"{clave}: el valor no es un número finito.")

    medida = clave.rsplit("_", 1)[0] if clave.endswith(("_L", "_R")) else clave
    # apoyo_piernas_unilateral_L → apoyo_piernas_unilateral
    for binaria in MEDIDAS_BINARIAS:
        if clave == binaria or clave.startswith(f"{binaria}_"):
            if float(valor) not in (0.0, 1.0):
                raise ValueError(
                    f"{clave}: solo admite 0 (No) o 1 (Sí); recibí {valor}."
                )
            return

    angulo = float(valor)
    if angulo < ANGULO_MIN or angulo > ANGULO_MAX:
        raise ValueError(
            f"{clave}: {angulo:g}° está fuera de rango sensato ({ANGULO_MIN:g}° a {ANGULO_MAX:g}°). "
            "Revisa si es el ángulo correcto medido en piso."
        )


def validar_overrides(overrides: dict[str, float | None]) -> None:
    for clave, valor in overrides.items():
        validar_angulo_override(clave, valor)


def validar_contexto_parcial(datos: dict[str, Any]) -> dict[str, Any]:
    """Valida campos de contexto que el operador declara (hoy: carga_kg)."""

    if "carga_kg" in datos and datos["carga_kg"] is not None and str(datos["carga_kg"]).strip() != "":
        datos = {**datos, "carga_kg": validar_carga_kg(datos["carga_kg"])}
    return datos
