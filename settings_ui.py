from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk

from config import normalize_channel, save_config
from kick_api import ChannelNotFound, KickClient, KickError

log = logging.getLogger("kickpresence.ui")

OK_COLOR = "#1a7f37"
ERROR_COLOR = "#b42318"
MUTED_COLOR = "#6b7280"

_single_window_lock = threading.Lock()


class SettingsWindow:
    def __init__(self, config: dict) -> None:
        self.config = dict(config)
        self.result: dict | None = None
        self.events: queue.Queue = queue.Queue()
        self.closed = False
        self.logo = None

        self.root = tk.Tk()
        self.root.title("KickPresence")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.columnconfigure(0, weight=1)

        channels = self.config.get("kick_channels") or [""]
        self.channel_var = tk.StringVar(value=str(channels[0]))
        self.status_var = tk.StringVar(value="Escribe el nombre de tu canal de Kick")

        self._build()

    def _build(self) -> None:
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass

        container = ttk.Frame(self.root, padding=16)
        container.grid(row=0, column=0, sticky="nsew")

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        try:
            from PIL import ImageTk

            from icon import make_image

            self.logo = ImageTk.PhotoImage(make_image(48))
            ttk.Label(header, image=self.logo).grid(row=0, column=0, rowspan=2, padx=(0, 12))
            self.root.iconphoto(True, self.logo)
        except Exception as exc:
            log.debug("Sin logo en la ventana: %s", exc)
        ttk.Label(header, text="KickPresence", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(
            header,
            text="Escribe el nombre de tu canal de Kick",
            foreground=MUTED_COLOR,
        ).grid(row=1, column=1, sticky="w")

        channel = ttk.Labelframe(container, text="Canal de Kick", padding=12)
        channel.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        channel.columnconfigure(0, weight=1)
        entry = ttk.Entry(channel, textvariable=self.channel_var, width=28)
        entry.grid(row=0, column=0, sticky="ew")
        entry.focus_set()
        entry.bind("<Return>", lambda event: self.save())
        ttk.Button(channel, text="Verificar", command=self.verify).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            channel,
            text="Puedes pegar la direccion completa: kick.com/tu-canal",
            foreground=MUTED_COLOR,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.status_label = ttk.Label(
            channel, textvariable=self.status_var, wraplength=330, justify="left"
        )
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        if self.channel_var.get():
            self.set_status(f"Canal configurado: {self.channel_var.get()}", muted=True)

        actions = ttk.Frame(container)
        actions.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Cancelar", command=self.close).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(actions, text="Guardar", command=self.save).grid(row=0, column=2, padx=(8, 0))

        self.root.update_idletasks()
        self._fit_window(center=True)

    def _fit_window(self, center: bool = False) -> None:
        self.root.update_idletasks()
        width = max(self.root.winfo_reqwidth(), 400)
        height = self.root.winfo_reqheight()
        if center:
            x = max(0, (self.root.winfo_screenwidth() - width) // 2)
            y = max(0, (self.root.winfo_screenheight() - height) // 3)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        else:
            self.root.geometry(f"{width}x{height}")

    def set_status(self, text: str, error: bool = False, muted: bool = False) -> None:
        self.status_var.set(text)
        color = ERROR_COLOR if error else (MUTED_COLOR if muted else OK_COLOR)
        try:
            self.status_label.configure(foreground=color)
        except Exception:
            pass
        try:
            self._fit_window()
        except Exception:
            pass

    def collect(self) -> dict:
        values = dict(self.config)
        values["kick_channels"] = [normalize_channel(self.channel_var.get())]
        return values

    def verify(self) -> None:
        slug = normalize_channel(self.channel_var.get())
        if not slug:
            self.set_status("Escribi el nombre de tu canal de Kick", error=True)
            return
        self.set_status("Consultando a Kick...", muted=True)
        threading.Thread(target=self._verify_worker, args=(slug,), daemon=True).start()

    def _verify_worker(self, slug: str) -> None:
        client = KickClient()
        try:
            info = client.get_channel_info(slug)
        except ChannelNotFound:
            self.events.put(("status", (f"No existe un canal '{slug}' en Kick", True, False)))
            return
        except KickError as exc:
            self.events.put(("status", (f"No se pudo verificar: {exc}", True, False)))
            return
        finally:
            client.close()

        if info.live:
            title = info.title or ""
            if len(title) > 90:
                title = title[:87].rstrip() + "..."
            message = f"Canal '{info.username}' encontrado y EN VIVO ahora: {title}"
        else:
            message = f"Canal '{info.username}' encontrado. Ahora mismo esta offline"
        self.events.put(("status", (message, False, False)))

    def save(self) -> None:
        values = self.collect()
        if not values["kick_channels"][0]:
            self.set_status("Escribi el nombre de tu canal de Kick", error=True)
            return
        try:
            path = save_config(values)
        except OSError as exc:
            self.set_status(f"No se pudo guardar la configuracion: {exc}", error=True)
            return
        log.info("Configuracion guardada en %s", path)
        self.result = values
        self.close()

    def close(self) -> None:
        self.closed = True
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.set_status(*payload)
        except queue.Empty:
            pass
        if not self.closed:
            self.root.after(120, self._drain)

    def run(self) -> dict | None:
        self.root.after(120, self._drain)
        self.root.mainloop()
        return self.result


def run_settings_window(config: dict) -> dict | None:
    if not _single_window_lock.acquire(blocking=False):
        return None
    try:
        window = SettingsWindow(config)
        return window.run()
    finally:
        _single_window_lock.release()
