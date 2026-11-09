/** JPEG/PNG aceptados por el backend de ErgoAI. */

const TIPO_OK = /^(image\/jpeg|image\/jpg|image\/png)$/i
const EXT_OK = /\.(jpe?g|png)$/i

export function esImagenErgo(archivo: File): boolean {
  if (TIPO_OK.test(archivo.type)) return true
  // Windows a veces arrastra con type vacío; caemos a la extensión.
  if (!archivo.type && EXT_OK.test(archivo.name)) return true
  if (EXT_OK.test(archivo.name) && archivo.type.startsWith("image/")) return true
  return false
}

/** Normaliza un Blob/File del portapapeles o del explorador a File JPEG/PNG. */
export async function normalizarImagenErgo(entrada: Blob, nombreHint = "pegado.png"): Promise<File | null> {
  const tipo = (entrada.type || "").toLowerCase()
  if (TIPO_OK.test(tipo) || (!tipo && entrada instanceof File && EXT_OK.test(entrada.name))) {
    const nombre = entrada instanceof File && entrada.name ? entrada.name : nombreHint
    const mime = tipo === "image/jpg" ? "image/jpeg" : (tipo || (/\.png$/i.test(nombre) ? "image/png" : "image/jpeg"))
    return new File([entrada], nombre, { type: mime })
  }
  if (!tipo.startsWith("image/") || tipo.includes("svg")) return null

  // WebP/BMP/etc. del portapapeles → PNG para el API.
  try {
    const bitmap = await createImageBitmap(entrada)
    const canvas = document.createElement("canvas")
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    const ctx = canvas.getContext("2d")
    if (!ctx) return null
    ctx.drawImage(bitmap, 0, 0)
    bitmap.close()
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"))
    if (!blob) return null
    return new File([blob], nombreHint.replace(/\.[^.]+$/, "") + ".png", { type: "image/png" })
  } catch {
    return null
  }
}

/** Extrae la primera imagen del portapapeles (Ctrl+V / pegar). */
export async function imagenDesdeClipboard(data: DataTransfer | null): Promise<File | null> {
  if (!data) return null
  const items = [...data.items]
  for (const item of items) {
    if (item.kind === "file" && item.type.startsWith("image/")) {
      const bruto = item.getAsFile()
      if (!bruto) continue
      const ok = await normalizarImagenErgo(bruto, `pegado-${Date.now()}.png`)
      if (ok) return ok
    }
  }
  const archivos = [...data.files].filter((f) => f.type.startsWith("image/") || esImagenErgo(f))
  if (archivos[0]) return normalizarImagenErgo(archivos[0], archivos[0].name || `pegado-${Date.now()}.png`)
  return null
}

export function filtrarImagenesErgo(lista: FileList | File[]): File[] {
  return [...lista].filter(esImagenErgo)
}
