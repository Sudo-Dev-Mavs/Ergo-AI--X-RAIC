import { Aperture, EyeOff, Pause, Play, Trash2, UserX } from "lucide-react"
import { useEffect, useState } from "react"

import { BorderBeam } from "@/components/magicui/border-beam"
import { api, type Toma, type Vista } from "@/lib/api"
import { cn } from "@/lib/utils"

const ORDEN: Vista[] = ["costado", "frente", "aerea"]
const NOMBRE: Record<Vista, string> = { costado: "costado", frente: "frente", aerea: "aérea" }

/** Vistas de la toma en las que no se encontró a nadie (no se difuminó nada). */
export function sinPersona(toma: Toma): Vista[] {
  return toma.vistas.filter((v) => toma.privacidad?.[v]?.rostros === 0)
}
export const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", second: "2-digit" })

/** Temporizador de capturas (cada N, definido por el operador) y tira de tomas guardadas para esta evaluación. */
export function PanelTomas({ borrador, tomas, seleccion, onSeleccion, seguirUltima, onSeguirUltima, auto, onAuto, intervaloS, onIntervalo,
  onCapturarAhora, proximaEn, capturando, error, onDescartar, maxTomas, retencionHoras, camarasAsignadas, capturaBust }: {
  borrador: string
  tomas: Toma[]
  seleccion: string | null
  onSeleccion: (id: string) => void
  seguirUltima: boolean
  onSeguirUltima: () => void
  auto: boolean
  onAuto: (activo: boolean) => void
  intervaloS: number
  onIntervalo: (segundos: number) => void
  onCapturarAhora: () => void
  proximaEn: number | null
  capturando: boolean
  error: string | null
  onDescartar: () => void
  maxTomas: number
  retencionHoras: number
  camarasAsignadas: number
  capturaBust?: number
}) {
  const [unidad, setUnidad] = useState<"s" | "min">(intervaloS >= 120 && intervaloS % 60 === 0 ? "min" : "s")
  const [texto, setTexto] = useState(String(unidad === "min" ? intervaloS / 60 : intervaloS))
  useEffect(() => setTexto(String(unidad === "min" ? intervaloS / 60 : intervaloS)), [intervaloS, unidad])

  const aplicar = (valor: string, u = unidad) => {
    setTexto(valor)
    const numero = Number(valor.replace(",", "."))
    if (Number.isFinite(numero) && numero > 0) onIntervalo(Math.min(3600, Math.max(2, Math.round(u === "min" ? numero * 60 : numero))))
  }
  const sinCamaras = camarasAsignadas === 0

  return (
    <section className="relative overflow-hidden rounded-[14px] border border-rule bg-sheet p-4 sm:p-5" aria-label="Capturas automáticas">
      {auto && <BorderBeam size={140} duration={6} colorFrom="#13233b" colorTo="#8a99ad" borderWidth={1.5} />}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="t-title text-[18px]">Capturas automáticas</h3>
          <p className="mt-1 max-w-[60ch] text-[14px] text-ink-soft">
            {sinCamaras
              ? "Asigna una cámara a alguna vista para capturar."
              : `Cada toma guarda ${camarasAsignadas === 1 ? "la vista con cámara" : `las ${camarasAsignadas} vistas con cámara`} en el mismo instante. Sigue capturando mientras llenas los pasos 2 y 3.`}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-[13px] text-graphite">
            Capturar cada
            <span className="mt-1 flex">
              <input className="campo t-num w-20 rounded-r-none text-[16px]" inputMode="decimal" value={texto} onChange={(e) => aplicar(e.target.value)} aria-label="Intervalo entre capturas" />
              <select className="campo w-auto rounded-l-none border-l-0 text-[14px]" value={unidad} aria-label="Unidad del intervalo"
                onChange={(e) => { const u = e.target.value as "s" | "min"; setUnidad(u); aplicar(texto, u) }}>
                <option value="s">segundos</option>
                <option value="min">minutos</option>
              </select>
            </span>
          </label>
          <button type="button" className={auto ? "boton-linea" : "boton-tinta"} disabled={sinCamaras} onClick={() => onAuto(!auto)}>
            {auto ? <><Pause className="size-4" /> Detener</> : <><Play className="size-4" /> Iniciar</>}
          </button>
          <button type="button" className="boton-linea" disabled={sinCamaras || capturando} onClick={onCapturarAhora}>
            <Aperture className={cn("size-4", capturando && "animate-spin")} /> Capturar ahora
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-graphite" aria-live="polite">
        {auto && proximaEn != null && <span className="font-medium text-ink"><span className="mr-1.5 inline-block size-2 animate-pulse rounded-full bg-ink align-middle" aria-hidden />Próxima toma en <span className="t-num">{proximaEn}</span> s</span>}
        <span><span className="t-num text-ink">{tomas.length}</span> de {maxTomas} tomas guardadas en este equipo; se borran a las {retencionHoras} h</span>
        <span className="flex items-center gap-1"><EyeOff className="size-3.5" aria-hidden />Cada toma se guarda con el rostro difuminado; la vista en vivo no se guarda</span>
        {error && <span role="alert" className="text-[var(--riesgo-muy-alto)]">{error}</span>}
      </div>

      {tomas.length > 0 && (
        <>
          <div className="mt-4 flex items-center justify-between gap-3">
            <p className="text-[14px] font-medium">Toma a analizar</p>
            <div className="flex items-center gap-2">
              {!seguirUltima && <button type="button" className="text-[13px] text-ink-soft underline underline-offset-4 hover:text-ink" onClick={onSeguirUltima}>Usar siempre la más reciente</button>}
              <button type="button" className="boton-linea px-2.5 py-1 text-[13px]" onClick={onDescartar}><Trash2 className="size-3.5" /> Descartar tomas</button>
            </div>
          </div>
          <ol className="mt-2 flex gap-2 overflow-x-auto pb-2" aria-label="Tomas capturadas">
            {tomas.map((toma) => {
              const elegida = toma.id === seleccion
              return (
                <li key={toma.id} className="shrink-0">
                  <button type="button" onClick={() => onSeleccion(toma.id)} aria-pressed={elegida}
                    className={cn("rounded-[10px] p-1.5 text-left transition-colors", elegida ? "trazo-tinta" : "border border-transparent hover:border-rule")}>
                    <span className="flex gap-1">
                      {ORDEN.filter((v) => toma.vistas.includes(v)).map((v) => (
                        <img key={`${v}-${capturaBust ?? 0}`} src={api.captura(borrador, toma.id, v, capturaBust)} alt={`Toma ${hora(toma.fecha)}, vista ${v}`} loading="lazy"
                          className="h-14 w-[74px] rounded-md bg-ink/5 object-cover" />
                      ))}
                    </span>
                    <span className="mt-1 flex items-center justify-between gap-2 px-0.5 text-[12px]">
                      <span className="t-num text-[13px]">{hora(toma.fecha)}</span>
                      {elegida && <span className="font-medium">{seguirUltima ? "Más reciente" : "Elegida"}</span>}
                    </span>
                    <span className="flex items-center gap-1 px-0.5 text-[12px] text-graphite">
                      {sinPersona(toma).length
                        ? <><UserX className="size-3.5" aria-hidden />Sin persona en {sinPersona(toma).map((v) => NOMBRE[v]).join(" y ")}</>
                        : <><EyeOff className="size-3.5" aria-hidden />Rostro difuminado</>}
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </>
      )}
    </section>
  )
}
