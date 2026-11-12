"""Mock eCabs.

Login:    an API key in the X-API-Key header.
Quotes:   POST /ecabs/api/quote
          {"from": {"latitude", "longitude"}, "to": {...}, "pax": 3, "bags": 2}
          returns {"vehicles": [...]}. The list is FLAT, price is in EUROS, times
          are in MINUTES, and "price_eur" can be null (no price), about one time
          in ten even without a fault.
Booking:  POST /ecabs/api/book {"quote_ref": "...", "client_ref": "..."}.
          client_ref is the idempotency key.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

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

router = APIRouter(prefix="/ecabs", tags=["mock-ecabs"])

RANDOM_NO_PRICE_CHANCE = 0.1


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.safe_equal(x_api_key, settings.ecabs_api_key()):
        raise HTTPException(status_code=401, detail="invalid api key")


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class QuoteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_location: Coordinate = Field(alias="from")
    to_location: Coordinate = Field(alias="to")
    pax: int = Field(ge=1, le=8)
    bags: int = Field(ge=0, le=6)


class BookRequest(BaseModel):
    quote_ref: str
    client_ref: str


@router.post("/api/quote", dependencies=[Depends(require_api_key)])
async def quote(body: QuoteRequest, x_mock_seed: str | None = Header(default=None)):
    mode = await fault_switch.apply_fault("ecabs")
    if mode == FaultMode.BAD_DATA:
        return {"unexpected": "data"}

    rng = make_rng(x_mock_seed)
    offers = build_offers(
        "ecabs",
        Point(body.from_location.latitude, body.from_location.longitude),
        Point(body.to_location.latitude, body.to_location.longitude),
        body.pax,
        body.bags,
        rng,
    )

    vehicles = []
    for offer in offers:
        no_price = mode == FaultMode.NO_PRICE or rng.random() < RANDOM_NO_PRICE_CHANCE
        vehicles.append(
            {
                "vehicle_id": f"ecabs_{'minivan' if offer.vehicle_class == 'XL' else 'saloon'}",
                "type": "MINIVAN" if offer.vehicle_class == "XL" else "SALOON",
                "max_passengers": offer.seats,
                "max_bags": offer.bags,
                "price_eur": None if no_price else offer.fare_eur,
                "eta_min": round(offer.pickup_eta_min),
                "trip_min": round(offer.trip_min),
                "quote_ref": offer.quote_id,
                "valid_until": offer.expires_at.isoformat(),
            }
        )
    return {"vehicles": vehicles}


@router.post("/api/book", dependencies=[Depends(require_api_key)])
async def book(body: BookRequest):
    await fault_switch.apply_fault("ecabs")
    try:
        booking = quote_book.book("ecabs", body.quote_ref, body.client_ref)
    except UnknownQuote:
        raise HTTPException(status_code=404, detail="unknown quote")
    except ExpiredQuote:
        raise HTTPException(status_code=410, detail="quote expired")
    return {"reservation": f"ECB-{booking['number']}", "state": "RESERVED"}
