"""Steps 2 and 3 of the recommendation engine: score and rank.

Each option gets 0 to 100 points:
  proximity (pickup ETA) 30, vehicle fit 30, provider preference 25, price 15.
Highest score first, ties go to the cheaper option. The top 3 are shown and
number 1 is marked Recommended. Options without a price are never scored or
recommended and are listed after the priced options.
"""

from api.core.models import CamelModel, JourneyCriteria, TransportOption
from api.scoring.fit import filter_by_fit, fit_factor

WEIGHT_PROXIMITY = 30
WEIGHT_FIT = 30
WEIGHT_PREFERENCE = 25
WEIGHT_PRICE = 15

PREFERRED = 1.0
NOT_PREFERRED = 0.5  # also used for everyone when no preference is set


class ScoreBreakdown(CamelModel):
    """Points per factor, so the screen can show why an option won."""

    proximity: float
    fit: float
    preference: float
    price: float
    total: float


class ScoredOption(CamelModel):
    option: TransportOption
    score: ScoreBreakdown | None  # None when the option has no price
    recommended: bool = False


class Recommendation(CamelModel):
    top_options: list[ScoredOption]
    all_options: list[ScoredOption]


def _lower_is_better(value: float, lowest: float, highest: float) -> float:
    """Lowest value scores 1, highest scores 0, scaled in between.
    If every option has the same value, nobody is penalised."""
    if highest == lowest:
        return 1.0
    return (highest - value) / (highest - lowest)


def preference_factor(option: TransportOption, journey: JourneyCriteria) -> float:
    if journey.preferred_provider is None:
        return NOT_PREFERRED
    if option.provider_id == journey.preferred_provider:
        return PREFERRED
    return NOT_PREFERRED


def rank_options(
    options: list[TransportOption],
    journey: JourneyCriteria,
    top_n: int = 3,
) -> Recommendation:
    fitting = filter_by_fit(options, journey)
    priced = [option for option in fitting if option.price.is_known]
    unpriced = [option for option in fitting if not option.price.is_known]

    scored: list[tuple[float, float, ScoredOption]] = []
    if priced:
        etas = [option.pickup_eta_min for option in priced]
        prices = [option.price.amount_eur for option in priced]
        for option in priced:
            points = ScoreBreakdown(
                proximity=WEIGHT_PROXIMITY
                * _lower_is_better(option.pickup_eta_min,
                                   min(etas), max(etas)),
                fit=WEIGHT_FIT * fit_factor(option, journey),
                preference=WEIGHT_PREFERENCE *
                preference_factor(option, journey),
                price=WEIGHT_PRICE
                * _lower_is_better(option.price.amount_eur,
                                   min(prices), max(prices)),
                total=0.0,
            )
            raw_total = points.proximity + points.fit + points.preference + points.price
            rounded = ScoreBreakdown(
                proximity=round(points.proximity, 2),
                fit=round(points.fit, 2),
                preference=round(points.preference, 2),
                price=round(points.price, 2),
                total=round(raw_total, 2),
            )
            scored.append(
                (raw_total, option.price.amount_eur,
                 ScoredOption(option=option, score=rounded))
            )

    # Highest score first. A tie goes to the cheaper option.
    scored.sort(key=lambda item: (-item[0], item[1]))
    ranked = [item[2] for item in scored]
    if ranked:
        ranked[0].recommended = True

    all_options = ranked + \
        [ScoredOption(option=option, score=None) for option in unpriced]
    return Recommendation(top_options=all_options[:top_n], all_options=all_options)
