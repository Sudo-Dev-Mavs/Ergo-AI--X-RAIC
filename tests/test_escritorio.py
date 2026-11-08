from pathlib import Path

import pytest

from ergoai import escritorio


def _recursos(tmp_path: Path) -> Path:
    recursos = tmp_path / "recursos"
    (recursos / "config").mkdir(parents=True)
    (recursos / "models").mkdir()
    (recursos / "config" / "umbrales.yaml").write_text("original: 1\n", encoding="utf-8")
    (recursos / "models" / "pose_landmarker_heavy.task").write_bytes(b"modelo-v2")
    return recursos


def test_preparar_datos_copia_recursos_sin_pisar_umbrales_del_especialista(tmp_path: Path) -> None:
    recursos, datos = _recursos(tmp_path), tmp_path / "ErgoAI"
    escritorio.preparar_datos(datos, recursos)
    assert (datos / "config" / "umbrales.yaml").read_text(encoding="utf-8") == "original: 1\n"
    assert (datos / "data" / "casos").is_dir() and (datos / "out").is_dir()

    (datos / "config" / "umbrales.yaml").write_text("ajustado: 2\n", encoding="utf-8")
    (datos / "models" / "pose_landmarker_heavy.task").write_bytes(b"viejo")
    escritorio.preparar_datos(datos, recursos)
    assert (datos / "config" / "umbrales.yaml").read_text(encoding="utf-8") == "ajustado: 2\n"
    assert (datos / "models" / "pose_landmarker_heavy.task").read_bytes() == b"modelo-v2"


def test_carpeta_de_datos_respeta_argumento_y_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ERGOAI_DATOS", str(tmp_path / "desde-env"))
    assert escritorio.carpeta_datos() == (tmp_path / "desde-env").resolve()
    assert escritorio.carpeta_datos(str(tmp_path / "explicita")) == (tmp_path / "explicita").resolve()


def test_navegador_forzado_por_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ERGOAI_NAVEGADOR", "/opt/navegador")
    assert escritorio.candidatos_navegador() == ["/opt/navegador"]


def test_instancia_previa_caida_se_ignora(tmp_path: Path) -> None:
    (tmp_path / ".instancia.json").write_text('{"url": "http://127.0.0.1:9/"}', encoding="utf-8")
    assert escritorio._instancia_activa(tmp_path) is None
