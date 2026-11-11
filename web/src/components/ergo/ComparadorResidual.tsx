import { motion, useReducedMotion } from "motion/react"

import { InfoTooltip, TituloConAyuda } from "@/components/ergo/InfoTooltip"
import type { RangoReba } from "@/lib/api"
import { colorRiesgo, textoRango } from "@/lib/dominio"
import { BANDAS_REBA, formatearComparacion } from "@/lib/useReba"
import { cn } from "@/lib/utils"

interface Props {
  inicial: number | null
  residual: number | null
  origen?: "agente" | "especialista"
  className?: string
  onAjustar?: (valor: number) => void
  ajustable?: boolean
  compacto?: boolean
  /** Mensaje accionable cuando no hay REBA inicial (p. ej. hay ángulos pero falta puntaje). */
  vacioAccion?: string
  /** Rango posible cuando falta un dato y no hay puntaje exacto. */
  rangoInicial?: RangoReba | null
  rangoResidual?: RangoReba | null
}

/** Comparador Medido hoy / Tras mejoras (criterio 7). */
export function ComparadorResidual({
  inicial, residual, origen = "agente", className, onAjustar, ajustable, compacto, vacioAccion, rangoInicial, rangoResidual,
}: Props) {
  const reducir = useReducedMotion() ?? false
  const cmp = formatearComparacion(inicial, residual)
  const maxBarra = 15
  const rangoI = inicial == null ? rangoInicial ?? null : null
  const rangoR = residual == null ? rangoResidual ?? null : null
  const sinDatos = inicial == null && !rangoI
  const estimado = Boolean(rangoI || rangoR)

  if (sinDatos && compacto) {
    return (
      <div className={cn("rounded-xl border border-rule bg-sheet p-4", className)}>
        <p className="text-[12px] font-semibold tracking-[0.08em] text-jabil-cyan uppercase">
          <TituloConAyuda clave="residual">Riesgo esperado tras mejoras</TituloConAyuda>
        </p>
        <p className="mt-2 text-[14px] leading-snug text-ink">
          <span className="font-medium">REBA medido</span>
          <InfoTooltip clave="reba" className="ml-1" />
          : pendiente de cálculo.
        </p>
        <p className="mt-1.5 text-[13px] leading-snug text-ink-soft">
          {vacioAccion ?? "Las cajas Medido / Tras mejoras aparecen cuando exista un REBA reportado."}
        </p>
      </div>
    )
  }

  return (
    <div className={cn("rounded-xl border border-rule bg-sheet", compacto ? "p-4" : "p-5", className)}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[12px] font-semibold tracking-[0.08em] text-jabil-cyan uppercase">
            <TituloConAyuda clave="residual">Riesgo esperado tras mejoras</TituloConAyuda>
          </p>
          <h3 className={cn("t-title text-jabil", compacto ? "text-[17px]" : "text-[20px]")}>
            Medido hoy vs tras mejoras
          </h3>
        </div>
        {origen === "especialista" && (
          <span className="etiqueta-estado bg-jabil/10 text-jabil">Ajuste manual</span>
        )}
      </div>

      <div className={cn("grid gap-3", compacto ? "grid-cols-2" : "sm:grid-cols-2 gap-4")}>
        <Columna titulo="Medido hoy" ayudaClave="inicial" {...cmp.inicial} rango={rangoI} max={maxBarra} reducir={reducir} compacto={compacto} />
        <Columna titulo="Tras mejoras" ayudaClave="residual" {...cmp.residual} rango={rangoR} max={maxBarra} reducir={reducir} destacado compacto={compacto} />
      </div>

      <div className="mt-4" role="img" aria-label="Escala REBA por niveles">
        <p className="mb-1.5 text-[12px] font-medium text-graphite">
          Escala REBA (1–15)
          <InfoTooltip clave="reba" className="ml-1" />
        </p>
        <div className="flex h-3 overflow-hidden rounded-full">
          {BANDAS_REBA.map((b) => (
            <div key={b.nivel} style={{ flexGrow: b.hasta - b.desde + 1, background: b.color }} title={`${b.nivel} (${b.desde}–${b.hasta}): ${b.accion}`} />
          ))}
        </div>
        <div className="mt-1.5 grid grid-cols-5 gap-1 text-[11px] leading-tight text-graphite sm:text-[12px]">
          {BANDAS_REBA.map((b) => (
            <span key={b.nivel} className="min-w-0 truncate" title={`${b.nivel} ${b.desde}–${b.hasta}: ${b.accion}`}>
              {b.nivel}<span className="t-num hidden sm:inline"> {b.desde === b.hasta ? b.desde : `${b.desde}–${b.hasta}`}</span>
            </span>
          ))}
        </div>
      </div>

      <p className="mt-3 text-[13px] leading-snug text-ink-soft">
        {sinDatos
          ? (vacioAccion ?? "Sin REBA calculado: completa el análisis o corrige ángulos pendientes.")
          : estimado
            ? textoEstimado(inicial, residual, rangoI, rangoR)
            : cmp.reduccion != null && cmp.reduccion > 0
              ? `Mejora proyectada: −${cmp.reduccion} pts${cmp.reduccionPct != null ? ` (${cmp.reduccionPct} %)` : ""}${cmp.mejoraNivel ? ` · ${cmp.inicial.nivel} → ${cmp.residual.nivel}` : ""}.`
              : cmp.reduccion === 0
                ? "Sin reducción con los controles vigentes."
                : "Aún no hay proyección: faltan controles con efecto medible."}
      </p>

      {ajustable && onAjustar && (
        <div className="mt-4 border-t border-rule-soft pt-3">
          {sinDatos ? (
            <p className="text-[13px] text-graphite">El ajuste estará disponible cuando exista un REBA medido.</p>
          ) : (
            <label className="block text-[13px] font-medium text-ink-soft">
              Ajustar riesgo esperado (si la IA fue optimista)
              <input
                type="range"
                min={1}
                max={15}
                step={1}
                value={residual ?? rangoR?.max ?? inicial ?? rangoI?.max ?? 1}
                onChange={(e) => onAjustar(Number(e.target.value))}
                className="slider-reba mt-3"
                aria-valuemin={1}
                aria-valuemax={15}
                aria-valuenow={residual ?? rangoR?.max ?? inicial ?? rangoI?.max ?? 1}
              />
              <span className="t-num mt-2 block text-[20px] text-jabil">{residual ?? (rangoR ? textoRango(rangoR) : "—")}</span>
            </label>
          )}
        </div>
      )}
    </div>
  )
}

/** Pie del comparador cuando al menos un lado es un rango: no se resta un rango de otro. */
function textoEstimado(inicial: number | null, residual: number | null, rangoI: RangoReba | null, rangoR: RangoReba | null): string {
  const lado = (valor: number | null, rango: RangoReba | null) => (rango ? `entre ${rango.min} y ${rango.max}` : `en ${valor ?? "—"}`)
  const nivelI = rangoI ? rangoI.nivel : null
  const nivelR = rangoR ? rangoR.nivel : null
  const base = `Falta un dato: el REBA medido hoy queda ${lado(inicial, rangoI)} y tras mejoras ${lado(residual, rangoR)}.`
  if (rangoI && !rangoI.nivel) return `${base} Completa el dato en Postura medida para fijar el nivel.`
  return nivelI && nivelR && nivelI !== nivelR ? `${base} Nivel ${nivelI} → ${nivelR} en cualquier caso.` : base
}

function Columna({ titulo, ayudaClave, puntaje, nivel, color, accion, rango, max, reducir, destacado, compacto }: {
  titulo: string
  ayudaClave?: "inicial" | "residual" | "reba"
  puntaje: number | null
  nivel: string | null
  color: string
  accion: string
  /** Rango posible cuando falta un dato: se muestra «4–6» y el nivel como estimado. */
  rango?: RangoReba | null
  max: number
  reducir: boolean
  destacado?: boolean
  compacto?: boolean
}) {
  const tono = rango ? colorRiesgo(rango.nivel) : color
  const etiqueta = rango ? (rango.nivel ? `${rango.nivel}, estimado` : "Nivel por confirmar") : nivel ?? "Pendiente de cálculo"
  const detalle = rango ? "Falta un dato para el valor exacto" : puntaje == null ? "Completa el análisis" : `Estatus: ${accion}`
  const firme = ((rango ? rango.min : puntaje ?? 0) / max) * 100
  const posible = rango ? ((rango.max - rango.min) / max) * 100 : 0
  return (
    <div className={cn("rounded-lg border", compacto ? "p-3" : "p-4", destacado ? "border-jabil/30 bg-jabil/[0.04]" : "border-rule-soft bg-slate-50")}>
      <p className="flex items-center gap-1 text-[12px] font-medium text-graphite">
        {titulo}
        {ayudaClave && <InfoTooltip clave={ayudaClave} />}
      </p>
      <p className={cn("t-num leading-none", compacto ? "mt-1 text-[28px]" : "mt-1 text-[36px]")} style={{ color: tono }}>
        {rango ? textoRango(rango) : puntaje ?? "—"}
      </p>
      <p className="mt-1 text-[13px] font-semibold" style={{ color: tono }}>
        {etiqueta}
        {!rango && puntaje != null && nivel ? <span className="font-normal text-graphite"> · {puntaje}</span> : null}
      </p>
      {!compacto && <p className="text-[12px] text-graphite">{detalle}</p>}
      <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-white" title={rango ? `Entre ${rango.min} y ${rango.max}` : undefined}>
        <motion.div
          className="h-full"
          style={{ background: tono }}
          initial={reducir ? false : { width: 0 }}
          animate={{ width: `${firme}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
        {rango && (
          <motion.div
            className="h-full opacity-40"
            style={{ background: tono }}
            initial={reducir ? false : { width: 0 }}
            animate={{ width: `${posible}%` }}
            transition={{ duration: 0.7, ease: "easeOut", delay: reducir ? 0 : 0.2 }}
          />
        )}
      </div>
    </div>
  )
}
