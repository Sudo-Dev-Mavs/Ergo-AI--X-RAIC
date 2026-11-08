import { ZONAS, colorRiesgo } from "@/lib/dominio"
import { cn } from "@/lib/utils"

/** Regla REBA 1–15 con el punto inicial y el residual esperado, para leer el cambio de un vistazo. */
export function ReglaRiesgo({ inicial, residual, nivel, nivelResidual, className }: {
  inicial: number | null
  residual: number | null
  nivel: string | null
  nivelResidual: string | null
  className?: string
}) {
  const pos = (valor: number) => `${((valor - 1) / 14) * 100}%`
  return (
    <div className={cn("relative h-6 w-full", className)} aria-label={`REBA ${inicial ?? "pendiente"} a ${residual ?? "pendiente"}`}>
      <div className="absolute inset-x-0 top-1/2 flex h-1.5 -translate-y-1/2 gap-[2px]">
        {ZONAS.map((zona) => (
          <div key={zona.nivel} className="h-full rounded-[1px]" style={{
            flexGrow: zona.hasta - zona.desde + 1, background: zona.color,
            opacity: zona.nivel === nivel || zona.nivel === nivelResidual ? 1 : 0.22,
          }} />
        ))}
      </div>
      {inicial != null && residual != null && residual < inicial && (
        <div className="absolute top-1/2 h-px -translate-y-1/2 bg-ink" style={{ left: pos(residual), right: `calc(100% - ${pos(inicial)})` }} />
      )}
      {residual != null && (
        <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-sheet"
          style={{ left: pos(residual), borderColor: colorRiesgo(nivelResidual) }} title={`Residual ${residual}`} />
      )}
      {inicial != null && (
        <span className="absolute top-1/2 h-5 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink"
          style={{ left: pos(inicial) }} title={`Inicial ${inicial}`} />
      )}
    </div>
  )
}
