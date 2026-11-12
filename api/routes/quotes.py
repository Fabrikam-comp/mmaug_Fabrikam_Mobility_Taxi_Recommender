"""POST /quotes: the "Find a ride" button.

Asks every provider in parallel, ranks the options, converts the price to the
chosen currency, saves the quotes so a booking can find them later, and
returns everything the results screen needs.

The body is the journey: pickup and destination (lat and lon), passengers,
load, preferredProvider and currency. Every position must be inside Malta.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import current_user
from api.auth.token_check import CurrentUser
from api.core.models import (
    CamelModel,
    CurrencyCode,
    FailureReason,
    JourneyCriteria,
    ProviderStatus,
    TransportOption,
)
from api.core.quote_service import all_options, collect_quotes
from api.currency.converter import ConvertedPrice, convert_from_eur
from api.locations.landmark_name import landmark_name
from api.locations.malta_bounds import is_in_malta
from api.routes.common import display_name, get_services, problem
from api.scoring.ranking import ScoreBreakdown, ScoredOption, rank_options
from api.services import Services

router = APIRouter(tags=["quotes"])

TOP_N = 3
SYMBOLS = {"GBP": "£", "USD": "$"}


class ConvertedOut(CamelModel):
    currency: CurrencyCode
    amount: float
    rate_date: date
    label: str  # for example "≈ £12.60 (ECB rate, 13 Oct)"


class OptionOut(CamelModel):
    # provider, vehicle, EUR price, pickup and journey time, quoteId, dataSource, status
    option: TransportOption
    score: ScoreBreakdown | None  # None when the option has no price
    recommended: bool
    converted_price: ConvertedOut | None  # None means: show the EUR price only


class ProviderOut(CamelModel):
    provider_id: str
    name: str
    status: ProviderStatus
    # why a provider gave no options (the page turns it into a banner)
    reason: FailureReason | None
    retry_after_s: float | None


class QuotesOut(CamelModel):
    # pass it to GET /explanations/{quoteSetId}; None when nothing can be explained
    quote_set_id: str | None
    currency: CurrencyCode
    top_options: list[OptionOut]
    all_options: list[OptionOut]
    providers: list[ProviderOut]
    # set when the user asked for another currency but only EUR can be shown
    currency_notice: str | None


def _label(converted: ConvertedPrice) -> str:
    symbol = SYMBOLS.get(converted.currency)
    amount = f"{converted.amount:,.2f}"
    text = f"{symbol}{amount}" if symbol else f"{amount} {converted.currency}"
    return f"≈ {text} (ECB rate, {converted.rate_date.day} {converted.rate_date:%b})"


@router.post("/quotes", response_model=QuotesOut)
async def get_quotes(
    journey: JourneyCriteria,
    user: CurrentUser = Depends(current_user),
    services: Services = Depends(get_services),
) -> QuotesOut:
    # The browser cannot be trusted: every position is checked here.
    for which, place in (("pickup", journey.pickup), ("destination", journey.destination)):
        if not is_in_malta(place):
            raise HTTPException(
                status_code=422,
                detail=problem(
                    "OUTSIDE_MALTA", f"the {which} must be inside Malta", field=which),
            )
    known = {adapter.provider_id for adapter in services.registry.adapters}
    if journey.preferred_provider and journey.preferred_provider not in known:
        raise HTTPException(
            status_code=422,
            detail=problem(
                "UNKNOWN_PROVIDER", "the preferred provider is not known", field="preferredProvider"),
        )

    results = await collect_quotes(journey, services.registry.adapters, services.registry.breakers)
    options = all_options(results)
    recommendation = rank_options(
        options, journey, top_n=TOP_N) if options else None

    # Keep every option, so "See all options" can be booked too. Only place
    # NAMES are kept with them, never coordinates.
    pickup_name = landmark_name(journey.pickup)
    destination_name = landmark_name(journey.destination)
    services.quote_store.save_many(
        user.user_id, options, pickup_name, destination_name)

    # Currency: the EUR price is the fact. The converted price is only a guide.
    converted: dict[str, ConvertedOut] = {}
    currency_notice = None
    if journey.currency != "EUR" and options:
        rates = await services.rates.get_rates()
        today = date.today()
        for option in options:
            amount = option.price.amount_eur
            if amount is None:
                continue
            price = convert_from_eur(amount, journey.currency, rates, today)
            if price is not None:
                converted[option.quote_id] = ConvertedOut(
                    currency=price.currency,
                    amount=price.amount,
                    rate_date=price.rate_date,
                    label=_label(price),
                )
        if not converted and any(o.price.amount_eur is not None for o in options):
            currency_notice = "Exchange rates are not available right now, so prices are shown in EUR only."

    def out(scored: ScoredOption) -> OptionOut:
        return OptionOut(
            option=scored.option,
            score=scored.score,
            recommended=scored.recommended,
            converted_price=converted.get(scored.option.quote_id),
        )

    quote_set_id = None
    if recommendation is not None and recommendation.top_options:
        labels = {qid: c.label for qid, c in converted.items()}
        quote_set_id = services.quote_set_store.save(
            user.user_id, recommendation, labels)

    return QuotesOut(
        quote_set_id=quote_set_id,
        currency=journey.currency,
        top_options=[
            out(s) for s in recommendation.top_options] if recommendation else [],
        all_options=[
            out(s) for s in recommendation.all_options] if recommendation else [],
        providers=[
            ProviderOut(
                provider_id=r.provider_id,
                name=display_name(services, r.provider_id),
                status=r.status,
                reason=r.reason,
                retry_after_s=r.retry_after_s,
            )
            for r in results
        ],
        currency_notice=currency_notice,
    )
