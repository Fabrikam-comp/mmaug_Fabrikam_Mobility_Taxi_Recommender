"""Circuit breaker (section 5.4).

Opens after 5 failures in a row, or when half of the last 20 calls failed.
While open, calls are skipped instantly. After 30 seconds one trial call is
allowed: if it works the breaker closes, if it fails the breaker opens again.
"""

import time
from collections import deque
from enum import Enum
from typing import Callable


class CircuitState(str, Enum):
    CLOSED = "CLOSED"  # normal, calls allowed
    OPEN = "OPEN"  # calls skipped
    HALF_OPEN = "HALF_OPEN"  # cool-down over, one trial call allowed


class CircuitBreaker:
    def __init__(
        self,
        *,
        consecutive_failures: int = 5,
        failure_rate: float = 0.5,
        window_size: int = 20,
        cooldown_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._consecutive_limit = consecutive_failures
        self._failure_rate = failure_rate
        self._window_size = window_size
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._results: deque[bool] = deque(
            maxlen=window_size)  # True = success
        self._consecutive = 0
        self._opened_at: float | None = None
        self._trial_in_flight = False

    @property
    def state(self) -> CircuitState:
        if self._opened_at is None:
            return CircuitState.CLOSED
        if self._clock() - self._opened_at >= self._cooldown_s:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            return False
        # Half open: let exactly one trial call through.
        if self._trial_in_flight:
            return False
        self._trial_in_flight = True
        return True

    def record_success(self) -> None:
        state = self.state
        if state == CircuitState.OPEN:
            return  # a late answer from before the breaker opened
        if state == CircuitState.HALF_OPEN:
            self._reset()
            return
        self._results.append(True)
        self._consecutive = 0

    def record_failure(self) -> None:
        state = self.state
        if state == CircuitState.OPEN:
            return
        if state == CircuitState.HALF_OPEN:
            self._trial_in_flight = False
            self._opened_at = self._clock()  # trial failed, open again
            return
        self._results.append(False)
        self._consecutive += 1
        if self._should_open():
            self._opened_at = self._clock()

    def _should_open(self) -> bool:
        if self._consecutive >= self._consecutive_limit:
            return True
        if len(self._results) == self._window_size:
            failures = self._results.count(False)
            return failures / self._window_size >= self._failure_rate
        return False

    def _reset(self) -> None:
        self._results.clear()
        self._consecutive = 0
        self._opened_at = None
        self._trial_in_flight = False
