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

* **GitHub Tree Sync**: Maps documentation in real-time from the Flet repository.
* **Intelligent Caching**: Uses `diskcache` for fast responses with 24-hour TTL.
* **Smart Search**: Fuzzy matching, keyword aliases, and direct path search over documentation.
* **Ecosystem Discovery**: Finds and verifies official and community Flet packages via PyPI metadata.
* **AI-Optimized**: Tool definitions designed for LLM understanding with clear usage guidance.
* **Configurable**: Supports custom Flet repo/branch via environment variables.
* **Resource Safe**: Shared HTTP client with proper lifecycle management and graceful shutdown.

## Tools Included

### 1. `list_flet_controls`
List all available Flet UI controls.

### 2. `search_flet_docs(query)`
Search the documentation index with fuzzy matching and keyword aliases.

### 3. `get_flet_doc(doc_path)`
Get raw Markdown for a specific doc file.

### 4. `list_official_packages()`
List official Flet extension packages from the monorepo.

### 5. `search_flet_ecosystem(query)`
Search for verified community Flet components on GitHub.

### 6. `get_package_details(package_name)`
Fetch version, type classification, and installation info from PyPI.

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
  "context_servers": {
    /// Configure an MCP server that runs locally via stdin/stdout
    ///
    /// The name of your MCP server
    "flet-mcp-server": {
      /// The command which runs the MCP server
      "command": "uvx",
      /// The arguments to pass to the MCP server
      "args": [
        "flet-mcp-server"
      ],
      /// The environment variables to set
      "env": {}
    }
  }
}

```

### OpenCode

Add this to your `~/.config/opencode/opencode.json` or project-level `.opencode/opencode.json`:

```json
{
  "$schema": "[https://opencode.ai/config.json](https://opencode.ai/config.json)",
  "mcp": {
    "flet-mcp": {
      "type": "local",
      "command": ["uvx", "flet-mcp-server"],
      "enabled": true
    }
  }
}

```

For authenticated GitHub API access (higher rate limits), set `GITHUB_TOKEN` in your environment:

```json
{
  "$schema": "[https://opencode.ai/config.json](https://opencode.ai/config.json)",
  "mcp": {
    "flet-mcp": {
      "type": "local",
      "command": ["uvx", "flet-mcp-server"],
      "enabled": true,
      "env": {
        "GITHUB_TOKEN": "your-github-token"
      }
    }
  }
}

```

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
│       ├── __init__.py
│       ├── exceptions.py
│       ├── http.py
│       ├── main.py
│       └── server.py
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

### Lint

```bash
uv run ruff check .

```

## Changelog

### v0.2.0
- **Smart Search**: Added fuzzy matching, keyword alias index, and multi-strategy search (direct > alias > fuzzy)
- **Shared HTTP Client**: Single `httpx.AsyncClient` with proper lifecycle management via server lifespan
- **Custom Exceptions**: `DocNotFoundError`, `PackageNotFoundError`, `FetchError`, `TreeFetchError` for better error handling
- **Configurable Repo/Branch**: `FLET_REPO` and `FLET_BRANCH` environment variables for version pinning
- **Robust Control Parsing**: Set-based deduplication with safer path parsing
- **Concurrent Verification**: Batched PyPI verification with semaphore-based rate limiting for ecosystem search
- **Graceful Shutdown**: Server lifespan handler cleans up HTTP connections
- **Better Error Handling**: All tools catch and format errors gracefully for LLM consumption
- **Mocked Tests**: Full test suite with mocked HTTP responses for fast, reliable CI
- **OpenCode Support**: Added OpenCode MCP configuration example to README
- **Expanded Fallback**: Added `flet`, `flet-cli`, `flet-desktop`, `flet-web` to fallback package list

<details>
<summary>v0.1.1</summary>

- Initial release with 6 MCP tools
- GitHub Tree API integration with diskcache
- PyPI verification for ecosystem packages

</details>

## License
MIT
