"""Adapter for Bolt. The shapes are described in mocks/bolt.py.

Login:  OAuth-style token (cached until shortly before it expires).
Price:  a range in cents. We use the middle and call it an ESTIMATE.
Times:  seconds, converted to minutes.
"""

import asyncio
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel

from api.adapters.base import (
    HttpAdapter,
    build_result,
    minutes_from_seconds,
    parse_body,
    raise_for_provider_response,
)
from api.core.models import Booking, JourneyCriteria, Price, PriceStatus, ProviderResult, VehicleClass

_CLASSES = {"bolt_standard": VehicleClass.STANDARD, "bolt_xl": VehicleClass.XL}
TOKEN_MARGIN_S = 60  # ask for a new token a minute before the old one ends


class _Token(BaseModel):
    access_token: str
    expires_in: int


class _PriceRange(BaseModel):
    min_cents: int
    max_cents: int
    currency: Literal["EUR"]


class _Category(BaseModel):
    id: str
    seats: int
    luggage: int
    price_range: _PriceRange | None
    surge_multiplier: float = 1.0
    pickup_eta_seconds: int
    ride_duration_seconds: int
    estimate_id: str
    expires_in_seconds: int


class _Estimates(BaseModel):
    categories: list[_Category]


class _BookingAnswer(BaseModel):
    booking_id: str
    status: str
    estimate_id: str


class BoltAdapter(HttpAdapter):
    provider_id = "mock-bolt"
    version = "1.0.0"

    def __init__(self, client, base_url, client_id: str, client_secret: str, **kwargs):
        super().__init__(client, base_url, **kwargs)
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_ends_at = 0.0
        self._token_lock = asyncio.Lock()  # one login at a time, even with many searches

    async def _get_token(self, rejected: str | None = None) -> str:
        async with self._token_lock:
            usable = self._token and self._clock() < self._token_ends_at - TOKEN_MARGIN_S
            if usable and self._token != rejected:
                return self._token
            response = await self._request(
                "POST",
                "/bolt/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            raise_for_provider_response(response)
            token = parse_body(response, _Token)
            self._token = token.access_token
            self._token_ends_at = self._clock() + token.expires_in
            return self._token

    async def _authorised(self, method: str, path: str, *, headers: dict | None = None, **kwargs):
        """Send with the token. If Bolt says 401, log in again once and retry."""
        token = await self._get_token()
        response = await self._request(
            method, path, headers={**(headers or {}), "Authorization": f"Bearer {token}"}, **kwargs
        )
        if response.status_code == 401:
            token = await self._get_token(rejected=token)
            response = await self._request(
                method, path, headers={**(headers or {}), "Authorization": f"Bearer {token}"}, **kwargs
            )
        return response

    async def get_quotes(self, journey: JourneyCriteria) -> ProviderResult:
        started = self._clock()
        response = await self._authorised(
            "POST",
            "/bolt/v1/rides/estimates",
            json={
                "start": {"lat": journey.pickup.lat, "lng": journey.pickup.lon},
                "end": {"lat": journey.destination.lat, "lng": journey.destination.lon},
                "passengers": journey.passengers,
                "luggage": journey.load,
            },
        )
        raise_for_provider_response(response)
        data = parse_body(response, _Estimates)
        elapsed = self._clock() - started

        options = []
        for category in data.categories:
            vehicle_class = _CLASSES.get(category.id)
            if vehicle_class is None:
                continue  # a category we do not know about
            if category.price_range is None:
                price = Price(status=PriceStatus.UNAVAILABLE)
            else:
                middle = (category.price_range.min_cents +
                          category.price_range.max_cents) / 2
                price = Price(status=PriceStatus.ESTIMATE,
                              amount_eur=round(middle / 100, 2))
            options.append(
                self._make_option(
                    vehicle_class=vehicle_class,
                    seats=category.seats,
                    bag_capacity=category.luggage,
                    price=price,
                    pickup_eta_min=minutes_from_seconds(
                        category.pickup_eta_seconds),
                    journey_min=minutes_from_seconds(
                        category.ride_duration_seconds),
                    quote_id=category.estimate_id,
                    expires_at=self._now() + timedelta(seconds=category.expires_in_seconds),
                    elapsed_s=elapsed,
                )
            )
        return build_result(self.provider_id, options, elapsed, self._slow_after_s)

    async def create_booking(self, quote_id: str, idempotency_key: str) -> Booking:
        response = await self._authorised(
            "POST",
            "/bolt/v1/bookings",
            json={"estimate_id": quote_id},
            headers={"Idempotency-Key": idempotency_key},
        )
        raise_for_provider_response(response)
        answer = parse_body(response, _BookingAnswer)
        return Booking(reference=answer.booking_id, provider_id=self.provider_id, quote_id=quote_id)
