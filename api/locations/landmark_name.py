"""Pin to nearest landmark name, so no coordinates are ever stored.

Rule: if one of the fallback places is within 1.5 km of the pin, the name is
"Near <place>". If none is that close, the name is "Pinned location in Malta".
"""

from math import asin, cos, radians, sin, sqrt

from api.core.models import Place
from api.locations.fallback_places import FALLBACK_PLACES

LANDMARK_RADIUS_M = 1500
EARTH_RADIUS_M = 6_371_000
GENERIC_NAME = "Pinned location in Malta"


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance over the earth surface (haversine formula)."""
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * \
        cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def landmark_name(place: Place) -> str:
    nearest_name = None
    nearest_distance = LANDMARK_RADIUS_M

    for candidate in FALLBACK_PLACES:
        d = distance_m(place.lat, place.lon, candidate.lat, candidate.lon)
        if d <= nearest_distance:
            nearest_distance = d
            nearest_name = candidate.name

    if nearest_name is None:
        return GENERIC_NAME
    return f"Near {nearest_name}"
