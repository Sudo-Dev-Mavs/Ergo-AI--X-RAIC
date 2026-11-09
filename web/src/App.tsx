import { ClipboardCheck, FilePlus2, House, LockKeyhole, PenLine, Shield } from "lucide-react"

import { PolishedToaster } from "@/components/cult/halo-toast"
import { Goniometro } from "@/components/ergo/goniometro"
import { PanelOpciones } from "@/components/ergo/PanelOpciones"
import { ProveedorEspecialista, ir, useEspecialista, useRuta } from "@/lib/app"
import { ProveedorPreferencias } from "@/lib/preferencias"
import { cn } from "@/lib/utils"
import { CasoPage } from "@/pages/caso"
import { CasosPage } from "@/pages/casos"
import { NuevaPage } from "@/pages/nueva"
import { ValidacionPage } from "@/pages/validacion"

export function App() {
  return (
    <ProveedorPreferencias>
      <ProveedorEspecialista>
        <Marco />
        <PolishedToaster position="bottom-right" />
      </ProveedorEspecialista>
    </ProveedorPreferencias>
  )
}

function Marco() {
  const ruta = useRuta()
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[248px_1fr]">
      <Riel actual={ruta.nombre} />
      <main className="min-w-0 overflow-x-clip px-4 pt-6 pb-24 sm:px-8 lg:px-12 lg:pt-10">
        {ruta.nombre === "casos" && <CasosPage />}
        {ruta.nombre === "nueva" && <NuevaPage />}
        {ruta.nombre === "validacion" && <ValidacionPage casoIdInicial={ruta.id} />}
        {ruta.nombre === "caso" && <CasoPage key={ruta.id} id={ruta.id} />}
      </main>
    </div>
  )
}

function Riel({ actual }: { actual: string }) {
  const { nombre, setNombre } = useEspecialista()
  const enlaces = [
    { ruta: "casos" as const, texto: "Inicio", icono: House, activo: actual === "casos" || actual === "caso" },
    { ruta: "validacion" as const, texto: "Validación", icono: ClipboardCheck, activo: actual === "validacion" },
    { ruta: "nueva" as const, texto: "Nueva evaluación", icono: FilePlus2, activo: actual === "nueva" },
  ]
  return (
    <aside className="sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule/80 bg-sheet/80 px-4 py-3 backdrop-blur-md lg:h-dvh lg:flex-col lg:flex-nowrap lg:overflow-y-auto lg:items-stretch lg:gap-7 lg:border-r lg:border-b-0 lg:bg-transparent lg:px-0 lg:py-0 lg:backdrop-blur-none">
      <div className="marca-jabil flex w-full flex-wrap items-center gap-3 rounded-xl px-4 py-3 lg:min-h-dvh lg:flex-col lg:flex-nowrap lg:items-stretch lg:gap-8 lg:rounded-none lg:px-5 lg:py-8">
        <a href="#/" className="flex items-center gap-2.5" aria-label="ErgoAI, ir al inicio">
          <span className="rounded-lg bg-white/10 p-1">
            <Goniometro inicial={11} residual={4} nivel="Muy alto" nivelResidual="Medio" tamano={40} compacto className="-mb-1" />
          </span>
          <div>
            <span className="t-display block text-[22px] text-white">ErgoAI</span>
            <span className="flex items-center gap-1 text-[11px] tracking-[0.14em] text-jabil-cyan-soft uppercase">
              <Shield className="size-3" strokeWidth={2} /> Jabil · NOM-036
            </span>
          </div>
        </a>

        <nav className="flex gap-1 lg:flex-col" aria-label="Principal">
          {enlaces.map(({ ruta, texto, icono: Icono, activo }) => (
            <button
              key={ruta}
              onClick={() => ir({ nombre: ruta })}
              aria-current={activo ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-[14px] font-medium transition-colors",
                activo ? "bg-white text-jabil shadow-sm" : "text-white/85 hover:bg-white/10 hover:text-white",
              )}
            >
              <Icono className="size-4" strokeWidth={1.75} />
              <span className={cn(ruta === "nueva" && "hidden sm:inline")}>{texto}</span>
            </button>
          ))}
        </nav>

        <div className="hidden w-full lg:block">
          <PanelOpciones />
        </div>

        <div className="w-full sm:ml-auto sm:w-auto lg:mt-auto lg:ml-0 lg:w-full">
          <label htmlFor="firma-especialista" className="mb-1.5 hidden text-[12px] text-white/70 lg:block">
            Firmas como
          </label>
          <div className={cn(
            "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 focus-within:border-jabil-cyan focus-within:bg-white/15",
            nombre.trim() ? "border-white/25 bg-white/10" : "border-amber-300/80 bg-amber-400/20",
          )}>
            <PenLine className={cn("size-3.5 shrink-0", nombre.trim() ? "text-jabil-cyan-soft" : "text-amber-200")} strokeWidth={1.75} />
            <input
              id="firma-especialista"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Nombre del especialista"
              className="w-full min-w-0 bg-transparent text-[14px] text-white outline-none placeholder:text-white/55 sm:w-40 lg:w-full"
              autoComplete="name"
              aria-invalid={!nombre.trim()}
            />
          </div>
          {!nombre.trim() ? (
            <p className="mt-2 hidden text-[12px] leading-snug text-amber-100 lg:block">
              Escribe tu nombre para firmar aprobaciones (trazabilidad).
            </p>
          ) : (
            <p className="mt-2 hidden text-[12px] leading-snug text-jabil-cyan-soft lg:block">
              ✓ Firmando como {nombre.trim()}
            </p>
          )}
          <p className="mt-4 hidden items-start gap-1.5 border-t border-white/15 pt-3 text-[12px] leading-snug text-white/65 lg:flex">
            <LockKeyhole className="mt-px size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
            Las fotos y resultados se quedan en este equipo.
          </p>
          <div className="mt-3 lg:hidden">
            <PanelOpciones />
          </div>
        </div>
      </div>
    </aside>
  )
}
