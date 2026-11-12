"""Small helpers shared by all routes."""

import re

from fastapi import HTTPException, Request
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from api.core.models import CamelModel
from api.services import Services


class RequestModel(CamelModel):
    """The body of a request. Fields we do not know are refused."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )


def problem(code: str, message: str, **extra) -> dict:
    """The error body every route returns: a code the page can act on, and a message."""
    return {"code": code, "message": message, **extra}


def display_name(services: Services, provider_id: str) -> str:
    """A friendly provider name: from the names list, else the id tidied up."""
    known = services.provider_names.get(provider_id)
    if known:
        return known
    words = re.split(r"[\s_\-]+", provider_id.strip())
    return " ".join(w.capitalize() for w in words if w)


def get_services(request: Request) -> Services:
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=500, detail=problem(
            "NOT_READY", "the service is not ready"))
    return services
