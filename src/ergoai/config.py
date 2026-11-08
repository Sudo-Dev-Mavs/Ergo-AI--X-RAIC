"""Carga y validación de la configuración versionada de ErgoAI."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfiguracionBase(BaseModel):
    """Modelo estricto para detectar claves mal escritas en la configuración."""

    model_config = ConfigDict(extra="forbid")


class PoseConfig(ConfiguracionBase):
    """Parámetros del detector de pose."""

    modelo: str
    num_poses: int = Field(ge=1)
    min_pose_detection_confidence: float = Field(ge=0, le=1)
    min_pose_presence_confidence: float = Field(ge=0, le=1)
    vis_min: float = Field(ge=0, le=1)
    vis_confiable: float = Field(ge=0, le=1)


class AngulosConfig(ConfiguracionBase):
    cuello_offset_neutro_deg: float
    umbral_discrepancia_3d_deg: float = Field(ge=0)
    umbral_pie_levantado: float = Field(ge=0)
    margen_umbral_deg: float = Field(ge=0)


class DosLimites(ConfiguracionBase):
    leve: float
    moderado: float


class LimiteSimple(ConfiguracionBase):
    flexion: float


class BrazoLimites(ConfiguracionBase):
    neutro: float
    medio: float
    alto: float


class RangoLimites(ConfiguracionBase):
    min: float
    max: float


class RodillaLimites(ConfiguracionBase):
    leve: float
    alta: float


class CargaLimites(ConfiguracionBase):
    baja: float
    alta: float


class RebaConfig(ConfiguracionBase):
    limite_superior_inclusivo: bool
    tolerancia_neutro_deg: float = Field(ge=0)
    tronco: DosLimites
    cuello: LimiteSimple
    brazo: BrazoLimites
    antebrazo: RangoLimites
    muneca: LimiteSimple
    rodilla: RodillaLimites
    carga_kg: CargaLimites
    umbral_torsion_tronco_deg: float = Field(ge=0)
    umbral_inclinacion_lateral_tronco_deg: float = Field(ge=0)
    umbral_cuello_lateral_rotacion_deg: float = Field(ge=0)
    umbral_abduccion_brazo_deg: float = Field(ge=0)
    lado_reportado: Literal["peor", "izquierdo", "derecho"]


class JabilConfig(ConfiguracionBase):
    angulo_apertura: float | None


class RulaMunecaConfig(ConfiguracionBase):
    neutro: float
    flexion: float


class RulaCuelloConfig(ConfiguracionBase):
    neutro: float
    medio: float


class RulaCargaConfig(ConfiguracionBase):
    baja: float
    alta: float


class RulaTroncoConfig(ConfiguracionBase):
    neutro: float
    leve: float
    moderado: float


class RulaConfig(ConfiguracionBase):
    limite_superior_inclusivo: bool
    brazo: BrazoLimites
    antebrazo: RangoLimites
    muneca: RulaMunecaConfig
    cuello: RulaCuelloConfig
    tronco: RulaTroncoConfig
    carga_kg: RulaCargaConfig


class EawsAccionesConfig(ConfiguracionBase):
    baja: float
    alta: float


class EawsConfig(ConfiguracionBase):
    tronco: DosLimites
    torsion_deg: float
    carga_kg: CargaLimites
    acciones: EawsAccionesConfig


class ManoConfig(ConfiguracionBase):
    modelo: str


class RecomendacionesConfig(ConfiguracionBase):
    """Valores dimensionales trazables usados por las recomendaciones."""

    limite_carga_jabil_kg: float = Field(ge=0)
    altura_precision_min_cm: float = Field(ge=0)
    altura_precision_max_cm: float = Field(ge=0)
    altura_ligero_min_cm: float = Field(ge=0)
    altura_ligero_max_cm: float = Field(ge=0)
    altura_pesado_min_cm: float = Field(ge=0)
    altura_pesado_max_cm: float = Field(ge=0)
    altura_rack_max_m: float = Field(ge=0)
    altura_carro_max_m: float = Field(ge=0)
    espacio_libre_min_cm: float = Field(ge=0)
    altura_conveyor_min_m: float = Field(ge=0)
    altura_conveyor_max_m: float = Field(ge=0)
    conveyor_gravedad_max_m: float = Field(ge=0)
    ayuda_visual_min_mm: float = Field(ge=0)
    ayuda_visual_max_mm: float = Field(ge=0)
    iluminacion_ensamble_lux: float = Field(ge=0)
    iluminacion_precision_lux: float = Field(ge=0)
    espacio_pies_min_cm: float = Field(ge=0)
    reposapies_min_cm: float = Field(ge=0)
    reposapies_max_cm: float = Field(ge=0)


class Configuracion(ConfiguracionBase):
    """Configuración completa y validada del módulo."""

    pose: PoseConfig
    angulos: AngulosConfig
    reba: RebaConfig
    jabil: JabilConfig
    rula: RulaConfig
    eaws: EawsConfig
    mano: ManoConfig
    recomendaciones: RecomendacionesConfig


def cargar_configuracion(ruta: str | Path) -> Configuracion:
    """Carga el YAML y explica claramente cualquier problema de esquema."""

    ruta_config = Path(ruta)
    try:
        with ruta_config.open(encoding="utf-8") as archivo:
            contenido = yaml.safe_load(archivo)
    except FileNotFoundError as exc:
        raise ValueError(f"No existe el archivo de configuración: {ruta_config}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML inválido en {ruta_config}: {exc}") from exc
    if not isinstance(contenido, dict):
        raise ValueError(f"La configuración {ruta_config} debe contener un objeto YAML.")
    try:
        return Configuracion.model_validate(contenido)
    except ValidationError as exc:
        raise ValueError(f"Configuración inválida en {ruta_config}:\n{exc}") from exc
