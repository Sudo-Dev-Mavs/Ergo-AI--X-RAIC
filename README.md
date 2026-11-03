# ErgoAI · X-RAIC 2026

Beta local para evaluar posturas de trabajo a partir de fotografías y contexto operativo. El flujo principal detecta pose con **MediaPipe Tasks**, calcula ángulos corporales y entrega una evaluación **REBA** trazable.

> Las fotografías del reto son confidenciales: ErgoAI procesa imágenes localmente. `data/`, `out/`, `models/` y `.venv/` no se versionan.

## Aspectos clave

- Detección local con `vision.PoseLandmarker`; no usa la API eliminada `mp.solutions.pose`.
- Soporte para vistas de frente, costado y aérea; selección de la persona de mayor área visible.
- Corrección de rotación EXIF, landmarks en píxeles y almacenamiento de landmarks 3D de MediaPipe.
- Vectores, ángulos, orientación lateral y banderas de baja visibilidad, escorzo y cercanía a umbrales.
- Puntaje REBA por lado, con carga, agarre, actividad, overrides del especialista y pendientes manuales cuando un dato no se puede medir.
- Interfaz gráfica local para cargar fotos y consultar los resultados; también hay CLI para flujos automatizados.

## Requisitos e instalación

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

```powershell
git clone https://github.com/marco-venegas-sepulveda/Ergo-AI--X-RAIC.git
cd Ergo-AI--X-RAIC
uv sync
uv run python scripts/descargar_modelo.py
```

## Uso

### Interfaz gráfica (recomendada para la beta)

```powershell
uv run ergoai-gui
```

1. Arrastra las fotos de frente, costado y/o aérea a cada tarjeta (también puedes usar **Elegir foto**). Si falta una vista, la interfaz lo avisa y no inventa esa pose.
2. Completa el caso, la carga, la postura y lo que se ve en la estación.
3. Pulsa **Analizar postura**. El cálculo es local.
4. Revisa el REBA, el residual recalculado, las recomendaciones NOM-036 y aprueba/rechaza cada una (queda en bitácora). El resultado es una propuesta: el especialista decide.
5. Abre el informe en `out/<caso_id>/informe.md` (también `resultado.json` y `bitacora.jsonl`).

### Línea de comandos

Prepara un caso en `data/casos/<caso_id>/` con imágenes llamadas `frente`, `costado` y/o `aerea`, más un `contexto.json`.

```powershell
# Solo landmarks y esqueleto
uv run python -m ergoai.cli pose data/casos/caso01

# Vectores, ángulos e imágenes anotadas
uv run python -m ergoai.cli angulos data/casos/caso01

# Resultado REBA + recomendaciones + residual + informe
uv run python -m ergoai.cli evaluar data/casos/caso01
```

Tras `evaluar`, en `out/<caso_id>/` quedan `resultado.json`, `informe.md` y `bitacora.jsonl`.

La anotación manual y la evaluación de precisión se ejecutan localmente:

```powershell
uv run python scripts/anotar_manual.py data/validacion/caso01/costado.jpg --vista costado
uv run python scripts/evaluar_precision.py
```

## Pruebas

```powershell
uv run pytest
```

La suite contiene pruebas de geometría, signos, relación de aspecto, selección de pose, tablas y límites REBA, pipeline sintético, precisión, RULA, EAWS, NOM-036 y muñeca experimental.

## Estado frente a la especificación

| Área | Estado actual | Nota |
|---|---|---|
| Fase 0 — Preparación | Implementada | Proyecto `uv`, configuración Pydantic, modelo descargable y pruebas. |
| Fase 1 — Imagen y pose | Implementada | Carga EXIF/RGB, MediaPipe Tasks, varias personas y esqueleto sin rostro. |
| Fase 2 — Vectores y ángulos | Parcial | Medición 2D, orientación, corrección de cámara y banderas disponibles. Faltan respaldos completos entre vistas/3D y anotaciones con flechas, color REBA y etiquetas junto a cada articulación. |
| Fase 3 — REBA | Implementada | Bandas, tablas A/B/C, ambos lados, contexto, overrides y `resultado.json`. |
| Fase 4 — Precisión | Parcial | Anotación manual, comparación y CSV disponibles. Falta correr la validación completa con las fotografías/referencias reales y demostrar la meta ≥90 %. |
| Fase 5 — Complementos | Parcial | Módulos base de RULA, EAWS, NOM-036 y muñeca; no alteran REBA. Falta integrar los complementos a la interfaz y validar HandLandmarker con referencias reales. |
| Interfaz beta | Implementada | Flujo de fotos, REBA, residual, recomendaciones con validación y apertura de informe. Falta empaquetar ejecutable. |
| Informe / R3 / R6 / R7 | Implementado (beta) | Informe Markdown, reglas NOM-036 con ingeniería primero, bitácora append-only y residual con el mismo motor REBA. Falta calibrar con los 6 casos de Jabil y doc de 10 cuartillas. |

## Alcance y limitaciones de la beta

- REBA es una ayuda de evaluación, no reemplaza al especialista ergonómico.
- Si un landmark o contexto requerido no está disponible, el sistema deja el resultado como pendiente; no rellena valores “típicos”.
- La precisión contra los casos de Jabil todavía debe medirse antes de usar el sistema para la competencia.
- RULA, EAWS, NOM-036 y muñeca experimental son complementos aislados: no modifican el REBA principal.

## Estructura relevante

```text
src/ergoai/       # Lógica de pose, ángulos, REBA, complementos y GUI
config/           # Umbrales auditables
scripts/          # Descarga de modelo, referencia manual y precisión
tests/            # Pruebas deterministas sin fotografías confidenciales
```
