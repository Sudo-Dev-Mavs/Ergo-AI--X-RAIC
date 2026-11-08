import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"

import { showPolishedToast } from "@/components/cult/halo-toast"

/* ---------- Rutas con hash: la app se sirve como archivo local, sin servidor de rutas ---------- */

export type Ruta = { nombre: "casos" } | { nombre: "nueva" } | { nombre: "caso"; id: string }

function leerRuta(): Ruta {
  const partes = window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean)
  if (partes[0] === "nueva") return { nombre: "nueva" }
  if (partes[0] === "caso" && partes[1]) return { nombre: "caso", id: decodeURIComponent(partes[1]) }
  return { nombre: "casos" }
}

export function useRuta(): Ruta {
  const [ruta, setRuta] = useState(leerRuta)
  useEffect(() => {
    const cambiar = () => {
      setRuta(leerRuta())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener("hashchange", cambiar)
    return () => window.removeEventListener("hashchange", cambiar)
  }, [])
  return ruta
}

export const ir = (ruta: Ruta) => {
  window.location.hash = ruta.nombre === "caso" ? `#/caso/${encodeURIComponent(ruta.id)}` : ruta.nombre === "nueva" ? "#/nueva" : "#/"
}

/* ---------- Especialista: toda decisión queda firmada con su nombre ---------- */

const CLAVE = "ergoai.especialista"

function leerNombre(): string {
  try {
    return window.localStorage.getItem(CLAVE) ?? ""
  } catch {
    return ""
  }
}

interface ContextoEspecialista {
  nombre: string
  setNombre: (nombre: string) => void
  pedirFirma: () => string | null
}

const Contexto = createContext<ContextoEspecialista | null>(null)

export function ProveedorEspecialista({ children }: { children: ReactNode }) {
  const [nombre, setNombreEstado] = useState(leerNombre)
  const setNombre = useCallback((valor: string) => {
    setNombreEstado(valor)
    try {
      window.localStorage.setItem(CLAVE, valor)
    } catch {
      /* almacenamiento no disponible: el nombre vive solo en esta sesión */
    }
  }, [])
  const pedirFirma = useCallback(() => {
    if (nombre.trim()) return nombre.trim()
    avisar({ titulo: "Falta tu nombre", detalle: "Escríbelo en «Firmas como» para registrar decisiones en la bitácora.", tipo: "error" })
    document.getElementById("firma-especialista")?.focus()
    return null
  }, [nombre])
  return <Contexto.Provider value={{ nombre, setNombre, pedirFirma }}>{children}</Contexto.Provider>
}

export function useEspecialista() {
  const valor = useContext(Contexto)
  if (!valor) throw new Error("useEspecialista fuera de ProveedorEspecialista")
  return valor
}

/* ---------- Avisos ---------- */

export function avisar({ titulo, detalle, tipo = "ok" }: { titulo: string; detalle?: string; tipo?: "ok" | "error" }) {
  showPolishedToast({ title: titulo, description: detalle, rimVariant: tipo === "error" ? "destructive" : "default", duration: tipo === "error" ? 7000 : 3500, politeness: tipo === "error" ? "alert" : "status" })
}
