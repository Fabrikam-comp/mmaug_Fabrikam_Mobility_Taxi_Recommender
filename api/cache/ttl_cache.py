"""Short memory cache with expiry.

Keeps a value for a number of seconds, then forgets it. When the cache is
full, expired entries are removed first, then the oldest entries. Nothing is
written to disk.

Do not store None as a value: get() returns None for "not found".
"""

import time
from collections import OrderedDict
from typing import Callable, Generic, Hashable, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(
        self,
        *,
        ttl_s: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._clock = clock
        # key -> (expires_at, value), oldest entry first
        self._items: OrderedDict[Hashable, tuple[float, V]] = OrderedDict()

    def get(self, key: Hashable) -> V | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self._clock() >= expires_at:
            del self._items[key]  # expired, forget it
            return None
        return value

    def set(self, key: Hashable, value: V, ttl_s: float | None = None) -> None:
        """Save a value. ttl_s overrides the default time for this one entry."""
        ttl = self._ttl_s if ttl_s is None else ttl_s
        self._items.pop(key, None)  # saving again makes it the newest entry
        self._items[key] = (self._clock() + ttl, value)
        self._make_room()

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def _make_room(self) -> None:
        if len(self._items) <= self._max_entries:
            return
        now = self._clock()
        expired = [k for k, (exp, _) in self._items.items() if now >= exp]
        for key in expired:
            del self._items[key]
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)  # remove the oldest entry
