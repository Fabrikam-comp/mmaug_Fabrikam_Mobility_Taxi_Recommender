"""Step 1 of the recommendation engine: the fit filter.

Vehicles that cannot carry the passengers or the bags are removed. Among the
rest, an exact fit scores 1.0 and a larger vehicle than needed scores 0.7.
"""

from api.core.models import JourneyCriteria, TransportOption, VehicleClass

EXACT_FIT = 1.0
LARGER_THAN_NEEDED = 0.7

# (class, most passengers, most bags), smallest class first.
_CLASS_LIMITS = [
    (VehicleClass.STANDARD, 4, 3),
    (VehicleClass.XL, 6, 6),
]


def required_class(passengers: int, bags: int) -> VehicleClass | None:
    """The smallest class that can carry the group.
    None means one vehicle is not enough (7 or 8 passengers)."""
    for vehicle_class, max_passengers, max_bags in _CLASS_LIMITS:
        if passengers <= max_passengers and bags <= max_bags:
            return vehicle_class
    return None


def can_carry(option: TransportOption, journey: JourneyCriteria) -> bool:
    return (
        option.seats >= journey.passengers
        and option.bag_capacity >= journey.load
    )


def filter_by_fit(
    options: list[TransportOption], journey: JourneyCriteria
) -> list[TransportOption]:
    return [option for option in options if can_carry(option, journey)]


def fit_factor(option: TransportOption, journey: JourneyCriteria) -> float:
    needed = required_class(journey.passengers, journey.load)
    if needed is not None and option.vehicle_class == needed:
        return EXACT_FIT
    return LARGER_THAN_NEEDED
