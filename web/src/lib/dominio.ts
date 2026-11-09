import type { Jerarquia, RangoReba, TipoTarea } from "./api"

/** Zonas REBA (Hignett y McAtamney, 2000). El color solo se usa para riesgo. */
export const ZONAS = [
  { nivel: "Inapreciable", desde: 1, hasta: 1, color: "var(--riesgo-inapreciable)", accion: "No necesaria" },
  { nivel: "Bajo", desde: 2, hasta: 3, color: "var(--riesgo-bajo)", accion: "Puede ser necesaria" },
  { nivel: "Medio", desde: 4, hasta: 7, color: "var(--riesgo-medio)", accion: "Necesaria" },
  { nivel: "Alto", desde: 8, hasta: 10, color: "var(--riesgo-alto)", accion: "Necesaria pronto" },
  { nivel: "Muy alto", desde: 11, hasta: 15, color: "var(--riesgo-muy-alto)", accion: "Necesaria de inmediato" },
] as const

export function colorRiesgo(nivel: string | null | undefined): string {
  return ZONAS.find((zona) => zona.nivel === nivel)?.color ?? "var(--riesgo-pendiente)"
}

export function accionRiesgo(nivel: string | null | undefined): string {
  return ZONAS.find((zona) => zona.nivel === nivel)?.accion ?? "Datos pendientes"
}

export const TAREAS: { valor: TipoTarea; etiqueta: string; corta: string }[] = [
  { valor: "levantamiento", etiqueta: "Levantamiento", corta: "Levantamiento" },
  { valor: "transporte_con_auxiliar", etiqueta: "Transporte con auxiliar", corta: "Con auxiliar" },
  { valor: "transporte_sin_auxiliar", etiqueta: "Transporte sin auxiliar", corta: "Sin auxiliar" },
  { valor: "otro", etiqueta: "Otra tarea", corta: "Otra" },
]

export const etiquetaTarea = (tipo: string | null | undefined) => TAREAS.find((t) => t.valor === tipo)?.etiqueta ?? "Otra tarea"

export const JERARQUIAS: { valor: Jerarquia; etiqueta: string; explicacion: string }[] = [
  { valor: "ingenieria", etiqueta: "Controles de ingeniería", explicacion: "Equipos o herramientas que eliminan el esfuerzo o la postura." },
  { valor: "rediseno", etiqueta: "Rediseño de estación", explicacion: "Alturas, alcances y distribución de la estación." },
  { valor: "administrativa", etiqueta: "Medidas administrativas", explicacion: "Complementan; no sustituyen a los controles anteriores." },
]

export const NOMBRE_MEDIDA: Record<string, string> = {
  tronco_flexion: "Flexión de tronco",
  tronco_torsion: "Torsión de tronco",
  tronco_inclinacion_lateral: "Inclinación lateral de tronco",
  cuello_flexion: "Flexión de cuello",
  cuello_inclinacion_rotacion: "Giro o inclinación de cuello",
  brazo_flexion: "Flexión de brazo",
  brazo_abduccion: "Abducción de brazo",
  codo_flexion: "Ángulo de codo",
  muneca_flexion_extension: "Flexión de muñeca",
  rodilla_flexion: "Flexión de rodilla",
  apoyo_piernas_unilateral: "Apoyo en una pierna",
}

export const SEGMENTO: Record<string, string> = {
  tronco_flexion: "Tronco", tronco_torsion: "Tronco", tronco_inclinacion_lateral: "Tronco",
  cuello_flexion: "Cuello", cuello_inclinacion_rotacion: "Cuello",
  brazo_flexion: "Brazos", brazo_abduccion: "Brazos", codo_flexion: "Antebrazos",
  muneca_flexion_extension: "Muñecas", rodilla_flexion: "Piernas", apoyo_piernas_unilateral: "Piernas",
}

export const NOMBRE_BANDERA: Record<string, string> = {
  baja_visibilidad: "baja visibilidad",
  cerca_de_umbral: "cerca del límite REBA",
  posible_escorzo: "posible escorzo",
  vista_respaldo: "medida de respaldo",
  baja_confianza_metodo: "método aproximado",
}

export const NOMBRE_ACCION: Record<string, string> = {
  generar: "Generó propuestas",
  agregar: "Agregó",
  aprobar: "Aprobó",
  rechazar: "Rechazó",
  reabrir: "Devolvió a propuesta",
  editar: "Editó",
  obsoleta: "Marcó como obsoleta",
  aprobar_informe: "Aprobó el informe",
  reabrir_informe: "Reabrió el informe",
  corregir_angulo: "Corrigió ángulos",
}

export function fechaCorta(iso: string | null | undefined): string {
  if (!iso) return "—"
  const fecha = new Date(iso)
  if (Number.isNaN(fecha.getTime())) return iso
  return fecha.toLocaleString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}

/** «5–7» o «6» para un rango REBA. */
export function textoRango(rango: RangoReba): string {
  return rango.min === rango.max ? String(rango.min) : `${rango.min}–${rango.max}`
}
