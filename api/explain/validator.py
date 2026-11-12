"""Validator: checks the AI text before anyone sees it.

The model may only write words and the placeholders it was given, such as
{opt1.provider}. It must not write any digit, currency, time expression or
provider name. If any rule fails, the text is rejected and the next provider
in the chain (and finally the template) is used.
"""

import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass

MIN_CHARS = 20
MAX_CHARS = 320

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")
WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")

# Names the model must never write, even if the fact sheet is empty.
BUILT_IN_NAMES = frozenset({"bolt", "uber", "ecabs", "e-cabs", "ecab"})

CURRENCY_SYMBOLS = frozenset("€£$¥₩₽₺₹₪¢")
CURRENCY_WORDS = frozenset({
    "eur", "euro", "euros", "gbp", "pound", "pounds", "sterling", "usd",
    "dollar", "dollars", "pln", "zloty", "zlotys", "zloties", "zł", "chf",
    "franc", "francs", "sek", "nok", "dkk", "krona", "kronor", "krone",
    "kroner", "czk", "koruna", "koruny", "huf", "forint", "forints",
    "cent", "cents", "pence", "penny",
})
TIME_WORDS = frozenset({
    "second", "seconds", "sec", "secs", "minute", "minutes", "min", "mins",
    "hour", "hours", "hr", "hrs", "am", "pm", "noon", "midnight",
    "o'clock", "o’clock",
})
FORBIDDEN_MARKUP = ("<", ">", "`", "http", "www.", "*", "#", "|", "[", "]")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    text: str  # cleaned text (only meaningful when ok is True)
    problem: str | None = None


def _reject(problem: str) -> ValidationResult:
    return ValidationResult(False, "", problem)


def validate_explanation(
    raw: str,
    allowed_placeholders: Collection[str],
    forbidden_names: Collection[str] = (),
    max_chars: int = MAX_CHARS,
) -> ValidationResult:
    text = " ".join(raw.split()).strip(" \"'“”‘’")
    if len(text) < MIN_CHARS:
        return _reject("too short")
    if len(text) > max_chars:
        return _reject("too long")

    # Placeholders: every one must be on the allowed list.
    for name in PLACEHOLDER.findall(text):
        if name not in allowed_placeholders:
            return _reject("unknown placeholder")
    rest = PLACEHOLDER.sub(" ", text)
    if "{" in rest or "}" in rest:
        return _reject("stray braces")

    lowered = rest.lower()
    if any(mark in lowered for mark in FORBIDDEN_MARKUP):
        return _reject("markup or link")

    # Digits and number characters (the placeholders are already removed).
    if any(unicodedata.category(ch) == "Nd" or ch.isnumeric() for ch in rest):
        return _reject("digit")
    if any(ch in CURRENCY_SYMBOLS for ch in rest):
        return _reject("currency symbol")

    words = WORD.findall(lowered)
    if any(word in CURRENCY_WORDS for word in words):
        return _reject("currency word")
    if any(word in TIME_WORDS for word in words):
        return _reject("time expression")

    names = {n.lower() for n in forbidden_names} | BUILT_IN_NAMES
    if any(word in names for word in words):
        return _reject("provider name")

    return ValidationResult(True, text)