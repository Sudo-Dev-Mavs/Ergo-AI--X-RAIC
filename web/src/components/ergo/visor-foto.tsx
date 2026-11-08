import { ImagePlus, X } from "lucide-react"
import { useEffect, useId, useState, type DragEvent } from "react"

import { cn } from "@/lib/utils"

/** Ranura de fotografía dibujada como visor de cámara con marcas de esquina. */
export function VisorFoto({ titulo, ayuda, archivo, onArchivo, principal = false }: {
  titulo: string
  ayuda: string
  archivo: File | null
  onArchivo: (archivo: File | null) => void
  principal?: boolean
}) {
  const id = useId()
  const [vista, setVista] = useState<string | null>(null)
  const [encima, setEncima] = useState(false)

  useEffect(() => {
    if (!archivo) {
      setVista(null)
      return
    }
    const url = URL.createObjectURL(archivo)
    setVista(url)
    return () => URL.revokeObjectURL(url)
  }, [archivo])

  const soltar = (evento: DragEvent) => {
    evento.preventDefault()
    setEncima(false)
    const primero = evento.dataTransfer.files[0]
    if (primero && /image\/(jpeg|png)/.test(primero.type)) onArchivo(primero)
  }

  return (
    <div className="min-w-0">
      <label htmlFor={id} onDragOver={(e) => { e.preventDefault(); setEncima(true) }} onDragLeave={() => setEncima(false)} onDrop={soltar}
        className={cn("group relative block aspect-[3/4] cursor-pointer overflow-hidden rounded-[10px] bg-sheet transition-colors",
          encima ? "outline-2 outline-ink" : "outline-1 outline-rule hover:outline-ink", "outline")}>
        {vista ? (
          <img src={vista} alt={`Vista ${titulo.toLowerCase()} seleccionada`} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center">
            <ImagePlus className="size-6 text-graphite" strokeWidth={1.5} />
            <span className="text-[13px] text-graphite">Arrastra o elige una foto</span>
          </div>
        )}
        {(["top-2 left-2 border-t-2 border-l-2", "top-2 right-2 border-t-2 border-r-2", "bottom-2 left-2 border-b-2 border-l-2", "right-2 bottom-2 border-r-2 border-b-2"] as const).map((pos) => (
          <span key={pos} aria-hidden className={cn("pointer-events-none absolute size-4", pos, vista ? "border-sheet" : "border-ink/70")} />
        ))}
        <input id={id} type="file" accept="image/jpeg,image/png" className="sr-only"
          onChange={(e) => onArchivo(e.target.files?.[0] ?? null)} />
      </label>
      <div className="mt-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-[15px] font-semibold">{titulo}{principal && <span className="ml-1.5 text-[13px] font-normal text-graphite">principal</span>}</p>
          <p className="text-[13px] leading-snug text-graphite">{ayuda}</p>
        </div>
        {archivo && (
          <button type="button" onClick={() => onArchivo(null)} className="rounded-md p-1 text-graphite hover:bg-rule-soft hover:text-ink" aria-label={`Quitar foto ${titulo}`}>
            <X className="size-4" />
          </button>
        )}
      </div>
    </div>
  )
}
