import { Check } from "lucide-react"
import { motion } from "motion/react"

import { cn } from "@/lib/utils"

export interface Paso {
  titulo: string
  resumen: string
  listo: boolean
}

/** Indicador de los tres pasos de la evaluación; cada paso es un botón para ir y volver libremente. */
export function Pasos({ pasos, actual, onIr }: { pasos: Paso[]; actual: number; onIr: (indice: number) => void }) {
  return (
    <nav aria-label="Pasos de la evaluación">
      <ol className="grid grid-cols-3 border-y border-ink">
        {pasos.map((paso, i) => {
          const activo = i === actual
          return (
            <li key={paso.titulo} className={cn("relative min-w-0", i > 0 && "border-l border-rule")}>
              <button type="button" onClick={() => onIr(i)} aria-current={activo ? "step" : undefined}
                className={cn("flex w-full items-start gap-3 px-3 py-4 text-left transition-colors sm:px-5", activo ? "bg-sheet" : "hover:bg-rule-soft/60")}>
                <span className={cn("t-num flex size-8 shrink-0 items-center justify-center rounded-full border-2 text-[16px]",
                  activo ? "border-ink bg-ink text-sheet" : paso.listo ? "border-ink text-ink" : "border-rule text-graphite")}>
                  {paso.listo && !activo ? <Check className="size-4" strokeWidth={2.5} /> : i + 1}
                </span>
                <span className="min-w-0">
                  <span className={cn("t-title block text-[16px] sm:text-[18px]", !activo && "text-ink-soft")}>{paso.titulo}</span>
                  <span className="hidden truncate text-[13px] text-graphite sm:block">{paso.resumen}</span>
                </span>
              </button>
              {activo && <motion.span layoutId="paso-activo" className="absolute inset-x-0 -bottom-px h-[3px] bg-ink" transition={{ type: "spring", bounce: 0.15, duration: 0.45 }} />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
