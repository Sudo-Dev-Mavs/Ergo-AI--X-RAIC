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

1. Elige las fotos disponibles de frente, costado y/o aérea.
2. Indica caso, postura, carga, agarre y actividad.
3. Pulsa **Analizar ergonomía**.
4. Consulta el REBA, nivel de riesgo, pendientes e imagen anotada. Los artefactos se guardan en `out/<caso_id>/`.

### Línea de comandos

Prepara un caso en `data/casos/<caso_id>/` con imágenes llamadas `frente`, `costado` y/o `aerea`, más un `contexto.json`. Cada vista lleva una sola imagen `.jpg`, `.jpeg` o `.png` (sin importar mayúsculas); si hay dos, por ejemplo `frente.jpg` y `frente.png`, la evaluación se detiene y pide dejar una. Al actualizar un caso desde la interfaz, la foto nueva reemplaza la anterior de esa vista.

```powershell
# Solo landmarks y esqueleto
uv run python -m ergoai.cli pose data/casos/caso01

# Vectores, ángulos e imágenes anotadas
uv run python -m ergoai.cli angulos data/casos/caso01

# Resultado REBA completo
uv run python -m ergoai.cli evaluar data/casos/caso01
```

En `contexto.json`, `overrides` declara valores del especialista en grados (p. ej. `{"tronco_flexion": 35}`). Reemplazan la medición automática, que se conserva en `valor_medido_deg`, y también completan medidas de una vista ausente: con `"tronco_torsion": 25` y sin foto aérea, la torsión entra en `angulos` con `vista: null` y deja de ser pendiente. En medidas por lado, `codo_flexion` aplica a ambos lados y `codo_flexion_R` tiene prioridad para el derecho.

Claves válidas de `overrides` (una clave desconocida o un valor no numérico detiene la evaluación):

- Únicas: `tronco_flexion`, `cuello_flexion`, `tronco_torsion`, `tronco_inclinacion_lateral`, `cuello_inclinacion_rotacion`, `apoyo_piernas_unilateral` (0 o 1).
- Por lado, sin sufijo o con `_L`/`_R`: `rodilla_flexion`, `brazo_flexion`, `codo_flexion`, `muneca_flexion_extension`, `brazo_abduccion`.

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
| Interfaz beta | Implementada | Aplicación de escritorio local. Falta empaquetarla como ejecutable para distribución sin Python. |

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
