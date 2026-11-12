"""Fetches the daily euro exchange rates and keeps the last good copy in memory.

Order of tries: Frankfurter (pinned to the ECB), then the ECB's own XML file.
New rates must pass rates_are_sane. If every source fails, the last good rates
are kept. After 3 days, is_stale (in converter.py) makes prices show in EUR only.
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET

from api.currency.converter import DISPLAY_CURRENCIES, Rates, is_stale, rates_are_sane

if TYPE_CHECKING:
    import httpx2

logger = logging.getLogger(__name__)

# Frankfurter v2. "providers=ECB" asks for the European Central Bank's own rates.
FRANKFURTER_URL = "https://api.frankfurter.dev/v2/rates"
# The ECB's daily file, the backup named in the proposal.
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

REFRESH_AFTER_S = 12 * 60 * 60  # fetch again when the saved rates are older than this
RETRY_AFTER_FAILURE_S = 15 * 60  # wait this long after a failed attempt


def _positive_finite(value: object) -> float:
    """Turn a value into a float, or raise ValueError if it is not a usable rate."""
    rate = float(value)  # type: ignore[arg-type]
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("rate is not a positive number")
    return rate


def parse_frankfurter(rows: object) -> Rates:
    """Frankfurter v2 returns a flat list: one row per currency with
    date, base, quote and rate. The ECB date is the oldest date in the rows."""
    if not isinstance(rows, list):
        raise ValueError("Frankfurter reply is not a list")
    per_eur: dict[str, float] = {}
    days: list[date] = []
    for row in rows:
        if row["base"] != "EUR":
            raise ValueError("Frankfurter row has a base other than EUR")
        code = row["quote"]
        if code not in DISPLAY_CURRENCIES:
            continue  # for example the EUR to EUR row
        per_eur[code] = _positive_finite(row["rate"])
        days.append(date.fromisoformat(row["date"]))
    if not days:
        raise ValueError("Frankfurter reply has no display currencies")
    # The oldest date is the safe choice for the 3-day stale rule.
    return Rates(as_of=min(days), per_eur=per_eur)


def _local_name(tag: str) -> str:
    """Remove the XML namespace, so '{ns}Cube' becomes 'Cube'."""
    return tag.rsplit("}", 1)[-1]


def parse_ecb_xml(content: bytes) -> Rates:
    """The ECB file has one Cube with a time (the date) that holds one Cube
    per currency, each with a currency code and a rate."""
    root: Element = SafeET.fromstring(content)
    as_of: date | None = None
    per_eur: dict[str, float] = {}
    for element in root.iter():
        if _local_name(element.tag) != "Cube":
            continue
        attributes = element.attrib
        if "time" in attributes:
            as_of = date.fromisoformat(attributes["time"])
        elif "currency" in attributes and "rate" in attributes:
            code = attributes["currency"]
            if code in DISPLAY_CURRENCIES:
                per_eur[code] = _positive_finite(attributes["rate"])
    if as_of is None or not per_eur:
        raise ValueError("ECB file has no date or no display currencies")
    return Rates(as_of=as_of, per_eur=per_eur)


class RatesProvider:
    """Hands out the current rates. The caller owns the HTTP client
    (create it once at startup with adapters.httpclient.create_client)."""

    def __init__(
        self,
        client: "httpx2.AsyncClient",
        *,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._client = client
        self._clock = clock
        self._today = today
        self._rates: Rates | None = None
        self._saved_at = 0.0  # clock time when the saved rates arrived
        self._retry_not_before = 0.0  # no new attempt before this clock time
        self._lock = asyncio.Lock()

    async def get_rates(self) -> Rates | None:
        """Returns the last good rates, or None if there never were any.
        The caller passes the result to convert_from_eur, which decides
        if the rates are too old."""
        if self._is_fresh() or self._in_cooldown():
            return self._rates
        async with self._lock:
            # Another request may have finished a fetch while this one waited.
            if self._is_fresh() or self._in_cooldown():
                return self._rates
            await self._refresh()
        return self._rates

    def _is_fresh(self) -> bool:
        return self._rates is not None and (self._clock() - self._saved_at) < REFRESH_AFTER_S

    def _in_cooldown(self) -> bool:
        return self._clock() < self._retry_not_before

    async def _refresh(self) -> None:
        # Old rates are only a fair yardstick while they are still usable.
        # After 3 days they are not shown anyway, so a real market move
        # must not lock new rates out.
        previous = self._rates
        if previous is not None and is_stale(previous, self._today()):
            previous = None

        sources: tuple[tuple[str, Callable[[], Awaitable[Rates]]], ...] = (
            ("frankfurter", self._fetch_frankfurter),
            ("ecb", self._fetch_ecb),
        )
        for name, fetch in sources:
            try:
                new_rates = await fetch()
            except Exception as error:  # any failure means: try the next source
                logger.warning("rates source %s failed: %s", name, type(error).__name__)
                continue
            if not rates_are_sane(new_rates, previous):
                logger.warning("rates source %s gave rates that failed the sanity check", name)
                continue
            self._rates = new_rates
            self._saved_at = self._clock()
            self._retry_not_before = 0.0
            logger.info("rates updated from %s for %s", name, new_rates.as_of)
            return

        self._retry_not_before = self._clock() + RETRY_AFTER_FAILURE_S
        logger.warning("all rate sources failed; keeping the last good rates")

    async def _fetch_frankfurter(self) -> Rates:
        response = await self._client.get(
            FRANKFURTER_URL,
            params={
                "base": "EUR",
                "quotes": ",".join(DISPLAY_CURRENCIES),
                "providers": "ECB",
            },
        )
        if response.status_code != 200:
            raise ValueError(f"Frankfurter returned status {response.status_code}")
        return parse_frankfurter(response.json())

    async def _fetch_ecb(self) -> Rates:
        response = await self._client.get(ECB_URL)
        if response.status_code != 200:
            raise ValueError(f"ECB returned status {response.status_code}")
        return parse_ecb_xml(response.content)