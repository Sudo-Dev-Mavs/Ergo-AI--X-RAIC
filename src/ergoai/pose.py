"""Backend intercambiable de detección de pose basado en MediaPipe Tasks."""

from pathlib import Path
from typing import Protocol

import numpy as np

from .config import PoseConfig
from .landmarks import NOMBRES_LANDMARKS
from .modelos import Landmark, PoseResult, WorldLandmark


class PoseBackend(Protocol):
    """Contrato mínimo para reemplazar el detector sin afectar el pipeline."""

    def detect(self, image: np.ndarray) -> list[PoseResult]:
        """Devuelve todas las personas detectadas en la imagen RGB."""


class MediaPipeBackend:
    """Implementación local con `vision.PoseLandmarker` de MediaPipe Tasks."""

    def __init__(self, configuracion: PoseConfig, raiz_proyecto: str | Path = ".") -> None:
        self.configuracion = configuracion
        self.ruta_modelo = Path(raiz_proyecto) / configuracion.modelo

    def detect(
        self,
        image: np.ndarray,
        *,
        min_pose_detection_confidence: float | None = None,
        min_pose_presence_confidence: float | None = None,
    ) -> list[PoseResult]:
        """Detecta poses, conservando coordenadas 2D en píxeles y mundo 3D."""

        if not self.ruta_modelo.is_file():
            raise FileNotFoundError(
                f"No existe el modelo MediaPipe: {self.ruta_modelo}. "
                "Ejecute `python scripts/descargar_modelo.py`."
            )
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError as exc:
            raise RuntimeError("MediaPipe no está instalado. Instale las dependencias con `uv sync`.") from exc

        opciones = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(self.ruta_modelo)),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=self.configuracion.num_poses,
            min_pose_detection_confidence=(
                self.configuracion.min_pose_detection_confidence
                if min_pose_detection_confidence is None
                else min_pose_detection_confidence
            ),
            min_pose_presence_confidence=(
                self.configuracion.min_pose_presence_confidence
                if min_pose_presence_confidence is None
                else min_pose_presence_confidence
            ),
            output_segmentation_masks=False,
        )
        alto, ancho = image.shape[:2]
        with vision.PoseLandmarker.create_from_options(opciones) as detector:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
            resultado = detector.detect(mp_image)

        personas: list[PoseResult] = []
        mundos = resultado.pose_world_landmarks or []
        for indice_persona, puntos in enumerate(resultado.pose_landmarks or []):
            landmarks = [
                Landmark(
                    indice=indice,
                    nombre=NOMBRES_LANDMARKS.get(indice, f"landmark_{indice}"),
                    x_px=float(punto.x * ancho), y_px=float(punto.y * alto), z=float(punto.z),
                    visibility=float(getattr(punto, "visibility", 0.0)),
                    presence=float(getattr(punto, "presence", 0.0)),
                )
                for indice, punto in enumerate(puntos)
            ]
            puntos_mundo = mundos[indice_persona] if indice_persona < len(mundos) else []
            world_landmarks = [
                WorldLandmark(
                    indice=indice, nombre=NOMBRES_LANDMARKS.get(indice, f"landmark_{indice}"),
                    x=float(punto.x), y=float(punto.y), z=float(punto.z),
                    visibility=float(getattr(punto, "visibility", 0.0)),
                    presence=float(getattr(punto, "presence", 0.0)),
                )
                for indice, punto in enumerate(puntos_mundo)
            ]
            personas.append(PoseResult(landmarks=landmarks, world_landmarks=world_landmarks))
        return personas
