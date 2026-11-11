import { X } from "lucide-react"
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react"

import { cn } from "@/lib/utils"

export type OpcionesDialogo = {
  titulo: string
  detalle?: string
  confirmarEtiqueta?: string
  cancelarEtiqueta?: string
  /** `peligro` = acción irreversible / rechazo / eliminar */
  tono?: "normal" | "peligro"
  /** Si se define, muestra un campo de texto (p. ej. motivo de rechazo). */
  motivo?: {
    etiqueta: string
    placeholder?: string
    obligatorio?: boolean
  }
}

type ResultadoDialogo = { ok: false } | { ok: true; motivo: string }

type ContextoDialogo = {
  pedir: (opciones: OpcionesDialogo) => Promise<ResultadoDialogo>
}

const Contexto = createContext<ContextoDialogo | null>(null)

export function ProveedorDialogo({ children }: { children: ReactNode }) {
  const [activo, setActivo] = useState<(OpcionesDialogo & { id: number }) | null>(null)
  const [motivo, setMotivo] = useState("")
  const resolver = useRef<((r: ResultadoDialogo) => void) | null>(null)
  const contador = useRef(0)
  const tituloId = useId()
  const detalleId = useId()
  const campoRef = useRef<HTMLTextAreaElement | null>(null)

  const cerrar = useCallback((resultado: ResultadoDialogo) => {
    resolver.current?.(resultado)
    resolver.current = null
    setActivo(null)
    setMotivo("")
  }, [])

  const pedir = useCallback((opciones: OpcionesDialogo) => {
    contador.current += 1
    setMotivo("")
    setActivo({ ...opciones, id: contador.current })
    return new Promise<ResultadoDialogo>((resolve) => {
      resolver.current = resolve
    })
  }, [])

  useEffect(() => {
    if (!activo) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") cerrar({ ok: false })
    }
    window.addEventListener("keydown", onKey)
    const t = window.setTimeout(() => {
      if (activo.motivo) campoRef.current?.focus()
      else (document.getElementById(`dialogo-confirmar-${activo.id}`) as HTMLButtonElement | null)?.focus()
    }, 30)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.clearTimeout(t)
    }
  }, [activo, cerrar])

  const peligro = activo?.tono === "peligro"
  const motivoObligatorio = Boolean(activo?.motivo?.obligatorio)
  const puedeConfirmar = !motivoObligatorio || motivo.trim().length > 0

  return (
    <Contexto.Provider value={{ pedir }}>
      {children}
      {activo && (
        <div className="fixed inset-0 z-[80] flex items-end justify-center p-4 sm:items-center" role="presentation">
          <button
            type="button"
            className="absolute inset-0 bg-jabil-deep/45 backdrop-blur-[2px]"
            aria-label="Cerrar"
            onClick={() => cerrar({ ok: false })}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={tituloId}
            aria-describedby={activo.detalle ? detalleId : undefined}
            className="relative z-[81] w-full max-w-[420px] rounded-[14px] border border-rule bg-sheet p-5 shadow-[0_24px_60px_-20px_rgba(0,37,84,0.45)] sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 id={tituloId} className="t-title text-[18px] text-jabil sm:text-[19px]">{activo.titulo}</h2>
                {activo.detalle && (
                  <p id={detalleId} className="mt-2 text-[14px] leading-snug text-ink-soft">{activo.detalle}</p>
                )}
              </div>
              <button
                type="button"
                className="shrink-0 rounded-md p-1 text-graphite hover:bg-slate-100 hover:text-ink"
                aria-label="Cerrar"
                onClick={() => cerrar({ ok: false })}
              >
                <X className="size-4" />
              </button>
            </div>

            {activo.motivo && (
              <label className="mt-4 block text-[13px] font-medium text-ink-soft">
                {activo.motivo.etiqueta}
                <textarea
                  ref={campoRef}
                  rows={3}
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                  placeholder={activo.motivo.placeholder}
                  className="campo mt-1.5 w-full resize-none font-normal"
                />
              </label>
            )}

            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button type="button" className="boton-linea" onClick={() => cerrar({ ok: false })}>
                {activo.cancelarEtiqueta ?? "Cancelar"}
              </button>
              <button
                id={`dialogo-confirmar-${activo.id}`}
                type="button"
                disabled={!puedeConfirmar}
                className={cn(
                  peligro
                    ? "inline-flex items-center justify-center gap-2 rounded-lg border border-red-700 bg-red-700 px-3.5 py-2 text-[14px] font-semibold text-white hover:bg-red-800 disabled:opacity-45"
                    : "boton-tinta",
                )}
                onClick={() => cerrar({ ok: true, motivo: motivo.trim() })}
              >
                {activo.confirmarEtiqueta ?? "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Contexto.Provider>
  )
}

export function useDialogo() {
  const ctx = useContext(Contexto)
  if (!ctx) throw new Error("useDialogo fuera de ProveedorDialogo")
  return ctx
}
