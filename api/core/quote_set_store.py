"""Quote set store: keeps one ranked result after a search.

GET /explanations/{quoteSetId} uses it to find the result it must explain.
It lives in memory only. If the app restarts, the set is gone and the page
simply hides the explanation panel (the ranking was already shown).
A set belongs to one user: asking with another user's ID gives "not found".
"""

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from api.cache.ttl_cache import TTLCache
from api.scoring.ranking import Recommendation

from .quote_store import GRACE_S

DEFAULT_TTL_S = 600  # used only when the result has no options at all


@dataclass(frozen=True)
class StoredQuoteSet:
    user_id: str
    recommendation: Recommendation
    price_labels: Mapping[str, str]  # quoteId -> price text the user saw


def _as_utc(moment: datetime) -> datetime:
    # A time with no zone is treated as UTC.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _ttl_s(recommendation: Recommendation) -> float:
    scored = recommendation.all_options or recommendation.top_options
    if not scored:
        return DEFAULT_TTL_S
    latest = max(_as_utc(item.option.expires_at) for item in scored)
    seconds_left = max(
        (latest - datetime.now(timezone.utc)).total_seconds(), 0)
    return seconds_left + GRACE_S


class QuoteSetStore:
    def __init__(self, cache: TTLCache[StoredQuoteSet]) -> None:
        self._cache = cache

    def save(
        self,
        user_id: str,
        recommendation: Recommendation,
        price_labels: Mapping[str, str] | None = None,
    ) -> str:
        """Saves the result and returns its quoteSetId (hard to guess)."""
        quote_set_id = secrets.token_urlsafe(16)
        stored = StoredQuoteSet(user_id, recommendation,
                                dict(price_labels or {}))
        self._cache.set(quote_set_id, stored, ttl_s=_ttl_s(recommendation))
        return quote_set_id

    def get(self, quote_set_id: str, user_id: str) -> StoredQuoteSet | None:
        stored = self._cache.get(quote_set_id)
        if stored is None or stored.user_id != user_id:
            return None
        return stored
