import os
import httpx
import diskcache

# Set up a persistent local cache
# In cloud/docker environments, /tmp is usually writable
CACHE_DIR = os.environ.get("FLET_MCP_CACHE_DIR", "/tmp/flet-mcp-cache")
cache = diskcache.Cache(CACHE_DIR)

class FletDocsFetcher:
    """Fetches and caches Flet documentation from the official GitHub repo."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Flet-MCP-Server/0.1.1"
        }
        # If the user has a GITHUB_TOKEN, use it to vastly expand API limits
        if token := os.getenv("GITHUB_TOKEN"):
            self.headers["Authorization"] = f"Bearer {token}"

    async def _fetch_json(self, url: str) -> dict | list | None:
        """Helper to fetch and cache JSON responses (24-hour TTL)."""
        if url in cache:
            return cache[url]

        response = await self.client.get(url, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            cache.set(url, data, expire=86400)  # 86400 seconds = 24 hours
            return data
        return None

    async def _fetch_text(self, url: str) -> str | None:
        """Helper to fetch and cache raw Markdown text (24-hour TTL)."""
        if url in cache:
            return cache[url]

        response = await self.client.get(url)
        if response.status_code == 200:
            text = response.text
            cache.set(url, text, expire=86400)
            return text
        return None

    async def get_docs_tree(self) -> list[str]:
        """Gets a flat list of all Markdown documentation paths in the Flet repo."""
        # The Tree API is the most efficient way to get all files in a repo at once
        repo_api_url = "https://api.github.com/repos/flet-dev/flet/git/trees/main?recursive=1"
        data = await self._fetch_json(repo_api_url)

        if not data or "tree" not in data:
            return []

        # Filter out everything except markdown files in the docs folder
        doc_paths = [
            item["path"] for item in data["tree"]
            if item["path"].startswith("website/docs/") and item["path"].endswith(".md")
        ]
        return doc_paths

    async def get_doc_content(self, file_path: str) -> str:
        """Fetches the raw Markdown content for a specific Flet doc file."""
        # Use raw.githubusercontent for fast, quota-free raw file fetching
        raw_url = f"https://raw.githubusercontent.com/flet-dev/flet/main/{file_path}"
        content = await self._fetch_text(raw_url)

        if content:
            return content
        return f"Error: Could not fetch documentation for {file_path}. Ensure the path is correct."

    async def search_docs(self, query: str) -> list[str]:
        """A keyword search over the available document paths."""
        all_docs = await self.get_docs_tree()
        query_lower = query.lower()

        # Filter paths that contain the query string 
        # e.g., querying "dropdown" will match "docs/docs/controls/dropdown.md"
        matches = [path for path in all_docs if query_lower in path.lower()]
        return matches

    async def list_flet_controls(self) -> list[str]:
        """Returns a list of all available Flet UI controls."""
        all_docs = await self.get_docs_tree()
        
        # Filter only the files that live in the controls directory
        controls = []
        for path in all_docs:
            if "website/docs/controls/" in path:
                # Extract just the control name from the path (e.g., 'dropdown/index.md' -> 'dropdown')
                parts = path.split("website/docs/controls/")
                if len(parts) > 1:
                    clean_name = parts[1].split("/")[0].replace(".md", "")
                    if clean_name not in controls:
                        controls.append(clean_name)
        
        return sorted(controls)
