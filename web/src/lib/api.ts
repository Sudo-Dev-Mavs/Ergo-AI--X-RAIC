export type Jerarquia = "ingenieria" | "rediseno" | "administrativa"
export type EstadoRec = "propuesta" | "aprobada" | "rechazada" | "obsoleta"
export type TipoTarea = "levantamiento" | "transporte_con_auxiliar" | "transporte_sin_auxiliar" | "otro"
export type Vista = "frente" | "costado" | "aerea"

export interface ResumenCaso {
  caso_id: string
  tipo_tarea: TipoTarea
  carga_kg: number | null
  realizado_por: string | null
  fecha_analisis: string | null
  reba: number | null
  nivel_riesgo: string | null
  nivel_accion: number | null
  residual: number | null
  nivel_residual: string | null
  reba_rango?: RangoReba | null
  residual_rango?: RangoReba | null
  origen_residual?: "agente" | "especialista"
  estado_validacion?: "pendiente" | "aprobado" | "rechazado" | "modificado"
  por_validar: number
  recomendaciones: number
  estado_informe: "borrador" | "aprobado"
  pendientes_manuales: number
  miniatura: Vista | null
}

export interface Recomendacion {
  id: string
  factor: string
  problema: string
  solucion: string
  jerarquia: Jerarquia
  referencias: string[]
  efecto: Record<string, Record<string, unknown>>
  prioridad: string
  estado: EstadoRec
  responsable: string
  fecha_compromiso: string
  comentario: string
  origen: "agente" | "especialista"
  delta_reba: number | null
}

export interface EntradaBitacora {
  n: number
  fecha: string
  usuario: string
  accion: string
  rec_id: string | null
  cambios: Record<string, { antes: unknown; despues: unknown }>
  comentario: string
  hash: string
}

export interface Angulo {
  medida: string
  lado: "L" | "R" | null
  valor_deg: number | null
  valor_medido_deg?: number | null
  vista: Vista | "contexto"
  metodo?: string
  banderas: string[]
  motivo: string | null
  banda_reba?: number | null
  fuente?: string
  clave_override: string
}

/** Puntajes REBA posibles cuando falta un dato; `nivel` solo si todo el rango cae en el mismo nivel. */
export interface RangoReba {
  min: number
  max: number
  nivel: string | null
  nivel_accion: number | null
}

export interface ResumenRiesgo {
  reba: number | null
  nivel_riesgo: string | null
  nivel_accion: number | null
  rango?: RangoReba | null
  bandas: Record<string, number | null>
}

export interface EstadoCaso {
  resultado: {
    caso_id: string
    fecha_analisis?: string
    angulos: Angulo[]
    reba: {
      grupo_a: Record<string, number | null>
      grupo_b: Record<"L" | "R", Record<string, number | null>>
      actividad: number
      final: { L: number | null; R: number | null; reportado: number | null; lado: "L" | "R" | null; rango?: RangoReba | null }
      nivel_riesgo: string | null
      nivel_accion: number | null
    }
    contexto: Record<string, any>
    mediciones_reba: Record<string, number | null>
    pendientes_manuales: { medida: string; motivo?: string; lado?: string | null }[]
    tiempos_s?: { analisis_total: number }
    advertencias?: string[]
  }
  validacion: {
    estado_informe: "borrador" | "aprobado"
    aprobado_por: string | null
    aprobado_en: string | null
    generado_en?: string
    recomendaciones: Recomendacion[]
    bitacora: EntradaBitacora[]
  }
  residual: {
    inicial: ResumenRiesgo
    residual: ResumenRiesgo
    residual_agente?: ResumenRiesgo
    origen_residual?: "agente" | "especialista"
    reduccion_puntos: number | null
    reduccion_pct: number | null
    recomendaciones_aplicadas: string[]
    nota: string
  }
  bloqueos: string[]
  bitacora_integra: boolean
  /** firmada: cadena y HMAC verificados · sin_firma: cadena íntegra sin firma comprobable · alterada */
  bitacora_estado: "firmada" | "sin_firma" | "alterada"
  imagenes: Vista[]
  fotos: Vista[]
}

/** Compatibilidad con casos antiguos (otro esquema de recomendaciones / contexto ausente). */
export function normalizarEstadoCaso(bruto: EstadoCaso): EstadoCaso {
  const resultado = bruto.resultado ?? ({} as EstadoCaso["resultado"])
  const validacion = bruto.validacion ?? ({} as EstadoCaso["validacion"])
  const residual = bruto.residual ?? {
    inicial: { reba: null, nivel_riesgo: null, nivel_accion: null, bandas: {} },
    residual: { reba: null, nivel_riesgo: null, nivel_accion: null, bandas: {} },
    reduccion_puntos: null, reduccion_pct: null, recomendaciones_aplicadas: [], nota: "",
  }
  const recs = (validacion.recomendaciones ?? []).map((rec) => normalizarRecomendacion(rec as Recomendacion & Record<string, unknown>))
  const reba = resultado.reba ?? {
    grupo_a: {}, grupo_b: { L: {}, R: {} }, actividad: 0,
    final: { L: null, R: null, reportado: null, lado: null },
    nivel_riesgo: null, nivel_accion: null,
  }
  return {
    ...bruto,
    resultado: {
      ...resultado,
      contexto: resultado.contexto ?? {},
      angulos: resultado.angulos ?? [],
      mediciones_reba: resultado.mediciones_reba ?? {},
      pendientes_manuales: resultado.pendientes_manuales ?? [],
      reba: {
        ...reba,
        final: reba.final ?? { L: null, R: null, reportado: null, lado: null },
        grupo_b: reba.grupo_b ?? { L: {}, R: {} },
      },
    },
    validacion: {
      estado_informe: validacion.estado_informe ?? "borrador",
      aprobado_por: validacion.aprobado_por ?? null,
      aprobado_en: validacion.aprobado_en ?? null,
      generado_en: validacion.generado_en,
      recomendaciones: recs,
      bitacora: validacion.bitacora ?? [],
    },
    residual: {
      ...residual,
      inicial: residual.inicial ?? { reba: null, nivel_riesgo: null, nivel_accion: null, bandas: {} },
      residual: residual.residual ?? { reba: null, nivel_riesgo: null, nivel_accion: null, bandas: {} },
      recomendaciones_aplicadas: residual.recomendaciones_aplicadas ?? [],
      nota: residual.nota ?? "",
    },
    bloqueos: bruto.bloqueos ?? [],
    bitacora_integra: bruto.bitacora_integra ?? true,
    bitacora_estado: bruto.bitacora_estado ?? (bruto.bitacora_integra === false ? "alterada" : "sin_firma"),
    imagenes: bruto.imagenes ?? [],
    fotos: bruto.fotos ?? [],
  }
}

function normalizarRecomendacion(rec: Recomendacion & Record<string, unknown>): Recomendacion {
  const jerarquiaCruda = String(rec.jerarquia ?? rec.tipo_control ?? "rediseno")
  const jerarquia = (["ingenieria", "rediseno", "administrativa"].includes(jerarquiaCruda)
    ? jerarquiaCruda
    : "rediseno") as Jerarquia
  const refs = Array.isArray(rec.referencias)
    ? rec.referencias
    : typeof rec.fuente === "string" && rec.fuente
      ? [rec.fuente]
      : []
  return {
    id: String(rec.id ?? "REC"),
    factor: String(rec.factor ?? rec.segmento ?? "general"),
    problema: String(rec.problema ?? ""),
    solucion: String(rec.solucion ?? ""),
    jerarquia,
    referencias: refs,
    efecto: (rec.efecto as Recomendacion["efecto"]) ?? {},
    prioridad: String(rec.prioridad ?? "normal"),
    estado: (["propuesta", "aprobada", "rechazada", "obsoleta"].includes(String(rec.estado))
      ? rec.estado
      : "propuesta") as EstadoRec,
    responsable: String(rec.responsable ?? ""),
    fecha_compromiso: String(rec.fecha_compromiso ?? ""),
    comentario: String(rec.comentario ?? ""),
    origen: rec.origen === "especialista" ? "especialista" : "agente",
    delta_reba: typeof rec.delta_reba === "number" ? rec.delta_reba : null,
  }
}

export interface PrivacidadVista {
  rostros: number | null
  metodo: "pose" | "rostro" | null
}

export interface Toma {
  id: string
  fecha: string
  vistas: Vista[]
  privacidad?: Partial<Record<Vista, PrivacidadVista>>
}

export interface ListaTomas {
  tomas: Toma[]
  max_tomas?: number
  retencion_horas?: number
}

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string) {
    super(mensaje)
  }
}

async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(url, init)
  } catch {
    throw new ErrorApi(0, "No hay conexión con el servidor local de ErgoAI. Verifica que `ergoai-gui` siga abierto.")
  }
  if (!respuesta.ok) {
    let detalle = respuesta.statusText
    try {
      const cuerpo = await respuesta.json()
      detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : cuerpo.detail?.[0]?.msg ?? detalle
    } catch {
      /* respuesta sin JSON */
    }
    throw new ErrorApi(respuesta.status, detalle)
  }
  return respuesta.json() as Promise<T>
}

const json = (cuerpo: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(cuerpo),
})

async function pedirCaso(url: string, init?: RequestInit): Promise<EstadoCaso> {
  return normalizarEstadoCaso(await pedir<EstadoCaso>(url, init))
}

export const api = {
  casos: () => pedir<ResumenCaso[]>("/api/casos"),
  caso: (id: string) => pedirCaso(`/api/casos/${encodeURIComponent(id)}`),
  /** Borra fotos, análisis e informe del caso en este equipo. */
  eliminarCaso: (id: string, usuario: string, confirmacion: string) =>
    pedir<{ ok: boolean; caso_id: string; eliminado_por: string }>(
      `/api/casos/${encodeURIComponent(id)}/eliminar`,
      json({ usuario, confirmacion }),
    ),
  crear: (formulario: FormData) => pedirCaso("/api/casos", { method: "POST", body: formulario }),
  /** Sugiere postura/ajustes REBA desde las fotos (sin crear el caso). */
  proponerContexto: (formulario: FormData) =>
    pedir<{
      ok: boolean
      motivos: string[]
      advertencias: string[]
      vistas_detectadas?: string[]
      sugerencias: {
        postura?: string | null
        tipo_trabajo?: string | null
        fuerza_brusca?: boolean
        actividad?: {
          estatica_mas_1min?: boolean
          repetitiva_mas_4_por_min?: boolean
          cambios_bruscos_o_base_inestable?: boolean
        }
        hombro_elevado?: { izquierdo?: boolean; derecho?: boolean }
        brazo_apoyado?: { izquierdo?: boolean; derecho?: boolean }
        muneca_desviada_o_torcida?: { izquierdo?: boolean; derecho?: boolean }
      }
    }>("/api/proponer-contexto", { method: "POST", body: formulario }),
  /** Clasifica fotos/capturas y dice a qué vista va cada una. */
  clasificarVistas: (formulario: FormData) =>
    pedir<{
      ok: boolean
      motivos: string[]
      asignaciones: { id: string; vista: Vista; confianza: number; nombre: string; detectado: boolean }[]
      toma_reordenada?: string[]
    }>("/api/clasificar-vistas", { method: "POST", body: formulario }),
  validar: (id: string, cuerpo: { usuario: string; accion: string; rec_id?: string; valores?: Record<string, string>; comentario?: string }) =>
    pedirCaso(`/api/casos/${encodeURIComponent(id)}/validacion`, json(cuerpo)),
  ajustarResidual: (id: string, usuario: string, puntaje: number, comentario: string) =>
    pedirCaso(`/api/casos/${encodeURIComponent(id)}/validacion`, json({
      usuario, accion: "ajustar_residual", valores: { riesgo_residual_proyectado: String(puntaje) }, comentario,
    })),
  limpiarResidual: (id: string, usuario: string, comentario = "") =>
    pedirCaso(`/api/casos/${encodeURIComponent(id)}/validacion`, json({ usuario, accion: "limpiar_residual", comentario })),
  corregir: (id: string, cuerpo: { usuario: string; overrides: Record<string, number | null>; comentario?: string }) =>
    pedirCaso(`/api/casos/${encodeURIComponent(id)}/correcciones`, json(cuerpo)),
  archivo: (id: string, nombre: string, version?: string) =>
    `/api/casos/${encodeURIComponent(id)}/archivos/${nombre}${version ? `?v=${encodeURIComponent(version)}` : ""}`,
  foto: (id: string, vista: Vista) => `/api/casos/${encodeURIComponent(id)}/fotos/${vista}`,
  tomas: (borrador: string) => pedir<ListaTomas>(`/api/capturas/${encodeURIComponent(borrador)}`),
  capturar: (borrador: string, vistas: Partial<Record<Vista, Blob>>) => {
    const formulario = new FormData()
    for (const [vista, imagen] of Object.entries(vistas)) if (imagen) formulario.set(vista, imagen, `${vista}.jpg`)
    return pedir<{ toma: Toma; tomas: Toma[] }>(`/api/capturas/${encodeURIComponent(borrador)}`, { method: "POST", body: formulario })
  },
  descartarTomas: (borrador: string) => pedir<ListaTomas>(`/api/capturas/${encodeURIComponent(borrador)}`, { method: "DELETE" }),
  captura: (borrador: string, toma: string, vista: Vista, bust?: number | string) =>
    `/api/capturas/${encodeURIComponent(borrador)}/${encodeURIComponent(toma)}/${vista}${bust != null ? `?v=${bust}` : ""}`,
}
