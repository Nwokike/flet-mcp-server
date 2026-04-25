from mcp.server.fastmcp import FastMCP
from flet_mcp.services.github_docs import FletDocsFetcher
from flet_mcp.services.packages import FletPackageFetcher

# Initialize the FastMCP server
mcp = FastMCP("Flet MCP Server")
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
    return await docs_fetcher.search_docs(query)

@mcp.tool()
async def get_flet_doc(doc_path: str) -> str:
    """
    Fetch the full Markdown documentation for a specific Flet control or topic.
    
    Args:
        doc_path: The exact path to the doc file, usually obtained from search_flet_docs 
                  (e.g., 'website/docs/controls/dropdown/index.md').
    """
    return await docs_fetcher.get_doc_content(doc_path)

@mcp.tool()
async def list_flet_controls() -> list[str]:
    """
    Get a complete list of all available Flet UI controls.
    Use this to discover what UI elements can be built in Flet.
    """
    return await docs_fetcher.list_flet_controls()

# --- ECOSYSTEM & PACKAGE TOOLS ---

@mcp.tool()
async def list_official_packages() -> list[str]:
    """
    Get a list of all official Flet extension packages (e.g. flet-audio, flet-video).
    Use this to see what official extra capabilities Flet supports outside the core library.
    """
    return await pkg_fetcher.list_official_packages()

@mcp.tool()
async def search_flet_ecosystem(query: str) -> list[dict]:
    """
    Search the open-source community for third-party Flet packages and components.
    Use this when the user wants to add a feature (e.g., 'calendar', 'table', 'auth') 
    that might not be in the core Flet library.
    
    Args:
        query: The keyword to search for (e.g., 'calendar').
    """
    return await pkg_fetcher.search_flet_ecosystem(query)

@mcp.tool()
async def get_package_details(package_name: str) -> str:
    """
    Fetch PyPI details, current version, and installation instructions for a specific Flet package.
    
    Args:
        package_name: The exact name of the package on PyPI (e.g., 'flet-audio').
    """
    return await pkg_fetcher.get_package_details(package_name)
