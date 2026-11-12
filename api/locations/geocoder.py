"""Typed place name to a position, using OpenStreetMap (Nominatim).

Rules from the public Nominatim usage policy (read from secondary sources,
the official page could not be opened):
- at most 1 request per second for the whole app
- a User-Agent that names the app, with a contact
- cache results
- no search-as-you-type (call this only when the user submits)
The website must also show "© OpenStreetMap contributors".

If OpenStreetMap fails, this returns UNAVAILABLE. The caller then offers the
fallback list of 50 places. Typed searches are never logged.
"""

import asyncio
import os
import time
from dataclasses import dataclass
from enum import Enum

import httpx2

from api.adapters.httpclient import create_client
from api.core.models import Place
from api.locations.malta_bounds import VIEWBOX, is_in_malta

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TIMEOUT_S = 2.0
MIN_GAP_S = 1.0
CACHE_SECONDS = 24 * 3600
CACHE_MAX_ITEMS = 500
MAX_QUERY_LENGTH = 200


class GeocodeStatus(str, Enum):
    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    OUTSIDE_MALTA = "OUTSIDE_MALTA"
    UNAVAILABLE = "UNAVAILABLE"  # OpenStreetMap failed: offer the fallback list


@dataclass(frozen=True)
class GeocodeResult:
    status: GeocodeStatus
    place: Place | None = None


def _user_agent() -> str:
    contact = os.environ.get("GEOCODER_CONTACT", "").strip()
    if contact:
        return f"fabrikam-map/1.0 ({contact})"
    return "fabrikam-map/1.0"


def _clean(query: str) -> str:
    return " ".join(query.split()).lower()[:MAX_QUERY_LENGTH]


class Geocoder:
    def __init__(self, client: httpx2.AsyncClient | None = None) -> None:
        self._client = client or create_client(TIMEOUT_S)
        self._cache: dict[str, tuple[float, GeocodeResult]] = {}
        self._gate = asyncio.Lock()
        self._last_call = 0.0

    async def close(self) -> None:
        await self._client.aclose()

    async def geocode(self, query: str) -> GeocodeResult:
        key = _clean(query)
        if not key:
            return GeocodeResult(GeocodeStatus.NOT_FOUND)

        cached = self._cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        result = await self._ask_openstreetmap(key)

        # Never cache a failure, so a short outage does not stick.
        if result.status != GeocodeStatus.UNAVAILABLE:
            if len(self._cache) >= CACHE_MAX_ITEMS:
                self._cache.clear()
            self._cache[key] = (time.monotonic() + CACHE_SECONDS, result)
        return result

    async def _wait_for_turn(self) -> None:
        """Keep at least 1 second between calls to OpenStreetMap."""
        async with self._gate:
            wait = MIN_GAP_S - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    async def _ask_openstreetmap(self, key: str) -> GeocodeResult:
        await self._wait_for_turn()
        params = {
            "q": key,
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "mt",
            "viewbox": VIEWBOX,
            "bounded": "1",
        }
        try:
            response = await self._client.get(
                NOMINATIM_URL,
                params=params,
                headers={"User-Agent": _user_agent()},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list) or not data:
                return GeocodeResult(GeocodeStatus.NOT_FOUND)
            place = Place(lat=float(data[0]["lat"]), lon=float(data[0]["lon"]))
        except (httpx2.HTTPError, ValueError, KeyError, TypeError):
            return GeocodeResult(GeocodeStatus.UNAVAILABLE)

        if not is_in_malta(place):
            return GeocodeResult(GeocodeStatus.OUTSIDE_MALTA)
        return GeocodeResult(GeocodeStatus.OK, place)
