import { useId, useState, type ReactNode } from "react"

import { cn } from "@/lib/utils"

/** Glosario corto para términos técnicos de ErgoAI (lenguaje común). */
export const GLOSARIO = {
  reba: "Método REBA: sistema internacional que mide la carga postural del cuerpo (del 1 al 15). Entre más alto el número, mayor riesgo de lesión física.",
  residual: "Riesgo restante: es el nivel de riesgo que le quedará al operador después de aplicar las mejoras aprobadas en la estación.",
  nom036: "Norma oficial (STPS): reglamento mexicano obligatorio para prevenir lesiones por manejo de cargas y sobreesfuerzo en el trabajo.",
  grupoAB: "Zonas del cuerpo: Grupo A analiza cuello, tronco y piernas. Grupo B analiza brazos, antebrazos y muñecas.",
  inicial: "REBA medido hoy con la postura observada en la foto, antes de aplicar mejoras.",
} as const

export type ClaveGlosario = keyof typeof GLOSARIO

/**
 * Ícono ? / i con explicación al hover o foco (teclado).
 * Sin dependencias extra: CSS + estado local.
 */
export function InfoTooltip({
  texto,
  clave,
  label = "Más información",
  className,
}: {
  texto?: ReactNode
  clave?: ClaveGlosario
  label?: string
  className?: string
}) {
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const contenido = texto ?? (clave ? GLOSARIO[clave] : null)
  if (!contenido) return null

  return (
    <span
      className={cn("relative inline-flex align-middle", className)}
      onMouseEnter={() => setAbierto(true)}
      onMouseLeave={() => setAbierto(false)}
    >
      <button
        type="button"
        className={cn(
          "inline-flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold leading-none transition-colors",
          "bg-slate-200 text-slate-600 hover:bg-jabil-cyan hover:text-white",
          "focus-visible:bg-jabil-cyan focus-visible:text-white",
          abierto && "bg-jabil-cyan text-white",
        )}
        aria-label={label}
        aria-describedby={abierto ? id : undefined}
        onFocus={() => setAbierto(true)}
        onBlur={() => setAbierto(false)}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setAbierto((v) => !v)
        }}
      >
        ?
      </button>
      {abierto && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-[calc(100%+8px)] left-1/2 z-50 w-[min(16rem,70vw)] -translate-x-1/2 rounded-lg bg-slate-900 px-2.5 py-2 text-left text-[12px] leading-snug font-normal text-white shadow-xl"
        >
          {contenido}
          <span aria-hidden className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-900" />
        </span>
      )}
    </span>
  )
}

/** Título + tooltip en línea. */
export function TituloConAyuda({
  children,
  clave,
  texto,
  className,
}: {
  children: ReactNode
  clave?: ClaveGlosario
  texto?: ReactNode
  className?: string
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      {children}
      <InfoTooltip clave={clave} texto={texto} />
    </span>
  )
}

/** Humaniza referencias técnicas en “¿Por qué se sugiere?”. */
export function humanizarReferencia(ref: string): string {
  const r = ref.trim()
  if (/reba|hignett|mcatamney/i.test(r)) return "Basado en la medición de postura (REBA)"
  if (/nom-?036|stps/i.test(r)) return "Requisito legal de ergonomía (NOM-036)"
  if (/jabil/i.test(r)) return "Criterio interno de ergonomía Jabil"
  return r
}
