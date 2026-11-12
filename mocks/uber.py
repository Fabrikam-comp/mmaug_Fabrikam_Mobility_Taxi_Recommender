"""Mock Uber.

Login:    a fixed server token. Send "Authorization: Bearer <server token>".
Quotes:   GET /uber/v1/estimates?start_latitude=&start_longitude=&end_latitude=
          &end_longitude=&seat_count=3&bag_count=2
          returns {"products": [{... "estimate": {...}}]}. The shape is NESTED.
          The price is a text RANGE like "€13-17" (or "Metered" when there is no
          price). Times are in SECONDS and "expires_at" is a unix timestamp.
Booking:  POST /uber/v1/requests {"estimate_id": "..."} with header X-Idempotency-Key.
"""

import math

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from mocks import fault_switch, settings
from mocks.fault_switch import FaultMode
from mocks.simulation import (
    ExpiredQuote,
    Point,
    UnknownQuote,
    build_offers,
    make_rng,
    quote_book,
)

router = APIRouter(prefix="/uber", tags=["mock-uber"])


def require_server_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.safe_equal(settings.bearer_token(authorization), settings.uber_token()):
        raise HTTPException(
            status_code=401, detail="unauthorized", headers={"WWW-Authenticate": "Bearer"}
        )


class RequestBody(BaseModel):
    estimate_id: str


@router.get("/v1/estimates", dependencies=[Depends(require_server_token)])
async def estimates(
    start_latitude: float = Query(ge=-90, le=90),
    start_longitude: float = Query(ge=-180, le=180),
    end_latitude: float = Query(ge=-90, le=90),
    end_longitude: float = Query(ge=-180, le=180),
    seat_count: int = Query(default=1, ge=1, le=8),
    bag_count: int = Query(default=0, ge=0, le=6),
    x_mock_seed: str | None = Header(default=None),
):
    mode = await fault_switch.apply_fault("uber")
    if mode == FaultMode.BAD_DATA:
        return {"unexpected": "data"}

    rng = make_rng(x_mock_seed)
    offers = build_offers(
        "uber",
        Point(start_latitude, start_longitude),
        Point(end_latitude, end_longitude),
        seat_count,
        bag_count,
        rng,
    )

    products = []
    for offer in offers:
        if mode == FaultMode.NO_PRICE:
            display = "Metered"
        else:
            low = math.floor(offer.fare_eur * 0.9)
            high = math.ceil(offer.fare_eur * 1.1)
            display = f"\u20ac{low}-{high}"
        products.append(
            {
                "product_id": f"uber_{offer.vehicle_class.lower()}",
                "display_name": "UberXL" if offer.vehicle_class == "XL" else "UberX",
                "capacity": offer.seats,
                "luggage_capacity": offer.bags,
                "estimate": {
                    "estimate_id": offer.quote_id,
                    "fare": {"display": display, "currency_code": "EUR"},
                    "pickup_eta_seconds": round(offer.pickup_eta_min * 60),
                    "trip_duration_seconds": round(offer.trip_min * 60),
                    "expires_at": int(offer.expires_at.timestamp()),
                },
            }
        )
    return {"products": products}


@router.post("/v1/requests", dependencies=[Depends(require_server_token)])
async def create_request(
    body: RequestBody, x_idempotency_key: str | None = Header(default=None)
):
    if not x_idempotency_key:
        raise HTTPException(
            status_code=400, detail="X-Idempotency-Key header is required")
    await fault_switch.apply_fault("uber")
    try:
        booking = quote_book.book("uber", body.estimate_id, x_idempotency_key)
    except UnknownQuote:
        raise HTTPException(status_code=404, detail="unknown estimate")
    except ExpiredQuote:
        raise HTTPException(status_code=410, detail="estimate expired")
    return {"request_id": f"UBR-{booking['number']}", "status": "accepted"}
