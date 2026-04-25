# Architecture

The Flet MCP Server is built with a focus on speed, reliability, and real-time data.

## Directory Structure
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

## Components

### 1. `FastMCP` Interface
Uses the official Python SDK to expose tools via the Model Context Protocol.

### 2. Documentation Service (`github_docs.py`)
*   Uses the GitHub Git Tree API to fetch documentation structure.
*   Caches content locally to minimize network latency.

### 3. Package Service (`packages.py`)
*   Scrapes official extensions from the Flet repository.
*   Searches GitHub for community packages.
*   **PyPI Verification**: Cross-references GitHub search results with PyPI metadata to ensure packages actually depend on `flet`.
*   **Classification**: Automatically classifies packages as "UI Control" or "Service Integration" based on summary analysis.

### 4. Caching Layer
*   Uses `diskcache` for persistent storage.
*   **Cloud Readiness**: The cache directory is configurable via `FLET_MCP_CACHE_DIR` (defaults to `/tmp/flet-mcp-cache`) to ensure compatibility with restricted cloud environments like Smithery.

### 5. Extreme Hardening
*   **Silence**: All `uv` and Python outputs are silenced or redirected to `stderr` to maintain MCP protocol integrity.
*   **Reliability**: The server entry point is wrapped in comprehensive error handling to prevent silent crashes.
*   **Immediate Flush**: Uses unbuffered I/O (`PYTHONUNBUFFERED=1`) to ensure logs are visible in real-time for debugging.

## Roadmap

- [ ] **Dynamic Documentation Switching**: Support fetching docs from specific Flet versions.
- [ ] **Advanced Package Analysis**: Deep-dive into community package source code for better usage examples.
- [ ] **Interactive Examples**: Generate and serve working Flet code snippets directly to the AI agent.
- [ ] **Local Mode**: Support indexing local Flet projects for project-specific AI assistance.
