import json
from pathlib import Path

import pytest
from PIL import Image

from ergoai.cli import ejecutar_pose
from ergoai.modelos import PoseResult


class BackendVacio:
    def detect(self, image) -> list[PoseResult]:
        return []


def _proyecto(tmp_path: Path, imagenes: tuple[str, ...]) -> tuple[Path, Path]:
    raiz = tmp_path / "proyecto"
    (raiz / "config").mkdir(parents=True)
    (raiz / "config" / "umbrales.yaml").write_text(
        (Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    caso = tmp_path / "caso"
    caso.mkdir()
    for nombre in imagenes:
        Image.new("RGB", (40, 60)).save(caso / nombre, format="PNG")
    return raiz, caso


def test_vista_con_extension_en_mayusculas_se_usa_y_ausente_se_omite(tmp_path: Path) -> None:
    raiz, caso = _proyecto(tmp_path, ("costado.JPG",))
    pose = json.loads(ejecutar_pose(caso, raiz, BackendVacio()).read_text(encoding="utf-8"))
    assert list(pose["vistas"]) == ["costado"]


def test_vista_duplicada_se_rechaza_con_ambos_nombres(tmp_path: Path) -> None:
    raiz, caso = _proyecto(tmp_path, ("frente.jpg", "frente.png"))
    with pytest.raises(ValueError, match="frente.jpg") as error:
        ejecutar_pose(caso, raiz, BackendVacio())
    assert "frente.png" in str(error.value)
