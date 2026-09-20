from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

log = logging.getLogger("kickpresence.config")

MIN_POLL_INTERVAL = 15
APP_FOLDER_NAME = "KickPresence"
BUILT_IN_CLIENT_ID = "1551306300632207420"

DEFAULT_CONFIG = {
    "discord_client_id": BUILT_IN_CLIENT_ID,
    "kick_channels": [],
    "poll_interval_seconds": 30,
    "refresh_interval_seconds": 300,
    "show_viewers": True,
    "show_category": True,
    "show_elapsed_time": True,
    "notify_on_change": True,
    "use_stream_thumbnail": True,
    "clickable_urls": True,
    "status_display_type": "details",
    "large_image_live": "kick-icon",
    "small_image_live": "live_badge",
    "large_text_live": "Kick",
    "button_label": "Ver",
}


class ConfigError(Exception):
    pass


def app_dir() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent

    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "config.json").exists():
        return exe_dir

    appdata = os.environ.get("APPDATA")
    if appdata:
        target = Path(appdata) / APP_FOLDER_NAME
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            pass
    return exe_dir


def config_path() -> Path:
    return app_dir() / "config.json"


def _as_int(value: object, default: int, minimum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def normalize_channel(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^(www\.)?kick\.com/", "", raw, flags=re.IGNORECASE)
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    return raw.split("/", 1)[0].strip().lstrip("@").lower()


def save_config(config: dict, path: str | Path | None = None) -> Path:
    target = Path(path) if path else config_path()
    ordered = {key: config[key] for key in DEFAULT_CONFIG if key in config}
    for key, value in config.items():
        if key not in ordered:
            ordered[key] = value
    target.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def load_config(path: str | Path | None = None) -> dict:
    target = Path(path) if path else config_path()
    if not target.exists():
        target.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        log.info("Se creo el archivo de configuracion: %s", target)
    try:
        raw = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"No se pudo leer {target}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{target} debe contener un objeto JSON")

    config: dict = {**DEFAULT_CONFIG}
    config.update(raw)

    config["discord_client_id"] = str(config.get("discord_client_id") or "").strip()

    channels = config.get("kick_channels")
    if isinstance(channels, str):
        channels = [channels]
    if not isinstance(channels, list):
        channels = []
    config["kick_channels"] = [
        normalize_channel(item) for item in channels if normalize_channel(item)
    ]

    config["poll_interval_seconds"] = _as_int(
        config.get("poll_interval_seconds"), DEFAULT_CONFIG["poll_interval_seconds"], MIN_POLL_INTERVAL
    )
    config["refresh_interval_seconds"] = _as_int(
        config.get("refresh_interval_seconds"),
        DEFAULT_CONFIG["refresh_interval_seconds"],
        config["poll_interval_seconds"],
    )
    for key in (
        "show_viewers",
        "show_category",
        "show_elapsed_time",
        "notify_on_change",
        "use_stream_thumbnail",
        "clickable_urls",
    ):
        config[key] = _as_bool(config.get(key), DEFAULT_CONFIG[key])

    status_display = str(config.get("status_display_type") or "").strip().lower()
    config["status_display_type"] = (
        status_display if status_display in {"name", "state", "details"} else "name"
    )
    for key in ("large_image_live", "small_image_live", "large_text_live", "button_label"):
        config[key] = str(config.get(key) or "").strip()

    return config


def validate(
    config: dict, require_client_id: bool = True, require_channels: bool = True
) -> list[str]:
    problems: list[str] = []
    client_id = config.get("discord_client_id", "")
    if require_client_id and not client_id:
        problems.append(
            "discord_client_id esta vacio: crea una app en "
            "https://discord.com/developers/applications y pega su Application ID"
        )
    elif client_id and not client_id.isdigit():
        problems.append("discord_client_id debe contener solo numeros")
    if require_channels and not config.get("kick_channels"):
        problems.append("kick_channels esta vacio: agrega al menos un canal de Kick")
    return problems
