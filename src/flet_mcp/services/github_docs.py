import difflib
import logging
import re
from urllib.parse import quote

import httpx

from flet_mcp import config
from flet_mcp.http_client import SharedClient
from flet_mcp.exceptions import FetchError, DocNotFoundError

logger = logging.getLogger(__name__)

cache = config.new_cache()

DOCS_SUBTREE = "website/docs"

# Keyword alias index for smarter search
# Maps common search terms to doc path fragments
KEYWORD_INDEX = {
    "input": ["textfield", "searchbar", "dropdown", "datepicker", "timepicker", "autocomplete"],
    "text": ["textfield", "text", "markdown", "codeeditor"],
    "button": [
        "filledbutton",
        "outlinedbutton",
        "textbutton",
        "iconbutton",
        "filledtonalbutton",
        "filledtonaliconbutton",
        "fillediconbutton",
        "outlinediconbutton",
        "floatingactionbutton",
        "popupmenubutton",
        "menubar",
        "menuitembutton",
        "submenubutton",
    ],
    "select": [
        "dropdown",
        "dropdownm2",
        "checkbox",
        "radio",
        "radiogroup",
        "switch",
        "segmentedbutton",
        "segment",
        "chip",
    ],
    "list": ["listview", "listtile", "reorderablelistview", "menubar", "cupertinolisttile"],
    "grid": ["gridview", "datatable", "datatable2"],
    "table": ["datatable", "datatable2", "datacolumn", "datarow", "datacell"],
    "dialog": [
        "alertdialog",
        "dialogcontrol",
        "cupertinoalertdialog",
        "cupertinoactionsheet",
        "cupertinodialogaction",
        "cupertinopicker",
    ],
    "nav": ["navigationbar", "navigationrail", "navigationdrawer", "router", "multiview"],
    "navigation": ["navigationbar", "navigationrail", "navigationdrawer", "router", "multiview"],
    "menu": ["menubar", "popupmenubutton", "menuitembutton", "submenubutton", "contextmenu"],
    "layout": ["row", "column", "stack", "container", "responsive", "gridview", "listview"],
    "form": [
        "textfield",
        "checkbox",
        "dropdown",
        "radiogroup",
        "formfieldcontrol",
        "autofillgroup",
    ],
    "image": ["image", "circleavatar", "avatar"],
    "avatar": ["circleavatar"],
    "video": ["video"],
    "audio": [],  # flet-audio is a package, not a control
    "map": ["map"],
    "chart": ["charts"],
    "web": ["webview"],
    "camera": ["camera"],
    "animation": ["animatedswitcher", "lottie", "rive", "shimmer"],
    "progress": ["progressbar", "progressring"],
    "slider": ["slider", "rangeslider"],
    "date": ["datepicker", "daterangepicker", "cupertinodatepicker"],
    "time": ["timepicker", "cupertinotimepicker", "cupertinotimerpicker"],
    "icon": [
        "icon",
        "iconbutton",
        "fillediconbutton",
        "outlinediconbutton",
        "filledtonaliconbutton",
    ],
    "card": ["card"],
    "banner": ["banner"],
    "snackbar": ["snackbar"],
    "tooltip": [],
    "badge": [],
    "tabs": ["tabs", "tab", "tabbar", "tabbarview"],
    "appbar": ["appbar", "bottomappbar", "cupertinoappbar"],
    "bottom": ["bottomappbar", "bottomsheet", "cupertinobottomsheet"],
    "sheet": ["bottomsheet", "cupertinoactionsheet"],
    "switch": ["switch", "cupertinoswitch"],
    "checkbox": ["checkbox", "cupertinocheckbox"],
    "radio": ["radio", "radiogroup", "cupertinoradio"],
    "divider": ["divider", "verticaldivider"],
    "drag": ["draggable", "dragtarget", "reorderabledraghandle", "windowdragarea"],
    "gesture": ["gesturedetector", "interactiveviewer"],
    "scroll": ["listview", "scrollable"],
    "safe": ["safearea"],
    "hero": ["hero"],
    "placeholder": ["placeholder"],
    "code": ["codeeditor"],
    "color": ["colorpickers"],
    "canvas": ["canvas"],
    "ads": ["ads"],
    "screenshot": ["screenshot"],
    "search": ["searchbar"],
    "expansion": ["expansionpanel", "expansionpanellist", "expansiontile"],
    "dismissible": ["dismissible"],
    "keyboard": ["keyboardlistener"],
    "lottie": ["lottie"],
    "rive": ["rive"],
    "markdown": ["markdown"],
    "page": ["page", "pagelet", "pageview"],
    "view": ["view", "pageview", "multiview"],
    "router": ["router"],
    "semantics": ["semantics", "mergesemantics"],
    "shader": ["shadermask"],
    "selection": ["selectionarea"],
    "rotated": ["rotatedbox"],
    "responsive": ["responsiverow"],
}


def _clean_markdown(text: str) -> str:
    """Strip Docusaurus scaffolding that adds noise for LLM consumption:
    YAML frontmatter, JSX import/export lines, and <CodeExample> tags
    (replaced with a pointer to the example source)."""
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    text = re.sub(r"^import\s+\{[^}]*\}\s+from\s+['\"].*['\"]\s*;?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^export\s+default\s+.*;?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"<CodeExample\s+path=[\"']([^\"']+)[\"'][^>]*/>",
        r"*Runnable example: `\1` in the flet repo.*",
        text,
    )
    return text.strip()


class FletDocsFetcher:
    """Fetches and caches Flet documentation from the official GitHub repo."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._headers = SharedClient.get_headers()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = SharedClient.get()
        return self._client

    async def _fetch_json(self, url: str) -> dict | list | None:
        """Helper to fetch and cache JSON responses (24-hour TTL)."""
        if url in cache:
            return cache[url]

        try:
            response = await self.client.get(url, headers=self._headers)
        except httpx.RequestError as exc:
            raise FetchError(url, detail=str(exc)) from exc

        if response.status_code == 200:
            data = response.json()
            cache.set(url, data, expire=86400, tag="github")
            return data
        if response.status_code == 404:
            return None
        raise FetchError(url, status_code=response.status_code, detail=response.text[:200])

    async def _fetch_text(self, url: str) -> str | None:
        """Helper to fetch and cache raw Markdown text (24-hour TTL), authenticated."""
        if url in cache:
            return cache[url]

        try:
            response = await self.client.get(url, headers=SharedClient.auth_headers())
        except httpx.RequestError as exc:
            raise FetchError(url, detail=str(exc)) from exc

        if response.status_code == 200:
            text = response.text
            cache.set(url, text, expire=86400, tag="github")
            return text
        if response.status_code == 404:
            return None
        raise FetchError(url, status_code=response.status_code, detail=response.text[:200])

    async def _get_tree_paths(self, subtree: str) -> list[str]:
        """Full repo paths under `subtree`.

        Fetches the subtree directly (`<branch>:<path>`) which is small and immune
        to GitHub's 100k-entry truncation of repo-wide recursive trees; falls back
        to the whole recursive tree if the subtree ref is unavailable.
        """
        api = f"https://api.github.com/repos/{config.FLET_REPO}/git/trees"

        subtree_ref = quote(f"{config.FLET_BRANCH}:{subtree}", safe="")
        data = await self._fetch_json(f"{api}/{subtree_ref}?recursive=1")
        if isinstance(data, dict) and data.get("tree"):
            if data.get("truncated"):
                logger.warning("GitHub tree for %s was truncated; results may be partial", subtree)
            return [f"{subtree}/{item['path']}" for item in data["tree"]]

        logger.warning("Subtree fetch for %s failed; falling back to full tree", subtree)
        data = await self._fetch_json(f"{api}/{config.FLET_BRANCH}?recursive=1")
        if not isinstance(data, dict) or "tree" not in data:
            return []
        if data.get("truncated"):
            logger.warning("Full GitHub tree was truncated; results may be partial")
        return [item["path"] for item in data["tree"] if item["path"].startswith(f"{subtree}/")]

    async def get_docs_tree(self) -> list[str]:
        """Gets a flat list of all Markdown documentation paths in the Flet repo."""
        return [p for p in await self._get_tree_paths(DOCS_SUBTREE) if p.endswith(".md")]

    async def get_doc_content(self, file_path: str) -> str:
        """Fetches the raw Markdown for a doc file, cleaned for LLM consumption
        (Docusaurus frontmatter, JSX imports and CodeExample tags stripped)."""
        raw_url = (
            f"https://raw.githubusercontent.com/{config.FLET_REPO}/{config.FLET_BRANCH}/{file_path}"
        )
        content = await self._fetch_text(raw_url)

        if content:
            return _clean_markdown(content)
        raise DocNotFoundError(file_path)

    async def search_docs(self, query: str) -> list[str]:
        """Search over document paths with fuzzy matching and keyword aliases."""
        all_docs = await self.get_docs_tree()
        query_lower = query.lower().strip()

        if not query_lower:
            return []

        # Step 1: Direct substring match (highest priority)
        direct_matches = [path for path in all_docs if query_lower in path.lower()]

        # Step 2: Keyword alias expansion
        alias_matches = []
        for keyword, targets in KEYWORD_INDEX.items():
            if query_lower == keyword or query_lower in keyword:
                for target in targets:
                    alias_matches.extend(
                        path
                        for path in all_docs
                        if target in path.lower() and path not in direct_matches
                    )

        # Step 3: Fuzzy matching for typos / near-misses
        control_names = set()
        for path in all_docs:
            if f"{DOCS_SUBTREE}/controls/" in path:
                parts = path.split(f"{DOCS_SUBTREE}/controls/")
                if len(parts) > 1:
                    name = parts[1].split("/")[0].replace(".md", "")
                    control_names.add(name)

        fuzzy_matches = []
        if control_names:
            close_names = difflib.get_close_matches(query_lower, control_names, n=5, cutoff=0.6)
            for name in close_names:
                fuzzy_matches.extend(
                    path
                    for path in all_docs
                    if name in path.lower()
                    and path not in direct_matches
                    and path not in alias_matches
                )

        # Combine: direct > alias > fuzzy
        seen = set()
        result = []
        for path in direct_matches + alias_matches + fuzzy_matches:
            if path not in seen:
                seen.add(path)
                result.append(path)

        return result

    async def list_flet_controls(self) -> list[str]:
        """Returns a list of all available Flet UI controls (from docs pages)."""
        all_docs = await self.get_docs_tree()

        controls = set()
        controls_prefix = f"{DOCS_SUBTREE}/controls/"

        for path in all_docs:
            if not path.startswith(controls_prefix):
                continue
            remainder = path[len(controls_prefix) :]
            # Handle both "website/docs/controls/dropdown/index.md" and "website/docs/controls/textfield.md"
            name = remainder.split("/")[0].replace(".md", "")
            # Skip type definitions and nested sub-docs that aren't control names
            if name and not name.startswith("_"):
                controls.add(name)

        return sorted(controls)
