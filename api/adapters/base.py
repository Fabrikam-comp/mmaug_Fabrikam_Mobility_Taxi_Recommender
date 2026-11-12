"""The interface every provider adapter follows, plus what they all share.

An adapter turns one provider's login, request shape, response shape and units
into the common model (api/core/models.py). Everything that is the same for
all adapters lives here, so each adapter file holds only what makes it special.
"""

import time
from datetime import datetime, timezone
from typing import Callable, Protocol, TypeVar

import httpx2
from pydantic import BaseModel, ValidationError

from api.core.models import (
    Booking,
    DataSource,
    HealthStatus,
    JourneyCriteria,
    Price,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
    TransportOption,
    VehicleClass,
)

SLOW_AFTER_S = 1.5  # an answer slower than this is marked SLOW

M = TypeVar("M", bound=BaseModel)


class ProviderError(Exception):
    """The provider answered with a server error or with data that failed
    the schema check at the edge of the adapter."""


class QuoteNotAvailable(ProviderError):
    """The provider says the quote is unknown or has expired (404 or 410)."""


class ProviderRateLimited(Exception):
    """The provider answered 429 (too many requests)."""

    def __init__(self, retry_after_s: float | None = None):
        super().__init__("provider rate limited")
        self.retry_after_s = retry_after_s


class ProviderAdapter(Protocol):
    provider_id: str  # for example "mock-bolt"
    version: str  # semantic version, for example "1.0.0"

    async def get_quotes(self, journey: JourneyCriteria) -> ProviderResult:
        """Read-only, so it is safe to retry once."""
        ...

    async def create_booking(self, quote_id: str, idempotency_key: str) -> Booking:
        """Never retried without the same idempotency key."""
        ...

    async def health(self) -> HealthStatus: ...


# ---------- shared helpers ----------

def retry_after_seconds(value: str | None) -> float | None:
    """Read a Retry-After header given in seconds. The date form is not handled."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def raise_for_provider_response(response: httpx2.Response) -> None:
    if response.status_code == 429:
        raise ProviderRateLimited(retry_after_seconds(
            response.headers.get("retry-after")))
    if response.status_code in (404, 410):
        raise QuoteNotAvailable(f"provider answered {response.status_code}")
    if response.status_code >= 400:
        raise ProviderError(f"provider answered {response.status_code}")


def parse_body(response: httpx2.Response, model: type[M]) -> M:
    """The schema check at the edge: bad data is rejected, never passed on."""
    try:
        return model.model_validate(response.json())
    except (ValueError, ValidationError) as error:
        raise ProviderError("provider sent data in the wrong shape") from error


def minutes_from_seconds(seconds: float) -> float:
    return round(seconds / 60, 1)


def build_result(
    provider_id: str,
    options: list[TransportOption],
    elapsed_s: float,
    slow_after_s: float = SLOW_AFTER_S,
) -> ProviderResult:
    if options and all(option.provider_status == ProviderStatus.NO_PRICE for option in options):
        status = ProviderStatus.NO_PRICE
    elif elapsed_s > slow_after_s:
        status = ProviderStatus.SLOW
    else:
        status = ProviderStatus.OK
    return ProviderResult(provider_id=provider_id, status=status, options=options)


class HttpAdapter:
    """Convenience base class: holds the shared client and settings, sends
    requests with the same error handling, builds options, and does health checks."""

    provider_id: str
    version: str

    def __init__(
        self,
        client: httpx2.AsyncClient,
        base_url: str,
        *,
        timeout_s: float = 2.0,
        slow_after_s: float = SLOW_AFTER_S,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
    ):
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._slow_after_s = slow_after_s
        self._clock = clock
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def _request(self, method: str, path: str, **kwargs) -> httpx2.Response:
        """A slow provider becomes a TimeoutError (which is not retried).
        Any other network problem becomes a ProviderError (retried once)."""
        try:
            return await self._client.request(
                method, f"{self._base_url}{path}", timeout=self._timeout_s, **kwargs
            )
        except httpx2.TimeoutException as error:
            raise TimeoutError(
                f"{self.provider_id} did not answer in time") from error
        except httpx2.HTTPError as error:
            raise ProviderError(
                f"could not reach {self.provider_id}") from error

    def _make_option(
        self,
        *,
        vehicle_class: VehicleClass,
        seats: int,
        bag_capacity: int,
        price: Price,
        pickup_eta_min: float,
        journey_min: float,
        quote_id: str,
        expires_at: datetime,
        elapsed_s: float,
    ) -> TransportOption:
        if price.status == PriceStatus.UNAVAILABLE:
            status = ProviderStatus.NO_PRICE
        elif elapsed_s > self._slow_after_s:
            status = ProviderStatus.SLOW
        else:
            status = ProviderStatus.OK
        return TransportOption(
            provider_id=self.provider_id,
            adapter_version=self.version,
            data_source=DataSource.SIMULATED,
            vehicle_class=vehicle_class,
            seats=seats,
            bag_capacity=bag_capacity,
            price=price,
            pickup_eta_min=pickup_eta_min,
            journey_min=journey_min,
            quote_id=quote_id,
            expires_at=expires_at,
            provider_status=status,
        )

    async def health(self) -> HealthStatus:
        started = self._clock()
        try:
            response = await self._client.get(f"{self._base_url}/health", timeout=self._timeout_s)
        except httpx2.HTTPError:
            return HealthStatus(provider_id=self.provider_id, status=ProviderStatus.UNAVAILABLE)
        latency_ms = round((self._clock() - started) * 1000, 1)
        status = ProviderStatus.OK if response.status_code == 200 else ProviderStatus.UNAVAILABLE
        return HealthStatus(provider_id=self.provider_id, status=status, latency_ms=latency_ms)
