import { ShieldAlert, ShieldCheck } from "lucide-react"

import { AnimatedList } from "@/components/magicui/animated-list"
import type { EstadoCaso } from "@/lib/api"
import { NOMBRE_ACCION, fechaCorta } from "@/lib/dominio"
import { cn } from "@/lib/utils"

const valorTexto = (valor: unknown) => (valor == null || valor === "" ? "vacío" : typeof valor === "number" ? `${valor}` : String(valor))

export function PanelBitacora({ estado }: { estado: EstadoCaso }) {
  const entradas = estado.validacion.bitacora
  const integra = estado.bitacora_integra
  const firmada = estado.bitacora_estado === "firmada"
  return (
    <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_300px]">
      <AnimatedList delay={70} className="items-stretch gap-2">
        {entradas.map((entrada) => {
          const agente = entrada.usuario.includes("agente")
          return (
            <article key={entrada.n} className={cn("grid grid-cols-[48px_1fr] gap-3 rounded-[10px] p-3.5", agente ? "trazo-lapiz" : "trazo-tinta")}>
              <span className="t-num pt-0.5 text-[18px] text-graphite">{entrada.n}</span>
              <div className="min-w-0">
                <p className="text-[15px]">
                  <span className="font-semibold">{entrada.usuario}</span>{" "}
                  <span className="text-ink-soft">{(NOMBRE_ACCION[entrada.accion] ?? entrada.accion).toLowerCase()}</span>
                  {entrada.rec_id && <span className="t-num ml-1.5 text-[14px]">{entrada.rec_id}</span>}
                </p>
                {Object.entries(entrada.cambios).length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-[13px] text-ink-soft">
                    {Object.entries(entrada.cambios).map(([campo, { antes, despues }]) => (
                      <li key={campo} className="break-words">
                        <span className="text-graphite">{campo.replaceAll("_", " ")}:</span> <s className="text-graphite">{valorTexto(antes)}</s> <span>{valorTexto(despues)}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {entrada.comentario && <p className="mt-1 text-[13px] text-graphite">{entrada.comentario}</p>}
                <p className="mt-1 text-[12px] text-graphite">{fechaCorta(entrada.fecha)}</p>
              </div>
            </article>
          )
        })}
      </AnimatedList>
      <aside className="xl:sticky xl:top-8 xl:self-start">
        <div className={cn("rounded-[12px] p-4", !integra ? "border-2 border-[var(--riesgo-muy-alto)] bg-sheet" : firmada ? "trazo-tinta" : "border-2 border-amber-400 bg-sheet")}>
          <div className="flex items-center gap-2">
            {integra ? <ShieldCheck className="size-5" strokeWidth={1.75} /> : <ShieldAlert className="size-5 text-[var(--riesgo-muy-alto)]" strokeWidth={1.75} />}
            <h3 className="t-title text-[17px]">{!integra ? "Bitácora alterada" : firmada ? "Bitácora íntegra y firmada" : "Bitácora íntegra, sin firma"}</h3>
          </div>
          <p className="mt-2 text-[14px] text-ink-soft">
            {!integra
              ? "Algún registro se modificó fuera de ErgoAI. No apruebes el informe hasta aclarar el cambio."
              : firmada
                ? `Los ${entradas.length} registros están encadenados con SHA-256 y firmados con la clave de esta instalación: editarlos o recalcular la cadena fuera de ErgoAI se detecta.`
                : "La cadena SHA-256 coincide, pero hay registros sin firma comprobable aquí (anteriores a la firma o de otro equipo): una edición que recalcule la cadena no se detectaría."}
          </p>
          {entradas.length > 0 && <p className="mt-3 break-all text-[12px] text-graphite">Último sello {entradas[entradas.length - 1].hash.slice(0, 16)}</p>}
        </div>
      </aside>
    </div>
  )
}
