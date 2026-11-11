from pathlib import Path

from ergoai.capturas import reordenar_vistas_toma


def test_reordena_ciclo_sin_pisar(tmp_path: Path) -> None:
    borrador = "borrador-test"
    toma = "20260101-120000-001"
    base = tmp_path / "capturas" / borrador / toma
    base.mkdir(parents=True)
    (base / "costado.jpg").write_bytes(b"COSTADO")
    (base / "frente.jpg").write_bytes(b"FRENTE")
    (base / "costado.pose.json").write_text('{"personas":[]}', encoding="utf-8")
    (base / "frente.pose.json").write_text('{"personas":[]}', encoding="utf-8")

    movidos = reordenar_vistas_toma(tmp_path, borrador, toma, {"costado": "frente", "frente": "costado"})
    assert "costado → frente" in movidos
    assert "frente → costado" in movidos
    assert (base / "costado.jpg").read_bytes() == b"FRENTE"
    assert (base / "frente.jpg").read_bytes() == b"COSTADO"
    assert (base / "costado.pose.json").is_file()
    assert (base / "frente.pose.json").is_file()
