"""Interfaz de escritorio local para la beta de ErgoAI."""

from __future__ import annotations

import argparse
import json
import shutil
import threading
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from typing import Any

from PIL import Image, ImageTk

from .cli import ejecutar_evaluar, imagenes_de_vista


class AplicacionErgoAI:
    """Ventana local para preparar, ejecutar y consultar una evaluación REBA."""

    def __init__(self, raiz: Path, caso_inicial: Path | None = None) -> None:
        self.raiz = raiz
        self.ventana = Tk()
        self.ventana.title("ErgoAI · Beta local")
        self.ventana.minsize(920, 700)
        self.archivos: dict[str, StringVar] = {vista: StringVar() for vista in ("frente", "costado", "aerea")}
        self.caso_id = StringVar(value=caso_inicial.name if caso_inicial else "caso01")
        self.carga_kg = StringVar(value="0")
        self.agarre = StringVar(value="bueno")
        self.postura = StringVar(value="de_pie")
        self.orientacion = StringVar(value="auto")
        self.estatica = BooleanVar(value=False)
        self.repetitiva = BooleanVar(value=False)
        self.inestable = BooleanVar(value=False)
        self.estado = StringVar(value="Selecciona al menos una fotografía para comenzar.")
        self._imagen_mostrada: ImageTk.PhotoImage | None = None
        self._construir()
        if caso_inicial:
            self._cargar_caso(caso_inicial)

    def _construir(self) -> None:
        cuaderno = ttk.Notebook(self.ventana)
        cuaderno.pack(fill="both", expand=True, padx=14, pady=14)
        entrada = ttk.Frame(cuaderno, padding=16)
        resultado = ttk.Frame(cuaderno, padding=16)
        cuaderno.add(entrada, text="Nueva evaluación")
        cuaderno.add(resultado, text="Resultado")
        self.panel_resultado = resultado

        ttk.Label(entrada, text="ErgoAI", font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(entrada, text="Beta local · las imágenes no salen de este equipo", foreground="#396a45").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))
        marco_caso = ttk.LabelFrame(entrada, text="Caso", padding=12)
        marco_caso.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        ttk.Label(marco_caso, text="Identificador:").grid(row=0, column=0, sticky="w")
        ttk.Entry(marco_caso, textvariable=self.caso_id, width=30).grid(row=0, column=1, sticky="w", padx=8)

        marco_fotos = ttk.LabelFrame(entrada, text="Fotografías (frente, costado y/o aérea)", padding=12)
        marco_fotos.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)
        for fila, vista in enumerate(("frente", "costado", "aerea")):
            ttk.Label(marco_fotos, text=f"{vista.capitalize()}:").grid(row=fila, column=0, sticky="w", pady=3)
            ttk.Entry(marco_fotos, textvariable=self.archivos[vista], width=75).grid(row=fila, column=1, sticky="ew", padx=8)
            ttk.Button(marco_fotos, text="Elegir…", command=lambda actual=vista: self._elegir_foto(actual)).grid(row=fila, column=2)
        marco_fotos.columnconfigure(1, weight=1)

        marco_contexto = ttk.LabelFrame(entrada, text="Contexto de la tarea", padding=12)
        marco_contexto.grid(row=4, column=0, columnspan=3, sticky="ew", pady=5)
        ttk.Label(marco_contexto, text="Postura:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(marco_contexto, textvariable=self.postura, values=("de_pie", "sentado", "alternada"), state="readonly", width=15).grid(row=0, column=1, sticky="w", padx=(6, 18))
        ttk.Label(marco_contexto, text="Carga (kg):").grid(row=0, column=2, sticky="w")
        ttk.Entry(marco_contexto, textvariable=self.carga_kg, width=10).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(marco_contexto, text="Agarre:").grid(row=0, column=4, sticky="w")
        ttk.Combobox(marco_contexto, textvariable=self.agarre, values=("bueno", "regular", "malo", "inaceptable"), state="readonly", width=14).grid(row=0, column=5, sticky="w", padx=6)
        ttk.Label(marco_contexto, text="Mirada lateral:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(marco_contexto, textvariable=self.orientacion, values=("auto", "derecha", "izquierda"), state="readonly", width=15).grid(row=1, column=1, sticky="w", padx=(6, 18), pady=(10, 0))
        ttk.Checkbutton(marco_contexto, text="Estática > 1 min", variable=self.estatica).grid(row=1, column=2, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(marco_contexto, text="Repetitiva > 4/min", variable=self.repetitiva).grid(row=1, column=4, sticky="w", pady=(10, 0))
        ttk.Checkbutton(marco_contexto, text="Cambios bruscos/base inestable", variable=self.inestable).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(entrada, textvariable=self.estado, wraplength=780).grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 5))
        self.boton_evaluar = ttk.Button(entrada, text="Analizar ergonomía", command=self._iniciar_evaluacion)
        self.boton_evaluar.grid(row=6, column=0, sticky="w")

    def _elegir_foto(self, vista: str) -> None:
        ruta = filedialog.askopenfilename(title=f"Seleccionar vista {vista}", filetypes=(("Imágenes", "*.jpg *.jpeg *.png"), ("Todos los archivos", "*.*")))
        if ruta:
            self.archivos[vista].set(ruta)

    def _cargar_caso(self, caso: Path) -> None:
        for vista in self.archivos:
            imagenes = imagenes_de_vista(caso, vista)
            if imagenes:
                self.archivos[vista].set(str(imagenes[0]))

    def _contexto(self) -> dict[str, Any]:
        try:
            carga = float(self.carga_kg.get())
        except ValueError as exc:
            raise ValueError("La carga debe ser un número, por ejemplo 8.5.") from exc
        if carga < 0:
            raise ValueError("La carga no puede ser negativa.")
        orientacion = self.orientacion.get()
        return {
            "caso_id": self.caso_id.get().strip(), "postura": self.postura.get(),
            "orientacion_costado": None if orientacion == "auto" else orientacion,
            "carga_kg": carga, "fuerza_brusca": False, "agarre": self.agarre.get(),
            "actividad": {"estatica_mas_1min": self.estatica.get(), "repetitiva_mas_4_por_min": self.repetitiva.get(), "cambios_bruscos_o_base_inestable": self.inestable.get()},
            "hombro_elevado": {"izquierdo": False, "derecho": False},
            "brazo_apoyado": {"izquierdo": False, "derecho": False},
            "muneca_desviada_o_torcida": {"izquierdo": False, "derecho": False}, "overrides": {},
        }

    def _preparar_caso(self) -> Path:
        contexto = self._contexto()
        caso_id = contexto["caso_id"]
        if not caso_id or any(caracter in caso_id for caracter in "\\/:*?\"<>|"):
            raise ValueError("El identificador del caso es obligatorio y no debe contener caracteres de ruta.")
        seleccionadas = {vista: Path(variable.get()) for vista, variable in self.archivos.items() if variable.get().strip()}
        if not seleccionadas:
            raise ValueError("Selecciona al menos una fotografía.")
        if any(not ruta.is_file() for ruta in seleccionadas.values()):
            raise ValueError("Una de las rutas de fotografía ya no existe.")
        destino = self.raiz / "data" / "casos" / caso_id
        if destino.exists() and any(destino.iterdir()) and not messagebox.askyesno("Caso existente", f"El caso '{caso_id}' ya existe. ¿Actualizar sus fotografías y contexto?"):
            raise RuntimeError("Operación cancelada.")
        destino.mkdir(parents=True, exist_ok=True)
        for vista, origen in seleccionadas.items():
            anteriores = imagenes_de_vista(destino, vista)
            if origen.resolve() in [anterior.resolve() for anterior in anteriores]:
                continue  # La foto elegida ya es la del caso (precargada con --caso).
            for anterior in anteriores:
                anterior.unlink()
            shutil.copy2(origen, destino / f"{vista}{origen.suffix.lower()}")
        (destino / "contexto.json").write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8")
        return destino

    def _iniciar_evaluacion(self) -> None:
        try:
            caso = self._preparar_caso()
        except (ValueError, RuntimeError) as exc:
            if str(exc) != "Operación cancelada.":
                messagebox.showerror("No se puede iniciar", str(exc))
            return
        self.boton_evaluar.configure(state="disabled")
        self.estado.set("Analizando localmente; puede tomar unos momentos…")
        threading.Thread(target=self._evaluar_en_segundo_plano, args=(caso,), daemon=True).start()

    def _evaluar_en_segundo_plano(self, caso: Path) -> None:
        try:
            salida = ejecutar_evaluar(caso, self.raiz)
            datos = json.loads(salida.read_text(encoding="utf-8"))
            self.ventana.after(0, lambda: self._mostrar_resultado(datos, salida.parent))
        except Exception as exc:  # La interfaz debe comunicar errores del backend sin cerrarse.
            mensaje = str(exc)  # Python borra `exc` al salir del except; Tk ejecuta la lambda después.
            self.ventana.after(0, lambda: self._mostrar_error(mensaje))

    def _mostrar_error(self, error: str) -> None:
        self.boton_evaluar.configure(state="normal")
        self.estado.set("La evaluación no pudo completarse.")
        messagebox.showerror("Error durante el análisis", error)

    def _mostrar_resultado(self, datos: dict[str, Any], carpeta: Path) -> None:
        self.boton_evaluar.configure(state="normal")
        self.estado.set(f"Evaluación completada. Archivos locales: {carpeta}")
        for widget in self.panel_resultado.winfo_children():
            widget.destroy()
        reba = datos.get("reba", {})
        final = reba.get("final", {}).get("reportado")
        riesgo = reba.get("nivel_riesgo") or "Pendiente"
        ttk.Label(self.panel_resultado, text="Resultado de evaluación", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self.panel_resultado, text=f"REBA: {final if final is not None else 'Pendiente'}   ·   Riesgo: {riesgo}", font=("Segoe UI", 15)).pack(anchor="w", pady=(8, 12))
        pendientes = datos.get("pendientes_manuales", [])
        if pendientes:
            texto = "\n".join(f"• {pendiente.get('medida')}: {pendiente.get('motivo', 'revisar')}" for pendiente in pendientes[:8])
            ttk.Label(self.panel_resultado, text="Revisión manual requerida:\n" + texto, justify="left", wraplength=780).pack(anchor="w", pady=(0, 10))
        resumen = ttk.Label(self.panel_resultado, text=json.dumps(reba, ensure_ascii=False, indent=2), justify="left", font=("Consolas", 9))
        resumen.pack(anchor="w", fill="x")
        imagen = next((carpeta / f"{vista}_angulos.png" for vista in ("costado", "frente", "aerea") if (carpeta / f"{vista}_angulos.png").is_file()), None)
        if imagen:
            with Image.open(imagen) as original:
                vista = original.copy()
                vista.thumbnail((760, 360))
            self._imagen_mostrada = ImageTk.PhotoImage(vista)
            ttk.Label(self.panel_resultado, image=self._imagen_mostrada).pack(anchor="w", pady=10)

    def ejecutar(self) -> None:
        """Inicia el bucle visible de Tk."""

        self.ventana.mainloop()


def main() -> None:
    """Punto de entrada de la beta de escritorio."""

    parser = argparse.ArgumentParser(description="ErgoAI Beta · interfaz local")
    parser.add_argument("--caso", type=Path, help="precarga las fotos de un caso existente")
    argumentos = parser.parse_args()
    AplicacionErgoAI(Path(__file__).resolve().parents[2], argumentos.caso).ejecutar()


if __name__ == "__main__":
    main()
