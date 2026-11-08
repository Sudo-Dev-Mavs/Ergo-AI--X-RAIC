# -*- mode: python ; coding: utf-8 -*-
# Empaquetado de ErgoAI con PyInstaller. Úsalo con: uv run python scripts/construir_ejecutable.py
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

RAIZ = Path(SPECPATH).parent
UN_ARCHIVO = bool(int(__import__("os").environ.get("ERGOAI_UN_ARCHIVO", "0")))

datas = [
    (str(RAIZ / "src/ergoai/web/dist"), "ergoai/web/dist"),
    (str(RAIZ / "config/umbrales.yaml"), "recursos/config"),
    (str(RAIZ / "models/pose_landmarker_heavy.task"), "recursos/models"),
    (str(RAIZ / "web/LICENCIAS-TERCEROS.md"), "licencias"),
]
binaries = []
hiddenimports = collect_submodules("uvicorn") + collect_submodules("ergoai") + ["multipart", "python_multipart"]

mp_datas, mp_binaries, mp_hidden = collect_all("mediapipe")
datas += [(origen, destino) for origen, destino in mp_datas if "/test" not in destino and "\\test" not in destino]
binaries += mp_binaries
hiddenimports += [m for m in mp_hidden if ".test" not in m]

a = Analysis(
    [str(RAIZ / "empaquetado/lanzador.py")],
    pathex=[str(RAIZ / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "_tkinter", "ergoai.gui",          # la interfaz Tk no viaja en el ejecutable
        "sounddevice", "_sounddevice", "_sounddevice_data",  # ver ergoai.pose.bloquear_audio_de_mediapipe
        "pytest", "_pytest", "IPython", "jax", "jaxlib", "PyInstaller",
        "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_qtagg", "PyQt5", "PyQt6", "PySide6",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
icono = str(RAIZ / ("empaquetado/icono.ico" if sys.platform == "win32" else "empaquetado/icono.png"))
consola = sys.platform != "win32"  # en Windows, sin ventana de consola; el registro va a ~/ErgoAI/ergoai.log

if UN_ARCHIVO:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ErgoAI", icon=icono, console=consola, upx=False, strip=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ErgoAI", icon=icono, console=consola, upx=False, strip=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="ErgoAI", upx=False, strip=False)
