import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

const CLAVE = "ergoai.preferencias.v1"

export interface Preferencias {
  /** Controles más compactos en listas y formularios */
  densidad: "comoda" | "compacta"
  /** Pedir confirmación antes de aprobar informe / rechazar */
  confirmarAcciones: boolean
  /** Mostrar atajos en el visor de fotos */
  mostrarAyudas: boolean
  /** Al abrir un caso, empezar en foto anotada o original */
  fotoInicial: "anotada" | "original"
}

const DEFECTO: Preferencias = {
  densidad: "comoda",
  confirmarAcciones: true,
  mostrarAyudas: true,
  fotoInicial: "anotada",
}

interface Ctx {
  preferencias: Preferencias
  setPreferencias: (parcial: Partial<Preferencias>) => void
  resetPreferencias: () => void
}

const Contexto = createContext<Ctx | null>(null)

function leer(): Preferencias {
  try {
    const crudo = window.localStorage.getItem(CLAVE)
    if (!crudo) return DEFECTO
    return { ...DEFECTO, ...(JSON.parse(crudo) as Partial<Preferencias>) }
  } catch {
    return DEFECTO
  }
}

export function ProveedorPreferencias({ children }: { children: ReactNode }) {
  const [preferencias, setEstado] = useState(leer)
  useEffect(() => {
    try {
      window.localStorage.setItem(CLAVE, JSON.stringify(preferencias))
    } catch {
      /* ignore */
    }
    document.documentElement.dataset.densidad = preferencias.densidad
  }, [preferencias])

  const setPreferencias = useCallback((parcial: Partial<Preferencias>) => {
    setEstado((prev) => ({ ...prev, ...parcial }))
  }, [])
  const resetPreferencias = useCallback(() => setEstado(DEFECTO), [])

  const valor = useMemo(() => ({ preferencias, setPreferencias, resetPreferencias }), [preferencias, setPreferencias, resetPreferencias])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function usePreferencias() {
  const ctx = useContext(Contexto)
  if (!ctx) throw new Error("usePreferencias fuera de ProveedorPreferencias")
  return ctx
}
