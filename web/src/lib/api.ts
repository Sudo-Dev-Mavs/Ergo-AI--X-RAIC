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

export interface ResumenRiesgo {
  reba: number | null
  nivel_riesgo: string | null
  nivel_accion: number | null
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
      final: { L: number | null; R: number | null; reportado: number | null; lado: "L" | "R" | null }
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
    reduccion_puntos: number | null
    reduccion_pct: number | null
    recomendaciones_aplicadas: string[]
    nota: string
  }
  bloqueos: string[]
  bitacora_integra: boolean
  imagenes: Vista[]
  fotos: Vista[]
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

export const api = {
  casos: () => pedir<ResumenCaso[]>("/api/casos"),
  caso: (id: string) => pedir<EstadoCaso>(`/api/casos/${encodeURIComponent(id)}`),
  crear: (formulario: FormData) => pedir<EstadoCaso>("/api/casos", { method: "POST", body: formulario }),
  validar: (id: string, cuerpo: { usuario: string; accion: string; rec_id?: string; valores?: Record<string, string>; comentario?: string }) =>
    pedir<EstadoCaso>(`/api/casos/${encodeURIComponent(id)}/validacion`, json(cuerpo)),
  corregir: (id: string, cuerpo: { usuario: string; overrides: Record<string, number | null>; comentario?: string }) =>
    pedir<EstadoCaso>(`/api/casos/${encodeURIComponent(id)}/correcciones`, json(cuerpo)),
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
  captura: (borrador: string, toma: string, vista: Vista) =>
    `/api/capturas/${encodeURIComponent(borrador)}/${encodeURIComponent(toma)}/${vista}`,
}
