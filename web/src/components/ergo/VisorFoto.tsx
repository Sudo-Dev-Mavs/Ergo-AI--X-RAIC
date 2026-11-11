import { CircleHelp, Maximize2, Minus, Plus, RotateCcw, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react"
import { createPortal } from "react-dom"

import { usePreferencias } from "@/lib/preferencias"
import { cn } from "@/lib/utils"

interface Props {
  src: string | null
  alt: string
  className?: string
  barraExtra?: ReactNode
  vacio?: ReactNode
}

const MIN = 1
const MAX = 5
const PASO = 0.25

/** Visor: zoom, pan, teclado. El ícono □□ abre la foto a pantalla completa. */
export function VisorFoto({ src, alt, className, barraExtra, vacio }: Props) {
  const { preferencias } = usePreferencias()
  const marco = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [ayudaAbierta, setAyudaAbierta] = useState(false)
  const [ampliada, setAmpliada] = useState(false)
  const arrastre = useRef<{ id: number; x: number; y: number; ox: number; oy: number } | null>(null)

  const reset = useCallback(() => {
    setZoom(1)
    setOffset({ x: 0, y: 0 })
  }, [])

  useEffect(() => {
    reset()
  }, [src, reset])

  useEffect(() => {
    const nodo = marco.current
    if (!nodo) return
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return
      if (e.key === "+" || e.key === "=") {
        e.preventDefault()
        setZoom((z) => Math.min(MAX, +(z + PASO).toFixed(2)))
      } else if (e.key === "-" || e.key === "_") {
        e.preventDefault()
        setZoom((z) => Math.max(MIN, +(z - PASO).toFixed(2)))
      } else if (e.key === "0") {
        e.preventDefault()
        reset()
      }
    }
    const onWheelNative = (e: globalThis.WheelEvent) => {
      if (!src) return
      e.preventDefault()
      const delta = e.deltaY < 0 ? PASO : -PASO
      setZoom((z) => {
        const siguiente = Math.min(MAX, Math.max(MIN, +(z + delta).toFixed(2)))
        if (siguiente === 1) setOffset({ x: 0, y: 0 })
        return siguiente
      })
    }
    nodo.addEventListener("keydown", onKey)
    nodo.addEventListener("wheel", onWheelNative, { passive: false })
    return () => {
      nodo.removeEventListener("keydown", onKey)
      nodo.removeEventListener("wheel", onWheelNative)
    }
  }, [reset, src])

  useEffect(() => {
    if (!ampliada) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAmpliada(false)
    }
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener("keydown", onKey)
    }
  }, [ampliada])

  const onPointerDown = (e: ReactPointerEvent) => {
    if (!src || zoom <= 1 || e.button !== 0) return
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    arrastre.current = { id: e.pointerId, x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y }
  }
  const onPointerMove = (e: ReactPointerEvent) => {
    const a = arrastre.current
    if (!a || a.id !== e.pointerId) return
    setOffset({ x: a.ox + (e.clientX - a.x), y: a.oy + (e.clientY - a.y) })
  }
  const onPointerUp = (e: ReactPointerEvent) => {
    if (arrastre.current?.id === e.pointerId) arrastre.current = null
  }

  return (
    <div className={cn("flex min-w-0 flex-col", className)}>
      <div
        ref={marco}
        tabIndex={0}
        role="img"
        aria-label={alt}
        onDoubleClick={reset}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className={cn(
          "relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-[14px] border border-rule bg-slate-50 outline-none focus-visible:ring-2 focus-visible:ring-jabil-cyan",
          zoom > 1 ? "cursor-grab active:cursor-grabbing" : "cursor-zoom-in",
        )}
      >
        {src ? (
          <img
            src={src}
            alt={alt}
            draggable={false}
            className="relative max-h-full max-w-full touch-none select-none object-contain will-change-transform"
            style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`, transition: arrastre.current ? undefined : "transform 120ms ease-out" }}
          />
        ) : (
          <div className="relative px-6 text-center text-[14px] text-graphite">{vacio ?? "Sin imagen"}</div>
        )}
        {preferencias.mostrarAyudas && src && (
          <div className="absolute top-2 right-2 z-10">
            <button
              type="button"
              className="rounded-md bg-jabil/90 p-1.5 text-white hover:bg-jabil"
              aria-label="Ayuda del visor"
              aria-expanded={ayudaAbierta}
              onClick={(e) => { e.stopPropagation(); setAyudaAbierta((v) => !v) }}
            >
              <CircleHelp className="size-4" />
            </button>
            {ayudaAbierta && (
              <div className="absolute top-9 right-0 w-56 rounded-lg border border-rule bg-sheet p-3 text-[12px] leading-snug text-ink-soft shadow-lg">
                Rueda o +/−: zoom. Arrastra con zoom: mover. Doble clic o 0: reset. □□ amplía a pantalla completa.
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <BotonVista aria="Alejar" onClick={() => setZoom((z) => Math.max(MIN, +(z - PASO).toFixed(2)))} disabled={!src || zoom <= MIN}><Minus className="size-4" /></BotonVista>
          <span className="t-num min-w-[3.5rem] text-center text-[13px] text-graphite">{Math.round(zoom * 100)}%</span>
          <BotonVista aria="Acercar" onClick={() => setZoom((z) => Math.min(MAX, +(z + PASO).toFixed(2)))} disabled={!src || zoom >= MAX}><Plus className="size-4" /></BotonVista>
          <BotonVista aria="Restablecer zoom" onClick={reset} disabled={!src || (zoom === 1 && offset.x === 0 && offset.y === 0)}><RotateCcw className="size-4" /></BotonVista>
          <BotonVista aria="Ampliar imagen" onClick={() => setAmpliada(true)} disabled={!src}><Maximize2 className="size-4" /></BotonVista>
        </div>
        {barraExtra}
      </div>

      {ampliada && src && createPortal(
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label={alt}
          onClick={() => setAmpliada(false)}
        >
          <button
            type="button"
            className="absolute top-4 right-4 z-[101] rounded-lg bg-white/10 p-2 text-white hover:bg-white/20"
            aria-label="Cerrar imagen ampliada"
            onClick={() => setAmpliada(false)}
          >
            <X className="size-5" />
          </button>
          <img
            src={src}
            alt={alt}
            draggable={false}
            className="max-h-[min(96vh,100%)] max-w-[min(96vw,100%)] object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>,
        document.body,
      )}
    </div>
  )
}

function BotonVista({ children, onClick, disabled, aria }: { children: ReactNode; onClick: () => void; disabled?: boolean; aria: string }) {
  return (
    <button type="button" className="boton-linea px-2.5" onClick={onClick} disabled={disabled} aria-label={aria}>
      {children}
    </button>
  )
}
