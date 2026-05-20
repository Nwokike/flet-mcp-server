class FletMCPError(Exception):
    """Base exception for Flet MCP Server errors."""


class DocNotFoundError(FletMCPError):
    """Raised when a documentation file cannot be found."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"Documentation not found: {file_path}")


class PackageNotFoundError(FletMCPError):
    """Raised when a package cannot be found on PyPI."""

    def __init__(self, package_name: str):
        self.package_name = package_name
        super().__init__(f"Package '{package_name}' not found on PyPI.")


class FetchError(FletMCPError):
    """Raised when a network request fails."""

    def __init__(self, url: str, status_code: int | None = None, detail: str | None = None):
        self.url = url
        self.status_code = status_code
        self.detail = detail
        parts = [f"Failed to fetch: {url}"]
        if status_code:
            parts.append(f"HTTP {status_code}")
        if detail:
            parts.append(detail)
        super().__init__(" | ".join(parts))


class TreeFetchError(FetchError):
    """Raised when the GitHub tree API request fails."""

    def __init__(self, repo: str, detail: str | None = None):
        url = f"https://api.github.com/repos/{repo}/git/trees"
        super().__init__(url, detail=detail)
