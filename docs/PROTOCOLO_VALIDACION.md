# Protocolo de validación de precisión · ErgoAI beta

Cómo armar el conjunto de validación, generar la referencia y medir la precisión de ErgoAI con los mismos criterios que califica la rúbrica del Track 4. Las pruebas automáticas (`uv run pytest`) verifican el código con datos sintéticos; **no** sustituyen esta medición con fotos reales.

## 1. Qué se mide

| Métrica | Definición | Meta de la rúbrica |
|---|---|---|
| **Criterio 1**: REBA y nivel | Casos en los que el puntaje REBA final **y** el nivel de riesgo del sistema coinciden con la referencia de Jabil. | 6 de 6 → Excelente (19-20); 5 → Bueno (15-18); 4 → Suficiente (11-14); 3 o menos → Insuficiente |
| **Criterio 2**: ángulos | Porcentaje de segmentos principales (tronco, cuello, brazo, codo, muñeca, rodilla) cuyo ángulo cae en la **misma banda REBA** que la referencia. Un segmento que el sistema no estimó cuenta como fallo. | ≥ 90 % → Excelente (14-15); 75-89 % → Bueno; 60-74 % → Suficiente; menos de 60 % → Insuficiente |

El reporte también da, como diagnóstico:

- error absoluto medio y máximo por segmento;
- precisión por vista;
- el criterio 2 contando solo los segmentos estimados;
- los ajustes REBA (torsión, inclinación lateral, abducción, giro de cuello, apoyo), que se reportan aparte;
- cuántas medidas salieron de un respaldo (otra vista o la pose 3D).

La banda de cada ángulo se calcula igual para el sistema y para la referencia (`ergoai.reba.banda_medida`), con los umbrales de `config/umbrales.yaml`.

## 2. Conjunto de validación

**Composición mínima**:

- 6 casos o más, con al menos uno de cada tipo de tarea: levantamiento, transporte con auxiliar y transporte sin auxiliar.
- Cada caso con vista de **costado** y de **frente**; la **aérea** cuando exista, porque sin ella la torsión sale del respaldo 3D.
- Conviene que estén representados varios niveles de riesgo (bajo, medio y alto o muy alto).

**Estructura** (la carpeta `data/` no se versiona):

```text
data/validacion/
  caso01/
    costado.jpg   frente.jpg   aerea.jpg     # las vistas disponibles, sin rostros
    contexto.json                             # mismo formato que un caso normal (README → Línea de comandos)
    referencia.json                           # la referencia (sección 4)
  caso02/
  ...
```

**Confidencialidad**: las fotos de Jabil se usan solo para el reto, no se suben al repositorio ni se comparten fuera del equipo. Si se capturan fotos propias de estaciones simuladas, deben ir sin rostros o con el rostro difuminado: las tomas de cámara de ErgoAI ya se guardan así.

## 3. Captura de fotos propias (si no son de Jabil)

- **Costado**: la cámara perpendicular al plano sagital del operador, a la altura de la cadera (unos 1 m), a 2–4 m de distancia y con el cuerpo completo en cuadro, de los pies a la cabeza.
- **Frente**: la cámara frente al operador, con las mismas condiciones.
- **Aérea**: la cámara cenital, sobre el operador, con hombros y caderas visibles.
- Buena iluminación, sin piezas ni mamparas que tapen codos, muñecas o rodillas, y con la postura sostenida en el instante crítico de la tarea.
- Si la cámara quedó inclinada, se puede anotar una vertical real en el contexto (`vertical_referencia`, dos puntos en píxeles por vista) para corregirla.
- Anotar en `contexto.json` la carga real, el agarre y los ajustes de actividad observados en piso.

## 4. Referencia

Crea la plantilla y complétala **sin mirar el resultado de ErgoAI** (evaluación a ciegas):

```powershell
uv run python scripts/evaluar_precision.py --plantilla data/validacion/caso01
```

Fuentes válidas, en orden de preferencia:

1. **Estudio de Jabil**: puntaje y nivel REBA de su evaluación (criterio 1) y los ángulos de su estudio o de su hoja de evaluación (criterio 2).
   ```json
   {
     "fuente": "Estudio Jabil, hoja 16-PE80-6500-00014, estación 7",
     "reba": {"puntaje": 9, "nivel": "Alto"},
     "angulos": [
       {"medida": "tronco_flexion", "lado": null, "valor_deg": 35},
       {"medida": "brazo_flexion", "lado": "R", "valor_deg": 70}
     ]
   }
   ```
   Si solo se conoce el puntaje, `nivel` puede omitirse: se deriva de la tabla REBA.
2. **Medición del especialista**: los ángulos medidos con goniómetro en piso o con un transportador digital sobre la foto, en el mismo formato `angulos`.
3. **Landmarks anotados a mano**: con `scripts/anotar_manual.py` se marcan las articulaciones con clics (Enter termina, R deshace) y ErgoAI calcula los ángulos con sus fórmulas. Esto mide el error del **detector de pose**, no del método, así que úsalo solo cuando no haya referencia de Jabil ni del especialista.
   ```powershell
   uv run python scripts/anotar_manual.py data/validacion/caso01/costado.jpg --vista costado
   ```

**Convenciones de `angulos`**:

- Medidas válidas: `tronco_flexion`, `cuello_flexion`, `brazo_flexion`, `codo_flexion`, `muneca_flexion_extension`, `rodilla_flexion`, más los ajustes `tronco_torsion`, `tronco_inclinacion_lateral`, `brazo_abduccion`, `cuello_inclinacion_rotacion` y `apoyo_piernas_unilateral` (0 o 1).
- `lado` es `"L"` (izquierdo del operador) o `"R"`; `null` para tronco y cuello.
- Flexión positiva y extensión negativa. El codo es el ángulo entre brazo y antebrazo: 0° es el brazo recto.
- Deja `valor_deg: null` en lo que no se midió; no se cuenta.

Registra en `fuente` quién hizo la referencia, cuándo y con qué método.

## 5. Procedimiento

```powershell
uv sync
uv run python scripts/descargar_modelo.py
uv run python scripts/evaluar_precision.py            # evalúa data/validacion y escribe out/precision/
uv run python scripts/evaluar_precision.py --reusar   # solo recalcula el reporte con los resultados existentes
```

En `out/precision/` quedan:

- `reporte.html`: tarjetas de los criterios 1 y 2 con el nivel de la rúbrica que corresponde, tabla por caso, tabla por segmento y la lista de segmentos fuera de banda o sin estimar con sus banderas;
- `precision.csv`: una fila por ángulo comparado;
- `resumen.json`: métricas y detalle completo;
- `<caso>/`: los resultados, informes e imágenes anotadas de cada caso, separados de los casos de la interfaz.

En Linux, ejecútalo desde una terminal normal y no desde la terminal integrada de un IDE que limite procesos en tiempo real (README → Solución de problemas).

## 6. Interpretación y ajustes

- **Un segmento fuera de banda**:
  - revisa sus banderas en el reporte: `cerca_de_umbral` (a menos de 5° del límite), `baja_visibilidad`, `posible_escorzo` (el segmento sale del plano de la foto), `vista_respaldo` (vino de otra vista o de la pose 3D) y `baja_confianza_metodo`;
  - revisa también la imagen `out/precision/<caso>/<vista>_angulos.png`.
- **Muchos fallos en un mismo segmento**:
  - revisa los umbrales marcados `SUPUESTO` en `config/umbrales.yaml` (tolerancia de «erguido», límites inclusivos, offset neutro del cuello) y confírmalos con Jabil;
  - comprueba la orientación del costado (`orientacion_costado`).
- **Criterio 1 falla con ángulos correctos**: casi siempre es contexto (carga, agarre, ajustes de actividad, hombro elevado, muñeca desviada). Compáralo con la hoja de Jabil.
- **No ajustes umbrales para «pasar» un caso concreto.** Si cambias un umbral, vuelve a correr todos los casos y documenta el cambio y el motivo.

## 7. Registro

Guarda con cada corrida:

- el `reporte.html`;
- la fecha;
- el commit del código (`git rev-parse --short HEAD`);
- la versión de `config/umbrales.yaml`.

Los números que se presenten en la documentación técnica o en el pitch deben salir de un reporte guardado.
