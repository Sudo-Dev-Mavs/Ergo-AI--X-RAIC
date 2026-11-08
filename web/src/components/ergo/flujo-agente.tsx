import { Camera, ClipboardCheck, Gauge, ListChecks, ScanLine, Triangle } from "lucide-react"
import { createRef, forwardRef, useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { AnimatedBeam } from "@/components/magicui/animated-beam"
import { BorderBeam } from "@/components/magicui/border-beam"
import { cn } from "@/lib/utils"

const PASOS = [
  { icono: Camera, titulo: "Fotos", detalle: "Frente, costado y aérea" },
  { icono: ScanLine, titulo: "Pose", detalle: "MediaPipe, en este equipo" },
  { icono: Triangle, titulo: "Ángulos", detalle: "Tronco, cuello, brazos…" },
  { icono: Gauge, titulo: "REBA", detalle: "Tablas A, B y C" },
  { icono: ListChecks, titulo: "Controles", detalle: "NOM-036-1 y Jabil" },
  { icono: ClipboardCheck, titulo: "Especialista", detalle: "Valida y aprueba" },
]

const Nodo = forwardRef<HTMLDivElement, { activo: boolean; hecho: boolean; children: ReactNode }>(({ activo, hecho, children }, ref) => (
  <div ref={ref} className={cn("relative z-10 flex size-14 items-center justify-center rounded-full border-2 bg-sheet transition-colors duration-500",
    activo ? "border-ink text-ink" : hecho ? "border-ink bg-ink text-sheet" : "border-rule text-graphite")}>
    {children}
  </div>
))
Nodo.displayName = "Nodo"

/** Recorrido del agente mientras analiza: la única animación orquestada de la app. */
export function FlujoAgente({ trabajando }: { trabajando: boolean }) {
  const contenedor = useRef<HTMLDivElement>(null)
  const nodos = useMemo(() => PASOS.map(() => createRef<HTMLDivElement>()), [])
  const [paso, setPaso] = useState(0)

  useEffect(() => {
    if (!trabajando) return
    setPaso(0)
    // El backend procesa todo en una llamada; avanzamos al ritmo típico de cada etapa y nos detenemos antes del especialista.
    const tiempos = [500, 1600, 900, 600, 700]
    let total = 0
    const relojes = tiempos.map((ms, i) => {
      total += ms
      return window.setTimeout(() => setPaso(i + 1), total)
    })
    return () => relojes.forEach(window.clearTimeout)
  }, [trabajando])

  const pasoVisible = Math.min(paso, PASOS.length - 2)

  return (
    <div ref={contenedor} className="relative overflow-hidden rounded-[14px] border border-rule bg-sheet px-6 py-8">
      {trabajando && <BorderBeam size={120} duration={5} colorFrom="#13233b" colorTo="#8a99ad" borderWidth={1.5} />}
      <div className="relative grid grid-cols-6 gap-2">
        {PASOS.map(({ icono: Icono, titulo, detalle }, i) => (
          <div key={titulo} className="flex flex-col items-center text-center">
            <Nodo ref={nodos[i]} activo={trabajando && i === pasoVisible} hecho={trabajando && i < pasoVisible}>
              <Icono className="size-5" strokeWidth={1.75} />
            </Nodo>
            <p className="mt-3 text-[14px] font-semibold">{titulo}</p>
            <p className="hidden text-[12px] leading-snug text-graphite sm:block">{detalle}</p>
          </div>
        ))}
      </div>
      {PASOS.slice(0, -1).map((_, i) => (
        <AnimatedBeam key={i} containerRef={contenedor} fromRef={nodos[i]} toRef={nodos[i + 1]}
          pathColor="var(--rule)" pathOpacity={1} pathWidth={2} gradientStartColor="#13233b" gradientStopColor="#5b6776"
          duration={trabajando ? 1.6 : 4} delay={i * 0.25} curvature={i % 2 ? 18 : -18} />
      ))}
    </div>
  )
}
