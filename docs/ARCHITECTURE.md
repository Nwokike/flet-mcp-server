# Architecture

The Flet MCP Server is built with a focus on speed, reliability, and real-time data.

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
Uses `diskcache` to store responses for 24 hours, ensuring near-instant tool execution for the AI agent.
