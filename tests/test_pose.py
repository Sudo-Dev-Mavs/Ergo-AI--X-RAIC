import numpy as np

from ergoai.cli import elegir_persona, procesar_vista
from ergoai.config import Configuracion
from ergoai.io_imagenes import ImagenRGB
from ergoai.modelos import Landmark, PoseResult


def _persona(desplazamiento: float, tamano: float) -> PoseResult:
    return PoseResult(
        landmarks=[
            Landmark(11, "hombro_izquierdo", desplazamiento, 10, 0, 0.9, 0.9),
            Landmark(12, "hombro_derecho", desplazamiento + tamano, 10 + tamano, 0, 0.9, 0.9),
        ],
        world_landmarks=[],
    )


def test_elije_la_persona_de_mayor_caja_visible() -> None:
    personas = [_persona(0, 10), _persona(0, 30)]
    indice, elegida = elegir_persona(personas, 0.5, None)
    assert indice == 1
    assert elegida == personas[1]


def test_vista_sin_deteccion_no_falla(configuracion: Configuracion) -> None:
    class BackendVacio:
        def detect(self, image: np.ndarray) -> list[PoseResult]:
            return []

    imagen = ImagenRGB(np.zeros((20, 30, 3), dtype=np.uint8), 30, 20)
    vista = procesar_vista("frente", imagen, BackendVacio(), configuracion)
    assert not vista.detectado
    assert vista.motivo.startswith("sin detección de pose")
