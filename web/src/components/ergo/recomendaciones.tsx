import { Check, Pencil, Plus, RotateCcw, X } from "lucide-react"
import { useState } from "react"

import { PopoverForm, PopoverFormButton } from "@/components/cult/popover-form"
import { BorderBeam } from "@/components/magicui/border-beam"
import type { EstadoCaso, Jerarquia, Recomendacion } from "@/lib/api"
import { JERARQUIAS } from "@/lib/dominio"
import { cn } from "@/lib/utils"

export type Accion = (accion: string, recId?: string, valores?: Record<string, string>, comentario?: string) => Promise<boolean>

const ESTADO_TEXTO = { propuesta: "Propuesta del agente", aprobada: "Aprobada", rechazada: "Rechazada", obsoleta: "Obsoleta" } as const

export function PanelRecomendaciones({ estado, accion, ocupado }: { estado: EstadoCaso; accion: Accion; ocupado: boolean }) {
  const recs = estado.validacion.recomendaciones.filter((rec) => rec.estado !== "obsoleta")
  const aprobado = estado.validacion.estado_informe === "aprobado"
  const nivel = estado.resultado.reba.nivel_accion ?? 0
  const porDecidir = recs.filter((rec) => rec.estado === "propuesta").length
  const [agregando, setAgregando] = useState(false)

  return (
    <div className="space-y-10">
      <div className="relative overflow-hidden rounded-[14px] border border-rule bg-sheet p-5 sm:p-6">
        {!aprobado && nivel >= 3 && porDecidir > 0 && <BorderBeam size={160} duration={7} colorFrom="var(--riesgo-alto)" colorTo="var(--riesgo-muy-alto)" borderWidth={1.5} />}
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-[62ch]">
            <h3 className="t-title text-[20px]">
              {aprobado ? `Informe aprobado por ${estado.validacion.aprobado_por}` : porDecidir > 0 ? `${porDecidir} de ${recs.length} propuestas esperan tu decisión` : "Todas las propuestas tienen decisión"}
            </h3>
            <p className="mt-1.5 text-[14px] text-ink-soft">
              {aprobado
                ? "Cualquier cambio regresará el informe a borrador y quedará registrado."
                : nivel >= 3
                  ? "Caso de riesgo alto: el informe necesita al menos un control de ingeniería o rediseño aprobado, con responsable."
                  : "Las propuestas se vuelven acciones de piso solo cuando las apruebas."}
            </p>
            {!aprobado && estado.bloqueos.length > 0 && (
              <ul className="mt-3 space-y-1 text-[14px] text-graphite">
                {estado.bloqueos.slice(0, 4).map((motivo) => <li key={motivo} className="flex gap-2"><span aria-hidden>·</span>{motivo}</li>)}
                {estado.bloqueos.length > 4 && <li className="pl-4">y {estado.bloqueos.length - 4} más</li>}
              </ul>
            )}
          </div>
          {!aprobado && (
            <button className="boton-tinta" disabled={ocupado || estado.bloqueos.length > 0} onClick={() => void accion("aprobar_informe")}>
              <Check className="size-4" /> Aprobar informe
            </button>
          )}
        </div>
      </div>

      {JERARQUIAS.map(({ valor, etiqueta, explicacion }, indice) => {
        const grupo = recs.filter((rec) => rec.jerarquia === valor)
        if (!grupo.length) return null
        return (
          <section key={valor}>
            <div className="mb-4 flex items-baseline gap-4 border-b border-ink pb-2">
              <span className="t-num text-[24px] text-graphite">{indice + 1}</span>
              <h3 className="t-title text-[21px]">{etiqueta}</h3>
              <p className="hidden text-[14px] text-graphite md:block">{explicacion}</p>
            </div>
            <ul className="grid gap-3">
              {grupo.map((rec) => <Tarjeta key={rec.id} rec={rec} accion={accion} ocupado={ocupado} />)}
            </ul>
          </section>
        )
      })}

      <section>
        {agregando ? (
          <FormularioRec titulo="Recomendación del especialista" inicial={null} ocupado={ocupado} onCancelar={() => setAgregando(false)}
            onGuardar={async (valores) => { if (await accion("agregar", undefined, valores)) setAgregando(false) }} />
        ) : (
          <button className="boton-linea border-dashed" onClick={() => setAgregando(true)}><Plus className="size-4" /> Agregar recomendación propia</button>
        )}
      </section>
    </div>
  )
}

function Tarjeta({ rec, accion, ocupado }: { rec: Recomendacion; accion: Accion; ocupado: boolean }) {
  const [editando, setEditando] = useState(false)
  const [rechazando, setRechazando] = useState(false)
  const [motivo, setMotivo] = useState("")
  const rechazada = rec.estado === "rechazada"

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
    <li className={cn("rounded-[12px] p-4 sm:p-5", rec.estado === "aprobada" ? "trazo-tinta" : rechazada ? "trazo-tachado" : "trazo-lapiz")}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-graphite">
        <span className="t-num text-[14px]">{rec.id}</span>
        <span className={cn("font-medium", rec.estado === "aprobada" && "text-ink")}>{ESTADO_TEXTO[rec.estado]}</span>
        {rec.origen === "especialista" && <span>Agregada por el especialista</span>}
        {rec.delta_reba != null && rec.delta_reba > 0 && (
          <span className="ml-auto rounded-md bg-ink px-2 py-0.5 text-sheet"><span className="t-num text-[14px]">−{rec.delta_reba}</span> REBA</span>
        )}
      </div>
      <p className={cn("mt-2 text-[16px] font-semibold", rechazada && "text-graphite line-through decoration-1")}>{rec.problema}</p>
      <p className={cn("mt-1 max-w-[78ch] text-[15px] text-ink-soft", rechazada && "text-graphite")}>{rec.solucion}</p>
      {rechazada && rec.comentario && <p className="mt-2 text-[14px] text-ink-soft">Motivo del rechazo: {rec.comentario}</p>}
      {!rechazada && rec.comentario && <p className="mt-2 text-[14px] text-graphite">Nota: {rec.comentario}</p>}

      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div className="text-[14px]">
          {rec.jerarquia !== "administrativa" && (
            <p className={cn(rec.responsable ? "text-ink" : "text-graphite")}>
              {rec.responsable ? `Responsable: ${rec.responsable}` : "Sin responsable"}{rec.fecha_compromiso ? `, compromiso ${rec.fecha_compromiso}` : ""}
            </p>
          )}
          {rec.referencias.length > 0 && (
            <details className="mt-1 text-[13px] text-graphite">
              <summary className="cursor-pointer select-none hover:text-ink">Fundamento ({rec.referencias.length})</summary>
              <ul className="mt-1.5 space-y-0.5 pl-4">{rec.referencias.map((ref) => <li key={ref} className="list-disc">{ref}</li>)}</ul>
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
            <PopoverForm title="Rechazar" layoutKey={`rechazar-${rec.id}`} open={rechazando} setOpen={setRechazando} showSuccess={false} width="340px" height="190px" align="right"
              triggerClassName="rounded-lg border-rule text-ink hover:border-ink"
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
              } />
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
