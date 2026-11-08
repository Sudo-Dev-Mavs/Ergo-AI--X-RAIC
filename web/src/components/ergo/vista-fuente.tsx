import { Camera, ImagePlus, Upload, VideoOff, X } from "lucide-react"
import { useEffect, useId, useRef, useState, type DragEvent, type ReactNode } from "react"

import { HaloSegmented } from "@/components/cult/halo-segmented"
import type { Vista } from "@/lib/api"
import type { Camara } from "@/lib/camaras"
import { cn } from "@/lib/utils"

export type Fuente = { modo: "archivo" } | { modo: "camara"; deviceId: string | null }

/** Una vista (frente, costado o aérea): foto subida o cámara asignada con vista previa en vivo. */
export function VistaFuente({ vista, titulo, ayuda, principal, fuente, onFuente, archivo, onArchivo, camaras, abrir, capturaElegida }: {
  vista: Vista
  titulo: string
  ayuda: string
  principal?: boolean
  fuente: Fuente
  onFuente: (fuente: Fuente) => void
  archivo: File | null
  onArchivo: (archivo: File | null) => void
  camaras: Camara[]
  abrir: (deviceId: string) => Promise<MediaStream>
  capturaElegida: string | null
}) {
  const idSelect = useId()
  const camaraConectada = fuente.modo === "camara" && fuente.deviceId && camaras.some((c) => c.deviceId === fuente.deviceId)

  // Cuatro filas fijas (encabezado, selector de cámara, recuadro, ayuda). En escritorio las tres vistas
  // comparten esas filas con CSS subgrid, así los recuadros quedan al mismo nivel aunque un encabezado
  // ocupe dos líneas o solo una vista use cámara.
  return (
    <div className="flex min-w-0 flex-col gap-2 md:row-span-4 md:grid md:grid-rows-subgrid">
      <div className="flex flex-col items-start gap-1.5">
        <p className="text-[16px] font-semibold">{titulo}{principal && <span className="ml-1.5 text-[13px] font-normal text-graphite">principal</span>}</p>
        <HaloSegmented translucent={false} className="overflow-x-auto" value={fuente.modo}
          onValueChange={(modo) => onFuente(modo === "camara" ? { modo: "camara", deviceId: fuente.modo === "camara" ? fuente.deviceId : camaras[0]?.deviceId ?? null } : { modo: "archivo" })}
          items={[{ value: "archivo", label: <span className="flex items-center gap-1.5"><Upload className="size-3.5" />Archivo</span> },
            { value: "camara", label: <span className="flex items-center gap-1.5"><Camera className="size-3.5" />Cámara</span> }]} />
      </div>

      <div className={cn("min-w-0", fuente.modo === "archivo" && "hidden md:block")}>
        {fuente.modo === "camara" && (
          <>
            <label htmlFor={idSelect} className="sr-only">Cámara para la vista {titulo}</label>
            <select id={idSelect} className="campo py-1.5 text-[14px]" value={fuente.deviceId ?? ""}
              onChange={(e) => onFuente({ modo: "camara", deviceId: e.target.value || null })}>
              <option value="">{camaras.length ? "Elige una cámara" : "Sin cámaras detectadas"}</option>
              {camaras.map((c) => <option key={c.deviceId} value={c.deviceId}>{c.nombre}</option>)}
              {fuente.deviceId && !camaraConectada && <option value={fuente.deviceId}>Cámara guardada, no conectada</option>}
            </select>
          </>
        )}
      </div>

      {fuente.modo === "archivo" ? (
        <RanuraArchivo titulo={titulo} archivo={archivo} onArchivo={onArchivo} />
      ) : (
        <Marco>
          {camaraConectada && fuente.deviceId
            ? <EnVivo key={fuente.deviceId} deviceId={fuente.deviceId} abrir={abrir} vista={vista} />
            : <Vacio icono={<VideoOff className="size-6 text-graphite" strokeWidth={1.5} />} texto={camaras.length ? "Elige qué cámara cubre esta vista" : "Detecta las cámaras arriba"} />}
        </Marco>
      )}

      <div>
        {fuente.modo === "camara" && capturaElegida && <p className="text-[13px] font-medium">Se analizará la toma de las {capturaElegida}</p>}
        <p className="text-[13px] leading-snug text-graphite">{ayuda}</p>
      </div>
    </div>
  )
}

function Marco({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("relative aspect-[4/3] overflow-hidden rounded-[10px] bg-ink/[0.04] outline outline-1 outline-rule", className)}>
      {children}
      {(["top-2 left-2 border-t-2 border-l-2", "top-2 right-2 border-t-2 border-r-2", "bottom-2 left-2 border-b-2 border-l-2", "right-2 bottom-2 border-r-2 border-b-2"] as const).map((pos) => (
        <span key={pos} aria-hidden className={cn("pointer-events-none absolute size-4 border-ink/70", pos)} />
      ))}
    </div>
  )
}

function Vacio({ icono, texto }: { icono: ReactNode; texto: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center">
      {icono}
      <span className="text-[13px] text-graphite">{texto}</span>
    </div>
  )
}

function EnVivo({ deviceId, abrir, vista }: { deviceId: string; abrir: (id: string) => Promise<MediaStream>; vista: Vista }) {
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [resolucion, setResolucion] = useState<string | null>(null)

  useEffect(() => {
    let vigente = true
    abrir(deviceId)
      .then((flujo) => {
        if (!vigente || !video.current) return
        video.current.srcObject = flujo
        void video.current.play().catch(() => undefined)
        const ajustes = flujo.getVideoTracks()[0]?.getSettings()
        if (ajustes?.width && ajustes?.height) setResolucion(`${ajustes.width}×${ajustes.height}`)
      })
      .catch((e) => vigente && setError(e instanceof DOMException && e.name === "NotReadableError" ? "La cámara está ocupada por otra aplicación." : "No se pudo abrir esta cámara."))
    return () => {
      vigente = false
    }
  }, [abrir, deviceId])

  if (error) return <Vacio icono={<VideoOff className="size-6 text-graphite" strokeWidth={1.5} />} texto={error} />
  return (
    <>
      <video ref={video} muted playsInline autoPlay className="h-full w-full object-contain" aria-label={`Vista previa en vivo, ${vista}`} />
      <span className="absolute top-2.5 left-8 flex items-center gap-1.5 rounded-full bg-ink/80 px-2 py-0.5 text-[12px] text-sheet">
        <span className="size-1.5 animate-pulse rounded-full bg-sheet" aria-hidden /> En vivo{resolucion && <span className="t-num opacity-70">{resolucion}</span>}
      </span>
    </>
  )
}

function RanuraArchivo({ titulo, archivo, onArchivo }: { titulo: string; archivo: File | null; onArchivo: (archivo: File | null) => void }) {
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
    <div className="relative">
      <label htmlFor={id} onDragOver={(e) => { e.preventDefault(); setEncima(true) }} onDragLeave={() => setEncima(false)} onDrop={soltar} className="block cursor-pointer">
        <Marco className={cn("transition-[outline-color]", encima ? "outline-2 outline-ink" : "hover:outline-ink")}>
          {vista
            ? <img src={vista} alt={`Vista ${titulo.toLowerCase()} seleccionada`} className="h-full w-full object-contain" />
            : <Vacio icono={<ImagePlus className="size-6 text-graphite" strokeWidth={1.5} />} texto="Arrastra o elige una foto" />}
        </Marco>
        <input id={id} type="file" accept="image/jpeg,image/png" className="sr-only" onChange={(e) => onArchivo(e.target.files?.[0] ?? null)} />
      </label>
      {archivo && (
        <button type="button" onClick={() => onArchivo(null)} className="absolute top-2 right-2 rounded-md bg-sheet/90 p-1 text-graphite hover:text-ink" aria-label={`Quitar foto ${titulo}`}>
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}
