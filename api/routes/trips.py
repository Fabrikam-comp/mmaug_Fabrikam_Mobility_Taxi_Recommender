"""GET /trips and DELETE /trips: the signed-in user's own trip history.

The user ID comes from the verified token, so one user can never read or
delete another user's trips. Trips hold place names only, never coordinates.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends

from api.auth.dependencies import current_user
from api.auth.token_check import CurrentUser
from api.core.models import CamelModel, DataSource, VehicleClass
from api.routes.common import get_services
from api.services import Services

router = APIRouter(tags=["trips"])


class TripOut(CamelModel):
    reference: str
    status: Literal["CONFIRMED"]
    data_source: DataSource
    provider_id: str
    vehicle_class: VehicleClass
    price_eur: float
    pickup_name: str
    destination_name: str
    created_at: datetime


class DeleteOut(CamelModel):
    deleted: int


@router.get("/trips", response_model=list[TripOut])
async def list_trips(
    user: CurrentUser = Depends(current_user),
    services: Services = Depends(get_services),
) -> list[TripOut]:
    trips = await services.trips.list_for_user(user.user_id)
    return [
        TripOut(
            reference=t.reference,
            status=t.status,
            data_source=t.data_source,
            provider_id=t.provider_id,
            vehicle_class=t.vehicle_class,
            price_eur=t.price_eur,
            pickup_name=t.pickup_name,
            destination_name=t.destination_name,
            created_at=t.created_at,
        )
        for t in trips
    ]


@router.delete("/trips", response_model=DeleteOut)
async def delete_trips(
    user: CurrentUser = Depends(current_user),
    services: Services = Depends(get_services),
) -> DeleteOut:
    deleted = await services.trips.delete_all_for_user(user.user_id)
    return DeleteOut(deleted=deleted)
