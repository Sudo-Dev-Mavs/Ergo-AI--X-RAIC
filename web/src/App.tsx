import { FilePlus2, House, PenLine } from "lucide-react"

import { PolishedToaster } from "@/components/cult/halo-toast"
import { Goniometro } from "@/components/ergo/goniometro"
import { ProveedorEspecialista, ir, useEspecialista, useRuta } from "@/lib/app"
import { cn } from "@/lib/utils"
import { CasoPage } from "@/pages/caso"
import { CasosPage } from "@/pages/casos"
import { NuevaPage } from "@/pages/nueva"

export function App() {
  return (
    <ProveedorEspecialista>
      <Marco />
      <PolishedToaster position="bottom-right" />
    </ProveedorEspecialista>
  )
}

function Marco() {
  const ruta = useRuta()
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_1fr]">
      <Riel actual={ruta.nombre} />
      <main className="min-w-0 overflow-x-clip px-4 pt-6 pb-24 sm:px-8 lg:px-12 lg:pt-10">
        {ruta.nombre === "casos" && <CasosPage />}
        {ruta.nombre === "nueva" && <NuevaPage />}
        {ruta.nombre === "caso" && <CasoPage key={ruta.id} id={ruta.id} />}
      </main>
    </div>
  )
}

function Riel({ actual }: { actual: string }) {
  const { nombre, setNombre } = useEspecialista()
  const enlaces = [
    { ruta: "casos" as const, texto: "Inicio", icono: House, activo: actual === "casos" || actual === "caso" },
    { ruta: "nueva" as const, texto: "Nueva evaluación", icono: FilePlus2, activo: actual === "nueva" },
  ]
  return (
    <aside className="sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule bg-vellum/90 px-4 py-3 backdrop-blur lg:h-dvh lg:flex-col lg:flex-nowrap lg:items-stretch lg:gap-8 lg:border-r lg:border-b-0 lg:px-5 lg:py-8">
      <a href="#/" className="flex items-center gap-2.5" aria-label="ErgoAI, ir al inicio">
        <Goniometro inicial={11} residual={null} nivel="Muy alto" nivelResidual={null} tamano={38} compacto className="-mb-2" />
        <span className="t-display text-[22px]">ErgoAI</span>
      </a>
      <nav className="flex gap-1 lg:flex-col">
        {enlaces.map(({ ruta, texto, icono: Icono, activo }) => (
          <button key={ruta} onClick={() => ir({ nombre: ruta })} aria-current={activo ? "page" : undefined}
            className={cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] font-medium transition-colors",
              activo ? "bg-ink text-sheet" : "text-ink-soft hover:bg-rule-soft")}>
            <Icono className="size-4" strokeWidth={1.75} />
            <span className={cn(ruta === "nueva" && "hidden sm:inline")}>{texto}</span>
          </button>
        ))}
      </nav>
      <div className="w-full sm:ml-auto sm:w-auto lg:mt-auto lg:ml-0 lg:w-full">
        <label htmlFor="firma-especialista" className="mb-1 hidden text-[13px] text-graphite lg:block">Firmas como</label>
        <div className="flex items-center gap-2 rounded-lg border border-dashed border-graphite/60 bg-sheet/70 px-2.5 py-1.5 focus-within:border-solid focus-within:border-ink">
          <PenLine className="size-3.5 shrink-0 text-graphite" strokeWidth={1.75} />
          <input id="firma-especialista" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre del especialista"
            className="w-full min-w-0 bg-transparent text-[14px] outline-none placeholder:text-graphite/70 sm:w-40 lg:w-full" autoComplete="name" />
        </div>
        <p className="mt-3 hidden text-[12px] leading-snug text-graphite lg:block">
          Las fotos y resultados se quedan en este equipo.
        </p>
      </div>
    </aside>
  )
}
