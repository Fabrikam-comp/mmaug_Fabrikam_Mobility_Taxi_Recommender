"""The shared services the routes use.

wiring.py builds them once at start-up and puts them on app.state.services.
Routes never build their own, so every route shares the same caches,
connections and locks.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from api.adapters.registry import Registry
from api.core.booking_service import BookingService
from api.core.quote_set_store import QuoteSetStore
from api.core.quote_store import QuoteStore
from api.currency.rates_client import RatesProvider
from api.data.repositories import TripRepository
from api.explain.service import ExplanationService
from api.locations.geocoder import Geocoder


@dataclass
class Services:
    registry: Registry  # provider adapters and their circuit breakers
    rates: RatesProvider
    trips: TripRepository
    quote_store: QuoteStore
    quote_set_store: QuoteSetStore
    booking: BookingService
    explanations: ExplanationService
    geocoder: Geocoder
    # provider_id -> friendly name, for banners and explanations
    provider_names: Mapping[str, str] = field(default_factory=dict)
