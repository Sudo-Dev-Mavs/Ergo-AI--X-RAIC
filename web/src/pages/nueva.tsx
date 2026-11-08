import { useState, type ReactNode } from "react"

import { HaloSegmented } from "@/components/cult/halo-segmented"
import { HaloSwitch } from "@/components/cult/halo-switch"
import { FlujoAgente } from "@/components/ergo/flujo-agente"
import { VisorFoto } from "@/components/ergo/visor-foto"
import { ShimmerButton } from "@/components/magicui/shimmer-button"
import { ErrorApi, api, type TipoTarea, type Vista } from "@/lib/api"
import { avisar, ir, useEspecialista } from "@/lib/app"
import { TAREAS } from "@/lib/dominio"

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

function sugerirId() {
  const hoy = new Date()
  return `caso-${hoy.getFullYear()}${String(hoy.getMonth() + 1).padStart(2, "0")}${String(hoy.getDate()).padStart(2, "0")}-${String(hoy.getHours()).padStart(2, "0")}${String(hoy.getMinutes()).padStart(2, "0")}`
}

export function NuevaPage() {
  const { nombre } = useEspecialista()
  const [casoId, setCasoId] = useState(sugerirId)
  const [fotos, setFotos] = useState<Record<Vista, File | null>>({ costado: null, frente: null, aerea: null })
  const [tarea, setTarea] = useState<TipoTarea>("levantamiento")
  const [carga, setCarga] = useState("0")
  const [agarre, setAgarre] = useState("bueno")
  const [postura, setPostura] = useState("de_pie")
  const [trabajo, setTrabajo] = useState("ligero")
  const [orientacion, setOrientacion] = useState("auto")
  const [ajustes, setAjustes] = useState<Record<string, boolean>>({})
  const [lados, setLados] = useState<Record<string, Record<Lado, boolean>>>({})
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const cargaNum = Number(carga.replace(",", "."))
  const hayFotos = Object.values(fotos).some(Boolean)
  const idValido = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(casoId)
  const puedeAnalizar = hayFotos && idValido && Number.isFinite(cargaNum) && cargaNum >= 0 && !trabajando

  async function analizar(reemplazar = false) {
    setError(null)
    setTrabajando(true)
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
    for (const [vista, archivo] of Object.entries(fotos)) if (archivo) formulario.set(vista, archivo)
    try {
      const estado = await api.crear(formulario)
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

  return (
    <div className="mx-auto max-w-[1180px]">
      <header className="border-b border-ink pb-6">
        <h1 className="t-display text-[44px] sm:text-[56px]">Nueva evaluación</h1>
        <p className="mt-3 max-w-[64ch] text-[16px] text-ink-soft">
          Sube fotos de la estación sin rostros. El análisis corre en este equipo y deja las recomendaciones como propuesta hasta que las valides.
        </p>
      </header>

      <form className="mt-8 grid min-w-0 gap-x-12 gap-y-10 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]" onSubmit={(e) => { e.preventDefault(); if (puedeAnalizar) void analizar() }}>
        <Seccion numero={1} titulo="Fotografías" detalle="Costado y frente bastan para un REBA completo; la aérea agrega la torsión del tronco. Sin la de frente, piernas y abducción quedan pendientes.">
          <div className="grid grid-cols-3 gap-2 sm:gap-4">
            {VISTAS.map(({ vista, titulo, ayuda }) => (
              <VisorFoto key={vista} titulo={titulo} ayuda={ayuda} principal={vista === "costado"} archivo={fotos[vista]}
                onArchivo={(archivo) => setFotos((previas) => ({ ...previas, [vista]: archivo }))} />
            ))}
          </div>
          <Campo etiqueta="El operador mira hacia" className="mt-6">
            <HaloSegmented className="overflow-x-auto" translucent={false} value={orientacion} onValueChange={setOrientacion}
              items={[{ value: "auto", label: "Detectar" }, { value: "derecha", label: "Derecha" }, { value: "izquierda", label: "Izquierda" }]} />
          </Campo>
        </Seccion>

        <div className="space-y-10">
          <Seccion numero={2} titulo="Tarea" detalle="Define qué controles de la NOM-036-1 aplican.">
            <Campo etiqueta="Identificador del caso">
              <input className="campo t-num text-[17px]" value={casoId} onChange={(e) => setCasoId(e.target.value.trim())} aria-invalid={!idValido} />
              {!idValido && <p className="mt-1 text-[13px] text-[var(--riesgo-muy-alto)]">Usa letras, números, punto, guion o guion bajo.</p>}
            </Campo>
            <Campo etiqueta="Tipo de tarea">
              <HaloSegmented className="overflow-x-auto" translucent={false} value={tarea} onValueChange={(v) => setTarea(v as TipoTarea)}
                items={TAREAS.map((t) => ({ value: t.valor, label: t.corta }))} />
            </Campo>
            <div className="flex flex-wrap gap-x-4 gap-y-4">
              <Campo etiqueta="Carga (kg)" className="w-[120px]">
                <input className="campo t-num text-[17px]" inputMode="decimal" value={carga} onChange={(e) => setCarga(e.target.value)} />
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
          </Seccion>

          <Seccion numero={3} titulo="Lo que la foto no muestra" detalle="Ajustes REBA que se observan en piso. Si no aplican, déjalos apagados.">
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
          </Seccion>
        </div>

        <div className="xl:col-span-2">
          <FlujoAgente trabajando={trabajando} />
          {error && <p role="alert" className="mt-4 rounded-lg border border-[var(--riesgo-muy-alto)] bg-sheet p-4 text-[14px]">{error}</p>}
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <ShimmerButton type="submit" disabled={!puedeAnalizar} background="var(--ink)" shimmerColor="#c8d0d8" borderRadius="10px"
              className="px-6 py-3 text-[15px] font-semibold disabled:opacity-40">
              {trabajando ? "Analizando…" : "Analizar postura"}
            </ShimmerButton>
            <p className="text-[14px] text-graphite">
              {!hayFotos ? "Agrega al menos una fotografía para analizar." : trabajando ? "Detectando pose y midiendo ángulos; suele tardar unos segundos." : "Las recomendaciones quedarán como propuesta hasta que las valides."}
            </p>
          </div>
        </div>
      </form>
    </div>
  )
}

function Seccion({ numero, titulo, detalle, children }: { numero: number; titulo: string; detalle: string; children: ReactNode }) {
  return (
    <section>
      <div className="mb-5 flex gap-4">
        <span className="t-num text-[28px] leading-none text-graphite">{numero}</span>
        <div>
          <h2 className="t-title text-[22px]">{titulo}</h2>
          <p className="mt-1 max-w-[56ch] text-[14px] text-graphite">{detalle}</p>
        </div>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
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
