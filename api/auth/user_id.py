"""Login ID to hashed user ID (HMAC).

The Microsoft user ID (oid) is never stored. We store a keyed hash of it, so
the saved userId is stable for the same person but cannot be turned back into
the Microsoft ID without the secret key.

WARNING: if USER_ID_HMAC_KEY ever changes, every user gets a new userId and
loses access to their saved trips. Choose it once and keep it safe.
"""

import hashlib
import hmac
import os
from collections.abc import Mapping

MIN_KEY_CHARS = 32


class UserIdSettingError(Exception):
    """USER_ID_HMAC_KEY is missing or too short."""


def load_hmac_key(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    key = env.get("USER_ID_HMAC_KEY", "").strip()
    if len(key) < MIN_KEY_CHARS:
        raise UserIdSettingError(
            f"USER_ID_HMAC_KEY must be set and at least {MIN_KEY_CHARS} characters")
    return key


def make_user_id(tenant_id: str, object_id: str, key: str) -> str:
    message = f"{tenant_id.strip().lower()}:{object_id.strip().lower()}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()
