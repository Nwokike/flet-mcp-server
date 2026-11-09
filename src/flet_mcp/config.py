"""Shared configuration: cache location and Flet repo settings."""

import os
from pathlib import Path

import diskcache_community


def cache_dir() -> str:
    """Cache directory: FLET_MCP_CACHE_DIR override, else XDG cache (survives reboots,
    unlike the old /tmp default)."""
    env = os.environ.get("FLET_MCP_CACHE_DIR")
    if env:
        return env
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return str(Path(base) / "flet-mcp")


def new_cache() -> diskcache_community.Cache:
    """Tuned cache: indexed tags (bulk invalidation), LRU eviction, 256MB cap."""
    return diskcache_community.Cache(
        cache_dir(),
        tag_index=True,
        eviction_policy="least-recently-used",
        size_limit=256 * 2**20,
        disk=diskcache_community.SafeDisk.with_options(on_error="miss"),
    )


FLET_REPO = os.environ.get("FLET_REPO", "flet-dev/flet")
FLET_BRANCH = os.environ.get("FLET_BRANCH", "main")
