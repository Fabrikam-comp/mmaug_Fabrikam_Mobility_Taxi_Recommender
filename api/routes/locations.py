"""Place search for the journey form.

POST /locations/search: the user typed a full name and pressed Enter. We ask
OpenStreetMap once. It is a POST so the typed text never appears in a URL
or in the logs.
GET /locations/fallback: the list of common places, shown only if the
OpenStreetMap search is unavailable.

Suggestions while typing come from Geoapify, called by the browser directly,
so they do not pass through here.
"""

from fastapi import APIRouter, Depends
from pydantic import Field

from api.auth.dependencies import current_user
from api.auth.token_check import CurrentUser
from api.core.models import CamelModel, Place
from api.locations.fallback_places import FALLBACK_PLACES
from api.locations.geocoder import GeocodeStatus
from api.routes.common import RequestModel, get_services
from api.services import Services

router = APIRouter(tags=["locations"])


class LocationSearchRequest(RequestModel):
    query: str = Field(min_length=1, max_length=200)


class LocationSearchOut(CamelModel):
    status: GeocodeStatus  # OK, NOT_FOUND, OUTSIDE_MALTA or UNAVAILABLE
    place: Place | None = None  # only when status is OK


class FallbackPlaceOut(CamelModel):
    name: str
    lat: float
    lon: float


@router.post("/locations/search", response_model=LocationSearchOut)
async def search_location(
    body: LocationSearchRequest,
    user: CurrentUser = Depends(current_user),
    services: Services = Depends(get_services),
) -> LocationSearchOut:
    result = await services.geocoder.geocode(body.query)
    return LocationSearchOut(status=result.status, place=result.place)


@router.get("/locations/fallback", response_model=list[FallbackPlaceOut])
async def fallback_locations(user: CurrentUser = Depends(current_user)) -> list[FallbackPlaceOut]:
    return [FallbackPlaceOut(name=p.name, lat=p.lat, lon=p.lon) for p in FALLBACK_PLACES]
