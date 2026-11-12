"""Booking service: turns a chosen quote into one simulated booking.

Rules:
- the browser sends only a quoteId and an Idempotency-Key
- the quote must exist, belong to this user and not be expired
- the same key used twice never creates a second booking
- the provider is asked once, and the provider call is never retried
- if the provider confirms but saving fails, the save is retried once
"""

import asyncio
import re
from collections.abc import Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from api.adapters.base import ProviderAdapter, ProviderError, ProviderRateLimited
from api.core.models import Booking, PriceStatus
from api.core.quote_store import QuoteStore, has_expired
from api.data.repositories import TripRecord, TripRepository

# Safe for a Cosmos record id: no slash, backslash, question mark or hash.
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
SAVE_RETRY_DELAY_S = 0.3


class BookingError(Exception):
    """Base class. The route turns `code` into an HTTP status later."""

    code = "BOOKING_ERROR"


class InvalidIdempotencyKey(BookingError):
    code = "INVALID_IDEMPOTENCY_KEY"


class QuoteNotFound(BookingError):
    # Also used when the quote belongs to someone else, so we never reveal it.
    code = "QUOTE_NOT_FOUND"


class QuoteExpired(BookingError):
    code = "QUOTE_EXPIRED"


class QuoteNotBookable(BookingError):
    code = "QUOTE_NOT_BOOKABLE"


class IdempotencyKeyReused(BookingError):
    code = "IDEMPOTENCY_KEY_REUSED"


class ProviderUnavailable(BookingError):
    code = "PROVIDER_UNAVAILABLE"

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class TripSaveFailed(BookingError):
    """The provider confirmed, but the trip could not be saved."""

    code = "TRIP_SAVE_FAILED"

    def __init__(self, message: str, booking: Booking) -> None:
        super().__init__(message)
        self.booking = booking


@dataclass(frozen=True)
class BookingResult:
    booking: Booking
    trip: TripRecord
    already_booked: bool  # True when this key was used before


def _booking_from_trip(trip: TripRecord) -> Booking:
    return Booking(
        reference=trip.reference,
        provider_id=trip.provider_id,
        quote_id=trip.quote_id,
    )


class BookingService:
    def __init__(
        self,
        quotes: QuoteStore,
        trips: TripRepository,
        adapters: Sequence[ProviderAdapter],
    ) -> None:
        self._quotes = quotes
        self._trips = trips
        self._adapters = {adapter.provider_id: adapter for adapter in adapters}
        self._locks: dict[str, list] = {}

    @asynccontextmanager
    async def _key_lock(self, name: str):
        """One lock per user and key, so two quick clicks run one after the other."""
        entry = self._locks.setdefault(name, [asyncio.Lock(), 0])
        entry[1] += 1
        try:
            async with entry[0]:
                yield
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                self._locks.pop(name, None)

    async def book(self, *, user_id: str, quote_id: str, idempotency_key: str) -> BookingResult:
        if not KEY_PATTERN.fullmatch(idempotency_key):
            raise InvalidIdempotencyKey("the Idempotency-Key must be 8 to 64 letters, digits, - or _")

        async with self._key_lock(f"{user_id}:{idempotency_key}"):
            return await self._book_once(user_id, quote_id, idempotency_key)

    async def _book_once(self, user_id: str, quote_id: str, key: str) -> BookingResult:
        # 1. Same key used before? Give back the saved booking.
        existing = await self._trips.get(user_id, key)
        if existing is not None:
            return self._replay(existing, quote_id)

        # 2. The quote must be ours, known and still valid.
        stored = self._quotes.get(quote_id)
        if stored is None or stored.user_id != user_id:
            raise QuoteNotFound("quote not found, please search again")
        option = stored.option
        if has_expired(option):
            raise QuoteExpired("this quote has expired, please search again")
        if option.price.status == PriceStatus.UNAVAILABLE or option.price.amount_eur is None:
            raise QuoteNotBookable("this option has no price and cannot be booked")

        # 3. Ask the provider once. Never retried here.
        adapter = self._adapters.get(option.provider_id)
        if adapter is None:
            raise ProviderUnavailable("this provider is not available")
        try:
            booking = await adapter.create_booking(quote_id, key)
        except ProviderRateLimited as exc:
            raise ProviderUnavailable(
                "the provider is busy, try again shortly",
                retry_after_s=getattr(exc, "retry_after_s", None),
            ) from exc
        except (ProviderError, TimeoutError) as exc:
            raise ProviderUnavailable("the provider could not confirm the booking") from exc

        # 4. Save the trip. Retry the save once, never the provider call.
        trip = TripRecord(
            id=key,
            user_id=user_id,
            quote_id=quote_id,
            reference=booking.reference,
            provider_id=booking.provider_id,
            vehicle_class=option.vehicle_class,
            price_eur=option.price.amount_eur,
            pickup_name=stored.pickup_name,
            destination_name=stored.destination_name,
            created_at=datetime.now(timezone.utc),
        )
        return await self._save(trip, booking)

    def _replay(self, trip: TripRecord, quote_id: str) -> BookingResult:
        if trip.quote_id != quote_id:
            raise IdempotencyKeyReused("this Idempotency-Key was already used for a different quote")
        return BookingResult(_booking_from_trip(trip), trip, already_booked=True)

    async def _save(self, trip: TripRecord, booking: Booking) -> BookingResult:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                added = await self._trips.add(trip)
            except Exception as exc:  # any storage failure, for example a network error
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(SAVE_RETRY_DELAY_S)
                continue
            if added:
                return BookingResult(booking, trip, already_booked=False)
            # The key already exists: another request saved it first.
            existing = await self._trips.get(trip.user_id, trip.id)
            if existing is not None:
                return self._replay(existing, trip.quote_id)
        raise TripSaveFailed(
            "the booking was confirmed but could not be saved, retry with the same Idempotency-Key",
            booking,
        ) from last_error