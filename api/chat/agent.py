"""Chatbot: sends the visitor's message to the Foundry agent and returns its reply.

The browser never talks to Foundry. This file does, with the web app's own Azure
identity (managed identity on Azure, your `az login` on your computer). No key is stored.

Settings (environment variables, plain values, not secrets):
  FOUNDRY_AGENT_RESPONSES_URL  the agent's Responses address, exactly as Foundry shows it
  CHAT_DAILY_CAP               most chat calls per day for the whole site (default 300)
  CHAT_TIMEOUT_S               how long to wait for the agent (default 30)
A missing address only switches the chat off. The rest of the API still starts.
"""

import logging
import os
import re
import time
from collections import deque
from datetime import datetime, timezone

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# the token scope Foundry agent endpoints expect
SCOPE = "https://ai.azure.com/.default"
MAX_MESSAGE_CHARS = 1000
MAX_REPLY_CHARS = 4000
PER_MINUTE = 10  # messages one visitor address may send per minute
SESSION_TTL_S = 30 * 60  # how long the agent remembers a conversation
MAX_SESSIONS = 2000
MAX_TRACKED_CLIENTS = 5000

# source markers an agent with file search may add
_CITATION = re.compile(r"【[^】]*】")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    sessionId: str | None = Field(default=None, max_length=100)


class ChatReply(BaseModel):
    reply: str


class AgentUnavailable(Exception):
    """The agent could not answer. The reason goes to the server log, never to the visitor."""


def client_key(forwarded_for: str, fallback_host: str | None) -> str:
    """Who is calling, for the rate limit. Azure's front end appends the caller's address
    to X-Forwarded-For, so the LAST item is the one a visitor cannot fake. It may carry
    a port. Check this against a real request on Azure."""
    last = forwarded_for.split(",")[-1].strip() if forwarded_for else ""
    if last.startswith("["):  # [IPv6]:port
        host = last[1:].split("]", 1)[0]
    elif last.count(":") == 1:  # IPv4:port
        host = last.split(":", 1)[0]
    else:
        host = last
    return host or fallback_host or "unknown"


class _Limiter:
    """Per-visitor limit per minute, plus one daily cap for the whole site."""

    def __init__(self, per_minute: int, daily_cap: int) -> None:
        self._per_minute = per_minute
        self._daily_cap = daily_cap
        self._hits: dict[str, deque[float]] = {}
        self._day = ""
        self._today = 0

    def check(self, client: str) -> int | None:
        """None means allowed. Otherwise: how many seconds the visitor should wait."""
        now = time.monotonic()
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if day != self._day:
            self._day, self._today = day, 0
        if self._today >= self._daily_cap:
            return 3600
        if len(self._hits) > MAX_TRACKED_CLIENTS:
            self._hits = {k: v for k, v in self._hits.items()
                          if v and now - v[-1] <= 60}
        hits = self._hits.setdefault(client, deque())
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self._per_minute:
            return int(60 - (now - hits[0])) + 1
        hits.append(now)
        self._today += 1
        return None


class _Sessions:
    """Remembers the agent's last response id per conversation, so it can continue it."""

    def __init__(self, ttl_s: float, max_items: int) -> None:
        self._ttl_s = ttl_s
        self._max_items = max_items
        self._items: dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> str | None:
        item = self._items.get(key)
        if item is None:
            return None
        if item[1] < time.monotonic():
            del self._items[key]
            return None
        return item[0]

    def put(self, key: str, response_id: str) -> None:
        if key not in self._items and len(self._items) >= self._max_items:
            del self._items[next(iter(self._items))]  # drop the oldest
        self._items[key] = (response_id, time.monotonic() + self._ttl_s)

    def forget(self, key: str) -> None:
        self._items.pop(key, None)


def _reply_text(data: object) -> str:
    """Pulls the answer text out of a Responses API reply."""
    if not isinstance(data, dict):
        return ""
    parts: list[str] = []
    for item in data.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "message":
            for part in item.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
    text = "".join(parts)
    if not text and isinstance(data.get("output_text"), str):
        text = data["output_text"]
    return _CITATION.sub("", text).strip()[:MAX_REPLY_CHARS]


def _describe_error(response) -> str:
    try:
        error = response.json().get("error", {})
        return f"{error.get('code')}: {str(error.get('message'))[:200]}"
    except Exception:
        return "no readable error body"


class AgentChat:
    def __init__(self, url: str, timeout_s: float, daily_cap: int,
                 credential=None, client=None) -> None:
        # Imported here, so a missing package switches only the chat off, not the whole API.
        if credential is None:
            from azure.identity.aio import DefaultAzureCredential
            credential = DefaultAzureCredential()
        if client is None:
            from api.adapters.httpclient import create_client
            client = create_client(timeout_s=timeout_s)
        self._url = url
        self._credential = credential
        self._client = client
        self._sessions = _Sessions(SESSION_TTL_S, MAX_SESSIONS)
        self.limiter = _Limiter(PER_MINUTE, daily_cap)

    async def close(self) -> None:
        await self._client.aclose()
        await self._credential.close()

    async def _post(self, body: dict, headers: dict):
        return await self._client.post(self._url, json=body, headers=headers)

    async def ask(self, message: str, session_id: str | None) -> str:
        try:
            token = await self._credential.get_token(SCOPE)
            headers = {"Authorization": f"Bearer {token.token}",
                       "Content-Type": "application/json"}
            body: dict = {"input": message}
            previous = self._sessions.get(session_id) if session_id else None
            if previous:
                body["previous_response_id"] = previous

            response = await self._post(body, headers)
            if response.status_code == 400 and previous:
                # The agent may not accept a follow-up id. Start fresh: no memory, but it answers.
                log.warning("agent refused previous_response_id: %s",
                            _describe_error(response))
                self._sessions.forget(session_id)
                body.pop("previous_response_id")
                response = await self._post(body, headers)

            if response.status_code != 200:
                log.warning("agent answered status %s: %s", response.status_code,
                            _describe_error(response))
                raise AgentUnavailable
            data = response.json()
            text = _reply_text(data)
            if not text:
                log.warning("agent answered with no text")
                raise AgentUnavailable
            response_id = data.get("id") if isinstance(data, dict) else None
            if session_id and isinstance(response_id, str):
                self._sessions.put(session_id, response_id)
            return text
        except AgentUnavailable:
            raise
        except Exception as error:  # token problem, timeout, network: all mean "unavailable"
            log.warning("agent call failed: %s", type(error).__name__)
            raise AgentUnavailable from error


_chat: AgentChat | None = None


def get_agent_chat() -> AgentChat | None:
    """Builds the chat on first use. None means the chat is switched off."""
    global _chat
    if _chat is not None:
        return _chat
    url = os.environ.get("FOUNDRY_AGENT_RESPONSES_URL", "").strip()
    if not url:
        return None
    try:
        _chat = AgentChat(
            url,
            float(os.environ.get("CHAT_TIMEOUT_S") or 30),
            int(os.environ.get("CHAT_DAILY_CAP") or 300),
        )
    except Exception as error:
        log.error("chat could not start: %s", type(error).__name__)
        return None
    return _chat


async def close_agent_chat() -> None:
    global _chat
    if _chat is not None:
        await _chat.close()
        _chat = None
