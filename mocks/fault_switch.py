"""The fault switch: make a mock provider misbehave on purpose.

Modes: NONE, TIMEOUT (answers too late), ERROR (503), RATE_LIMIT (429 with
Retry-After), NO_PRICE (answers without a price), BAD_DATA (wrong shape).
The state lives in memory and resets when the app restarts.
The admin routes need the X-Admin-Key header. If MOCK_ADMIN_KEY is not set,
they refuse everything, so the switch can be turned off in production.
"""

import asyncio
from enum import Enum
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from mocks import settings

PROVIDERS = ("bolt", "uber", "ecabs")
RETRY_AFTER_S = 10


class FaultMode(str, Enum):
    NONE = "NONE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    NO_PRICE = "NO_PRICE"
    BAD_DATA = "BAD_DATA"


_modes: dict[str, FaultMode] = {name: FaultMode.NONE for name in PROVIDERS}


def get_mode(provider: str) -> FaultMode:
    return _modes[provider]


def set_mode(provider: str, mode: FaultMode) -> None:
    targets = PROVIDERS if provider == "all" else (provider,)
    for name in targets:
        _modes[name] = mode


def reset() -> None:
    set_mode("all", FaultMode.NONE)


async def apply_fault(provider: str) -> FaultMode:
    """Call at the start of every provider route. TIMEOUT, ERROR and RATE_LIMIT
    act here. NO_PRICE and BAD_DATA are returned so the route can shape its answer."""
    mode = get_mode(provider)
    if mode == FaultMode.TIMEOUT:
        # the caller gives up first
        await asyncio.sleep(settings.fault_timeout_s())
    elif mode == FaultMode.ERROR:
        raise HTTPException(status_code=503, detail="simulated provider error")
    elif mode == FaultMode.RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="simulated rate limit",
            headers={"Retry-After": str(RETRY_AFTER_S)},
        )
    return mode


# ---------- admin routes ----------

admin_router = APIRouter(prefix="/mock-admin", tags=["mock-admin"])


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    expected = settings.admin_key()
    if not expected:
        raise HTTPException(
            status_code=403, detail="admin is switched off (no MOCK_ADMIN_KEY)")
    if not settings.safe_equal(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="bad admin key")


class FaultRequest(BaseModel):
    provider: Literal["bolt", "uber", "ecabs", "all"]
    mode: FaultMode


@admin_router.get("/faults", dependencies=[Depends(require_admin)])
def list_faults():
    return {name: mode.value for name, mode in _modes.items()}


@admin_router.put("/faults", dependencies=[Depends(require_admin)])
def change_fault(body: FaultRequest):
    set_mode(body.provider, body.mode)
    return {name: mode.value for name, mode in _modes.items()}


@admin_router.delete("/faults", dependencies=[Depends(require_admin)])
def clear_faults():
    reset()
    return {name: mode.value for name, mode in _modes.items()}
