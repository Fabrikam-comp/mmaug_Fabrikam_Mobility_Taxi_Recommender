"""POST /bookings: create a simulated booking.

Needs a signed-in user, the 'confirmed' flag and an Idempotency-Key header.
The browser sends only the quoteId. Provider, vehicle and price come from the
quote the server saved, never from the browser.
"""

import math
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import Field

from api.auth.dependencies import current_user
from api.auth.token_check import CurrentUser
from api.core.booking_service import BookingError, ProviderUnavailable, TripSaveFailed
from api.core.models import CamelModel, DataSource, VehicleClass
from api.data.repositories import TripRecord
from api.routes.common import RequestModel, get_services, problem
from api.services import Services

router = APIRouter(tags=["bookings"])

STATUS_FOR_CODE = {
    "INVALID_IDEMPOTENCY_KEY": 400,
    "QUOTE_NOT_FOUND": 404,
    "QUOTE_EXPIRED": 410,
    "QUOTE_NOT_BOOKABLE": 422,
    "IDEMPOTENCY_KEY_REUSED": 409,
    "PROVIDER_UNAVAILABLE": 503,
    "TRIP_SAVE_FAILED": 503,
}


class BookingRequest(RequestModel):
    quote_id: str = Field(min_length=1, max_length=100)
    confirmed: bool
    # Shown on the confirmation screen. Nothing is charged and it is not stored.
    payment_method: Literal["CARD_SIMULATED", "CASH"] | None = None


class BookingOut(CamelModel):
    reference: str
    status: Literal["CONFIRMED"]
    data_source: DataSource
    provider_id: str
    vehicle_class: VehicleClass
    price_eur: float
    pickup_name: str
    destination_name: str
    created_at: datetime
    already_booked: bool  # True when the same Idempotency-Key was used before


def booking_out(trip: TripRecord, already_booked: bool) -> BookingOut:
    return BookingOut(
        reference=trip.reference,
        status=trip.status,
        data_source=trip.data_source,
        provider_id=trip.provider_id,
        vehicle_class=trip.vehicle_class,
        price_eur=trip.price_eur,
        pickup_name=trip.pickup_name,
        destination_name=trip.destination_name,
        created_at=trip.created_at,
        already_booked=already_booked,
    )


@router.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(
    body: BookingRequest,
    response: Response,
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(current_user),
    services: Services = Depends(get_services),
) -> BookingOut:
    if not body.confirmed:
        raise HTTPException(
            status_code=400,
            detail=problem("CONFIRMATION_REQUIRED",
                           "the user must confirm the booking"),
        )
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail=problem("INVALID_IDEMPOTENCY_KEY",
                           "the Idempotency-Key header is required"),
        )

    try:
        result = await services.booking.book(
            user_id=user.user_id,
            quote_id=body.quote_id,
            idempotency_key=idempotency_key,
        )
    except BookingError as exc:
        extra: dict = {}
        headers = None
        if isinstance(exc, ProviderUnavailable) and exc.retry_after_s:
            headers = {"Retry-After": str(math.ceil(exc.retry_after_s))}
        if isinstance(exc, TripSaveFailed):
            # so the user can quote it
            extra["reference"] = exc.booking.reference
        raise HTTPException(
            status_code=STATUS_FOR_CODE.get(exc.code, 500),
            detail=problem(exc.code, str(exc), **extra),
            headers=headers,
        ) from exc

    if result.already_booked:
        response.status_code = 200  # the booking already existed, nothing new was created
    return booking_out(result.trip, result.already_booked)
