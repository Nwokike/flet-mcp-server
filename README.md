# Flet MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

An auto-updating Model Context Protocol (MCP) server that dynamically fetches, caches, and serves the official Flet documentation and ecosystem packages directly from GitHub and PyPI.

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

## Getting Started

### 🤖 Claude Desktop
Add this to `claude_desktop_config.json`:

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
Add a new Command server:
- **Command**: `uvx flet-mcp-server`

## Development

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
