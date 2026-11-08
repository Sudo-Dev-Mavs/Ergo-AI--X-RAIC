import { FilePlus2, RefreshCw } from "lucide-react"

import { BlurFade } from "@/components/magicui/blur-fade"
import { ReglaRiesgo } from "@/components/ergo/regla-riesgo"
import { api, type ResumenCaso } from "@/lib/api"
import { ir } from "@/lib/app"
import { colorRiesgo, etiquetaTarea, fechaCorta } from "@/lib/dominio"
import { useDatos } from "@/lib/useDatos"
import { cn } from "@/lib/utils"

export function CasosPage() {
  const { datos: casos, error, cargando, recargar } = useDatos(api.casos, [])
  const urgentes = (casos ?? []).filter((caso) => (caso.nivel_accion ?? 0) >= 3 && caso.estado_informe !== "aprobado")

  return (
    <div className="mx-auto max-w-[1180px]">
      <header className="flex flex-wrap items-end justify-between gap-6 border-b border-ink pb-6">
        <div>
          <h1 className="t-display text-[44px] sm:text-[56px]">Casos</h1>
          <p className="mt-3 max-w-[60ch] text-[16px] text-ink-soft">
            {casos == null
              ? "Cargando evaluaciones…"
              : casos.length === 0
                ? "Todavía no hay estaciones evaluadas."
                : urgentes.length > 0
                  ? `${urgentes.length === 1 ? "Un caso" : `${urgentes.length} casos`} de riesgo alto o muy alto ${urgentes.length === 1 ? "espera" : "esperan"} tu validación. Están primero en la lista.`
                  : "Ningún caso de riesgo alto espera validación."}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="boton-linea" onClick={() => void recargar()} disabled={cargando} aria-label="Actualizar lista">
            <RefreshCw className={cn("size-4", cargando && "animate-spin")} strokeWidth={1.75} />
          </button>
          <button className="boton-tinta" onClick={() => ir({ nombre: "nueva" })}>
            <FilePlus2 className="size-4" strokeWidth={1.75} /> Nueva evaluación
          </button>
        </div>
      </header>

      {error && <p role="alert" className="mt-6 rounded-lg border border-[var(--riesgo-muy-alto)] bg-sheet p-4 text-[14px]">{error}</p>}

      {casos && casos.length === 0 && <Vacio />}

      {casos && casos.length > 0 && (
        <div className="mt-2">
          <div className="hidden grid-cols-[minmax(0,1.4fr)_88px_minmax(0,1.6fr)_120px_130px] gap-6 px-4 pt-4 pb-2 text-[13px] text-graphite md:grid">
            <span>Caso</span><span className="text-right">REBA</span><span>Inicial y residual esperado</span><span>Por validar</span><span>Informe</span>
          </div>
          <ol>
            {casos.map((caso, indice) => (
              <BlurFade key={caso.caso_id} delay={0.04 * Math.min(indice, 8)}>
                <FilaCaso caso={caso} />
              </BlurFade>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

function FilaCaso({ caso }: { caso: ResumenCaso }) {
  const urgente = (caso.nivel_accion ?? 0) >= 3 && caso.estado_informe !== "aprobado"
  return (
    <li>
      <a href={`#/caso/${encodeURIComponent(caso.caso_id)}`}
        className="group grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-3 border-b border-rule px-4 py-5 transition-colors hover:bg-sheet md:grid-cols-[minmax(0,1.4fr)_88px_minmax(0,1.6fr)_120px_130px]">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <span className="size-2.5 shrink-0 rounded-full" style={{ background: colorRiesgo(caso.nivel_riesgo) }} aria-hidden />
            <span className="t-title truncate text-[19px] group-hover:underline group-hover:underline-offset-4">{caso.caso_id}</span>
          </div>
          <p className="mt-1 truncate pl-5 text-[14px] text-graphite">
            {etiquetaTarea(caso.tipo_tarea)}{caso.carga_kg ? `, ${caso.carga_kg} kg` : ""}
            <span className="hidden sm:inline">{`. Analizado ${fechaCorta(caso.fecha_analisis)}`}</span>
          </p>
        </div>
        <div className="text-right">
          <span className="t-num block text-[34px] leading-none" style={{ color: colorRiesgo(caso.nivel_riesgo) }}>{caso.reba ?? "—"}</span>
          <span className="text-[12px] text-graphite">{caso.nivel_riesgo ?? "Pendiente"}</span>
        </div>
        <div className="col-span-2 md:col-span-1">
          <ReglaRiesgo inicial={caso.reba} residual={caso.residual} nivel={caso.nivel_riesgo} nivelResidual={caso.nivel_residual} />
          <p className="mt-1 text-[13px] text-graphite">
            {caso.residual != null && caso.reba != null
              ? caso.residual < caso.reba ? `Baja a ${caso.residual} (${caso.nivel_residual}) con los controles propuestos` : "Sin reducción con los controles vigentes"
              : "Faltan datos para estimar el residual"}
          </p>
        </div>
        <div className="text-[14px]">
          {caso.por_validar > 0
            ? <span className={cn("t-num text-[22px]", urgente && "underline decoration-[var(--riesgo-alto)] decoration-2 underline-offset-4")}>{caso.por_validar}</span>
            : <span className="text-graphite">Ninguna</span>}
          {caso.por_validar > 0 && <span className="ml-1.5 text-graphite">de {caso.recomendaciones}</span>}
        </div>
        <div>
          <span className={cn("inline-flex rounded-md px-2.5 py-1 text-[13px] font-medium",
            caso.estado_informe === "aprobado" ? "trazo-tinta" : "trazo-lapiz text-ink-soft")}>
            {caso.estado_informe === "aprobado" ? "Aprobado" : "Borrador"}
          </span>
        </div>
      </a>
    </li>
  )
}

function Vacio() {
  return (
    <div className="mt-16 grid gap-10 md:grid-cols-[1fr_1fr] md:items-center">
      <div>
        <h2 className="t-title text-[28px]">Empieza con las fotos de una estación</h2>
        <p className="mt-3 max-w-[52ch] text-[16px] text-ink-soft">
          Sube las vistas de costado y de frente; la aérea agrega la torsión del tronco. ErgoAI mide los ángulos, calcula el REBA,
          propone controles según la NOM-036-1 y deja todo listo para que lo valides.
        </p>
        <button className="boton-tinta mt-6" onClick={() => ir({ nombre: "nueva" })}>
          <FilePlus2 className="size-4" strokeWidth={1.75} /> Nueva evaluación
        </button>
      </div>
      <ol className="space-y-3 text-[15px]">
        {["Sube fotos sin rostros, de frente, costado y aérea.", "Revisa el REBA y los ángulos medidos; corrige los que no coincidan con piso.", "Aprueba, edita o rechaza cada control propuesto.", "Aprueba el informe con el riesgo residual esperado."].map((paso, i) => (
          <li key={paso} className="flex gap-4 border-t border-rule pt-3">
            <span className="t-num text-[20px] text-graphite">{i + 1}</span>
            <span className="text-ink-soft">{paso}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
