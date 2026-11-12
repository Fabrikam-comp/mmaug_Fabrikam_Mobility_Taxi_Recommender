"""The fallback list of 50 common places in Malta.

Used when OpenStreetMap is unavailable: the user picks from this list.
"""

from dataclasses import dataclass

from api.core.models import Place


@dataclass(frozen=True)
class FallbackPlace:
    name: str
    lat: float
    lon: float

    def to_place(self) -> Place:
        return Place(lat=self.lat, lon=self.lon)


FALLBACK_PLACES: tuple[FallbackPlace, ...] = (
    FallbackPlace("Malta International Airport", 35.84741, 14.49229),
    FallbackPlace("Valletta Cruise Port", 35.89187, 14.51006),
    FallbackPlace("Ċirkewwa Ferry Terminal", 35.98853, 14.32885),
    FallbackPlace("Mġarr Ferry Terminal", 36.02439, 14.29816),
    FallbackPlace("Sliema Ferries", 35.90883, 14.50428),
    FallbackPlace("Valletta Ferry Terminal", 35.89187, 14.51006),
    FallbackPlace("Valletta", 35.899, 14.51366),
    FallbackPlace("Sliema", 35.91276, 14.50207),
    FallbackPlace("St Julian’s", 35.91992, 14.48771),
    FallbackPlace("Paceville", 35.9228, 14.49098),
    FallbackPlace("Gżira", 35.90778, 14.49612),
    FallbackPlace("Mdina", 35.88589, 14.40253),
    FallbackPlace("Rabat", 35.88189, 14.39882),
    FallbackPlace("Mosta", 35.90792, 14.42415),
    FallbackPlace("Bugibba", 35.94818, 14.40841),
    FallbackPlace("Qawra", 35.95413, 14.41981),
    FallbackPlace("St Paul’s Bay", 35.94794, 14.39724),
    FallbackPlace("Mellieħa", 35.95996, 14.36837),
    FallbackPlace("Marsaxlokk", 35.84177, 14.54484),
    FallbackPlace("Birgu", 35.88811, 14.52384),
    FallbackPlace("Senglea", 35.88717, 14.51731),
    FallbackPlace("Cospicua", 35.88258, 14.52272),
    FallbackPlace("Victoria", 36.04289, 14.23985),
    FallbackPlace("Marsalforn", 36.07089, 14.25981),
    FallbackPlace("Xlendi", 36.0312, 14.21827),
    FallbackPlace("Mqabba", 35.84568, 14.46663),
    FallbackPlace("Dingli", 35.86042, 14.38168),
    FallbackPlace("Blue Grotto", 35.82127, 14.45655),
    FallbackPlace("Popeye Village", 35.96084, 14.34068),
    FallbackPlace("Golden Bay", 35.93374, 14.34461),
    FallbackPlace("Għajn Tuffieħa Bay", 35.92927, 14.34375),
    FallbackPlace("Għadira Bay", 35.97077, 14.35364),
    FallbackPlace("Ħaġar Qim", 35.8272, 14.44353),
    FallbackPlace("Mnajdra", 35.82364, 14.43732),
    FallbackPlace("Ġgantija Temples", 36.04723, 14.26906),
    FallbackPlace("Ta’ Pinu Basilica", 36.06194, 14.21488),
    FallbackPlace("Dwejra", 36.05356, 14.18826),
    FallbackPlace("Citadel Victoria", 36.04632, 14.23961),
    FallbackPlace("Ħal Saflieni Hypogeum", 35.86955, 14.50689),
    FallbackPlace("Upper Barrakka Gardens", 35.89496, 14.51201),
    FallbackPlace("St John’s Co-Cathedral", 35.8977, 14.51264),
    FallbackPlace("Fort St Elmo", 35.90198, 14.51881),
    FallbackPlace("Mosta Dome", 35.91008, 14.42581),
    FallbackPlace("Manoel Island", 35.90332, 14.50195),
    FallbackPlace("Spinola Bay", 35.91898, 14.492),
    FallbackPlace("The Point Shopping Mall", 35.90763, 14.51062),
    FallbackPlace("Marsaskala", 35.86292, 14.55919),
    FallbackPlace("Tigné Point", 35.90763, 14.51062),
)


def find_fallback_place(name: str) -> FallbackPlace | None:
    wanted = name.strip().lower()
    for place in FALLBACK_PLACES:
        if place.name.lower() == wanted:
            return place
    return None
