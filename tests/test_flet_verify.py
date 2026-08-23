"""Tests for verify_flet_code: static AST pass + sandboxed dynamic pass.

The dynamic tests spawn real subprocesses against the bundled flet — that is
the feature working exactly as in production.
"""

import pytest

from flet_mcp.services import flet_verify as fv


@pytest.fixture(autouse=True)
def _fresh_resolution(monkeypatch):
    monkeypatch.delenv("FLET_MCP_VENV", raising=False)
    from flet_mcp.services import flet_source as fs

    fs._reset_resolution()
    fs._py_files.cache_clear()
    yield
    fs._reset_resolution()
    fs._py_files.cache_clear()


def codes(diags):
    return {d.code for d in diags}


# --- Static pass ---


def test_static_syntax_error():
    diags = fv.run_static("def broken(:\n    pass")
    assert diags[0].code == "syntax"
    assert diags[0].line == 1


def test_static_unknown_name():
    diags = fv.run_static("import flet as ft\nx = ft.Buton()")
    (d,) = [d for d in diags if d.code == "unknown-name"]
    assert "Buton" in d.message
    assert d.line == 2
    assert d.hint and "Button" in d.hint


def test_static_bad_kwarg_with_hint():
    diags = fv.run_static("import flet as ft\nb = ft.Button(text='hi')")
    (d,) = [d for d in diags if d.code == "bad-kwarg"]
    assert "'text'" in d.message and d.line == 2


def test_static_enum_typo():
    diags = fv.run_static("import flet as ft\nr = ft.Row(alignment='middleish')")
    assert "enum-value" in codes(diags)


def test_static_valid_enum_ok():
    diags = fv.run_static("import flet as ft\nr = ft.Row(alignment='center')")
    assert "enum-value" not in codes(diags)


def test_static_deprecated_class():
    diags = fv.run_static("import flet as ft\nb = ft.ElevatedButton()")
    assert "deprecated" in codes(diags)


def test_static_undefined_handler():
    diags = fv.run_static("import flet as ft\nb = ft.Button(on_click=not_defined_anywhere)")
    assert "undefined-handler" in codes(diags)


def test_static_from_import_form():
    diags = fv.run_static("from flet import Buton\nx = Buton()")
    assert "unknown-name" in codes(diags)


def test_static_no_flet_import():
    diags = fv.run_static("x = 1")
    assert codes(diags) == {"no-import"}


# --- Dynamic pass ---


@pytest.mark.asyncio
async def test_dynamic_passes_clean_code():
    report = await fv.verify_code(
        "import flet as ft\n"
        "def main(page):\n"
        "    page.add(ft.Button(content=ft.Text('hi'), on_click=lambda e: None))\n"
        "ft.app(main)\n"
    )
    assert report.status == "passed"
    assert report.controls_verified >= 2
    assert report.diagnostics == []


@pytest.mark.asyncio
async def test_dynamic_catches_deferred_validator():
    report = await fv.verify_code(
        "import flet as ft\ndef main(page):\n    page.add(ft.Slider(min=10, max=5))\nft.app(main)\n"
    )
    assert report.status == "errors"
    runtime = [d for d in report.diagnostics if d.code == "runtime"]
    assert any("min" in d.message and "max" in d.message for d in runtime)


@pytest.mark.asyncio
async def test_dynamic_catches_wrong_kwarg_with_line():
    report = await fv.verify_code(
        "import flet as ft\ndef main(page):\n    page.add(ft.Button(text='hi'))\nft.app(main)\n"
    )
    runtime = [d for d in report.diagnostics if d.code == "runtime"]
    assert any(d.line == 3 and "text" in d.message for d in runtime)
    assert "bad-kwarg" in codes(report.diagnostics)  # static also catches it


@pytest.mark.asyncio
async def test_dynamic_captures_deprecation_warning():
    report = await fv.verify_code(
        "import flet as ft\ndef main(page):\n    page.add(ft.ElevatedButton())\nft.app(main)\n"
    )
    assert "deprecated" in codes(report.diagnostics)


@pytest.mark.asyncio
async def test_deprecation_reported_once():
    """v1.0.2 regression: one deprecated usage produced THREE 'deprecated'
    diagnostics (static + flet warning on both __init__ and __post_init__)."""
    report = await fv.verify_code(
        "import flet as ft\ndef main(page):\n    page.add(ft.ElevatedButton())\nft.app(main)\n"
    )
    deprecated = [d for d in report.diagnostics if d.code == "deprecated"]
    assert len(deprecated) == 1, deprecated


@pytest.mark.asyncio
async def test_dynamic_neutralizes_ft_app():
    # If ft.app were NOT neutralized this would hang until timeout.
    report = await fv.verify_code(
        "import flet as ft\ndef main(page):\n    page.add(ft.Text('hi'))\nft.app(main)\n"
    )
    assert report.status == "passed"


@pytest.mark.asyncio
async def test_dynamic_timeout():
    report = await fv.verify_code("import flet as ft\nwhile True:\n    pass\n", timeout_secs=3)
    assert report.status == "timeout"
    assert "timeout" in codes(report.diagnostics)


@pytest.mark.asyncio
async def test_dynamic_name_error_line():
    report = await fv.verify_code("import flet as ft\nx = does_not_exist\n")
    runtime = [d for d in report.diagnostics if d.code == "runtime"]
    assert any(d.line == 2 and "does_not_exist" in d.message for d in runtime)


@pytest.mark.asyncio
async def test_verify_report_schema():
    report = await fv.verify_code("import flet as ft\nft.Text('ok')\n")
    assert report.flet_version[0].isdigit()
    assert set(report.checks) == {"static", "dynamic"}
    assert report.duration_ms >= 0
    assert report.status in {"passed", "errors", "timeout"}
