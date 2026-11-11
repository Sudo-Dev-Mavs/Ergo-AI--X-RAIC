import { ArrowLeft, Download, ExternalLink, Printer, Trash2 } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"

import { DirectionAwareTabs } from "@/components/cult/direction-aware-tabs"
import { PanelBitacora } from "@/components/ergo/bitacora"
import { ComparadorResidual } from "@/components/ergo/ComparadorResidual"
import { useDialogo } from "@/components/ergo/DialogoConfirmar"
import { ImpactoReba } from "@/components/ergo/ImpactoReba"
import { Goniometro } from "@/components/ergo/goniometro"
import { InfoTooltip, TituloConAyuda } from "@/components/ergo/InfoTooltip"
import { PanelPostura } from "@/components/ergo/postura"
import { PanelRecomendaciones } from "@/components/ergo/recomendaciones"
import { VisorFoto } from "@/components/ergo/VisorFoto"
import { api, type EstadoCaso, type Vista } from "@/lib/api"
import { avisar, ir, useEspecialista } from "@/lib/app"
import { accionRiesgo, colorRiesgo, etiquetaTarea, fechaCorta, textoRango } from "@/lib/dominio"
import { usePreferencias } from "@/lib/preferencias"
import { useDatos } from "@/lib/useDatos"
import { cn } from "@/lib/utils"

const MENSAJE_ACCION: Record<string, string> = {
  aprobar: "Recomendación aprobada", rechazar: "Recomendación rechazada", reabrir: "Recomendación devuelta a propuesta",
  editar: "Cambios guardados", agregar: "Recomendación agregada", aprobar_informe: "Informe aprobado",
}

export function CasoPage({ id }: { id: string }) {
  const { datos: estado, setDatos, error } = useDatos(() => api.caso(id), [id])
  const { pedirFirma } = useEspecialista()
  const { pedir } = useDialogo()
  const [ocupado, setOcupado] = useState(false)

  async function eliminarCaso() {
    const usuario = pedirFirma()
    if (!usuario) return
    const r = await pedir({
      titulo: `¿Eliminar el caso «${id}»?`,
      detalle: "Se borran de este equipo las fotos, el análisis REBA, la validación y el informe. No se puede deshacer.",
      confirmarEtiqueta: "Eliminar caso",
      tono: "peligro",
      motivo: {
        etiqueta: `Escribe ${id} para confirmar`,
        placeholder: id,
        obligatorio: true,
      },
    })
    if (!r.ok) return
    if (r.motivo !== id) {
      avisar({ titulo: "Confirmación incorrecta", detalle: `Debes escribir exactamente «${id}».`, tipo: "error" })
      return
    }
    setOcupado(true)
    try {
      await api.eliminarCaso(id, usuario, r.motivo)
      avisar({ titulo: "Caso eliminado", detalle: `«${id}» ya no está en este equipo.` })
      ir({ nombre: "casos" })
    } catch (e) {
      avisar({ titulo: "No se eliminó el caso", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
    } finally {
      setOcupado(false)
    }
  }

  async function accion(nombre: string, recId?: string, valores?: Record<string, string>, comentario?: string) {
    const usuario = pedirFirma()
    if (!usuario) return false
    setOcupado(true)
    try {
      setDatos(await api.validar(id, { usuario, accion: nombre, rec_id: recId, valores, comentario }))
      avisar({ titulo: MENSAJE_ACCION[nombre] ?? "Cambio registrado", detalle: "Quedó firmado en la bitácora." })
      return true
    } catch (e) {
      avisar({ titulo: "No se registró el cambio", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
      return false
    } finally {
      setOcupado(false)
    }
  }

  async function corregir(overrides: Record<string, number | null>, comentario: string) {
    const usuario = pedirFirma()
    if (!usuario) return false
    setOcupado(true)
    try {
      const nuevo = await api.corregir(id, { usuario, overrides, comentario })
      setDatos(nuevo)
      avisar({ titulo: "REBA recalculado", detalle: `Ahora ${nuevo.resultado.reba.final.reportado ?? "pendiente"} (${nuevo.resultado.reba.nivel_riesgo ?? "pendiente"}). La corrección quedó en la bitácora.` })
      return true
    } catch (e) {
      avisar({ titulo: "No se pudo recalcular", detalle: e instanceof Error ? e.message : String(e), tipo: "error" })
      return false
    } finally {
      setOcupado(false)
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-[1180px]">
        <a href="#/" className="inline-flex items-center gap-1.5 text-[14px] text-ink-soft hover:text-ink"><ArrowLeft className="size-4" /> Inicio</a>
        <h1 className="t-display mt-6 text-[40px]">No se pudo abrir «{id}»</h1>
        <p className="mt-3 text-[16px] text-ink-soft">{error}</p>
      </div>
    )
  }
  if (!estado) return <p className="text-graphite">Cargando caso…</p>

  const { resultado, validacion, residual } = estado
  const reba = resultado.reba
  const ctx = resultado.contexto ?? {}
  const porValidar = validacion.recomendaciones.filter((rec) => rec.estado === "propuesta").length
  const version = encodeURIComponent(validacion.bitacora.at(-1)?.hash.slice(0, 8) ?? resultado.fecha_analisis ?? "")

  const pestanas = [
    { id: 0, label: <>Recomendaciones {porValidar > 0 && <span className="t-num rounded-full bg-[var(--riesgo-alto)] px-1.5 text-[12px] text-white">{porValidar}</span>}</>, content: <PanelRecomendaciones estado={estado} accion={accion} ocupado={ocupado} /> },
    { id: 1, label: "Postura medida", content: <PanelPostura estado={estado} ocupado={ocupado} onCorregir={corregir} /> },
    { id: 2, label: "Bitácora", content: <PanelBitacora estado={estado} /> },
    { id: 3, label: "Informe", content: <PanelInforme id={id} estado={estado} version={version} /> },
  ]

  return (
    <div className="mx-auto max-w-[1180px]">
      <a href="#/" className="inline-flex items-center gap-1.5 text-[14px] text-ink-soft hover:text-ink"><ArrowLeft className="size-4" /> Inicio</a>
      <header className="mt-4 flex flex-wrap items-end justify-between gap-6 border-b border-ink pb-6">
        <div className="min-w-0">
          <h1 className="t-display break-words text-[40px] sm:text-[56px]">{resultado.caso_id}</h1>
          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-[14px]">
            <Dato termino="Tarea" valor={etiquetaTarea(ctx.tipo_tarea)} />
            <Dato termino="Carga" valor={`${ctx.carga_kg ?? 0} kg, agarre ${ctx.agarre ?? "—"}`} />
            <Dato termino="Postura" valor={ctx.postura === "de_pie" ? "De pie" : ctx.postura === "sentado" ? "Sentado" : "Alterna"} />
            <Dato termino="Analizado" valor={`${fechaCorta(resultado.fecha_analisis)}${resultado.tiempos_s ? `, en ${resultado.tiempos_s.analisis_total.toFixed(1)} s` : ""}`} />
            {ctx.realizado_por && <Dato termino="Por" valor={ctx.realizado_por} />}
          </dl>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("rounded-lg px-3 py-1.5 text-[14px] font-medium", validacion.estado_informe === "aprobado" ? "trazo-tinta" : "trazo-lapiz text-ink-soft")}>
            {validacion.estado_informe === "aprobado" ? `Informe aprobado por ${validacion.aprobado_por}` : "Informe en borrador"}
          </span>
          <button
            type="button"
            className="boton-linea border-red-300 text-red-800 hover:border-red-400 hover:bg-red-50"
            disabled={ocupado}
            onClick={() => void eliminarCaso()}
            title="Borrar fotos, análisis e informe de este caso"
          >
            <Trash2 className="size-4" /> Eliminar caso
          </button>
        </div>
      </header>

      <p className="mt-5 rounded-lg border border-rule-soft bg-slate-50 px-3.5 py-2.5 text-[13px] leading-snug text-ink-soft">
        <span className="font-medium text-jabil">Nota:</span>{" "}
        Los valores <TituloConAyuda clave="reba" className="inline-flex">REBA</TituloConAyuda> miden la postura del 1 al 15.
        El <TituloConAyuda clave="residual" className="inline-flex">riesgo esperado tras mejoras</TituloConAyuda> muestra cómo bajará el peligro
        al aplicar las recomendaciones de <TituloConAyuda clave="nom036" className="inline-flex">NOM-036</TituloConAyuda>.
      </p>

      <section className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,1fr)]">
        <Muestra id={id} estado={estado} version={version} />
        <div className="flex flex-col">
          <Goniometro inicial={reba.final.reportado} residual={residual.residual.reba} nivel={reba.nivel_riesgo} nivelResidual={residual.residual.nivel_riesgo} tamano={340} className="mx-auto" />
          <p className="text-center text-[15px] text-ink-soft">
            {reba.nivel_riesgo
              ? <>Estatus: {accionRiesgo(reba.nivel_riesgo)}</>
              : reba.final.rango
                ? `Falta un dato: el REBA queda entre ${reba.final.rango.min} y ${reba.final.rango.max}${reba.final.rango.nivel ? `, nivel ${reba.final.rango.nivel.toLowerCase()} en cualquier caso` : ""}. Complétalo en Postura medida.`
                : "Faltan datos para el REBA: revisa la pestaña Postura medida."}
          </p>
          <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-[12px] border border-rule bg-rule">
            {residual.residual.reba == null && residual.residual.rango ? (
              <Cifra
                titulo={<>Tras mejoras <InfoTooltip clave="residual" /></>}
                valor={textoRango(residual.residual.rango)}
                nota={residual.residual.rango.nivel ? `${residual.residual.rango.nivel}, estimado` : "Rango estimado"}
                color={colorRiesgo(residual.residual.rango.nivel)}
              />
            ) : (
              <Cifra
                titulo={<>Tras mejoras <InfoTooltip clave="residual" /></>}
                valor={residual.residual.reba}
                nota={residual.residual.nivel_riesgo ? `${residual.residual.nivel_riesgo}${residual.residual.reba != null ? ` (${residual.residual.reba})` : ""}` : "Pendiente"}
                color={colorRiesgo(residual.residual.nivel_riesgo)}
              />
            )}
            <Cifra titulo="Reducción" valor={residual.reduccion_puntos == null ? null : residual.reduccion_puntos > 0 ? `−${residual.reduccion_puntos}` : "0"}
              nota={residual.reduccion_pct == null ? "Sin datos suficientes"
                : `${residual.reduccion_pct} % con ${residual.recomendaciones_aplicadas.length} ${residual.recomendaciones_aplicadas.length === 1 ? "control" : "controles"}`} />
            <Cifra titulo="Lado reportado" valor={reba.final.lado === "L" ? "Izq." : reba.final.lado === "R" ? "Der." : null} nota={`Izq. ${reba.final.L ?? "—"}, der. ${reba.final.R ?? "—"}`} />
            <Cifra
              titulo={<>Grupo A y B <InfoTooltip clave="grupoAB" /></>}
              valor={reba.grupo_a.puntaje_a != null ? `${reba.grupo_a.puntaje_a} / ${reba.final.lado ? reba.grupo_b[reba.final.lado].puntaje_b ?? "—" : "—"}` : null}
              nota={`Actividad +${reba.actividad}`}
            />
          </div>
          <p className="mt-3 text-[13px] leading-snug text-graphite">
            Aguja sólida: REBA medido hoy. Aguja punteada: riesgo esperado tras aplicar los controles no rechazados.
          </p>
        </div>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <ComparadorResidual
          inicial={reba.final.reportado}
          residual={residual.residual.reba}
          rangoInicial={reba.final.rango}
          rangoResidual={residual.residual.rango}
          origen={residual.origen_residual ?? "agente"}
        />
        <div className="hoja flex flex-col justify-center gap-3 p-5">
          <p className="text-[13px] font-semibold tracking-[0.08em] text-jabil-cyan uppercase">Siguiente paso</p>
          <p className="text-[15px] text-ink-soft">
            {validacion.estado_informe === "aprobado"
              ? "Informe aprobado. Descarga o imprime desde la pestaña Informe."
              : porValidar > 0
                ? `Decide las ${porValidar} propuestas en Recomendaciones. El botón de acción de piso se habilita al completar.`
                : estado.bloqueos.length > 0
                  ? estado.bloqueos[0]
                  : "Listo: aprueba el informe para generar la acción de piso."}
          </p>
        </div>
      </section>

      <section className="mt-12">
        <DirectionAwareTabs tabs={pestanas} />
      </section>
    </div>
  )
}

function Dato({ termino, valor }: { termino: string; valor: string }) {
  return (
    <div>
      <dt className="text-[13px] text-graphite">{termino}</dt>
      <dd className="font-medium">{valor}</dd>
    </div>
  )
}

function Cifra({ titulo, valor, nota, color }: { titulo: ReactNode; valor: string | number | null; nota: string; color?: string }) {
  return (
    <div className="bg-sheet px-4 py-3">
      <p className="flex flex-wrap items-center gap-1 text-[13px] text-graphite">{titulo}</p>
      <p className="t-num text-[30px] leading-tight" style={color ? { color } : undefined}>{valor ?? "—"}</p>
      <p className="text-[13px] text-ink-soft">{nota}</p>
    </div>
  )
}

function Muestra({ id, estado, version }: { id: string; estado: EstadoCaso; version: string }) {
  const { preferencias } = usePreferencias()
  const vistas = (["costado", "frente", "aerea"] as Vista[]).filter((v) => estado.imagenes.includes(v) || estado.fotos.includes(v))
  const [vista, setVista] = useState<Vista>(vistas[0] ?? "costado")
  const [original, setOriginal] = useState(preferencias.fotoInicial === "original")
  useEffect(() => {
    setOriginal(preferencias.fotoInicial === "original")
  }, [preferencias.fotoInicial, id])
  const anotada = estado.imagenes.includes(vista)
  const src = vistas.length
    ? (original || !anotada ? api.foto(id, vista) : api.archivo(id, `${vista}_angulos.png`, version))
    : null

  return (
    <figure className="min-w-0">
      <VisorFoto
        src={src}
        alt={`Vista ${vista} ${original ? "original" : "con ángulos medidos"}`}
        vacio="Sin imágenes para este caso."
        barraExtra={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex gap-1" role="tablist" aria-label="Vista">
              {vistas.map((v) => (
                <button key={v} type="button" role="tab" aria-selected={v === vista} onClick={() => setVista(v)}
                  className={cn("rounded-md px-3 py-1.5 text-[14px] font-medium capitalize", v === vista ? "bg-jabil text-white" : "text-ink-soft hover:bg-rule-soft")}>
                  {v === "aerea" ? "Aérea" : v}
                </button>
              ))}
            </div>
            {anotada && estado.fotos.includes(vista) && (
              <label className="flex items-center gap-2 text-[14px] text-ink-soft">
                <input type="checkbox" checked={original} onChange={(e) => setOriginal(e.target.checked)} className="size-4 accent-[var(--jabil)]" />
                Original
              </label>
            )}
          </div>
        }
      />
    </figure>
  )
}

function PanelInforme({ id, estado, version }: { id: string; estado: EstadoCaso; version: string }) {
  const marco = useRef<HTMLIFrameElement>(null)
  const url = api.archivo(id, "informe.html", version)
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-[64ch] text-[14px] text-ink-soft">
          {estado.validacion.estado_informe === "aprobado"
            ? "Versión aprobada. Imprímela a PDF o descarga las acciones para el formato 16-PE80-6500-00014."
            : "Vista previa del borrador. Se marca como BORRADOR hasta que apruebes el informe."}
        </p>
        <div className="flex flex-wrap gap-2">
          <a className="boton-linea" href={api.archivo(id, "acciones_00014.csv", version)} download><Download className="size-4" /> Acciones CSV</a>
          <a className="boton-linea" href={url} target="_blank" rel="noreferrer"><ExternalLink className="size-4" /> Abrir aparte</a>
          <button className="boton-tinta" onClick={() => marco.current?.contentWindow?.print()}><Printer className="size-4" /> Imprimir o PDF</button>
        </div>
      </div>
      <iframe ref={marco} src={url} title="Informe del estudio ergonómico" className="h-[78vh] w-full rounded-[12px] border border-rule bg-white" />
    </div>
  )
}
