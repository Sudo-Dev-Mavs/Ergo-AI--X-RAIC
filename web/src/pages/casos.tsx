import { FilePlus2, RefreshCw } from "lucide-react"

import { BlurFade } from "@/components/magicui/blur-fade"
import { ReglaRiesgo } from "@/components/ergo/regla-riesgo"
import { api, type ResumenCaso } from "@/lib/api"
import { ir } from "@/lib/app"
import { colorRiesgo, etiquetaTarea, fechaCorta } from "@/lib/dominio"
import { useDatos } from "@/lib/useDatos"
import { cn } from "@/lib/utils"

const PASOS = [
  "Sube fotos sin rostros, de frente, costado y aérea, o captúralas con las cámaras conectadas.",
  "Revisa el REBA y los ángulos medidos; corrige los que no coincidan con piso.",
  "Aprueba, edita o rechaza cada control propuesto.",
  "Aprueba el informe con el riesgo residual esperado.",
]

/** Pantalla principal: cómo empezar a la izquierda y los casos evaluados al costado. */
export function CasosPage() {
  const { datos: casos, error, cargando, recargar } = useDatos(api.casos, [])
  const urgentes = (casos ?? []).filter((caso) => (caso.nivel_accion ?? 0) >= 3 && caso.estado_informe !== "aprobado")

  return (
    <div className="mx-auto max-w-[1280px]">
      <header className="border-b border-ink pb-6">
        <h1 className="t-display text-[40px] sm:text-[56px]">Evaluación ergonómica</h1>
        <p className="mt-3 max-w-[64ch] text-[16px] text-ink-soft">
          {casos == null
            ? "Cargando evaluaciones…"
            : casos.length === 0
              ? "Todavía no hay estaciones evaluadas."
              : urgentes.length > 0
                ? `${urgentes.length === 1 ? "Un caso" : `${urgentes.length} casos`} de riesgo alto o muy alto ${urgentes.length === 1 ? "espera" : "esperan"} tu validación.`
                : `${casos.length} ${casos.length === 1 ? "estación evaluada" : "estaciones evaluadas"}; ningún caso de riesgo alto espera validación.`}
        </p>
      </header>

      <div className="mt-10 grid grid-cols-[minmax(0,1fr)] gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(360px,440px)] lg:items-start">
        <section aria-labelledby="empezar" className="min-w-0">
          <h2 id="empezar" className="t-title max-w-[22ch] text-[28px] sm:text-[32px]">Empieza con las fotos de una estación</h2>
          <p className="mt-3 max-w-[56ch] text-[16px] text-ink-soft">
            Sube las vistas de costado y de frente; la aérea agrega la torsión del tronco. ErgoAI mide los ángulos, calcula el REBA,
            propone controles según la NOM-036-1 y deja todo listo para que lo valides.
          </p>
          <button className="boton-tinta mt-6" onClick={() => ir({ nombre: "nueva" })}>
            <FilePlus2 className="size-4" strokeWidth={1.75} /> Nueva evaluación
          </button>
          <ol className="mt-10 max-w-[620px]">
            {PASOS.map((paso, i) => (
              <li key={paso} className="flex gap-4 border-t border-rule py-3.5 last:border-b">
                <span className="t-num w-5 shrink-0 text-[20px] leading-6 text-graphite">{i + 1}</span>
                <span className="text-[15px] leading-6 text-ink-soft">{paso}</span>
              </li>
            ))}
          </ol>
        </section>

        <aside aria-labelledby="titulo-casos" className="hoja flex min-h-0 min-w-0 flex-col lg:sticky lg:top-8 lg:max-h-[calc(100dvh-4rem)]">
          <div className="flex items-start justify-between gap-3 border-b border-rule px-5 pt-5 pb-4">
            <div>
              <h2 id="titulo-casos" className="t-title text-[20px]">
                Casos evaluados{casos && casos.length > 0 && <span className="t-num ml-2 text-[18px] text-graphite">{casos.length}</span>}
              </h2>
              <p className="mt-0.5 text-[13px] text-graphite">Los de mayor riesgo sin validar van primero.</p>
            </div>
            <button className="boton-linea px-2.5" onClick={() => void recargar()} disabled={cargando} aria-label="Actualizar casos">
              <RefreshCw className={cn("size-4", cargando && "animate-spin")} strokeWidth={1.75} />
            </button>
          </div>

          {error && <p role="alert" className="m-4 rounded-lg border border-[var(--riesgo-muy-alto)] p-3 text-[14px]">{error}</p>}

          {casos && casos.length === 0 && (
            <div className="px-5 py-10 text-center">
              <p className="text-[15px] text-ink-soft">Aquí aparecerán las estaciones que evalúes, con su REBA y el estado de validación.</p>
            </div>
          )}

          {casos && casos.length > 0 && (
            <ol className="min-h-0 flex-1 overflow-y-auto" aria-label="Casos evaluados">
              {casos.map((caso, indice) => (
                <BlurFade key={caso.caso_id} delay={0.04 * Math.min(indice, 8)}>
                  <FilaCaso caso={caso} />
                </BlurFade>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </div>
  )
}

function FilaCaso({ caso }: { caso: ResumenCaso }) {
  const urgente = (caso.nivel_accion ?? 0) >= 3 && caso.estado_informe !== "aprobado"
  return (
    <li className="border-b border-rule-soft last:border-b-0">
      <a href={`#/caso/${encodeURIComponent(caso.caso_id)}`} className="group block px-5 py-4 transition-colors hover:bg-vellum/60">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: colorRiesgo(caso.nivel_riesgo) }} aria-hidden />
              <span className="t-title truncate text-[16px] group-hover:underline group-hover:underline-offset-4">{caso.caso_id}</span>
            </div>
            <p className="mt-0.5 truncate pl-[18px] text-[13px] text-graphite">
              {etiquetaTarea(caso.tipo_tarea)}{caso.carga_kg ? `, ${caso.carga_kg} kg` : ""}, {fechaCorta(caso.fecha_analisis)}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <span className="t-num block text-[28px] leading-none" style={{ color: colorRiesgo(caso.nivel_riesgo) }}>{caso.reba ?? "—"}</span>
            <span className="text-[12px] text-graphite">{caso.nivel_riesgo ?? "Pendiente"}</span>
          </div>
        </div>
        <ReglaRiesgo className="mt-2" inicial={caso.reba} residual={caso.residual} nivel={caso.nivel_riesgo} nivelResidual={caso.nivel_residual} />
        <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[13px]">
          <span className="text-graphite">
            {caso.residual != null && caso.reba != null
              ? caso.residual < caso.reba ? `Residual ${caso.residual} (${caso.nivel_residual})` : "Sin reducción"
              : "Residual pendiente"}
          </span>
          <span className="flex items-center gap-2">
            {caso.por_validar > 0 && (
              <span className={cn("text-ink-soft", urgente && "font-medium text-ink underline decoration-[var(--riesgo-alto)] decoration-2 underline-offset-4")}>
                <span className="t-num">{caso.por_validar}</span> por validar
              </span>
            )}
            <span className={cn("rounded-md px-2 py-0.5 text-[12px] font-medium", caso.estado_informe === "aprobado" ? "trazo-tinta" : "trazo-lapiz text-ink-soft")}>
              {caso.estado_informe === "aprobado" ? "Aprobado" : "Borrador"}
            </span>
          </span>
        </div>
      </a>
    </li>
  )
}
