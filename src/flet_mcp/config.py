"""Shared configuration: cache location and Flet repo settings."""

import os
from pathlib import Path

import diskcache


def cache_dir() -> str:
    """Cache directory: FLET_MCP_CACHE_DIR override, else XDG cache (survives reboots,
    unlike the old /tmp default)."""
    env = os.environ.get("FLET_MCP_CACHE_DIR")
    if env:
        return env
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return str(Path(base) / "flet-mcp")


def new_cache() -> diskcache.Cache:
    """Tuned cache: indexed tags (bulk invalidation), LRU eviction, 256MB cap."""
    return diskcache.Cache(
        cache_dir(),
        tag_index=True,
        eviction_policy="least-recently-used",
        size_limit=256 * 2**20,
    )


FLET_REPO = os.environ.get("FLET_REPO", "flet-dev/flet")
FLET_BRANCH = os.environ.get("FLET_BRANCH", "main")
