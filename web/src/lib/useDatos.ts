import { useCallback, useEffect, useRef, useState } from "react"

/** Carga datos de la API local y permite reemplazarlos tras una acción (aprobar, corregir…). */
export function useDatos<T>(cargar: () => Promise<T>, claves: unknown[]) {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const vigente = useRef(0)

  const recargar = useCallback(async () => {
    const turno = ++vigente.current
    setCargando(true)
    try {
      const valor = await cargar()
      if (turno === vigente.current) {
        setDatos(valor)
        setError(null)
      }
    } catch (e) {
      if (turno === vigente.current) setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (turno === vigente.current) setCargando(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, claves)

  useEffect(() => {
    void recargar()
  }, [recargar])

  return { datos, setDatos, error, cargando, recargar }
}
