import pytest
from flet_mcp.services.github_docs import FletDocsFetcher
from flet_mcp.services.packages import FletPackageFetcher

@pytest.fixture
async def docs_fetcher():
    f = FletDocsFetcher()
    yield f
    await f.client.aclose()

@pytest.fixture
async def pkg_fetcher():
    f = FletPackageFetcher()
    yield f
    await f.client.aclose()

# --- Documentation Tests ---

@pytest.mark.asyncio
async def test_get_docs_tree(docs_fetcher):
    tree = await docs_fetcher.get_docs_tree()
    assert len(tree) > 0
    assert all(path.startswith("website/docs/") for path in tree)

@pytest.mark.asyncio
async def test_search_docs(docs_fetcher):
    matches = await docs_fetcher.search_docs("dropdown")
    assert len(matches) > 0

@pytest.mark.asyncio
async def test_list_flet_controls(docs_fetcher):
    controls = await docs_fetcher.list_flet_controls()
    assert len(controls) > 100
    assert "dropdown" in controls

@pytest.mark.asyncio
async def test_get_doc_content(docs_fetcher):
    content = await docs_fetcher.get_doc_content("website/docs/controls/dropdown/index.md")
    assert "flet.Dropdown" in content

@pytest.mark.asyncio
async def test_get_doc_content_not_found(docs_fetcher):
    content = await docs_fetcher.get_doc_content("website/docs/non_existent_file.md")
    assert "Error: Could not fetch documentation" in content

# --- Package & Ecosystem Tests ---

@pytest.mark.asyncio
async def test_list_official_packages(pkg_fetcher):
    packages = await pkg_fetcher.list_official_packages()
    assert len(packages) > 0
    assert any("audio" in pkg for pkg in packages) or "flet-audio" in packages

@pytest.mark.asyncio
async def test_is_true_flet_package(pkg_fetcher):
    # flet-audio is a known flet package
    assert await pkg_fetcher._is_true_flet_package("flet-audio") is True
    # requests is NOT a flet package
    assert await pkg_fetcher._is_true_flet_package("requests") is False

@pytest.mark.asyncio
async def test_search_flet_ecosystem(pkg_fetcher):
    results = await pkg_fetcher.search_flet_ecosystem("calendar")
    assert isinstance(results, list)
    if results:
        assert "is_verified_flet_package" in results[0]

@pytest.mark.asyncio
async def test_get_package_details(pkg_fetcher):
    details = await pkg_fetcher.get_package_details("flet-audio")
    assert "Package: flet-audio" in details
    assert "Type: UI Control" in details or "Type: Python Package" in details
    assert "uv add flet-audio" in details

@pytest.mark.asyncio
async def test_get_package_details_not_found(pkg_fetcher):
    details = await pkg_fetcher.get_package_details("this-package-does-not-exist-xyz")
    assert "not found on PyPI" in details
