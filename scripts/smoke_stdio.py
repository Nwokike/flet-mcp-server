"""Fresh-install stdio smoke test.

Builds an ephemeral environment from the local source the same way end users
install the server (`uvx`), then runs a full MCP handshake and exercises one
tool from every group plus prompts and resources. This is the regression test
that would have caught the mcp 2.0 breakage: the server must start from a CLEAN
resolution of the current dependency floors, not a warm dev venv.

Usage: uv run python scripts/smoke_stdio.py
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REQUIRED_TOOLS = {
    "verify_flet_code",
    "get_flet_version",
    "inspect_flet_control",
    "search_flet_source",
    "read_flet_source",
    "list_flet_api",
    "search_flet_icons",
    "search_flet_colors",
    "search_flet_docs",
    "get_flet_doc",
    "list_flet_controls",
    "search_flet_examples",
    "get_flet_example",
    "list_official_packages",
    "search_flet_ecosystem",
    "get_package_details",
}

REQUIRED_PROMPTS = {"verify_flet_code_prompt", "migrate_flet_prompt", "build_flet_ui_prompt"}

BROKEN_CODE = """import flet as ft

def main(page):
    page.add(ft.ElevatedButton(text="hi"), ft.Slider(min=10, max=5))

ft.app(main)
"""

GOOD_CODE = """import flet as ft

def main(page):
    page.add(ft.Button(content=ft.Text("hi"), on_click=lambda e: None))

ft.app(main)
"""


async def main() -> int:
    params = StdioServerParameters(
        command="uvx",
        args=["--from", ".", "flet-mcp-server"],
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            missing = REQUIRED_TOOLS - names
            assert not missing, f"Server is missing tools: {sorted(missing)}"

            prompts = await session.list_prompts()
            prompt_names = {p.name for p in prompts.prompts}
            missing_prompts = REQUIRED_PROMPTS - prompt_names
            assert not missing_prompts, f"Server is missing prompts: {sorted(missing_prompts)}"

            resources = await session.list_resources()
            templates = await session.list_resource_templates()
            template_uris = {t.uri_template for t in templates.resource_templates}
            assert any(r.uri == "flet://version" for r in resources.resources), (
                "flet://version resource missing"
            )
            assert any("flet-source://" in u for u in template_uris), (
                "flet-source:// template missing"
            )

            version = await session.read_resource("flet://version")
            assert "flet_version" in version.contents[0].text

            src = await session.read_resource("flet-source://controls/material/button.py")
            assert "class Button" in src.contents[0].text

            result = await session.call_tool("get_flet_version", {})
            assert "flet_version" in result.content[0].text

            # Regression for v1.0.0: the protocol validates structured outputs
            # against the declared return type — calling (not just listing) this
            # tool caught a dict[str, list[str]] annotation rejecting the
            # "flet_version" string key.
            result = await session.call_tool("list_flet_api", {})
            assert "Material controls" in result.content[0].text

            result = await session.call_tool("inspect_flet_control", {"control_name": "Button"})
            assert "# Button" in result.content[0].text
            assert "Property" in result.content[0].text

            result = await session.call_tool("search_flet_icons", {"query": "home"})
            assert "Icons.HOME" in result.content[0].text

            result = await session.call_tool("search_flet_source", {"query": "class Button"})
            assert "button" in result.content[0].text.lower()

            # Flagship: broken code must be caught, clean code must pass.
            result = await session.call_tool("verify_flet_code", {"code": BROKEN_CODE})
            report = json.loads(result.content[0].text)
            assert report["status"] == "errors", report
            codes = {d["code"] for d in report["diagnostics"]}
            assert "deprecated" in codes and "bad-kwarg" in codes, codes

            result = await session.call_tool("verify_flet_code", {"code": GOOD_CODE})
            report = json.loads(result.content[0].text)
            assert report["status"] == "passed", report

    print(
        f"smoke: OK ({len(REQUIRED_TOOLS)} tools, {len(REQUIRED_PROMPTS)} prompts, "
        "2 resources, fresh uvx env, handshake + calls verified)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
