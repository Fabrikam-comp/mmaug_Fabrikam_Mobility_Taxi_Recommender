"""Cosmos DB connection: one shared client for the whole app.

Settings come from environment variables (in Azure they are App Service
settings, copied from GitHub secrets by the Deploy workflow):
  COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DATABASE, COSMOS_CONTAINER_TRIPS

If COSMOS_KEY is empty, the app signs in with its managed identity instead
(needs the azure-identity package and a data role assigned by an admin).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from azure.cosmos.aio import CosmosClient


class CosmosSettingError(Exception):
    """A required Cosmos setting is missing."""


@dataclass(frozen=True)
class CosmosSettings:
    endpoint: str
    database: str
    trips_container: str
    key: str | None = None


def load_cosmos_settings(env: Mapping[str, str] | None = None) -> CosmosSettings:
    env = os.environ if env is None else env

    def required(name: str) -> str:
        value = env.get(name, "").strip()
        if not value:
            raise CosmosSettingError(f"missing setting: {name}")
        return value

    return CosmosSettings(
        endpoint=required("COSMOS_ENDPOINT"),
        database=required("COSMOS_DATABASE"),
        trips_container=required("COSMOS_CONTAINER_TRIPS"),
        key=env.get("COSMOS_KEY", "").strip() or None,
    )


class CosmosConnection:
    """Call start() when the app starts and close() when it stops."""

    def __init__(self, settings: CosmosSettings) -> None:
        self._settings = settings
        self._client: CosmosClient | None = None
        self._credential = None
        self.trips = None  # the trips container, set by start()

    async def start(self) -> None:
        credential = self._settings.key
        if credential is None:
            from azure.identity.aio import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
            credential = self._credential

        self._client = CosmosClient(self._settings.endpoint, credential=credential)
        database = self._client.get_database_client(self._settings.database)
        self.trips = database.get_container_client(self._settings.trips_container)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential is not None:
            await self._credential.close()