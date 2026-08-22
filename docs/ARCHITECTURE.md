# Architecture

The Flet MCP Server is built around one idea: **the installed flet source code
is the source of truth**. Docs and training data go stale; the package sitting
in site-packages never lies about the API your app actually runs.

## Directory Structure
```text
flet-mcp-server/
├── .github/workflows/          # CI (matrix + fresh-install smoke), publish
├── docs/
├── scripts/
│   └── smoke_stdio.py          # full MCP handshake from a clean uvx env
├── src/flet_mcp/
│   ├── services/
│   │   ├── flet_source.py      # introspection over installed flet (no HTTP)
│   │   ├── flet_verify.py      # verify_flet_code: static AST + sandbox orchestration
│   │   ├── github_docs.py      # official docs from the Flet repo
│   │   ├── packages.py         # ecosystem discovery (GitHub + PyPI)
│   │   └── __init__.py
│   ├── config.py               # cache dir/factory, repo/branch env vars
│   ├── exceptions.py
│   ├── http.py                 # shared retrying httpx client + rate-limit hook
│   ├── main.py                 # entry point; stdio/sse/streamable-http via env
│   ├── models.py               # pydantic models for structured tool outputs
│   ├── sandbox_runner.py       # subprocess code-execution sandbox
│   └── server.py               # MCPServer + 14 tools, 3 prompts, 2 resources
├── tests/
│   ├── test_flet_source.py     # runs against the REAL bundled flet
│   ├── test_flet_verify.py     # static + real-subprocess dynamic tests
│   └── test_fetcher.py         # mocked HTTP tests
├── CHANGELOG.md
├── README.md
├── pyproject.toml
└── uv.lock
```

## Components

### 1. `MCPServer` interface (mcp >= 2)
Built on `mcp.server.mcpserver.MCPServer` — the successor to `FastMCP`, which
the mcp SDK removed in 2.0 (the cause of the v0.2.0 outage). The server passes
`instructions` that teach clients the workflow: verify APIs against the
installed source before writing Flet code, and verify code before delivering
it. Every tool carries `ToolAnnotations(read_only_hint=True,
destructive_hint=False)`; list methods advertise `CacheHint`s so clients may
cache `tools/list`/`resources/list`/`prompts/list`. Structured outputs come
from pydantic return models (`VerifyReport`, `FletVersionInfo`) in `models.py`.

### 2. Flet source service (`flet_source.py`)
Bundles flet as a dependency and reads it locally, three ways:

* **File/AST-based** (works on any flet layout, even a different Python's
  venv): `read_flet_source` (path-guarded, symbol extraction via AST),
  `search_flet_source` (ranked scan), `search_flet_icons` (the icon JSON
  databases), `search_flet_colors` (enum members parsed from source).
* **Import-based**: `inspect_flet_control` resolves a class through flet's lazy
  `__init__`, walks the MRO, and renders a property table from
  `dataclasses.fields()` with origin classes, defaults, `on_*` events and
  deprecation detection (flet controls are `@dataclass(kw_only=True)` with
  validators and per-field docstrings — the docstrings only exist in source).
* **Registry-based**: `list_flet_api` reads flet's runtime `__all__` and the
  `_LAZY` name→module registry to group the API by category. On flet versions
  without the registry it degrades to an ungrouped listing.

**Local Mode**: `FLET_MCP_VENV=/path/to/.venv` prepends that venv's
site-packages before flet is first imported, so every tool reads the user's
project flet instead of the bundled one. Resolution happens once and is cached;
every response carries a `[flet X.Y.Z — source]` banner.

### 3. Code verification (`flet_verify.py` + `sandbox_runner.py`)
`verify_flet_code` runs two passes:

* **Static** (in-process AST, never executes user code): unknown `ft.X` names
  and bad `from flet import X` names (against `flet.__all__`), constructor
  kwargs that aren't dataclass fields (against `cls.__dataclass_fields__`,
  which includes InitVars), enum literal typos (against `Enum.__members__` via
  `get_type_hints`), undefined `on_*` handlers, and deprecated classes
  (source-scanned `@deprecated_class` registry). Every diagnostic has a line
  number and a difflib hint.
* **Dynamic** (fresh subprocess, `python -m flet_mcp.sandbox_runner`, code via
  stdin, timeout enforced): flet's app launchers are neutralized (nothing can
  open a window or start a server), `main(page)` — if defined and nothing was
  constructed at module level — is invoked against a permissive `_MockPage`
  so the controls actually get built; `DeprecationWarning`s are recorded;
  then every live control is pushed through `_before_update_safe()` — the
  same hook flet's update cycle uses — which fires the deferred `V.*`
  validators that construction alone never triggers (`Slider(min > max)`
  etc.). The mock page and `main`'s return value are kept referenced until
  after the walk: CPython frees unreferenced controls immediately, and freed
  controls are invisible to `gc.get_objects()`. In Local Mode the subprocess
  gets the project venv's site-packages on `PYTHONPATH`, so verification runs
  against the user's flet.

Limitations (documented in the tool description): runtime semantics, layout,
and session-dependent behavior are not verifiable headlessly; enum-string
errors in dynamically-built dicts are only caught by the static pass.

### 4. Prompts, resources, transports
Three prompts encode the verify→fix→re-verify, migration, and
build-then-verify workflows. Two resources expose the installed flet:
`flet://version` (static) and `flet-source://{+module}` (template; the SDK's
`ResourceSecurity` default rejects path traversal/absolute paths/NUL bytes
after URI decoding). `main.py` maps `FLET_MCP_TRANSPORT`/`FLET_MCP_HOST`/
`FLET_MCP_PORT` to `MCPServer.run()` — stdio by default, `sse` and
`streamable-http` via the uvicorn/starlette the SDK already depends on — and a
`custom_route` provides `GET /health` for HTTP deployments.

### 5. Documentation service (`github_docs.py`)
Fetches the `website/docs` **subtree** (`<branch>:website/docs`) rather than
the whole recursive tree — small, and immune to GitHub's 100k-entry truncation
—with a whole-tree fallback and truncation warnings. Raw Markdown fetches are
authenticated when `GITHUB_TOKEN` is set.

### 6. Package service (`packages.py`)
Official packages come from the `sdk/python/packages` subtree (direct children
only). Community search hits GitHub's repository search, then verifies each
result against PyPI metadata (`requires_dist` contains `flet`) with
semaphore-limited concurrency. Network failures raise `FetchError` (surfaced
as friendly tool errors) instead of silently returning empty results.

### 7. Caching & HTTP layers
`diskcache` (24h TTL, tagged `github`/`pypi` for bulk invalidation, LRU
eviction, 256MB cap) under `~/.cache/flet-mcp` (XDG-aware,
`FLET_MCP_CACHE_DIR` override — Smithery sets this). One shared
`httpx.AsyncClient` — retrying transport, `follow_redirects`, granular
timeouts, and a response hook that turns GitHub 403/429 rate-limit responses
into a friendly `RateLimitedError` that suggests setting `GITHUB_TOKEN` —
created lazily and closed in the server lifespan.

### 8. Release safety
`scripts/smoke_stdio.py` installs the server into a **fresh ephemeral uvx
environment** — exactly what end users get — and runs a full MCP handshake
plus one call per tool group, the prompts/resources listings, and a
verify_flet_code round-trip (broken code must fail, clean code must pass). CI
runs it on every push; it is the regression test that would have caught the
mcp 2.0 outage.

## Dependency policy

All dependencies are pinned to latest at release time (`mcp>=2.0.0`,
`flet>=0.86.0`). Users can pin a specific flet with
`uvx --with flet==X.Y.Z flet-mcp-server`; Local Mode (`FLET_MCP_VENV`) can read
any venv regardless of the floor, since file-based tools never import it.

## Roadmap

- [x] **Local Mode**: verify against the user's project venv (`FLET_MCP_VENV`).
- [ ] **Dynamic documentation switching**: fetch docs for a specific Flet version.
- [ ] **Advanced package analysis**: deep-dive community package sources.
- [ ] **Interactive examples**: generate runnable Flet snippets from verified API data.
