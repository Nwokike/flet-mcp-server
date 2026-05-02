<p align="center">
  <a href="https://github.com/Nwokike/flet-mcp-server" target="_blank">
    <img src="https://raw.githubusercontent.com/flet-dev/flet/refs/heads/main/media/logo/flet-logo.svg" height="150" alt="Flet MCP Server logo">
  </a>
</p>

<h1 align="center">Flet MCP Server</h1>

<p align="center">
  <em>Model Context Protocol that serves official Flet resources to AI agents.</em>
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

Flet MCP Server dynamically fetches and serves official Flet documentation, controls, packages, and ecosystem resources for AI agents and MCP-compatible clients.
<div align="center">

[![Nwokike/flet-mcp-server MCP server](https://glama.ai/mcp/servers/Nwokike/flet-mcp-server/badges/card.svg)](https://glama.ai/mcp/servers/Nwokike/flet-mcp-server)

</div>

## Features

*   **GitHub Tree Sync**: Maps documentation in real-time.
*   **Intelligent Caching**: Uses `diskcache` for fast responses.
*   **Ecosystem Discovery**: Finds and verifies official and community Flet packages.
*   **AI-Optimized**: Tool definitions designed for LLM understanding.

## Tools Included

### 1. `list_flet_controls`
List all available Flet UI controls.

### 2. `search_flet_docs(query)`
Search the documentation index.

### 3. `get_flet_doc(doc_path)`
Get raw Markdown for a specific doc.

### 4. `list_official_packages()`
List official Flet extension packages.

### 5. `search_flet_ecosystem(query)`
Search for verified community Flet components.

### 6. `get_package_details(package_name)`
Fetch version and installation info from PyPI.

## Client Configuration Examples

### 🌌 VSCode
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


### 🌌 Antigravity / Cascade
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

### 🤖 Claude Desktop
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

### 💻 Cursor / Windsurf
In your IDE's MCP settings, add a new server:
- **Name**: Flet MCP
- **Type**: Command
- **Command**: `uvx flet-mcp-server`

## Development

### Directory Structure
```text
flet-mcp-server/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── publish.yml
├── docs/
│   ├── ARCHITECTURE.md
│   └── CONTRIBUTING.md
├── src/
│   └── flet_mcp/
│       ├── services/
│       │   ├── github_docs.py
│       │   ├── packages.py
│       │   └── __init__.py
│       ├── main.py
│       ├── server.py
│       └── __init__.py
├── tests/
│   └── test_fetcher.py
├── LICENSE
├── README.md
├── pyproject.toml
└── uv.lock
```

### Install
```bash
git clone https://github.com/Nwokike/flet-mcp-server.git
cd flet-mcp-server
uv sync
```

### Test
```bash
uv run pytest
```

## License
MIT
