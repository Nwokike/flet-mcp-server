import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx
import diskcache
import tempfile
import os

from flet_mcp import config
from flet_mcp.services import github_docs, packages
from flet_mcp.services.github_docs import FletDocsFetcher
from flet_mcp.services.packages import FletPackageFetcher
from flet_mcp.exceptions import DocNotFoundError, PackageNotFoundError, FetchError, TreeFetchError


@pytest.fixture(autouse=True)
def isolated_cache():
    """Redirect cache to a temp directory and clear it between tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cache_dir = os.environ.get("FLET_MCP_CACHE_DIR")
        os.environ["FLET_MCP_CACHE_DIR"] = tmpdir
        github_docs.cache = diskcache.Cache(tmpdir)
        packages.cache = diskcache.Cache(tmpdir)
        yield
        if old_cache_dir is None:
            os.environ.pop("FLET_MCP_CACHE_DIR", None)
        else:
            os.environ["FLET_MCP_CACHE_DIR"] = old_cache_dir
        github_docs.cache = diskcache.Cache(config.cache_dir())
        packages.cache = diskcache.Cache(config.cache_dir())


# --- Fixtures ---


@pytest.fixture
def mock_response():
    def _response(status_code=200, json_data=None, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.text = text
        return resp

    return _response


@pytest.fixture
async def docs_fetcher():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    f = FletDocsFetcher(client=mock_client)
    yield f
    await mock_client.aclose()


@pytest.fixture
async def pkg_fetcher():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    f = FletPackageFetcher(client=mock_client)
    yield f
    await mock_client.aclose()


# --- GitHub Tree Response Fixtures ---
# The docs fetcher now requests the website/docs subtree directly
# (`<branch>:website/docs`), so GitHub returns paths RELATIVE to that subtree.

MOCK_TREE_DATA = {
    "tree": [
        {"path": "controls/dropdown/index.md", "type": "blob"},
        {"path": "controls/dropdownm2.md", "type": "blob"},
        {"path": "controls/dropdownoption.md", "type": "blob"},
        {"path": "controls/textfield.md", "type": "blob"},
        {"path": "controls/filledbutton.md", "type": "blob"},
        {"path": "controls/container.md", "type": "blob"},
        {"path": "controls/row.md", "type": "blob"},
        {"path": "controls/column.md", "type": "blob"},
        {"path": "controls/stack.md", "type": "blob"},
        {"path": "controls/navigationbar/index.md", "type": "blob"},
        {"path": "controls/alertdialog.md", "type": "blob"},
        {"path": "controls/icon.md", "type": "blob"},
        {"path": "controls/card.md", "type": "blob"},
        {"path": "controls/listtile.md", "type": "blob"},
        {"path": "cookbook/animations.md", "type": "blob"},
        {"path": "types/animationcurve.md", "type": "blob"},
        {"path": "types/buttonstyle.md", "type": "blob"},
    ]
}

# Direct children of sdk/python/packages in the monorepo (non-recursive subtree).

MOCK_PACKAGES_TREE = {
    "tree": [
        {"path": "flet-audio", "type": "tree"},
        {"path": "flet-video", "type": "tree"},
        {"path": "flet-charts", "type": "tree"},
        {"path": "ci", "type": "tree"},
    ]
}

MOCK_DROPDOWN_DOC = """---
class_name: "flet.Dropdown"
title: "Dropdown"
---

# Dropdown

A dropdown control for selecting one value from a list.
"""


# --- Documentation Tests ---


@pytest.mark.asyncio
async def test_get_docs_tree(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    tree = await docs_fetcher.get_docs_tree()

    assert len(tree) > 0
    assert all(path.startswith("website/docs/") for path in tree)
    assert "website/docs/controls/dropdown/index.md" in tree


@pytest.mark.asyncio
async def test_get_docs_tree_api_failure(docs_fetcher):
    docs_fetcher.client.get = AsyncMock(
        return_value=MagicMock(status_code=500, text="Server Error")
    )

    with pytest.raises(FetchError):
        await docs_fetcher.get_docs_tree()


@pytest.mark.asyncio
async def test_search_docs_direct_match(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    matches = await docs_fetcher.search_docs("dropdown")

    assert len(matches) >= 3
    assert any("dropdown/index.md" in m for m in matches)
    assert any("dropdownm2.md" in m for m in matches)


@pytest.mark.asyncio
async def test_search_docs_keyword_alias(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    matches = await docs_fetcher.search_docs("input")

    assert any("textfield" in m for m in matches)


@pytest.mark.asyncio
async def test_search_docs_fuzzy_match(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    matches = await docs_fetcher.search_docs("dropdwn")

    assert any("dropdown" in m for m in matches)


@pytest.mark.asyncio
async def test_search_docs_empty_query(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    matches = await docs_fetcher.search_docs("")

    assert matches == []


@pytest.mark.asyncio
async def test_search_docs_no_results(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    matches = await docs_fetcher.search_docs("nonexistentcontrol123")

    assert matches == []


@pytest.mark.asyncio
async def test_list_flet_controls(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_TREE_DATA))

    controls = await docs_fetcher.list_flet_controls()

    assert len(controls) > 10
    assert "dropdown" in controls
    assert "textfield" in controls
    assert "filledbutton" in controls
    assert controls == sorted(controls)


@pytest.mark.asyncio
async def test_get_doc_content(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(text=MOCK_DROPDOWN_DOC))

    content = await docs_fetcher.get_doc_content("website/docs/controls/dropdown/index.md")

    assert "# Dropdown" in content
    assert "selecting one value" in content
    assert "class_name" not in content  # frontmatter is stripped


MDX_DOC = """---
class_name: "flet.Dropdown"
title: "Dropdown"
---

import {CodeExample} from '@site/src/components/crocodocs';

# Dropdown

<CodeExample path="controls/material/dropdown/basic/main.py" language="python" />

<RealContent>stay</RealContent>
"""


@pytest.mark.asyncio
async def test_get_doc_content_strips_mdx_scaffolding(docs_fetcher, mock_response):
    """v1.0.2: raw MDX frontmatter/imports/CodeExample tags are noise for
    LLMs — get_doc_content cleans them."""
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(text=MDX_DOC))

    content = await docs_fetcher.get_doc_content("website/docs/controls/dropdown/index.md")

    assert "class_name" not in content  # frontmatter stripped
    assert "@site/src/components" not in content  # JSX import stripped
    assert "<CodeExample" not in content
    assert "controls/material/dropdown/basic/main.py" in content  # path preserved as note
    assert "# Dropdown" in content
    assert "<RealContent>" in content  # unknown JSX tags left alone


@pytest.mark.asyncio
async def test_get_doc_content_not_found(docs_fetcher, mock_response):
    docs_fetcher.client.get = AsyncMock(return_value=mock_response(status_code=404))

    with pytest.raises(DocNotFoundError) as exc_info:
        await docs_fetcher.get_doc_content("website/docs/non_existent_file.md")

    assert "non_existent_file.md" in str(exc_info.value)


# --- Package & Ecosystem Tests ---

MOCK_PYPI_FLET_AUDIO = {
    "info": {
        "version": "0.85.1",
        "summary": "Provides audio integration and playback in Flet apps.",
        "requires_dist": ["flet (>=0.1.0)"],
    }
}

MOCK_PYPI_REQUESTS = {
    "info": {
        "version": "2.31.0",
        "summary": "Python HTTP for Humans.",
        "requires_dist": [],
    }
}


@pytest.mark.asyncio
async def test_list_official_packages(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_PACKAGES_TREE))

    packages = await pkg_fetcher.list_official_packages()

    assert len(packages) > 0
    assert "flet-audio" in packages
    assert "flet-video" in packages
    assert "flet-charts" in packages


@pytest.mark.asyncio
async def test_list_official_packages_fallback(pkg_fetcher):
    pkg_fetcher.client.get = AsyncMock(return_value=MagicMock(status_code=500, text="Error"))

    packages = await pkg_fetcher.list_official_packages()

    assert len(packages) > 0
    assert "flet-audio" in packages


@pytest.mark.asyncio
async def test_is_true_flet_package(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_PYPI_FLET_AUDIO))

    assert await pkg_fetcher._is_true_flet_package("flet-audio") is True


@pytest.mark.asyncio
async def test_is_not_true_flet_package(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_PYPI_REQUESTS))

    assert await pkg_fetcher._is_true_flet_package("requests") is False


@pytest.mark.asyncio
async def test_is_true_flet_package_not_found(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(status_code=404))

    assert await pkg_fetcher._is_true_flet_package("nonexistent-pkg-xyz") is False


@pytest.mark.asyncio
async def test_search_flet_ecosystem(pkg_fetcher, mock_response):
    github_search_data = {
        "items": [
            {
                "name": "flet-calendar",
                "full_name": "someone/flet-calendar",
                "description": "A calendar widget for Flet",
                "stargazers_count": 10,
                "html_url": "https://github.com/someone/flet-calendar",
            }
        ]
    }
    pkg_fetcher.client.get = AsyncMock(
        side_effect=[
            mock_response(json_data=github_search_data),
            mock_response(json_data=MOCK_PYPI_REQUESTS),
        ]
    )

    results = await pkg_fetcher.search_flet_ecosystem("calendar")

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["name"] == "flet-calendar"
    assert "is_verified_flet_package" in results[0]


@pytest.mark.asyncio
async def test_search_flet_ecosystem_no_results(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(json_data={"items": []}))

    results = await pkg_fetcher.search_flet_ecosystem("nonexistent-xyz-123")

    assert results == []


@pytest.mark.asyncio
async def test_get_package_details(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(json_data=MOCK_PYPI_FLET_AUDIO))

    details = await pkg_fetcher.get_package_details("flet-audio")

    assert "Package: flet-audio" in details
    assert "v0.85.1" in details
    assert "Type: UI Control" in details or "Type: Python Package" in details
    assert "uv add flet-audio" in details


@pytest.mark.asyncio
async def test_get_package_details_not_found(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(return_value=mock_response(status_code=404))

    with pytest.raises(PackageNotFoundError) as exc_info:
        await pkg_fetcher.get_package_details("this-package-does-not-exist-xyz")

    assert "this-package-does-not-exist-xyz" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_package_details_service_classification(pkg_fetcher, mock_response):
    pkg_fetcher.client.get = AsyncMock(
        return_value=mock_response(
            json_data={
                "info": {
                    "version": "1.0.0",
                    "summary": "Authentication service for Flet apps.",
                    "requires_dist": ["flet"],
                }
            }
        )
    )

    details = await pkg_fetcher.get_package_details("flet-auth")

    assert "Type: Service Integration" in details


# --- Exception Tests ---


def test_doc_not_found_error():
    err = DocNotFoundError("some/path.md")
    assert "some/path.md" in str(err)
    assert err.file_path == "some/path.md"


def test_package_not_found_error():
    err = PackageNotFoundError("missing-pkg")
    assert "missing-pkg" in str(err)
    assert err.package_name == "missing-pkg"


def test_fetch_error_with_status():
    err = FetchError("https://example.com", status_code=404, detail="Not found")
    assert "https://example.com" in str(err)
    assert "404" in str(err)
    assert err.url == "https://example.com"
    assert err.status_code == 404


def test_fetch_error_without_status():
    err = FetchError("https://example.com", detail="Connection refused")
    assert "https://example.com" in str(err)
    assert "Connection refused" in str(err)


def test_tree_fetch_error():
    err = TreeFetchError("flet-dev/flet", detail="Rate limited")
    assert "flet-dev/flet" in str(err)
    assert "Rate limited" in str(err)
