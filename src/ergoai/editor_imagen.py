"""Recorte y zoom local de fotografías. No altera el cálculo REBA."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

from PIL import Image, ImageTk

FONDO = "#F3F5F7"
TEXTO = "#1C2430"
MUDO = "#5B6775"
ACENTO = "#0F7A66"
BLANCO = "#FFFFFF"


def guardar_recorte(origen: Path, caja: tuple[int, int, int, int], destino: Path | None = None) -> Path:
    """Guarda un recorte RGB. `caja` está en píxeles de la imagen original (l, t, r, b)."""

    izquierda, arriba, derecha, abajo = caja
    if derecha - izquierda < 8 or abajo - arriba < 8:
        raise ValueError("El recorte es demasiado pequeño.")
    with Image.open(origen) as original:
        recorte = original.convert("RGB").crop((izquierda, arriba, derecha, abajo))
    salida = destino or origen.with_name(f"{origen.stem}_recorte{origen.suffix.lower() or '.jpg'}")
    if salida.suffix.lower() in {".jpg", ".jpeg"}:
        recorte.save(salida, quality=95)
    else:
        recorte.save(salida)
    return salida


class DialogoRecorte(tk.Toplevel):
    """Selecciona un área rectangular sobre la foto antes de evaluar."""

    def __init__(self, padre: tk.Misc, ruta: Path, titulo: str = "Recortar foto") -> None:
        super().__init__(padre)
        self.title(titulo)
        self.configure(bg=FONDO)
        self.resizable(True, True)
        self.ruta = Path(ruta)
        self.resultado: Path | None = None
        self._foto: ImageTk.PhotoImage | None = None
        self._escala = 1.0
        self._inicio: tuple[int, int] | None = None
        self._rect = None
        with Image.open(self.ruta) as original:
            self._original = original.convert("RGB")
        self.geometry("980x720")
        self.transient(padre)
        self.grab_set()
        barra = tk.Frame(self, bg=FONDO)
        barra.pack(fill="x", padx=12, pady=10)
        tk.Label(barra, text="Arrastra para marcar el área. Útil para encuadrar al operador o sacar el rostro del cuadro.", font=("Segoe UI", 10), bg=FONDO, fg=MUDO).pack(side="left")
        ttk.Button(barra, text="Aplicar recorte", command=self._aplicar).pack(side="right", padx=(8, 0))
        ttk.Button(barra, text="Cancelar", command=self.destroy).pack(side="right")
        self.canvas = tk.Canvas(self, bg="#1C2430", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.canvas.bind("<Configure>", self._redibujar)
        self.canvas.bind("<ButtonPress-1>", self._iniciar)
        self.canvas.bind("<B1-Motion>", self._arrastrar)
        self.canvas.bind("<ButtonRelease-1>", self._soltar)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _redibujar(self, _evento=None) -> None:
        ancho = max(self.canvas.winfo_width(), 100)
        alto = max(self.canvas.winfo_height(), 100)
        vista = self._original.copy()
        vista.thumbnail((ancho - 20, alto - 20))
        self._escala = vista.width / self._original.width
        self._foto = ImageTk.PhotoImage(vista)
        self.canvas.delete("all")
        self._ox = (ancho - vista.width) // 2
        self._oy = (alto - vista.height) // 2
        self.canvas.create_image(self._ox, self._oy, anchor="nw", image=self._foto, tags="img")
        self._rect = None
        self._inicio = None

    def _iniciar(self, evento: tk.Event) -> None:
        self._inicio = (evento.x, evento.y)
        if self._rect is not None:
            self.canvas.delete(self._rect)
            self._rect = None

    def _arrastrar(self, evento: tk.Event) -> None:
        if self._inicio is None:
            return
        if self._rect is not None:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(self._inicio[0], self._inicio[1], evento.x, evento.y, outline=ACENTO, width=2)

    def _soltar(self, evento: tk.Event) -> None:
        self._arrastrar(evento)

    def _caja_original(self) -> tuple[int, int, int, int] | None:
        if self._inicio is None or self._rect is None:
            return None
        coords = self.canvas.coords(self._rect)
        if len(coords) != 4:
            return None
        x1, y1, x2, y2 = coords
        izquierda = int((min(x1, x2) - self._ox) / self._escala)
        arriba = int((min(y1, y2) - self._oy) / self._escala)
        derecha = int((max(x1, x2) - self._ox) / self._escala)
        abajo = int((max(y1, y2) - self._oy) / self._escala)
        izquierda = max(0, min(izquierda, self._original.width - 1))
        arriba = max(0, min(arriba, self._original.height - 1))
        derecha = max(izquierda + 1, min(derecha, self._original.width))
        abajo = max(arriba + 1, min(abajo, self._original.height))
        return izquierda, arriba, derecha, abajo

    def _aplicar(self) -> None:
        caja = self._caja_original()
        if caja is None:
            messagebox.showwarning("Recorte", "Marca un área arrastrando el mouse sobre la foto.", parent=self)
            return
        try:
            self.resultado = guardar_recorte(self.ruta, caja)
        except ValueError as exc:
            messagebox.showerror("Recorte", str(exc), parent=self)
            return
        self.destroy()


class VisorZoom(tk.Toplevel):
    """Visor con zoom (rueda) y paneo (arrastrar) para fotos anotadas."""

    def __init__(self, padre: tk.Misc, ruta: Path, titulo: str) -> None:
        super().__init__(padre)
        self.title(titulo)
        self.configure(bg=FONDO)
        self.geometry("1100x780")
        self.ruta = Path(ruta)
        self._escala = 1.0
        self._foto: ImageTk.PhotoImage | None = None
        self._arrastre: tuple[int, int] | None = None
        with Image.open(self.ruta) as original:
            self._original = original.convert("RGB")
        barra = tk.Frame(self, bg=FONDO)
        barra.pack(fill="x", padx=12, pady=8)
        tk.Label(barra, text=f"{titulo}  ·  rueda = zoom  ·  arrastra = mover  ·  doble clic = ajustar", font=("Segoe UI", 10), bg=FONDO, fg=MUDO).pack(side="left")
        ttk.Button(barra, text="Cerrar", command=self.destroy).pack(side="right")
        self.canvas = tk.Canvas(self, bg="#111827", highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.canvas.bind("<Configure>", lambda _e: self._mostrar(centrar=True))
        self.canvas.bind("<MouseWheel>", self._zoom)
        self.canvas.bind("<ButtonPress-1>", self._iniciar_paneo)
        self.canvas.bind("<B1-Motion>", self._paneo)
        self.canvas.bind("<Double-Button-1>", lambda _e: self._ajustar())
        self.after(50, self._ajustar)

    def _ajustar(self) -> None:
        ancho = max(self.canvas.winfo_width(), 200)
        alto = max(self.canvas.winfo_height(), 200)
        self._escala = min(ancho / self._original.width, alto / self._original.height, 1.0)
        self._mostrar(centrar=True)

    def _mostrar(self, centrar: bool = False) -> None:
        ancho = max(int(self._original.width * self._escala), 1)
        alto = max(int(self._original.height * self._escala), 1)
        vista = self._original.resize((ancho, alto), Image.Resampling.LANCZOS)
        self._foto = ImageTk.PhotoImage(vista)
        self.canvas.delete("all")
        if centrar:
            x = max((self.canvas.winfo_width() - ancho) // 2, 0)
            y = max((self.canvas.winfo_height() - alto) // 2, 0)
            self.canvas.create_image(x, y, anchor="nw", image=self._foto, tags="img")
        else:
            self.canvas.create_image(0, 0, anchor="nw", image=self._foto, tags="img")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def _zoom(self, evento: tk.Event) -> None:
        factor = 1.12 if evento.delta > 0 else 1 / 1.12
        nueva = max(0.15, min(self._escala * factor, 6.0))
        if abs(nueva - self._escala) < 1e-6:
            return
        self._escala = nueva
        self._mostrar(centrar=True)

    def _iniciar_paneo(self, evento: tk.Event) -> None:
        self._arrastre = (evento.x, evento.y)
        self.canvas.scan_mark(evento.x, evento.y)

    def _paneo(self, evento: tk.Event) -> None:
        self.canvas.scan_dragto(evento.x, evento.y, gain=1)


def abrir_recorte(padre: tk.Misc, ruta: Path, titulo: str) -> Path | None:
    dialogo = DialogoRecorte(padre, ruta, titulo=titulo)
    padre.wait_window(dialogo)
    return dialogo.resultado


def abrir_zoom(padre: tk.Misc, ruta: Path, titulo: str) -> None:
    VisorZoom(padre, ruta, titulo)
