import { ChevronDown, FilePlus2, RefreshCw } from "lucide-react"
import { useState } from "react"

import { BlurFade } from "@/components/magicui/blur-fade"
import { ReglaRiesgo } from "@/components/ergo/regla-riesgo"
import { api, type ResumenCaso } from "@/lib/api"
import { ir } from "@/lib/app"
import { colorPuntoCaso, colorRiesgo, etiquetaReba, etiquetaTarea, fechaCorta } from "@/lib/dominio"
import { useDatos } from "@/lib/useDatos"
import { cn } from "@/lib/utils"

const PASOS = [
  { t: "Fotografiar", d: "Costado (obligatorio), frente y aérea. Sin rostros." },
  { t: "Medir", d: "Ángulos → REBA con niveles NOM-alineados." },
  { t: "Validar", d: "Apruebas, editas o rechazas cada control." },
  { t: "Actuar", d: "Informe con residual y acciones de piso." },
]

export function CasosPage() {
  const { datos: casos, error, cargando, recargar } = useDatos(api.casos, [])
  const urgentes = (casos ?? []).filter((c) => (c.nivel_accion ?? 0) >= 3 && c.estado_informe !== "aprobado")
  const sinReba = (casos ?? []).filter((c) => c.reba == null).length
  const [guiaAbierta, setGuiaAbierta] = useState(!(casos && casos.length > 0))

  const resumen = (() => {
    if (casos == null) return "Cargando evaluaciones…"
    if (casos.length === 0) return "Todavía no hay estaciones evaluadas."
    if (sinReba > 0) return `${casos.length} caso${casos.length === 1 ? "" : "s"} · ${sinReba} sin REBA calculado.`
    if (urgentes.length > 0) {
      return `${urgentes.length} de riesgo alto/muy alto esperan validación.`
    }
    return `${casos.length} estación${casos.length === 1 ? "" : "es"} · ningún riesgo alto pendiente.`
  })()

  return (
    <div className="mx-auto max-w-[1280px]">
      <header className="border-b border-rule pb-5">
        <div className="h-1 w-16 rounded-full bg-jabil-cyan" aria-hidden />
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[12px] font-semibold tracking-[0.14em] text-jabil-cyan uppercase">ErgoAI · Jabil</p>
            <h1 className="t-display mt-1 text-[36px] text-jabil sm:text-[48px]">Evaluaciones ergonómicas</h1>
            <p className="mt-2 max-w-[58ch] text-[15px] text-ink-soft">{resumen}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="boton-tinta" onClick={() => ir({ nombre: "nueva" })}>
              <FilePlus2 className="size-4" strokeWidth={1.75} /> Nueva evaluación
            </button>
            {urgentes.length > 0 && (
              <button type="button" className="boton-cian" onClick={() => ir({ nombre: "validacion", id: urgentes[0].caso_id })}>
                Validar urgentes
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)] lg:items-start">
        <section aria-labelledby="titulo-casos" className="hoja min-w-0 overflow-hidden shadow-[0_16px_40px_-28px_rgba(0,56,118,0.4)]">
          <div className="flex items-start justify-between gap-3 border-b border-rule px-5 py-4">
            <div>
              <h2 id="titulo-casos" className="t-title text-[20px] text-jabil">
                Casos{casos && casos.length > 0 && <span className="t-num ml-2 text-[18px] text-graphite">{casos.length}</span>}
              </h2>
              <p className="mt-0.5 text-[13px] text-graphite">Mayor riesgo sin validar primero.</p>
            </div>
            <button type="button" className="boton-linea px-2.5" onClick={() => void recargar()} disabled={cargando} aria-label="Actualizar lista de casos" title="Actualizar">
              <RefreshCw className={cn("size-4", cargando && "animate-spin")} strokeWidth={1.75} />
            </button>
          </div>

          {error && <p role="alert" className="m-4 rounded-lg border border-[var(--riesgo-muy-alto)] p-3 text-[14px]">{error}</p>}

          {casos && casos.length === 0 && (
            <div className="px-5 py-14 text-center">
              <p className="text-[15px] text-ink-soft">Aquí verás REBA, residual y estado de cada estación.</p>
              <button type="button" className="boton-tinta mt-4" onClick={() => ir({ nombre: "nueva" })}>
                <FilePlus2 className="size-4" /> Empezar
              </button>
            </div>
          )}

          {casos && casos.length > 0 && (
            <ol className="divide-y divide-rule-soft" aria-label="Casos evaluados">
              {casos.map((caso, i) => (
                <BlurFade key={caso.caso_id} delay={0.03 * Math.min(i, 8)}>
                  <FilaCaso caso={caso} />
                </BlurFade>
              ))}
            </ol>
          )}
        </section>

        <aside className="min-w-0">
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-xl border border-rule bg-sheet px-4 py-3 text-left"
            aria-expanded={guiaAbierta}
            onClick={() => setGuiaAbierta((v) => !v)}
          >
            <span className="t-title text-[16px] text-jabil">Cómo funciona</span>
            <ChevronDown className={cn("size-4 text-graphite transition-transform", guiaAbierta && "rotate-180")} />
          </button>
          {guiaAbierta && (
            <ol className="mt-3 space-y-0 rounded-xl border border-rule bg-sheet px-4">
              {PASOS.map((paso, i) => (
                <li key={paso.t} className="grid grid-cols-[2rem_1fr] gap-3 border-b border-rule-soft py-3 last:border-b-0">
                  <span className="t-num text-[18px] text-jabil-cyan">{i + 1}</span>
                  <div>
                    <p className="text-[14px] font-semibold text-jabil">{paso.t}</p>
                    <p className="text-[13px] text-ink-soft">{paso.d}</p>
                  </div>
                </li>
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
  const estadoPrincipal = caso.estado_informe === "aprobado"
    ? { texto: "Aprobado", cls: "bg-jabil text-white" }
    : caso.por_validar > 0
      ? { texto: `${caso.por_validar} por validar`, cls: cn("bg-amber-100 text-amber-950", urgente && "ring-1 ring-amber-400") }
      : { texto: "Borrador", cls: "bg-slate-100 text-ink-soft" }

  return (
    <li>
      <a href={`#/caso/${encodeURIComponent(caso.caso_id)}`} className="group flex items-stretch gap-3 px-5 py-4 transition-colors hover:bg-jabil/[0.03]">
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-full ring-2 ring-white" style={{ background: colorPuntoCaso(caso.reba) }} aria-hidden />
                <span className="t-title truncate text-[16px] text-jabil group-hover:underline group-hover:underline-offset-4">{caso.caso_id}</span>
              </div>
              <p className="mt-0.5 truncate pl-[18px] text-[13px] text-graphite">
                {etiquetaTarea(caso.tipo_tarea)}
                {caso.carga_kg != null ? ` · ${caso.carga_kg} kg` : ""}
                {caso.fecha_analisis ? ` · ${fechaCorta(caso.fecha_analisis)}` : ""}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <span className="t-num block text-[26px] leading-none" style={{ color: colorRiesgo(caso.nivel_riesgo) }}>
                {caso.reba ?? "—"}
              </span>
              <span className="text-[12px] text-graphite">{caso.reba == null ? "Pendiente de cálculo" : caso.nivel_riesgo}</span>
            </div>
          </div>
          {caso.reba != null && (
            <ReglaRiesgo className="mt-2" inicial={caso.reba} residual={caso.residual} nivel={caso.nivel_riesgo} nivelResidual={caso.nivel_residual} />
          )}
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[13px]">
            <span className="text-graphite">
              {caso.reba == null
                ? "REBA pendiente de cálculo"
                : caso.residual != null && caso.residual < caso.reba
                  ? `Residual ${etiquetaReba(caso.residual, caso.nivel_residual)}`
                  : "Sin reducción residual"}
            </span>
            <span className={cn("etiqueta-estado", estadoPrincipal.cls)}>{estadoPrincipal.texto}</span>
          </div>
        </div>
        <span className="boton-linea self-center shrink-0 px-3 py-2 text-[13px]">
          {caso.por_validar > 0 && caso.estado_informe !== "aprobado" ? "Validar" : "Abrir"}
        </span>
      </a>
    </li>
  )
}
