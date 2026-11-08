"""Detector de pose en un proceso hijo: si MediaPipe se cierra de forma nativa, el servidor sigue vivo."""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .config import PoseConfig
from .modelos import PoseResult

_DETECTOR: Any = None


def _detectar_en_hijo(configuracion: dict[str, Any], raiz: str, imagen: np.ndarray) -> list[PoseResult]:
    """Se ejecuta en el proceso hijo; reutiliza el backend entre llamadas."""

    global _DETECTOR
    if _DETECTOR is None:
        from .pose import MediaPipeBackend

        _DETECTOR = MediaPipeBackend(PoseConfig.model_validate(configuracion), raiz)
    return _DETECTOR.detect(imagen)


class DetectorAislado:
    """Implementa ``PoseBackend`` delegando la detección a un único proceso trabajador."""

    def __init__(self, configuracion: PoseConfig, raiz: Path, funcion: Callable[..., list[PoseResult]] = _detectar_en_hijo,
                 tiempo_max_s: float = 300) -> None:
        self.configuracion = configuracion.model_dump()
        self.raiz = str(raiz)
        self.funcion = funcion
        self.tiempo_max_s = tiempo_max_s
        self._ejecutor: ProcessPoolExecutor | None = None

    def _trabajador(self) -> ProcessPoolExecutor:
        if self._ejecutor is None:
            self._ejecutor = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
        return self._ejecutor

    def detect(self, image: np.ndarray) -> list[PoseResult]:
        try:
            return self._trabajador().submit(self.funcion, self.configuracion, self.raiz, image).result(timeout=self.tiempo_max_s)
        except BrokenProcessPool as exc:
            self.cerrar()
            raise RuntimeError(
                "El detector de pose (MediaPipe) se cerró inesperadamente. El análisis no se guardó; "
                "vuelve a intentarlo. Si se repite, abre ErgoAI fuera de otras aplicaciones que limiten "
                "procesos en tiempo real (por ejemplo, la terminal integrada de un IDE)."
            ) from exc

    def cerrar(self) -> None:
        if self._ejecutor is not None:
            self._ejecutor.shutdown(wait=False, cancel_futures=True)
            self._ejecutor = None
