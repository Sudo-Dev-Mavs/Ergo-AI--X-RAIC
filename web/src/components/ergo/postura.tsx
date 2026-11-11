import { RotateCcw } from "lucide-react"
import { useMemo, useState } from "react"

import type { Angulo, EstadoCaso } from "@/lib/api"
import { NOMBRE_BANDERA, NOMBRE_MEDIDA, SEGMENTO } from "@/lib/dominio"
import { cn } from "@/lib/utils"

const ORDEN = ["Tronco", "Cuello", "Piernas", "Brazos", "Antebrazos", "Muñecas"]
const NOMBRE_VISTA: Record<string, string> = { costado: "costado", frente: "frente", aerea: "aérea" }

/** De dónde salió la medida: su vista primaria, la vista de respaldo, la pose 3D o el contexto. */
function origenMedida(angulo: Angulo): string {
  const metodo = angulo.metodo ?? ""
  if (metodo.startsWith("respaldo 3D")) return `pose 3D de la vista ${NOMBRE_VISTA[angulo.vista] ?? angulo.vista}`
  if (angulo.vista === "contexto") return "según la postura declarada"
  if (metodo.startsWith("respaldo")) return `respaldo con la vista ${NOMBRE_VISTA[angulo.vista] ?? angulo.vista}`
  return `vista ${NOMBRE_VISTA[angulo.vista] ?? angulo.vista}`
}

function etiquetaPendiente(medida: string): string {
  const base = medida.replace(/_[LR]$/, "")
  return NOMBRE_MEDIDA[base] ?? base.replaceAll("_", " ")
}

function ladoPendiente(p: { medida: string; lado?: string | null }): "L" | "R" | null {
  if (p.lado === "L" || p.lado === "R") return p.lado
  if (p.medida.endsWith("_L")) return "L"
  if (p.medida.endsWith("_R")) return "R"
  return null
}

function clavePendiente(p: { medida: string; lado?: string | null }): string {
  const base = p.medida.replace(/_[LR]$/, "")
  const lado = ladoPendiente(p)
  return lado && base !== "cuello_flexion" ? `${base}_${lado}` : base
}

/** Quita duplicados y omite avisos de “no medible” si ya hay un valor usable (p. ej. muñeca con °). */
function compactarPendientes(
  pendientes: EstadoCaso["resultado"]["pendientes_manuales"],
  angulos: Angulo[],
) {
  const valorPorClave = new Map<string, number | null>()
  for (const a of angulos) {
    valorPorClave.set(a.clave_override, a.valor_deg)
    if (a.lado) valorPorClave.set(`${a.medida}_${a.lado}`, a.valor_deg)
    else valorPorClave.set(a.medida, a.valor_deg)
  }

  const vistos = new Set<string>()
  const out: typeof pendientes = []
  for (const p of pendientes) {
    const clave = clavePendiente(p)
    const valor = valorPorClave.get(clave)
    const motivo = (p.motivo ?? "").toLowerCase()
    const esFaltaMedicion = /landmark|ausente|no utilizable|medición ausente/.test(motivo)
    if (valor != null && esFaltaMedicion) continue
    if (vistos.has(clave)) continue
    vistos.add(clave)
    out.push(p)
  }
  return out
}

function parseAngulo(texto: string): number | null {
  const limpio = texto.replace(/°/g, "").replace(",", ".").trim()
  if (limpio === "") return null
  const valor = Number(limpio)
  return Number.isFinite(valor) ? valor : null
}

export function PanelPostura({ estado, ocupado, onCorregir }: {
  estado: EstadoCaso
  ocupado: boolean
  onCorregir: (overrides: Record<string, number | null>, comentario: string) => Promise<boolean>
}) {
  const [borrador, setBorrador] = useState<Record<string, string>>({})
  const [quitar, setQuitar] = useState<Set<string>>(new Set())
  const [comentario, setComentario] = useState("")
  const grupos = useMemo(() => {
    const mapa = new Map<string, Angulo[]>()
    for (const angulo of estado.resultado.angulos) {
      const segmento = SEGMENTO[angulo.medida] ?? "Otros"
      mapa.set(segmento, [...(mapa.get(segmento) ?? []), angulo])
    }
    return [...mapa.entries()].sort(([a], [b]) => ORDEN.indexOf(a) - ORDEN.indexOf(b))
  }, [estado.resultado.angulos])

  const cambios: Record<string, number | null> = {}
  for (const [clave, texto] of Object.entries(borrador)) {
    const valor = parseAngulo(texto)
    if (valor != null) cambios[clave] = valor
  }
  for (const clave of quitar) cambios[clave] = null
  const total = Object.keys(cambios).length
  const pendientes = useMemo(
    () => compactarPendientes(estado.resultado.pendientes_manuales ?? [], estado.resultado.angulos),
    [estado.resultado.pendientes_manuales, estado.resultado.angulos],
  )

  function toggleQuitar(clave: string) {
    setQuitar((q) => {
      const n = new Set(q)
      if (n.has(clave)) n.delete(clave)
      else n.add(clave)
      return n
    })
  }

  return (
    <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="space-y-8">
        {grupos.map(([segmento, angulos]) => (
          <section key={segmento}>
            <h3 className="t-title mb-2 border-b border-ink pb-1.5 text-[19px]">{segmento}</h3>
            <table className="w-full table-fixed text-[14px]">
              <colgroup><col /><col className="w-[104px]" /><col className="w-[64px]" /><col className="w-[30%]" /><col className="w-[168px]" /></colgroup>
              <thead className="sr-only"><tr><th>Medida</th><th>Valor</th><th>Banda REBA</th><th>Notas</th><th>Corrección</th></tr></thead>
              <tbody>
                {angulos.map((angulo) => {
                  const clave = angulo.clave_override
                  const corregido = angulo.fuente === "especialista"
                  const esBinario = angulo.medida === "apoyo_piernas_unilateral"
                  const borradorActual = borrador[clave]
                  return (
                    <tr key={`${clave}-${angulo.vista}`} className="border-b border-rule-soft align-middle">
                      <td className="py-2.5 pr-3">
                        <span className="font-medium">{NOMBRE_MEDIDA[angulo.medida] ?? angulo.medida}</span>
                        {angulo.lado && <span className="ml-1.5 text-graphite">{angulo.lado === "L" ? "izquierdo" : "derecho"}</span>}
                        <span className="block text-[12px] text-graphite">{origenMedida(angulo)}</span>
                      </td>
                      <td className="py-2.5 pr-3 text-right">
                        <span className={cn("t-num text-[24px] leading-none", angulo.valor_deg == null && "text-graphite")}>
                          {angulo.valor_deg == null ? "—" : esBinario ? (angulo.valor_deg ? "Sí" : "No") : `${angulo.valor_deg.toFixed(0)}°`}
                        </span>
                        {corregido && angulo.valor_medido_deg != null && !esBinario && (
                          <span className="block text-[12px] text-graphite">medido {angulo.valor_medido_deg.toFixed(0)}°</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-3 text-center">
                        {angulo.banda_reba != null ? <span className="t-num inline-block min-w-7 rounded-md border border-ink px-1.5 text-[15px]">{angulo.banda_reba}</span> : <span className="text-graphite">—</span>}
                      </td>
                      <td className="py-2.5 pr-3 text-[13px] text-graphite">
                        {corregido && <span className="mr-2 font-medium text-ink">Corregido por especialista</span>}
                        {angulo.valor_deg == null && angulo.motivo}
                        {angulo.banderas.map((b) => NOMBRE_BANDERA[b] ?? b.replaceAll("_", " ")).join(", ")}
                      </td>
                      <td className="py-2.5">
                        <div className="flex items-center justify-end gap-1.5">
                          {esBinario ? (
                            <div className="inline-flex overflow-hidden rounded-md border border-rule" role="group" aria-label={`Corregir ${NOMBRE_MEDIDA[angulo.medida]}`}>
                              {([["1", "Sí"], ["0", "No"]] as const).map(([val, lab]) => (
                                <button
                                  key={val}
                                  type="button"
                                  disabled={ocupado}
                                  onClick={() => {
                                    setQuitar((q) => { const n = new Set(q); n.delete(clave); return n })
                                    setBorrador((b) => ({ ...b, [clave]: val }))
                                  }}
                                  className={cn(
                                    "px-3 py-1.5 text-[13px] font-medium transition-colors",
                                    (borradorActual ?? (angulo.valor_deg != null ? (angulo.valor_deg ? "1" : "0") : "")) === val
                                      ? "bg-jabil text-white"
                                      : "bg-sheet text-ink-soft hover:bg-slate-50",
                                  )}
                                >
                                  {lab}
                                </button>
                              ))}
                            </div>
                          ) : (
                            <label className="relative block w-[5.5rem]">
                              <span className="sr-only">Corregir {NOMBRE_MEDIDA[angulo.medida] ?? angulo.medida}</span>
                              <input
                                inputMode="decimal"
                                placeholder="ej. 20"
                                value={borrador[clave] ?? ""}
                                onChange={(e) => {
                                  const crudo = e.target.value.replace(/°/g, "")
                                  setBorrador((b) => ({ ...b, [clave]: crudo }))
                                }}
                                className="campo t-num w-full py-1 pr-6 pl-2 text-right text-[15px]"
                              />
                              <span aria-hidden className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-[14px] text-graphite">°</span>
                            </label>
                          )}
                          {corregido && (
                            <button
                              type="button"
                              title="Volver a la medición automática"
                              aria-pressed={quitar.has(clave)}
                              onClick={() => toggleQuitar(clave)}
                              className={cn("rounded-md border p-1.5", quitar.has(clave) ? "border-ink bg-ink text-sheet" : "border-rule text-graphite hover:border-ink")}
                            >
                              <RotateCcw className="size-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </section>
        ))}
      </div>

      <aside className="space-y-6 xl:sticky xl:top-8 xl:self-start">
        <div className={cn("rounded-[12px] p-4", total ? "trazo-tinta" : "trazo-lapiz")}>
          <h3 className="t-title text-[17px]">Corregir ángulos</h3>
          <p className="mt-1 text-[14px] text-ink-soft">
            Si una medición no coincide con lo que ves en piso, escribe el valor (el ° se pone solo) o elige Sí/No en apoyo. ErgoAI recalcula el REBA con tu firma.
          </p>
          <label className="mt-3 block text-[13px] text-graphite">Motivo (opcional)
            <input className="campo mt-1 text-[14px]" value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Ej. medido con goniómetro" />
          </label>
          <button className="boton-tinta mt-3 w-full justify-center" disabled={!total || ocupado}
            onClick={async () => { if (await onCorregir(cambios, comentario)) { setBorrador({}); setQuitar(new Set()); setComentario("") } }}>
            {total ? `Recalcular con ${total} ${total === 1 ? "corrección" : "correcciones"}` : "Sin correcciones"}
          </button>
        </div>
        {pendientes.length > 0 && (
          <div>
            <h3 className="t-title text-[17px]">Revisar en piso</h3>
            <p className="mt-1 text-[13px] text-graphite">
              Solo lo que aún no tiene un valor usable. Si ya ves un ángulo en la tabla, el REBA ya puede usarlo.
            </p>
            <ul className="mt-2 space-y-1.5 text-[14px]">
              {pendientes.slice(0, 12).map((p) => {
                const lado = ladoPendiente(p)
                return (
                  <li key={clavePendiente(p)} className="border-l-2 border-[var(--riesgo-medio)] pl-2.5">
                    <span className="font-medium">
                      {etiquetaPendiente(p.medida)}
                      {lado ? ` (${lado === "L" ? "izq." : "der."})` : ""}
                    </span>
                    {p.motivo && <span className="block text-[13px] text-graphite">{p.motivo}</span>}
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </aside>
    </div>
  )
}
