"""Shared pretend world used by all three mock providers.

Drivers, distances, times and prices are made up. Each provider turns the
same simulation into its own response shape (see bolt.py, uber.py, ecabs.py).
Pass a seeded random.Random to get the same answer every time (for tests).
"""

import math
import random
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EARTH_RADIUS_KM = 6371.0
ROAD_FACTOR = 1.3  # roads are longer than a straight line
AVERAGE_SPEED_KMH = 28.0  # slow Malta traffic
QUOTE_LIFETIME_S = 60
MAX_DRIVER_DISTANCE_KM = 6.0

# class name -> (seats, bag capacity)
VEHICLES = {"STANDARD": (4, 3), "XL": (6, 6)}


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float


@dataclass(frozen=True)
class Trip:
    road_km: float
    duration_min: float


@dataclass(frozen=True)
class FareProfile:
    base_eur: float
    per_km_eur: float
    per_min_eur: float
    xl_factor: float
    minimum_eur: float


# Made-up prices. Each provider is a little different so the results differ.
FARE_PROFILES = {
    "bolt": FareProfile(2.00, 0.80, 0.14, 1.40, 4.00),
    "uber": FareProfile(2.50, 0.85, 0.16, 1.45, 4.50),
    "ecabs": FareProfile(3.00, 0.90, 0.12, 1.35, 5.00),
}


@dataclass(frozen=True)
class Offer:
    vehicle_class: str
    seats: int
    bags: int
    fare_eur: float
    pickup_eta_min: float
    trip_min: float
    quote_id: str
    expires_at: datetime


# ---------- maths ----------

def haversine_km(a: Point, b: Point) -> float:
    """Straight-line distance between two positions."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    d_lat = lat2 - lat1
    d_lon = math.radians(b.lon - a.lon)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * \
        math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def random_driver_positions(
    pickup: Point, count: int, rng: random.Random, max_km: float = MAX_DRIVER_DISTANCE_KM
) -> list[Point]:
    """Drivers placed at random around the pickup point."""
    positions = []
    for _ in range(count):
        distance = max_km * math.sqrt(rng.random())  # sqrt spreads them evenly
        bearing = rng.uniform(0, 2 * math.pi)
        d_lat = (distance / 111.0) * math.cos(bearing)
        d_lon = (distance / (111.0 * math.cos(math.radians(pickup.lat)))
                 ) * math.sin(bearing)
        positions.append(Point(pickup.lat + d_lat, pickup.lon + d_lon))
    return positions


def driver_count(vehicle_class: str, rng: random.Random) -> int:
    """XL cars are rarer than standard ones."""
    return rng.randint(1, 4) if vehicle_class == "XL" else rng.randint(3, 8)


def pickup_eta_minutes(straight_km: float) -> float:
    return max(1.0, round(straight_km * ROAD_FACTOR / AVERAGE_SPEED_KMH * 60, 1))


def estimate_trip(pickup: Point, destination: Point) -> Trip:
    road_km = haversine_km(pickup, destination) * ROAD_FACTOR
    return Trip(road_km=road_km, duration_min=road_km / AVERAGE_SPEED_KMH * 60 + 2)


# ---------- busy-time pricing ----------

def malta_now() -> datetime:
    try:
        return datetime.now(ZoneInfo("Europe/Malta"))
    except ZoneInfoNotFoundError:
        # fallback if the system has no time zone data
        return datetime.now(timezone.utc)


def busy_multiplier(local_time: datetime) -> float:
    """Weekday rush hours cost more, and so do Friday and Saturday nights."""
    weekday = local_time.weekday()  # Monday is 0
    hour = local_time.hour + local_time.minute / 60
    if (weekday in (4, 5) and hour >= 22) or (weekday in (5, 6) and hour < 3):
        return 1.5
    if weekday < 5 and (7 <= hour < 9 or 16.5 <= hour < 19):
        return 1.3
    return 1.0


def fare_eur(provider: str, vehicle_class: str, trip: Trip, multiplier: float) -> float:
    profile = FARE_PROFILES[provider]
    fare = profile.base_eur + profile.per_km_eur * \
        trip.road_km + profile.per_min_eur * trip.duration_min
    if vehicle_class == "XL":
        fare *= profile.xl_factor
    return round(max(fare * multiplier, profile.minimum_eur), 2)


# ---------- quotes and bookings ----------

class UnknownQuote(Exception):
    pass


class ExpiredQuote(Exception):
    pass


class QuoteBook:
    """Remembers issued quotes (so they can expire) and bookings (so the same
    idempotency key always gives back the same booking)."""

    def __init__(
        self,
        lifetime_s: int = QUOTE_LIFETIME_S,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._lifetime_s = lifetime_s
        self._clock = clock
        self._quotes: dict[str, tuple[str, datetime]] = {}
        self._bookings: dict[tuple[str, str], dict] = {}

    def clear(self) -> None:
        self._quotes.clear()
        self._bookings.clear()

    def issue(self, provider: str) -> tuple[str, datetime]:
        now = self._clock()
        self._prune(now)
        quote_id = f"{provider}_q_{secrets.token_hex(6)}"
        expires_at = now + timedelta(seconds=self._lifetime_s)
        self._quotes[quote_id] = (provider, expires_at)
        return quote_id, expires_at

    def book(self, provider: str, quote_id: str, idempotency_key: str) -> dict:
        existing = self._bookings.get((provider, idempotency_key))
        if existing is not None:
            return existing
        entry = self._quotes.get(quote_id)
        if entry is None or entry[0] != provider:
            raise UnknownQuote(quote_id)
        if self._clock() >= entry[1]:
            raise ExpiredQuote(quote_id)
        booking = {"quote_id": quote_id,
                   "number": secrets.token_hex(4).upper()}
        self._bookings[(provider, idempotency_key)] = booking
        if len(self._bookings) > 1000:  # keep memory small
            self._bookings.pop(next(iter(self._bookings)))
        return booking

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(minutes=10)
        for quote_id in [q for q, (_, expires) in self._quotes.items() if expires < cutoff]:
            del self._quotes[quote_id]


quote_book = QuoteBook()


def reset_state() -> None:
    quote_book.clear()


def make_rng(seed: str | None) -> random.Random:
    """A seed (from the X-Mock-Seed header) makes the answer repeatable."""
    if seed is not None:
        try:
            return random.Random(int(seed))
        except ValueError:
            pass
    return random.Random()


def build_offers(
    provider: str,
    pickup: Point,
    destination: Point,
    passengers: int,
    bags: int,
    rng: random.Random,
    extra_multiplier: float = 1.0,
    local_time: datetime | None = None,
) -> list[Offer]:
    """One offer per vehicle class that can carry the group."""
    trip = estimate_trip(pickup, destination)
    multiplier = busy_multiplier(local_time or malta_now()) * extra_multiplier
    offers = []
    for vehicle_class, (seats, capacity) in VEHICLES.items():
        if passengers > seats or bags > capacity:
            continue
        drivers = random_driver_positions(
            pickup, driver_count(vehicle_class, rng), rng)
        nearest_km = min(haversine_km(pickup, driver) for driver in drivers)
        quote_id, expires_at = quote_book.issue(provider)
        offers.append(
            Offer(
                vehicle_class=vehicle_class,
                seats=seats,
                bags=capacity,
                fare_eur=fare_eur(provider, vehicle_class, trip, multiplier),
                pickup_eta_min=pickup_eta_minutes(nearest_km),
                trip_min=round(trip.duration_min, 1),
                quote_id=quote_id,
                expires_at=expires_at,
            )
        )
    return offers
