"""Ask every provider for quotes at the same time.

- All providers are called in parallel.
- Each call has its own timeout (1.5 to 2 s) inside an overall budget (2.5 s).
- A provider whose circuit breaker is open is skipped instantly.
- A timeout is not retried. A server error or bad data is retried once, and
  only if time remains. A 429 is not retried inside the request.
- Bookings are not handled here. They are never retried without the same
  idempotency key.
"""

import asyncio
import time
from typing import Callable, Mapping, Sequence

from api.adapters.base import ProviderAdapter, ProviderRateLimited
from api.core.circuit_breaker import CircuitBreaker
from api.core.models import (
    FailureReason,
    JourneyCriteria,
    ProviderResult,
    ProviderStatus,
    TransportOption,
)

PER_PROVIDER_TIMEOUT_S = 1.0
OVERALL_BUDGET_S = 2.5


def _failed(provider_id: str, reason: FailureReason) -> ProviderResult:
    return ProviderResult(
        provider_id=provider_id,
        status=ProviderStatus.UNAVAILABLE,
        reason=reason,
    )


async def _quote_one(
    adapter: ProviderAdapter,
    journey: JourneyCriteria,
    breaker: CircuitBreaker,
    per_provider_timeout_s: float,
    deadline: float,
    clock: Callable[[], float],
) -> ProviderResult:
    provider_id = adapter.provider_id
    if not breaker.allow_request():
        return _failed(provider_id, FailureReason.CIRCUIT_OPEN)

    for attempt in (1, 2):
        time_left = deadline - clock()
        if time_left <= 0:
            breaker.record_failure()
            return _failed(provider_id, FailureReason.TIMEOUT)
        try:
            result = await asyncio.wait_for(
                adapter.get_quotes(journey),
                timeout=min(per_provider_timeout_s, time_left),
            )
        except TimeoutError:
            breaker.record_failure()
            return _failed(provider_id, FailureReason.TIMEOUT)
        except ProviderRateLimited as error:
            # Busy but alive, so this does not count against the breaker.
            breaker.record_success()
            return ProviderResult(
                provider_id=provider_id,
                status=ProviderStatus.RATE_LIMITED,
                reason=FailureReason.RATE_LIMITED,
                retry_after_s=error.retry_after_s,
            )
        except Exception:
            if attempt == 1 and clock() < deadline:
                continue  # retry once, because time remains
            breaker.record_failure()
            return _failed(provider_id, FailureReason.ERROR)
        else:
            breaker.record_success()
            return result

    return _failed(provider_id, FailureReason.ERROR)


async def collect_quotes(
    journey: JourneyCriteria,
    adapters: Sequence[ProviderAdapter],
    breakers: Mapping[str, CircuitBreaker],
    *,
    per_provider_timeout_s: float = PER_PROVIDER_TIMEOUT_S,
    overall_budget_s: float = OVERALL_BUDGET_S,
    clock: Callable[[], float] = time.monotonic,
) -> list[ProviderResult]:
    deadline = clock() + overall_budget_s
    results = await asyncio.gather(
        *(
            _quote_one(
                adapter,
                journey,
                breakers[adapter.provider_id],
                per_provider_timeout_s,
                deadline,
                clock,
            )
            for adapter in adapters
        )
    )
    return list(results)


def all_options(results: Sequence[ProviderResult]) -> list[TransportOption]:
    return [option for result in results for option in result.options]
