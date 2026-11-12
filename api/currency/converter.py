"""Display currencies (sections 4.3 and 5.8).

The provider's EUR price is the fact. Other currencies are approximate and
come from European Central Bank daily rates. This file holds the rules only.
Fetching the rates from the internet is a separate job (not written yet).
"""

from dataclasses import dataclass
from datetime import date

from api.core.models import CamelModel, CurrencyCode

MAX_RATE_MOVE = 0.10  # reject a rate that moves more than 10% in one update
MAX_RATE_AGE_DAYS = 3  # older than this, show prices in EUR only

DISPLAY_CURRENCIES = ("GBP", "PLN", "USD", "CHF", "SEK", "NOK", "DKK", "CZK", "HUF")


@dataclass(frozen=True)
class Rates:
    as_of: date  # the date the ECB published these rates
    per_eur: dict[str, float]  # units of each currency for 1 EUR


class ConvertedPrice(CamelModel):
    currency: CurrencyCode
    amount: float
    rate_date: date


def rates_are_sane(new: Rates, previous: Rates | None) -> bool:
    """Every display currency is present and positive, and none moved
    more than 10% compared with the previous rates."""
    for code in DISPLAY_CURRENCIES:
        rate = new.per_eur.get(code)
        if rate is None or rate <= 0:
            return False
        if previous is not None and code in previous.per_eur:
            move = abs(rate / previous.per_eur[code] - 1)
            if move > MAX_RATE_MOVE:
                return False
    return True


def is_stale(rates: Rates, today: date) -> bool:
    return (today - rates.as_of).days > MAX_RATE_AGE_DAYS


def convert_from_eur(
    amount_eur: float,
    currency: str,
    rates: Rates | None,
    today: date,
) -> ConvertedPrice | None:
    """Returns None when the price should simply be shown in EUR."""
    if currency == "EUR" or rates is None or is_stale(rates, today):
        return None
    rate = rates.per_eur.get(currency)
    if rate is None:
        return None
    return ConvertedPrice(
        currency=currency,
        amount=round(amount_eur * rate, 2),
        rate_date=rates.as_of,
    )