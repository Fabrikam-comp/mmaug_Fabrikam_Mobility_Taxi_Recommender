"""Keys come from environment variables (Azure app settings). Never from code.

Local example (PowerShell):
    $env:MOCK_BOLT_CLIENT_ID = "dev-bolt-id"
    $env:MOCK_BOLT_CLIENT_SECRET = "dev-bolt-secret"
    $env:MOCK_UBER_TOKEN = "dev-uber-token"
    $env:MOCK_ECABS_API_KEY = "dev-ecabs-key"
    $env:MOCK_ADMIN_KEY = "dev-admin-key"
If a key is not set, that provider (or the admin page) refuses every request.
"""

import os
import secrets


def bolt_credentials() -> tuple[str | None, str | None]:
    return os.getenv("MOCK_BOLT_CLIENT_ID"), os.getenv("MOCK_BOLT_CLIENT_SECRET")


def uber_token() -> str | None:
    return os.getenv("MOCK_UBER_TOKEN")


def ecabs_api_key() -> str | None:
    return os.getenv("MOCK_ECABS_API_KEY")


def admin_key() -> str | None:
    return os.getenv("MOCK_ADMIN_KEY")


def fault_timeout_s() -> float:
    """How long a TIMEOUT fault keeps the caller waiting."""
    return float(os.getenv("MOCK_FAULT_TIMEOUT_S", "10"))


def safe_equal(given: str | None, expected: str | None) -> bool:
    """Compare secrets without leaking timing. An unset expected value never matches."""
    if not given or not expected:
        return False
    return secrets.compare_digest(given.encode(), expected.encode())


def bearer_token(authorization: str | None) -> str | None:
    """Pull the token out of 'Bearer <token>'."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
