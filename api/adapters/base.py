"""The interface every provider adapter must follow (section 5.3)."""

from typing import Protocol

from api.core.models import Booking, HealthStatus, JourneyCriteria, ProviderResult


class ProviderError(Exception):
    """The provider answered with a server error, or with data that failed
    the schema check at the edge of the adapter."""


class ProviderRateLimited(Exception):
    """The provider answered 429 (too many requests)."""

    def __init__(self, retry_after_s: float | None = None):
        super().__init__("provider rate limited")
        self.retry_after_s = retry_after_s


class ProviderAdapter(Protocol):
    provider_id: str  # for example "mock-bolt"
    version: str  # semantic version, for example "1.2.0"

    async def get_quotes(self, journey: JourneyCriteria) -> ProviderResult:
        """Read-only, so it is safe to retry once."""
        ...

    async def create_booking(self, quote_id: str, idempotency_key: str) -> Booking:
        """Never retried without the same idempotency key."""
        ...

    async def health(self) -> HealthStatus: ...
