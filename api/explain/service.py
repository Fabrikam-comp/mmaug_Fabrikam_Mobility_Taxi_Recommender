"""Explanation service: puts the explain pieces together.

recommendation -> fact sheet -> cache -> AI chain -> validator -> fill -> label.
If anything fails, the template text is used, so there is always an answer.
The page shows the text under "Why we recommend this, AI-generated" when
source is "AI", and as a plain rule-based sentence when it is "TEMPLATE".
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from api.cache.ttl_cache import TTLCache
from api.explain.fact_sheet import build_fact_sheet
from api.explain.model_chain import Attempt, ModelChain
from api.explain.template import template_text
from api.scoring.ranking import Recommendation

CACHE_TTL_S = 600  # 10 minutes, as in the proposal


@dataclass(frozen=True)
class Explanation:
    text: str  # final text with the real values filled in
    source: Literal["AI", "TEMPLATE"]
    provider: str | None  # which AI provider wrote it, when source is AI
    cached: bool
    attempts: tuple[Attempt, ...]  # for metrics: fallback rate, rejection rate


class ExplanationService:
    def __init__(self, chain: ModelChain, cache: TTLCache[tuple[str, str]]) -> None:
        self._chain = chain
        self._cache = cache

    async def explain(
        self,
        recommendation: Recommendation,
        provider_names: Mapping[str, str] | None = None,
        price_labels: Mapping[str, str] | None = None,
    ) -> Explanation | None:
        """Returns None when there is nothing to explain."""
        facts = build_fact_sheet(recommendation, provider_names, price_labels)
        if facts is None:
            return None

        hit = self._cache.get(facts.key)
        if hit is not None:
            text, provider = hit
            return Explanation(facts.fill(text), "AI", provider, True, ())

        result = await self._chain.generate(facts)
        if result.text is not None:
            # Cache the text WITH placeholders. The cache key depends only on
            # what the model saw, and the real values are filled in each time.
            self._cache.set(facts.key, (result.text, result.provider), ttl_s=CACHE_TTL_S)
            return Explanation(facts.fill(result.text), "AI", result.provider, False, result.attempts)

        text = template_text(facts.reasons)
        return Explanation(facts.fill(text), "TEMPLATE", None, False, result.attempts)