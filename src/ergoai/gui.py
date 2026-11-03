"""Interfaz de escritorio local para evaluar posturas en estación."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import BooleanVar, StringVar, filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from .bitacora import actualizar_estado_recomendacion
from .cli import ejecutar_evaluar
from .config import cargar_configuracion
from .editor_imagen import abrir_recorte, abrir_zoom
from .informe import guardar_informe
from .presentacion import (
    AYUDA_VISTA,
    EXTENSIONES_IMAGEN,
    ETIQUETAS_AGARRE,
    ETIQUETAS_ORIENTACION,
    ETIQUETAS_POSTURA,
    ETIQUETAS_VISTA,
    VISTAS,
    aviso_vistas_faltantes,
    clave_desde_etiqueta,
    color_riesgo,
    etiqueta_segmento,
    filas_angulos,
    texto_tiempo,
)
from .recomendaciones import Recomendacion
from .residual import recalcular_residual

try:
    import windnd
except ImportError:  # Arrastrar archivos es opcional; el botón Elegir sigue disponible.
    windnd = None


def _ruta_soltada(dato: Any) -> Path | None:
    """Normaliza la ruta que llega al soltar un archivo en Windows."""

    if isinstance(dato, bytes):
        for encoding in ("utf-8", "mbcs", "latin-1"):
            try:
                dato = dato.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return None
    texto = str(dato).strip().strip("{}").strip('"')
    if not texto:
        return None
    return Path(texto)


def _primera_imagen(rutas: list[Any]) -> Path | None:
    """Toma la primera imagen válida de una lista soltada."""

    for dato in rutas:
        ruta = _ruta_soltada(dato)
        if ruta is None:
            continue
        if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES_IMAGEN:
            return ruta
    return None

FONDO = "#E8EEF2"
HEADER = "#0B2C28"
HEADER_2 = "#134039"
ACENTO = "#0F7A66"
ACENTO_SUAVE = "#D7EFE8"
ACENTO_CALIDO = "#C45C26"
TEXTO = "#14202B"
MUDO = "#5A6A78"
BLANCO = "#FBFCFD"
TARJETA = "#FFFFFF"
BORDE = "#C9D5DE"
AVISO = "#9A3B00"
AVISO_FONDO = "#FFF1E0"
COLOR_VISTA = {"frente": "#0F7A66", "costado": "#2F6FED", "aerea": "#C45C26"}


def _activar_dpi() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        return


class TarjetaFoto(tk.Frame):
    """Tarjeta para elegir, arrastrar y previsualizar una vista de la estación."""

    def __init__(self, padre: tk.Misc, vista: str, variable: StringVar, al_cambiar) -> None:
        super().__init__(padre, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        self.vista = vista
        self.variable = variable
        self.al_cambiar = al_cambiar
        self._foto: ImageTk.PhotoImage | None = None
        self.variable.trace_add("write", lambda *_: self._refrescar())
        franja = tk.Frame(self, bg=COLOR_VISTA[vista], height=6)
        franja.pack(fill="x")
        franja.pack_propagate(False)
        tk.Label(self, text=ETIQUETAS_VISTA[vista].upper(), font=("Segoe UI Semibold", 11), bg=TARJETA, fg=COLOR_VISTA[vista]).pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(self, text=AYUDA_VISTA[vista], font=("Segoe UI", 9), bg=TARJETA, fg=MUDO, wraplength=280, justify="left").pack(anchor="w", padx=14, pady=(2, 8))
        self.lienzo = tk.Frame(self, bg="#DDE7EE", height=150)
        self.lienzo.pack(fill="both", expand=True, padx=14)
        self.lienzo.pack_propagate(False)
        self.preview = tk.Label(self.lienzo, text="Arrastra una foto aquí\no haz doble clic para zoom", font=("Segoe UI", 10), bg="#DDE7EE", fg=MUDO, cursor="hand2", justify="center")
        self.preview.pack(expand=True)
        self.preview.bind("<Double-Button-1>", lambda _e: self._ver())
        fila = tk.Frame(self, bg=TARJETA)
        fila.pack(fill="x", padx=14, pady=12)
        ttk.Button(fila, text="Elegir", command=self._elegir).pack(side="left")
        self.boton_recortar = ttk.Button(fila, text="Recortar", command=self._recortar)
        self.boton_ver = ttk.Button(fila, text="Zoom", command=self._ver)
        self.boton_quitar = ttk.Button(fila, text="Quitar", command=self._quitar)
        self.estado = tk.Label(fila, text="", font=("Segoe UI Semibold", 9), bg=TARJETA, fg=MUDO)
        self.estado.pack(side="right")
        self._activar_arrastre()
        self._refrescar()

    def _activar_arrastre(self) -> None:
        if windnd is None:
            return

        def _al_soltar(rutas: list[Any]) -> None:
            imagen = _primera_imagen(list(rutas))
            if imagen is None:
                messagebox.showwarning("Archivo no válido", "Suelta una imagen JPG o PNG en esta tarjeta.")
                return
            self.variable.set(str(imagen))

        for widget in (self, self.lienzo, self.preview):
            windnd.hook_dropfiles(widget, func=_al_soltar)

    def _elegir(self) -> None:
        ruta = filedialog.askopenfilename(
            title=f"Foto de {ETIQUETAS_VISTA[self.vista].lower()}",
            filetypes=(("Imágenes", "*.jpg *.jpeg *.png"), ("Todos los archivos", "*.*")),
        )
        if ruta:
            self.variable.set(ruta)

    def _quitar(self) -> None:
        self.variable.set("")

    def _recortar(self) -> None:
        ruta = self.variable.get().strip()
        if not ruta:
            return
        padre = self.winfo_toplevel()
        nueva = abrir_recorte(padre, Path(ruta), titulo=f"Recortar · {ETIQUETAS_VISTA[self.vista]}")
        if nueva is not None:
            self.variable.set(str(nueva))

    def _ver(self) -> None:
        ruta = self.variable.get().strip()
        if not ruta:
            return
        abrir_zoom(self.winfo_toplevel(), Path(ruta), f"{ETIQUETAS_VISTA[self.vista]} · original")

    def _refrescar(self) -> None:
        ruta = self.variable.get().strip()
        if not ruta:
            self._foto = None
            self.preview.configure(image="", text="Arrastra una foto aquí\no haz doble clic para zoom", bg="#DDE7EE", fg=MUDO)
            self.configure(highlightbackground=BORDE)
            self.boton_recortar.pack_forget()
            self.boton_ver.pack_forget()
            self.boton_quitar.pack_forget()
            self.estado.configure(text="Pendiente", fg=MUDO)
            self.al_cambiar()
            return
        try:
            with Image.open(ruta) as original:
                imagen = original.copy()
                imagen.thumbnail((420, 150))
            self._foto = ImageTk.PhotoImage(imagen)
            self.preview.configure(image=self._foto, text="", bg="#DDE7EE")
            self.configure(highlightbackground=COLOR_VISTA[self.vista])
            self.boton_recortar.pack(side="left", padx=(6, 0))
            self.boton_ver.pack(side="left", padx=(6, 0))
            self.boton_quitar.pack(side="left", padx=(6, 0))
            self.estado.configure(text="Lista", fg=ACENTO)
        except OSError:
            self._foto = None
            self.preview.configure(image="", text="No se pudo leer", bg="#DDE7EE", fg="#8E1B1B")
            self.estado.configure(text="Error", fg="#8E1B1B")
        self.al_cambiar()


class AplicacionErgoAI:
    """Ventana de trabajo: fotos, contexto de estación y resultado REBA."""

    def __init__(self, raiz: Path, caso_inicial: Path | None = None) -> None:
        _activar_dpi()
        self.raiz = raiz
        self.ventana = tk.Tk()
        self.ventana.title("ErgoAI · Evaluación de postura")
        self.ventana.geometry("1400x900")
        self.ventana.minsize(1024, 700)
        self.ventana.configure(bg=FONDO)
        try:
            self.ventana.state("zoomed")  # pantalla completa usable en Windows
        except tk.TclError:
            self.ventana.attributes("-fullscreen", False)
        self.archivos: dict[str, StringVar] = {vista: StringVar() for vista in VISTAS}
        self.caso_id = StringVar(value=caso_inicial.name if caso_inicial else "")
        self.carga_kg = StringVar(value="0")
        self.agarre = StringVar(value=ETIQUETAS_AGARRE["bueno"])
        self.postura = StringVar(value="de_pie")
        self.orientacion = StringVar(value=ETIQUETAS_ORIENTACION["auto"])
        self.estatica = BooleanVar(value=False)
        self.repetitiva = BooleanVar(value=False)
        self.inestable = BooleanVar(value=False)
        self.hombro_izq = BooleanVar(value=False)
        self.hombro_der = BooleanVar(value=False)
        self.brazo_izq = BooleanVar(value=False)
        self.brazo_der = BooleanVar(value=False)
        self.muneca_izq = BooleanVar(value=False)
        self.muneca_der = BooleanVar(value=False)
        self.estado = StringVar(value="Arrastra al menos una foto a las tarjetas, o elige desde archivo.")
        self._fotos_resultado: list[ImageTk.PhotoImage] = []
        self._datos_resultado: dict[str, Any] | None = None
        self._carpeta_resultado: Path | None = None
        self._segundos_eval = 0.0
        self._aplicar_estilo()
        self._construir()
        if caso_inicial:
            self._cargar_caso(caso_inicial)

    def _aplicar_estilo(self) -> None:
        estilo = ttk.Style(self.ventana)
        estilo.theme_use("clam")
        estilo.configure(".", font=("Segoe UI", 10), background=FONDO, foreground=TEXTO)
        estilo.configure("TFrame", background=FONDO)
        estilo.configure("TLabel", background=FONDO, foreground=TEXTO)
        estilo.configure("TCheckbutton", background=TARJETA, foreground=TEXTO, font=("Segoe UI", 10))
        estilo.configure("TRadiobutton", background=TARJETA, foreground=TEXTO, font=("Segoe UI", 10))
        estilo.configure("TEntry", fieldbackground=BLANCO, padding=7)
        estilo.configure("TCombobox", padding=5)
        estilo.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        estilo.configure("Primario.TButton", font=("Segoe UI Semibold", 11), background=ACENTO, foreground="#FFFFFF", padding=(24, 11))
        estilo.map("Primario.TButton", background=[("!disabled", ACENTO), ("disabled", "#8AABB0"), ("pressed", "#0C5E50")], foreground=[("!disabled", "#FFFFFF"), ("disabled", "#FFFFFF")])
        estilo.configure("Secundario.TButton", padding=(12, 8))
        estilo.configure("Angulos.Treeview", font=("Segoe UI", 10), rowheight=30, background=TARJETA, fieldbackground=TARJETA, borderwidth=0)
        estilo.configure("Angulos.Treeview.Heading", font=("Segoe UI Semibold", 9), background="#E4EDF3", foreground=MUDO, relief="flat")
        estilo.map("Angulos.Treeview", background=[("selected", ACENTO_SUAVE)], foreground=[("selected", TEXTO)])

    def _construir(self) -> None:
        barra = tk.Frame(self.ventana, bg=HEADER, height=78)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        marca = tk.Frame(barra, bg=HEADER)
        marca.pack(side="left", padx=22, pady=12)
        tk.Label(marca, text="ErgoAI", font=("Segoe UI", 22, "bold"), bg=HEADER, fg="#FFFFFF").pack(anchor="w")
        tk.Label(marca, text="Evaluación de postura en estación · local", font=("Segoe UI", 10), bg=HEADER, fg="#9ED0C5").pack(anchor="w")
        derecha = tk.Frame(barra, bg=HEADER)
        derecha.pack(side="right", padx=22)
        tk.Label(derecha, text="El especialista decide", font=("Segoe UI Semibold", 10), bg=ACENTO_CALIDO, fg="#FFFFFF", padx=12, pady=6).pack()
        self.pasos = tk.Frame(self.ventana, bg=FONDO)
        self.pasos.pack(fill="x", padx=24, pady=(14, 0))
        self.chip_paso_1 = tk.Label(self.pasos, font=("Segoe UI Semibold", 10), padx=14, pady=7)
        self.chip_paso_2 = tk.Label(self.pasos, font=("Segoe UI Semibold", 10), padx=14, pady=7)
        self.chip_paso_1.pack(side="left")
        tk.Label(self.pasos, text="›", font=("Segoe UI", 14), bg=FONDO, fg="#9AA8B5").pack(side="left", padx=8)
        self.chip_paso_2.pack(side="left")
        self.etiqueta_paso_1 = self.chip_paso_1
        self.etiqueta_paso_2 = self.chip_paso_2
        self.cuerpo = tk.Frame(self.ventana, bg=FONDO)
        self.cuerpo.pack(fill="both", expand=True)
        self.vista_captura = tk.Frame(self.cuerpo, bg=FONDO)
        self.vista_resultado = tk.Frame(self.cuerpo, bg=FONDO)
        self._construir_captura()
        self._mostrar("captura")
        self.ventana.bind("<Configure>", self._al_redimensionar)
        self._ultimo_ancho = 0

    def _marco_desplazable(self, padre: tk.Misc) -> tk.Frame:
        lienzo = tk.Canvas(padre, bg=FONDO, highlightthickness=0)
        scroll = ttk.Scrollbar(padre, orient="vertical", command=lienzo.yview)
        interior = tk.Frame(lienzo, bg=FONDO)
        ventana = lienzo.create_window((0, 0), window=interior, anchor="nw")
        interior.bind("<Configure>", lambda _evento: lienzo.configure(scrollregion=lienzo.bbox("all")))
        lienzo.bind("<Configure>", lambda evento: lienzo.itemconfigure(ventana, width=evento.width))
        lienzo.configure(yscrollcommand=scroll.set)
        lienzo.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def _rueda(evento: tk.Event) -> None:
            lienzo.yview_scroll(int(-evento.delta / 120), "units")

        interior.bind("<Enter>", lambda _e: lienzo.bind_all("<MouseWheel>", _rueda))
        interior.bind("<Leave>", lambda _e: lienzo.unbind_all("<MouseWheel>"))
        return interior

    def _al_redimensionar(self, evento: tk.Event) -> None:
        if evento.widget is not self.ventana:
            return
        ancho = max(evento.width, 900)
        if abs(ancho - getattr(self, "_ultimo_ancho", 0)) < 40:
            return
        self._ultimo_ancho = ancho
        # Reparte las tarjetas en 3 columnas en pantallas anchas y apila mejor el texto.
        if hasattr(self, "estado_label"):
            self.estado_label.configure(wraplength=max(ancho - 420, 280))

    def _construir_captura(self) -> None:
        pie = tk.Frame(self.vista_captura, bg=HEADER_2, highlightthickness=0)
        pie.pack(side="bottom", fill="x")
        self.boton_evaluar = ttk.Button(pie, text="Analizar postura", style="Primario.TButton", command=self._iniciar_evaluacion)
        self.boton_evaluar.pack(side="left", padx=22, pady=14)
        self.progreso = ttk.Progressbar(pie, mode="indeterminate", length=180)
        self.estado_label = tk.Label(pie, textvariable=self.estado, font=("Segoe UI", 10), bg=HEADER_2, fg="#D7EFE8", wraplength=900, justify="left")
        self.estado_label.pack(side="left", padx=8, pady=14)
        interior = self._marco_desplazable(self.vista_captura)

        hero = tk.Frame(interior, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        hero.pack(fill="x", padx=24, pady=(12, 10))
        tk.Frame(hero, bg=ACENTO, width=8).pack(side="left", fill="y")
        bloque = tk.Frame(hero, bg=TARJETA)
        bloque.pack(side="left", fill="x", expand=True, padx=16, pady=14)
        tk.Label(bloque, text="Fotos de la estación", font=("Segoe UI", 18, "bold"), bg=TARJETA, fg=TEXTO).pack(anchor="w")
        tk.Label(bloque, text="Frente · costado · aérea  ·  sin rostro  ·  si falta una vista se avisa y no se inventa la pose", font=("Segoe UI", 10), bg=TARJETA, fg=MUDO).pack(anchor="w", pady=(2, 0))

        self.fotos_frame = tk.Frame(interior, bg=FONDO)
        self.fotos_frame.pack(fill="x", padx=18)
        for columna, vista in enumerate(VISTAS):
            tarjeta = TarjetaFoto(self.fotos_frame, vista, self.archivos[vista], self._actualizar_aviso_vistas)
            tarjeta.grid(row=0, column=columna, sticky="nsew", padx=6, pady=4)
            self.fotos_frame.columnconfigure(columna, weight=1, uniform="fotos")
        self.caja_aviso = tk.Frame(interior, bg=FONDO)
        self.caja_aviso.pack(fill="x", padx=24, pady=(10, 0))
        self.aviso_vistas = tk.Label(self.caja_aviso, text="", font=("Segoe UI", 10), bg=AVISO_FONDO, fg=AVISO, anchor="w", justify="left", padx=12, pady=8)
        self._actualizar_aviso_vistas()

        tk.Label(interior, text="Datos de la tarea", font=("Segoe UI", 16, "bold"), bg=FONDO, fg=TEXTO).pack(anchor="w", padx=24, pady=(16, 8))
        tarjeta = tk.Frame(interior, bg=FONDO)
        tarjeta.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        tarjeta.columnconfigure(0, weight=1, uniform="datos")
        tarjeta.columnconfigure(1, weight=1, uniform="datos")

        col_izq = tk.Frame(tarjeta, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        col_izq.grid(row=0, column=0, sticky="nsew", padx=(6, 6), pady=0)
        col_der = tk.Frame(tarjeta, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        col_der.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=0)

        tk.Label(col_izq, text="Estación y tarea", font=("Segoe UI Semibold", 11), bg=TARJETA, fg=ACENTO).pack(anchor="w", padx=16, pady=(14, 8))
        grid_izq = tk.Frame(col_izq, bg=TARJETA)
        grid_izq.pack(fill="x", padx=16, pady=(0, 8))
        grid_izq.columnconfigure(1, weight=1)
        grid_izq.columnconfigure(3, weight=1)
        self._etiqueta_campo(grid_izq, "Caso o estación").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Entry(grid_izq, textvariable=self.caso_id).grid(row=0, column=1, sticky="ew", pady=6, padx=(0, 16))
        self._etiqueta_campo(grid_izq, "Carga (kg)").grid(row=0, column=2, sticky="w", pady=6, padx=(0, 8))
        ttk.Entry(grid_izq, textvariable=self.carga_kg, width=10).grid(row=0, column=3, sticky="w", pady=6)
        self._etiqueta_campo(grid_izq, "Lado visible").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Combobox(grid_izq, textvariable=self.orientacion, values=list(ETIQUETAS_ORIENTACION.values()), state="readonly").grid(row=1, column=1, sticky="ew", pady=6, padx=(0, 16))
        self._etiqueta_campo(grid_izq, "Agarre").grid(row=1, column=2, sticky="w", pady=6, padx=(0, 8))
        ttk.Combobox(grid_izq, textvariable=self.agarre, values=list(ETIQUETAS_AGARRE.values()), state="readonly").grid(row=1, column=3, sticky="ew", pady=6)

        postura = tk.Frame(col_izq, bg=TARJETA)
        postura.pack(fill="x", padx=16, pady=(4, 16))
        self._etiqueta_campo(postura, "Postura").pack(anchor="w", pady=(0, 6))
        fila_postura = tk.Frame(postura, bg=TARJETA)
        fila_postura.pack(fill="x")
        for valor, etiqueta in ETIQUETAS_POSTURA.items():
            ttk.Radiobutton(fila_postura, text=etiqueta, value=valor, variable=self.postura).pack(side="left", padx=(0, 18))

        tk.Label(col_der, text="Condiciones y lo que se ve", font=("Segoe UI Semibold", 11), bg=TARJETA, fg=ACENTO_CALIDO).pack(anchor="w", padx=16, pady=(14, 8))
        condiciones = tk.Frame(col_der, bg=TARJETA)
        condiciones.pack(fill="x", padx=16, pady=(0, 8))
        self._etiqueta_campo(condiciones, "Condiciones").pack(anchor="w", pady=(0, 6))
        for texto, variable in (
            ("Sostiene más de 1 min", self.estatica),
            ("Se repite más de 4 veces/min", self.repetitiva),
            ("Cambios bruscos o piso inestable", self.inestable),
        ):
            ttk.Checkbutton(condiciones, text=texto, variable=variable).pack(anchor="w", pady=2)

        ajustes = tk.Frame(col_der, bg=TARJETA)
        ajustes.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self._etiqueta_campo(ajustes, "Lo que se ve").pack(anchor="w", pady=(0, 6))
        pares = (
            ("Hombro elevado izq.", self.hombro_izq),
            ("Hombro elevado der.", self.hombro_der),
            ("Brazo apoyado izq.", self.brazo_izq),
            ("Brazo apoyado der.", self.brazo_der),
            ("Muñeca torcida izq.", self.muneca_izq),
            ("Muñeca torcida der.", self.muneca_der),
        )
        grid_obs = tk.Frame(ajustes, bg=TARJETA)
        grid_obs.pack(fill="x")
        grid_obs.columnconfigure(0, weight=1)
        grid_obs.columnconfigure(1, weight=1)
        for indice, (texto, variable) in enumerate(pares):
            ttk.Checkbutton(grid_obs, text=texto, variable=variable).grid(
                row=indice // 2, column=indice % 2, sticky="w", pady=3, padx=(0, 12)
            )

    def _etiqueta_campo(self, padre: tk.Misc, texto: str) -> tk.Label:
        return tk.Label(padre, text=texto, font=("Segoe UI Semibold", 9), bg=TARJETA, fg=MUDO)

    def _actualizar_aviso_vistas(self) -> None:
        if not hasattr(self, "aviso_vistas"):
            return
        presentes = [vista for vista, variable in self.archivos.items() if variable.get().strip()]
        aviso = aviso_vistas_faltantes(presentes)
        if aviso:
            self.aviso_vistas.configure(text=aviso)
            self.aviso_vistas.pack(fill="x")
        else:
            self.aviso_vistas.pack_forget()

    def _marcar_paso(self, activo: str) -> None:
        activo_estilo = {"fg": "#FFFFFF", "bg": ACENTO}
        inactivo_estilo = {"fg": TEXTO, "bg": "#D5DEE6"}
        self.etiqueta_paso_1.configure(text="1  Fotos y tarea", **(activo_estilo if activo == "captura" else inactivo_estilo))
        self.etiqueta_paso_2.configure(text="2  Resultado REBA", **(activo_estilo if activo == "resultado" else inactivo_estilo))

    def _mostrar(self, cual: str) -> None:
        self.vista_captura.pack_forget()
        self.vista_resultado.pack_forget()
        if cual == "captura":
            self.vista_captura.pack(fill="both", expand=True)
        else:
            self.vista_resultado.pack(fill="both", expand=True)
        self._marcar_paso(cual)

    def _cargar_caso(self, caso: Path) -> None:
        self.caso_id.set(caso.name)
        for vista in self.archivos:
            for extension in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
                candidata = caso / f"{vista}{extension}"
                if candidata.exists():
                    self.archivos[vista].set(str(candidata))
                    break

    def _contexto(self) -> dict[str, Any]:
        try:
            carga = float(self.carga_kg.get().replace(",", "."))
        except ValueError as exc:
            raise ValueError("La carga debe ser un número, por ejemplo 8.5.") from exc
        if carga < 0:
            raise ValueError("La carga no puede ser negativa.")
        orientacion = clave_desde_etiqueta(ETIQUETAS_ORIENTACION, self.orientacion.get())
        return {
            "caso_id": self.caso_id.get().strip(),
            "postura": self.postura.get(),
            "orientacion_costado": None if orientacion == "auto" else orientacion,
            "carga_kg": carga,
            "fuerza_brusca": False,
            "agarre": clave_desde_etiqueta(ETIQUETAS_AGARRE, self.agarre.get()),
            "actividad": {
                "estatica_mas_1min": self.estatica.get(),
                "repetitiva_mas_4_por_min": self.repetitiva.get(),
                "cambios_bruscos_o_base_inestable": self.inestable.get(),
            },
            "hombro_elevado": {"izquierdo": self.hombro_izq.get(), "derecho": self.hombro_der.get()},
            "brazo_apoyado": {"izquierdo": self.brazo_izq.get(), "derecho": self.brazo_der.get()},
            "muneca_desviada_o_torcida": {"izquierdo": self.muneca_izq.get(), "derecho": self.muneca_der.get()},
            "overrides": {},
        }

    def _preparar_caso(self) -> Path:
        contexto = self._contexto()
        caso_id = contexto["caso_id"]
        if not caso_id or any(caracter in caso_id for caracter in '\\/:*?"<>|'):
            raise ValueError("Escribe un nombre de caso o estación, sin caracteres de ruta.")
        seleccionadas = {vista: Path(variable.get()) for vista, variable in self.archivos.items() if variable.get().strip()}
        if not seleccionadas:
            raise ValueError("Elige al menos una fotografía.")
        if any(not ruta.is_file() for ruta in seleccionadas.values()):
            raise ValueError("Una de las fotografías ya no existe.")
        destino = self.raiz / "data" / "casos" / caso_id
        destino.mkdir(parents=True, exist_ok=True)
        for vista, origen in seleccionadas.items():
            destino_foto = destino / f"{vista}{origen.suffix.lower()}"
            if origen.resolve() != destino_foto.resolve():
                shutil.copy2(origen, destino_foto)
        (destino / "contexto.json").write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8")
        return destino

    def _aviso(self, titulo: str, mensaje: str, error: bool = False) -> None:
        self.ventana.lift()
        self.ventana.attributes("-topmost", True)
        self.ventana.after(200, lambda: self.ventana.attributes("-topmost", False))
        if error:
            messagebox.showerror(titulo, mensaje, parent=self.ventana)
        else:
            messagebox.showwarning(titulo, mensaje, parent=self.ventana)

    def _iniciar_evaluacion(self) -> None:
        self.estado.set("Preparando el caso…")
        self.boton_evaluar.configure(state="disabled")
        self.ventana.update_idletasks()
        try:
            caso = self._preparar_caso()
        except ValueError as exc:
            self.boton_evaluar.configure(state="normal")
            self.estado.set(str(exc))
            self._aviso("No se puede iniciar", str(exc), error=True)
            return
        except Exception as exc:
            self.boton_evaluar.configure(state="normal")
            self.estado.set("No se pudo preparar el caso.")
            self._aviso("No se puede iniciar", str(exc) or exc.__class__.__name__, error=True)
            return
        self.progreso.pack(side="left", padx=(16, 0))
        self.progreso.start(12)
        self.estado.set("Analizando en este equipo. Puede tardar 10–30 s…")
        threading.Thread(target=self._evaluar_en_segundo_plano, args=(caso,), daemon=True).start()

    def _evaluar_en_segundo_plano(self, caso: Path) -> None:
        try:
            inicio = time.perf_counter()
            salida = ejecutar_evaluar(caso, self.raiz)
            segundos = time.perf_counter() - inicio
            datos = json.loads(salida.read_text(encoding="utf-8-sig"))
            carpeta = salida.parent
            self.ventana.after(0, lambda d=datos, c=carpeta, s=segundos: self._mostrar_resultado(d, c, s))
        except Exception as exc:
            mensaje = str(exc) or exc.__class__.__name__
            self.ventana.after(0, lambda m=mensaje: self._mostrar_error(m))

    def _mostrar_error(self, error: str) -> None:
        self.boton_evaluar.configure(state="normal")
        self.progreso.stop()
        self.progreso.pack_forget()
        self.estado.set(f"Error: {error}")
        self._aviso("Error durante el análisis", error, error=True)

    def _mostrar_resultado(self, datos: dict[str, Any], carpeta: Path, segundos: float) -> None:
        self.boton_evaluar.configure(state="normal")
        self.progreso.stop()
        self.progreso.pack_forget()
        self.estado.set("Evaluación lista. Revisa, valida e informa; el especialista decide.")
        self._datos_resultado = datos
        self._carpeta_resultado = carpeta
        self._segundos_eval = segundos
        for widget in self.vista_resultado.winfo_children():
            widget.destroy()
        self._fotos_resultado.clear()
        reba = datos.get("reba", {})
        final = reba.get("final", {}).get("reportado")
        riesgo = reba.get("nivel_riesgo")
        paleta = color_riesgo(riesgo)
        residual = datos.get("riesgo_residual") or {}
        lado = reba.get("final", {}).get("lado")
        vistas_usadas = [vista for vista in VISTAS if (carpeta / f"{vista}_angulos.png").is_file() or (carpeta / f"{vista}_pose.png").is_file()]
        if not vistas_usadas:
            vistas_usadas = [vista for vista in VISTAS if self.archivos[vista].get().strip()]

        pagina = self._marco_desplazable(self.vista_resultado)

        acciones = tk.Frame(pagina, bg=FONDO)
        acciones.pack(fill="x", padx=22, pady=(8, 0))
        ttk.Button(acciones, text="Nueva evaluación", style="Secundario.TButton", command=lambda: self._mostrar("captura")).pack(side="left")
        ttk.Button(acciones, text="Abrir archivos", style="Secundario.TButton", command=lambda: os.startfile(carpeta)).pack(side="left", padx=8)
        informe = carpeta / "informe.md"
        if informe.is_file():
            ttk.Button(acciones, text="Abrir informe", style="Secundario.TButton", command=lambda: os.startfile(informe)).pack(side="left", padx=8)

        heroe = tk.Frame(pagina, bg=paleta["bg"], highlightbackground=paleta["barra"], highlightthickness=1)
        heroe.pack(fill="x", padx=22, pady=16)
        tk.Label(heroe, text="REBA" if final is not None else "REBA pendiente", font=("Segoe UI", 10, "bold"), bg=paleta["bg"], fg=paleta["fg"]).pack(anchor="w", padx=20, pady=(16, 0))
        fila_heroe = tk.Frame(heroe, bg=paleta["bg"])
        fila_heroe.pack(fill="x", padx=20, pady=(4, 16))
        tk.Label(fila_heroe, text=str(final) if final is not None else "—", font=("Segoe UI", 48, "bold"), bg=paleta["bg"], fg=paleta["fg"]).pack(side="left")
        bloque = tk.Frame(fila_heroe, bg=paleta["bg"])
        bloque.pack(side="left", padx=20)
        tk.Label(bloque, text=(riesgo or "Pendiente").upper(), font=("Segoe UI", 18, "bold"), bg=paleta["bg"], fg=paleta["fg"]).pack(anchor="w")
        detalle_lado = f"Lado {'izquierdo' if lado == 'L' else 'derecho' if lado == 'R' else 'sin definir'}"
        tk.Label(bloque, text=f"{detalle_lado}  ·  {texto_tiempo(segundos)}  ·  caso {datos.get('caso_id', self.caso_id.get())}", font=("Segoe UI", 10), bg=paleta["bg"], fg=paleta["fg"]).pack(anchor="w", pady=(4, 0))
        residual_txt = f"Residual: {residual.get('puntaje_residual')} ({residual.get('nivel_residual')})  ·  delta {residual.get('delta')}"
        tk.Label(bloque, text=residual_txt, font=("Segoe UI", 10, "bold"), bg=paleta["bg"], fg=paleta["fg"]).pack(anchor="w", pady=(6, 0))
        aviso = aviso_vistas_faltantes(vistas_usadas)
        if aviso:
            tk.Label(heroe, text=aviso, font=("Segoe UI", 10), bg=paleta["bg"], fg=paleta["fg"], wraplength=900, justify="left").pack(anchor="w", padx=20, pady=(0, 14))

        grupos = tk.Frame(pagina, bg=FONDO)
        grupos.pack(fill="x", padx=18)
        grupo_a = reba.get("grupo_a") or {}
        grupo_b = reba.get("grupo_b") or {}
        self._ficha_grupo(grupos, "Tronco, cuello y piernas", (("Tronco", grupo_a.get("tronco")), ("Cuello", grupo_a.get("cuello")), ("Piernas", grupo_a.get("piernas")), ("Carga", grupo_a.get("carga")))).pack(side="left", fill="both", expand=True, padx=4)
        izq = grupo_b.get("L") or {}
        der = grupo_b.get("R") or {}
        self._ficha_grupo(grupos, "Brazos", (("Brazo I", izq.get("brazo")), ("Brazo D", der.get("brazo")), ("Antebrazo I", izq.get("antebrazo")), ("Antebrazo D", der.get("antebrazo")), ("Muñeca I", izq.get("muneca")), ("Muñeca D", der.get("muneca")))).pack(side="left", fill="both", expand=True, padx=4)

        cuerpo = tk.Frame(pagina, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=12)
        izquierda = tk.Frame(cuerpo, bg=FONDO)
        izquierda.pack(side="left", fill="both", expand=True, padx=4)
        derecha = tk.Frame(cuerpo, bg=FONDO)
        derecha.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(izquierda, text="Ángulos por segmento", font=("Segoe UI", 13, "bold"), bg=FONDO, fg=TEXTO).pack(anchor="w", pady=(0, 8))
        tabla = ttk.Treeview(izquierda, style="Angulos.Treeview", columns=("seg", "lado", "ang", "rango", "vista", "conf"), show="headings", height=9)
        for clave, titulo, ancho in (("seg", "Segmento", 160), ("lado", "Lado", 50), ("ang", "Ángulo", 80), ("rango", "Rango REBA", 90), ("vista", "Vista", 80), ("conf", "Confianza", 110)):
            tabla.heading(clave, text=titulo)
            tabla.column(clave, width=ancho, stretch=True)
        for fila in filas_angulos(datos.get("angulos") or []):
            tabla.insert("", "end", values=fila)
        tabla.pack(fill="both", expand=True)

        tk.Label(derecha, text="Fotos anotadas", font=("Segoe UI", 13, "bold"), bg=FONDO, fg=TEXTO).pack(anchor="w", pady=(0, 4))
        tk.Label(derecha, text="Clic o Zoom para ampliar · rueda = zoom", font=("Segoe UI", 9), bg=FONDO, fg=MUDO).pack(anchor="w", pady=(0, 8))
        self._galeria_resultado(derecha, carpeta)
        self._panel_aerea(pagina, datos)
        self._panel_recomendaciones(pagina, datos, carpeta)
        self._mostrar("resultado")

    def _panel_aerea(self, pagina: tk.Misc, datos: dict[str, Any]) -> None:
        angulos = datos.get("angulos") or []
        de_aerea = [a for a in angulos if a.get("vista") == "aerea"]
        marco = tk.Frame(pagina, bg=TARJETA, highlightbackground=COLOR_VISTA["aerea"], highlightthickness=2)
        marco.pack(fill="x", padx=22, pady=(4, 10))
        tk.Frame(marco, bg=COLOR_VISTA["aerea"], height=4).pack(fill="x")
        tk.Label(marco, text="Aporte de la vista aérea", font=("Segoe UI", 13, "bold"), bg=TARJETA, fg=COLOR_VISTA["aerea"]).pack(anchor="w", padx=14, pady=(10, 2))
        if not de_aerea:
            tk.Label(
                marco,
                text="No hubo lectura aérea útil. Recorta la foto desde arriba centrando hombros y caderas, o vuelve a analizar.",
                font=("Segoe UI", 10),
                bg=TARJETA,
                fg=MUDO,
                wraplength=1000,
                justify="left",
            ).pack(anchor="w", padx=14, pady=(0, 12))
            return
        fila = tk.Frame(marco, bg=TARJETA)
        fila.pack(fill="x", padx=10, pady=(4, 12))
        for angulo in de_aerea:
            nombre = angulo.get("medida")
            lado = angulo.get("lado") or ""
            valor = angulo.get("valor_deg")
            celda = tk.Frame(fila, bg="#FFF4EC", highlightbackground="#F0D2BC", highlightthickness=1)
            celda.pack(side="left", padx=4, pady=2, fill="both", expand=True)
            titulo = f"{etiqueta_segmento(str(nombre))} {lado}".strip()
            tk.Label(celda, text=titulo, font=("Segoe UI", 8), bg="#FFF4EC", fg=MUDO).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(celda, text="—" if valor is None else f"{valor:.1f}°", font=("Segoe UI", 16, "bold"), bg="#FFF4EC", fg=TEXTO).pack(anchor="w", padx=8, pady=(0, 6))
        tk.Label(
            marco,
            text="La aérea aporta torsión y asimetría de alcance en el plano horizontal; no sustituye frente/costado.",
            font=("Segoe UI", 9),
            bg=TARJETA,
            fg=MUDO,
        ).pack(anchor="w", padx=14, pady=(0, 10))

    def _galeria_resultado(self, padre: tk.Misc, carpeta: Path) -> None:
        galeria = tk.Frame(padre, bg=FONDO)
        galeria.pack(fill="x")
        disponibles = 0
        for columna, vista in enumerate(VISTAS):
            ruta = next(
                (
                    carpeta / nombre
                    for nombre in (f"{vista}_angulos.png", f"{vista}_pose.png")
                    if (carpeta / nombre).is_file()
                ),
                None,
            )
            celda = tk.Frame(galeria, bg=TARJETA, highlightbackground=COLOR_VISTA[vista], highlightthickness=1)
            celda.grid(row=0, column=columna, sticky="nsew", padx=3)
            galeria.columnconfigure(columna, weight=1, uniform="gal")
            tk.Frame(celda, bg=COLOR_VISTA[vista], height=4).pack(fill="x")
            tk.Label(celda, text=ETIQUETAS_VISTA[vista], font=("Segoe UI Semibold", 9), bg=TARJETA, fg=COLOR_VISTA[vista]).pack(anchor="w", padx=8, pady=(8, 0))
            lienzo = tk.Label(celda, text="Sin foto", bg="#DDE7EE", fg=MUDO, font=("Segoe UI", 9), cursor="hand2")
            lienzo.pack(fill="x", padx=8, pady=6)
            if ruta is None:
                continue
            disponibles += 1
            with Image.open(ruta) as original:
                miniatura = original.copy()
                miniatura.thumbnail((240, 160))
            foto = ImageTk.PhotoImage(miniatura)
            self._fotos_resultado.append(foto)
            lienzo.configure(image=foto, text="")
            titulo = f"{ETIQUETAS_VISTA[vista]} · anotada"
            lienzo.bind("<Button-1>", lambda _e, r=ruta, t=titulo: abrir_zoom(self.ventana, r, t))
            ttk.Button(celda, text="Zoom", command=lambda r=ruta, t=titulo: abrir_zoom(self.ventana, r, t)).pack(anchor="e", padx=8, pady=(0, 8))
        if disponibles == 0:
            tk.Label(padre, text="No hay imágenes anotadas todavía.", bg=FONDO, fg=MUDO).pack(anchor="w")

    def _panel_recomendaciones(self, pagina: tk.Misc, datos: dict[str, Any], carpeta: Path) -> None:
        residual = datos.get("riesgo_residual") or {}
        recomendaciones = datos.get("recomendaciones") or []
        marco = tk.Frame(pagina, bg=FONDO)
        marco.pack(fill="x", padx=22, pady=(4, 20))
        tk.Label(marco, text="Recomendaciones (propuestas)", font=("Segoe UI", 13, "bold"), bg=FONDO, fg=TEXTO).pack(anchor="w")
        tk.Label(
            marco,
            text="Ingeniería primero. Solo «aprobada» puede ser acción de piso. Cada cambio queda en bitácora.",
            font=("Segoe UI", 9),
            bg=FONDO,
            fg=MUDO,
        ).pack(anchor="w", pady=(0, 8))
        caja_res = tk.Frame(marco, bg=BLANCO, highlightbackground=BORDE, highlightthickness=1)
        caja_res.pack(fill="x", pady=(0, 10))
        tk.Label(
            caja_res,
            text=(
                f"Riesgo residual recalculado: {residual.get('puntaje_inicial')} ({residual.get('nivel_inicial')}) → "
                f"{residual.get('puntaje_residual')} ({residual.get('nivel_residual')})  ·  delta {residual.get('delta')}"
            ),
            font=("Segoe UI", 10, "bold"),
            bg=BLANCO,
            fg=TEXTO,
            wraplength=1000,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(10, 4))
        supuestos = residual.get("supuestos") or []
        tk.Label(caja_res, text="Supuestos: " + ("; ".join(supuestos[:6]) if supuestos else "ninguno"), font=("Segoe UI", 9), bg=BLANCO, fg=MUDO, wraplength=1000, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        if not recomendaciones:
            tk.Label(marco, text="Sin recomendaciones automáticas para este caso.", bg=FONDO, fg=MUDO).pack(anchor="w")
            return

        for item in recomendaciones:
            tarjeta = tk.Frame(marco, bg=BLANCO, highlightbackground=BORDE, highlightthickness=1)
            tarjeta.pack(fill="x", pady=4)
            encabezado = f"{item.get('id')} · {item.get('tipo_control')} · {item.get('estado')} · {item.get('segmento')}"
            tk.Label(tarjeta, text=encabezado, font=("Segoe UI Semibold", 10), bg=BLANCO, fg=TEXTO).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(tarjeta, text=item.get("problema", ""), font=("Segoe UI", 9), bg=BLANCO, fg=MUDO, wraplength=980, justify="left").pack(anchor="w", padx=12)
            tk.Label(tarjeta, text=item.get("solucion", ""), font=("Segoe UI", 10), bg=BLANCO, fg=TEXTO, wraplength=980, justify="left").pack(anchor="w", padx=12, pady=(4, 6))
            tk.Label(tarjeta, text=f"Fuente: {item.get('fuente', '')}", font=("Segoe UI", 8), bg=BLANCO, fg=MUDO).pack(anchor="w", padx=12, pady=(0, 6))
            fila = tk.Frame(tarjeta, bg=BLANCO)
            fila.pack(anchor="w", padx=12, pady=(0, 10))
            rec_id = str(item.get("id"))
            ttk.Button(fila, text="Aprobar", command=lambda i=rec_id: self._validar_recomendacion(i, "aprobada")).pack(side="left")
            ttk.Button(fila, text="Rechazar", command=lambda i=rec_id: self._validar_recomendacion(i, "rechazada")).pack(side="left", padx=6)
            ttk.Button(fila, text="En revisión", command=lambda i=rec_id: self._validar_recomendacion(i, "en_revision")).pack(side="left")

    def _validar_recomendacion(self, recomendacion_id: str, nuevo_estado: str) -> None:
        if not self._datos_resultado or not self._carpeta_resultado:
            return
        motivo = f"Especialista marca como {nuevo_estado}"
        actualizadas = actualizar_estado_recomendacion(
            list(self._datos_resultado.get("recomendaciones") or []),
            recomendacion_id,
            nuevo_estado,
            usuario="especialista",
            motivo=motivo,
            carpeta_salida=self._carpeta_resultado,
        )
        self._datos_resultado["recomendaciones"] = actualizadas
        # Residual solo con propuestas/aprobadas/en revisión/editadas (rechazadas fuera).
        try:
            objetos = [Recomendacion(**{k: v for k, v in item.items() if k in Recomendacion.__dataclass_fields__}) for item in actualizadas]
            config = cargar_configuracion(self.raiz / "config" / "umbrales.yaml")
            mediciones: dict[str, float | None] = {}
            for angulo in self._datos_resultado.get("angulos") or []:
                medida, lado = angulo["medida"], angulo.get("lado")
                clave = f"{medida}_{lado}" if lado and medida != "cuello_flexion" else medida
                mediciones[clave] = angulo.get("valor_deg")
            contexto = {
                "caso_id": self._datos_resultado.get("caso_id"),
                "postura": self.postura.get(),
                "carga_kg": float(self.carga_kg.get().replace(",", ".") or 0),
                "agarre": clave_desde_etiqueta(ETIQUETAS_AGARRE, self.agarre.get()),
                "actividad": {
                    "estatica_mas_1min": self.estatica.get(),
                    "repetitiva_mas_4_por_min": self.repetitiva.get(),
                    "cambios_bruscos_o_base_inestable": self.inestable.get(),
                },
            }
            self._datos_resultado["riesgo_residual"] = recalcular_residual(mediciones, contexto, config.reba, objetos)
        except Exception as exc:
            self._aviso("No se pudo recalcular residual", str(exc), error=True)
        (self._carpeta_resultado / "resultado.json").write_text(json.dumps(self._datos_resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        guardar_informe(self._datos_resultado, self._carpeta_resultado, tiempo_evaluacion_s=self._segundos_eval)
        self._mostrar_resultado(self._datos_resultado, self._carpeta_resultado, self._segundos_eval)

    def _ficha_grupo(self, padre: tk.Misc, titulo: str, pares: tuple[tuple[str, Any], ...]) -> tk.Frame:
        marco = tk.Frame(padre, bg=BLANCO, highlightbackground=BORDE, highlightthickness=1)
        tk.Label(marco, text=titulo, font=("Segoe UI Semibold", 10), bg=BLANCO, fg=MUDO).pack(anchor="w", padx=14, pady=(12, 6))
        fila = tk.Frame(marco, bg=BLANCO)
        fila.pack(fill="x", padx=8, pady=(0, 12))
        for nombre, valor in pares:
            celda = tk.Frame(fila, bg=BLANCO)
            celda.pack(side="left", expand=True, fill="x")
            tk.Label(celda, text="—" if valor is None else str(valor), font=("Segoe UI", 18, "bold"), bg=BLANCO, fg=TEXTO).pack()
            tk.Label(celda, text=nombre, font=("Segoe UI", 8), bg=BLANCO, fg=MUDO).pack()
        return marco

    def _nota(self, padre: tk.Misc, titulo: str, cuerpo: str) -> tk.Frame:
        marco = tk.Frame(padre, bg=BLANCO, highlightbackground=BORDE, highlightthickness=1)
        tk.Label(marco, text=titulo, font=("Segoe UI Semibold", 10), bg=BLANCO, fg=TEXTO).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(marco, text=cuerpo, font=("Segoe UI", 9), bg=BLANCO, fg=MUDO, wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(0, 12))
        return marco

    def ejecutar(self) -> None:
        """Inicia el bucle visible de Tk."""

        self.ventana.mainloop()


def main() -> None:
    """Punto de entrada de la interfaz local."""

    parser = argparse.ArgumentParser(description="ErgoAI · interfaz local")
    parser.add_argument("--caso", type=Path, help="precarga las fotos de un caso existente")
    argumentos = parser.parse_args()
    AplicacionErgoAI(Path(__file__).resolve().parents[2], argumentos.caso).ejecutar()


if __name__ == "__main__":
    main()
