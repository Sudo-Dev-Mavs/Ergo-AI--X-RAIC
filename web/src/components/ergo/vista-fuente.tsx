import { Camera, ImagePlus, Upload, VideoOff, X } from "lucide-react"
import { useEffect, useId, useRef, useState, type ClipboardEvent, type DragEvent, type ReactNode } from "react"

import { HaloSegmented } from "@/components/cult/halo-segmented"
import type { Vista } from "@/lib/api"
import type { Camara } from "@/lib/camaras"
import { esImagenErgo, imagenDesdeClipboard, normalizarImagenErgo } from "@/lib/imagenes"
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

  return (
    <div className="flex min-w-0 flex-col gap-2 md:row-span-4 md:grid md:grid-rows-subgrid">
      <div className="flex flex-col items-start gap-1.5">
        <p className="text-[16px] font-semibold text-jabil">
          {titulo}
          {principal
            ? <span className="etiqueta-estado ml-2 bg-jabil text-white">Obligatoria</span>
            : <span className="ml-2 text-[12px] font-medium text-graphite">Recomendada</span>}
        </p>
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
        <RanuraArchivo titulo={titulo} archivo={archivo} onArchivo={onArchivo} principal={principal} />
      ) : (
        <Marco principal={principal}>
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

function Marco({ children, className, drop, principal }: { children: ReactNode; className?: string; drop?: boolean; principal?: boolean }) {
  return (
    <div className={cn(
      "relative aspect-[4/3] overflow-hidden rounded-[12px]",
      drop ? "drop-zona" : "bg-slate-50 outline outline-rule",
      !drop && (principal ? "outline-[3px] outline-jabil" : "outline-1"),
      drop && principal && "border-jabil border-[3px] border-solid",
      className,
    )}>
      {children}
      {(["top-2.5 left-2.5 border-t-2 border-l-2", "top-2.5 right-2.5 border-t-2 border-r-2", "bottom-2.5 left-2.5 border-b-2 border-l-2", "right-2.5 bottom-2.5 border-r-2 border-b-2"] as const).map((pos) => (
        <span key={pos} aria-hidden className={cn("pointer-events-none absolute size-4 border-jabil/70", pos)} />
      ))}
    </div>
  )
}

function Vacio({ icono, texto }: { icono: ReactNode; texto: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2.5 px-4 text-center">
      {icono}
      <span className="max-w-[22ch] text-[13px] font-medium text-ink-soft">{texto}</span>
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

function RanuraArchivo({ titulo, archivo, onArchivo, principal }: {
  titulo: string
  archivo: File | null
  onArchivo: (archivo: File | null) => void
  principal?: boolean
}) {
  const id = useId()
  const zonaRef = useRef<HTMLDivElement>(null)
  const [vista, setVista] = useState<string | null>(null)
  const [encima, setEncima] = useState(false)
  const [activa, setActiva] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => {
    if (!archivo) {
      setVista(null)
      return
    }
    const url = URL.createObjectURL(archivo)
    setVista(url)
    return () => URL.revokeObjectURL(url)
  }, [archivo])

  async function aplicarArchivo(bruto: File | null) {
    setAviso(null)
    if (!bruto) {
      onArchivo(null)
      return
    }
    if (!esImagenErgo(bruto) && !bruto.type.startsWith("image/")) {
      setAviso("Solo JPG o PNG")
      return
    }
    const normal = await normalizarImagenErgo(bruto, bruto.name || `${titulo.toLowerCase()}.png`)
    if (!normal) {
      setAviso("No se pudo usar esa imagen (usa JPG/PNG)")
      return
    }
    onArchivo(normal)
  }

  const soltar = (evento: DragEvent) => {
    // Evita que el contenedor padre reasigne la foto a otra vista.
    evento.preventDefault()
    evento.stopPropagation()
    setEncima(false)
    const primero = evento.dataTransfer.files[0]
    void aplicarArchivo(primero ?? null)
  }

  const pegarAqui = (evento: ClipboardEvent) => {
    const hayImagen = [...(evento.clipboardData?.items ?? [])].some((i) => i.kind === "file" && i.type.startsWith("image/"))
    if (!hayImagen) return
    evento.preventDefault()
    evento.stopPropagation()
    void imagenDesdeClipboard(evento.clipboardData).then((img) => {
      if (img) void aplicarArchivo(img)
    })
  }

  return (
    <div
      ref={zonaRef}
      className="relative"
      tabIndex={0}
      onFocus={() => setActiva(true)}
      onBlur={() => setActiva(false)}
      onPaste={(e) => void pegarAqui(e)}
      data-ranura-foto="1"
      aria-label={`Zona de foto ${titulo}. Arrastra, elige archivo o pega con Ctrl+V.`}
    >
      <label
        htmlFor={id}
        onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setEncima(true) }}
        onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = "copy"; setEncima(true) }}
        onDragLeave={(e) => {
          // Solo apagar si salimos de la zona (no al entrar a hijos).
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setEncima(false)
        }}
        onDrop={soltar}
        className="block cursor-pointer outline-none"
      >
        <Marco
          drop
          principal={principal}
          className={cn(
            "transition-[border-color,background,box-shadow]",
            encima && "drop-activo",
            activa && !encima && "ring-2 ring-jabil-cyan ring-offset-1",
          )}
        >
          {vista
            ? <img src={vista} alt={`Vista ${titulo.toLowerCase()} seleccionada`} className="pointer-events-none h-full w-full object-contain" />
            : (
              <Vacio
                icono={<ImagePlus className="size-10 text-jabil" strokeWidth={1.5} />}
                texto={encima ? "Suelta la foto aquí" : activa ? "Ctrl+V para pegar" : "Arrastra, elige o Ctrl+V"}
              />
            )}
        </Marco>
        <input
          id={id}
          type="file"
          accept="image/jpeg,image/png,.jpg,.jpeg,.png"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null
            void aplicarArchivo(f)
            e.target.value = ""
          }}
        />
      </label>
      {aviso && <p className="mt-1 text-[12px] font-medium text-[var(--riesgo-muy-alto)]">{aviso}</p>}
      {archivo && (
        <button
          type="button"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onArchivo(null) }}
          className="absolute top-2 right-2 z-10 rounded-md bg-sheet/90 p-1 text-graphite hover:text-ink"
          aria-label={`Quitar foto ${titulo}`}
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}
