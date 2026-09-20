from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

log = logging.getLogger("kickpresence.kick")

API_URLS = (
    "https://kick.com/api/v1/channels/{slug}",
    "https://kick.com/api/v2/channels/{slug}",
)
PUBLIC_THUMBNAIL_HOST = "images.kick.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ")


class KickError(Exception):
    pass


class ChannelNotFound(KickError):
    pass


def parse_kick_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class KickChannelInfo:
    slug: str
    username: str
    live: bool
    title: str | None


@dataclass(frozen=True)
class KickStream:
    slug: str
    username: str
    title: str
    category: str | None
    language: str | None
    viewers: int
    started_at: datetime | None
    thumbnail_url: str | None

    @property
    def url(self) -> str:
        return f"https://kick.com/{self.slug}"

    @property
    def public_thumbnail(self) -> str | None:
        url = self.thumbnail_url
        if url and len(url) <= 256 and PUBLIC_THUMBNAIL_HOST in url:
            return url
        return None


class KickClient:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Referer": "https://kick.com/",
            }
        )

    def close(self) -> None:
        self._session.close()

    def get_stream(self, slug: str) -> KickStream | None:
        data = self._fetch(slug)
        livestream = data.get("livestream")
        if not livestream or livestream.get("is_live") is False:
            return None
        return self._parse(data, livestream)

    def get_channel_info(self, slug: str) -> KickChannelInfo:
        data = self._fetch(slug)
        user = data.get("user") or {}
        livestream = data.get("livestream") or {}
        live = bool(livestream) and livestream.get("is_live") is not False
        title = None
        if live:
            title = str(livestream.get("session_title") or "").strip() or None
        return KickChannelInfo(
            slug=str(data.get("slug") or slug).strip(),
            username=str(user.get("username") or data.get("slug") or slug).strip(),
            live=live,
            title=title,
        )

    def _fetch(self, slug: str) -> dict:
        last_error: KickError | None = None
        for template in API_URLS:
            url = template.format(slug=slug)
            try:
                response = self._session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = KickError(f"Error de red consultando '{slug}': {exc}")
                continue

            if response.status_code == 404:
                raise ChannelNotFound(f"El canal '{slug}' no existe en Kick")
            if response.status_code in (403, 429):
                last_error = KickError(
                    f"Kick bloqueo la peticion de '{slug}' (HTTP {response.status_code})"
                )
                continue
            if response.status_code >= 400:
                last_error = KickError(f"HTTP {response.status_code} consultando '{slug}'")
                continue

            try:
                data = response.json()
            except ValueError:
                last_error = KickError(f"Kick devolvio una respuesta invalida para '{slug}'")
                continue

            if isinstance(data, dict) and "livestream" in data:
                return data
            last_error = KickError(f"Respuesta inesperada de Kick para '{slug}'")

        raise last_error or KickError(f"No se pudo consultar '{slug}'")

    @staticmethod
    def _parse(data: dict, livestream: dict) -> KickStream:
        categories = livestream.get("categories") or []
        category = None
        for item in categories:
            name = (item or {}).get("name")
            if name:
                category = str(name).strip()
                break

        viewers = 0
        for key in ("viewer_count", "viewers"):
            try:
                viewers = max(viewers, int(livestream.get(key) or 0))
            except (TypeError, ValueError):
                continue

        user = data.get("user") or {}
        thumbnail = livestream.get("thumbnail") or {}
        title = str(livestream.get("session_title") or "").strip()

        return KickStream(
            slug=str(data.get("slug") or livestream.get("slug") or "").strip(),
            username=str(user.get("username") or data.get("slug") or "").strip(),
            title=title or "En vivo en Kick",
            category=category,
            language=livestream.get("language"),
            viewers=max(viewers, 0),
            started_at=parse_kick_datetime(livestream.get("start_time")),
            thumbnail_url=thumbnail.get("url") or thumbnail.get("src") or None,
        )
