"""Token check: proves who is calling the API.

Two kinds of Microsoft Entra token are accepted, so the choice can be made
later with settings only:
  1. an ACCESS token for your API (it has a scope, claim "scp")
  2. the login ID token of your own website (audience = your client ID, no scope)

Every token must have a valid signature (RS256, keys from Microsoft), not be
expired, come from your own tenant (tid) and a known issuer, and have an
accepted audience. The user ID comes ONLY from the verified token (oid).

Settings (environment variables):
  AUTH_MODE                  token (default) or dev. dev is refused on Azure App Service.
  AZURE_AD_TENANTID          your tenant ID (existing secret)
  AZURE_AD_CLIENTID          your app registration client ID (existing secret)
  AUTH_REQUIRED_SCOPE        short scope name as it appears in the token claim "scp"
  AUTH_API_AUDIENCE          optional extra audience for access tokens, for example an api:// address
  AUTH_ACCEPT_ACCESS_TOKEN   true (default) or false
  AUTH_ACCEPT_ID_TOKEN       true (default) or false
  AUTH_DEV_OID               fake user for dev mode (default is a fixed test value)
  USER_ID_HMAC_KEY           secret for hashing user IDs
"""

import asyncio
import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from .user_id import load_hmac_key, make_user_id

MAX_TOKEN_CHARS = 8192
CLOCK_SKEW_S = 60
DEV_OID_DEFAULT = "00000000-0000-0000-0000-000000000001"
AZURE_MARKERS = ("WEBSITE_SITE_NAME",
                 "WEBSITE_INSTANCE_ID", "WEBSITE_HOSTNAME")


class AuthSettingError(Exception):
    """A setting is missing or not allowed."""


class AuthError(Exception):
    status = 401

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason  # for logs only, never sent to the caller


class Unauthorized(AuthError):
    status = 401


class Forbidden(AuthError):
    status = 403


class VerifierUnavailable(AuthError):
    status = 503


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    tenant_id: str
    client_id: str
    api_audience: str | None
    required_scope: str | None
    accept_access_token: bool
    accept_id_token: bool
    dev_oid: str


@dataclass(frozen=True)
class CurrentUser:
    user_id: str  # hashed, safe to store
    kind: str  # "access", "id" or "dev"


def _flag(value: str, default: bool) -> bool:
    if not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_auth_settings(env: Mapping[str, str] | None = None) -> AuthSettings:
    env = os.environ if env is None else env

    def get(name: str) -> str:
        return env.get(name, "").strip()

    mode = (get("AUTH_MODE") or "token").lower()
    if mode not in {"token", "dev"}:
        raise AuthSettingError("AUTH_MODE must be token or dev")
    if mode == "dev" and any(env.get(marker) for marker in AZURE_MARKERS):
        raise AuthSettingError(
            "AUTH_MODE=dev is not allowed on Azure App Service")

    accept_access = _flag(get("AUTH_ACCEPT_ACCESS_TOKEN"), True)
    accept_id = _flag(get("AUTH_ACCEPT_ID_TOKEN"), True)
    scope = get("AUTH_REQUIRED_SCOPE") or None

    if mode == "token":
        for name in ("AZURE_AD_TENANTID", "AZURE_AD_CLIENTID"):
            if not get(name):
                raise AuthSettingError(f"missing setting: {name}")
        if not (accept_access or accept_id):
            raise AuthSettingError("at least one token kind must be accepted")
        if accept_access and scope is None:
            raise AuthSettingError(
                "AUTH_REQUIRED_SCOPE is required when access tokens are accepted "
                "(or set AUTH_ACCEPT_ACCESS_TOKEN=false)"
            )

    return AuthSettings(
        mode=mode,
        tenant_id=get("AZURE_AD_TENANTID"),
        client_id=get("AZURE_AD_CLIENTID"),
        api_audience=get("AUTH_API_AUDIENCE") or None,
        required_scope=scope,
        accept_access_token=accept_access,
        accept_id_token=accept_id,
        dev_oid=get("AUTH_DEV_OID") or DEV_OID_DEFAULT,
    )


def _bearer(header: str | None) -> str:
    if not header:
        raise Unauthorized("missing token", "no Authorization header")
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise Unauthorized("invalid token", "not a Bearer header")
    token = parts[1].strip()
    if not token or len(token) > MAX_TOKEN_CHARS:
        raise Unauthorized("invalid token", "empty or too long")
    return token


def _audiences(claim) -> list[str]:
    if isinstance(claim, str):
        return [claim.lower()]
    return [str(item).lower() for item in claim]


class Authenticator:
    def __init__(
        self,
        settings: AuthSettings,
        hmac_key: str,
        key_fetcher: Callable[[str], Awaitable[object]] | None = None,
    ) -> None:
        self._settings = settings
        self._hmac_key = hmac_key
        if key_fetcher is None and settings.mode == "token":
            jwks = PyJWKClient(
                f"https://login.microsoftonline.com/{settings.tenant_id}/discovery/v2.0/keys",
                cache_keys=True,
            )

            async def key_fetcher(token: str):
                # PyJWKClient does a blocking web call, so run it in a worker thread.
                signing_key = await asyncio.to_thread(jwks.get_signing_key_from_jwt, token)
                return signing_key.key

        self._fetch_key = key_fetcher

    async def authenticate(self, authorization: str | None) -> CurrentUser:
        settings = self._settings
        if settings.mode == "dev":
            tenant = settings.tenant_id or "dev"
            return CurrentUser(make_user_id(tenant, settings.dev_oid, self._hmac_key), "dev")

        claims = await self._verify(_bearer(authorization))
        return self._identify(claims)

    async def _verify(self, token: str) -> dict:
        settings = self._settings
        audiences = {settings.client_id}
        if settings.api_audience:
            audiences.add(settings.api_audience)
        try:
            key = await self._fetch_key(token)
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=sorted(audiences),
                leeway=CLOCK_SKEW_S,
                options={"require": ["exp", "iss", "aud", "oid", "tid"]},
            )
        except PyJWKClientConnectionError as exc:
            raise VerifierUnavailable(
                "cannot verify tokens right now", type(exc).__name__) from exc
        except jwt.PyJWTError as exc:
            raise Unauthorized("invalid or expired token",
                               type(exc).__name__) from exc

    def _identify(self, claims: dict) -> CurrentUser:
        settings = self._settings
        tid = str(claims["tid"]).lower()
        if tid != settings.tenant_id.lower():
            raise Unauthorized("invalid or expired token", "wrong tenant")
        allowed_issuers = {
            f"https://login.microsoftonline.com/{tid}/v2.0",  # v2.0 tokens
            f"https://sts.windows.net/{tid}/",  # v1.0 tokens
        }
        if claims["iss"] not in allowed_issuers:
            raise Unauthorized("invalid or expired token", "wrong issuer")

        audiences = _audiences(claims["aud"])
        client_id = settings.client_id.lower()

        if "scp" in claims:  # an access token for the API
            if not settings.accept_access_token:
                raise Unauthorized("invalid or expired token",
                                   "access tokens not accepted")
            allowed = {client_id}
            if settings.api_audience:
                allowed.add(settings.api_audience.lower())
            if not any(a in allowed for a in audiences):
                raise Unauthorized(
                    "invalid or expired token", "wrong audience")
            if settings.required_scope not in str(claims["scp"]).split():
                raise Forbidden(
                    "this token does not have the required permission", "missing scope")
            kind = "access"
        else:  # the login ID token
            if not settings.accept_id_token:
                raise Unauthorized("invalid or expired token",
                                   "ID tokens not accepted")
            if client_id not in audiences:
                raise Unauthorized(
                    "invalid or expired token", "wrong audience")
            # An app-only token (no user) must never pass as a login token.
            if claims.get("idtyp") == "app" or "roles" in claims:
                raise Unauthorized("invalid or expired token", "app token")
            kind = "id"

        return CurrentUser(make_user_id(tid, str(claims["oid"]), self._hmac_key), kind)


def build_authenticator(env: Mapping[str, str] | None = None) -> Authenticator:
    """Reads the settings and builds the one shared Authenticator (call at app start)."""
    return Authenticator(load_auth_settings(env), load_hmac_key(env))
