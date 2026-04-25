# 🛸 Flet MCP Server

[![PyPI Version](https://img.shields.io/pypi/v/flet-mcp-server)](https://pypi.org/project/flet-mcp-server/)
[![PyPI Downloads](https://static.pepy.tech/badge/flet-mcp-server)](https://pepy.tech/project/flet-mcp-server)
[![Nwokike/flet-mcp-server MCP server](https://glama.ai/mcp/servers/Nwokike/flet-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/Nwokike/flet-mcp-server)
[![CI Status](https://github.com/Nwokike/flet-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/Nwokike/flet-mcp-server/actions/workflows/ci.yml)
![Python Versions](https://img.shields.io/pypi/pyversions/flet-mcp-server)

Model Context Protocol (MCP) server that dynamically fetches and serves official Flet resources to AI agents, including documentation, controls, packages, and ecosystem components.

[![Nwokike/flet-mcp-server MCP server](https://glama.ai/mcp/servers/Nwokike/flet-mcp-server/badges/card.svg)](https://glama.ai/mcp/servers/Nwokike/flet-mcp-server)
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
