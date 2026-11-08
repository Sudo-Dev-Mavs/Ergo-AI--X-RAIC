import { ArrowLeft, ArrowRight, Camera, RefreshCw } from "lucide-react"
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
import { conLimite, useCamaras } from "@/lib/camaras"
import { TAREAS, etiquetaTarea } from "@/lib/dominio"
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
const TITULOS = ["Fotografías", "Tarea", "Lo que la foto no muestra"]
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
  const cargaValida = Number.isFinite(cargaNum) && cargaNum >= 0
  const activos = Object.values(ajustes).filter(Boolean).length + Object.values(lados).flatMap((l) => Object.values(l)).filter(Boolean).length
  const pasos = [
    { titulo: TITULOS[0], listo: vistasListas.length > 0, resumen: vistasListas.length ? `${vistasListas.length} de 3 vistas listas` : "Falta al menos una vista" },
    { titulo: TITULOS[1], listo: idValido && cargaValida, resumen: idValido && cargaValida ? `${etiquetaTarea(tarea)}, ${cargaNum} kg` : "Revisa identificador y carga" },
    { titulo: TITULOS[2], listo: paso === 2 || activos > 0, resumen: activos ? `${activos} ${activos === 1 ? "ajuste activo" : "ajustes activos"}` : "Sin ajustes" },
  ]
  const primerPendiente = !pasos[0].listo ? 0 : !pasos[1].listo ? 1 : null
  const puedeAnalizar = primerPendiente === null && !trabajando

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

  return (
    <div className="mx-auto max-w-[1180px]">
      <header className="pb-6">
        <h1 className="t-display text-[44px] sm:text-[56px]">Nueva evaluación</h1>
        <p className="mt-3 max-w-[64ch] text-[16px] text-ink-soft">
          Sube fotos o usa las cámaras conectadas, describe la tarea y marca lo que la foto no muestra. Puedes ir y volver entre pasos antes de analizar.
        </p>
      </header>

      <Pasos pasos={pasos} actual={paso} onIr={irPaso} />

      <form className="mt-8" onSubmit={(e) => { e.preventDefault(); if (paso < 2) irPaso(paso + 1); else if (puedeAnalizar) void analizar() }}>
        <AnimatePresence mode="wait" custom={direccion} initial={false}>
          <motion.div key={paso} custom={direccion} variants={variantes} initial="entra" animate="quieto" exit="sale" transition={{ duration: 0.22, ease: "easeOut" }}>
            {paso === 0 && (
              <div className="space-y-6">
                <EstadoCamaras {...camaras} />
                <div className="grid gap-6 md:grid-cols-3 md:gap-4">
                  {VISTAS.map(({ vista, titulo, ayuda }) => (
                    <VistaFuente key={vista} vista={vista} titulo={titulo} ayuda={ayuda} principal={vista === "costado"}
                      fuente={fuentes[vista]} onFuente={(f) => setFuentes((prev) => ({ ...prev, [vista]: f }))}
                      archivo={fotos[vista]} onArchivo={(a) => setFotos((prev) => ({ ...prev, [vista]: a }))}
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
                    camarasAsignadas={vistasCamara.length}
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
                <Campo etiqueta="Identificador del caso">
                  <input className="campo t-num text-[17px]" value={casoId} onChange={(e) => setCasoId(e.target.value.trim())} aria-invalid={!idValido} />
                  {!idValido && <p className="mt-1 text-[13px] text-[var(--riesgo-muy-alto)]">Usa letras, números, punto, guion o guion bajo.</p>}
                </Campo>
                <Campo etiqueta="Tipo de tarea">
                  <HaloSegmented className="overflow-x-auto" translucent={false} value={tarea} onValueChange={(v) => setTarea(v as TipoTarea)}
                    items={TAREAS.map((t) => ({ value: t.valor, label: t.etiqueta }))} />
                </Campo>
                <div className="flex flex-wrap gap-x-4 gap-y-4">
                  <Campo etiqueta="Carga (kg)" className="w-[120px]">
                    <input className="campo t-num text-[17px]" inputMode="decimal" value={carga} onChange={(e) => setCarga(e.target.value)} aria-invalid={!cargaValida} />
                  </Campo>
                  <Campo etiqueta="Agarre de la carga">
                    <HaloSegmented className="overflow-x-auto" translucent={false} value={agarre} onValueChange={setAgarre}
                      items={["bueno", "regular", "malo", "inaceptable"].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }))} />
                  </Campo>
                </div>
                {cargaNum > 14 && <p className="text-[14px] text-ink-soft">Más de 14 kg: supera el límite por persona de Jabil y se propondrá asistencia mecánica.</p>}
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
              <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px]">
                <div>
                  <p className="mb-2 max-w-[60ch] text-[14px] text-graphite">Ajustes REBA que se observan en piso. Si no aplican, déjalos apagados.</p>
                  <ul className="divide-y divide-rule-soft">
                    {AJUSTES.map(({ clave, texto }) => (
                      <li key={clave} className="flex items-center justify-between gap-4 py-2.5">
                        <span className="text-[15px]">{texto}</span>
                        <HaloSwitch translucent={false} size="sm" aria-label={texto} checked={Boolean(ajustes[clave])}
                          onCheckedChange={(v) => setAjustes((a) => ({ ...a, [clave]: v }))} />
                      </li>
                    ))}
                    {AJUSTES_LADO.map(({ clave, texto }) => (
                      <li key={clave} className="flex items-center justify-between gap-4 py-2.5">
                        <span className="text-[15px]">{texto}</span>
                        <span className="flex items-center gap-4 text-[13px] text-graphite">
                          {(["izquierdo", "derecho"] as Lado[]).map((lado) => (
                            <label key={lado} className="flex items-center gap-2">
                              {lado === "izquierdo" ? "Izq." : "Der."}
                              <HaloSwitch translucent={false} size="sm" aria-label={`${texto} ${lado}`} checked={Boolean(lados[clave]?.[lado])}
                                onCheckedChange={(v) => setLados((l) => ({ ...l, [clave]: { ...(l[clave] ?? { izquierdo: false, derecho: false }), [lado]: v } }))} />
                            </label>
                          ))}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                <Resumen fotos={fotos} origen={origen} tomaElegida={tomaElegida} borrador={borrador} casoId={casoId} tarea={tarea}
                  carga={cargaNum} agarre={agarre} postura={postura} onIr={irPaso} />
                <div className="lg:col-span-2"><FlujoAgente trabajando={trabajando} /></div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {error && <p role="alert" className="mt-6 rounded-lg border border-[var(--riesgo-muy-alto)] bg-sheet p-4 text-[14px]">{error}</p>}

        <div className="sticky bottom-0 z-20 mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-ink bg-vellum/95 py-4 backdrop-blur">
          <button type="button" className="boton-linea" disabled={paso === 0 || trabajando} onClick={() => irPaso(paso - 1)}>
            <ArrowLeft className="size-4" /> Anterior
          </button>
          <p className="hidden text-[14px] text-graphite md:block">
            {trabajando ? "Detectando pose y midiendo ángulos; suele tardar unos segundos."
              : paso === 2 && primerPendiente !== null ? `Falta completar el paso ${primerPendiente + 1}: ${TITULOS[primerPendiente].toLowerCase()}.`
              : auto ? `Capturando cada ${intervaloS} s.` : `Paso ${paso + 1} de 3`}
          </p>
          {paso < 2 ? (
            <button type="submit" className="boton-tinta">Siguiente: {TITULOS[paso + 1].toLowerCase()} <ArrowRight className="size-4" /></button>
          ) : (
            <ShimmerButton type="submit" disabled={!puedeAnalizar} background="var(--ink)" shimmerColor="#c8d0d8" borderRadius="10px"
              className="px-6 py-3 text-[15px] font-semibold disabled:opacity-40">
              {trabajando ? "Analizando…" : "Analizar postura"}
            </ShimmerButton>
          )}
        </div>
      </form>
    </div>
  )
}

function EstadoCamaras({ camaras, permiso, error, detectar }: ReturnType<typeof useCamaras>) {
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
            {error ?? (permiso === "concedido" ? camaras.map((c) => c.nombre).join(", ") || "Conecta una y vuelve a detectar." : "Asigna una cámara a cada vista y captura cada cierto tiempo.")}
          </p>
        </div>
      </div>
      <button type="button" className={permiso === "concedido" ? "boton-linea" : "boton-tinta"} onClick={() => void detectar()}>
        <RefreshCw className="size-4" /> {permiso === "concedido" ? "Volver a detectar" : "Detectar cámaras"}
      </button>
    </div>
  )
}

function Resumen({ fotos, origen, tomaElegida, borrador, casoId, tarea, carga, agarre, postura, onIr }: {
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
}) {
  const [urls, setUrls] = useState<Record<string, string>>({})
  useEffect(() => {
    const creadas = Object.fromEntries(Object.entries(fotos).filter(([, f]) => f).map(([v, f]) => [v, URL.createObjectURL(f!)]))
    setUrls(creadas)
    return () => Object.values(creadas).forEach(URL.revokeObjectURL)
  }, [fotos])
  return (
    <aside className="trazo-tinta self-start rounded-[12px] p-4" aria-label="Resumen antes de analizar">
      <div className="flex items-center justify-between">
        <h3 className="t-title text-[17px]">Se va a analizar</h3>
        <button type="button" className="text-[13px] text-ink-soft underline underline-offset-4 hover:text-ink" onClick={() => onIr(0)}>Cambiar fotos</button>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {VISTAS.map(({ vista, titulo }) => {
          const fuente = origen(vista)
          const src = fuente === "archivo" ? urls[vista] : fuente === "captura" && tomaElegida ? api.captura(borrador, tomaElegida.id, vista) : null
          return (
            <figure key={vista}>
              <div className="aspect-[4/3] overflow-hidden rounded-md bg-ink/5">
                {src ? <img src={src} alt={`Vista ${titulo}`} className="h-full w-full object-cover" /> : <span className="flex h-full items-center justify-center text-[12px] text-graphite">Sin foto</span>}
              </div>
              <figcaption className="mt-1 text-[12px] text-graphite">
                {titulo}{fuente === "captura" && tomaElegida ? `, toma ${hora(tomaElegida.fecha)}` : fuente === "archivo" ? ", archivo" : ""}
                {fuente === "captura" && tomaElegida?.privacidad?.[vista]?.rostros === 0 && <span className="block font-medium text-ink">Sin persona detectada</span>}
              </figcaption>
            </figure>
          )
        })}
      </div>
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[14px]">
        <dt className="text-graphite">Caso</dt><dd className="t-num truncate">{casoId}</dd>
        <dt className="text-graphite">Tarea</dt><dd>{etiquetaTarea(tarea)}</dd>
        <dt className="text-graphite">Carga</dt><dd>{carga} kg, agarre {agarre}</dd>
        <dt className="text-graphite">Postura</dt><dd>{postura === "de_pie" ? "De pie" : postura === "sentado" ? "Sentado" : "Alterna"}</dd>
      </dl>
      <button type="button" className="mt-3 text-[13px] text-ink-soft underline underline-offset-4 hover:text-ink" onClick={() => onIr(1)}>Cambiar tarea</button>
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
