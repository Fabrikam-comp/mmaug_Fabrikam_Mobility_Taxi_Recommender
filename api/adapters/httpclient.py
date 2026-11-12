"""One shared HTTP client for every outside call (providers, maps, rates, AI).

Reusing one client keeps connections open, so each call skips a new secure
handshake. Create it once when the app starts and close it when the app stops.
"""

import httpx2


def create_client(timeout_s: float = 2.0) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        timeout=httpx2.Timeout(timeout_s),
        limits=httpx2.Limits(
            max_connections=50,
            max_keepalive_connections=20,
            keepalive_expiry=30,
        ),
        headers={"User-Agent": "FabrikamTaxiRecommender/1.0 (bootcamp demo)"},
    )
