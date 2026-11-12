"""Trip storage. One contract, two versions: Cosmos DB and in memory.

A saved trip holds place NAMES only, never coordinates. The record id is the
idempotency key, and the partition key is /userId, so one user can never
read another user's trips. The 90 day deletion is the container's own
Time to Live setting (7776000 seconds), so no ttl is set on each item.
"""

from datetime import datetime
from typing import Literal, Protocol

from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError

from api.core.models import CamelModel, DataSource, VehicleClass


class TripRecord(CamelModel):
    id: str  # the idempotency key
    user_id: str  # hashed user ID, never an email
    quote_id: str
    reference: str
    provider_id: str
    vehicle_class: VehicleClass
    price_eur: float
    pickup_name: str
    destination_name: str
    status: Literal["CONFIRMED"] = "CONFIRMED"
    data_source: DataSource = DataSource.SIMULATED
    created_at: datetime


class TripRepository(Protocol):
    async def get(self, user_id: str, idempotency_key: str) -> TripRecord | None: ...

    async def add(self, trip: TripRecord) -> bool:
        """Save a trip. Returns False if this key already exists for the user."""
        ...

    async def list_for_user(self, user_id: str) -> list[TripRecord]: ...

    async def delete_all_for_user(self, user_id: str) -> int: ...


class InMemoryTripRepository:
    """For tests and for working before Cosmos is connected."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], TripRecord] = {}

    async def get(self, user_id: str, idempotency_key: str) -> TripRecord | None:
        return self._items.get((user_id, idempotency_key))

    async def add(self, trip: TripRecord) -> bool:
        key = (trip.user_id, trip.id)
        if key in self._items:
            return False
        self._items[key] = trip
        return True

    async def list_for_user(self, user_id: str) -> list[TripRecord]:
        trips = [t for (owner, _), t in self._items.items() if owner == user_id]
        return sorted(trips, key=lambda t: t.created_at, reverse=True)

    async def delete_all_for_user(self, user_id: str) -> int:
        keys = [k for k in self._items if k[0] == user_id]
        for key in keys:
            del self._items[key]
        return len(keys)


class CosmosTripRepository:
    def __init__(self, container) -> None:
        self._container = container

    async def get(self, user_id: str, idempotency_key: str) -> TripRecord | None:
        try:
            item = await self._container.read_item(item=idempotency_key, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None
        return TripRecord.model_validate(item)

    async def add(self, trip: TripRecord) -> bool:
        body = trip.model_dump(by_alias=True, mode="json")
        try:
            await self._container.create_item(body=body)
        except CosmosResourceExistsError:
            return False
        return True

    async def list_for_user(self, user_id: str) -> list[TripRecord]:
        items = self._container.query_items(
            query="SELECT * FROM c WHERE c.userId = @user ORDER BY c.createdAt DESC",
            parameters=[{"name": "@user", "value": user_id}],
            partition_key=user_id,
        )
        return [TripRecord.model_validate(item) async for item in items]

    async def delete_all_for_user(self, user_id: str) -> int:
        items = self._container.query_items(
            query="SELECT c.id FROM c WHERE c.userId = @user",
            parameters=[{"name": "@user", "value": user_id}],
            partition_key=user_id,
        )
        ids = [item["id"] async for item in items]
        deleted = 0
        for item_id in ids:
            try:
                await self._container.delete_item(item=item_id, partition_key=user_id)
                deleted += 1
            except CosmosResourceNotFoundError:
                pass  # already removed, for example by the 90 day expiry
        return deleted