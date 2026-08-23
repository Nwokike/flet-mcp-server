import asyncio
from urllib.parse import quote

import httpx

from flet_mcp import config
from flet_mcp.http_client import SharedClient
from flet_mcp.exceptions import FetchError, PackageNotFoundError

cache = config.new_cache()

PACKAGES_SUBTREE = "sdk/python/packages"

# Max concurrent PyPI checks to avoid rate limiting
MAX_CONCURRENT_VERIFICATIONS = 3

_FALLBACK_OFFICIAL = [
    "flet",
    "flet-ads",
    "flet-audio",
    "flet-audio-recorder",
    "flet-camera",
    "flet-charts",
    "flet-cli",
    "flet-code-editor",
    "flet-color-pickers",
    "flet-datatable2",
    "flet-desktop",
    "flet-flashlight",
    "flet-geolocator",
    "flet-lottie",
    "flet-map",
    "flet-permission-handler",
    "flet-rive",
    "flet-secure-storage",
    "flet-video",
    "flet-web",
    "flet-webview",
]


class FletPackageFetcher:
    """Fetches and verifies Flet packages from GitHub and PyPI."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._github_headers = SharedClient.get_headers()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = SharedClient.get()
        return self._client

    async def _fetch_json(self, url: str, headers: dict | None = None) -> dict | None:
        """Fetch and cache JSON responses (24-hour TTL).

        Returns None only for a genuine 404 (callers treat it as "not found");
        network failures and error statuses raise FetchError.
        """
        if url in cache:
            return cache[url]

        try:
            response = await self.client.get(url, headers=headers or self._github_headers)
        except httpx.RequestError as exc:
            raise FetchError(url, detail=str(exc)) from exc

        if response.status_code == 200:
            data = response.json()
            tag = "github" if "github.com" in url else "pypi"
            cache.set(url, data, expire=86400, tag=tag)
            return data
        if response.status_code == 404:
            return None
        raise FetchError(url, status_code=response.status_code, detail=response.text[:200])

    async def list_official_packages(self) -> list[str]:
        """Lists official Flet packages from the monorepo's packages directory."""
        api = f"https://api.github.com/repos/{config.FLET_REPO}/git/trees"

        # The packages dir's direct children are the packages — no recursion needed.
        subtree_ref = quote(f"{config.FLET_BRANCH}:{PACKAGES_SUBTREE}", safe="")
        try:
            data = await self._fetch_json(f"{api}/{subtree_ref}")
        except FetchError:
            data = None

        if isinstance(data, dict) and data.get("tree"):
            packages = {item["path"] for item in data["tree"] if item.get("type") == "tree"}
            if packages:
                # Normalise to PyPI-style distribution names and include the core.
                return sorted({f"flet-{p}" if not p.startswith("flet") else p for p in packages})

        return _FALLBACK_OFFICIAL

    async def _is_true_flet_package(self, package_name: str) -> bool:
        """Verifies PyPI metadata to ensure the package actually depends on flet."""
        url = f"https://pypi.org/pypi/{package_name}/json"
        data = await self._fetch_json(url)

        if not data or "info" not in data:
            return False

        requires_dist = data["info"].get("requires_dist")
        if not requires_dist:
            return False

        for req in requires_dist:
            dep_name = req.split(";")[0].split(" ")[0].split(">")[0].split("=")[0].split("<")[0]
            base_name = dep_name.split("[")[0].strip().lower()
            if base_name == "flet":
                return True
        return False

    async def _verify_batch(self, items: list[dict]) -> list[dict]:
        """Verify a batch of packages concurrently with rate limiting."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_VERIFICATIONS)

        async def verify_one(item: dict) -> dict:
            async with semaphore:
                repo_name = item["name"]
                is_verified = await self._is_true_flet_package(repo_name)
                return {**item, "is_verified_flet_package": is_verified}

        tasks = [verify_one(item) for item in items]
        return await asyncio.gather(*tasks)

    async def search_flet_ecosystem(self, query: str) -> list[dict]:
        """Searches GitHub for third-party Flet packages and verifies them."""
        search_query = f"flet {query} language:python"
        url = (
            f"https://api.github.com/search/repositories"
            f"?q={search_query}&sort=stars&order=desc&per_page=15"
        )

        data = await self._fetch_json(url, headers=self._github_headers)
        if not data or "items" not in data:
            return []

        results = []
        for item in data["items"]:
            results.append(
                {
                    "name": item["name"],
                    "full_name": item["full_name"],
                    "description": item["description"],
                    "stars": item["stargazers_count"],
                    "url": item["html_url"],
                }
            )

        # Verify in batches to avoid overwhelming PyPI
        verified = await self._verify_batch(results)
        return verified

    async def get_package_details(self, package_name: str) -> str:
        """Fetches detailed package info and installation instructions from PyPI."""
        url = f"https://pypi.org/pypi/{package_name}/json"
        data = await self._fetch_json(url)

        if not data or "info" not in data:
            raise PackageNotFoundError(package_name)

        info = data["info"]
        version = info.get("version", "Unknown")
        summary = info.get("summary", "No summary available.")

        pkg_type = "Python Package"
        summary_lower = summary.lower()
        if any(kw in summary_lower for kw in ("control", "widget", "ui")):
            pkg_type = "UI Control"
        elif any(kw in summary_lower for kw in ("service", "auth", "database")):
            pkg_type = "Service Integration"

        return (
            f"Package: {package_name} (v{version})\n"
            f"Type: {pkg_type}\n"
            f"Summary: {summary}\n\n"
            f"Installation:\n```bash\n"
            f"uv add {package_name}\n```\n"
        )
