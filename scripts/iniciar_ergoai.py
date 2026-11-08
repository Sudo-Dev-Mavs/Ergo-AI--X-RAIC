"""Iniciador de desarrollo que evita el ejecutable de entrada de Windows.

Uso:
    uv run python scripts/iniciar_ergoai.py
"""

from ergoai.servidor import main


if __name__ == "__main__":
    main()
