from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import ConfigError, app_dir, config_path, load_config, validate
from kick_api import ChannelNotFound, KickClient, KickError, KickStream
from presence import PresenceConfigError, PresenceManager, truncate

log = logging.getLogger("kickpresence")


def log_file_path() -> Path:
    return app_dir() / "KickPresence.log"


def setup_logging(verbose: bool) -> None:
    root = logging.getLogger()
    root.handlers.clear()

    short = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    full = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s")

    if sys.stdout is not None:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(short)
        root.addHandler(stream_handler)

    if getattr(sys, "frozen", False) or sys.stdout is None:
        try:
            file_handler = RotatingFileHandler(
                log_file_path(), maxBytes=1_000_000, backupCount=1, encoding="utf-8"
            )
            file_handler.setFormatter(full)
            root.addHandler(file_handler)
        except OSError:
            pass

    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def pause_on_error() -> None:
    if not getattr(sys, "frozen", False):
        return
    try:
        if sys.stdin and sys.stdin.isatty():
            input("Presiona Enter para cerrar...")
    except (EOFError, KeyboardInterrupt, OSError):
        pass


def message_box(text: str, title: str = "KickPresence", flags: int = 0x40) -> None:
    if sys.platform != "win32" or sys.stdout is not None:
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except Exception:
        pass


def fail(message: str, title: str = "KickPresence") -> None:
    for line in message.splitlines() or [message]:
        log.error("%s", line)
    if sys.stdout is None:
        message_box(message, title, 0x10)
        return
    pause_on_error()


_mutex_handle = None


def acquire_single_instance() -> bool:
    global _mutex_handle
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, "KickPresence_SingleInstance")
        if not handle:
            return True
        if ctypes.get_last_error() == 183:
            kernel32.CloseHandle(handle)
            return False
        _mutex_handle = handle
        return True
    except Exception as exc:
        log.debug("No se pudo comprobar la instancia unica: %s", exc)
        return True


def open_settings_window(config: dict) -> dict | None:
    try:
        from settings_ui import run_settings_window
    except Exception as exc:
        log.warning("La ventana de configuracion no esta disponible (%s)", exc)
        return None
    try:
        return run_settings_window(config)
    except Exception as exc:
        log.warning("No se pudo abrir la ventana de configuracion (%s)", exc)
        return None


def _open_path(path: Path) -> None:
    opener = getattr(os, "startfile", None)
    if opener is not None:
        try:
            opener(str(path))
            return
        except OSError:
            pass
    webbrowser.open(path.as_uri())


def format_viewers(count: int) -> str:
    if count >= 1_000_000:
        return f"{_short(count / 1_000_000)}M espectadores"
    if count >= 1_000:
        return f"{_short(count / 1_000)}K espectadores"
    return f"{count} espectadores"


def _short(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def build_payload(stream: KickStream, config: dict) -> dict:
    parts: list[str] = []
    if config["show_category"] and stream.category:
        parts.append(stream.category)
    if config["show_viewers"] and stream.viewers > 0:
        parts.append(format_viewers(stream.viewers))

    start = None
    if config["show_elapsed_time"] and stream.started_at is not None:
        start = min(int(stream.started_at.timestamp()), int(time.time()))

    large_image = config["large_image_live"] or None
    if config["use_stream_thumbnail"]:
        thumbnail = stream.public_thumbnail
        if thumbnail:
            large_image = thumbnail

    link = stream.url if config["clickable_urls"] else None

    return {
        "details": truncate(stream.title),
        "state": truncate(" | ".join(parts) or "En vivo en Kick"),
        "start": start,
        "large_image": large_image,
        "large_text": truncate(stream.category or config["large_text_live"] or "Kick"),
        "small_image": config["small_image_live"] or None,
        "small_text": truncate(
            f"{format_viewers(stream.viewers)} en vivo" if stream.viewers > 0 else "En vivo"
        ),
        "status_display_type": config["status_display_type"],
        "details_url": link,
        "large_url": link,
        "buttons": [
            {
                "label": truncate(config["button_label"] or "Ver stream", 32),
                "url": stream.url,
            }
        ],
    }


def example_payload(config: dict) -> dict:
    channels = config.get("kick_channels") or []
    link = f"https://kick.com/{channels[0]}" if channels else "https://kick.com"
    return {
        "details": "Prueba de presencia",
        "state": "Si ves esto en tu perfil, todo funciona",
        "start": int(time.time()),
        "large_image": config["large_image_live"] or None,
        "large_text": truncate(config["large_text_live"] or "Kick"),
        "small_image": config["small_image_live"] or None,
        "small_text": "En vivo",
        "status_display_type": config["status_display_type"],
        "details_url": link if config["clickable_urls"] else None,
        "large_url": link if config["clickable_urls"] else None,
        "buttons": [
            {
                "label": truncate(config["button_label"] or "Ver stream", 32),
                "url": link,
            }
        ],
    }


def stream_signature(stream: KickStream, config: dict) -> tuple:
    return (
        stream.slug,
        stream.title,
        stream.category,
        stream.viewers if config["show_viewers"] else None,
        int(stream.started_at.timestamp())
        if stream.started_at and config["show_elapsed_time"]
        else None,
    )


def poll(client: KickClient, channels: list[str]) -> tuple[KickStream | None, list[str], int]:
    errors: list[str] = []
    checked = 0
    for slug in channels:
        try:
            stream = client.get_stream(slug)
        except (ChannelNotFound, KickError) as exc:
            message = str(exc)
            if message not in errors:
                errors.append(message)
            continue
        checked += 1
        if stream is not None:
            return stream, errors, checked
    return None, errors, checked


@dataclass
class PollResult:
    stream: KickStream | None = None
    errors: list[str] = field(default_factory=list)
    checked: int = 0
    payload: dict | None = None
    updated: bool = False
    went_live: bool = False
    went_offline: bool = False


class Monitor:
    def __init__(self, config: dict, presence: PresenceManager | None) -> None:
        self.config = config
        self.presence = presence
        self.client = KickClient()
        self.stream: KickStream | None = None
        self._signature = None
        self._updated_at = 0.0
        self._closed = False

    def reload(self) -> None:
        self._updated_at = 0.0
        self.stream = None

    def step(self) -> PollResult:
        stream, errors, checked = poll(self.client, self.config["kick_channels"])
        result = PollResult(stream=stream, errors=errors, checked=checked)

        if not checked:
            return result

        if stream is None:
            if self._signature is not None:
                if self.presence is not None:
                    self.presence.clear()
                self._signature = None
                self.stream = None
                result.went_offline = True
            return result

        signature = stream_signature(stream, self.config)
        stale = (time.monotonic() - self._updated_at) >= self.config["refresh_interval_seconds"]
        disconnected = self.presence is not None and not self.presence.connected

        if signature != self._signature or stale or disconnected:
            payload = build_payload(stream, self.config)
            result.payload = payload
            if self.presence is None:
                result.updated = True
            else:
                result.updated = self.presence.update(payload)
            if result.updated:
                self._signature = signature
                self._updated_at = time.monotonic()

        result.went_live = self.stream is None
        self.stream = stream
        return result

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.presence is not None:
            self.presence.clear()
            self.presence.close()
        self.client.close()


def _log_result(result: PollResult) -> None:
    if not result.checked:
        log.debug("Sin respuesta de Kick; se mantiene el ultimo estado")
    if result.updated and result.payload is not None:
        log.info(
            "Presencia actualizada: %s | %s | %s",
            result.stream.username if result.stream else "",
            result.stream.title if result.stream else "",
            result.payload["state"],
        )
    if result.went_offline:
        log.info("El canal ya no esta en vivo; presencia limpiada")


def run_loop(config: dict, dry_run: bool) -> int:
    presence = None if dry_run else PresenceManager(config["discord_client_id"])
    monitor = Monitor(config, presence)
    interval = config["poll_interval_seconds"]
    last_errors: tuple[str, ...] = ()

    log.info("Monitoreando %s cada %ss", ", ".join(config["kick_channels"]), interval)
    if dry_run:
        log.info("Modo dry-run: no se enviara nada a Discord")

    try:
        while True:
            result = monitor.step()

            errors = tuple(result.errors)
            if errors and errors != last_errors:
                for message in errors:
                    log.warning(message)
            last_errors = errors

            if dry_run and result.updated and result.payload is not None:
                log.info("EN VIVO: %s", json.dumps(result.payload, ensure_ascii=False))
            else:
                _log_result(result)

            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Cerrando...")
    finally:
        monitor.close()
    return 0


def _notify(icon, message: str, title: str) -> None:
    try:
        icon.notify(message, title)
    except Exception:
        pass


def run_tray(config: dict, dry_run: bool) -> int:
    try:
        import pystray

        from icon import make_image

        background = make_image(64)
    except Exception as exc:
        log.warning("No se pudo cargar la bandeja del sistema (%s); se usa el modo consola", exc)
        return run_loop(config, dry_run)

    presence = None if dry_run else PresenceManager(config["discord_client_id"])
    monitor = Monitor(config, presence)
    stop_event = threading.Event()
    status = {"text": "Iniciando..."}
    settings_lock = threading.Lock()

    def status_text(item=None):
        return status["text"]

    def channel_text(item=None):
        return f"Canal: {config['kick_channels'][0]}"

    def open_channel(icon=None, item=None):
        target = (
            monitor.stream.url
            if monitor.stream is not None
            else f"https://kick.com/{config['kick_channels'][0]}"
        )
        webbrowser.open(target)

    def open_settings(icon=None, item=None):
        if not settings_lock.acquire(blocking=False):
            return

        def worker():
            try:
                updated = open_settings_window(dict(config))
                if updated:
                    config.clear()
                    config.update(updated)
                    monitor.reload()
                    log.info(
                        "Configuracion aplicada: canal %s", ", ".join(config["kick_channels"])
                    )
                    status["text"] = "Configuracion guardada"
            finally:
                settings_lock.release()

        threading.Thread(target=worker, name="kick-settings", daemon=True).start()

    def open_log(icon=None, item=None):
        path = log_file_path()
        _open_path(path if path.exists() else app_dir())

    def quit_app(icon=None, item=None):
        stop_event.set()
        if icon is not None:
            icon.stop()

    icon = pystray.Icon(
        "KickPresence",
        background,
        "KickPresence",
        pystray.Menu(
            pystray.MenuItem(status_text, None, enabled=False),
            pystray.MenuItem(channel_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir canal en Kick", open_channel, default=True),
            pystray.MenuItem("Configurar canal...", open_settings),
            pystray.MenuItem("Abrir registro", open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", quit_app),
        ),
    )

    def worker() -> None:
        last_errors: tuple[str, ...] = ()
        while not stop_event.is_set():
            result = monitor.step()

            errors = tuple(result.errors)
            if errors and errors != last_errors:
                for message in errors:
                    log.warning(message)
            last_errors = errors
            _log_result(result)

            if result.stream is not None:
                status["text"] = f"EN VIVO: {truncate(result.stream.title, 45)}"
            elif result.checked:
                status["text"] = "Offline"
            else:
                status["text"] = "Sin respuesta de Kick"
            if not dry_run and presence is not None and not presence.connected:
                status["text"] += " (Discord no disponible)"

            if config["notify_on_change"]:
                if result.went_live and result.stream is not None:
                    _notify(icon, result.stream.title, "Estas en vivo en Kick")
                if result.went_offline:
                    _notify(icon, "Termino el stream", "Presencia de Discord limpiada")

            try:
                icon.title = status["text"]
                icon.update_menu()
            except Exception:
                pass

            stop_event.wait(config["poll_interval_seconds"])
        monitor.close()

    log.info(
        "Monitoreando %s cada %ss",
        ", ".join(config["kick_channels"]),
        config["poll_interval_seconds"],
    )
    if dry_run:
        log.info("Modo dry-run: no se enviara nada a Discord")

    thread = threading.Thread(target=worker, name="kick-monitor", daemon=True)
    thread.start()
    try:
        icon.run()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        thread.join(timeout=15)
        monitor.close()
    return 0


def run_once(config: dict) -> int:
    client = KickClient()
    try:
        stream, errors, checked = poll(client, config["kick_channels"])
    finally:
        client.close()
    for message in errors:
        log.warning(message)
    if stream is None:
        log.info("Ningun canal esta en vivo (canales consultados: %s)", checked)
        return 1
    log.info("EN VIVO: %s", json.dumps(build_payload(stream, config), ensure_ascii=False))
    return 0


def send_test_presence(config: dict, seconds: float) -> tuple[bool, str]:
    presence = PresenceManager(config["discord_client_id"])

    client = KickClient()
    try:
        stream, errors, checked = poll(client, config["kick_channels"])
    finally:
        client.close()
    for message in errors:
        log.warning(message)

    if stream is not None:
        payload = build_payload(stream, config)
        message = f"datos reales de '{stream.slug}': {stream.title}"
    else:
        payload = example_payload(config)
        message = "ningun canal en vivo; se envio una presencia de ejemplo"

    if not presence.update(payload):
        presence.close()
        return False, (
            "No se pudo enviar la presencia. Revisa que Discord este abierto y el Application ID"
        )

    log.info("Presencia de prueba enviada; se mantendra %.0f segundos", seconds)
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        pass
    presence.clear()
    presence.close()
    log.info("Presencia de prueba finalizada")
    return True, message


def run_test(config: dict, seconds: float) -> int:
    ok, message = send_test_presence(config, seconds)
    if not ok:
        fail(message)
        return 1
    log.info("%s", message)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="KickPresence",
        description="Muestra en tu actividad de Discord cuando un canal de Kick esta en vivo",
    )
    parser.add_argument("--config", help="Ruta alternativa al config.json")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Abre la ventana de configuracion y sale",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Consulta los canales una vez, muestra el resultado y sale (no toca Discord)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Monitorea sin enviar la presencia a Discord",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Envia una presencia de prueba a Discord y sale",
    )
    parser.add_argument(
        "--test-seconds",
        type=float,
        default=60.0,
        help="Duracion de la presencia de prueba (default 60)",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Ejecuta con icono en la bandeja del sistema",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Ejecuta en modo consola (sin bandeja)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log detallado")
    args = parser.parse_args(argv)

    setup_logging(args.verbose)

    monitoring = not (args.once or args.dry_run or args.test or args.setup)
    if monitoring and not acquire_single_instance():
        message = "KickPresence ya esta abierto. Buscalo en el icono de la bandeja del sistema."
        log.info("%s", message)
        message_box(message)
        return 0

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        fail(str(exc))
        return 2

    if args.setup:
        open_settings_window(config)
        return 0

    if args.once and not config["kick_channels"]:
        log.info("No hay canales configurados todavia; abri la app y elegi tu canal de Kick")
        return 1

    needs_discord = args.test or (not args.once and not args.dry_run)
    problems = validate(
        config, require_client_id=needs_discord, require_channels=not args.test
    )
    if problems and not args.once and not args.dry_run and not args.test:
        log.info("Configuracion incompleta; abriendo la ventana de configuracion")
        updated = open_settings_window(config)
        if updated is not None:
            config = updated
            problems = validate(config, require_client_id=needs_discord)

    if problems:
        fail("\n".join([*problems, "", f"Edita la configuracion en: {config_path()}"]))
        return 2

    use_tray = args.tray or (not args.console and sys.stdout is None)

    try:
        if args.test:
            return run_test(config, args.test_seconds)
        if args.once:
            return run_once(config)
        if use_tray:
            return run_tray(config, dry_run=args.dry_run)
        return run_loop(config, dry_run=args.dry_run)
    except PresenceConfigError as exc:
        fail(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
