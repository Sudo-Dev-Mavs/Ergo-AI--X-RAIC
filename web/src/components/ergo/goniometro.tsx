import { motion, useReducedMotion, useSpring, useTransform } from "motion/react"
import { useEffect } from "react"

import { NumberTicker } from "@/components/magicui/number-ticker"
import { ZONAS, colorRiesgo } from "@/lib/dominio"
import { cn } from "@/lib/utils"

/**
 * Goniómetro REBA: la escala 1–15 dibujada como el transportador con el que se miden
 * ángulos en piso. La aguja sólida es el riesgo inicial; la hueca, el residual esperado.
 */
const MIN = 1
const MAX = 15
const INICIO = -110 // grados, en sentido horario desde las 12
const BARRIDO = 220

function angulo(valor: number) {
  return INICIO + ((Math.min(MAX, Math.max(MIN, valor)) - MIN) / (MAX - MIN)) * BARRIDO
}

function punto(cx: number, cy: number, r: number, grados: number) {
  const rad = (grados * Math.PI) / 180
  return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)] as const
}

function arco(cx: number, cy: number, r: number, desde: number, hasta: number) {
  const [x1, y1] = punto(cx, cy, r, desde)
  const [x2, y2] = punto(cx, cy, r, hasta)
  return `M ${x1} ${y1} A ${r} ${r} 0 ${hasta - desde > 180 ? 1 : 0} 1 ${x2} ${y2}`
}

interface GoniometroProps {
  inicial: number | null
  residual: number | null
  nivel: string | null
  nivelResidual: string | null
  tamano?: number
  className?: string
  compacto?: boolean
}

export function Goniometro({ inicial, residual, nivel, nivelResidual, tamano = 300, className, compacto = false }: GoniometroProps) {
  const reducir = useReducedMotion() ?? false
  const cx = 150
  const cy = 150
  const rZona = 118
  const rEscala = 104
  const largoAguja = 96
  const media = (desde: number) => angulo(desde - 0.5) + 0.6
  const fin = (hasta: number) => angulo(hasta + 0.5) - 0.6

  return (
    <div className={cn("relative select-none", className)} style={{ width: tamano, height: compacto ? tamano * 0.7 : tamano * 0.9 }}>
      <svg viewBox="0 0 300 210" className="w-full overflow-visible" style={{ height: tamano * 0.7 }} role="img"
        aria-label={`REBA inicial ${inicial ?? "pendiente"}${residual != null ? `, residual esperado ${residual}` : ""}`}>
        {ZONAS.map((zona) => (
          <path key={zona.nivel} d={arco(cx, cy, rZona, media(zona.desde), fin(zona.hasta))}
            stroke={zona.color} strokeWidth={compacto ? 10 : 12} fill="none"
            opacity={nivel && zona.nivel !== nivel && zona.nivel !== nivelResidual ? 0.28 : 1} />
        ))}
        {Array.from({ length: MAX * 2 - 1 }, (_, i) => MIN + i / 2).map((valor) => {
          const mayor = Number.isInteger(valor)
          const [x1, y1] = punto(cx, cy, rEscala, angulo(valor))
          const [x2, y2] = punto(cx, cy, rEscala - (mayor ? 9 : 4), angulo(valor))
          return <line key={valor} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--ink)" strokeWidth={mayor ? 1.4 : 0.8} opacity={mayor ? 0.85 : 0.45} />
        })}
        {!compacto && [1, 3, 7, 10, 15].map((valor) => {
          const [x, y] = punto(cx, cy, rEscala - 21, angulo(valor))
          return <text key={valor} x={x} y={y + 4} textAnchor="middle" className="t-num" fontSize="12" fill="var(--graphite)">{valor}</text>
        })}
        {residual != null && inicial != null && residual !== inicial && (
          <Aguja desde={angulo(inicial)} hasta={angulo(residual)} retraso={reducir ? 0 : 1.1} cx={cx} cy={cy} largo={largoAguja} cola={0}
            reducir={reducir} color={colorRiesgo(nivelResidual)} grosor={2} punteada />
        )}
        {inicial != null && (
          <Aguja desde={INICIO} hasta={angulo(inicial)} retraso={0} cx={cx} cy={cy} largo={largoAguja} cola={8}
            reducir={reducir} color="var(--ink)" grosor={3} punta={colorRiesgo(nivel)} />
        )}
        <circle cx={cx} cy={cy} r={7} fill="var(--ink)" />
        <circle cx={cx} cy={cy} r={2.5} fill="var(--sheet)" />
      </svg>
      {!compacto && (
        <div className="pointer-events-none absolute inset-x-0 flex flex-col items-center" style={{ top: tamano * 0.55 }}>
          <span className="t-num text-[64px] leading-none" style={{ color: colorRiesgo(nivel) }}>
            {inicial != null ? <NumberTicker value={inicial} startValue={1} className="text-inherit" style={{ color: "inherit" }} /> : "—"}
          </span>
          <span className="mt-1 text-sm font-semibold">{nivel ?? "Pendiente"}</span>
        </div>
      )}
    </div>
  )
}

/** Aguja que gira con resorte: se animan las coordenadas de la línea, no un transform SVG. */
function Aguja({ desde, hasta, retraso, cx, cy, largo, cola, reducir, color, grosor, punteada = false, punta }: {
  desde: number; hasta: number; retraso: number; cx: number; cy: number; largo: number; cola: number
  reducir: boolean; color: string; grosor: number; punteada?: boolean; punta?: string
}) {
  const giro = useSpring(reducir ? hasta : desde, { stiffness: 55, damping: 13 })
  const rad = (v: number) => (v * Math.PI) / 180
  const x1 = useTransform(giro, (v) => cx - cola * Math.sin(rad(v)))
  const y1 = useTransform(giro, (v) => cy + cola * Math.cos(rad(v)))
  const x2 = useTransform(giro, (v) => cx + largo * Math.sin(rad(v)))
  const y2 = useTransform(giro, (v) => cy - largo * Math.cos(rad(v)))
  useEffect(() => {
    const reloj = window.setTimeout(() => giro.set(hasta), retraso * 1000)
    return () => window.clearTimeout(reloj)
  }, [giro, hasta, retraso])
  return (
    <g>
      <motion.line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={grosor} strokeLinecap="round" strokeDasharray={punteada ? "5 4" : undefined} />
      <motion.circle cx={x2} cy={y2} r={punteada ? 5 : 4} fill={punteada ? "var(--sheet)" : punta ?? color} stroke={punteada ? color : "none"} strokeWidth={2} />
    </g>
  )
}
