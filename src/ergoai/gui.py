"""Interfaz de escritorio local de ErgoAI: evaluación, validación del especialista e informe."""

from __future__ import annotations

import argparse
import json
import shutil
import threading
import webbrowser
from pathlib import Path
from tkinter import BooleanVar, StringVar, Text, Tk, Toplevel, filedialog, messagebox, simpledialog
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

from PIL import Image, ImageTk

from .cli import ejecutar_evaluar, ejecutar_validacion
from .config import cargar_configuracion
from .informe import COLOR_RIESGO, ETIQUETA_ESTADO, cargar_estado
from .recomendaciones import ETIQUETA_JERARQUIA, JERARQUIAS, TIPOS_TAREA, TIPOS_TRABAJO
from .validacion import bloqueos_aprobacion, verificar_bitacora

# Sustitutos para fuentes bitmap (Tk sin Xft, p. ej. Python de uv en Linux) que no tienen estos glifos.
_ASCII = str.maketrans({"−": "-", "→": "->", "Δ": "d", "–": "-", "—": "-", "≥": ">=", "≤": "<=", "⚠": "!"})

ETIQUETA_TAREA = {"levantamiento": "Levantamiento", "transporte_con_auxiliar": "Transporte con auxiliar",
                  "transporte_sin_auxiliar": "Transporte sin auxiliar", "otro": "Otra tarea"}


class AplicacionErgoAI:
    """Ventana local para evaluar, validar recomendaciones y emitir el informe."""

    def __init__(self, raiz: Path, caso_inicial: Path | None = None) -> None:
        self.raiz = raiz
        self.config = cargar_configuracion(raiz / "config" / "umbrales.yaml")
        self.ventana = Tk()
        self.ventana.title("ErgoAI · Evaluación ergonómica")
        self.ventana.minsize(1000, 720)
        base = tkfont.nametofont("TkDefaultFont")
        familia = base.actual("family")
        self._solo_ascii = familia == "fixed"
        self.f_titulo = tkfont.Font(family=familia, size=20, weight="bold")
        self.f_grande = tkfont.Font(family=familia, size=14, weight="bold")
        self.f_negrita = tkfont.Font(family=familia, size=base.actual("size"), weight="bold")
        self.archivos: dict[str, StringVar] = {vista: StringVar() for vista in ("frente", "costado", "aerea")}
        self.caso_id = StringVar(value=caso_inicial.name if caso_inicial else "caso01")
        self.especialista = StringVar()
        self.tipo_tarea = StringVar(value=ETIQUETA_TAREA["levantamiento"])
        self.tipo_trabajo = StringVar(value="ligero")
        self.carga_kg = StringVar(value="0")
        self.agarre = StringVar(value="bueno")
        self.postura = StringVar(value="de_pie")
        self.orientacion = StringVar(value="auto")
        self.banderas = {nombre: BooleanVar(value=False) for nombre in (
            "estatica", "repetitiva", "inestable", "fuerza_brusca", "hombro_izq", "hombro_der",
            "apoyo_izq", "apoyo_der", "muneca_izq", "muneca_der")}
        self.estado = StringVar(value="Selecciona al menos una fotografía para comenzar.")
        self.carpeta_actual: Path | None = None
        self.estado_caso: dict[str, Any] | None = None
        self._imagen_mostrada: ImageTk.PhotoImage | None = None
        self._construir()
        if caso_inicial:
            self._cargar_caso(caso_inicial)
        self._refrescar_bandeja()

    def _t(self, texto: Any) -> str:
        texto = str(texto)
        return texto.translate(_ASCII) if self._solo_ascii else texto

    # ------------------------------------------------------------------ construcción
    def _construir(self) -> None:
        self.cuaderno = ttk.Notebook(self.ventana)
        self.cuaderno.pack(fill="both", expand=True, padx=12, pady=12)
        self.tab_entrada = ttk.Frame(self.cuaderno, padding=14)
        self.tab_resultado = ttk.Frame(self.cuaderno, padding=14)
        self.tab_validacion = ttk.Frame(self.cuaderno, padding=14)
        self.tab_bandeja = ttk.Frame(self.cuaderno, padding=14)
        self.cuaderno.add(self.tab_entrada, text="Nueva evaluación")
        self.cuaderno.add(self.tab_resultado, text="Resultado")
        self.cuaderno.add(self.tab_validacion, text="Validación del especialista")
        self.cuaderno.add(self.tab_bandeja, text="Bandeja de casos")
        self._construir_entrada()
        self._construir_validacion()
        self._construir_bandeja()
        ttk.Label(self.tab_resultado, text="Analiza un caso o ábrelo desde la bandeja.").pack(anchor="w")

    def _construir_entrada(self) -> None:
        e = self.tab_entrada
        ttk.Label(e, text="ErgoAI", font=self.f_titulo).grid(row=0, column=0, sticky="w")
        ttk.Label(e, text="Las imágenes se procesan solo en este equipo", foreground="#396a45").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        caso = ttk.LabelFrame(e, text="Caso", padding=10)
        caso.grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(caso, text="Identificador:").grid(row=0, column=0, sticky="w")
        ttk.Entry(caso, textvariable=self.caso_id, width=24).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(caso, text="Especialista:").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Entry(caso, textvariable=self.especialista, width=28).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(caso, text="Tipo de tarea:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(caso, textvariable=self.tipo_tarea, values=[ETIQUETA_TAREA[t] for t in TIPOS_TAREA], state="readonly", width=24).grid(row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(caso, text="Tipo de trabajo:").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(6, 0))
        ttk.Combobox(caso, textvariable=self.tipo_trabajo, values=TIPOS_TRABAJO, state="readonly", width=12).grid(row=1, column=3, sticky="w", padx=6, pady=(6, 0))

        fotos = ttk.LabelFrame(e, text="Fotografías (frente, costado y/o aérea, sin rostro)", padding=10)
        fotos.grid(row=3, column=0, columnspan=3, sticky="ew", pady=4)
        for fila, vista in enumerate(("frente", "costado", "aerea")):
            ttk.Label(fotos, text=f"{vista.capitalize()}:").grid(row=fila, column=0, sticky="w", pady=2)
            ttk.Entry(fotos, textvariable=self.archivos[vista], width=80).grid(row=fila, column=1, sticky="ew", padx=6)
            ttk.Button(fotos, text="Elegir…", command=lambda actual=vista: self._elegir_foto(actual)).grid(row=fila, column=2)
        fotos.columnconfigure(1, weight=1)

        ctx = ttk.LabelFrame(e, text="Contexto de la tarea", padding=10)
        ctx.grid(row=4, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(ctx, text="Postura:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(ctx, textvariable=self.postura, values=("de_pie", "sentado", "alternada"), state="readonly", width=12).grid(row=0, column=1, sticky="w", padx=(6, 16))
        ttk.Label(ctx, text="Carga (kg):").grid(row=0, column=2, sticky="w")
        ttk.Entry(ctx, textvariable=self.carga_kg, width=8).grid(row=0, column=3, sticky="w", padx=(6, 16))
        ttk.Label(ctx, text="Agarre:").grid(row=0, column=4, sticky="w")
        ttk.Combobox(ctx, textvariable=self.agarre, values=("bueno", "regular", "malo", "inaceptable"), state="readonly", width=12).grid(row=0, column=5, sticky="w", padx=6)
        ttk.Label(ctx, text="Mirada lateral:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(ctx, textvariable=self.orientacion, values=("auto", "derecha", "izquierda"), state="readonly", width=12).grid(row=1, column=1, sticky="w", padx=(6, 16), pady=(8, 0))
        casillas = (
            ("estatica", "Estática > 1 min"), ("repetitiva", "Repetitiva > 4/min"), ("inestable", "Cambios bruscos / base inestable"),
            ("fuerza_brusca", "Fuerza brusca o de golpe"), ("hombro_izq", "Hombro elevado izq."), ("hombro_der", "Hombro elevado der."),
            ("apoyo_izq", "Brazo apoyado izq."), ("apoyo_der", "Brazo apoyado der."), ("muneca_izq", "Muñeca desviada/torcida izq."),
            ("muneca_der", "Muñeca desviada/torcida der."),
        )
        for indice, (clave, texto) in enumerate(casillas):
            ttk.Checkbutton(ctx, text=texto, variable=self.banderas[clave]).grid(row=2 + indice // 3, column=(indice % 3) * 2, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(e, textvariable=self.estado, wraplength=900).grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 4))
        self.boton_evaluar = ttk.Button(e, text="Analizar ergonomía", command=self._iniciar_evaluacion)
        self.boton_evaluar.grid(row=6, column=0, sticky="w")
        e.columnconfigure(1, weight=1)

    def _construir_validacion(self) -> None:
        v = self.tab_validacion
        arriba = ttk.Frame(v)
        arriba.pack(fill="x")
        self.lbl_val_titulo = ttk.Label(arriba, text="Sin caso cargado", font=self.f_grande)
        self.lbl_val_titulo.pack(side="left")
        ttk.Label(arriba, text="   Especialista:").pack(side="left")
        ttk.Entry(arriba, textvariable=self.especialista, width=26).pack(side="left", padx=6)
        self.lbl_val_estado = ttk.Label(v, text="", wraplength=950, justify="left")
        self.lbl_val_estado.pack(anchor="w", pady=(6, 6))

        columnas = ("id", "jerarquia", "problema", "delta", "estado", "responsable")
        marco_arbol = ttk.Frame(v)
        marco_arbol.pack(fill="both", expand=True)
        self.arbol = ttk.Treeview(marco_arbol, columns=columnas, show="headings", height=10, selectmode="browse")
        for columna, titulo, ancho in (("id", "ID", 120), ("jerarquia", "Jerarquía", 160), ("problema", "Problema detectado", 380),
                                       ("delta", "Reduce", 70), ("estado", "Validación", 150), ("responsable", "Responsable", 130)):
            self.arbol.heading(columna, text=titulo)
            self.arbol.column(columna, width=ancho, anchor="center" if columna in ("delta",) else "w", stretch=columna == "problema")
        self.arbol.tag_configure("aprobada", background="#e3f4e8")
        self.arbol.tag_configure("rechazada", foreground="#999999")
        self.arbol.tag_configure("propuesta", background="#fff4d6")
        barra = ttk.Scrollbar(marco_arbol, orient="vertical", command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.arbol.bind("<<TreeviewSelect>>", lambda _evento: self._mostrar_detalle())
        self.arbol.bind("<Double-1>", lambda _evento: self._dialogo_editar())

        self.detalle = Text(v, height=6, wrap="word", relief="flat", background="#f5f7fa")
        self.detalle.pack(fill="x", pady=6)
        self.detalle.configure(state="disabled")

        botones = ttk.Frame(v)
        botones.pack(fill="x")
        for texto, comando in (("Aprobar", lambda: self._decidir("aprobar")), ("Rechazar…", lambda: self._decidir("rechazar")),
                               ("Editar…", self._dialogo_editar), ("Devolver a propuesta", lambda: self._decidir("reabrir")),
                               ("Agregar recomendación…", self._dialogo_agregar)):
            ttk.Button(botones, text=texto, command=comando).pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="Abrir informe", command=self._abrir_informe).pack(side="right")
        self.boton_aprobar_informe = ttk.Button(botones, text="Aprobar informe", command=self._aprobar_informe)
        self.boton_aprobar_informe.pack(side="right", padx=6)

        ttk.Label(v, text="Bitácora de cambios", font=self.f_negrita).pack(anchor="w", pady=(10, 2))
        self.arbol_bitacora = ttk.Treeview(v, columns=("n", "fecha", "usuario", "accion", "rec", "detalle"), show="headings", height=6)
        for columna, titulo, ancho in (("n", "#", 40), ("fecha", "Fecha", 170), ("usuario", "Usuario", 140), ("accion", "Acción", 110),
                                       ("rec", "Rec.", 110), ("detalle", "Cambios / comentario", 400)):
            self.arbol_bitacora.heading(columna, text=titulo)
            self.arbol_bitacora.column(columna, width=ancho, stretch=columna == "detalle")
        self.arbol_bitacora.pack(fill="x")

    def _construir_bandeja(self) -> None:
        b = self.tab_bandeja
        cabecera = ttk.Frame(b)
        cabecera.pack(fill="x")
        ttk.Label(cabecera, text="Casos ordenados por prioridad de riesgo", font=self.f_grande).pack(side="left")
        ttk.Button(cabecera, text="Actualizar", command=self._refrescar_bandeja).pack(side="right")
        ttk.Label(b, text="Los casos de riesgo alto y muy alto aparecen primero. Doble clic para abrir.", foreground="#5b6573").pack(anchor="w", pady=(4, 8))
        columnas = ("caso", "tarea", "reba", "riesgo", "residual", "pendientes", "informe")
        self.arbol_bandeja = ttk.Treeview(b, columns=columnas, show="headings", height=18)
        for columna, titulo, ancho in (("caso", "Caso", 140), ("tarea", "Tarea", 170), ("reba", "REBA", 60), ("riesgo", "Riesgo", 100),
                                       ("residual", "Residual", 110), ("pendientes", "Por validar", 90), ("informe", "Informe", 100)):
            self.arbol_bandeja.heading(columna, text=titulo)
            self.arbol_bandeja.column(columna, width=ancho, anchor="w")
        for nivel, color in COLOR_RIESGO.items():
            if nivel:
                self.arbol_bandeja.tag_configure(nivel, foreground=color)
        self.arbol_bandeja.pack(fill="both", expand=True)
        self.arbol_bandeja.bind("<Double-1>", lambda _evento: self._abrir_desde_bandeja())

    # ------------------------------------------------------------------ entrada
    def _elegir_foto(self, vista: str) -> None:
        ruta = filedialog.askopenfilename(title=f"Seleccionar vista {vista}", filetypes=(("Imágenes", "*.jpg *.jpeg *.png"), ("Todos los archivos", "*.*")))
        if ruta:
            self.archivos[vista].set(ruta)

    def _cargar_caso(self, caso: Path) -> None:
        for vista in self.archivos:
            for extension in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
                candidata = caso / f"{vista}{extension}"
                if candidata.exists():
                    self.archivos[vista].set(str(candidata))
                    break

    def _tipo_tarea(self) -> str:
        return next((clave for clave, texto in ETIQUETA_TAREA.items() if texto == self.tipo_tarea.get()), "otro")

    def _contexto(self) -> dict[str, Any]:
        try:
            carga = float(self.carga_kg.get())
        except ValueError as exc:
            raise ValueError("La carga debe ser un número, por ejemplo 8.5.") from exc
        if carga < 0:
            raise ValueError("La carga no puede ser negativa.")
        orientacion = self.orientacion.get()
        b = {clave: variable.get() for clave, variable in self.banderas.items()}
        return {
            "caso_id": self.caso_id.get().strip(), "realizado_por": self.especialista.get().strip(),
            "tipo_tarea": self._tipo_tarea(), "tipo_trabajo": self.tipo_trabajo.get(), "postura": self.postura.get(),
            "orientacion_costado": None if orientacion == "auto" else orientacion,
            "carga_kg": carga, "fuerza_brusca": b["fuerza_brusca"], "agarre": self.agarre.get(),
            "actividad": {"estatica_mas_1min": b["estatica"], "repetitiva_mas_4_por_min": b["repetitiva"], "cambios_bruscos_o_base_inestable": b["inestable"]},
            "hombro_elevado": {"izquierdo": b["hombro_izq"], "derecho": b["hombro_der"]},
            "brazo_apoyado": {"izquierdo": b["apoyo_izq"], "derecho": b["apoyo_der"]},
            "muneca_desviada_o_torcida": {"izquierdo": b["muneca_izq"], "derecho": b["muneca_der"]}, "overrides": {},
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
        anterior = destino / "contexto.json"
        if anterior.is_file():  # conserva overrides de ángulos capturados antes por el especialista
            try:
                contexto["overrides"] = json.loads(anterior.read_text(encoding="utf-8")).get("overrides", {})
            except (json.JSONDecodeError, AttributeError):
                pass
        for vista, origen in seleccionadas.items():
            final = destino / f"{vista}{origen.suffix.lower()}"
            if origen.resolve() != final.resolve():
                shutil.copy2(origen, final)
        anterior.write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8")
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
            self.ventana.after(0, lambda: self._evaluacion_lista(salida.parent))
        except Exception as exc:  # La interfaz debe comunicar errores del backend sin cerrarse.
            mensaje = str(exc)
            self.ventana.after(0, lambda: self._mostrar_error(mensaje))

    def _evaluacion_lista(self, carpeta: Path) -> None:
        self.boton_evaluar.configure(state="normal")
        self.estado.set(f"Evaluación completada. Archivos locales: {carpeta}")
        self._abrir_carpeta(carpeta)
        self._refrescar_bandeja()
        self.cuaderno.select(self.tab_resultado)

    def _mostrar_error(self, error: str) -> None:
        self.boton_evaluar.configure(state="normal")
        self.estado.set("La evaluación no pudo completarse.")
        messagebox.showerror("Error durante el análisis", error)

    # ------------------------------------------------------------------ resultado
    def _abrir_carpeta(self, carpeta: Path) -> None:
        try:
            self.estado_caso = cargar_estado(carpeta, self.config.reba)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("No se pudo abrir el caso", str(exc))
            return
        self.carpeta_actual = carpeta
        self._pintar_resultado()
        self._pintar_validacion()

    def _insignia(self, padre: ttk.Frame, titulo: str, puntaje: Any, nivel: str | None, pie: str) -> None:
        marco = ttk.Frame(padre, padding=10, relief="groove")
        marco.pack(side="left", padx=(0, 10), fill="y")
        ttk.Label(marco, text=titulo, foreground="#5b6573").pack(anchor="w")
        ttk.Label(marco, text=self._t(f"REBA {puntaje if puntaje is not None else '—'} · {nivel or 'Pendiente'}"), font=self.f_grande,
                  foreground=COLOR_RIESGO.get(nivel, "#888")).pack(anchor="w")
        ttk.Label(marco, text=pie, foreground="#5b6573").pack(anchor="w")

    def _pintar_resultado(self) -> None:
        assert self.estado_caso and self.carpeta_actual
        for widget in self.tab_resultado.winfo_children():
            widget.destroy()
        resultado, residual = self.estado_caso["resultado"], self.estado_caso["residual"]
        ini, res = residual["inicial"], residual["residual"]
        r = self.tab_resultado
        cabecera = ttk.Frame(r)
        cabecera.pack(fill="x")
        ttk.Label(cabecera, text=f"Caso {resultado.get('caso_id')}", font=self.f_titulo).pack(side="left")
        ttk.Button(cabecera, text="Abrir informe", command=self._abrir_informe).pack(side="right")
        ttk.Button(cabecera, text="Validar recomendaciones →", command=lambda: self.cuaderno.select(self.tab_validacion)).pack(side="right", padx=6)
        tarjetas = ttk.Frame(r)
        tarjetas.pack(fill="x", pady=10)
        self._insignia(tarjetas, "Riesgo inicial", ini["reba"], ini["nivel_riesgo"], f"Nivel de acción {ini['nivel_accion'] if ini['nivel_accion'] is not None else '—'}")
        self._insignia(tarjetas, "Riesgo residual esperado", res["reba"], res["nivel_riesgo"], f"{len(residual['recomendaciones_aplicadas'])} controles vigentes")
        tiempo = (resultado.get("tiempos_s") or {}).get("analisis_total")
        reduccion = residual.get("reduccion_puntos")
        marco = ttk.Frame(tarjetas, padding=10, relief="groove")
        marco.pack(side="left", fill="y")
        ttk.Label(marco, text="Reducción / tiempo del agente", foreground="#5b6573").pack(anchor="w")
        ttk.Label(marco, text=self._t(f"{'—' if reduccion is None else f'−{reduccion} pts'}"), font=self.f_grande).pack(anchor="w")
        ttk.Label(marco, text=f"{'—' if tiempo is None else f'{tiempo:.1f} s de análisis'}", foreground="#5b6573").pack(anchor="w")

        cuerpo = ttk.Frame(r)
        cuerpo.pack(fill="both", expand=True)
        imagen = next((self.carpeta_actual / f"{vista}_angulos.png" for vista in ("costado", "frente", "aerea") if (self.carpeta_actual / f"{vista}_angulos.png").is_file()), None)
        if imagen:
            with Image.open(imagen) as original:
                vista = original.copy()
                vista.thumbnail((520, 460))
            self._imagen_mostrada = ImageTk.PhotoImage(vista)
            ttk.Label(cuerpo, image=self._imagen_mostrada).pack(side="left", anchor="n", padx=(0, 12))
        derecha = ttk.Frame(cuerpo)
        derecha.pack(side="left", fill="both", expand=True)
        reba = resultado.get("reba", {})
        a = reba.get("grupo_a", {})
        lado = (reba.get("final") or {}).get("lado")
        b = (reba.get("grupo_b") or {}).get(lado or "L", {})
        filas = (("Tronco", a.get("tronco")), ("Cuello", a.get("cuello")), ("Piernas", a.get("piernas")), ("Carga/fuerza", a.get("carga")),
                 (f"Brazo ({lado or '—'})", b.get("brazo")), ("Antebrazo", b.get("antebrazo")), ("Muñeca", b.get("muneca")),
                 ("Agarre", b.get("agarre")), ("Actividad", reba.get("actividad")))
        tabla = ttk.Treeview(derecha, columns=("seg", "banda"), show="headings", height=len(filas))
        tabla.heading("seg", text="Componente REBA")
        tabla.heading("banda", text="Puntos")
        tabla.column("banda", width=70, anchor="center")
        for nombre, valor in filas:
            tabla.insert("", "end", values=(nombre, self._t("—") if valor is None else valor))
        tabla.pack(fill="x")
        pendientes = resultado.get("pendientes_manuales", [])
        if pendientes:
            texto = "\n".join(f"• {p.get('medida')}: {p.get('motivo', 'revisar')}" for p in pendientes[:10])
            ttk.Label(derecha, text="Revisión manual requerida:\n" + texto, justify="left", wraplength=420, foreground="#7a5600").pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------------ validación
    def _rec_seleccionada(self) -> dict[str, Any] | None:
        if not self.estado_caso:
            return None
        seleccion = self.arbol.selection()
        if not seleccion:
            return None
        return next((rec for rec in self.estado_caso["validacion"]["recomendaciones"] if rec["id"] == seleccion[0]), None)

    def _pintar_validacion(self) -> None:
        if not self.estado_caso:
            return
        validacion, residual = self.estado_caso["validacion"], self.estado_caso["residual"]
        nivel = self.estado_caso["resultado"].get("reba", {}).get("nivel_accion")
        seleccion = self.arbol.selection()
        self.arbol.delete(*self.arbol.get_children())
        for rec in validacion["recomendaciones"]:
            if rec.get("estado") == "obsoleta":
                continue
            delta = rec.get("delta_reba")
            self.arbol.insert("", "end", iid=rec["id"], tags=(rec.get("estado", "propuesta"),), values=tuple(self._t(valor) for valor in (
                rec["id"], ETIQUETA_JERARQUIA.get(rec.get("jerarquia"), rec.get("jerarquia")), rec["problema"],
                "—" if delta is None else (f"−{delta}" if delta > 0 else "0"), ETIQUETA_ESTADO.get(rec.get("estado"), rec.get("estado")),
                rec.get("responsable") or "—")))
        if seleccion and self.arbol.exists(seleccion[0]):
            self.arbol.selection_set(seleccion[0])
        aprobado = validacion.get("estado_informe") == "aprobado"
        self.lbl_val_titulo.configure(text=f"Caso {self.estado_caso['resultado'].get('caso_id')} · informe {'APROBADO' if aprobado else 'BORRADOR'}",
                                      foreground="#1f6b38" if aprobado else "#7a5600")
        ini, res = residual["inicial"], residual["residual"]
        partes = [f"REBA inicial {ini['reba']} ({ini['nivel_riesgo']}) → residual {res['reba']} ({res['nivel_riesgo']}) con los controles no rechazados."]
        if aprobado:
            partes.append(f"Aprobado por {validacion.get('aprobado_por')} el {validacion.get('aprobado_en')}.")
        else:
            bloqueos = bloqueos_aprobacion(validacion, nivel)
            partes.append("Listo para aprobar." if not bloqueos else "Falta: " + "; ".join(bloqueos[:4]) + (" …" if len(bloqueos) > 4 else ""))
        self.lbl_val_estado.configure(text=self._t("  ".join(partes)))
        self.arbol_bitacora.delete(*self.arbol_bitacora.get_children())
        for entrada in reversed(validacion.get("bitacora", [])):
            cambios = "; ".join(f"{campo}: {v.get('antes')} → {v.get('despues')}" for campo, v in entrada.get("cambios", {}).items())
            detalle = " · ".join(parte for parte in (cambios, entrada.get("comentario")) if parte)
            self.arbol_bitacora.insert("", "end", values=(entrada["n"], entrada["fecha"], entrada["usuario"], entrada["accion"], entrada.get("rec_id") or "", self._t(detalle)))
        if not verificar_bitacora(validacion):
            self.lbl_val_estado.configure(text=self.lbl_val_estado.cget("text") + self._t("  ⚠ La bitácora fue alterada fuera de ErgoAI."))
        self._mostrar_detalle()

    def _mostrar_detalle(self) -> None:
        rec = self._rec_seleccionada()
        self.detalle.configure(state="normal")
        self.detalle.delete("1.0", "end")
        if rec:
            refs = "\n".join(f"  · {ref}" for ref in rec.get("referencias", []))
            self.detalle.insert("end", self._t(f"{rec['id']} — {ETIQUETA_JERARQUIA.get(rec.get('jerarquia'), '')} · prioridad {rec.get('prioridad')}\n"
                                               f"Recomendación: {rec['solucion']}\n" + (f"Fundamento:\n{refs}\n" if refs else "")
                                               + (f"Comentario: {rec['comentario']}\n" if rec.get("comentario") else "")))
        else:
            self.detalle.insert("end", "Selecciona una recomendación para ver su fundamento. Doble clic para editar.")
        self.detalle.configure(state="disabled")

    def _usuario(self) -> str | None:
        usuario = self.especialista.get().strip()
        if not usuario:
            usuario = (simpledialog.askstring("Especialista", "Nombre del especialista que valida:", parent=self.ventana) or "").strip()
            self.especialista.set(usuario)
        if not usuario:
            messagebox.showwarning("Especialista requerido", "Cada cambio queda registrado con el nombre de quien lo hace.")
            return None
        return usuario

    def _validar(self, accion: str, rec_id: str | None = None, valores: dict[str, str] | None = None, comentario: str = "") -> bool:
        if not self.carpeta_actual:
            messagebox.showinfo("Sin caso", "Primero analiza o abre un caso.")
            return False
        usuario = self._usuario()
        if not usuario:
            return False
        try:
            ejecutar_validacion(self.carpeta_actual, self.raiz, usuario, accion, rec_id, valores, comentario)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("No se registró el cambio", str(exc).strip("'\""))
            return False
        self._abrir_carpeta(self.carpeta_actual)
        self._refrescar_bandeja()
        return True

    def _decidir(self, accion: str) -> None:
        rec = self._rec_seleccionada()
        if not rec:
            messagebox.showinfo("Selecciona", "Selecciona una recomendación de la lista.")
            return
        comentario = ""
        if accion == "rechazar":
            comentario = (simpledialog.askstring("Motivo del rechazo", f"¿Por qué se rechaza {rec['id']}?", parent=self.ventana) or "").strip()
            if not comentario:
                return
        self._validar(accion, rec["id"], comentario=comentario)

    def _formulario(self, titulo: str, rec: dict[str, Any] | None) -> None:
        dialogo = Toplevel(self.ventana)
        dialogo.title(titulo)
        dialogo.transient(self.ventana)
        dialogo.grab_set()
        marco = ttk.Frame(dialogo, padding=14)
        marco.pack(fill="both", expand=True)
        campos_texto: dict[str, Text] = {}
        for fila, (campo, etiqueta) in enumerate((("problema", "Problema"), ("solucion", "Recomendación"))):
            ttk.Label(marco, text=etiqueta + ":").grid(row=fila, column=0, sticky="nw", pady=3)
            caja = Text(marco, width=70, height=3 if campo == "problema" else 5, wrap="word")
            caja.insert("1.0", (rec or {}).get(campo, ""))
            caja.grid(row=fila, column=1, sticky="ew", pady=3)
            campos_texto[campo] = caja
        jerarquia = StringVar(value=ETIQUETA_JERARQUIA[(rec or {}).get("jerarquia", "rediseno")])
        responsable = StringVar(value=(rec or {}).get("responsable", ""))
        fecha = StringVar(value=(rec or {}).get("fecha_compromiso", ""))
        comentario = StringVar()
        aprobar = BooleanVar(value=True)
        ttk.Label(marco, text="Jerarquía:").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(marco, textvariable=jerarquia, values=[ETIQUETA_JERARQUIA[j] for j in JERARQUIAS], state="readonly", width=28).grid(row=2, column=1, sticky="w")
        ttk.Label(marco, text="Responsable:").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(marco, textvariable=responsable, width=40).grid(row=3, column=1, sticky="w")
        ttk.Label(marco, text="Fecha compromiso:").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(marco, textvariable=fecha, width=20).grid(row=4, column=1, sticky="w")
        ttk.Label(marco, text="Comentario:").grid(row=5, column=0, sticky="w", pady=3)
        ttk.Entry(marco, textvariable=comentario, width=70).grid(row=5, column=1, sticky="ew")
        if rec:
            ttk.Checkbutton(marco, text="Aprobar al guardar", variable=aprobar).grid(row=6, column=1, sticky="w", pady=(6, 0))

        def guardar() -> None:
            valores = {
                "problema": campos_texto["problema"].get("1.0", "end").strip(), "solucion": campos_texto["solucion"].get("1.0", "end").strip(),
                "jerarquia": next(clave for clave, texto in ETIQUETA_JERARQUIA.items() if texto == jerarquia.get()),
                "responsable": responsable.get().strip(), "fecha_compromiso": fecha.get().strip(),
            }
            if rec is None:
                ok = self._validar("agregar", valores=valores)
            else:
                ok = self._validar("editar", rec["id"], valores, comentario.get().strip())
                if ok and aprobar.get() and self._rec_estado(rec["id"]) != "aprobada":
                    ok = self._validar("aprobar", rec["id"], comentario=comentario.get().strip())
            if ok:
                dialogo.destroy()

        acciones = ttk.Frame(marco)
        acciones.grid(row=7, column=1, sticky="e", pady=(12, 0))
        ttk.Button(acciones, text="Cancelar", command=dialogo.destroy).pack(side="right")
        ttk.Button(acciones, text="Guardar", command=guardar).pack(side="right", padx=6)
        marco.columnconfigure(1, weight=1)

    def _rec_estado(self, rec_id: str) -> str | None:
        if not self.estado_caso:
            return None
        return next((rec.get("estado") for rec in self.estado_caso["validacion"]["recomendaciones"] if rec["id"] == rec_id), None)

    def _dialogo_editar(self) -> None:
        rec = self._rec_seleccionada()
        if not rec:
            messagebox.showinfo("Selecciona", "Selecciona una recomendación de la lista.")
            return
        self._formulario(f"Editar {rec['id']}", rec)

    def _dialogo_agregar(self) -> None:
        if not self.carpeta_actual:
            messagebox.showinfo("Sin caso", "Primero analiza o abre un caso.")
            return
        self._formulario("Agregar recomendación del especialista", None)

    def _aprobar_informe(self) -> None:
        if self._validar("aprobar_informe"):
            messagebox.showinfo("Informe aprobado", "El informe quedó aprobado y registrado en la bitácora.")

    def _abrir_informe(self) -> None:
        if not self.carpeta_actual or not (self.carpeta_actual / "informe.html").is_file():
            messagebox.showinfo("Sin informe", "Primero analiza o abre un caso.")
            return
        webbrowser.open((self.carpeta_actual / "informe.html").resolve().as_uri())

    # ------------------------------------------------------------------ bandeja
    def _refrescar_bandeja(self) -> None:
        self.arbol_bandeja.delete(*self.arbol_bandeja.get_children())
        filas = []
        for ruta in sorted((self.raiz / "out").glob("*/resultado.json")):
            try:
                estado = cargar_estado(ruta.parent, self.config.reba)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            resultado, validacion, residual = estado["resultado"], estado["validacion"], estado["residual"]
            reba = resultado.get("reba", {})
            pendientes = sum(1 for rec in validacion["recomendaciones"] if rec.get("estado") == "propuesta")
            filas.append((reba.get("nivel_accion") if reba.get("nivel_accion") is not None else -1, pendientes, ruta.parent, (
                resultado.get("caso_id"), ETIQUETA_TAREA.get((resultado.get("contexto") or {}).get("tipo_tarea") or "otro", "—"),
                (reba.get("final") or {}).get("reportado") or "—", reba.get("nivel_riesgo") or "Pendiente",
                f"{residual['residual']['reba'] or '—'} ({residual['residual']['nivel_riesgo'] or '—'})", pendientes,
                "Aprobado" if validacion.get("estado_informe") == "aprobado" else "Borrador"), reba.get("nivel_riesgo")))
        for _nivel, _pend, carpeta, valores, riesgo in sorted(filas, key=lambda fila: (-fila[0], -fila[1])):
            self.arbol_bandeja.insert("", "end", iid=str(carpeta), values=tuple(self._t(valor) for valor in valores), tags=(riesgo,) if riesgo else ())

    def _abrir_desde_bandeja(self) -> None:
        seleccion = self.arbol_bandeja.selection()
        if seleccion:
            self._abrir_carpeta(Path(seleccion[0]))
            self.cuaderno.select(self.tab_validacion)

    def ejecutar(self) -> None:
        """Inicia el bucle visible de Tk."""

        self.ventana.mainloop()


def main() -> None:
    """Punto de entrada de la aplicación de escritorio."""

    parser = argparse.ArgumentParser(description="ErgoAI · interfaz local")
    parser.add_argument("--caso", type=Path, help="precarga las fotos de un caso existente")
    argumentos = parser.parse_args()
    AplicacionErgoAI(Path(__file__).resolve().parents[2], argumentos.caso).ejecutar()


if __name__ == "__main__":
    main()
