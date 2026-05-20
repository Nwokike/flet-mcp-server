import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from flet_mcp.http import SharedClient
from flet_mcp.services.github_docs import FletDocsFetcher
from flet_mcp.services.packages import FletPackageFetcher
from flet_mcp.exceptions import DocNotFoundError, PackageNotFoundError, FetchError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Manage server lifecycle: initialize and cleanup shared resources."""
    logger.info("Flet MCP Server starting")
    yield
    logger.info("Flet MCP Server shutting down, cleaning up HTTP client")
    await SharedClient.close()


mcp = FastMCP("Flet MCP Server", lifespan=lifespan)

docs_fetcher = FletDocsFetcher()
pkg_fetcher = FletPackageFetcher()


# --- DOCUMENTATION TOOLS ---

@mcp.tool()
async def search_flet_docs(query: str) -> list[str]:
    """
    Search the official Flet documentation index for a specific topic or control.
    Always use this first to find the correct file path before calling get_flet_doc.

    Args:
        query: The keyword to search for (e.g., 'dropdown', 'navigation', 'layout').
    """
    try:
        return await docs_fetcher.search_docs(query)
    except FetchError as exc:
        logger.error(f"search_flet_docs failed: {exc}")
        return [f"Error searching documentation: {exc}"]


@mcp.tool()
async def get_flet_doc(doc_path: str) -> str:
    """
    Fetch the full Markdown documentation for a specific Flet control or topic.

    Args:
        doc_path: The exact path to the doc file, usually obtained from search_flet_docs
                  (e.g., 'website/docs/controls/dropdown/index.md').
    """
    try:
        return await docs_fetcher.get_doc_content(doc_path)
    except DocNotFoundError:
        return f"Error: Documentation not found for '{doc_path}'. Use search_flet_docs to find valid paths."
    except FetchError as exc:
        logger.error(f"get_flet_doc failed: {exc}")
        return f"Error: Could not fetch documentation: {exc}"


@mcp.tool()
async def list_flet_controls() -> list[str]:
    """
    Get a complete list of all available Flet UI controls.
    Use this to discover what UI elements can be built in Flet.
    """
    try:
        return await docs_fetcher.list_flet_controls()
    except FetchError as exc:
        logger.error(f"list_flet_controls failed: {exc}")
        return [f"Error listing controls: {exc}"]


# --- ECOSYSTEM & PACKAGE TOOLS ---

@mcp.tool()
async def list_official_packages() -> list[str]:
    """
    Get a list of all official Flet extension packages (e.g. flet-audio, flet-video).
    Use this to see what official extra capabilities Flet supports outside the core library.
    """
    try:
        return await pkg_fetcher.list_official_packages()
    except FetchError as exc:
        logger.error(f"list_official_packages failed: {exc}")
        return [f"Error listing packages: {exc}"]


@mcp.tool()
async def search_flet_ecosystem(query: str) -> list[dict]:
    """
    Search the open-source community for third-party Flet packages and components.
    Use this when the user wants to add a feature (e.g., 'calendar', 'table', 'auth')
    that might not be in the core Flet library.

    Args:
        query: The keyword to search for (e.g., 'calendar').
    """
    try:
        return await pkg_fetcher.search_flet_ecosystem(query)
    except FetchError as exc:
        logger.error(f"search_flet_ecosystem failed: {exc}")
        return [{"error": f"Error searching ecosystem: {exc}"}]


@mcp.tool()
async def get_package_details(package_name: str) -> str:
    """
    Fetch PyPI details, current version, and installation instructions for a specific Flet package.

    Args:
        package_name: The exact name of the package on PyPI (e.g., 'flet-audio').
    """
    try:
        return await pkg_fetcher.get_package_details(package_name)
    except PackageNotFoundError:
        return f"Package '{package_name}' not found on PyPI."
    except FetchError as exc:
        logger.error(f"get_package_details failed: {exc}")
        return f"Error fetching package details: {exc}"
