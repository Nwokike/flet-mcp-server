import os
import httpx


class SharedClient:
    """Singleton-style shared httpx.AsyncClient with lifecycle management."""

    _instance: httpx.AsyncClient | None = None

    @classmethod
    def get(cls) -> httpx.AsyncClient:
        if cls._instance is None or cls._instance.is_closed:
            cls._instance = httpx.AsyncClient(timeout=15.0)
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        if cls._instance and not cls._instance.is_closed:
            await cls._instance.aclose()
            cls._instance = None

    @classmethod
    def get_headers(cls, include_token: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Flet-MCP-Server/0.2.0",
        }
        if include_token and (token := os.getenv("GITHUB_TOKEN")):
            headers["Authorization"] = f"Bearer {token}"
        return headers
