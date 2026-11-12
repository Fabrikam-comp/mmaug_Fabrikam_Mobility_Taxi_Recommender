"""Mock Bolt.

Login:    OAuth-style. POST /bolt/oauth/token with JSON
          {"grant_type": "client_credentials", "client_id": "...", "client_secret": "..."}
          returns {"access_token", "token_type": "Bearer", "expires_in"}. Then send
          "Authorization: Bearer <access_token>" on every call.
Quotes:   POST /bolt/v1/rides/estimates
          {"start": {"lat", "lng"}, "end": {"lat", "lng"}, "passengers": 3, "luggage": 2}
          returns {"categories": [...]}. Price is a RANGE in CENTS, times are in
          SECONDS, and "surge_multiplier" is sometimes above 1.0.
Booking:  POST /bolt/v1/bookings {"estimate_id": "..."} with header Idempotency-Key.
"""

import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from mocks import fault_switch, settings
from mocks.fault_switch import FaultMode
from mocks.simulation import (
    QUOTE_LIFETIME_S,
    ExpiredQuote,
    Point,
    UnknownQuote,
    build_offers,
    make_rng,
    quote_book,
)

router = APIRouter(prefix="/bolt", tags=["mock-bolt"])

TOKEN_LIFETIME_S = 3600
_tokens: dict[str, float] = {}  # token -> time it stops working


def reset_tokens() -> None:
    _tokens.clear()


class TokenRequest(BaseModel):
    grant_type: str
    client_id: str
    client_secret: str


@router.post("/oauth/token")
def issue_token(body: TokenRequest):
    client_id, client_secret = settings.bolt_credentials()
    if body.grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")
    if not (
        settings.safe_equal(body.client_id, client_id)
        and settings.safe_equal(body.client_secret, client_secret)
    ):
        raise HTTPException(status_code=401, detail="invalid_client")
    token = secrets.token_urlsafe(24)
    _tokens[token] = time.monotonic() + TOKEN_LIFETIME_S
    return {"access_token": token, "token_type": "Bearer", "expires_in": TOKEN_LIFETIME_S}


def require_token(authorization: str | None = Header(default=None)) -> None:
    token = settings.bearer_token(authorization)
    expires = _tokens.get(token) if token else None
    if expires is None or time.monotonic() >= expires:
        raise HTTPException(
            status_code=401, detail="invalid_token", headers={"WWW-Authenticate": "Bearer"}
        )


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class EstimateRequest(BaseModel):
    start: LatLng
    end: LatLng
    passengers: int = Field(ge=1, le=8)
    luggage: int = Field(ge=0, le=6)


class BookingRequest(BaseModel):
    estimate_id: str


@router.post("/v1/rides/estimates", dependencies=[Depends(require_token)])
async def estimates(body: EstimateRequest, x_mock_seed: str | None = Header(default=None)):
    mode = await fault_switch.apply_fault("bolt")
    if mode == FaultMode.BAD_DATA:
        return {"unexpected": "data"}

    rng = make_rng(x_mock_seed)
    surge = rng.choice([1.0] * 8 + [1.25, 1.5])  # now and then, prices jump
    offers = build_offers(
        "bolt",
        Point(body.start.lat, body.start.lng),
        Point(body.end.lat, body.end.lng),
        body.passengers,
        body.luggage,
        rng,
        extra_multiplier=surge,
    )

    categories = []
    for offer in offers:
        price_range = None
        if mode != FaultMode.NO_PRICE:
            price_range = {
                "min_cents": round(offer.fare_eur * 0.9 * 100),
                "max_cents": round(offer.fare_eur * 1.1 * 100),
                "currency": "EUR",
            }
        categories.append(
            {
                "id": f"bolt_{offer.vehicle_class.lower()}",
                "name": "Bolt XL" if offer.vehicle_class == "XL" else "Bolt",
                "seats": offer.seats,
                "luggage": offer.bags,
                "price_range": price_range,
                "surge_multiplier": surge,
                "pickup_eta_seconds": round(offer.pickup_eta_min * 60),
                "ride_duration_seconds": round(offer.trip_min * 60),
                "estimate_id": offer.quote_id,
                "expires_in_seconds": QUOTE_LIFETIME_S,
            }
        )
    return {"categories": categories}


@router.post("/v1/bookings", dependencies=[Depends(require_token)])
async def book(body: BookingRequest, idempotency_key: str | None = Header(default=None)):
    if not idempotency_key:
        raise HTTPException(
            status_code=400, detail="Idempotency-Key header is required")
    await fault_switch.apply_fault("bolt")
    try:
        booking = quote_book.book("bolt", body.estimate_id, idempotency_key)
    except UnknownQuote:
        raise HTTPException(status_code=404, detail="unknown estimate")
    except ExpiredQuote:
        raise HTTPException(status_code=410, detail="estimate expired")
    return {
        "booking_id": f"BLT-{booking['number']}",
        "status": "confirmed",
        "estimate_id": booking["quote_id"],
    }
