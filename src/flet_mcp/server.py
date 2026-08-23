import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from starlette.responses import PlainTextResponse

from flet_mcp.http import SharedClient
from flet_mcp.models import Diagnostic, FletVersionInfo, VerifyReport
from flet_mcp.services.flet_source import (
    VENV_ENV_VAR,
    inspect_control,
    list_api,
    read_source,
    resolve_flet,
    search_colors,
    search_icons,
    search_source,
)
from flet_mcp.services.flet_verify import DEFAULT_TIMEOUT_SECS, verify_code
from flet_mcp.services.github_docs import FletDocsFetcher
from flet_mcp.services.packages import FletPackageFetcher
from flet_mcp.services.examples import FletExamplesFetcher
from flet_mcp.exceptions import (
    DocNotFoundError,
    FetchError,
    PackageNotFoundError,
    SourceError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

INSTRUCTIONS = f"""Tools for building apps with Flet, the Python UI framework.

CRITICAL: Flet's API changes faster than your training data. Controls, properties
and event names you remember may be renamed, deprecated or removed (e.g.
ElevatedButton and its `text` argument are both gone in current flet). Work like
this:

1. inspect_flet_control(name) — exact, current API for any control: every
   property, type, default, event and deprecation, from the installed source.
2. verify_flet_code(code) — ALWAYS run this before delivering Flet code: it
   checks it against the installed flet (static + a sandboxed execution that
   fires flet's own validators) and reports every error with line numbers.
   Fix and re-verify until status is 'passed'.
3. get_flet_version() — which flet version these tools are reading.
4. search_flet_source / read_flet_source — grep and read the implementation.
5. search_flet_icons / search_flet_colors — valid constant names (never guess).
6. Docs tools (search_flet_docs, get_flet_doc, list_flet_controls) — official
   guides and cookbook patterns; search_flet_examples / get_flet_example —
   real runnable apps for learning idioms.
7. Ecosystem tools — official and third-party flet packages on PyPI.

This server reads the flet package installed alongside it. To verify against
YOUR project's exact flet version, set {VENV_ENV_VAR}=/path/to/project/.venv in
the server's environment, or run it with: uvx --with flet==<version> flet-mcp-server."""


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[None]:
    """Manage server lifecycle: initialize and cleanup shared resources."""
    logger.info("Flet MCP Server starting")
    try:
        flet_info = resolve_flet()
        logger.info(
            "Reading flet %s from %s (%s)", flet_info.version, flet_info.pkg_dir, flet_info.source
        )
    except SourceError as exc:
        logger.warning("Flet source tools unavailable: %s", exc)
    yield
    logger.info("Flet MCP Server shutting down, cleaning up HTTP client")
    await SharedClient.close()


mcp = MCPServer(
    name="Flet MCP Server",
    instructions=INSTRUCTIONS,
    lifespan=lifespan,
    cache_hints={
        "tools/list": CacheHint(ttl_ms=600_000),
        "resources/list": CacheHint(ttl_ms=600_000),
        "resources/templates/list": CacheHint(ttl_ms=600_000),
        "prompts/list": CacheHint(ttl_ms=600_000),
    },
)

docs_fetcher = FletDocsFetcher()
pkg_fetcher = FletPackageFetcher()
examples_fetcher = FletExamplesFetcher()

_READONLY = dict(read_only_hint=True, destructive_hint=False)


# --- CODE VERIFICATION (flagship) ---


@mcp.tool(annotations=ToolAnnotations(title="Verify Flet code", **_READONLY))
async def verify_flet_code(code: str, timeout_secs: int = DEFAULT_TIMEOUT_SECS) -> VerifyReport:
    """
    Verify Flet code against the INSTALLED flet — ALWAYS call this before
    delivering Flet code to the user. Two passes: (1) static analysis for
    unknown controls, invalid constructor properties, enum typos, deprecated
    usage and undefined event handlers, each with line numbers and hints;
    (2) sandboxed execution that constructs the controls (app launchers are
    neutralized, nothing opens) and fires flet's own validators, catching
    errors that only appear at runtime (e.g. Slider(min > max)). Fix every
    diagnostic and re-verify until status == 'passed'.

    Args:
        code: Complete, runnable Flet app code (a main(page) function plus
              ft.app(main) is ideal — main is invoked against a mock page).
        timeout_secs: Execution timeout for the sandbox (default 15, max 60).
    """
    timeout_secs = max(1, min(int(timeout_secs), 60))
    try:
        return await verify_code(code, timeout_secs)
    except SourceError as exc:
        logger.error("verify_flet_code failed: %s", exc)
        return VerifyReport(
            status="errors",
            flet_version="unknown",
            checks=[],
            controls_verified=0,
            duration_ms=0,
            diagnostics=[Diagnostic(severity="error", code="source", message=str(exc))],
        )


# --- SOURCE-OF-TRUTH TOOLS (installed flet) ---


@mcp.tool(annotations=ToolAnnotations(title="Get flet version", **_READONLY))
async def get_flet_version() -> FletVersionInfo:
    """
    Report which flet version the source tools read, and from where.
    Call this first when a Flet API question matters — Flet changes faster than
    model training data, so the installed source is the only truth.
    """
    try:
        r = resolve_flet()
        return FletVersionInfo(flet_version=r.version, package_path=str(r.pkg_dir), source=r.source)
    except SourceError as exc:
        logger.error("get_flet_version failed: %s", exc)
        return FletVersionInfo(flet_version="", package_path="", source="", error=str(exc))


@mcp.tool(annotations=ToolAnnotations(title="Inspect a flet control", **_READONLY))
async def inspect_flet_control(control_name: str) -> str:
    """
    Get the exact, current API of any Flet control straight from the installed
    source: every property with its type and default (inherited ones marked),
    events (on_*), deprecation warnings, the class hierarchy, and the full class
    source with per-property docstrings. ALWAYS use this before writing Flet UI
    code — control APIs in training data are often outdated.

    Args:
        control_name: Public flet class name, e.g. 'Button', 'TextField',
                      'CupertinoSwitch', 'Page', 'View'.
    """
    try:
        return inspect_control(control_name)
    except SymbolNotFoundError as exc:
        return f"Error: {exc}"
    except SourceError as exc:
        logger.error("inspect_flet_control failed: %s", exc)
        return f"Error: {exc}"


@mcp.tool(annotations=ToolAnnotations(title="Search flet source", **_READONLY))
async def search_flet_source(query: str, max_results: int = 25) -> list[str]:
    """
    Search the installed flet source code (every .py file in the flet package).
    Class and function definitions rank first, then assignments, then comments.
    Use this to find where anything is defined, which modules exist, or how a
    feature is actually implemented in the CURRENT version.

    Args:
        query: Case-insensitive substring, e.g. 'Snackbar', 'on_route_change',
               'adaptive', 'cupertino_switch'.
        max_results: Maximum matches to return (default 25).
    """
    try:
        return search_source(query, max_results)
    except SourceError as exc:
        logger.error("search_flet_source failed: %s", exc)
        return [f"Error: {exc}"]


@mcp.tool(annotations=ToolAnnotations(title="Read flet source", **_READONLY))
async def read_flet_source(module: str, symbol: str | None = None, max_lines: int = 400) -> str:
    """
    Read the actual installed source of a flet module (numbered lines). This is
    the ground truth when docs and training data disagree.

    Args:
        module: Dotted module or path relative to the flet package, e.g.
                'controls/material/button.py', 'flet.controls.page', 'controls/types'.
        symbol: Optional class or function to extract instead of the whole file
                (e.g. 'Button', 'Page', 'Button.style' or 'app').
        max_lines: Line cap when reading a whole file (default 400).
    """
    try:
        return read_source(module, symbol, max_lines)
    except (SourceError, SymbolNotFoundError) as exc:
        return f"Error: {exc}"


@mcp.tool(annotations=ToolAnnotations(title="List flet API", **_READONLY))
async def list_flet_api() -> dict[str, list[str] | str]:
    """
    List every public name in the installed flet (the true flet.__all__), grouped
    by category: Material/Cupertino/Core controls, Services, Components & hooks,
    types. Use this to discover what exists in the CURRENT version before
    guessing control or API names.
    """
    try:
        return list_api()  # type: ignore[return-value]
    except SourceError as exc:
        logger.error("list_flet_api failed: %s", exc)
        return {"error": str(exc)}


@mcp.tool(annotations=ToolAnnotations(title="Search flet icons", **_READONLY))
async def search_flet_icons(
    query: str, icon_set: str = "material", max_results: int = 50
) -> list[str]:
    """
    Search valid flet icon names for ft.Icons.* / ft.CupertinoIcons.*. NEVER
    invent icon names — models consistently hallucinate them. This reads the
    icon database of the installed flet version.

    Args:
        query: Icon name fragment, e.g. 'home', 'arrow_back', 'delete_outline'.
        icon_set: 'material' (ft.Icons, default) or 'cupertino' (ft.CupertinoIcons).
        max_results: Maximum names to return (default 50).
    """
    try:
        return search_icons(query, icon_set, max_results)
    except SourceError as exc:
        logger.error("search_flet_icons failed: %s", exc)
        return [f"Error: {exc}"]


@mcp.tool(annotations=ToolAnnotations(title="Search flet colors", **_READONLY))
async def search_flet_colors(query: str, max_results: int = 50) -> list[str]:
    """
    Search valid flet color constants (ft.Colors.*, incl. shades like AMBER_500,
    and ft.CupertinoColors.*). Use this instead of guessing color names.

    Args:
        query: Color name fragment, e.g. 'amber', 'teal', 'primary', 'error'.
        max_results: Maximum names to return (default 50).
    """
    try:
        return search_colors(query, max_results)
    except SourceError as exc:
        logger.error("search_flet_colors failed: %s", exc)
        return [f"Error: {exc}"]


# --- DOCUMENTATION TOOLS (official guides) ---


@mcp.tool(annotations=ToolAnnotations(title="Search flet docs", **_READONLY))
async def search_flet_docs(query: str) -> list[str]:
    """
    Search the official Flet documentation index for a specific topic or control.
    Always use this first to find the correct file path before calling get_flet_doc.
    Docs explain intent and cookbook patterns; use the source tools for exact APIs.

    Args:
        query: The keyword to search for (e.g., 'dropdown', 'navigation', 'layout').
    """
    try:
        return await docs_fetcher.search_docs(query)
    except FetchError as exc:
        logger.error("search_flet_docs failed: %s", exc)
        return [f"Error searching documentation: {exc}"]


@mcp.tool(annotations=ToolAnnotations(title="Get flet doc page", **_READONLY))
async def get_flet_doc(doc_path: str, offset: int = 0, max_lines: int = 400) -> str:
    """
    Fetch the Markdown documentation for a specific Flet control or topic, paged
    to keep responses small. Long pages are cut off with a hint for the next
    `offset` — page through instead of dumping huge docs into the conversation.

    Args:
        doc_path: The exact path of the doc file, usually obtained from search_flet_docs
                  (e.g., 'website/docs/controls/dropdown/index.md').
        offset: Line to start from (default 0; the response tells you the next offset).
        max_lines: Maximum lines to return per call (default 400).
    """
    try:
        content = await docs_fetcher.get_doc_content(doc_path)
    except DocNotFoundError:
        return f"Error: Documentation not found for '{doc_path}'. Use search_flet_docs to find valid paths."
    except FetchError as exc:
        logger.error("get_flet_doc failed: %s", exc)
        return f"Error: Could not fetch documentation: {exc}"

    lines = content.splitlines()
    offset = max(0, min(offset, len(lines)))
    chunk = lines[offset : offset + max_lines]
    more = (
        f"\n\n… ({len(lines)} lines total — call get_flet_doc again with "
        f"offset={offset + max_lines} for the rest)"
        if offset + max_lines < len(lines)
        else ""
    )
    return "\n".join(chunk) + more


# --- OFFICIAL EXAMPLES (live from the flet repo) ---


@mcp.tool(annotations=ToolAnnotations(title="Search flet examples", **_READONLY))
async def search_flet_examples(query: str, max_results: int = 5) -> list[str]:
    """
    Search the official Flet example apps in the flet repo (counter, todo, 7guis,
    routing, games, declarative components, …) by keyword. Each result is a
    runnable project; fetch its full source with get_flet_example. Reading a real
    example is the fastest way to learn correct Flet idioms for a pattern.

    Args:
        query: Keywords describing the app or pattern (e.g., 'counter', 'todo',
               'routing', 'drag', 'animation', 'form validation').
        max_results: Maximum results (default 5).
    """
    try:
        return await examples_fetcher.search_examples(query, max_results)
    except FetchError as exc:
        logger.error("search_flet_examples failed: %s", exc)
        return [f"Error searching examples: {exc}"]


@mcp.tool(annotations=ToolAnnotations(title="Get flet example source", **_READONLY))
async def get_flet_example(example_id: str, max_chars: int = 24000) -> str:
    """
    Fetch the full source of an official Flet example app (from
    search_flet_examples): pyproject.toml plus its Python files, bundled with a
    character budget so huge examples page gracefully.

    Args:
        example_id: Example id from search_flet_examples (e.g., 'counter' or
                    '7guis/flight_booker').
        max_chars: Total character budget for the returned source (default 24000).
    """
    try:
        return await examples_fetcher.get_example(example_id, max_chars)
    except SourceError as exc:
        return f"Error: {exc}"
    except FetchError as exc:
        logger.error("get_flet_example failed: %s", exc)
        return f"Error fetching example: {exc}"


@mcp.tool(annotations=ToolAnnotations(title="List documented controls", **_READONLY))
async def list_flet_controls() -> list[str]:
    """
    Get a list of all Flet UI controls that have a documentation page.
    For the complete programmatic API surface of the installed version
    (including undocumented controls, services and hooks), use list_flet_api.
    """
    try:
        return await docs_fetcher.list_flet_controls()
    except FetchError as exc:
        logger.error("list_flet_controls failed: %s", exc)
        return [f"Error listing controls: {exc}"]


# --- ECOSYSTEM & PACKAGE TOOLS ---


@mcp.tool(annotations=ToolAnnotations(title="List official packages", **_READONLY))
async def list_official_packages() -> list[str]:
    """
    Get a list of all official Flet extension packages (e.g. flet-audio, flet-video).
    Use this to see what official extra capabilities Flet supports outside the core library.
    """
    try:
        return await pkg_fetcher.list_official_packages()
    except FetchError as exc:
        logger.error("list_official_packages failed: %s", exc)
        return [f"Error listing packages: {exc}"]


@mcp.tool(annotations=ToolAnnotations(title="Search flet ecosystem", **_READONLY))
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
        logger.error("search_flet_ecosystem failed: %s", exc)
        return [{"error": f"Error searching ecosystem: {exc}"}]


@mcp.tool(annotations=ToolAnnotations(title="Get package details", **_READONLY))
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
        logger.error("get_package_details failed: %s", exc)
        return f"Error fetching package details: {exc}"


# --- PROMPTS (guided workflows) ---


@mcp.prompt()
def verify_flet_code_prompt(code: str) -> list[dict]:
    """Verify the given Flet code, fix every diagnostic against the installed API, and re-verify until it passes."""
    return [
        {
            "role": "user",
            "content": (
                "Verify this Flet code with the verify_flet_code tool. For every diagnostic, "
                "look up the correct current API with inspect_flet_control (and read_flet_source "
                "if needed), fix the code, and re-verify. Only present code whose final report "
                f"has status 'passed'.\n\n```\n{code}\n```"
            ),
        }
    ]


@mcp.prompt()
def migrate_flet_prompt(project_summary: str) -> list[dict]:
    """Hunt deprecated/outdated Flet API usage in a codebase and migrate it to the installed flet version."""
    return [
        {
            "role": "user",
            "content": (
                "I will migrate a Flet codebase to the installed flet version. First call "
                "get_flet_version. Then, for every control mentioned below, call "
                "inspect_flet_control to get its CURRENT properties, events and deprecations, "
                "and rewrite the code accordingly. Finish by verifying the rewritten code with "
                "verify_flet_code until it passes.\n\nProject summary / code:\n"
                f"{project_summary}"
            ),
        }
    ]


@mcp.prompt()
def build_flet_ui_prompt(spec: str) -> list[dict]:
    """Build a Flet UI from a specification: inspect the controls first, write the code, then verify it before presenting."""
    return [
        {
            "role": "user",
            "content": (
                "Build this Flet UI. Workflow: 1) get_flet_version; 2) inspect_flet_control for "
                "every control you plan to use (properties change between versions — do not trust "
                "memory); 3) pick real icon/color names with search_flet_icons / "
                "search_flet_colors; 4) write the code; 5) verify_flet_code and fix until "
                "status is 'passed'; 6) present the verified code.\n\nSpec:\n" + spec
            ),
        }
    ]


# --- RESOURCES (addressable content) ---


@mcp.resource("flet://version", name="Flet version", mime_type="application/json")
def flet_version_resource() -> dict:
    """Which flet install the server reads (version, path, source)."""
    r = resolve_flet()
    return {"flet_version": r.version, "package_path": str(r.pkg_dir), "source": r.source}


@mcp.resource(
    "flet-source://{+module}",
    name="Flet source file",
    mime_type="text/x-python",
    description="Source of any module in the installed flet package (e.g. controls/material/button.py).",
)
def flet_source_resource(module: str) -> str:
    """Serve installed flet source by module path (path-traversal safe)."""
    return read_source(module)


# --- HTTP liveness (served when running in sse / streamable-http mode) ---


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return PlainTextResponse("ok")
