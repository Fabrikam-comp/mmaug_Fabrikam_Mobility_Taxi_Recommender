"""Template text: the always-available fallback explanation.

Pre-written sentences that use the same placeholders as the AI text, so the
same fill step works for both. No digits and no names are written here.
"""

from collections.abc import Sequence

REASON_PHRASES = {
    "only_option": "it is the only option available right now",
    "soonest_pickup": "it can pick you up soonest ({opt1.eta})",
    "best_fit": "it fits your group and luggage best",
    "preferred_provider": "it is the provider you preferred",
    "lowest_price": "it has the lowest price ({opt1.price})",
    "highest_overall": "it scored highest overall on our published factors",
}


def _join(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def template_text(reasons: Sequence[str]) -> str:
    phrases = [REASON_PHRASES[r] for r in reasons if r in REASON_PHRASES]
    if not phrases:
        phrases = [REASON_PHRASES["highest_overall"]]
    return "{opt1.provider} is recommended because " + _join(phrases) + "."