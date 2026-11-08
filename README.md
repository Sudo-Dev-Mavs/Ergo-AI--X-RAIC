# ErgoAI · X-RAIC 2026

Beta local para evaluar posturas de trabajo a partir de fotografías y contexto operativo. El flujo principal detecta pose con **MediaPipe Tasks**, calcula ángulos corporales y entrega una evaluación **REBA** trazable.

> Las fotografías del reto son confidenciales: ErgoAI procesa imágenes localmente. `data/`, `out/`, `models/` y `.venv/` no se versionan.

## Aspectos clave

- Detección local con `vision.PoseLandmarker`; no usa la API eliminada `mp.solutions.pose`.
- Soporte para vistas de frente, costado y aérea; selección de la persona de mayor área visible.
- Corrección de rotación EXIF, landmarks en píxeles y almacenamiento de landmarks 3D de MediaPipe.
- Vectores, ángulos, orientación lateral y banderas de baja visibilidad, escorzo y cercanía a umbrales.
- Respaldos entre vistas y pose 3D cuando la vista primaria no puede sostener una medida; las estimaciones de respaldo se identifican explícitamente.
- Imágenes anotadas sin rostro, con flechas de vectores, valores junto a la articulación y color de banda REBA.
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
uv run python scripts/descargar_modelo.py   # pose y detector de rostros
```

## Uso

### Ejecutable de escritorio (para usar ErgoAI sin instalar nada)

**Beta Windows 0.2.0b1:** el paquete se genera en Windows y contiene el servidor local, la interfaz web, MediaPipe y los modelos requeridos. En GitHub Actions, ejecuta el flujo **Ejecutable** para obtener el artefacto `ErgoAI-Windows`; descomprímelo y abre `ErgoAI.exe`.

Descomprime `ErgoAI-<sistema>.zip` / `.tar.gz` y abre **ErgoAI** (`ErgoAI.exe` en Windows). La app abre su propia ventana (Edge, Chrome, Chromium o Brave en modo aplicación) y al cerrarla se detiene. En Linux, `./instalar-acceso-directo.sh` la agrega al lanzador de aplicaciones.

- Los casos, resultados, informes y la bitácora se guardan en `~/ErgoAI` (en Windows, `C:\Users\<usuario>\ErgoAI`). Usa `--datos <carpeta>` o la variable `ERGOAI_DATOS` para cambiarla.
- Los umbrales se copian a `~/ErgoAI/config/umbrales.yaml` la primera vez; los ajustes del especialista no se sobrescriben al actualizar.
- El registro de errores queda en `~/ErgoAI/ergoai.log`.

Para construirlo (PyInstaller no compila de forma cruzada: el `.exe` se construye en Windows y el binario de Linux en Linux):

```powershell
uv sync
uv run python scripts/descargar_modelo.py
uv run python scripts/construir_ejecutable.py          # dist/ErgoAI/ y dist/ErgoAI-<sistema>.zip|tar.gz
uv run python scripts/construir_ejecutable.py --web    # además recompila la interfaz (requiere Node)
```

### Interfaz web local (recomendada)

```powershell
uv run python scripts/iniciar_ergoai.py
```

Abre `http://127.0.0.1:8765/` en el navegador. El servidor escucha solo en este equipo; las fotos y resultados no salen de él. La interfaz ya viene compilada en `src/ergoai/web/dist`, así que no hace falta Node para usarla.

1. **Inicio** (*Evaluación ergonómica*): a la izquierda, cómo empezar y el acceso a **Nueva evaluación**; al costado, el panel **Casos evaluados**, ordenado por riesgo con los casos alto/muy alto sin validar primero. Cada caso muestra su REBA, el residual esperado sobre la escala 1–15, cuántas propuestas faltan por validar y si el informe está aprobado.
2. **Nueva evaluación**, en tres pasos entre los que puedes ir y volver antes de analizar:
   1. **Fotografías**: para cada vista (costado, frente, aérea) elige *Archivo* o *Cámara*. Con **Detectar cámaras** aparecen las cámaras conectadas con su nombre; asigna una a cada vista y define **Capturar cada N** segundos o minutos. Cada toma guarda las vistas con cámara en el mismo instante y sigue capturando mientras llenas los pasos 2 y 3. Elige qué toma analizar (por defecto, la más reciente).
   2. **Tarea**: identificador, tipo de tarea (levantamiento, transporte con o sin auxiliar), carga, agarre, postura y tipo de trabajo.
   3. **Lo que la foto no muestra**: ajustes REBA observados en piso, resumen de lo que se va a analizar y **Analizar postura**.

   Las tomas se guardan solo en este equipo, en `capturas/<borrador>/` dentro de la carpeta de datos, con un máximo de 120 por evaluación; se borran a las 24 h o con **Descartar tomas**. Al analizar, la toma elegida se copia al caso y queda registrada en su contexto.

   **Privacidad de tomas y archivos**: antes de guardar una imagen, ErgoAI detecta la pose original, ubica la cabeza (nariz, ojos, orejas y boca, con margen) y la difumina con mosaico y desenfoque; si no hay pose, usa el detector de rostros de MediaPipe (BlazeFace). Esto aplica tanto a cámara como a fotografías subidas. En disco solo queda la imagen protegida. La pose medida antes de difuminar se guarda en `<vista>.pose.json`, ligada a la imagen por SHA-256, y el análisis la reutiliza para no perder precisión en el cuello. Si el detector no está disponible, la imagen no se guarda. La vista previa en vivo no se almacena.
3. **Caso**: goniómetro con el REBA medido (aguja sólida) y el residual esperado (aguja punteada), más cuatro pestañas:
   - **Recomendaciones**: aprueba, edita, rechaza con motivo o agrega controles; **Aprobar informe** se habilita cuando no quedan pendientes. Las propuestas se dibujan punteadas y las aprobadas con trazo sólido.
   - **Postura medida**: ángulos por segmento con su banda REBA; el especialista puede corregir un ángulo y ErgoAI recalcula y lo registra.
   - **Bitácora**: historial firmado con verificación de la cadena SHA-256.
   - **Informe**: vista previa, impresión a PDF y CSV para el formato 00014.

Escribe tu nombre en **Firmas como**: cada decisión queda registrada con él. La interfaz anterior de Tk sigue disponible con `uv run ergoai-tk`.

#### Desarrollo de la interfaz

```powershell
uv run python scripts/iniciar_ergoai.py --sin-navegador  # API en 127.0.0.1:8765
cd web
npm install
npm run dev                           # Vite con proxy a /api
npm run build                         # recompila src/ergoai/web/dist
```

La interfaz usa React 19, Tailwind CSS 4 y componentes de [Magic UI](https://github.com/magicuidesign/magicui) (contador, haces animados, rejilla, lista animada, botón con brillo) y [Cult UI](https://github.com/nolly-studio/cult-ui) (pestañas con dirección, formulario emergente, controles segmentados, interruptores y avisos), adaptados a la paleta del proyecto. Sus licencias MIT están en `web/LICENCIAS-TERCEROS.md`.

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
uv run python scripts/evaluar_precision.py --plantilla data/validacion/caso01
uv run python scripts/anotar_manual.py data/validacion/caso01/costado.jpg --vista costado
uv run python scripts/evaluar_precision.py
```

El protocolo está en [`docs/PROTOCOLO_VALIDACION.md`](docs/PROTOCOLO_VALIDACION.md). El reporte se escribe en `out/precision/reporte.html` y separa los casos de validación de los casos de la interfaz.

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
| Fase 2 — Vectores y ángulos | Implementada | Medición 2D, orientación, respaldos entre vistas/3D y anotaciones con flechas, color REBA y etiquetas junto a cada articulación. Las flexiones 3D de respaldo se marcan con menor confianza. |
| Fase 3 — REBA | Implementada | Bandas, tablas A/B/C, ambos lados, contexto, overrides y `resultado.json`. |
| Fase 4 — Precisión | Pendiente de datos | Protocolo, plantillas y reporte HTML/CSV disponibles. Falta correr la validación con fotografías/referencias reales y demostrar la meta ≥90 %. |
| Fase 5 — Complementos | Parcial | Módulos base de RULA, EAWS, NOM-036 y muñeca; no alteran REBA. Falta integrar los complementos a la interfaz y validar HandLandmarker con referencias reales. |
| Informe y recomendaciones | Implementada | Motor de reglas NOM-036-1 + Jabil con jerarquía de controles, fundamento y Δ REBA por recomendación; informe HTML y CSV 00014. |
| Riesgo residual | Implementada | REBA recalculado con los efectos declarados de los controles no rechazados; las medidas administrativas no cuentan. |
| Validación del especialista | Implementada | Aprobar/rechazar/editar/agregar con bitácora encadenada por hash; el informe se reabre ante cualquier cambio. |
| Interfaz | Implementada | Interfaz web local (FastAPI + React) con evaluación, corrección de ángulos, validación, bitácora e informe. Tk queda como respaldo (`ergoai-tk`). |

## Alcance y limitaciones de la beta

- **MediaPipe en Linux con PipeWire**: `import mediapipe` carga `sounddevice`, que vía PortAudio, ALSA y el JACK de PipeWire activa `module-rt`; ese módulo fija `RLIMIT_RTTIME` y el kernel termina el proceso con SIGKILL al crear el detector. ErgoAI no usa audio y bloquea ese import (`ergoai.pose.bloquear_audio_de_mediapipe`). Además, el detector corre en un proceso hijo (`ergoai.pose_aislada`): si se cierra, la API responde un error y sigue funcionando.
- Algunas aplicaciones lanzan procesos con `RLIMIT_RTTIME=0` (por ejemplo, la terminal integrada de la app de escritorio de Claude) y ahí MediaPipe no puede ejecutarse; abre ErgoAI desde el lanzador o una terminal normal.

- REBA es una ayuda de evaluación, no reemplaza al especialista ergonómico.
- Si un landmark o contexto requerido no está disponible, el sistema deja el resultado como pendiente; no rellena valores “típicos”.
- La precisión contra los casos de Jabil todavía debe medirse antes de usar el sistema para la competencia.
- RULA, EAWS, NOM-036 y muñeca experimental son complementos aislados: no modifican el REBA principal.

## Estructura relevante

```text
src/ergoai/       # Lógica de pose, ángulos, REBA, complementos, API local y GUI
web/              # Código fuente de la interfaz web (React + Tailwind)
config/           # Umbrales auditables
scripts/          # Descarga de modelo, referencia manual y precisión
tests/            # Pruebas deterministas sin fotografías confidenciales
```
