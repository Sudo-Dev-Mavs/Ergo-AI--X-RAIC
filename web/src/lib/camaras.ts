import { useCallback, useEffect, useRef, useState } from "react"

/** Cámaras del equipo vía la API del navegador: nombres reales, vista previa y captura de fotogramas. */

export interface Camara {
  deviceId: string
  nombre: string
}

export type EstadoPermiso = "pendiente" | "concedido" | "denegado" | "sin-soporte"

const soportado = () => typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia

export function useCamaras() {
  const [camaras, setCamaras] = useState<Camara[]>([])
  const [permiso, setPermiso] = useState<EstadoPermiso>(soportado() ? "pendiente" : "sin-soporte")
  const [error, setError] = useState<string | null>(null)
  const flujos = useRef(new Map<string, Promise<MediaStream>>())
  const lectores = useRef(new Map<string, HTMLVideoElement>())

  const listar = useCallback(async () => {
    if (!soportado()) return []
    const dispositivos = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput" && d.deviceId)
    const lista = dispositivos.map((d, i) => ({ deviceId: d.deviceId, nombre: d.label || `Cámara ${i + 1}` }))
    setCamaras(lista)
    if (dispositivos.some((d) => d.label)) setPermiso("concedido")
    return lista
  }, [])

  const detectar = useCallback(async () => {
    if (!soportado()) {
      setPermiso("sin-soporte")
      return
    }
    setError(null)
    try {
      const prueba = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      prueba.getTracks().forEach((t) => t.stop())
      setPermiso("concedido")
      const lista = await listar()
      if (!lista.length) setError("No se encontraron cámaras conectadas.")
    } catch (e) {
      const nombre = e instanceof DOMException ? e.name : ""
      if (nombre === "NotAllowedError" || nombre === "SecurityError") {
        setPermiso("denegado")
        setError("El acceso a las cámaras está bloqueado. Permítelo en el candado de la barra de la ventana y vuelve a detectar.")
      } else if (nombre === "NotFoundError" || nombre === "OverconstrainedError") {
        setCamaras([])
        setError("No se encontraron cámaras conectadas.")
      } else if (nombre === "NotReadableError") {
        setError("Una cámara está ocupada por otra aplicación. Ciérrala y vuelve a detectar.")
      } else {
        setError(e instanceof Error ? e.message : String(e))
      }
    }
  }, [listar])

  useEffect(() => {
    if (!soportado()) return
    void listar()
    navigator.permissions?.query({ name: "camera" as PermissionName }).then((estado) => {
      if (estado.state === "granted") void listar()
      if (estado.state === "denied") setPermiso("denegado")
    }).catch(() => undefined)
    const cambio = () => void listar()
    navigator.mediaDevices.addEventListener("devicechange", cambio)
    return () => navigator.mediaDevices.removeEventListener("devicechange", cambio)
  }, [listar])

  /** Abre (o reutiliza) el flujo de una cámara; varias vistas pueden compartir la misma cámara. */
  const abrir = useCallback((deviceId: string) => {
    const existente = flujos.current.get(deviceId)
    if (existente) return existente
    const promesa = navigator.mediaDevices
      .getUserMedia({ audio: false, video: { deviceId: { exact: deviceId }, width: { ideal: 1920 }, height: { ideal: 1080 } } })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "OverconstrainedError") {
          return navigator.mediaDevices.getUserMedia({ audio: false, video: { deviceId: { exact: deviceId } } })
        }
        throw e
      })
    promesa.catch(() => flujos.current.delete(deviceId))
    flujos.current.set(deviceId, promesa)
    return promesa
  }, [])

  const soltarLector = useCallback((deviceId: string) => {
    const lector = lectores.current.get(deviceId)
    lectores.current.delete(deviceId)
    if (lector) {
      lector.pause()
      lector.srcObject = null
      lector.remove()
    }
  }, [])

  const cerrar = useCallback((deviceId: string) => {
    soltarLector(deviceId)
    const promesa = flujos.current.get(deviceId)
    flujos.current.delete(deviceId)
    void promesa?.then((flujo) => flujo.getTracks().forEach((t) => t.stop())).catch(() => undefined)
  }, [soltarLector])

  /** Fotograma actual de una cámara como JPEG, leído de un video oculto que siempre está reproduciendo. */
  const capturar = useCallback(async (deviceId: string) => {
    const flujo = await abrir(deviceId)
    let lector = lectores.current.get(deviceId)
    if (!lector || lector.srcObject !== flujo) {
      lector = document.createElement("video")
      lector.muted = true
      lector.playsInline = true
      lector.setAttribute("aria-hidden", "true")
      lector.style.cssText = "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none"
      lector.srcObject = flujo
      document.body.appendChild(lector)
      lectores.current.set(deviceId, lector)
      void lector.play().catch(() => undefined)
    }
    await esperarCuadro(lector)
    return codificar(lector)
  }, [abrir])

  useEffect(() => {
    const abiertos = flujos.current
    const videos = lectores.current
    return () => {
      for (const video of videos.values()) {
        video.pause()
        video.srcObject = null
        video.remove()
      }
      videos.clear()
      for (const id of [...abiertos.keys()]) {
        void abiertos.get(id)?.then((f) => f.getTracks().forEach((t) => t.stop())).catch(() => undefined)
      }
      abiertos.clear()
    }
  }, [])

  return { camaras, permiso, error, detectar, listar, abrir, cerrar, capturar }
}

function esperarCuadro(video: HTMLVideoElement, limiteMs = 4000): Promise<void> {
  if (video.readyState >= 2 && video.videoWidth > 0) return Promise.resolve()
  return new Promise((resolver, rechazar) => {
    const listo = () => {
      if (video.videoWidth > 0) {
        limpiar()
        resolver()
      }
    }
    const reloj = window.setTimeout(() => {
      limpiar()
      rechazar(new Error("La cámara no entregó imagen a tiempo."))
    }, limiteMs)
    const limpiar = () => {
      window.clearTimeout(reloj)
      video.removeEventListener("loadeddata", listo)
      video.removeEventListener("playing", listo)
    }
    video.addEventListener("loadeddata", listo)
    video.addEventListener("playing", listo)
  })
}

function codificar(video: HTMLVideoElement): Promise<Blob> {
  const lienzo = document.createElement("canvas")
  lienzo.width = video.videoWidth
  lienzo.height = video.videoHeight
  lienzo.getContext("2d")!.drawImage(video, 0, 0)
  return new Promise((resolver, rechazar) =>
    lienzo.toBlob((blob) => (blob ? resolver(blob) : rechazar(new Error("No se pudo codificar la captura."))), "image/jpeg", 0.92),
  )
}

/** Rechaza si la promesa no termina a tiempo, para que una cámara colgada no detenga las tomas. */
export function conLimite<T>(promesa: Promise<T>, ms: number, mensaje: string): Promise<T> {
  return new Promise((resolver, rechazar) => {
    const reloj = window.setTimeout(() => rechazar(new Error(mensaje)), ms)
    promesa.then((v) => { window.clearTimeout(reloj); resolver(v) }, (e) => { window.clearTimeout(reloj); rechazar(e) })
  })
}
