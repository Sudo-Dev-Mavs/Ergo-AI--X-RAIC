import { Settings2, X } from "lucide-react"
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react"

import { HaloSwitch } from "@/components/cult/halo-switch"
import { usePreferencias, type Preferencias } from "@/lib/preferencias"
import { cn } from "@/lib/utils"

/** Menú de opciones ligeras: densidad, confirmaciones, ayudas del visor. */
export function PanelOpciones({ className }: { className?: string }) {
  const { preferencias, setPreferencias, resetPreferencias } = usePreferencias()
  const [abierto, setAbierto] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number; width: number } | null>(null)
  const tituloId = useId()
  const ancla = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const boton = useRef<HTMLButtonElement>(null)

  useLayoutEffect(() => {
    if (!abierto || !boton.current) {
      setCoords(null)
      return
    }
    const colocar = () => {
      const r = boton.current!.getBoundingClientRect()
      const ancho = Math.min(340, window.innerWidth - 16)
      let left = r.left
      if (left + ancho > window.innerWidth - 8) left = Math.max(8, window.innerWidth - ancho - 8)
      // Preferir debajo del botón; si no cabe, abrir hacia arriba.
      const altoAprox = 420
      const debajo = r.bottom + 8
      const arriba = r.top - 8 - altoAprox
      const top = debajo + altoAprox < window.innerHeight - 8 ? debajo : Math.max(8, arriba)
      setCoords({ top, left, width: ancho })
    }
    colocar()
    window.addEventListener("resize", colocar)
    window.addEventListener("scroll", colocar, true)
    return () => {
      window.removeEventListener("resize", colocar)
      window.removeEventListener("scroll", colocar, true)
    }
  }, [abierto])

  useEffect(() => {
    if (!abierto) return
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setAbierto(false) }
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node
      if (ancla.current?.contains(t) || panel.current?.contains(t)) return
      setAbierto(false)
    }
    window.addEventListener("keydown", onKey)
    window.addEventListener("mousedown", onClick)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("mousedown", onClick)
    }
  }, [abierto])

  return (
    <div className={cn("relative", className)} ref={ancla}>
      <button
        ref={boton}
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
      {abierto && coords && (
        <div
          ref={panel}
          id={tituloId}
          role="dialog"
          aria-label="Opciones de la interfaz"
          className="fixed z-[70] max-h-[min(70dvh,520px)] overflow-y-auto rounded-xl border border-rule bg-sheet p-4 shadow-[0_12px_40px_-12px_rgba(0,56,118,0.35)]"
          style={{ top: coords.top, left: coords.left, width: coords.width }}
        >
          <div className="mb-3 flex items-center justify-between">
            <p className="t-title text-[15px] text-jabil">Preferencias</p>
            <button type="button" className="rounded-md p-1 text-graphite hover:text-jabil" aria-label="Cerrar" onClick={() => setAbierto(false)}>
              <X className="size-4" />
            </button>
          </div>
          <p className="mb-3 text-[12px] leading-snug text-graphite">
            Solo cambian cómo se ve y se usa la interfaz en este equipo. No modifican el cálculo REBA ni la bitácora.
          </p>
          <ul className="space-y-3.5 text-[13px]">
            <Fila
              etiqueta="Densidad"
              ayuda="Cómoda: letras y botones más grandes, con más aire. Compacta: se nota al instante — texto más chico, menos márgenes y botones más bajos."
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
              ayuda={'Al abrir un caso: «Con ángulos» muestra la foto con esqueleto y grados dibujados; «Original» muestra la foto limpia sin anotaciones.'}
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
              ayuda="Si está activo, pide confirmación antes de aprobar/rechazar una recomendación o de firmar el informe."
              checked={preferencias.confirmarAcciones}
              onChange={(v) => setPreferencias({ confirmarAcciones: v })}
            />
            <Toggle
              etiqueta="Mostrar ayudas del visor"
              ayuda="Muestra el botón «?» sobre la foto con atajos (rueda, +/−, arrastrar). No quita ni pone los ángulos dibujados."
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

function Fila({ etiqueta, ayuda, control }: { etiqueta: string; ayuda: string; control: ReactNode }) {
  return (
    <li className="grid gap-1">
      <span className="font-medium text-ink-soft">{etiqueta}</span>
      {control}
      <p className="text-[11px] leading-snug text-graphite">{ayuda}</p>
    </li>
  )
}

function Toggle({
  etiqueta,
  ayuda,
  checked,
  onChange,
}: {
  etiqueta: string
  ayuda: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  const id = useId()
  return (
    <li className="grid gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="min-w-0 flex-1 font-medium text-ink-soft">{etiqueta}</label>
        <HaloSwitch
          id={id}
          size="sm"
          translucent={false}
          checked={checked}
          onCheckedChange={(v) => onChange(Boolean(v))}
          aria-label={etiqueta}
        />
      </div>
      <p className="text-[11px] leading-snug text-graphite">{ayuda}</p>
    </li>
  )
}
