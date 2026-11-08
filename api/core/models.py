# Adapters format

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


CurrencyCode = Literal[
    "EUR", "GBP", "PLN", "USD", "CHF", "SEK", "NOK", "DKK", "CZK", "HUF"
]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )


class VehicleClass(str, Enum):
    STANDARD = "STANDARD"
    XL = "XL"


class PriceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ESTIMATE = "ESTIMATE"


class ProviderStatus(str, Enum):
    OK = "OK"
    SLOW = "SLOW"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    NO_PRICE = "NO_PRICE"


class DataSource(str, Enum):
    SIMULATED = "SIMULATED"


class FailureReason(str, Enum):
    """Why a provider gave no options. The frontend turns this into a banner."""

    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class Place(CamelModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class JourneyCriteria(CamelModel):
    pickup: Place
    destination: Place
    passengers: int = Field(ge=1, le=8)
    load: int = Field(ge=0, le=6, description="Number of bags")
    preferred_provider: str | None = None
    currency: CurrencyCode = "EUR"

    @model_validator(mode="after")
    def pickup_and_destination_must_differ(self):
        if self.pickup == self.destination:
            raise ValueError("pickup and destination must be different places")
        return self


class Price(CamelModel):
    status: PriceStatus
    amount_eur: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def amount_matches_status(self):
        if self.status == PriceStatus.UNAVAILABLE and self.amount_eur is not None:
            raise ValueError("an UNAVAILABLE price must not have an amount")
        if self.status != PriceStatus.UNAVAILABLE and self.amount_eur is None:
            raise ValueError("an AVAILABLE or ESTIMATE price needs an amount")
        return self

    @property
    def is_known(self) -> bool:
        return self.status != PriceStatus.UNAVAILABLE


class TransportOption(CamelModel):
    provider_id: str
    adapter_version: str
    data_source: DataSource = DataSource.SIMULATED
    vehicle_class: VehicleClass
    seats: int = Field(ge=1)
    bag_capacity: int = Field(ge=0)
    price: Price
    pickup_eta_min: float = Field(ge=0)
    journey_min: float = Field(ge=0)
    quote_id: str
    expires_at: datetime
    provider_status: ProviderStatus


class ProviderResult(CamelModel):
    """What one adapter hands back for one search."""

    provider_id: str
    status: ProviderStatus
    options: list[TransportOption] = Field(default_factory=list)
    reason: FailureReason | None = None
    retry_after_s: float | None = None


class Booking(CamelModel):
    """Minimal for now. The full booking design is still to be written."""

    reference: str  # for example FAB-7K3Q9
    provider_id: str
    quote_id: str
    status: Literal["CONFIRMED"] = "CONFIRMED"
    data_source: DataSource = DataSource.SIMULATED


class HealthStatus(CamelModel):
    provider_id: str
    status: ProviderStatus
    latency_ms: float | None = None
