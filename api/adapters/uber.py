"""Adapter for Uber. The shapes are described in mocks/uber.py.

Login:  a fixed server token in the Authorization header.
Shape:  nested products and estimates.
Price:  a text range like "€13-17" (we use the middle, an ESTIMATE) or
        "Metered", which means no price.
Times:  seconds, converted to minutes. expires_at is a unix timestamp.
"""

import re
from datetime import datetime, timezone
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

_CLASSES = {"uber_standard": VehicleClass.STANDARD, "uber_xl": VehicleClass.XL}
_RANGE = re.compile(r"^\u20ac\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$")


def parse_price_range(text: str) -> float | None:
    """'€13-17' gives 15.0. Anything else (like 'Metered') gives None."""
    match = _RANGE.match(text.strip())
    if match is None:
        return None
    low, high = float(match.group(1)), float(match.group(2))
    return round((low + high) / 2, 2)


class _Fare(BaseModel):
    display: str
    currency_code: Literal["EUR"]


class _Estimate(BaseModel):
    estimate_id: str
    fare: _Fare
    pickup_eta_seconds: int
    trip_duration_seconds: int
    expires_at: int


class _Product(BaseModel):
    product_id: str
    capacity: int
    luggage_capacity: int
    estimate: _Estimate


class _Estimates(BaseModel):
    products: list[_Product]


class _RequestAnswer(BaseModel):
    request_id: str
    status: str


class UberAdapter(HttpAdapter):
    provider_id = "mock-uber"
    version = "1.0.0"

    def __init__(self, client, base_url, server_token: str, **kwargs):
        super().__init__(client, base_url, **kwargs)
        self._auth = {"Authorization": f"Bearer {server_token}"}

    async def get_quotes(self, journey: JourneyCriteria) -> ProviderResult:
        started = self._clock()
        response = await self._request(
            "GET",
            "/uber/v1/estimates",
            headers=self._auth,
            params={
                "start_latitude": journey.pickup.lat,
                "start_longitude": journey.pickup.lon,
                "end_latitude": journey.destination.lat,
                "end_longitude": journey.destination.lon,
                "seat_count": journey.passengers,
                "bag_count": journey.load,
            },
        )
        raise_for_provider_response(response)
        data = parse_body(response, _Estimates)
        elapsed = self._clock() - started

        options = []
        for product in data.products:
            vehicle_class = _CLASSES.get(product.product_id)
            if vehicle_class is None:
                continue
            middle = parse_price_range(product.estimate.fare.display)
            price = (
                Price(status=PriceStatus.UNAVAILABLE)
                if middle is None
                else Price(status=PriceStatus.ESTIMATE, amount_eur=middle)
            )
            options.append(
                self._make_option(
                    vehicle_class=vehicle_class,
                    seats=product.capacity,
                    bag_capacity=product.luggage_capacity,
                    price=price,
                    pickup_eta_min=minutes_from_seconds(
                        product.estimate.pickup_eta_seconds),
                    journey_min=minutes_from_seconds(
                        product.estimate.trip_duration_seconds),
                    quote_id=product.estimate.estimate_id,
                    expires_at=datetime.fromtimestamp(
                        product.estimate.expires_at, tz=timezone.utc),
                    elapsed_s=elapsed,
                )
            )
        return build_result(self.provider_id, options, elapsed, self._slow_after_s)

    async def create_booking(self, quote_id: str, idempotency_key: str) -> Booking:
        response = await self._request(
            "POST",
            "/uber/v1/requests",
            headers={**self._auth, "X-Idempotency-Key": idempotency_key},
            json={"estimate_id": quote_id},
        )
        raise_for_provider_response(response)
        answer = parse_body(response, _RequestAnswer)
        return Booking(reference=answer.request_id, provider_id=self.provider_id, quote_id=quote_id)
