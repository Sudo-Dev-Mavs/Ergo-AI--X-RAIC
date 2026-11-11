/**
 * Niveles REBA (Hignett y McAtamney, 2000) + reglas NOM-036-1-STPS-2018.
 * Separado del cálculo de pose (visión) y del motor de recomendaciones.
 */

export type NivelReba =
  | "Inapreciable"
  | "Bajo"
  | "Medio"
  | "Alto"
  | "Muy alto"

export interface BandaReba {
  nivel: NivelReba
  desde: number
  hasta: number
  /** Token CSS / hex del semáforo corporativo */
  color: string
  colorTailwind: string
  accion: string
  urgencia: "ninguna" | "posible" | "necesaria" | "pronto" | "inmediata"
}

/** Los 5 niveles exactos de la regla de negocio del hackathon. */
export const BANDAS_REBA: readonly BandaReba[] = [
  { nivel: "Inapreciable", desde: 1, hasta: 1, color: "var(--riesgo-inapreciable)", colorTailwind: "bg-emerald-800", accion: "Sin cambios requeridos en el puesto", urgencia: "ninguna" },
  { nivel: "Bajo", desde: 2, hasta: 3, color: "var(--riesgo-bajo)", colorTailwind: "bg-emerald-500", accion: "Puede requerir ajustes menores", urgencia: "posible" },
  { nivel: "Medio", desde: 4, hasta: 7, color: "var(--riesgo-medio)", colorTailwind: "bg-amber-400", accion: "Requiere cambios en el puesto", urgencia: "necesaria" },
  { nivel: "Alto", desde: 8, hasta: 10, color: "var(--riesgo-alto)", colorTailwind: "bg-orange-500", accion: "Requiere cambios pronto en el puesto", urgencia: "pronto" },
  { nivel: "Muy alto", desde: 11, hasta: 15, color: "var(--riesgo-muy-alto)", colorTailwind: "bg-red-600", accion: "Requiere cambios inmediatos en el puesto", urgencia: "inmediata" },
] as const

export const UMBRAL_RIESGO_ALTO = 8

export function bandaReba(puntaje: number | null | undefined): BandaReba | null {
  if (puntaje == null || Number.isNaN(puntaje)) return null
  const entero = Math.round(puntaje)
  return BANDAS_REBA.find((b) => entero >= b.desde && entero <= b.hasta) ?? null
}

export function nivelReba(puntaje: number | null | undefined): NivelReba | null {
  return bandaReba(puntaje)?.nivel ?? null
}

export function colorReba(puntaje: number | null | undefined): string {
  return bandaReba(puntaje)?.color ?? "var(--riesgo-pendiente)"
}

export function esRiesgoAlto(puntaje: number | null | undefined): boolean {
  return puntaje != null && puntaje >= UMBRAL_RIESGO_ALTO
}

export type JerarquiaControl = "ingenieria" | "rediseno" | "administrativa"

export interface ControlPropuesto {
  id: string
  jerarquia: JerarquiaControl
  estado?: string
  solucion?: string
}

/**
 * NOM-036: con REBA ≥ 8 está prohibido un paquete solo administrativo
 * (rotación de personal / pausas activas / capacitación sin ingeniería).
 */
export function cumpleNom036(puntaje: number | null | undefined, controles: ControlPropuesto[]): {
  ok: boolean
  motivo: string | null
  exigeIngenieria: boolean
} {
  const exigeIngenieria = esRiesgoAlto(puntaje)
  if (!exigeIngenieria) return { ok: true, motivo: null, exigeIngenieria: false }

  const vigentes = controles.filter((c) => c.estado !== "rechazada" && c.estado !== "obsoleta")
  const tieneIngenieria = vigentes.some((c) => c.jerarquia === "ingenieria" || c.jerarquia === "rediseno")
  if (tieneIngenieria) return { ok: true, motivo: null, exigeIngenieria: true }

  return {
    ok: false,
    motivo: `REBA ${puntaje}: la NOM-036-1 exige controles de ingeniería o rediseño; rotación/pausas no bastan.`,
    exigeIngenieria: true,
  }
}

export function formatearComparacion(inicial: number | null, residual: number | null) {
  const bandaInicial = bandaReba(inicial)
  const bandaResidual = bandaReba(residual)
  const delta = inicial != null && residual != null ? inicial - residual : null
  return {
    inicial: { puntaje: inicial, nivel: bandaInicial?.nivel ?? null, color: bandaInicial?.color ?? "var(--riesgo-pendiente)", accion: bandaInicial?.accion ?? "Pendiente" },
    residual: { puntaje: residual, nivel: bandaResidual?.nivel ?? null, color: bandaResidual?.color ?? "var(--riesgo-pendiente)", accion: bandaResidual?.accion ?? "Pendiente" },
    reduccion: delta,
    reduccionPct: inicial && residual != null ? Math.round((100 * (inicial - residual)) / inicial) : null,
    mejoraNivel: Boolean(bandaInicial && bandaResidual && BANDAS_REBA.indexOf(bandaResidual) < BANDAS_REBA.indexOf(bandaInicial)),
  }
}

/** Hook de presentación: formatea REBA + cumplimiento NOM-036 para el dashboard. */
export function useReba(
  inicial: number | null | undefined,
  residual: number | null | undefined,
  controles: ControlPropuesto[] = [],
) {
  const comparacion = formatearComparacion(inicial ?? null, residual ?? null)
  const nom036 = cumpleNom036(inicial, controles)
  return {
    ...comparacion,
    nom036,
    bandas: BANDAS_REBA,
    semaforo: (puntaje: number | null | undefined) => {
      if (puntaje == null) return "pendiente" as const
      if (puntaje >= 11) return "rojo" as const
      if (puntaje >= 8) return "naranja" as const
      if (puntaje >= 4) return "amarillo" as const
      if (puntaje >= 2) return "verde" as const
      return "verde-oscuro" as const
    },
  }
}
