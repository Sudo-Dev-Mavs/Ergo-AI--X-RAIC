import { AlertTriangle, Check, Pencil, Plus, RotateCcw, X } from "lucide-react"
import { useState } from "react"

import { PopoverForm, PopoverFormButton } from "@/components/cult/popover-form"
import { InfoTooltip, TituloConAyuda, humanizarReferencia } from "@/components/ergo/InfoTooltip"
import { BorderBeam } from "@/components/magicui/border-beam"
import type { EstadoCaso, Jerarquia, Recomendacion } from "@/lib/api"
import { JERARQUIAS } from "@/lib/dominio"
import { cn } from "@/lib/utils"

export type Accion = (accion: string, recId?: string, valores?: Record<string, string>, comentario?: string) => Promise<boolean>

const ESTADO_TEXTO = { propuesta: "Propuesta del agente", aprobada: "Aprobada", rechazada: "Rechazada", obsoleta: "Obsoleta" } as const

export function PanelRecomendaciones({ estado, accion, ocupado, ocultarAprobarInforme = false, compacto = false }: {
  estado: EstadoCaso; accion: Accion; ocupado: boolean; ocultarAprobarInforme?: boolean; compacto?: boolean
}) {
  const recs = estado.validacion.recomendaciones.filter((rec) => rec.estado !== "obsoleta")
  const aprobado = estado.validacion.estado_informe === "aprobado"
  const nivel = estado.resultado.reba.nivel_accion ?? 0
  const porDecidir = recs.filter((rec) => rec.estado === "propuesta").length
  const decididas = recs.length - porDecidir
  const [agregando, setAgregando] = useState(false)
  const bloqueosResumen = estado.bloqueos.filter((m) => !m.includes("sigue como propuesta"))

  return (
    <div className={cn("space-y-5", compacto && "space-y-4")}>
      {/* En layout HITL el CTA vive en PanelDecision: aquí solo contador sticky. */}
      {!ocultarAprobarInforme ? (
        <div className="relative overflow-hidden rounded-[14px] border border-rule bg-sheet p-5 sm:p-6">
          {!aprobado && nivel >= 3 && porDecidir > 0 && <BorderBeam size={160} duration={7} colorFrom="var(--riesgo-alto)" colorTo="var(--riesgo-muy-alto)" borderWidth={1.5} />}
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div className="max-w-[62ch]">
              <h3 className="t-title text-[20px]">
                {aprobado
                  ? `Informe aprobado por ${estado.validacion.aprobado_por}`
                  : porDecidir > 0
                    ? `${porDecidir} propuestas pendientes de validación`
                    : "Todas las propuestas tienen decisión"}
              </h3>
              <p className="mt-1.5 text-[14px] text-ink-soft">
                {aprobado
                  ? "Cualquier cambio regresará el informe a borrador y quedará registrado."
                  : nivel >= 3
                    ? <>Riesgo alto: se requiere control de ingeniería o rediseño aprobado, con responsable (<TituloConAyuda clave="nom036" className="inline-flex">NOM-036</TituloConAyuda>).</>
                    : "Las propuestas se vuelven acciones de piso solo cuando las apruebas."}
              </p>
              {!aprobado && bloqueosResumen.length > 0 && (
                <ul className="mt-3 space-y-1 text-[14px] text-graphite">
                  {bloqueosResumen.slice(0, 3).map((motivo) => <li key={motivo} className="flex gap-2"><span aria-hidden>·</span>{motivo}</li>)}
                </ul>
              )}
            </div>
            {!aprobado && (
              <button
                className="boton-tinta"
                disabled={ocupado || estado.bloqueos.length > 0}
                title={estado.bloqueos.length ? estado.bloqueos.join(" · ") : undefined}
                onClick={() => void accion("aprobar_informe")}
              >
                <Check className="size-4" /> Aprobar acciones de piso ({decididas}/{recs.length})
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rule bg-sheet/95 px-3 py-2 backdrop-blur">
          <p className="text-[13px] font-medium text-jabil">
            {aprobado ? "Informe aprobado" : `${decididas} de ${recs.length} decididas`}
            {porDecidir > 0 && !aprobado ? <span className="font-normal text-ink-soft"> · faltan {porDecidir}</span> : null}
          </p>
          {nivel >= 3 && !aprobado && (
            <span className="flex items-center gap-1 text-[12px] text-graphite">
              NOM-036 · riesgo alto <InfoTooltip clave="nom036" />
            </span>
          )}
        </div>
      )}

      {JERARQUIAS.map(({ valor, etiqueta, explicacion }, indice) => {
        const grupo = recs.filter((rec) => rec.jerarquia === valor)
        if (!grupo.length) return null
        return (
          <section key={valor} className="rounded-xl border border-rule-soft bg-slate-50 p-3 sm:p-4">
            <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-rule pb-2">
              <span className="t-num text-[20px] text-graphite">{indice + 1}</span>
              <h3 className="t-title text-[17px] text-jabil sm:text-[18px]">{etiqueta}</h3>
              <p className="hidden text-[13px] text-graphite md:block">{explicacion}</p>
            </div>
            <ul className="grid gap-2.5">
              {grupo.map((rec) => <Tarjeta key={rec.id} rec={rec} accion={accion} ocupado={ocupado} compacto={compacto} />)}
            </ul>
          </section>
        )
      })}

      <section>
        {agregando ? (
          <FormularioRec titulo="Recomendación del especialista" inicial={null} ocupado={ocupado} onCancelar={() => setAgregando(false)}
            onGuardar={async (valores) => { if (await accion("agregar", undefined, valores)) setAgregando(false) }} />
        ) : (
          <button className="boton-linea border-dashed" onClick={() => setAgregando(true)}>
            <Plus className="size-4" /> Agregar recomendación del especialista
          </button>
        )}
      </section>
    </div>
  )
}

function Tarjeta({ rec, accion, ocupado, compacto }: { rec: Recomendacion; accion: Accion; ocupado: boolean; compacto?: boolean }) {
  const [editando, setEditando] = useState(false)
  const [rechazando, setRechazando] = useState(false)
  const [motivo, setMotivo] = useState("")
  const rechazada = rec.estado === "rechazada"
  const aprobada = rec.estado === "aprobada"
  const avisoNom = /no usar como única medida|riesgo alto|administrativ/i.test(`${rec.problema} ${rec.solucion} ${rec.comentario ?? ""}`)
    || (rec.jerarquia === "administrativa" && /única|sustitu/i.test(rec.solucion))

  if (editando) {
    return (
      <li>
        <FormularioRec titulo={`Editar ${rec.id}`} inicial={rec} ocupado={ocupado} onCancelar={() => setEditando(false)}
          onGuardar={async (valores, aprobar) => {
            const cambios = Object.fromEntries(Object.entries(valores).filter(([campo, valor]) => (rec as unknown as Record<string, string>)[campo] !== valor))
            let ok = Object.keys(cambios).length ? await accion("editar", rec.id, cambios) : true
            if (ok && aprobar && rec.estado !== "aprobada") ok = await accion("aprobar", rec.id)
            if (ok) setEditando(false)
          }} />
      </li>
    )
  }

  return (
    <li className={cn(
      "rounded-[10px] bg-sheet p-3.5 sm:p-4",
      aprobada ? "border-2 border-jabil/40" : rechazada ? "trazo-tachado" : "border border-dashed border-slate-300",
    )}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-graphite">
        <span className="t-num text-[13px]">{rec.id}</span>
        <span className={cn("font-medium", aprobada && "text-jabil")}>
          {aprobada ? "✓ " : ""}{ESTADO_TEXTO[rec.estado]}
        </span>
        {rec.origen === "especialista" && <span>Agregada por el especialista</span>}
        {rec.delta_reba != null && rec.delta_reba > 0 && (
          <span className="ml-auto rounded-md bg-ink px-2 py-0.5 text-sheet"><span className="t-num text-[13px]">−{rec.delta_reba}</span> REBA</span>
        )}
      </div>
      <p className={cn("mt-2 font-semibold text-ink", compacto ? "text-[15px]" : "text-[16px]", rechazada && "text-graphite line-through decoration-1")}>{rec.problema}</p>
      <p className={cn("mt-1 max-w-[78ch] text-ink-soft", compacto ? "text-[13px]" : "text-[14px]", rechazada && "text-graphite")}>{rec.solucion}</p>
      {avisoNom && !rechazada && (
        <p className="mt-2 flex items-start gap-1.5 text-[12px] font-medium text-amber-900">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          No usar como única medida si el riesgo es alto (NOM-036).
        </p>
      )}
      {rechazada && rec.comentario && <p className="mt-2 text-[13px] text-ink-soft">Motivo del rechazo: {rec.comentario}</p>}
      {!rechazada && rec.comentario && <p className="mt-2 text-[13px] text-graphite">Nota: {rec.comentario}</p>}

      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div className="text-[13px]">
          {rec.jerarquia !== "administrativa" && (
            <p className={cn(rec.responsable ? "text-ink" : "text-graphite")}>
              {rec.responsable ? `Responsable: ${rec.responsable}` : "Sin responsable"}{rec.fecha_compromiso ? `, compromiso ${rec.fecha_compromiso}` : ""}
            </p>
          )}
          {(rec.referencias?.length ?? 0) > 0 && (
            <details className="mt-1 text-[12px] text-graphite">
              <summary className="cursor-pointer select-none hover:text-ink">
                ¿Por qué se sugiere esta medida? ({rec.referencias!.length})
              </summary>
              <ul className="mt-1.5 space-y-0.5 pl-4">
                {rec.referencias!.map((ref) => (
                  <li key={ref} className="list-disc" title={ref}>{humanizarReferencia(ref)}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {rec.estado !== "propuesta" && (
            <button className="boton-linea px-2.5" disabled={ocupado} onClick={() => void accion("reabrir", rec.id)} title="Devolver a propuesta">
              <RotateCcw className="size-4" /><span className="sr-only">Devolver a propuesta</span>
            </button>
          )}
          <button className="boton-linea" disabled={ocupado} onClick={() => setEditando(true)}><Pencil className="size-4" /> Editar</button>
          {!rechazada && (
            <PopoverForm title="✕ Rechazar" layoutKey={`rechazar-${rec.id}`} open={rechazando} setOpen={setRechazando} showSuccess={false} width="340px" height="190px" align="right"
              triggerClassName="rounded-lg border-red-300 bg-red-50 text-red-800 hover:border-red-400 hover:bg-red-100"
              openChild={
                <form className="flex h-full flex-col p-3" onSubmit={async (e) => {
                  e.preventDefault()
                  if (!motivo.trim()) return
                  if (await accion("rechazar", rec.id, undefined, motivo.trim())) { setRechazando(false); setMotivo("") }
                }}>
                  <label htmlFor={`motivo-${rec.id}`} className="pt-7 pb-1 text-[13px] text-graphite">Motivo del rechazo, queda en la bitácora</label>
                  <textarea id={`motivo-${rec.id}`} autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)}
                    className="flex-1 resize-none rounded-md border border-rule bg-vellum/40 p-2 text-[14px] outline-none focus:border-ink" placeholder="Ej. el contenedor lo define el cliente" />
                  <div className="mt-2 flex"><PopoverFormButton loading={ocupado} text="Rechazar" /></div>
                </form>
              }
            />
          )}
          {rec.estado !== "aprobada" && (
            <button className="boton-tinta" disabled={ocupado} onClick={() => void accion("aprobar", rec.id)}><Check className="size-4" /> Aprobar</button>
          )}
        </div>
      </div>
    </li>
  )
}

function FormularioRec({ titulo, inicial, ocupado, onGuardar, onCancelar }: {
  titulo: string
  inicial: Recomendacion | null
  ocupado: boolean
  onGuardar: (valores: Record<string, string>, aprobar: boolean) => Promise<void>
  onCancelar: () => void
}) {
  const [problema, setProblema] = useState(inicial?.problema ?? "")
  const [solucion, setSolucion] = useState(inicial?.solucion ?? "")
  const [jerarquia, setJerarquia] = useState<Jerarquia>(inicial?.jerarquia ?? "ingenieria")
  const [responsable, setResponsable] = useState(inicial?.responsable ?? "")
  const [fecha, setFecha] = useState(inicial?.fecha_compromiso ?? "")
  const [aprobar, setAprobar] = useState(true)

  return (
    <form className="trazo-tinta rounded-[12px] p-4 sm:p-5" onSubmit={(e) => {
      e.preventDefault()
      void onGuardar({ problema: problema.trim(), solucion: solucion.trim(), jerarquia, responsable: responsable.trim(), fecha_compromiso: fecha }, aprobar)
    }}>
      <div className="mb-4 flex items-center justify-between">
        <h4 className="t-title text-[17px]">{titulo}</h4>
        <button type="button" onClick={onCancelar} className="rounded-md p-1 text-graphite hover:text-ink" aria-label="Cancelar"><X className="size-4" /></button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block text-[14px] font-medium text-ink-soft">Problema detectado
          <textarea required rows={3} className="campo mt-1.5 font-normal" value={problema} onChange={(e) => setProblema(e.target.value)} />
        </label>
        <label className="block text-[14px] font-medium text-ink-soft">Recomendación
          <textarea required rows={3} className="campo mt-1.5 font-normal" value={solucion} onChange={(e) => setSolucion(e.target.value)} />
        </label>
        <label className="block text-[14px] font-medium text-ink-soft">Tipo de control
          <select className="campo mt-1.5 font-normal" value={jerarquia} onChange={(e) => setJerarquia(e.target.value as Jerarquia)}>
            {JERARQUIAS.map((j) => <option key={j.valor} value={j.valor}>{j.etiqueta}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-[1fr_160px] gap-3">
          <label className="block text-[14px] font-medium text-ink-soft">Responsable
            <input className="campo mt-1.5 font-normal" value={responsable} onChange={(e) => setResponsable(e.target.value)} placeholder="Ej. IE celda 3" />
          </label>
          <label className="block text-[14px] font-medium text-ink-soft">Fecha compromiso
            <input type="date" className="campo t-num mt-1.5" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </label>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        {inicial && inicial.estado !== "aprobada" ? (
          <label className="flex items-center gap-2 text-[14px]">
            <input type="checkbox" checked={aprobar} onChange={(e) => setAprobar(e.target.checked)} className="size-4 accent-[var(--ink)]" /> Aprobar al guardar
          </label>
        ) : <span className="text-[13px] text-graphite">{inicial ? "Los cambios quedan en la bitácora." : "Se agrega aprobada y firmada por ti."}</span>}
        <div className="flex gap-2">
          <button type="button" className="boton-linea" onClick={onCancelar}>Cancelar</button>
          <button type="submit" className="boton-tinta" disabled={ocupado}>{inicial ? "Guardar cambios" : "Agregar"}</button>
        </div>
      </div>
    </form>
  )
}
