import { Check, ChevronLeft, ChevronRight, ClipboardCheck, PanelLeft, Pencil, ShieldAlert } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { ComparadorResidual } from "@/components/ergo/ComparadorResidual"
import { PanelRecomendaciones, type Accion } from "@/components/ergo/recomendaciones"
import { VisorFoto } from "@/components/ergo/VisorFoto"
import { api, type EstadoCaso, type ResumenCaso, type Vista } from "@/lib/api"
import { useEspecialista } from "@/lib/app"
import { colorPuntoCaso, etiquetaReba, etiquetaTarea } from "@/lib/dominio"
import { usePreferencias } from "@/lib/preferencias"
import { esRiesgoAlto, useReba } from "@/lib/useReba"
import { cn } from "@/lib/utils"

interface Props {
  casos: ResumenCaso[]
  casoActivo: EstadoCaso | null
  cargandoCaso?: boolean
  ocupado: boolean
  onSeleccionar: (casoId: string) => void
  onAccion: Accion
  onAjustarResidual: (puntaje: number, motivo: string) => Promise<boolean>
  onLimpiarResidual: () => Promise<boolean>
}

/** HITL: cola colapsable · evidencia + recomendaciones · panel de decisión. */
export function ValidationDashboard({
  casos, casoActivo, cargandoCaso, ocupado, onSeleccionar, onAccion, onAjustarResidual, onLimpiarResidual,
}: Props) {
  const pendientes = useMemo(
    () => casos
      .filter((c) => c.estado_informe !== "aprobado")
      .sort((a, b) => (b.nivel_accion ?? -1) - (a.nivel_accion ?? -1) || b.por_validar - a.por_validar || (b.reba ?? -1) - (a.reba ?? -1)),
    [casos],
  )

  const autoSel = useRef(false)
  useEffect(() => {
    if (autoSel.current || casoActivo || cargandoCaso || pendientes.length === 0) return
    autoSel.current = true
    onSeleccionar(pendientes[0].caso_id)
  }, [casoActivo, cargandoCaso, pendientes, onSeleccionar])

  const [colaAbierta, setColaAbierta] = useState(true)
  const [motivoResidual, setMotivoResidual] = useState("")
  const [borradorResidual, setBorradorResidual] = useState<number | null>(null)

  useEffect(() => {
    setBorradorResidual(null)
    setMotivoResidual("")
  }, [casoActivo?.resultado.caso_id])

  const residualVista = borradorResidual ?? casoActivo?.residual.residual.reba ?? null
  const reba = useReba(
    casoActivo?.resultado.reba.final.reportado,
    residualVista,
    casoActivo?.validacion.recomendaciones ?? [],
  )
  const porDecidir = casoActivo?.validacion.recomendaciones.filter((r) => r.estado === "propuesta").length ?? 0
  const totalVigentes = casoActivo?.validacion.recomendaciones.filter((r) => r.estado !== "obsoleta").length ?? 0
  const bloqueado = (casoActivo?.bloqueos.length ?? 0) > 0
  const aprobado = casoActivo?.validacion.estado_informe === "aprobado"
  const sinSeleccion = !casoActivo && !cargandoCaso && pendientes.length === 0

  return (
    <div className="mx-auto max-w-[1400px]">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-rule pb-4">
        <div>
          <div className="h-1 w-14 rounded-full bg-jabil-cyan" aria-hidden />
          <h1 className="t-display mt-3 text-[32px] text-jabil sm:text-[40px]">Validación</h1>
          <p className="mt-1 text-[14px] text-ink-soft">El agente propone · tú decides · queda en bitácora.</p>
        </div>
        <button
          type="button"
          className="boton-linea"
          onClick={() => setColaAbierta((v) => !v)}
          aria-expanded={colaAbierta}
          aria-controls="cola-validacion"
        >
          <PanelLeft className="size-4" />
          {colaAbierta ? "Ocultar cola" : `Cola (${pendientes.length})`}
          {colaAbierta ? <ChevronLeft className="size-4" /> : <ChevronRight className="size-4" />}
        </button>
      </header>

      <div className={cn(
        "grid gap-5",
        colaAbierta
          ? "lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1.15fr)_minmax(300px,0.85fr)]"
          : "xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]",
      )}>
        {colaAbierta && (
          <aside id="cola-validacion" className="hoja overflow-hidden lg:sticky lg:top-8 lg:max-h-[calc(100dvh-5rem)]">
            <div className="border-b border-rule bg-jabil px-3 py-3 text-white">
              <p className="text-[11px] tracking-[0.12em] text-jabil-cyan uppercase">Cola</p>
              <p className="t-title text-[16px]">{pendientes.length} pendiente{pendientes.length === 1 ? "" : "s"}</p>
            </div>
            <ol className="max-h-[40dvh] overflow-y-auto lg:max-h-[calc(100dvh-9rem)]">
              {pendientes.map((caso) => {
                const activo = casoActivo?.resultado.caso_id === caso.caso_id
                return (
                  <li key={caso.caso_id} className="border-b border-rule-soft">
                    <button
                      type="button"
                      onClick={() => onSeleccionar(caso.caso_id)}
                      className={cn("flex w-full items-start gap-2.5 px-3 py-3 text-left", activo ? "bg-jabil/8" : "hover:bg-slate-50")}
                    >
                      <span className="mt-1 size-2.5 shrink-0 rounded-full" style={{ background: colorPuntoCaso(caso.reba) }} />
                      <span className="min-w-0 flex-1">
                        <span className="t-title block truncate text-[14px] text-jabil">{caso.caso_id}</span>
                        <span className="block text-[12px] text-graphite">
                          {etiquetaReba(caso.reba, caso.nivel_riesgo)}
                          {caso.por_validar > 0 ? ` · ${caso.por_validar} prop.` : ""}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
              {pendientes.length === 0 && <li className="px-3 py-6 text-center text-[13px] text-graphite">Sin pendientes</li>}
            </ol>
          </aside>
        )}

        <section className="min-w-0 space-y-4">
          {cargandoCaso && <p className="text-[14px] text-graphite">Cargando evaluación…</p>}
          {sinSeleccion && (
            <div className="hoja flex flex-col items-center gap-3 px-6 py-16 text-center">
              <ClipboardCheck className="size-9 text-jabil" strokeWidth={1.5} />
              <h2 className="t-title text-[22px] text-jabil">No hay casos pendientes</h2>
              <p className="max-w-[42ch] text-[14px] text-ink-soft">Cuando haya borradores, aparecerán ordenados por riesgo.</p>
            </div>
          )}
          {casoActivo && (
            <>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <h2 className="t-title text-[26px] text-jabil">{casoActivo.resultado.caso_id}</h2>
                <p className="text-[14px] text-ink-soft">
                  {etiquetaTarea(casoActivo.resultado.contexto?.tipo_tarea)}
                  {casoActivo.resultado.contexto?.carga_kg != null ? ` · ${casoActivo.resultado.contexto.carga_kg} kg` : ""}
                </p>
              </div>
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                <Evidencia estado={casoActivo} />
                <PanelRecomendaciones estado={casoActivo} accion={onAccion} ocupado={ocupado} ocultarAprobarInforme compacto />
              </div>
              <div className="xl:hidden">
                <PanelDecision
                  casoActivo={casoActivo}
                  residualVista={residualVista}
                  borradorResidual={borradorResidual}
                  setBorradorResidual={setBorradorResidual}
                  motivoResidual={motivoResidual}
                  setMotivoResidual={setMotivoResidual}
                  rebaOk={reba.nom036.ok}
                  rebaMotivo={reba.nom036.motivo}
                  porDecidir={porDecidir}
                  totalVigentes={totalVigentes}
                  bloqueado={bloqueado}
                  aprobado={!!aprobado}
                  ocupado={ocupado}
                  onAccion={onAccion}
                  onAjustarResidual={onAjustarResidual}
                  onLimpiarResidual={onLimpiarResidual}
                />
              </div>
            </>
          )}
        </section>

        {casoActivo && (
          <aside className="hidden xl:block">
            <div className="sticky top-8">
              <PanelDecision
                casoActivo={casoActivo}
                residualVista={residualVista}
                borradorResidual={borradorResidual}
                setBorradorResidual={setBorradorResidual}
                motivoResidual={motivoResidual}
                setMotivoResidual={setMotivoResidual}
                rebaOk={reba.nom036.ok}
                rebaMotivo={reba.nom036.motivo}
                porDecidir={porDecidir}
                totalVigentes={totalVigentes}
                bloqueado={bloqueado}
                aprobado={!!aprobado}
                ocupado={ocupado}
                onAccion={onAccion}
                onAjustarResidual={onAjustarResidual}
                onLimpiarResidual={onLimpiarResidual}
              />
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}

function PanelDecision({
  casoActivo, residualVista, borradorResidual, setBorradorResidual, motivoResidual, setMotivoResidual,
  rebaOk, rebaMotivo, porDecidir, totalVigentes, bloqueado, aprobado, ocupado,
  onAccion, onAjustarResidual, onLimpiarResidual,
}: {
  casoActivo: EstadoCaso
  residualVista: number | null
  borradorResidual: number | null
  setBorradorResidual: (n: number | null) => void
  motivoResidual: string
  setMotivoResidual: (s: string) => void
  rebaOk: boolean
  rebaMotivo: string | null
  porDecidir: number
  totalVigentes: number
  bloqueado: boolean
  aprobado: boolean
  ocupado: boolean
  onAccion: Accion
  onAjustarResidual: (puntaje: number, motivo: string) => Promise<boolean>
  onLimpiarResidual: () => Promise<boolean>
}) {
  const { nombre } = useEspecialista()
  const sinFirma = !nombre.trim()
  const inicial = casoActivo.resultado.reba.final.reportado
  const decididas = totalVigentes - porDecidir
  const angulosOk = (casoActivo.resultado.angulos ?? []).some((a) => a.valor_deg != null)
  const bloqueosCortos = casoActivo.bloqueos.filter((m) => !m.includes("sigue como propuesta")).slice(0, 2)
  const ctaBloqueado = ocupado || aprobado || bloqueado || sinFirma

  return (
    <div className="space-y-3">
      {!rebaOk && (
        <div className="flex items-start gap-2 rounded-lg border border-[var(--riesgo-alto)]/35 bg-orange-50 px-3 py-2 text-[13px] text-orange-950">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <span>{rebaMotivo}</span>
        </div>
      )}

      <ComparadorResidual
        compacto
        inicial={inicial}
        residual={residualVista}
        origen={borradorResidual != null ? "especialista" : (casoActivo.residual.origen_residual ?? "agente")}
        ajustable={!aprobado && inicial != null}
        onAjustar={setBorradorResidual}
        vacioAccion={inicial == null && angulosOk ? "Hay ángulos medidos pero aún no hay REBA reportado. Revisa Postura medida o vuelve a analizar el caso." : undefined}
      />

      {!aprobado && borradorResidual != null && borradorResidual !== casoActivo.residual.residual_agente?.reba && (
        <div className="rounded-xl border border-dashed border-jabil/35 bg-sheet p-3">
          <label className="block text-[12px] font-medium text-ink-soft">
            Motivo del ajuste (bitácora)
            <textarea className="campo mt-1 text-[13px]" rows={2} value={motivoResidual} onChange={(e) => setMotivoResidual(e.target.value)} placeholder="Ej. el lifter no elimina del todo la flexión" />
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" className="boton-tinta" disabled={ocupado || !motivoResidual.trim()}
              onClick={async () => { if (await onAjustarResidual(borradorResidual, motivoResidual.trim())) { setMotivoResidual(""); setBorradorResidual(null) } }}>
              <Pencil className="size-3.5" /> Guardar
            </button>
            <button type="button" className="boton-linea" disabled={ocupado} onClick={async () => { setBorradorResidual(null); await onLimpiarResidual() }}>
              Restaurar IA
            </button>
          </div>
        </div>
      )}

      <div className="hoja p-4">
        <p className="text-[14px] font-medium text-jabil">
          Decisiones: <span className="t-num">{decididas}/{totalVigentes}</span>
          {porDecidir > 0 ? <span className="font-normal text-ink-soft"> · faltan {porDecidir}</span> : <span className="font-normal text-ink-soft"> · listo</span>}
        </p>
        {bloqueosCortos.length > 0 && (
          <ul className="mt-2 space-y-1 text-[12px] text-graphite">
            {bloqueosCortos.map((m) => <li key={m}>· {m}</li>)}
          </ul>
        )}
        {sinFirma && !aprobado && (
          <p className="mt-2 text-[13px] font-medium text-amber-900">Escribe tu nombre en «Firmas como» para autorizar.</p>
        )}
        <button
          type="button"
          className="boton-tinta mt-3 w-full justify-center py-3 text-[15px]"
          disabled={ctaBloqueado}
          title={sinFirma ? "Escribe tu nombre para firmar" : bloqueado ? casoActivo.bloqueos.join(" · ") : undefined}
          onClick={() => void onAccion("aprobar_informe")}
        >
          <Check className="size-4" />
          {aprobado
            ? "Informe aprobado"
            : sinFirma
              ? "Escribe tu nombre para firmar"
              : `Aprobar acciones de piso (${decididas}/${totalVigentes})`}
        </button>
        {esRiesgoAlto(inicial) && (
          <p className="mt-2 text-[12px] text-graphite">
            Norma NOM-036: con riesgo alto hace falta ingeniería o rediseño aprobado, con responsable asignado.
          </p>
        )}
      </div>
    </div>
  )
}

function Evidencia({ estado }: { estado: EstadoCaso }) {
  const { preferencias } = usePreferencias()
  const id = estado.resultado.caso_id
  const vistas = (["costado", "frente", "aerea"] as Vista[]).filter((v) => estado.imagenes.includes(v) || estado.fotos.includes(v))
  const [vista, setVista] = useState<Vista>(vistas[0] ?? "costado")
  const [original, setOriginal] = useState(preferencias.fotoInicial === "original")
  useEffect(() => {
    setOriginal(preferencias.fotoInicial === "original")
  }, [preferencias.fotoInicial, id])
  const anotada = estado.imagenes.includes(vista)
  const src = vistas.length
    ? (original || !anotada ? api.foto(id, vista) : api.archivo(id, `${vista}_angulos.png`))
    : null

  return (
    <VisorFoto
      src={src}
      alt={`Vista ${vista} ${original ? "original" : "con ángulos"}`}
      vacio="Sin imagen analizada"
      barraExtra={
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1" role="tablist" aria-label="Vista">
            {vistas.map((v) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={v === vista}
                onClick={() => setVista(v)}
                className={cn("rounded-md px-3 py-1.5 text-[13px] font-medium capitalize", v === vista ? "bg-jabil text-white" : "text-ink-soft hover:bg-slate-100")}
              >
                {v === "aerea" ? "Aérea" : v}
              </button>
            ))}
          </div>
          {anotada && estado.fotos.includes(vista) && (
            <label className="flex items-center gap-2 text-[13px] text-ink-soft">
              <input type="checkbox" checked={original} onChange={(e) => setOriginal(e.target.checked)} className="size-4 accent-[var(--jabil)]" />
              Original
            </label>
          )}
        </div>
      }
    />
  )
}
