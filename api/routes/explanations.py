"""GET /explanations/{quoteSetId}: the short 'why we recommend this' text.

The text is AI-written and checked against the facts, or a plain template if
the AI is unavailable. The page shows the "AI-generated" label only when
source is "AI". If the server restarted since the search, the result set is
gone and this returns 404, so the page just hides the panel.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import current_user
from api.auth.token_check import CurrentUser
from api.core.models import CamelModel
from api.routes.common import get_services, problem
from api.services import Services

router = APIRouter(tags=["explanations"])


class ExplanationOut(CamelModel):
    text: str
    source: Literal["AI", "TEMPLATE"]


@router.get("/explanations/{quote_set_id}", response_model=ExplanationOut)
async def get_explanation(
    quote_set_id: str,
    user: CurrentUser = Depends(current_user),
    services: Services = Depends(get_services),
) -> ExplanationOut:
    stored = services.quote_set_store.get(quote_set_id, user.user_id)
    if stored is None:
        raise HTTPException(
            status_code=404,
            detail=problem(
                "QUOTE_SET_NOT_FOUND", "this result is no longer available, please search again"),
        )

    explanation = await services.explanations.explain(
        stored.recommendation,
        provider_names=services.provider_names,
        price_labels=stored.price_labels,
    )
    if explanation is None:
        raise HTTPException(
            status_code=404,
            detail=problem("NOTHING_TO_EXPLAIN",
                           "there is no recommended option to explain"),
        )
    return ExplanationOut(text=explanation.text, source=explanation.source)
