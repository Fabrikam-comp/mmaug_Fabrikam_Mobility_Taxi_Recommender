"""Malta bounds: rejects positions outside Malta (Malta, Gozo and Comino).

The box is a rectangle, so it also covers some sea. That is fine: its job is
to reject places like Sicily or Tunisia, not to trace the coastline.

Source of the numbers: a published boundary dataset for Malta gives
west 14.183, east 14.576, north 36.083, south 35.806.
We round each side outward a little so no coastal spot is cut off.
"""

from api.core.models import Place

MIN_LAT = 35.79
MAX_LAT = 36.09
MIN_LON = 14.17
MAX_LON = 14.59

# OpenStreetMap wants the box as: left,top,right,bottom
VIEWBOX = f"{MIN_LON},{MAX_LAT},{MAX_LON},{MIN_LAT}"


def is_in_malta(place: Place) -> bool:
    return MIN_LAT <= place.lat <= MAX_LAT and MIN_LON <= place.lon <= MAX_LON
