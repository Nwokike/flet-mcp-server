"""Tests for the official examples service (mocked HTTP)."""

import tempfile

import diskcache
import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx

from flet_mcp.services import examples
from flet_mcp.services.examples import FletExamplesFetcher
from flet_mcp.exceptions import FetchError, SourceError


@pytest.fixture(autouse=True)
def isolated_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        old = examples.cache
        examples.cache = diskcache.Cache(tmpdir)
        yield
        examples.cache = old


TREE = {
    "tree": [
        {"path": "counter/pyproject.toml", "type": "blob"},
        {"path": "counter/main.py", "type": "blob"},
        {"path": "counter/flet_app.py", "type": "blob"},
        {"path": "7guis/flight_booker/pyproject.toml", "type": "blob"},
        {"path": "7guis/flight_booker/main.py", "type": "blob"},
        {"path": "todo/README.md", "type": "blob"},
    ]
}


@pytest.fixture
async def fetcher():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    f = FletExamplesFetcher(client=mock_client)
    yield f
    await mock_client.aclose()


def _response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_search_matches_tokens(fetcher):
    fetcher.client.get = AsyncMock(return_value=_response(json_data=TREE))
    results = await fetcher.search_examples("counter app")
    assert results and results[0].startswith("counter (")
    assert "get_flet_example('counter')" in results[0]


@pytest.mark.asyncio
async def test_search_no_match_gives_hint(fetcher):
    fetcher.client.get = AsyncMock(return_value=_response(json_data=TREE))
    results = await fetcher.search_examples("zzzznothing")
    assert "No example matches" in results[0]


@pytest.mark.asyncio
async def test_get_example_bundles_files(fetcher):
    fetcher.client.get = AsyncMock(
        side_effect=[
            _response(json_data=TREE),  # tree
            _response(text="[project]\nname='counter'"),  # pyproject
            _response(text="def main(page):\n    pass\n"),  # main.py
            _response(text="# app\n"),  # flet_app.py
        ]
    )
    out = await fetcher.get_example("counter")
    assert "# Example: counter" in out
    assert "pyproject.toml" in out and "main.py" in out and "flet_app.py" in out
    assert "[project]" in out and "def main" in out


@pytest.mark.asyncio
async def test_get_example_rejects_unknown_and_traversal(fetcher):
    fetcher.client.get = AsyncMock(return_value=_response(json_data=TREE))
    with pytest.raises(SourceError, match="not found"):
        await fetcher.get_example("does/not/exist")
    with pytest.raises(SourceError, match="Invalid example id"):
        await fetcher.get_example("../../etc/passwd")


@pytest.mark.asyncio
async def test_tree_fetch_failure_raises(fetcher):
    fetcher.client.get = AsyncMock(return_value=_response(status_code=500, text="boom"))
    with pytest.raises(FetchError):
        await fetcher.search_examples("counter")
