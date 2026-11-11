import { ArrowLeft, ArrowRight, Camera, RefreshCw, Sparkles, Wand2 } from "lucide-react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { HaloSegmented } from "@/components/cult/halo-segmented"
import { HaloSwitch } from "@/components/cult/halo-switch"
import { FlujoAgente } from "@/components/ergo/flujo-agente"
import { Pasos } from "@/components/ergo/pasos"
import { PanelTomas, hora } from "@/components/ergo/tomas"
import { VistaFuente, type Fuente } from "@/components/ergo/vista-fuente"
import { ShimmerButton } from "@/components/magicui/shimmer-button"
import { ErrorApi, api, type TipoTarea, type Toma, type Vista } from "@/lib/api"
import { avisar, ir, useEspecialista } from "@/lib/app"
import { conLimite, useCamaras, type Camara } from "@/lib/camaras"
import { TAREAS, etiquetaTarea } from "@/lib/dominio"
import { filtrarImagenesErgo, imagenDesdeClipboard } from "@/lib/imagenes"
import { cn } from "@/lib/utils"

type Lado = "izquierdo" | "derecho"
const AJUSTES = [
  { clave: "estatica", texto: "Postura estática más de 1 minuto" },
  { clave: "repetitiva", texto: "Repite la acción más de 4 veces por minuto" },
  { clave: "inestable", texto: "Cambios bruscos o base inestable" },
  { clave: "fuerza_brusca", texto: "Aplica fuerza de golpe" },
] as const
const AJUSTES_LADO = [
  { clave: "hombro_elevado", texto: "Hombro elevado" },
  { clave: "brazo_apoyado", texto: "Brazo apoyado" },
  { clave: "muneca_desviada_o_torcida", texto: "Muñeca desviada o torcida" },
] as const

const VISTAS: { vista: Vista; titulo: string; ayuda: string }[] = [
  { vista: "costado", titulo: "Costado", ayuda: "Tronco, cuello, brazos, codos, muñecas y rodillas." },
  { vista: "frente", titulo: "Frente", ayuda: "Inclinación lateral, abducción y apoyo de piernas." },
  { vista: "aerea", titulo: "Aérea", ayuda: "Torsión de tronco entre hombros y caderas." },
]
const TITULOS = ["Fotografías", "Tarea", "Limitaciones de la evidencia fotográfica"]
const CLAVE_FUENTES = "ergoai.camaras.asignacion"
const CLAVE_INTERVALO = "ergoai.camaras.intervalo"
const CLAVE_BORRADOR = "ergoai.borrador"

function leer<T>(almacen: "local" | "sesion", clave: string, defecto: T): T {
  try {
    const crudo = (almacen === "local" ? window.localStorage : window.sessionStorage).getItem(clave)
    return crudo ? (JSON.parse(crudo) as T) : defecto
  } catch {
    return defecto
  }
}

function guardar(almacen: "local" | "sesion", clave: string, valor: unknown) {
  try {
    const destino = almacen === "local" ? window.localStorage : window.sessionStorage
    if (valor === null) destino.removeItem(clave)
    else destino.setItem(clave, JSON.stringify(valor))
  } catch {
    /* almacenamiento no disponible: el valor vive solo en esta pantalla */
  }
}

function sugerirId() {
  const hoy = new Date()
  const p = (n: number) => String(n).padStart(2, "0")
  return `caso-${hoy.getFullYear()}${p(hoy.getMonth() + 1)}${p(hoy.getDate())}-${p(hoy.getHours())}${p(hoy.getMinutes())}`
}

export function NuevaPage() {
  const { nombre } = useEspecialista()
  const camaras = useCamaras()
  const reducir = useReducedMotion() ?? false

  // Paso actual y dirección de la transición
  const [paso, setPaso] = useState(0)
  const [direccion, setDireccion] = useState(1)
  const irPaso = (destino: number) => {
    setDireccion(destino >= paso ? 1 : -1)
    setPaso(Math.max(0, Math.min(2, destino)))
    window.scrollTo({ top: 0, behavior: reducir ? "auto" : "smooth" })
  }

  // Paso 1: fotos y cámaras
  const [fotos, setFotos] = useState<Record<Vista, File | null>>({ costado: null, frente: null, aerea: null })
  const [fuentes, setFuentes] = useState<Record<Vista, Fuente>>(() => leer("local", CLAVE_FUENTES, { costado: { modo: "archivo" }, frente: { modo: "archivo" }, aerea: { modo: "archivo" } }))
  const [orientacion, setOrientacion] = useState("auto")
  const [borrador] = useState(() => {
    const existente = leer<string | null>("sesion", CLAVE_BORRADOR, null)
    const id = existente ?? `borrador-${Date.now().toString(36)}`
    guardar("sesion", CLAVE_BORRADOR, id)
    return id
  })
  const [tomas, setTomas] = useState<Toma[]>([])
  const [capturaBust, setCapturaBust] = useState(0)
  const [limites, setLimites] = useState({ max: 120, horas: 24 })
  const [tomaSel, setTomaSel] = useState<string | null>(null)
  const [seguirUltima, setSeguirUltima] = useState(true)
  const [auto, setAuto] = useState(false)
  const [intervaloS, setIntervaloS] = useState(() => leer("local", CLAVE_INTERVALO, 10))
  const [proxima, setProxima] = useState<number | null>(null)
  const [ahora, setAhora] = useState(() => Date.now())
  const [capturando, setCapturando] = useState(false)
  const [errorCaptura, setErrorCaptura] = useState<string | null>(null)

  // Paso 2: tarea
  const [casoId, setCasoId] = useState(sugerirId)
  const [tarea, setTarea] = useState<TipoTarea>("levantamiento")
  const [carga, setCarga] = useState("0")
  const [agarre, setAgarre] = useState("bueno")
  const [postura, setPostura] = useState("de_pie")
  const [trabajo, setTrabajo] = useState("ligero")

  // Paso 3: ajustes
  const [ajustes, setAjustes] = useState<Record<string, boolean>>({})
  const [lados, setLados] = useState<Record<string, Record<Lado, boolean>>>({})

  const [trabajando, setTrabajando] = useState(false)
  const [proponiendo, setProponiendo] = useState(false)
  const [asignandoVistas, setAsignandoVistas] = useState(false)
  const [propuesta, setPropuesta] = useState<{ motivos: string[]; advertencias: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => guardar("local", CLAVE_FUENTES, fuentes), [fuentes])
  useEffect(() => guardar("local", CLAVE_INTERVALO, intervaloS), [intervaloS])

  useEffect(() => {
    api.tomas(borrador).then((r) => {
      setTomas(r.tomas)
      setLimites({ max: r.max_tomas ?? 120, horas: r.retencion_horas ?? 24 })
      setTomaSel(r.tomas[0]?.id ?? null)
    }).catch(() => undefined)
  }, [borrador])

  // Cámaras asignadas y conectadas; cierra las que ya no usa ninguna vista
  const conectada = useCallback((f: Fuente) => f.modo === "camara" && !!f.deviceId && camaras.camaras.some((c) => c.deviceId === f.deviceId), [camaras.camaras])
  const vistasCamara = VISTAS.map((v) => v.vista).filter((v) => conectada(fuentes[v]))
  const asignadas = useMemo(() => new Set(Object.values(fuentes).flatMap((f) => (f.modo === "camara" && f.deviceId ? [f.deviceId] : []))), [fuentes])
  const previas = useRef(new Set<string>())
  const { cerrar } = camaras
  useEffect(() => {
    for (const id of previas.current) if (!asignadas.has(id)) cerrar(id)
    previas.current = new Set(asignadas)
  }, [asignadas, cerrar])

  // Captura simultánea de todas las vistas con cámara
  const capturandoRef = useRef(false)
  const seguirRef = useRef(seguirUltima)
  seguirRef.current = seguirUltima
  const tomar = async () => {
    if (capturandoRef.current || !vistasCamara.length) return
    capturandoRef.current = true
    setCapturando(true)
    try {
      const pares = await conLimite(Promise.all(vistasCamara.map(async (v) => {
        const fuente = fuentes[v] as { modo: "camara"; deviceId: string }
        return [v, await camaras.capturar(fuente.deviceId)] as const
      })), 10000, "una cámara no respondió en 10 s")
      const respuesta = await api.capturar(borrador, Object.fromEntries(pares))
      setTomas(respuesta.tomas)
      setErrorCaptura(null)
      if (seguirRef.current) setTomaSel(respuesta.toma.id)
    } catch (e) {
      setErrorCaptura(`No se guardó la toma: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      capturandoRef.current = false
      setCapturando(false)
    }
  }
  const tomarRef = useRef(tomar)
  tomarRef.current = tomar

  useEffect(() => {
    if (!auto) {
      setProxima(null)
      return
    }
    let siguiente = Date.now() + intervaloS * 1000
    setProxima(siguiente)
    const reloj = window.setInterval(() => {
      const t = Date.now()
      setAhora(t)
      if (t >= siguiente) {
        siguiente = t + intervaloS * 1000
        setProxima(siguiente)
        void tomarRef.current()
      }
    }, 250)
    return () => window.clearInterval(reloj)
  }, [auto, intervaloS])

  useEffect(() => {
    if (!vistasCamara.length && auto) setAuto(false)
  }, [vistasCamara.length, auto])

  const tomaElegida = tomas.find((t) => t.id === tomaSel) ?? (seguirUltima ? tomas[0] : undefined) ?? null
  const origen = (v: Vista): "archivo" | "captura" | null =>
    fuentes[v].modo === "archivo" ? (fotos[v] ? "archivo" : null) : tomaElegida?.vistas.includes(v) && conectada(fuentes[v]) ? "captura" : null
  const vistasListas = VISTAS.filter(({ vista }) => origen(vista))
  const vistasCaptura = VISTAS.map((v) => v.vista).filter((v) => origen(v) === "captura")

  const cargaNum = Number(carga.replace(",", "."))
  const idValido = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(casoId)
  const CARGA_KG_MAX = 100
  const cargaValida = Number.isFinite(cargaNum) && cargaNum >= 0 && cargaNum <= CARGA_KG_MAX
  const motivoCarga = !Number.isFinite(cargaNum)
    ? "La carga debe ser un número en kg."
    : cargaNum < 0
      ? "La carga no puede ser negativa."
      : cargaNum > CARGA_KG_MAX
        ? `Máximo ${CARGA_KG_MAX} kg (manejo manual creíble). Si es asistida, declara lo que sostiene la persona.`
        : null
  const activos = Object.values(ajustes).filter(Boolean).length + Object.values(lados).flatMap((l) => Object.values(l)).filter(Boolean).length
  const pasos = [
    { titulo: TITULOS[0], listo: vistasListas.length > 0, resumen: vistasListas.length ? `${vistasListas.length} de 3 vistas listas` : "Falta al menos una vista" },
    { titulo: TITULOS[1], listo: idValido && cargaValida, resumen: idValido && cargaValida ? `${etiquetaTarea(tarea)}, ${cargaNum} kg` : "Revisa identificador y carga" },
    { titulo: TITULOS[2], listo: paso === 2 || activos > 0, resumen: activos ? `${activos} ${activos === 1 ? "ajuste activo" : "ajustes activos"}` : "Sin ajustes" },
  ]
  const primerPendiente = !pasos[0].listo ? 0 : !pasos[1].listo ? 1 : null
  const puedeAnalizar = primerPendiente === null && !trabajando

  async function asignarVistasAutomatico() {
    setAsignandoVistas(true)
    setError(null)
    const partes: string[] = []
    let fotosTrasClasificar = fotos
    try {
      const hayArchivo = VISTAS.some(({ vista }) => origen(vista) === "archivo" && fotos[vista])
      const hayToma = Boolean(vistasCaptura.length && tomaElegida)
      if (hayArchivo || hayToma) {
        const formulario = new FormData()
        for (const { vista } of VISTAS) {
          if (origen(vista) === "archivo" && fotos[vista]) formulario.set(vista, fotos[vista]!)
        }
        if (hayToma && tomaElegida) {
          formulario.set("borrador", borrador)
          formulario.set("toma", tomaElegida.id)
          formulario.set("vistas_toma", vistasCaptura.join(","))
          formulario.set("aplicar_toma", "1")
        }
        const resp = await api.clasificarVistas(formulario)
        if (resp.ok && resp.asignaciones?.length) {
          const porId = new Map(resp.asignaciones.map((a) => [a.id, a.vista]))
          const originales: Partial<Record<Vista, File>> = {}
          for (const { vista } of VISTAS) {
            if (origen(vista) === "archivo" && fotos[vista]) originales[vista] = fotos[vista]!
          }
          const reordenadas: Record<Vista, File | null> = { costado: null, frente: null, aerea: null }
          let movioArchivo = false
          for (const origenVista of Object.keys(originales) as Vista[]) {
            const dest = porId.get(origenVista)
            if (!dest || !originales[origenVista]) continue
            reordenadas[dest] = originales[origenVista]!
            if (dest !== origenVista) movioArchivo = true
          }
          if (Object.values(originales).some(Boolean)) {
            fotosTrasClasificar = reordenadas
            if (movioArchivo || Object.values(reordenadas).filter(Boolean).length) {
              setFotos(reordenadas)
              setFuentes((prev) => ({
                costado: reordenadas.costado ? { modo: "archivo" } : prev.costado,
                frente: reordenadas.frente ? { modo: "archivo" } : prev.frente,
                aerea: reordenadas.aerea ? { modo: "archivo" } : prev.aerea,
              }))
            }
          }
          if (resp.toma_reordenada?.length) {
            setCapturaBust(Date.now())
            try {
              const r = await api.tomas(borrador)
              setTomas(r.tomas)
            } catch { /* la asignación ya quedó en disco */ }
          }
          partes.push(resp.motivos?.slice(0, 3).join(" · ") || "Fotos/capturas colocadas por pose y nombre.")
        }
      }

      let lista = camaras.camaras
      if (!lista.length || camaras.permiso !== "concedido") {
        await camaras.detectar()
        lista = await camaras.listar()
      }
      if (lista.length) {
        const { fuentes: asignadas, detalle } = asignarCamarasAVistas(lista)
        setFuentes((prev) => ({
          costado: prev.costado.modo === "archivo" && fotosTrasClasificar.costado ? prev.costado : asignadas.costado,
          frente: prev.frente.modo === "archivo" && fotosTrasClasificar.frente ? prev.frente : asignadas.frente,
          aerea: prev.aerea.modo === "archivo" && fotosTrasClasificar.aerea ? prev.aerea : asignadas.aerea,
        }))
        partes.push(detalle)
      }

      if (!partes.length) {
        avisar({
          titulo: "Nada que asignar",
          detalle: "Sube fotos, elige una toma capturada o conecta cámaras.",
          tipo: "error",
        })
        return
      }
      avisar({ titulo: "Vistas asignadas", detalle: partes.join(" ") })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      avisar({ titulo: "No se asignaron las vistas", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
    } finally {
      setAsignandoVistas(false)
    }
  }

  async function proponerDesdeFotos() {
    if (!vistasListas.length) {
      avisar({ titulo: "Faltan fotos", detalle: "Sube o captura al menos una vista antes de proponer.", tipo: "error" })
      irPaso(0)
      return
    }
    setError(null)
    setProponiendo(true)
    const formulario = new FormData()
    formulario.set("carga_kg", String(Number.isFinite(cargaNum) ? cargaNum : 0))
    for (const { vista } of VISTAS) if (origen(vista) === "archivo" && fotos[vista]) formulario.set(vista, fotos[vista]!)
    if (vistasCaptura.length && tomaElegida) {
      formulario.set("borrador", borrador)
      formulario.set("toma", tomaElegida.id)
      formulario.set("vistas_toma", vistasCaptura.join(","))
    }
    try {
      const resp = await api.proponerContexto(formulario)
      setPropuesta({ motivos: resp.motivos ?? [], advertencias: resp.advertencias ?? [] })
      if (!resp.ok) {
        avisar({ titulo: "No se pudo proponer", detalle: resp.motivos?.[0] ?? "Revisa las fotos.", tipo: "error" })
        return
      }
      const s = resp.sugerencias ?? {}
      if (s.postura === "de_pie" || s.postura === "sentado" || s.postura === "alternada") setPostura(s.postura)
      if (s.tipo_trabajo === "precision" || s.tipo_trabajo === "ligero" || s.tipo_trabajo === "pesado") setTrabajo(s.tipo_trabajo)
      setAjustes({
        estatica: Boolean(s.actividad?.estatica_mas_1min),
        repetitiva: Boolean(s.actividad?.repetitiva_mas_4_por_min),
        inestable: Boolean(s.actividad?.cambios_bruscos_o_base_inestable),
        fuerza_brusca: Boolean(s.fuerza_brusca),
      })
      setLados({
        hombro_elevado: {
          izquierdo: Boolean(s.hombro_elevado?.izquierdo),
          derecho: Boolean(s.hombro_elevado?.derecho),
        },
        brazo_apoyado: {
          izquierdo: Boolean(s.brazo_apoyado?.izquierdo),
          derecho: Boolean(s.brazo_apoyado?.derecho),
        },
        muneca_desviada_o_torcida: {
          izquierdo: Boolean(s.muneca_desviada_o_torcida?.izquierdo),
          derecho: Boolean(s.muneca_desviada_o_torcida?.derecho),
        },
      })
      avisar({
        titulo: "Propuesta lista",
        detalle: "Se rellenaron postura y ajustes según la pose. Revísalos: tú decides qué queda.",
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      avisar({ titulo: "No se propuso el contexto", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
    } finally {
      setProponiendo(false)
    }
  }

  async function analizar(reemplazar = false) {
    if (primerPendiente !== null) {
      irPaso(primerPendiente)
      return
    }
    setError(null)
    setTrabajando(true)
    setAuto(false)
    const contexto = {
      caso_id: casoId, realizado_por: nombre.trim(), tipo_tarea: tarea, tipo_trabajo: trabajo, postura,
      orientacion_costado: orientacion === "auto" ? null : orientacion, carga_kg: cargaNum, agarre,
      fuerza_brusca: Boolean(ajustes.fuerza_brusca),
      actividad: { estatica_mas_1min: Boolean(ajustes.estatica), repetitiva_mas_4_por_min: Boolean(ajustes.repetitiva), cambios_bruscos_o_base_inestable: Boolean(ajustes.inestable) },
      ...Object.fromEntries(AJUSTES_LADO.map(({ clave }) => [clave, { izquierdo: Boolean(lados[clave]?.izquierdo), derecho: Boolean(lados[clave]?.derecho) }])),
    }
    const formulario = new FormData()
    formulario.set("contexto", JSON.stringify(contexto))
    formulario.set("reemplazar", String(reemplazar))
    for (const { vista } of VISTAS) if (origen(vista) === "archivo" && fotos[vista]) formulario.set(vista, fotos[vista]!)
    if (vistasCaptura.length && tomaElegida) {
      formulario.set("borrador", borrador)
      formulario.set("toma", tomaElegida.id)
      formulario.set("vistas_toma", vistasCaptura.join(","))
    }
    try {
      const estado = await api.crear(formulario)
      guardar("sesion", CLAVE_BORRADOR, null) // la próxima evaluación empieza con tomas nuevas
      avisar({ titulo: "Análisis terminado", detalle: `REBA ${estado.resultado.reba.final.reportado ?? "pendiente"} con ${estado.validacion.recomendaciones.length} controles propuestos para validar.` })
      ir({ nombre: "caso", id: estado.resultado.caso_id })
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 409) {
        setTrabajando(false)
        if (window.confirm(`${e.message}\n\n¿Reemplazar el análisis anterior? Las decisiones ya registradas se conservan en la bitácora.`)) void analizar(true)
        return
      }
      setError(e instanceof Error ? e.message : String(e))
    }
    setTrabajando(false)
  }

  const proximaEn = proxima != null ? Math.max(0, Math.ceil((proxima - ahora) / 1000)) : null
  const variantes = {
    entra: (d: number) => ({ x: reducir ? 0 : 48 * d, opacity: 0 }),
    quieto: { x: 0, opacity: 1 },
    sale: (d: number) => ({ x: reducir ? 0 : -48 * d, opacity: 0 }),
  }

  async function aceptarFoto(archivo: File, vista: Vista): Promise<boolean> {
    try {
      const resp = await api.validarFoto(archivo, vista)
      if (!resp.ok) {
        avisar({
          titulo: "Foto rechazada",
          detalle: resp.motivo ?? "No sirve para medir postura.",
          tipo: "error",
        })
        return false
      }
      setFotos((prev) => ({ ...prev, [vista]: archivo }))
      if (resp.advertencia) {
        avisar({ titulo: "Foto aérea aceptada", detalle: resp.advertencia })
      }
      return true
    } catch (e) {
      avisar({
        titulo: "No se pudo validar la foto",
        detalle: e instanceof Error ? e.message : String(e),
        tipo: "error",
      })
      return false
    }
  }

  function repartirArchivos(lista: FileList | File[]) {
    const imagenes = filtrarImagenesErgo(lista).slice(0, 3)
    if (!imagenes.length) {
      if ([...lista].some((f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|bmp)$/i.test(f.name))) {
        avisar({ titulo: "Formato no admitido", detalle: "Usa JPG o PNG.", tipo: "error" })
      }
      return
    }
    const orden: Vista[] = ["costado", "frente", "aerea"]
    void (async () => {
      const libres = orden.filter((v) => fuentes[v].modo === "archivo" && !fotos[v])
      const destinos = libres.length ? libres : orden.filter((v) => fuentes[v].modo === "archivo")
      let ok = 0
      for (let i = 0; i < imagenes.length; i++) {
        const archivo = imagenes[i]!
        const nombre = archivo.name.toLowerCase()
        const porNombre = orden.find((v) => nombre.includes(v) || (v === "aerea" && (nombre.includes("aerea") || nombre.includes("aérea") || nombre.includes("top"))))
        const vista = porNombre && fuentes[porNombre].modo === "archivo" ? porNombre : destinos[i]
        if (!vista) continue
        if (await aceptarFoto(archivo, vista)) ok += 1
      }
      if (ok > 0) {
        avisar({ titulo: ok === 1 ? "Foto aceptada" : `${ok} fotos aceptadas`, detalle: "Pasaron el filtro de calidad y persona." })
      }
    })()
  }

  // Ctrl+V en el paso de fotos: pega en el primer hueco libre (si el foco no está en una ranura).
  useEffect(() => {
    if (paso !== 0) return
    const onPaste = (e: globalThis.ClipboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return
      if (t?.closest?.("[data-ranura-foto]")) return
      const hayImagen = [...(e.clipboardData?.items ?? [])].some((i) => i.kind === "file" && i.type.startsWith("image/"))
      if (!hayImagen) return
      e.preventDefault()
      void imagenDesdeClipboard(e.clipboardData).then(async (img) => {
        if (!img) return
        const orden: Vista[] = ["costado", "frente", "aerea"]
        const libre = orden.find((v) => fuentes[v].modo === "archivo" && !fotos[v]) ?? orden.find((v) => fuentes[v].modo === "archivo")
        if (!libre) {
          avisar({ titulo: "No hay ranura libre", detalle: "Cambia una vista a Archivo o quita una foto.", tipo: "error" })
          return
        }
        if (await aceptarFoto(img, libre)) {
          avisar({ titulo: "Foto pegada", detalle: `Se asignó a ${libre}.` })
        }
      })
    }
    window.addEventListener("paste", onPaste)
    return () => window.removeEventListener("paste", onPaste)
  }, [paso, fuentes, fotos])

  return (
    <div className="mx-auto max-w-[1180px]">
      <header className="pb-6">
        <p className="text-[12px] font-semibold tracking-[0.14em] text-jabil-cyan uppercase">Paso a paso</p>
        <h1 className="t-display mt-1 text-[44px] text-jabil sm:text-[56px]">Nueva evaluación</h1>
        <p className="mt-3 max-w-[64ch] text-[16px] text-ink-soft">
          Arrastra, elige o pega fotos con Ctrl+V (o usa cámaras). Describe la tarea y marca lo que la foto no muestra.
        </p>
      </header>

      <Pasos pasos={pasos} actual={paso} onIr={irPaso} />

      <form className="mt-8" onSubmit={(e) => { e.preventDefault(); if (paso < 2) irPaso(paso + 1); else if (puedeAnalizar) void analizar() }}>
        <AnimatePresence mode="wait" custom={direccion} initial={false}>
          <motion.div key={paso} custom={direccion} variants={variantes} initial="entra" animate="quieto" exit="sale" transition={{ duration: 0.22, ease: "easeOut" }}>
            {paso === 0 && (
              <div
                className="space-y-6"
                onDragOver={(e) => {
                  if ([...e.dataTransfer.types].includes("Files")) {
                    e.preventDefault()
                    e.dataTransfer.dropEffect = "copy"
                  }
                }}
                onDrop={(e) => {
                  if (![...e.dataTransfer.types].includes("Files")) return
                  // Si cayó en una ranura, ella ya lo manejó con stopPropagation.
                  if ((e.target as HTMLElement | null)?.closest?.("[data-ranura-foto]")) return
                  e.preventDefault()
                  repartirArchivos(e.dataTransfer.files)
                }}
              >
                <EstadoCamaras
                  {...camaras}
                  asignando={asignandoVistas}
                  onAsignarAuto={() => void asignarVistasAutomatico()}
                />
                <p className="text-[13px] text-ink-soft">
                  <span className="font-semibold text-jabil">Costado</span> es la vista principal. Suelta la foto en su recuadro, o pega con <kbd className="rounded border border-rule bg-sheet px-1 font-medium text-jabil">Ctrl+V</kbd>.
                  {" "}<span className="font-medium text-jabil">Asignar vistas</span> coloca fotos/capturas en costado·frente·aérea (pose + nombre) y enlaza cámaras si hay.
                </p>
                <div className="grid gap-6 md:grid-cols-3 md:grid-rows-[auto_auto_auto_auto] md:gap-x-4 md:gap-y-2">
                  {VISTAS.map(({ vista, titulo, ayuda }) => (
                    <VistaFuente key={vista} vista={vista} titulo={titulo} ayuda={ayuda} principal={vista === "costado"}
                      fuente={fuentes[vista]} onFuente={(f) => setFuentes((prev) => ({ ...prev, [vista]: f }))}
                      archivo={fotos[vista]}
                      onArchivo={async (a) => {
                        if (!a) {
                          setFotos((prev) => ({ ...prev, [vista]: null }))
                          return
                        }
                        const ok = await aceptarFoto(a, vista)
                        if (ok && vista !== "aerea") {
                          avisar({ titulo: "Foto aceptada", detalle: `Vista ${vista}: hay persona y calidad suficiente.` })
                        }
                        return ok
                      }}
                      camaras={camaras.camaras} abrir={camaras.abrir}
                      capturaElegida={origen(vista) === "captura" && tomaElegida ? hora(tomaElegida.fecha) : null} />
                  ))}
                </div>
                {Object.values(fuentes).some((f) => f.modo === "camara") && (
                  <PanelTomas borrador={borrador} tomas={tomas} seleccion={tomaElegida?.id ?? null}
                    onSeleccion={(id) => { setTomaSel(id); setSeguirUltima(false) }}
                    seguirUltima={seguirUltima} onSeguirUltima={() => { setSeguirUltima(true); setTomaSel(tomas[0]?.id ?? null) }}
                    auto={auto} onAuto={(activo) => { setAuto(activo); if (activo) void tomar() }}
                    intervaloS={intervaloS} onIntervalo={setIntervaloS} onCapturarAhora={() => void tomar()}
                    proximaEn={proximaEn} capturando={capturando} error={errorCaptura} maxTomas={limites.max} retencionHoras={limites.horas}
                    camarasAsignadas={vistasCamara.length} capturaBust={capturaBust}
                    onDescartar={async () => {
                      if (!window.confirm("¿Descartar todas las tomas de esta evaluación? Se borran de este equipo.")) return
                      setAuto(false)
                      setTomas((await api.descartarTomas(borrador)).tomas)
                      setTomaSel(null)
                      setSeguirUltima(true)
                    }} />
                )}
                <Campo etiqueta="En la vista de costado, el operador mira hacia">
                  <HaloSegmented className="overflow-x-auto" translucent={false} value={orientacion} onValueChange={setOrientacion}
                    items={[{ value: "auto", label: "Detectar" }, { value: "derecha", label: "Derecha" }, { value: "izquierda", label: "Izquierda" }]} />
                </Campo>
                <p className="text-[14px] text-graphite">
                  Costado y frente bastan para un REBA completo; la aérea agrega la torsión del tronco. Las tomas de cámara se guardan con el rostro difuminado
                  y la pose se mide antes de difuminar, así que la precisión no cambia. Las fotos subidas como archivo deben venir ya sin rostros.
                </p>
              </div>
            )}

            {paso === 1 && (
              <div className="grid max-w-[720px] gap-5">
                <BotonProponer
                  disabled={!vistasListas.length || proponiendo || trabajando}
                  ocupado={proponiendo}
                  onClick={() => void proponerDesdeFotos()}
                />
                {propuesta && <ResumenPropuesta propuesta={propuesta} />}
                <Campo etiqueta="Identificador del caso">
                  <input className="campo t-num text-[17px]" value={casoId} onChange={(e) => setCasoId(e.target.value.trim())} aria-invalid={!idValido} />
                  <p className="mt-1 text-[12px] text-graphite">Autogenerado · editable</p>
                  {!idValido && <p className="mt-1 text-[13px] text-[var(--riesgo-muy-alto)]">Usa letras, números, punto, guion o guion bajo.</p>}
                </Campo>
                <Campo etiqueta="Tipo de tarea">
                  <HaloSegmented className="overflow-x-auto" translucent={false} value={tarea} onValueChange={(v) => setTarea(v as TipoTarea)}
                    items={TAREAS.map((t) => ({ value: t.valor, label: t.etiqueta }))} />
                </Campo>
                <div className="flex flex-wrap gap-x-4 gap-y-4">
                  <Campo etiqueta="Carga (kg)" className="w-[120px]">
                    <input className="campo t-num text-[17px]" inputMode="decimal" value={carga} onChange={(e) => setCarga(e.target.value)} placeholder="0" aria-invalid={!cargaValida} />
                    {carga === "0" || carga === "" ? <p className="mt-1 text-[12px] text-graphite">0 kg (sin carga)</p> : null}
                    {motivoCarga && <p className="mt-1 text-[13px] font-medium text-amber-950">{motivoCarga}</p>}
                  </Campo>
                  <Campo etiqueta="Agarre de la carga">
                    <HaloSegmented className="overflow-x-auto" translucent={false} value={agarre} onValueChange={setAgarre}
                      items={["bueno", "regular", "malo", "inaceptable"].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }))} />
                  </Campo>
                </div>
                {cargaValida && cargaNum > 14 && <p className="text-[14px] text-ink-soft">Más de 14 kg: supera el límite por persona de Jabil y se propondrá asistencia mecánica.</p>}
                <div className="flex flex-wrap gap-x-6 gap-y-4">
                  <Campo etiqueta="Postura">
                    <HaloSegmented className="overflow-x-auto" translucent={false} value={postura} onValueChange={setPostura}
                      items={[{ value: "de_pie", label: "De pie" }, { value: "sentado", label: "Sentado" }, { value: "alternada", label: "Alterna" }]} />
                  </Campo>
                  <Campo etiqueta="Tipo de trabajo">
                    <HaloSegmented className="overflow-x-auto" translucent={false} value={trabajo} onValueChange={setTrabajo}
                      items={[{ value: "precision", label: "Precisión" }, { value: "ligero", label: "Ligero" }, { value: "pesado", label: "Pesado" }]} />
                  </Campo>
                </div>
              </div>
            )}

            {paso === 2 && (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="max-w-[480px]">
                  <BotonProponer
                    disabled={!vistasListas.length || proponiendo || trabajando}
                    ocupado={proponiendo}
                    onClick={() => void proponerDesdeFotos()}
                  />
                  {propuesta && <div className="mb-3"><ResumenPropuesta propuesta={propuesta} /></div>}
                  <p className="mb-2 text-[14px] text-graphite">Ajustes REBA que se observan en piso. Si no aplican, déjalos apagados.</p>
                  <ul className="divide-y divide-rule-soft">
                    {AJUSTES.map(({ clave, texto }) => (
                      <li key={clave} className="flex items-center justify-between gap-3 py-2">
                        <span className="text-[14px] leading-snug">{texto}</span>
                        <HaloSwitch translucent={false} size="sm" aria-label={texto} checked={Boolean(ajustes[clave])}
                          onCheckedChange={(v) => setAjustes((a) => ({ ...a, [clave]: v }))} />
                      </li>
                    ))}
                    {AJUSTES_LADO.map(({ clave, texto }) => (
                      <li key={clave} className="flex items-center justify-between gap-3 py-2">
                        <span className="text-[14px] leading-snug">{texto}</span>
                        <span className="flex shrink-0 items-center gap-3 text-[12px] text-graphite">
                          {(["izquierdo", "derecho"] as Lado[]).map((lado) => (
                            <label key={lado} className="flex items-center gap-1.5">
                              {lado === "izquierdo" ? "Izq." : "Der."}
                              <HaloSwitch translucent={false} size="sm" aria-label={`${texto} ${lado}`} checked={Boolean(lados[clave]?.[lado])}
                                onCheckedChange={(v) => setLados((l) => ({ ...l, [clave]: { ...(l[clave] ?? { izquierdo: false, derecho: false }), [lado]: v } }))} />
                            </label>
                          ))}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4"><FlujoAgente trabajando={trabajando} /></div>
                </div>
                <Resumen fotos={fotos} origen={origen} tomaElegida={tomaElegida} borrador={borrador} casoId={casoId} tarea={tarea}
                  carga={cargaNum} agarre={agarre} postura={postura} onIr={irPaso} capturaBust={capturaBust} />
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {error && <p role="alert" className="mt-6 rounded-lg border border-[var(--riesgo-muy-alto)] bg-sheet p-4 text-[14px]">{error}</p>}

        <div className="sticky bottom-0 z-20 mt-10 flex flex-wrap items-end justify-between gap-3 border-t border-ink bg-vellum/95 py-4 backdrop-blur">
          <button type="button" className="boton-linea" disabled={paso === 0 || trabajando} onClick={() => irPaso(paso - 1)}>
            <ArrowLeft className="size-4" /> Anterior
          </button>
          <div className="flex flex-col items-end gap-1.5">
            {paso === 2 && !puedeAnalizar && !trabajando && (
              <p className="max-w-[36ch] text-right text-[13px] font-medium text-amber-900">
                {primerPendiente !== null
                  ? `Falta completar el paso ${primerPendiente + 1}: ${TITULOS[primerPendiente].toLowerCase()}.`
                  : "Completa los requisitos para analizar."}
              </p>
            )}
            {paso < 2 ? (
              <button type="submit" className="boton-tinta">Siguiente: {TITULOS[paso + 1].toLowerCase()} <ArrowRight className="size-4" /></button>
            ) : (
              <ShimmerButton type="submit" disabled={!puedeAnalizar} background="#00a3e0" shimmerColor="#e0f5fc" borderRadius="10px"
                className="px-6 py-3 text-[15px] font-semibold text-white disabled:opacity-40">
                {trabajando ? "Analizando…" : "Analizar postura"}
              </ShimmerButton>
            )}
            {trabajando && (
              <p className="text-[13px] text-graphite">Detectando pose y midiendo ángulos…</p>
            )}
          </div>
        </div>
      </form>
    </div>
  )
}

function BotonProponer({ disabled, ocupado, onClick }: { disabled?: boolean; ocupado?: boolean; onClick: () => void }) {
  return (
    <div className="rounded-[12px] border border-jabil/20 bg-jabil/[0.04] p-3">
      <button type="button" className="boton-tinta" disabled={disabled} onClick={onClick}>
        <Sparkles className="size-4" />
        {ocupado ? "Analizando fotos…" : "Proponer desde las fotos"}
      </button>
      <p className="mt-2 text-[12px] leading-snug text-graphite">
        Detecta la pose en este equipo (MediaPipe) y sugiere postura y ajustes REBA. No inventa kg, agarre ni estática/repetición:
        eso se confirma en piso. Tú puedes corregir todo antes de analizar.
      </p>
    </div>
  )
}

function ResumenPropuesta({ propuesta }: { propuesta: { motivos: string[]; advertencias: string[] } }) {
  return (
    <div className="rounded-[12px] border border-rule bg-sheet p-3 text-[12px] leading-snug text-ink-soft">
      {propuesta.advertencias.slice(0, 2).map((t) => (
        <p key={t} className="text-graphite">{t}</p>
      ))}
      {propuesta.motivos.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-4">
          {propuesta.motivos.slice(0, 8).map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
    </div>
  )
}

/** Empareja cámaras con costado/frente/aérea por el nombre del dispositivo; el resto en orden. */
function asignarCamarasAVistas(lista: Camara[]): { fuentes: Record<Vista, Fuente>; detalle: string } {
  const orden: Vista[] = ["costado", "frente", "aerea"]
  const pistas: Record<Vista, RegExp> = {
    costado: /\b(costado|lado|side|perfil|lateral)\b/i,
    frente: /\b(frente|front|frontal)\b/i,
    aerea: /\b(a[eé]rea|aerial|overhead|cenital|top|arriba|techo)\b/i,
  }
  const usadas = new Set<string>()
  const mapa: Partial<Record<Vista, string>> = {}

  for (const vista of orden) {
    const hit = lista.find((c) => !usadas.has(c.deviceId) && pistas[vista].test(c.nombre))
    if (hit) {
      mapa[vista] = hit.deviceId
      usadas.add(hit.deviceId)
    }
  }
  for (const vista of orden) {
    if (mapa[vista]) continue
    const siguiente = lista.find((c) => !usadas.has(c.deviceId))
    if (!siguiente) break
    mapa[vista] = siguiente.deviceId
    usadas.add(siguiente.deviceId)
  }

  const fuentes: Record<Vista, Fuente> = {
    costado: mapa.costado ? { modo: "camara", deviceId: mapa.costado } : { modo: "archivo" },
    frente: mapa.frente ? { modo: "camara", deviceId: mapa.frente } : { modo: "archivo" },
    aerea: mapa.aerea ? { modo: "camara", deviceId: mapa.aerea } : { modo: "archivo" },
  }
  const etiqueta = (id: string) => lista.find((c) => c.deviceId === id)?.nombre ?? "cámara"
  const partes = orden
    .filter((v) => mapa[v])
    .map((v) => `${v === "aerea" ? "Aérea" : v[0].toUpperCase() + v.slice(1)} → ${etiqueta(mapa[v]!)}`)
  return {
    fuentes,
    detalle: partes.length
      ? `${partes.join(" · ")}. Puedes cambiarlas a mano si hace falta.`
      : "No se pudo asignar ninguna cámara.",
  }
}

function EstadoCamaras({
  camaras, permiso, error, detectar, onAsignarAuto, asignando,
}: ReturnType<typeof useCamaras> & { onAsignarAuto?: () => void | Promise<void>; asignando?: boolean }) {
  if (permiso === "sin-soporte") {
    return <p className="rounded-[12px] border border-rule bg-sheet p-4 text-[14px] text-ink-soft">Este navegador no permite usar cámaras. Abre ErgoAI con su ejecutable o en Edge/Chrome.</p>
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-rule bg-sheet px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <Camera className="size-5 shrink-0 text-ink-soft" strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-[15px] font-medium">
            {permiso === "concedido" ? (camaras.length ? `${camaras.length} ${camaras.length === 1 ? "cámara conectada" : "cámaras conectadas"}` : "No hay cámaras conectadas") : "Usa las cámaras conectadas a este equipo"}
          </p>
          <p className={cn("truncate text-[13px]", error ? "text-[var(--riesgo-muy-alto)]" : "text-graphite")}>
            {error ?? (permiso === "concedido" ? camaras.map((c) => c.nombre).join(", ") || "Conecta una y vuelve a detectar." : "Asigna fotos, capturas o cámaras a cada vista.")}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {onAsignarAuto && (
          <button
            type="button"
            className="boton-tinta"
            disabled={asignando}
            onClick={() => void onAsignarAuto()}
            title="Coloca fotos/capturas en costado·frente·aérea y enlaza cámaras si hay"
          >
            <Wand2 className={cn("size-4", asignando && "animate-spin")} /> {asignando ? "Asignando…" : "Asignar vistas"}
          </button>
        )}
        <button type="button" className={permiso === "concedido" ? "boton-linea" : "boton-tinta"} onClick={() => void detectar()}>
          <RefreshCw className="size-4" /> {permiso === "concedido" ? "Volver a detectar" : "Detectar cámaras"}
        </button>
      </div>
    </div>
  )
}

function Resumen({ fotos, origen, tomaElegida, borrador, casoId, tarea, carga, agarre, postura, onIr, capturaBust }: {
  fotos: Record<Vista, File | null>
  origen: (v: Vista) => "archivo" | "captura" | null
  tomaElegida: Toma | null
  borrador: string
  casoId: string
  tarea: TipoTarea
  carga: number
  agarre: string
  postura: string
  onIr: (paso: number) => void
  capturaBust?: number
}) {
  const [urls, setUrls] = useState<Record<string, string>>({})
  useEffect(() => {
    const creadas = Object.fromEntries(Object.entries(fotos).filter(([, f]) => f).map(([v, f]) => [v, URL.createObjectURL(f!)]))
    setUrls(creadas)
    return () => Object.values(creadas).forEach(URL.revokeObjectURL)
  }, [fotos])

  const srcDe = (vista: Vista) => {
    const fuente = origen(vista)
    if (fuente === "archivo") return urls[vista] ?? null
    if (fuente === "captura" && tomaElegida) return api.captura(borrador, tomaElegida.id, vista, capturaBust)
    return null
  }
  const principal = (["costado", "frente", "aerea"] as Vista[]).find((v) => srcDe(v)) ?? "costado"
  const srcPrincipal = srcDe(principal)
  const faltaCostado = !srcDe("costado")

  return (
    <aside className="trazo-tinta self-start rounded-[12px] p-4" aria-label="Resumen antes de analizar">
      <div className="flex items-center justify-between gap-2">
        <h3 className="t-title text-[17px]">Se va a analizar</h3>
        <button type="button" className="text-[13px] font-medium text-jabil underline underline-offset-4 hover:text-jabil-soft" onClick={() => onIr(0)}>Cambiar fotos</button>
      </div>

      {faltaCostado && (
        <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-[13px] font-medium text-amber-950">
          Falta foto de costado (obligatoria).
        </p>
      )}

      <figure className="mt-3">
        <div className="aspect-[4/3] max-w-[220px] overflow-hidden rounded-md border border-rule bg-ink/5">
          {srcPrincipal
            ? <img src={srcPrincipal} alt={`Vista ${principal}`} className="h-full w-full object-cover" />
            : <span className="flex h-full items-center justify-center text-[13px] text-graphite">Sin foto principal</span>}
        </div>
        <figcaption className="mt-1.5 text-[12px] text-graphite capitalize">
          {principal === "aerea" ? "Aérea" : principal}
          {origen(principal) === "captura" && tomaElegida ? ` · toma ${hora(tomaElegida.fecha)}` : origen(principal) === "archivo" ? " · archivo" : ""}
        </figcaption>
      </figure>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {VISTAS.map(({ vista, titulo }) => {
          const ok = Boolean(srcDe(vista))
          return (
            <span
              key={vista}
              className={cn(
                "rounded-md px-2 py-0.5 text-[12px] font-medium",
                ok ? "bg-jabil/10 text-jabil" : "bg-slate-100 text-graphite",
              )}
            >
              {titulo}{ok ? " ✓" : " —"}
            </span>
          )
        })}
      </div>

      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[14px]">
        <dt className="text-graphite">Caso</dt><dd className="t-num truncate">{casoId}</dd>
        <dt className="text-graphite">Tarea</dt><dd>{etiquetaTarea(tarea)}</dd>
        <dt className="text-graphite">Carga</dt><dd>{carga} kg · agarre {agarre}</dd>
        <dt className="text-graphite">Postura</dt><dd>{postura === "de_pie" ? "De pie" : postura === "sentado" ? "Sentado" : "Alterna"}</dd>
      </dl>
      <button type="button" className="mt-3 text-[13px] text-ink-soft underline underline-offset-4 hover:text-ink" onClick={() => onIr(1)}>Cambiar de tarea</button>
    </aside>
  )
}

function Campo({ etiqueta, children, className }: { etiqueta: string; children: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <p className="mb-1.5 text-[14px] font-medium text-ink-soft">{etiqueta}</p>
      {children}
    </div>
  )
}
