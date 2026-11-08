"""Genera icono.png e icono.ico (goniómetro REBA) para el ejecutable."""

import math
from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
TAM = 512
TINTA, HOJA = (19, 35, 59), (246, 248, 249)
ZONAS = [((111, 143, 122), 1, 1), ((47, 143, 91), 2, 3), ((217, 154, 0), 4, 7), ((224, 97, 14), 8, 10), ((196, 43, 28), 11, 15)]


def angulo(v: float) -> float:  # grados en sentido horario desde las 12, igual que la interfaz
    return -110 + (min(15, max(1, v)) - 1) / 14 * 220


def main() -> None:
    img = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, TAM - 16, TAM - 16), radius=112, fill=HOJA, outline=TINTA, width=10)
    cx, cy, r = TAM / 2, TAM * 0.6, TAM * 0.34
    caja = (cx - r, cy - r, cx + r, cy + r)
    for color, desde, hasta in ZONAS:  # PIL mide desde las 3 en sentido horario
        d.arc(caja, start=angulo(desde - 0.5) - 90 + 1.5, end=angulo(hasta + 0.5) - 90 - 1.5, fill=color, width=34)
    a = math.radians(angulo(11))
    d.line((cx, cy, cx + r * 0.86 * math.sin(a), cy - r * 0.86 * math.cos(a)), fill=TINTA, width=22)
    d.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=TINTA)
    img.save(AQUI / "icono.png")
    img.save(AQUI / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(AQUI / "icono.ico")


if __name__ == "__main__":
    main()
