import os
import signal
from pathlib import Path

import numpy as np
import pytest

from ergoai.config import Configuracion
from ergoai.pose_aislada import DetectorAislado


def _una_persona(configuracion, raiz, imagen):
    from ergoai.modelos import Landmark, PoseResult

    return [PoseResult([Landmark(0, "nariz", float(imagen.shape[1]), 1.0, 0.0, 0.9, 0.9)], [])]


def _morir(configuracion, raiz, imagen):
    os.kill(os.getpid(), signal.SIGKILL)


def test_detector_aislado_devuelve_resultados_del_hijo(configuracion: Configuracion, tmp_path: Path) -> None:
    detector = DetectorAislado(configuracion.pose, tmp_path, _una_persona)
    try:
        personas = detector.detect(np.zeros((40, 30, 3), dtype=np.uint8))
        assert personas[0].landmarks[0].x_px == 30.0
    finally:
        detector.cerrar()


def test_cierre_nativo_del_hijo_no_tumba_al_proceso_principal(configuracion: Configuracion, tmp_path: Path) -> None:
    detector = DetectorAislado(configuracion.pose, tmp_path, _morir)
    try:
        with pytest.raises(RuntimeError, match="se cerró inesperadamente"):
            detector.detect(np.zeros((4, 4, 3), dtype=np.uint8))
        detector.funcion = _una_persona  # el siguiente análisis arranca un trabajador nuevo
        assert detector.detect(np.zeros((4, 4, 3), dtype=np.uint8))
    finally:
        detector.cerrar()
