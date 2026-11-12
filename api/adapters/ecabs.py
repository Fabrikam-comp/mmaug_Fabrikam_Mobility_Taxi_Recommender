"""Adapter for eCabs. The shapes are described in mocks/ecabs.py.

Login:  an API key in the X-API-Key header.
Shape:  a flat list of vehicles.
Price:  an exact amount in euros (AVAILABLE), or null (no price).
Times:  already in minutes.
"""

from datetime import datetime

from pydantic import BaseModel

from api.adapters.base import HttpAdapter, build_result, parse_body, raise_for_provider_response
from api.core.models import Booking, JourneyCriteria, Price, PriceStatus, ProviderResult, VehicleClass

_CLASSES = {"SALOON": VehicleClass.STANDARD, "MINIVAN": VehicleClass.XL}


class _Vehicle(BaseModel):
    type: str
    max_passengers: int
    max_bags: int
    price_eur: float | None
    eta_min: int
    trip_min: int
    quote_ref: str
    valid_until: datetime


class _Quote(BaseModel):
    vehicles: list[_Vehicle]


class _BookAnswer(BaseModel):
    reservation: str
    state: str


class ECabsAdapter(HttpAdapter):
    provider_id = "mock-ecabs"
    version = "1.0.0"

    def __init__(self, client, base_url, api_key: str, **kwargs):
        super().__init__(client, base_url, **kwargs)
        self._auth = {"X-API-Key": api_key}

    async def get_quotes(self, journey: JourneyCriteria) -> ProviderResult:
        started = self._clock()
        response = await self._request(
            "POST",
            "/ecabs/api/quote",
            headers=self._auth,
            json={
                "from": {"latitude": journey.pickup.lat, "longitude": journey.pickup.lon},
                "to": {"latitude": journey.destination.lat, "longitude": journey.destination.lon},
                "pax": journey.passengers,
                "bags": journey.load,
            },
        )
        raise_for_provider_response(response)
        data = parse_body(response, _Quote)
        elapsed = self._clock() - started

        options = []
        for vehicle in data.vehicles:
            vehicle_class = _CLASSES.get(vehicle.type)
            if vehicle_class is None:
                continue
            price = (
                Price(status=PriceStatus.UNAVAILABLE)
                if vehicle.price_eur is None
                else Price(status=PriceStatus.AVAILABLE, amount_eur=vehicle.price_eur)
            )
            options.append(
                self._make_option(
                    vehicle_class=vehicle_class,
                    seats=vehicle.max_passengers,
                    bag_capacity=vehicle.max_bags,
                    price=price,
                    pickup_eta_min=float(vehicle.eta_min),
                    journey_min=float(vehicle.trip_min),
                    quote_id=vehicle.quote_ref,
                    expires_at=vehicle.valid_until,
                    elapsed_s=elapsed,
                )
            )
        return build_result(self.provider_id, options, elapsed, self._slow_after_s)

    async def create_booking(self, quote_id: str, idempotency_key: str) -> Booking:
        response = await self._request(
            "POST",
            "/ecabs/api/book",
            headers=self._auth,
            json={"quote_ref": quote_id, "client_ref": idempotency_key},
        )
        raise_for_provider_response(response)
        answer = parse_body(response, _BookAnswer)
        return Booking(reference=answer.reservation, provider_id=self.provider_id, quote_id=quote_id)
