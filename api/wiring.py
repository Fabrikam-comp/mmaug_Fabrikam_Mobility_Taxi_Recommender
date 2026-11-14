import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.adapters.httpclient import create_client
from api.adapters.registry import load_registry
from api.auth.token_check import build_authenticator
from api.cache.ttl_cache import TTLCache
from api.core.booking_service import BookingService
from api.core.quote_set_store import QuoteSetStore
from api.core.quote_store import QuoteStore
from api.currency.rates_client import RatesProvider
from api.data.cosmos_client import CosmosConnection, load_cosmos_settings
from api.data.repositories import CosmosTripRepository, InMemoryTripRepository
from api.explain.model_chain import ModelChain, load_model_providers
from api.explain.service import CACHE_TTL_S, ExplanationService
from api.locations.geocoder import Geocoder
from api.routes import bookings, explanations, locations, quotes, trips
from api.services import Services

log = logging.getLogger(__name__)

# Friendly names for the three mock providers. Edit if your provider ids differ.
PROVIDER_NAMES = {"mock-bolt": "Bolt",
                  "mock-uber": "Uber", "mock-ecabs": "eCabs"}

AZURE_MARKERS = ("WEBSITE_SITE_NAME",
                 "WEBSITE_INSTANCE_ID", "WEBSITE_HOSTNAME")


def include_routes(app: FastAPI) -> None:
    for module in (quotes, bookings, trips, explanations, locations):
        app.include_router(module.router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # one shared client for the providers and the exchange rates
    http_client = create_client()
    registry = load_registry(http_client)
    for problem in registry.problems:
        log.warning("provider not loaded: %s", problem)

    # Trips: Cosmos DB. Locally, without Cosmos settings, an in-memory store is
    # used. On Azure the settings are required, so data is never lost silently.
    cosmos = None
    if os.environ.get("COSMOS_ENDPOINT") or any(os.environ.get(m) for m in AZURE_MARKERS):
        cosmos = CosmosConnection(load_cosmos_settings())
        await cosmos.start()
        trips_repo = CosmosTripRepository(cosmos.trips)
    else:
        log.warning("COSMOS_ENDPOINT is not set: trips are kept in memory only")
        trips_repo = InMemoryTripRepository()

    quote_store = QuoteStore(TTLCache(ttl_s=600, max_entries=2000))
    quote_set_store = QuoteSetStore(TTLCache(ttl_s=600, max_entries=1000))
    chain = ModelChain(load_model_providers())
    geocoder = Geocoder()

    app.state.authenticator = build_authenticator()
    app.state.services = Services(
        registry=registry,
        rates=RatesProvider(http_client),
        trips=trips_repo,
        quote_store=quote_store,
        quote_set_store=quote_set_store,
        booking=BookingService(quote_store, trips_repo, registry.adapters),
        explanations=ExplanationService(
            chain, TTLCache(ttl_s=CACHE_TTL_S, max_entries=500)),
        geocoder=geocoder,
        provider_names=PROVIDER_NAMES,
    )
    try:
        yield
    finally:
        await chain.close()
        await geocoder.close()
        if cosmos is not None:
            await cosmos.close()
        await http_client.aclose()
