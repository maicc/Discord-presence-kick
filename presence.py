from __future__ import annotations

import logging
import time

from pypresence import Presence
from pypresence.exceptions import (
    ConnectionTimeout,
    DiscordError,
    DiscordNotFound,
    InvalidID,
    InvalidPipe,
    PipeClosed,
    PyPresenceException,
    ResponseTimeout,
    ServerError,
)
from pypresence.types import StatusDisplayType

log = logging.getLogger("kickpresence.presence")

MAX_DETAILS = 128
MAX_BUTTON_LABEL = 32

STATUS_DISPLAY_TYPES = {
    "name": StatusDisplayType.NAME,
    "state": StatusDisplayType.STATE,
    "details": StatusDisplayType.DETAILS,
}

UNREACHABLE_ERRORS = (
    DiscordNotFound,
    InvalidPipe,
    ConnectionTimeout,
    ResponseTimeout,
    PipeClosed,
    ConnectionResetError,
    BrokenPipeError,
    OSError,
    PyPresenceException,
)


class PresenceConfigError(Exception):
    pass


def truncate(text: object, limit: int = MAX_DETAILS) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


class PresenceManager:
    def __init__(self, client_id: str, retry_delay: float = 15.0) -> None:
        self.client_id = client_id
        self.retry_delay = retry_delay
        self._rpc: Presence | None = None
        self._retry_at = 0.0
        self._last_problem: str | None = None

    @property
    def connected(self) -> bool:
        return self._rpc is not None

    def _report(self, message: str) -> None:
        if message != self._last_problem:
            log.warning(message)
            self._last_problem = message

    def _connect(self) -> bool:
        if self._rpc is not None:
            return True
        if time.monotonic() < self._retry_at:
            return False
        try:
            rpc = Presence(self.client_id)
            rpc.connect()
        except InvalidID as exc:
            raise PresenceConfigError(
                f"Discord rechazo el client id '{self.client_id}'. "
                "Verifica el Application ID en https://discord.com/developers/applications"
            ) from exc
        except UNREACHABLE_ERRORS as exc:
            self._retry_at = time.monotonic() + self.retry_delay
            self._report(
                f"No se pudo conectar a Discord ({exc.__class__.__name__}). "
                f"Reintento en {self.retry_delay:.0f}s"
            )
            return False
        self._rpc = rpc
        self._retry_at = 0.0
        self._last_problem = None
        log.info("Conectado a Discord (client id %s)", self.client_id)
        return True

    def _send(self, payload: dict) -> None:
        assert self._rpc is not None
        self._rpc.update(
            details=payload.get("details"),
            state=payload.get("state"),
            start=payload.get("start"),
            large_image=payload.get("large_image"),
            large_text=payload.get("large_text"),
            small_image=payload.get("small_image"),
            small_text=payload.get("small_text"),
            buttons=payload.get("buttons"),
            status_display_type=STATUS_DISPLAY_TYPES.get(
                str(payload.get("status_display_type") or "name").lower()
            ),
            details_url=payload.get("details_url"),
            large_url=payload.get("large_url"),
        )

    def update(self, payload: dict) -> bool:
        if not self._connect():
            return False
        try:
            self._send(payload)
        except (ServerError, DiscordError) as exc:
            if payload.get("large_image") or payload.get("small_image"):
                without_images = {
                    **payload,
                    "large_image": None,
                    "large_text": None,
                    "small_image": None,
                    "small_text": None,
                }
                try:
                    self._send(without_images)
                except UNREACHABLE_ERRORS as retry_exc:
                    self._report(f"Discord rechazo la presencia: {retry_exc}")
                    self._teardown()
                    return False
                self._report(
                    f"Discord rechazo el payload original ({exc}); "
                    "se envio la presencia sin imagenes. Sube los assets en el Developer Portal"
                )
                return True
            self._report(f"Discord rechazo la presencia: {exc}")
            self._teardown()
            return False
        except UNREACHABLE_ERRORS as exc:
            self._report(
                f"Se perdio la conexion con Discord ({exc.__class__.__name__}); se reconectara"
            )
            self._teardown()
            return False
        self._last_problem = None
        return True

    def clear(self) -> bool:
        if self._rpc is None:
            return False
        try:
            self._rpc.clear()
        except UNREACHABLE_ERRORS:
            self._teardown()
            return False
        return True

    def close(self) -> None:
        self._teardown()

    def _teardown(self) -> None:
        rpc, self._rpc = self._rpc, None
        if rpc is None:
            return
        try:
            rpc.close()
        except Exception:
            try:
                rpc.loop.close()
            except Exception:
                pass
