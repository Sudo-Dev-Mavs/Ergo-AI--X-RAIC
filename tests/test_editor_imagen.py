from pathlib import Path

from PIL import Image

from ergoai.editor_imagen import guardar_recorte


def test_guardar_recorte_produce_imagen_mas_chica(tmp_path: Path):
    origen = tmp_path / "frente.jpg"
    Image.new("RGB", (200, 100), color=(20, 80, 40)).save(origen, quality=90)
    destino = guardar_recorte(origen, (20, 10, 120, 80))
    assert destino.is_file()
    with Image.open(destino) as recorte:
        assert recorte.size == (100, 70)


def test_recorte_minimo_falla(tmp_path: Path):
    origen = tmp_path / "costado.png"
    Image.new("RGB", (80, 80), color=(10, 10, 10)).save(origen)
    try:
        guardar_recorte(origen, (10, 10, 12, 12))
        assert False, "debía fallar"
    except ValueError:
        pass
