# Demo hackathon · ErgoAI (Track 4 Jabil)

## Pitch en una frase

Fotos locales → pose MediaPipe → REBA → controles NOM-036 → el ingeniero firma → acción de piso (CSV 00014). Sin nube, con trazabilidad HMAC.

## Casos «show» (este equipo)

| Caso | REBA | Por qué |
|---|---|---|
| `caso-20261108-2129` | 10 Alto · levantamiento | Mejor historia: riesgo alto + NOM exige ingeniería/rediseño |
| `caso-20261111-1006` | 9 Alto · respaldo | Segundo ejemplo si el primero ya está aprobado |

Los casos de prueba incompletos (`prueba01`, `prueba02`) conviene borrarlos antes de la demo (Inicio → basurero / Eliminar caso).

## Guion ~3 minutos

1. **(20 s) Privacidad** — «Todo corre en `127.0.0.1`; rostros difuminados; sin nube.»
2. **(40 s) Nueva evaluación** — Fotos costado/frente/(aérea) → *Asignar vistas* → *Proponer desde las fotos* → Analizar.
3. **(40 s) Impacto** — Abrir el caso: bloque **Antes → Después**, goniometro, residual y Δ REBA.
4. **(50 s) Validación HITL** — Aprobar ingeniería/rediseño (atajo *Aprobar ingeniería y rediseño* si aplica), rechazar una administrativa con motivo, *Aprobar acciones de piso*.
5. **(30 s) Evidencia** — Bitácora íntegra + Informe / CSV 00014.

## Límites (decir con calma)

Una foto no prueba kg exactos, estática >1 min ni repetición: el especialista confirma en piso. Eso es madurez, no debilidad.

## Checklist pre-demo

- [ ] Nombre en «Firmas como»
- [ ] Solo casos show en la lista
- [ ] Caso alto con costado+frente (aérea si hay)
- [ ] Preferencias: confirmar acciones ON (diálogo moderno)
- [ ] Servidor local arriba (`ergoai-gui` o `python -m ergoai.servidor`)
