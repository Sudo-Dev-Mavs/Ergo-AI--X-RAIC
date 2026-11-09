import { Settings2, X } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import { usePreferencias, type Preferencias } from "@/lib/preferencias"
import { cn } from "@/lib/utils"

/** Menú de opciones ligeras: densidad, confirmaciones, ayudas del visor. */
export function PanelOpciones({ className }: { className?: string }) {
  const { preferencias, setPreferencias, resetPreferencias } = usePreferencias()
  const [abierto, setAbierto] = useState(false)
  const tituloId = useId()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!abierto) return
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setAbierto(false) }
    const onClick = (e: MouseEvent) => {
      if (panel.current && !panel.current.contains(e.target as Node)) setAbierto(false)
    }
    window.addEventListener("keydown", onKey)
    window.addEventListener("mousedown", onClick)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("mousedown", onClick)
    }
  }, [abierto])

  return (
    <div className={cn("relative", className)} ref={panel}>
      <button
        type="button"
        className={cn(
          "inline-flex w-full items-center justify-start gap-2 rounded-lg border border-white/30 bg-white/10 px-3 py-2 text-[14px] font-medium text-white transition-colors hover:bg-white/15",
          abierto && "border-jabil-cyan bg-white/20",
        )}
        aria-expanded={abierto}
        aria-controls={tituloId}
        onClick={() => setAbierto((v) => !v)}
      >
        <Settings2 className="size-4" strokeWidth={1.75} />
        Opciones
      </button>
      {abierto && (
        <div
          id={tituloId}
          role="dialog"
          aria-label="Opciones de la interfaz"
          className="absolute top-[calc(100%+8px)] left-0 z-40 w-[min(100vw-2rem,320px)] rounded-xl border border-rule bg-sheet p-4 shadow-[0_12px_40px_-12px_rgba(0,56,118,0.35)] lg:left-0"
        >
          <div className="mb-3 flex items-center justify-between">
            <p className="t-title text-[15px] text-jabil">Preferencias</p>
            <button type="button" className="rounded-md p-1 text-graphite hover:text-jabil" aria-label="Cerrar" onClick={() => setAbierto(false)}>
              <X className="size-4" />
            </button>
          </div>
          <ul className="space-y-3 text-[13px]">
            <Fila
              etiqueta="Densidad"
              control={
                <select
                  className="campo py-1.5 text-[13px]"
                  value={preferencias.densidad}
                  onChange={(e) => setPreferencias({ densidad: e.target.value as Preferencias["densidad"] })}
                >
                  <option value="comoda">Cómoda</option>
                  <option value="compacta">Compacta</option>
                </select>
              }
            />
            <Fila
              etiqueta="Foto inicial del caso"
              control={
                <select
                  className="campo py-1.5 text-[13px]"
                  value={preferencias.fotoInicial}
                  onChange={(e) => setPreferencias({ fotoInicial: e.target.value as Preferencias["fotoInicial"] })}
                >
                  <option value="anotada">Con ángulos</option>
                  <option value="original">Original</option>
                </select>
              }
            />
            <Toggle
              etiqueta="Confirmar al aprobar o rechazar"
              checked={preferencias.confirmarAcciones}
              onChange={(v) => setPreferencias({ confirmarAcciones: v })}
            />
            <Toggle
              etiqueta="Mostrar ayudas del visor"
              checked={preferencias.mostrarAyudas}
              onChange={(v) => setPreferencias({ mostrarAyudas: v })}
            />
          </ul>
          <button type="button" className="boton-linea mt-4 w-full justify-center text-[13px]" onClick={resetPreferencias}>
            Restaurar valores
          </button>
        </div>
      )}
    </div>
  )
}

function Fila({ etiqueta, control }: { etiqueta: string; control: React.ReactNode }) {
  return (
    <li className="grid gap-1.5">
      <span className="font-medium text-ink-soft">{etiqueta}</span>
      {control}
    </li>
  )
}

function Toggle({ etiqueta, checked, onChange }: { etiqueta: string; checked: boolean; onChange: (v: boolean) => void }) {
  const id = useId()
  return (
    <li className="flex items-center justify-between gap-3">
      <label htmlFor={id} className="font-medium text-ink-soft">{etiqueta}</label>
      <input id={id} type="checkbox" className="size-4 accent-[var(--jabil)]" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </li>
  )
}
