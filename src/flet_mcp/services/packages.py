import os
import httpx
import diskcache

CACHE_DIR = os.environ.get("FLET_MCP_CACHE_DIR", "/tmp/flet-mcp-cache")
cache = diskcache.Cache(CACHE_DIR)

class FletPackageFetcher:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)
        self.github_headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Flet-MCP-Server/0.1.1"
        }
        if token := os.getenv("GITHUB_TOKEN"):
            self.github_headers["Authorization"] = f"Bearer {token}"

    _FALLBACK_OFFICIAL = [
        "flet-ads", "flet-audio", "flet-audio-recorder", "flet-camera",
        "flet-charts", "flet-code-editor", "flet-color-pickers", "flet-datatable2",
        "flet-flashlight", "flet-geolocator", "flet-lottie", "flet-map",
        "flet-permission-handler", "flet-rive", "flet-secure-storage",
        "flet-video", "flet-webview"
    ]

    async def _fetch_json(self, url: str, headers: dict | None = None) -> dict | None:
        if url in cache:
            return cache[url]
        try:
            response = await self.client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                cache.set(url, data, expire=86400)
                return data
        except Exception:
            pass
        return None

    async def list_official_packages(self) -> list[str]:
        """Scrapes the Flet monorepo to find all official extensions."""
        url = "https://api.github.com/repos/flet-dev/flet/git/trees/main?recursive=1"
        data = await self._fetch_json(url, headers=self.github_headers)
        
        if not data or "tree" not in data:
            return self._FALLBACK_OFFICIAL 

        packages = []
        for item in data["tree"]:
            path = item["path"]
            if path.startswith("sdk/python/packages/") and item["type"] == "tree":
                parts = path.split("/")
                if len(parts) == 4: 
                    packages.append(parts[3])
                    
        return sorted(list(set(packages))) if packages else self._FALLBACK_OFFICIAL

    async def _is_true_flet_package(self, package_name: str) -> bool:
        """Verifies PyPI metadata to ensure the package actually depends on flet."""
        url = f"https://pypi.org/pypi/{package_name}/json"
        data = await self._fetch_json(url)
        
        if not data or "info" not in data:
            return False
            
        requires_dist = data["info"].get("requires_dist")
        if not requires_dist:
            # Some packages might be Flet related but not strictly depend on 'flet' in metadata
            # but for a 'strict' check we require it.
            return False
            
        for req in requires_dist:
            # Clean up requirement string (e.g. 'flet (>=0.1.1) ; extra == "all"')
            dep_name = req.split(";")[0].split(" ")[0].split(">")[0].split("=")[0].split("<")[0]
            base_name = dep_name.split("[")[0].strip().lower()
            if base_name == "flet":
                return True
        return False

    async def search_flet_ecosystem(self, query: str) -> list[dict]:
        """Searches GitHub for third-party Flet packages and verifies them."""
        search_query = f"flet {query} language:python"
        url = f"https://api.github.com/search/repositories?q={search_query}&sort=stars&order=desc&per_page=15"
        
        data = await self._fetch_json(url, headers=self.github_headers)
        if not data or "items" not in data:
            return []

        results = []
        for item in data["items"]:
            # Check if this GitHub repo is actually a published PyPI package depending on flet
            repo_name = item["name"]
            is_verified = await self._is_true_flet_package(repo_name)
            
            results.append({
                "name": repo_name,
                "full_name": item["full_name"],
                "description": item["description"],
                "stars": item["stargazers_count"],
                "url": item["html_url"],
                "is_verified_flet_package": is_verified
            })
        return results

    async def get_package_details(self, package_name: str) -> str:
        """Fetches detailed package info and installation instructions from PyPI."""
        url = f"https://pypi.org/pypi/{package_name}/json"
        data = await self._fetch_json(url)
        
        if not data or "info" not in data:
            return f"Package '{package_name}' not found on PyPI."

        info = data["info"]
        version = info.get("version", "Unknown")
        summary = info.get("summary", "No summary available.")
        
        # Smart Classification
        pkg_type = "Python Package"
        summary_lower = summary.lower()
        if "control" in summary_lower or "widget" in summary_lower or "ui" in summary_lower:
            pkg_type = "UI Control"
        elif "service" in summary_lower or "auth" in summary_lower or "database" in summary_lower:
            pkg_type = "Service Integration"

        details = (
            f"Package: {package_name} (v{version})\n"
            f"Type: {pkg_type}\n"
            f"Summary: {summary}\n\n"
            f"Installation:\n```bash\n"
            f"uv add {package_name}\n```\n"
        )
        return details
