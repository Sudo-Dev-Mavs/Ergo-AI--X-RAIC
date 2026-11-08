"""Evalúa los casos de validación y genera el reporte de precisión (criterios 1 y 2 de la rúbrica).

    uv run python scripts/evaluar_precision.py                         # data/validacion → out/precision/
    uv run python scripts/evaluar_precision.py --reusar                # no reevalúa casos ya procesados
    uv run python scripts/evaluar_precision.py --plantilla data/validacion/caso01

Protocolo completo: docs/PROTOCOLO_VALIDACION.md
"""

import argparse
from pathlib import Path

from ergoai.reporte_precision import crear_plantilla, generar_reporte


def main() -> None:
    parser = argparse.ArgumentParser(description="Reporte de precisión de ErgoAI contra referencias de Jabil")
    parser.add_argument("--validacion", type=Path, default=Path("data/validacion"), help="carpeta con un subdirectorio por caso")
    parser.add_argument("--salida", type=Path, default=Path("out/precision"), help="dónde escribir resultados y reporte")
    parser.add_argument("--reusar", action="store_true", help="no reevaluar los casos que ya tienen resultado.json")
    parser.add_argument("--plantilla", type=Path, help="crea un referencia.json para completar en esa carpeta de caso y termina")
    args = parser.parse_args()
    if args.plantilla:
        print(f"Plantilla creada: {crear_plantilla(args.plantilla)}")
        return
    raiz = Path(__file__).resolve().parents[1]
    resumen = generar_reporte(args.validacion, raiz, args.salida, args.reusar)
    c1, c2 = resumen["criterio_1"], resumen["criterio_2"]
    print(f"Casos evaluados: {resumen['casos']}")
    print(f"Criterio 1 (REBA y nivel coinciden): {c1['coinciden']} de {c1['comparables']} -> {c1['rubrica']}")
    print(f"Criterio 2 (segmentos en la misma banda): {c2['misma_banda_pct']} % de {c2['segmentos']} ({c2['sin_estimar']} sin estimar) -> {c2['rubrica']}")
    print(f"Reporte: {args.salida / 'reporte.html'}")


if __name__ == "__main__":
    main()
