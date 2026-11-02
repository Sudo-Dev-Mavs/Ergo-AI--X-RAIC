from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from ergoai import gui  # noqa: E402


class _Boton:
    def __init__(self) -> None:
        self.estado = "disabled"

    def configure(self, state: str) -> None:
        self.estado = state


class _Ventana:
    """Encola callbacks como Tk: se ejecutan después de salir del `except`."""

    def __init__(self) -> None:
        self.pendientes: list = []

    def after(self, _retardo: int, funcion) -> None:
        self.pendientes.append(funcion)


class _Variable:
    def __init__(self) -> None:
        self.valor = ""

    def set(self, valor: str) -> None:
        self.valor = valor

    def get(self) -> str:
        return self.valor


def test_error_en_segundo_plano_se_muestra_y_rehabilita_boton(monkeypatch, tmp_path: Path) -> None:
    app = object.__new__(gui.AplicacionErgoAI)
    app.raiz, app.ventana, app.boton_evaluar, app.estado = tmp_path, _Ventana(), _Boton(), _Variable()
    errores: list[tuple[str, str]] = []

    def fallar(caso, raiz):
        raise FileNotFoundError("Ejecuta scripts/descargar_modelo.py")

    monkeypatch.setattr(gui, "ejecutar_evaluar", fallar)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda titulo, mensaje: errores.append((titulo, mensaje)))

    app._evaluar_en_segundo_plano(tmp_path)
    for funcion in app.ventana.pendientes:
        funcion()

    assert errores == [("Error durante el análisis", "Ejecuta scripts/descargar_modelo.py")]
    assert app.boton_evaluar.estado == "normal"
    assert app.estado.valor == "La evaluación no pudo completarse."


def test_actualizar_vista_reemplaza_imagen_anterior(monkeypatch, tmp_path: Path) -> None:
    destino = tmp_path / "data" / "casos" / "caso01"
    destino.mkdir(parents=True)
    (destino / "frente.jpg").write_bytes(b"vieja")
    (destino / "costado.jpg").write_bytes(b"costado")
    nueva = tmp_path / "foto.png"
    nueva.write_bytes(b"nueva")
    app = object.__new__(gui.AplicacionErgoAI)
    app.raiz = tmp_path
    app.archivos = {vista: _Variable() for vista in ("frente", "costado", "aerea")}
    app.archivos["frente"].set(str(nueva))
    monkeypatch.setattr(app, "_contexto", lambda: {"caso_id": "caso01"}, raising=False)
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *argumentos: True)

    app._preparar_caso()

    assert sorted(ruta.name for ruta in destino.iterdir()) == ["contexto.json", "costado.jpg", "frente.png"]
    assert (destino / "frente.png").read_bytes() == b"nueva"


def test_foto_precargada_del_caso_no_se_borra(monkeypatch, tmp_path: Path) -> None:
    destino = tmp_path / "data" / "casos" / "caso01"
    destino.mkdir(parents=True)
    (destino / "frente.JPG").write_bytes(b"original")
    app = object.__new__(gui.AplicacionErgoAI)
    app.raiz = tmp_path
    app.archivos = {vista: _Variable() for vista in ("frente", "costado", "aerea")}
    app.archivos["frente"].set(str(destino / "frente.JPG"))
    monkeypatch.setattr(app, "_contexto", lambda: {"caso_id": "caso01"}, raising=False)
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *argumentos: True)

    app._preparar_caso()

    assert (destino / "frente.JPG").read_bytes() == b"original"
