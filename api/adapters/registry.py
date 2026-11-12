"""Reads the settings and builds the adapters.

A provider can be switched off, or pointed at another address, without
touching code. A provider with a missing setting is skipped and the reason is
listed in `problems`, so one mistake does not stop the whole API.

Settings (Azure app settings). Real values, never in the repo:
  ADAPTERS_ENABLED     bolt,uber,ecabs      (optional, default is all three)
  ADAPTER_TIMEOUT_S    2.0                  (optional)
  BOLT_BASE_URL, BOLT_CLIENT_ID, BOLT_CLIENT_SECRET
  UBER_BASE_URL, UBER_SERVER_TOKEN
  ECABS_BASE_URL, ECABS_API_KEY
"""

import os
from dataclasses import dataclass, field
from typing import Callable, Mapping

import httpx2

from api.adapters.base import ProviderAdapter
from api.adapters.bolt import BoltAdapter
from api.adapters.ecabs import ECabsAdapter
from api.adapters.uber import UberAdapter
from api.core.circuit_breaker import CircuitBreaker

ALL_PROVIDERS = ("bolt", "uber", "ecabs")


class MissingSetting(Exception):
    pass


@dataclass
class Registry:
    adapters: list[ProviderAdapter] = field(default_factory=list)
    breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise MissingSetting(f"{key} is not set")
    return value


def _build_bolt(client, env, timeout_s):
    return BoltAdapter(
        client,
        _required(env, "BOLT_BASE_URL"),
        _required(env, "BOLT_CLIENT_ID"),
        _required(env, "BOLT_CLIENT_SECRET"),
        timeout_s=timeout_s,
    )


def _build_uber(client, env, timeout_s):
    return UberAdapter(
        client,
        _required(env, "UBER_BASE_URL"),
        _required(env, "UBER_SERVER_TOKEN"),
        timeout_s=timeout_s,
    )


def _build_ecabs(client, env, timeout_s):
    return ECabsAdapter(
        client,
        _required(env, "ECABS_BASE_URL"),
        _required(env, "ECABS_API_KEY"),
        timeout_s=timeout_s,
    )


_BUILDERS: dict[str, Callable] = {
    "bolt": _build_bolt, "uber": _build_uber, "ecabs": _build_ecabs}


def load_registry(client: httpx2.AsyncClient, env: Mapping[str, str] | None = None) -> Registry:
    env = os.environ if env is None else env
    wanted = [name.strip().lower() for name in env.get(
        "ADAPTERS_ENABLED", ",".join(ALL_PROVIDERS)).split(",") if name.strip()]
    timeout_s = float(env.get("ADAPTER_TIMEOUT_S", "2.0"))

    registry = Registry()
    for name in wanted:
        builder = _BUILDERS.get(name)
        if builder is None:
            registry.problems.append(
                f"unknown adapter '{name}' in ADAPTERS_ENABLED")
            continue
        try:
            adapter = builder(client, env, timeout_s)
        except MissingSetting as error:
            registry.problems.append(f"{name} is switched off: {error}")
            continue
        registry.adapters.append(adapter)
        registry.breakers[adapter.provider_id] = CircuitBreaker()
    return registry
