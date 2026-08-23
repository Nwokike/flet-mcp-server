import os
from datetime import datetime, timezone

import httpx

from flet_mcp.exceptions import RateLimitedError

SERVER_VERSION = "1.0.0"

_GITHUB_HOSTS = {"api.github.com", "raw.githubusercontent.com", "github.com"}


async def _rate_limit_hook(response: httpx.Response) -> None:
    """Turn GitHub rate-limit responses into a friendly, actionable error."""
    if response.request.url.host not in _GITHUB_HOSTS:
        return
    if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
        reset = response.headers.get("x-ratelimit-reset", "")
        when = ""
        if reset.isdigit():
            when = datetime.fromtimestamp(int(reset), tz=timezone.utc).strftime(" at %H:%M UTC")
        raise RateLimitedError(
            str(response.request.url),
            detail=f"GitHub API rate limit exhausted (resets{when}). "
            "Set GITHUB_TOKEN in the server environment for a much higher limit.",
        )
    if response.status_code == 429:
        retry = response.headers.get("retry-after")
        raise RateLimitedError(
            str(response.request.url),
            detail=f"HTTP 429 (retry after {retry}s)" if retry else "HTTP 429",
        )


class SharedClient:
    """Singleton-style shared httpx.AsyncClient with lifecycle management."""

    _instance: httpx.AsyncClient | None = None

    @classmethod
    def get(cls) -> httpx.AsyncClient:
        if cls._instance is None or cls._instance.is_closed:
            cls._instance = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                follow_redirects=True,
                transport=httpx.AsyncHTTPTransport(retries=2),
                event_hooks={"response": [_rate_limit_hook]},
            )
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        if cls._instance and not cls._instance.is_closed:
            await cls._instance.aclose()
            cls._instance = None

    @classmethod
    def auth_headers(cls) -> dict[str, str]:
        """Headers safe for any GitHub endpoint: UA plus token when available."""
        headers = {"User-Agent": f"Flet-MCP-Server/{SERVER_VERSION}"}
        if token := os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @classmethod
    def get_headers(cls, include_token: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"Flet-MCP-Server/{SERVER_VERSION}",
        }
        if include_token and (token := os.getenv("GITHUB_TOKEN")):
            headers["Authorization"] = f"Bearer {token}"
        return headers
