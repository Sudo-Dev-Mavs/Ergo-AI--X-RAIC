"""Construye el ejecutable de ErgoAI para el sistema operativo actual.

    uv run python scripts/construir_ejecutable.py            # carpeta dist/ErgoAI + archivo comprimido
    uv run python scripts/construir_ejecutable.py --web      # además recompila la interfaz (requiere Node)
    uv run python scripts/construir_ejecutable.py --un-archivo

PyInstaller no compila de forma cruzada: el .exe de Windows se construye en Windows y el
binario de Linux en Linux, con este mismo comando.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIST = RAIZ / "dist"


def paso(texto: str) -> None:
    print(f"\n==> {texto}", flush=True)


def correr(comando: list[str], **kwargs) -> None:
    print("   $", " ".join(comando), flush=True)
    subprocess.run(comando, check=True, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--web", action="store_true", help="recompila la interfaz con npm antes de empaquetar")
    parser.add_argument("--un-archivo", action="store_true", help="un solo ejecutable (arranca más lento)")
    parser.add_argument("--sin-comprimir", action="store_true", help="no generar el .zip/.tar.gz")
    argumentos = parser.parse_args()

    if argumentos.web:
        paso("Compilando la interfaz web")
        npm = shutil.which("npm")
        if not npm:
            sys.exit("No se encontró npm. Instala Node.js o quita --web para usar la interfaz ya compilada.")
        correr([npm, "install", "--no-audit", "--no-fund"], cwd=RAIZ / "web")
        correr([npm, "run", "build"], cwd=RAIZ / "web")
    if not (RAIZ / "src/ergoai/web/dist/index.html").is_file():
        sys.exit("Falta la interfaz compilada (src/ergoai/web/dist). Ejecuta con --web.")

    if not (RAIZ / "models/pose_landmarker_heavy.task").is_file():
        paso("Descargando el modelo de pose")
        correr([sys.executable, str(RAIZ / "scripts/descargar_modelo.py")], cwd=RAIZ)
    if not (RAIZ / "empaquetado/icono.ico").is_file():
        correr([sys.executable, str(RAIZ / "empaquetado/generar_icono.py")])

    paso("Empaquetando con PyInstaller")
    entorno = {**os.environ, "ERGOAI_UN_ARCHIVO": "1" if argumentos.un_archivo else "0"}
    correr([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(DIST),
            "--workpath", str(RAIZ / "build"), str(RAIZ / "empaquetado/ergoai.spec")], cwd=RAIZ, env=entorno)

    sistema = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    nombre = f"ErgoAI-{sistema}-{platform.machine().lower()}"
    if not argumentos.un_archivo:
        carpeta = DIST / "ErgoAI"
        shutil.copy2(RAIZ / "empaquetado/icono.png", carpeta / "icono.png")
        if sistema == "linux":
            instalar = carpeta / "instalar-acceso-directo.sh"
            instalar.write_text(
                "#!/bin/sh\n# Agrega ErgoAI al lanzador de aplicaciones del usuario.\n"
                'AQUI="$(cd "$(dirname "$0")" && pwd)"\n'
                'mkdir -p "$HOME/.local/share/applications"\n'
                'cat > "$HOME/.local/share/applications/ergoai.desktop" <<EOD\n'
                "[Desktop Entry]\nType=Application\nName=ErgoAI\nComment=Evaluación ergonómica REBA local\n"
                'Exec="$AQUI/ErgoAI"\nIcon=$AQUI/icono.png\nTerminal=false\nCategories=Science;Office;\nStartupWMClass=chrome-127.0.0.1__-Default\nEOD\n'
                'echo "Listo: busca ErgoAI en el lanzador de aplicaciones."\n',
                encoding="utf-8",
            )
            instalar.chmod(0o755)
        if not argumentos.sin_comprimir:
            paso("Comprimiendo")
            formato = "zip" if sistema == "windows" else "gztar"
            archivo = shutil.make_archive(str(DIST / nombre), formato, root_dir=DIST, base_dir="ErgoAI")
            print(f"   {archivo}")
        ejecutable = carpeta / ("ErgoAI.exe" if sistema == "windows" else "ErgoAI")
    else:
        ejecutable = DIST / ("ErgoAI.exe" if sistema == "windows" else "ErgoAI")
    paso(f"Ejecutable listo: {ejecutable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
