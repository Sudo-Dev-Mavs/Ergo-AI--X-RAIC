import { RotateCcw } from "lucide-react"
import { useMemo, useState } from "react"

import type { Angulo, EstadoCaso } from "@/lib/api"
import { NOMBRE_BANDERA, NOMBRE_MEDIDA, SEGMENTO } from "@/lib/dominio"
import { cn } from "@/lib/utils"

const ORDEN = ["Tronco", "Cuello", "Piernas", "Brazos", "Antebrazos", "Muñecas"]

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
    const valor = Number(texto.replace(",", "."))
    if (texto.trim() !== "" && Number.isFinite(valor)) cambios[clave] = valor
  }
  for (const clave of quitar) cambios[clave] = null
  const total = Object.keys(cambios).length
  const pendientes = estado.resultado.pendientes_manuales

  return (
    <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="space-y-8">
        {grupos.map(([segmento, angulos]) => (
          <section key={segmento}>
            <h3 className="t-title mb-2 border-b border-ink pb-1.5 text-[19px]">{segmento}</h3>
            <table className="w-full table-fixed text-[14px]">
              <colgroup><col /><col className="w-[104px]" /><col className="w-[64px]" /><col className="w-[30%]" /><col className="w-[140px]" /></colgroup>
              <thead className="sr-only"><tr><th>Medida</th><th>Valor</th><th>Banda REBA</th><th>Notas</th><th>Corrección</th></tr></thead>
              <tbody>
                {angulos.map((angulo) => {
                  const clave = angulo.clave_override
                  const corregido = angulo.fuente === "especialista"
                  const esBinario = angulo.medida === "apoyo_piernas_unilateral"
                  return (
                    <tr key={`${clave}-${angulo.vista}`} className="border-b border-rule-soft align-middle">
                      <td className="py-2.5 pr-3">
                        <span className="font-medium">{NOMBRE_MEDIDA[angulo.medida] ?? angulo.medida}</span>
                        {angulo.lado && <span className="ml-1.5 text-graphite">{angulo.lado === "L" ? "izquierdo" : "derecho"}</span>}
                        <span className="block text-[12px] text-graphite">vista {angulo.vista}</span>
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
                        {!esBinario && (
                          <div className="flex items-center justify-end gap-1.5">
                            <input aria-label={`Corregir ${NOMBRE_MEDIDA[angulo.medida] ?? angulo.medida}`} inputMode="decimal" placeholder="°"
                              value={borrador[clave] ?? ""} onChange={(e) => setBorrador((b) => ({ ...b, [clave]: e.target.value }))}
                              className="campo t-num w-20 px-2 py-1 text-right text-[15px]" />
                            {corregido && (
                              <button title="Volver a la medición automática" aria-pressed={quitar.has(clave)}
                                onClick={() => setQuitar((q) => { const n = new Set(q); if (n.has(clave)) n.delete(clave); else n.add(clave); return n })}
                                className={cn("rounded-md border p-1.5", quitar.has(clave) ? "border-ink bg-ink text-sheet" : "border-rule text-graphite hover:border-ink")}>
                                <RotateCcw className="size-3.5" />
                              </button>
                            )}
                          </div>
                        )}
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
            Si una medición no coincide con lo que ves en piso, escribe el valor correcto. ErgoAI recalcula el REBA y registra el cambio con tu firma.
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
            <p className="mt-1 text-[13px] text-graphite">Datos que la foto o el contexto no permitieron medir.</p>
            <ul className="mt-2 space-y-1.5 text-[14px]">
              {pendientes.slice(0, 12).map((p, i) => (
                <li key={`${p.medida}-${i}`} className="border-l-2 border-[var(--riesgo-medio)] pl-2.5">
                  <span className="font-medium">{NOMBRE_MEDIDA[p.medida.replace(/_[LR]$/, "")] ?? p.medida.replaceAll("_", " ")}</span>
                  {p.motivo && <span className="block text-[13px] text-graphite">{p.motivo}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    </div>
  )
}
