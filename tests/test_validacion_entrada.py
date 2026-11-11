import numpy as np
import pytest

from ergoai.validacion_entrada import (
    validar_angulo_override,
    validar_calidad_imagen,
    validar_carga_kg,
    validar_persona_en_pose,
)


def test_rechaza_imagen_negra() -> None:
    negra = np.zeros((400, 400, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="negra|sin contenido"):
        validar_calidad_imagen(negra, "La foto costado")


def test_rechaza_imagen_muy_chica() -> None:
    chica = np.random.randint(40, 200, (80, 80, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="pequeña"):
        validar_calidad_imagen(chica, "La foto frente")


def test_acepta_imagen_con_detalle() -> None:
    rng = np.random.default_rng(0)
    # Gradiente + ruido → contraste y nitidez suficientes.
    base = np.linspace(30, 220, 480, dtype=np.float32)
    img = np.tile(base, (640, 1))
    img = np.stack([img, img, img], axis=-1)
    img = np.clip(img + rng.normal(0, 18, img.shape), 0, 255).astype(np.uint8)
    validar_calidad_imagen(img, "La foto costado")


def test_sin_persona() -> None:
    with pytest.raises(ValueError, match="persona"):
        validar_persona_en_pose([], "La foto costado")
    # Aérea: MediaPipe casi nunca ve pose cenital → no bloquear.
    validar_persona_en_pose([], "La foto aérea", requerida=False)


def test_persona_requerida_solo_fuera_de_aerea() -> None:
    from ergoai.validacion_entrada import persona_requerida_en_vista

    assert persona_requerida_en_vista("costado") is True
    assert persona_requerida_en_vista("frente") is True
    assert persona_requerida_en_vista("aerea") is False


def test_carga_absurda() -> None:
    with pytest.raises(ValueError, match="creíble|máximo"):
        validar_carga_kg(1_000_000)
    assert validar_carga_kg("12,5") == 12.5


def test_angulo_fuera_de_rango() -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        validar_angulo_override("tronco_flexion", 900)
    validar_angulo_override("tronco_flexion", 45)
    with pytest.raises(ValueError, match="0 \\(No\\) o 1 \\(Sí\\)"):
        validar_angulo_override("apoyo_piernas_unilateral_L", 3)
