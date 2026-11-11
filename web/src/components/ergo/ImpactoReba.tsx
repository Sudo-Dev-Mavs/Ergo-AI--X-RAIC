import { ArrowRight, ShieldAlert } from "lucide-react"

import { InfoTooltip, TituloConAyuda } from "@/components/ergo/InfoTooltip"
import type { EstadoCaso } from "@/lib/api"
import { colorRiesgo, etiquetaReba, textoRango } from "@/lib/dominio"
import { esRiesgoAlto } from "@/lib/useReba"
import { cn } from "@/lib/utils"

/** Bloque compacto Antes → Después para que el juez vea el valor sin buscar. */
export function ImpactoReba({ estado, className }: { estado: EstadoCaso; className?: string }) {
  const reba = estado.resultado.reba
  const residual = estado.residual
  const inicial = reba.final.reportado
  const nivelInicial = reba.nivel_riesgo
  const rangoInicial = inicial == null ? reba.final.rango ?? null : null
  const residualN = residual.residual.reba
  const nivelResidual = residual.residual.nivel_riesgo
  const rangoResidual = residualN == null ? residual.residual.rango ?? null : null
  const alto = esRiesgoAlto(inicial) || (rangoInicial != null && rangoInicial.min >= 8)
  const vigentes = estado.validacion.recomendaciones.filter((r) => r.estado !== "obsoleta")
  const hayIngORed = vigentes.some((r) => r.estado === "aprobada" && (r.jerarquia === "ingenieria" || r.jerarquia === "rediseno"))
  const faltaIngORed = alto && !hayIngORed

  return (
    <div className={cn("rounded-[14px] border border-jabil/25 bg-sheet p-4 sm:p-5", className)}>
      <p className="text-[12px] font-semibold tracking-[0.1em] text-jabil-cyan uppercase">Impacto</p>
      <div className="mt-3 flex flex-wrap items-center gap-3 sm:gap-4">
        <CifraImpacto
          etiqueta="Hoy"
          valor={inicial != null ? String(inicial) : rangoInicial ? textoRango(rangoInicial) : "—"}
          nivel={nivelInicial ?? rangoInicial?.nivel ?? null}
          color={colorRiesgo(nivelInicial ?? rangoInicial?.nivel)}
        />
        <ArrowRight className="size-5 shrink-0 text-graphite" aria-hidden />
        <CifraImpacto
          etiqueta="Tras mejoras"
          valor={residualN != null ? String(residualN) : rangoResidual ? textoRango(rangoResidual) : "—"}
          nivel={nivelResidual ?? rangoResidual?.nivel ?? null}
          color={colorRiesgo(nivelResidual ?? rangoResidual?.nivel)}
          destacado
        />
        {(residual.reduccion_puntos != null || residual.reduccion_pct != null) && (
          <div className="min-w-[7rem] rounded-lg bg-jabil/[0.06] px-3 py-2">
            <p className="text-[11px] font-medium text-graphite">Reducción</p>
            <p className="t-num text-[22px] leading-none text-jabil">
              {residual.reduccion_puntos != null && residual.reduccion_puntos > 0 ? `−${residual.reduccion_puntos}` : "0"}
              {residual.reduccion_pct != null ? <span className="ml-1 text-[14px] font-semibold">({residual.reduccion_pct} %)</span> : null}
            </p>
          </div>
        )}
      </div>
      <p className="mt-3 text-[13px] leading-snug text-ink-soft">
        <TituloConAyuda clave="reba" className="inline-flex">REBA</TituloConAyuda>
        {" "}hoy {etiquetaReba(inicial, nivelInicial, rangoInicial)}
        {" → "}
        <TituloConAyuda clave="residual" className="inline-flex">esperado</TituloConAyuda>
        {" "}{etiquetaReba(residualN, nivelResidual, rangoResidual)}
        {residual.recomendaciones_aplicadas.length > 0
          ? ` con ${residual.recomendaciones_aplicadas.length} control${residual.recomendaciones_aplicadas.length === 1 ? "" : "es"} no rechazado${residual.recomendaciones_aplicadas.length === 1 ? "" : "s"}.`
          : "."}
      </p>
      {faltaIngORed && (
        <p className="mt-2 flex items-start gap-1.5 text-[13px] font-medium text-amber-950">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            <TituloConAyuda clave="nom036" className="inline-flex">NOM-036</TituloConAyuda>
            : con riesgo alto/muy alto hace falta al menos un control de ingeniería o rediseño aprobado, con responsable. Las medidas administrativas no bastan solas.
            <InfoTooltip clave="nom036" />
          </span>
        </p>
      )}
    </div>
  )
}

function CifraImpacto({
  etiqueta, valor, nivel, color, destacado,
}: {
  etiqueta: string
  valor: string
  nivel: string | null
  color: string
  destacado?: boolean
}) {
  return (
    <div className={cn("min-w-[6.5rem] rounded-lg border px-3 py-2", destacado ? "border-jabil/40 bg-jabil/[0.04]" : "border-rule")}>
      <p className="text-[11px] font-medium text-graphite">{etiqueta}</p>
      <p className="t-num text-[28px] leading-none" style={{ color }}>{valor}</p>
      <p className="mt-0.5 text-[12px] font-medium" style={{ color }}>{nivel ?? "Pendiente"}</p>
    </div>
  )
}
