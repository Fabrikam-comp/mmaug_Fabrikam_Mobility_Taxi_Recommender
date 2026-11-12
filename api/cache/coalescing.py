"""Request coalescing.

If the same search arrives while an identical one is still running, the
second caller waits for the first caller's result instead of starting a
second provider call. When the work finishes, the entry is removed, so the
next search starts fresh (the TTL cache is what keeps results for a while).

If the work fails, every caller waiting for it gets the same failure.
If one caller gives up (is cancelled), the work keeps running for the others.
"""

import asyncio
from typing import Any, Callable, Coroutine, Hashable, TypeVar

T = TypeVar("T")


class Coalescer:
    def __init__(self) -> None:
        self._in_flight: dict[Hashable, asyncio.Task[Any]] = {}

    async def run(
        self,
        key: Hashable,
        work: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Run work() once per key at a time. Others with the same key share it."""
        task = self._in_flight.get(key)
        if task is None:
            task = asyncio.create_task(work())
            self._in_flight[key] = task
            task.add_done_callback(lambda t, k=key: self._finish(k, t))
        # shield: a caller that gives up must not cancel the shared work
        return await asyncio.shield(task)

    def _finish(self, key: Hashable, task: asyncio.Task[Any]) -> None:
        if self._in_flight.get(key) is task:
            del self._in_flight[key]
        if not task.cancelled():
            task.exception()  # mark as read, so Python does not warn about it
