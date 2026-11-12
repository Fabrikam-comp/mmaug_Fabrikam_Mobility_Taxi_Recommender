"""Fact sheet: the facts about a recommendation, built from validated data only.

Two things come out of it:
1. what the model is allowed to see: option labels (opt1, opt2, opt3), reason
   codes and the list of placeholders. It never sees a provider name, a price
   or a time, so it has nothing to copy or invent.
2. the real values, kept on the server and filled in after the text passes
   the validator.

No free text from providers or users is ever included.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from api.core.models import PriceStatus, TransportOption, VehicleClass
from api.scoring.ranking import Recommendation, ScoredOption

MAX_OPTIONS = 3
PROMPT_VERSION = "1"  # change it when the prompt changes, so old cache entries are not reused
FIELDS = ("provider", "eta", "journey", "price", "vehicle")

REASON_MEANING = {
    "only_option": "it is the only option available",
    "soonest_pickup": "it can pick the user up soonest",
    "best_fit": "it fits the group size and luggage best",
    "preferred_provider": "it is the provider the user preferred",
    "lowest_price": "it has the lowest price",
    "highest_overall": "it scored highest overall on the published factors",
}

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")


@dataclass(frozen=True, eq=False)
class FactSheet:
    values: Mapping[str, str]  # for example {"opt1.provider": "Bolt"}
    reasons: tuple[str, ...]
    option_count: int
    forbidden_names: frozenset[str]

    @property
    def allowed_placeholders(self) -> frozenset[str]:
        return frozenset(self.values)

    def prompt_payload(self) -> dict:
        return {
            "recommended": "opt1",
            "other_options": [f"opt{i}" for i in range(2, self.option_count + 1)],
            "reasons": [{"code": r, "meaning": REASON_MEANING[r]} for r in self.reasons],
            "placeholders": sorted("{" + name + "}" for name in self.values),
        }

    @property
    def key(self) -> str:
        """Hash used to cache the AI text. It depends only on what the model sees."""
        canonical = json.dumps({"v": PROMPT_VERSION, "p": self.prompt_payload()}, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def fill(self, text: str) -> str:
        """Put the real values in place of the placeholders."""
        return PLACEHOLDER.sub(lambda m: self.values[m.group(1)], text)


def _tidy(provider_id: str) -> str:
    words = re.split(r"[\s_\-]+", provider_id.strip())
    return " ".join(w.capitalize() for w in words if w)


def _name_tokens(*names: str) -> set[str]:
    tokens: set[str] = set()
    for name in names:
        lowered = name.lower()
        tokens.add(lowered)
        tokens.update(re.findall(r"[^\W\d_]{3,}", lowered))
    return tokens


def _minutes(value: float) -> str:
    return f"{max(1, round(value))} min"


def _eur_label(option: TransportOption) -> str:
    price = option.price
    if price.status == PriceStatus.UNAVAILABLE or price.amount_eur is None:
        return "price not available"
    text = f"€{price.amount_eur:.2f}"
    return f"about {text} (estimate)" if price.status == PriceStatus.ESTIMATE else text


def _vehicle_label(vehicle: VehicleClass) -> str:
    return "XL" if vehicle == VehicleClass.XL else "standard"


def _reasons(options: list[ScoredOption]) -> tuple[str, ...]:
    winner = options[0].score
    if winner is None:
        return ()
    others = [o.score for o in options[1:] if o.score is not None]
    if not others:
        return ("only_option",)

    found = []
    for code, factor in (
        ("soonest_pickup", "proximity"),
        ("best_fit", "fit"),
        ("preferred_provider", "preference"),
        ("lowest_price", "price"),
    ):
        mine = getattr(winner, factor)
        theirs = [getattr(s, factor) for s in others]
        # a real strength: at least as good as everyone and better than someone
        if mine >= max(theirs) and mine > min(theirs):
            found.append(code)
    return tuple(found) if found else ("highest_overall",)


def build_fact_sheet(
    recommendation: Recommendation,
    provider_names: Mapping[str, str] | None = None,
    price_labels: Mapping[str, str] | None = None,
) -> FactSheet | None:
    """Returns None when there is nothing to explain (no recommended option).

    provider_names: provider_id -> friendly name (otherwise the id is tidied up).
    price_labels: quote_id -> text to show, for example a converted price.
    """
    shown = recommendation.top_options
    winners = [o for o in shown if o.recommended]
    if not winners or winners[0].score is None:
        return None
    options = (winners + [o for o in shown if o is not winners[0]])[:MAX_OPTIONS]

    names = provider_names or {}
    labels = price_labels or {}
    values: dict[str, str] = {}
    forbidden: set[str] = set()
    for number, scored in enumerate(options, start=1):
        option = scored.option
        display = names.get(option.provider_id) or _tidy(option.provider_id)
        forbidden |= _name_tokens(display, option.provider_id)
        prefix = f"opt{number}"
        values[f"{prefix}.provider"] = display
        values[f"{prefix}.eta"] = _minutes(option.pickup_eta_min)
        values[f"{prefix}.journey"] = _minutes(option.journey_min)
        values[f"{prefix}.price"] = labels.get(option.quote_id) or _eur_label(option)
        values[f"{prefix}.vehicle"] = _vehicle_label(option.vehicle_class)

    return FactSheet(
        values=values,
        reasons=_reasons(options),
        option_count=len(options),
        forbidden_names=frozenset(forbidden),
    )