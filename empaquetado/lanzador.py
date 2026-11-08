"""Punto de entrada del ejecutable de ErgoAI (PyInstaller)."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()  # el detector aislado usa procesos "spawn"
    from ergoai.escritorio import main

    raise SystemExit(main())
