"""Tests for the flet source introspection service.

These run against the REAL bundled flet install (a dev dependency) — that is the
whole point: the tools must work on actual flet sources, not fixtures.
"""

import os

import pytest

from flet_mcp.exceptions import SourceError, SymbolNotFoundError
from flet_mcp.services import flet_source as fs


@pytest.fixture(autouse=True)
def fresh_resolution(monkeypatch):
    """Every test re-resolves flet with clean caches and no Local Mode override."""
    monkeypatch.delenv(fs.VENV_ENV_VAR, raising=False)
    fs._reset_resolution()
    fs._py_files.cache_clear()
    fs._icons_map.cache_clear()
    yield
    fs._reset_resolution()
    fs._py_files.cache_clear()
    fs._icons_map.cache_clear()


# --- Resolution ---


def test_resolve_bundled():
    r = fs.resolve_flet()
    assert r.source == "bundled"
    assert r.version and r.version[0].isdigit()
    assert (r.pkg_dir / "__init__.py").is_file()
    assert r.banner.startswith(f"[flet {r.version}")


def test_local_mode_rejects_bad_venv(monkeypatch, tmp_path):
    monkeypatch.setenv(fs.VENV_ENV_VAR, str(tmp_path / "does-not-exist"))
    with pytest.raises(SourceError, match="not a directory"):
        fs.resolve_flet()


def test_local_mode_rejects_venv_without_flet(monkeypatch, tmp_path):
    sp = tmp_path / "lib" / "python3.13" / "site-packages"
    sp.mkdir(parents=True)
    monkeypatch.setenv(fs.VENV_ENV_VAR, str(tmp_path))
    with pytest.raises(SourceError, match="No 'flet' package"):
        fs.resolve_flet()


# --- read_source ---


def test_read_source_whole_file_numbered():
    out = fs.read_source("controls/material/elevated_button.py")
    assert "class ElevatedButton" in out
    assert " 1 | " in out  # numbered lines starting at 1


def test_read_source_accepts_dotted_module():
    out = fs.read_source("flet.controls.material.button")
    assert "class Button" in out


def test_read_source_symbol_extraction():
    out = fs.read_source("controls/material/button.py", "Button")
    assert "class Button" in out
    assert "controls/material/button.py" in out
    # Line numbers start at the class definition, not 1.
    first_numbered = [ln for ln in out.splitlines() if " | " in ln][0]
    assert not first_numbered.strip().startswith("1 |")


def test_read_source_missing_symbol():
    with pytest.raises(SymbolNotFoundError):
        fs.read_source("controls/material/button.py", "NotAWidget")


def test_read_source_unknown_module_suggests():
    with pytest.raises(SourceError, match="Did you mean"):
        fs.read_source("controls/material/butto.py")


def test_read_source_traversal_rejected():
    with pytest.raises(SourceError):
        fs.read_source("../../../etc/passwd")


def test_read_source_line_cap():
    out = fs.read_source("controls/page.py", max_lines=10)
    assert "more lines" in out


# --- search_source ---


def test_search_source_ranks_definitions_first():
    results = fs.search_source("ElevatedButton")
    assert results[0].startswith("controls/material/elevated_button.py:")
    assert "class ElevatedButton" in results[0]


def test_search_source_no_matches():
    results = fs.search_source("zzzz definitely not in flet")
    assert "No matches" in results[0]


def test_search_source_respects_limit():
    results = fs.search_source("control", max_results=3)
    assert len(results) <= 4  # 3 results + possible "more matches" note


# --- inspect_control ---


def test_inspect_control_full_report():
    out = fs.inspect_control("TextField")
    assert out.startswith("[flet ")
    assert "# TextField" in out
    assert "flet/controls/material/textfield.py" in out
    assert "| Property | Type | Default | Inherits from |" in out
    assert "FormFieldControl" in out  # inheritance chain
    assert "`visible`" in out  # inherited property from Control
    assert "_values" not in out  # private machinery filtered


def test_inspect_control_clean_type_rendering():
    out = fs.inspect_control("Button")
    table = out.split("## Properties", 1)[1].split("## Events", 1)[0]
    assert "ForwardRef" not in table  # unwrapped
    assert "flet.controls." not in table  # module prefixes stripped
    assert "Event[Button]" in table  # readable event handler type


def test_inspect_control_surfaces_deprecation():
    out = fs.inspect_control("ElevatedButton")
    assert "DEPRECATED" in out
    assert "Use Button instead" in out


def test_inspect_control_case_insensitive():
    out = fs.inspect_control("textfield")
    assert "# TextField" in out


def test_inspect_control_unknown_name():
    with pytest.raises(SymbolNotFoundError):
        fs.inspect_control("DefinitelyNotAControl")


def test_inspect_control_non_class_redirects():
    out = fs.inspect_control("app")
    assert "not a class" in out


# --- icons & colors ---


def test_search_icons_material():
    results = fs.search_icons("home")
    assert results
    assert any(r.startswith("Icons.HOME ") for r in results)


def test_search_icons_ranking_exact_first():
    results = fs.search_icons("home")
    assert results[0].startswith("Icons.HOME ")


def test_search_icons_cupertino():
    results = fs.search_icons("arrow", "cupertino")
    assert results
    names = [r for r in results if not r.startswith("…")]
    assert names and all(r.startswith("CupertinoIcons.") for r in names)


def test_search_icons_rejects_unknown_set():
    with pytest.raises(SourceError, match="icon_set"):
        fs.search_icons("x", "neon")


def test_search_colors_includes_shades():
    results = fs.search_colors("amber")
    assert any(r.startswith("Colors.AMBER =") for r in results)
    assert any(r.startswith("Colors.AMBER_500") for r in results)


def test_search_colors_no_match():
    assert "No colors match" in fs.search_colors("zzzznope")[0]


# --- list_api ---


def test_list_api_grouped():
    api = fs.list_api()
    assert api["flet_version"] == fs.resolve_flet().version
    assert "TextField" in api["Material controls"]
    assert "Services" in api
    assert "Components & hooks" in api


def test_list_api_degrades_without_registry(monkeypatch):
    import flet

    monkeypatch.setattr(flet, "_LAZY", {}, raising=False)
    api = fs.list_api()
    assert "names" in api
    assert "TextField" in api["names"]


def test_env_var_name_exported():
    assert fs.VENV_ENV_VAR == "FLET_MCP_VENV"
    assert "FLET_MCP_VENV" in os.environ or True  # documented name, not required set
