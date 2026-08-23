"""Official Flet example projects, served live from the monorepo.

The examples live under `sdk/python/examples/apps/` — each directory with a
pyproject.toml is a runnable project. We fetch the subtree (cached 24h), so
unlike a prebuilt snapshot the examples are always in sync with the repo.
"""

from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from flet_mcp import config
from flet_mcp.http import SharedClient
from flet_mcp.exceptions import FetchError, SourceError

cache = config.new_cache()

EXAMPLES_SUBTREE = "sdk/python/examples/apps"
MAX_EXAMPLE_CHARS = 24_000


class FletExamplesFetcher:
    """Search and fetch official Flet example apps from GitHub."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._headers = SharedClient.get_headers()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = SharedClient.get()
        return self._client

    async def _fetch_text(self, url: str) -> str | None:
        if url in cache:
            return cache[url]
        try:
            response = await self.client.get(url, headers=SharedClient.auth_headers())
        except httpx.RequestError as exc:
            raise FetchError(url, detail=str(exc)) from exc
        if response.status_code == 200:
            cache.set(url, response.text, expire=86400, tag="github")
            return response.text
        if response.status_code == 404:
            return None
        raise FetchError(url, status_code=response.status_code, detail=response.text[:200])

    async def _tree_paths(self) -> list[str]:
        """All file paths under the examples subtree (cached)."""
        url = (
            f"https://api.github.com/repos/{config.FLET_REPO}/git/trees/"
            f"{quote(f'{config.FLET_BRANCH}:{EXAMPLES_SUBTREE}', safe='')}?recursive=1"
        )
        if url in cache:
            return cache[url]

        try:
            response = await self.client.get(url, headers=self._headers)
        except httpx.RequestError as exc:
            raise FetchError(url, detail=str(exc)) from exc
        if response.status_code != 200:
            raise FetchError(url, status_code=response.status_code, detail=response.text[:200])

        data = response.json()
        paths = [item["path"] for item in data.get("tree", []) if item.get("type") == "blob"]
        cache.set(url, paths, expire=86400, tag="github")
        return paths

    async def _projects(self) -> dict[str, list[str]]:
        """Map of example id (dir with pyproject.toml) -> its files, relative."""
        paths = await self._tree_paths()
        projects: dict[str, list[str]] = {}
        for path in paths:
            if path.endswith("pyproject.toml"):
                projects[path.rsplit("/", 1)[0] if "/" in path else "."] = []
        for path in paths:
            for project in projects:
                if path.startswith(project + "/"):
                    projects[project].append(path)
        return projects

    async def search_examples(self, query: str, max_results: int = 5) -> list[str]:
        """Token match over example ids (paths describe the app, e.g.
        'apps/counter' or 'apps/7guis/flight_booker')."""
        tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if t]
        if not tokens:
            return []

        scored: list[tuple[int, str, int]] = []
        for project_id, files in (await self._projects()).items():
            hay = project_id.lower().replace("/", " ").replace("_", " ")
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((-score, project_id, len(files)))

        scored.sort()
        results = [
            f"{pid} ({files} files) — get with: get_flet_example('{pid}')"
            for _, pid, files in scored[:max_results]
        ]
        if not results:
            return [
                f"No example matches '{query}'. Browse ids with broad terms like "
                "'counter', 'todo', 'grid', 'animation', '7guis', 'routing'."
            ]
        return results

    async def get_example(self, example_id: str, max_chars: int = MAX_EXAMPLE_CHARS) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", example_id) or ".." in example_id:
            raise SourceError(f"Invalid example id: '{example_id}'.")
        projects = await self._projects()
        if example_id not in projects:
            close = sorted(projects)[:10]
            raise SourceError(
                f"Example '{example_id}' not found. Use search_flet_examples first. "
                f"Some available: {', '.join(close)}"
            )

        files = sorted(
            projects[example_id],
            key=lambda p: (0 if p.endswith("pyproject.toml") else 1 if p.endswith(".py") else 2, p),
        )

        out: list[str] = [f"# Example: {example_id} (flet repo, {config.FLET_BRANCH} branch)\n"]
        used = 0
        for path in files:
            if used >= max_chars:
                out.append(f"\n(… remaining files not shown: {path} and later — raise max_chars)")
                break
            url = (
                f"https://raw.githubusercontent.com/{config.FLET_REPO}/"
                f"{config.FLET_BRANCH}/{EXAMPLES_SUBTREE}/{path}"
            )
            content = await self._fetch_text(url)
            if content is None:
                continue
            room = max_chars - used
            truncated = ""
            if len(content) > room:
                content = content[:room]
                truncated = "\n… (file truncated — raise max_chars for the rest)"
            out.append(f"\n## {path}\n```python\n{content}\n```{truncated}")
            used += len(content)

        return "\n".join(out)
