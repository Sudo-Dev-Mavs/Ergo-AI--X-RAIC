# ErgoAI · X-RAIC 2026

Beta local para evaluar posturas de trabajo a partir de fotografías y contexto operativo. El flujo principal detecta pose con **MediaPipe Tasks**, calcula ángulos corporales y entrega una evaluación **REBA** trazable.

> Las fotografías del reto son confidenciales: ErgoAI procesa imágenes localmente. `data/`, `out/`, `models/` y `.venv/` no se versionan.

## Aspectos clave

- Detección local con `vision.PoseLandmarker`; no usa la API eliminada `mp.solutions.pose`.
- Soporte para vistas de frente, costado y aérea; selección de la persona de mayor área visible.
- Corrección de rotación EXIF, landmarks en píxeles y almacenamiento de landmarks 3D de MediaPipe.
- Vectores, ángulos, orientación lateral y banderas de baja visibilidad, escorzo y cercanía a umbrales.
- Puntaje REBA por lado, con carga, agarre, actividad, overrides del especialista y pendientes manuales cuando un dato no se puede medir.
- Recomendaciones jerarquizadas (ingeniería → rediseño → administrativas) basadas en la NOM-036-1-STPS-2018 y en los lineamientos Jabil (16-PE30-6500-00023 §6.4, formato 16-PE80-6500-00014), cada una con su fundamento y su reducción esperada de REBA.
- Riesgo residual recalculado con el mismo método REBA aplicando los controles vigentes, y comparado contra el inicial.
- Validación del especialista: aprobar, rechazar (con motivo), editar o agregar recomendaciones; bitácora con usuario, fecha, valor anterior/nuevo y cadena SHA-256 que detecta alteraciones. El informe queda en BORRADOR hasta que el especialista lo aprueba.
- Informe del estudio en HTML autocontenido (imprimible a PDF) y CSV con las columnas de «OBSERVACIONES Y MEJORAS» del formato 00014.
- Interfaz gráfica local para cargar fotos, validar y consultar los resultados, con bandeja de casos ordenada por riesgo; también hay CLI para flujos automatizados.

## Requisitos e instalación

- Python 3.12 (fijado en `.python-version`). En Linux, si `ergoai-gui` falla con `libtk8.6.so`, usa el Python gestionado por uv: `uv sync --python 3.12 --managed-python`.
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
4. Consulta el REBA, nivel de riesgo, riesgo residual, pendientes e imagen anotada.
5. En **Validación del especialista** aprueba, rechaza o edita cada recomendación y pulsa **Aprobar informe**. Para aprobar, todas deben estar decididas, las acciones aprobadas necesitan responsable y un caso de riesgo alto/muy alto requiere al menos un control de ingeniería o rediseño aprobado.
6. **Bandeja de casos** muestra todos los casos con los de mayor riesgo primero.

Los artefactos se guardan en `out/<caso_id>/`: `resultado.json`, `validacion.json` (decisiones y bitácora), `informe.html` y `acciones_00014.csv`.

### Línea de comandos

Prepara un caso en `data/casos/<caso_id>/` con imágenes llamadas `frente`, `costado` y/o `aerea`, más un `contexto.json`.

```powershell
# Solo landmarks y esqueleto
uv run python -m ergoai.cli pose data/casos/caso01

# Vectores, ángulos e imágenes anotadas
uv run python -m ergoai.cli angulos data/casos/caso01

# REBA + recomendaciones + riesgo residual + informe borrador
uv run python -m ergoai.cli evaluar data/casos/caso01

# Decisiones del especialista (quedan en la bitácora y regeneran el informe)
uv run python -m ergoai.cli validar out/caso01 aprobar --usuario "Ing. Pérez" --rec R-TRONCO-ING
uv run python -m ergoai.cli validar out/caso01 editar --usuario "Ing. Pérez" --rec R-TRONCO-ING --campo responsable="IE celda 3" --campo fecha_compromiso=2026-12-01
uv run python -m ergoai.cli validar out/caso01 rechazar --usuario "Ing. Pérez" --rec R-AGARRE-RED --comentario "contenedor del cliente"
uv run python -m ergoai.cli validar out/caso01 aprobar_informe --usuario "Ing. Pérez"
```

`contexto.json` acepta además `tipo_tarea` (`levantamiento`, `transporte_con_auxiliar`, `transporte_sin_auxiliar`, `otro`), `tipo_trabajo` (`precision`, `ligero`, `pesado`) y `realizado_por`.

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
| Informe y recomendaciones | Implementada | Motor de reglas NOM-036-1 + Jabil con jerarquía de controles, fundamento y Δ REBA por recomendación; informe HTML y CSV 00014. |
| Riesgo residual | Implementada | REBA recalculado con los efectos declarados de los controles no rechazados; las medidas administrativas no cuentan. |
| Validación del especialista | Implementada | Aprobar/rechazar/editar/agregar con bitácora encadenada por hash; el informe se reabre ante cualquier cambio. |
| Interfaz beta | Implementada | Aplicación de escritorio local con validación y bandeja por riesgo. Falta empaquetarla como ejecutable para distribución sin Python. |

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
