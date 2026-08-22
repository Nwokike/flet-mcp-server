<p align="center">
  <a href="https://github.com/Nwokike/flet-mcp-server" target="_blank">
    <img src="https://raw.githubusercontent.com/flet-dev/flet/refs/heads/main/media/logo/flet-logo.svg" height="150" alt="Flet MCP Server logo">
  </a>
</p>

<h1 align="center">Flet MCP Server</h1>

<p align="center">
  <em>MCP server that makes the installed Flet source code the source of truth for AI agents.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/flet-mcp-server/" target="_blank">
    <img src="https://img.shields.io/pypi/v/flet-mcp-server?color=%2334D058&label=PyPI" alt="PyPI version" />
  </a>
  <a href="https://pepy.tech/projects/flet-mcp-server" target="_blank">
    <img src="https://static.pepy.tech/personalized-badge/flet-mcp-server?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=Users" alt="Total users" />
  </a>
  <a href="https://github.com/Nwokike/flet-mcp-server/actions/workflows/ci.yml" target="_blank">
    <img src="https://github.com/Nwokike/flet-mcp-server/actions/workflows/ci.yml/badge.svg" alt="CI status" />
  </a>
  <a href="https://pypi.org/project/flet-mcp-server/" target="_blank">
    <img src="https://img.shields.io/badge/python-%3E%3D3.10-%2334D058" alt="Python >= 3.10" />
  </a>
  <a href="https://glama.ai/mcp/servers/Nwokike/flet-mcp-server" target="_blank">
    <img src="https://glama.ai/mcp/servers/Nwokike/flet-mcp-server/badges/score.svg" alt="MCP server score" />
  </a>
</p>

---

Flet changes faster than model training data. Controls get renamed, deprecated
and removed (`ft.ElevatedButton` → `ft.Button`, and `Button(text=...)` is now
`Button(content=...)`), properties change types, icon names get hallucinated.
The only reliable reference is the flet source code **actually installed in
your environment** — this server ships with flet as a dependency, gives your AI
tools to read it directly, and — uniquely — can **run and verify AI-written
Flet code against that installed flet** before you ever see it.

> **Upgrading from v0.2.x?** The plain command below works again — no
> `--with mcp<2 --with typing_extensions` flags needed anymore. v0.2.x broke
> because the mcp SDK 2.0 removed `mcp.server.fastmcp`; v1.0.0 is built on the
> new `MCPServer` API and pins `mcp>=2`.

```bash
uvx flet-mcp-server
```

## Verify your Flet code (the killer feature)

`verify_flet_code(code)` checks AI-generated Flet code against the installed
flet in two passes and reports **every problem with line numbers and hints**:

* **Static**: unknown controls, properties that don't exist anymore, enum
  typos, deprecated classes, undefined event handlers.
* **Dynamic**: the code runs in a sandboxed subprocess (app launchers are
  neutralized — nothing opens, nothing starts) while flet's own validators
  fire on every constructed control, catching errors that normally only appear
  at runtime — like `Slider(min=10, max=5)`.

```json
{
  "status": "errors",
  "flet_version": "0.86.5",
  "controls_verified": 6,
  "diagnostics": [
    {"severity": "warning", "code": "deprecated", "line": 4,
     "message": "'ElevatedButton' is deprecated in flet 0.86.5.",
     "hint": "Did you mean 'FilledButton'?"},
    {"severity": "error", "code": "bad-kwarg", "line": 4,
     "message": "'ElevatedButton' has no property 'text' in flet 0.86.5."},
    {"severity": "error", "code": "runtime", "line": null,
     "message": "ValueError: Slider: min (10) must be less than or equal to max (5)"}
  ]
}
```

The server's instructions tell AI clients to **verify before delivering** and
fix-and-reverify until the report is `passed` — plus three ready-made prompts
(`verify_flet_code_prompt`, `migrate_flet_prompt`, `build_flet_ui_prompt`)
that encode the full workflow.

## What your AI gets

**Verify (new in v1.0.0)** — confidence that AI-written code is actually valid:

* `verify_flet_code(code)` — static + sandboxed dynamic verification against
  the installed flet, structured diagnostics with line numbers and hints.
* Prompts: `verify_flet_code_prompt`, `migrate_flet_prompt`, `build_flet_ui_prompt`.
* Resources: `flet://version` and `flet-source://<module>` (browsable installed
  source, path-traversal safe).

**Source of truth** — reads the flet package installed alongside the server,
so every answer matches the exact version your app runs:

* `inspect_flet_control(control_name)` — every property with type, default and
  origin class (inherited fields marked), `on_*` events, deprecation warnings,
  the class hierarchy, and the full class source with per-property docstrings.
* `get_flet_version()` — which flet version the tools are reading, and from where.
* `search_flet_source(query)` — grep the installed flet sources; definitions
  rank first.
* `read_flet_source(module, symbol?)` — numbered source of any module, or a
  single class/function extracted by AST.
* `list_flet_api()` — the true `flet.__all__` of the installed version, grouped
  by category (Material / Cupertino / Core controls, Services, Components & hooks).
* `search_flet_icons(query, icon_set)` — valid `ft.Icons.*` /
  `ft.CupertinoIcons.*` names, so the AI never invents one again.
* `search_flet_colors(query)` — valid `ft.Colors.*` constants, including shades
  like `AMBER_500`.

**Docs** — official guides from the Flet repo (fetched live, cached 24h):

* `search_flet_docs(query)` — smart search (direct > keyword aliases > fuzzy).
* `get_flet_doc(doc_path)` — full Markdown of a doc page.
* `list_flet_controls()` — every control that has a docs page.

**Ecosystem** — packages beyond core flet:

* `list_official_packages()` — official extensions from the monorepo (flet-audio, flet-video, …).
* `search_flet_ecosystem(query)` — verified community packages on GitHub/PyPI.
* `get_package_details(package_name)` — PyPI version, classification, install command.

## Matching your project's Flet version

By default the source tools read the latest flet bundled with the server. Two
ways to verify against the exact version **your project** uses:

**1. Pin the version at launch** (matches `uvx`-style workflows):

```bash
uvx --with flet==0.86.1 flet-mcp-server
```

**2. Local Mode** — point the tools at your project's virtualenv, so they read
its flet (and only its flet) no matter what the server bundles:

```json
{
  "mcpServers": {
    "flet-mcp-server": {
      "command": "uvx",
      "args": ["flet-mcp-server"],
      "env": { "FLET_MCP_VENV": "/absolute/path/to/your/project/.venv" }
    }
  }
}
```

Every tool response then reports e.g. `[flet 0.86.5 — FLET_MCP_VENV=…/project/.venv]`,
and `inspect_flet_control` shows deprecations relative to that version.

## Client Configuration Examples

### VSCode
Add this to your `.vscode/mcp.json`:

```json
{
  "servers": {
    "flet-mcp-server": {
      "command": "uvx",
      "args": ["flet-mcp-server"]
    }
  }
}
```

### Antigravity

Add this to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "flet-mcp-server": {
      "command": "uvx",
      "args": ["flet-mcp-server"]
    }
  }
}
```

### Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "flet-mcp-server": {
      "command": "uvx",
      "args": ["flet-mcp-server"]
    }
  }
}
```

### Cursor / Windsurf

In your IDE's MCP settings, add a new server:

* **Name**: Flet MCP
* **Type**: Command
* **Command**: `uvx flet-mcp-server`

### Zed

Add this to your `settings.json` file inside the `context_servers` object:

```jsonc
{
  "flet": {
    "command": "uvx",
    "args": ["flet-mcp-server"],
    "env": {}
  }
}
```

### OpenCode

Add this to your `~/.config/opencode/opencode.json` or project-level `.opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "flet-mcp": {
      "type": "local",
      "command": ["uvx", "flet-mcp-server"],
      "enabled": true
    }
  }
}
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `FLET_MCP_VENV` | *(unset)* | Read flet from this project venv instead of the bundled one (Local Mode). |
| `FLET_MCP_TRANSPORT` | `stdio` | `stdio`, `sse`, or `streamable-http` (uses the bundled uvicorn). |
| `FLET_MCP_HOST` | `127.0.0.1` | Bind host for HTTP transports. |
| `FLET_MCP_PORT` | `8000` | Bind port for HTTP transports. |
| `GITHUB_TOKEN` | *(unset)* | Authenticated GitHub API access — higher rate limits. |
| `FLET_REPO` | `flet-dev/flet` | Docs source repo. |
| `FLET_BRANCH` | `main` | Docs source branch. |
| `FLET_MCP_CACHE_DIR` | `~/.cache/flet-mcp` | HTTP cache location (XDG-aware). |

Docker / remote deployments: run with `FLET_MCP_TRANSPORT=streamable-http
FLET_MCP_HOST=0.0.0.0` — a `GET /health` liveness endpoint is included.
OpenTelemetry traces are emitted automatically by the MCP SDK; configure any
standard `OTEL_*` environment variables to export them.

## Development

```bash
git clone https://github.com/Nwokike/flet-mcp-server.git
cd flet-mcp-server
uv sync

uv run pytest                              # unit tests (69)
uv run ruff check src/ tests/ scripts/     # lint
uv run python scripts/smoke_stdio.py       # full MCP handshake from a fresh uvx env
```

The smoke script is the regression test for the v0.2.0 outage: it installs the
server into a clean ephemeral environment (exactly what end users get) and
verifies the handshake plus one call per tool group.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture and
[CHANGELOG.md](CHANGELOG.md) for release history.

## License
MIT
