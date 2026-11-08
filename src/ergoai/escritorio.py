"""ErgoAI como aplicación de escritorio: servidor local y ventana propia.

Al abrir el ejecutable:
1. Prepara la carpeta de datos del usuario (por defecto ``~/ErgoAI``) con la configuración y
   el modelo de pose incluidos en el paquete; los casos, resultados e informes viven ahí.
2. Levanta la API en 127.0.0.1 con MediaPipe aislado en un proceso hijo.
3. Abre la interfaz en una ventana de aplicación (Edge, Chrome, Chromium o Brave en modo
   ``--app``); al cerrar esa ventana se detiene el servidor. Si no hay navegador compatible,
   usa el predeterminado.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP = "ErgoAI"
log = logging.getLogger("ergoai")


def carpeta_recursos() -> Path:
    """Configuración y modelo incluidos: dentro del paquete congelado o en el repositorio."""

    congelado = getattr(sys, "_MEIPASS", None)
    return Path(congelado) / "recursos" if congelado else Path(__file__).resolve().parents[2]


def carpeta_datos(explicita: str | None = None) -> Path:
    return Path(explicita or os.environ.get("ERGOAI_DATOS") or Path.home() / APP).expanduser().resolve()


def preparar_datos(datos: Path, recursos: Path) -> None:
    """Crea la estructura de trabajo sin sobrescribir umbrales que el especialista haya ajustado."""

    for sub in ("config", "models", "data/casos", "out"):
        (datos / sub).mkdir(parents=True, exist_ok=True)
    config = datos / "config" / "umbrales.yaml"
    if not config.is_file():
        shutil.copy2(recursos / "config" / "umbrales.yaml", config)
    origen_modelo = recursos / "models" / "pose_landmarker_heavy.task"
    destino_modelo = datos / "models" / "pose_landmarker_heavy.task"
    if origen_modelo.is_file() and (not destino_modelo.is_file() or destino_modelo.stat().st_size != origen_modelo.stat().st_size):
        shutil.copy2(origen_modelo, destino_modelo)


def candidatos_navegador() -> list[str]:
    if os.environ.get("ERGOAI_NAVEGADOR"):
        return [os.environ["ERGOAI_NAVEGADOR"]]
    if sys.platform == "win32":
        bases = [os.environ.get(v, "") for v in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData")]
        relativos = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                     r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Chromium\Application\chrome.exe"]
        return [str(Path(b) / r) for r in relativos for b in bases if b]
    if sys.platform == "darwin":
        return [f"/Applications/{n}.app/Contents/MacOS/{n}" for n in ("Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser")]
    nombres = ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome", "microsoft-edge-stable", "brave-browser", "brave")
    return [ruta for nombre in nombres if (ruta := shutil.which(nombre))]


def abrir_ventana(url: str, datos: Path) -> subprocess.Popen | None:
    """Abre la interfaz en una ventana de aplicación con un perfil propio de ErgoAI."""

    for ejecutable in candidatos_navegador():
        if not Path(ejecutable).is_file():
            continue
        argumentos = [ejecutable, f"--app={url}", f"--user-data-dir={datos / '.ventana'}", "--no-first-run",
                      "--no-default-browser-check", "--disable-features=Translate", "--window-size=1440,960", f"--class={APP}"]
        try:
            log.info("Abriendo ventana con %s", ejecutable)
            return subprocess.Popen(argumentos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            log.exception("No se pudo abrir %s", ejecutable)
    return None


def _responde(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}api/salud", timeout=1.5) as respuesta:
            return respuesta.status == 200
    except OSError:
        return False


def _instancia_activa(datos: Path) -> str | None:
    """Si ErgoAI ya está abierto con esta carpeta de datos, devuelve su URL."""

    try:
        url = json.loads((datos / ".instancia.json").read_text(encoding="utf-8"))["url"]
    except (OSError, ValueError, KeyError):
        return None
    return url if _responde(url) else None


def _salidas_seguras(datos: Path) -> None:
    """En Windows sin consola, stdout/stderr son None: se redirigen al registro."""

    if sys.stdout is None or sys.stderr is None:
        flujo = open(datos / "ergoai-consola.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or flujo
        sys.stderr = sys.stderr or flujo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP, description="ErgoAI · evaluación ergonómica local")
    parser.add_argument("--datos", help="carpeta de casos y resultados (por defecto ~/ErgoAI)")
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--sin-ventana", action="store_true", help="solo levanta el servidor e imprime la URL")
    argumentos = parser.parse_args(argv)

    datos = carpeta_datos(argumentos.datos)
    datos.mkdir(parents=True, exist_ok=True)
    _salidas_seguras(datos)
    logging.basicConfig(filename=datos / "ergoai.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    existente = _instancia_activa(datos)
    if existente and not argumentos.sin_ventana:
        log.info("Ya hay una instancia en %s; se abre otra ventana", existente)
        if abrir_ventana(existente, datos) is None:
            webbrowser.open(existente)
        return 0

    import uvicorn

    from .servidor import crear_app_produccion, puerto_libre

    preparar_datos(datos, carpeta_recursos())
    puerto = puerto_libre(argumentos.puerto)
    url = f"http://127.0.0.1:{puerto}/"
    app, detector = crear_app_produccion(datos)
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_config=None, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, name="api", daemon=True)
    hilo.start()
    limite = time.monotonic() + 30
    while not servidor.started and hilo.is_alive() and time.monotonic() < limite:
        time.sleep(0.05)
    if not servidor.started:
        log.error("El servidor no arrancó en %s", url)
        print(f"{APP}: no se pudo iniciar el servidor local. Revisa {datos / 'ergoai.log'}.", file=sys.stderr)
        return 1
    (datos / ".instancia.json").write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    log.info("Servidor en %s con datos en %s", url, datos)
    print(f"{APP} disponible en {url}\nDatos: {datos}", flush=True)

    try:
        ventana = None if argumentos.sin_ventana else abrir_ventana(url, datos)
        if ventana is not None:
            ventana.wait()  # cerrar la ventana cierra ErgoAI
        else:
            if not argumentos.sin_ventana:
                webbrowser.open(url)
                print("No se encontró Edge/Chrome/Chromium: se abrió el navegador predeterminado. Ctrl+C para cerrar.", flush=True)
            while hilo.is_alive():
                hilo.join(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        servidor.should_exit = True
        hilo.join(10)
        detector.cerrar()
        (datos / ".instancia.json").unlink(missing_ok=True)
        log.info("ErgoAI cerrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
