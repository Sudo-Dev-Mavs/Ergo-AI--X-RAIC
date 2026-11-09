import { useCallback, useEffect, useState } from "react"

import { ValidationDashboard } from "@/components/ergo/ValidationDashboard"
import { api, type EstadoCaso } from "@/lib/api"
import { avisar, ir, useEspecialista } from "@/lib/app"
import { usePreferencias } from "@/lib/preferencias"
import { useDatos } from "@/lib/useDatos"

const MENSAJE: Record<string, string> = {
  aprobar: "Recomendación aprobada",
  rechazar: "Recomendación rechazada",
  reabrir: "Recomendación devuelta a propuesta",
  editar: "Cambios guardados",
  agregar: "Recomendación agregada",
  aprobar_informe: "Informe aprobado · acción de piso generada",
  ajustar_residual: "Residual proyectado ajustado",
  limpiar_residual: "Residual del agente restaurado",
}

/** Pantalla dedicada al ingeniero de seguridad (HITL + residual). */
export function ValidacionPage({ casoIdInicial }: { casoIdInicial?: string }) {
  const { datos: casos, recargar } = useDatos(api.casos, [])
  const { pedirFirma } = useEspecialista()
  const { preferencias } = usePreferencias()
  const [activoId, setActivoId] = useState<string | undefined>(casoIdInicial)
  const [estado, setEstado] = useState<EstadoCaso | null>(null)
  const [cargandoCaso, setCargandoCaso] = useState(false)
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    if (casoIdInicial) setActivoId(casoIdInicial)
  }, [casoIdInicial])

  useEffect(() => {
    if (!activoId) {
      setEstado(null)
      return
    }
    let cancelado = false
    setCargandoCaso(true)
    void api.caso(activoId)
      .then((datos) => { if (!cancelado) setEstado(datos) })
      .catch((e) => {
        if (!cancelado) {
          setEstado(null)
          avisar({ titulo: "No se abrió el caso", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
        }
      })
      .finally(() => { if (!cancelado) setCargandoCaso(false) })
    return () => { cancelado = true }
  }, [activoId])

  async function accion(nombre: string, recId?: string, valores?: Record<string, string>, comentario?: string) {
    if (!activoId) return false
    const usuario = pedirFirma()
    if (!usuario) return false
    if (preferencias.confirmarAcciones && nombre === "aprobar_informe") {
      if (!window.confirm("¿Aprobar el informe y generar las acciones de piso?")) return false
    }
    setOcupado(true)
    try {
      const nuevo = await api.validar(activoId, { usuario, accion: nombre, rec_id: recId, valores, comentario })
      setEstado(nuevo)
      void recargar()
      avisar({ titulo: MENSAJE[nombre] ?? "Cambio registrado", detalle: "Quedó firmado en la bitácora." })
      if (nombre === "aprobar_informe") ir({ nombre: "caso", id: activoId })
      return true
    } catch (e) {
      avisar({ titulo: "No se registró el cambio", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
      return false
    } finally {
      setOcupado(false)
    }
  }

  async function ajustarResidual(puntaje: number, motivo: string) {
    if (!activoId) return false
    const usuario = pedirFirma()
    if (!usuario) return false
    setOcupado(true)
    try {
      setEstado(await api.ajustarResidual(activoId, usuario, puntaje, motivo))
      void recargar()
      avisar({ titulo: MENSAJE.ajustar_residual, detalle: `Residual proyectado = ${puntaje}` })
      return true
    } catch (e) {
      avisar({ titulo: "No se ajustó el residual", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
      return false
    } finally {
      setOcupado(false)
    }
  }

  async function limpiarResidual() {
    if (!activoId) return false
    const usuario = pedirFirma()
    if (!usuario) return false
    setOcupado(true)
    try {
      setEstado(await api.limpiarResidual(activoId, usuario))
      void recargar()
      avisar({ titulo: MENSAJE.limpiar_residual })
      return true
    } catch (e) {
      avisar({ titulo: "No se restauró el residual", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
      return false
    } finally {
      setOcupado(false)
    }
  }

  const seleccionar = useCallback((id: string) => {
    setActivoId(id)
    window.location.hash = `#/validacion/${encodeURIComponent(id)}`
  }, [])

  return (
    <ValidationDashboard
      casos={casos ?? []}
      casoActivo={estado}
      cargandoCaso={cargandoCaso}
      ocupado={ocupado}
      onSeleccionar={seleccionar}
      onAccion={accion}
      onAjustarResidual={ajustarResidual}
      onLimpiarResidual={limpiarResidual}
    />
  )
}
