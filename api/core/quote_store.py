"""Quote store: keeps each quote after a search so a booking can find it again.

The browser sends only a quoteId. Provider, vehicle class and price always
come from the quote saved here, never from the browser.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from api.cache.ttl_cache import TTLCache
from api.core.models import TransportOption

# A quote stays a little after it expires, so the booking service can say
# "this quote expired" instead of "quote not found".
GRACE_S = 300


@dataclass(frozen=True)
class StoredQuote:
    user_id: str
    option: TransportOption
    pickup_name: str
    destination_name: str


def _as_utc(moment: datetime) -> datetime:
    # A time with no zone is treated as UTC.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def has_expired(option: TransportOption, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return _as_utc(option.expires_at) <= now


class QuoteStore:
    def __init__(self, cache: TTLCache[StoredQuote]) -> None:
        self._cache = cache

    def save(
        self,
        user_id: str,
        option: TransportOption,
        pickup_name: str,
        destination_name: str,
    ) -> None:
        seconds_left = (_as_utc(option.expires_at) -
                        datetime.now(timezone.utc)).total_seconds()
        ttl_s = seconds_left + GRACE_S
        if ttl_s <= 0:
            return
        stored = StoredQuote(user_id, option, pickup_name, destination_name)
        self._cache.set(option.quote_id, stored, ttl_s=ttl_s)

    def save_many(
        self,
        user_id: str,
        options: Iterable[TransportOption],
        pickup_name: str,
        destination_name: str,
    ) -> None:
        for option in options:
            self.save(user_id, option, pickup_name, destination_name)

    def get(self, quote_id: str) -> StoredQuote | None:
        return self._cache.get(quote_id)
