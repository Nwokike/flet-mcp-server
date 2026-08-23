# Changelog

## 1.0.2 (2026-08-23)

Polish release from a full live-tool audit — every tool exercised against the
published package, every found defect fixed and regression-tested.

- **Fixed: stdlib shadowing** — the internal module `http.py` shadowed
  Python's stdlib `http` package whenever `src/flet_mcp` landed on `sys.path`
  (e.g. `python src/flet_mcp/main.py`), breaking `import http.client` inside
  starlette. Renamed to `http_client.py`.
- **Fixed: duplicate deprecation diagnostics** — one deprecated-class usage in
  `verify_flet_code` produced three `deprecated` entries (static pass plus
  flet's warning firing on both `__init__` and `__post_init__`); now reported
  exactly once, with the static entry's did-you-mean hint.
- **Fixed: repr leaks in `inspect_flet_control`** — property tables no longer
  show `<class 'RouteChangeEvent'>` (bare names now) or `<<lambda>()>`
  defaults (`[]`, `{}`, `<factory>`).
- **Fixed: fuzzy-match noise** — icon/color searches no longer return
  look-alikes (`CupertinoColors.LABEL` for "amber", `PALETTE` for "delete");
  fuzzy cutoff tightened to 0.7.
- **Fixed: `list_flet_api`** no longer lists `__version__` and other
  underscore names.
- **Improved: `get_flet_doc` output** — Docusaurus frontmatter, JSX imports
  and `<CodeExample>` tags are stripped (replaced by a pointer to the example
  source), so docs pages read as clean Markdown.
- 82 tests (was 75), each fix covered by a regression test.

## 1.0.1 (2026-08-23)

- **New: official examples** — `search_flet_examples(query)` and
  `get_flet_example(example_id)` serve the runnable example apps from the flet
  repo (counter, todo, 7guis, routing, games, declarative components…), live
  via the same subtree-fetch + cache infra as the docs tools — always in sync
  with the repo, with a character budget so big examples page gracefully.
- **New: paged doc reads** — `get_flet_doc` takes `offset`/`max_lines` and
  tells you the next offset, keeping long doc pages from flooding the
  conversation.
- **Fixed**: `list_flet_api` failed through the MCP protocol — its
  `dict[str, list[str]]` return annotation made the SDK's structured-output
  validation reject the `flet_version` string key. Now typed
  `dict[str, list[str] | str]`. Found by live-testing all tools against the
  published 1.0.0; the smoke test now *calls* the tool through the protocol
  (listing it wasn't enough).
- **Polish**: `inspect_flet_control` property tables render readable type
  names (`Event[Button]` instead of
  `flet.controls.control_event.Event[ForwardRef('Button')]`).
- **Docs**: README now carries a complete tools reference (all 16 tools,
  prompts and resources) in one table.

## 1.0.0 (2026-08-22)

The source-of-truth release. Flet changes faster than model training data, so
the server now ships with flet as a dependency and exposes tools that read the
**installed** flet source — the only reference that matches what your app
actually runs.

### Fixed
- **The outage**: `uvx flet-mcp-server` works again with no extra flags. v0.2.0
  broke for every fresh install because the mcp SDK 2.0 removed
  `mcp.server.fastmcp`; the server now builds on `MCPServer` (`mcp>=2.0.0`).
- GitHub docs/packages listings now fetch repo **subtrees** instead of the
  whole recursive tree, immune to GitHub's 100k-entry truncation, with
  truncation-aware fallbacks.
- Raw doc fetches now send `GITHUB_TOKEN` when configured (previously only the
  tree API was authenticated).

### Added
- **`verify_flet_code(code)`** — verify AI-written Flet code against the
  installed flet: static analysis (unknown controls, removed/renamed
  properties, enum typos, deprecated classes, undefined handlers — with line
  numbers and did-you-mean hints) plus a sandboxed dynamic pass (app launchers
  neutralized, `main()` invoked against a mock page, flet's own deferred
  validators fired on every constructed control) catching runtime-only errors
  like `Slider(min > max)`. Returns a structured `VerifyReport`.
- **MCP prompts**: `verify_flet_code_prompt`, `migrate_flet_prompt`,
  `build_flet_ui_prompt` — one-click guided workflows.
- **MCP resources**: `flet://version` and the `flet-source://{+module}`
  template (browsable installed source with built-in path-traversal security).
- **HTTP transports**: `FLET_MCP_TRANSPORT=stdio|sse|streamable-http` with
  `FLET_MCP_HOST`/`FLET_MCP_PORT` (bundled uvicorn) and a `GET /health`
  liveness route — stdio remains the default.
- `ToolAnnotations` (read-only hints, titles) on every tool; structured
  outputs via pydantic return models; client cache hints for list methods.
- `inspect_flet_control(name)` — exact, current API for any control: property
  table (name, type, default, origin class), `on_*` events, deprecation
  warnings, inheritance chain, and the full class source with per-property
  docstrings.
- `get_flet_version()` — the flet version and install path the tools read.
- `search_flet_source(query)` — ranked grep over installed flet sources.
- `read_flet_source(module, symbol?)` — numbered source of a module or a single
  class/function, with path-traversal protection.
- `list_flet_api()` — the installed version's true `flet.__all__`, grouped by
  category.
- `search_flet_icons(query, icon_set)` — valid Material/Cupertino icon names
  (no more hallucinated icons).
- `search_flet_colors(query)` — valid `Colors.*`/`CupertinoColors.*` constants.
- **Local Mode**: set `FLET_MCP_VENV=/path/to/project/.venv` to read that
  project's flet instead of the bundled one (works for verification too).
- Server `instructions` that teach clients the verify-against-source workflow.
- `scripts/smoke_stdio.py` + CI `smoke-fresh-install` job: full MCP handshake
  from a clean `uvx` environment — the regression test for the outage.
- CI matrix extended to Python 3.10–3.14.

### Changed
- All dependencies refreshed and pinned to latest (`mcp>=2.0.0`,
  `flet>=0.86.0`, `httpx>=0.28.1`, `diskcache>=5.6.3`).
- HTTP client: follow redirects, granular timeouts, and a response hook that
  turns GitHub 403/429 rate limits into a friendly error that suggests
  `GITHUB_TOKEN`; cache is LRU with tagged entries for bulk invalidation.
- HTTP client uses retrying transport; cache moved from `/tmp` to
  `~/.cache/flet-mcp` (XDG-aware, `FLET_MCP_CACHE_DIR` override retained).
- Package service raises `FetchError` on network failures instead of silently
  returning empty results.

## 0.2.0

- Smart search (direct > keyword aliases > fuzzy), shared HTTP client, custom
  exceptions, configurable repo/branch, mocked tests.

## 0.1.1

- Initial release with 6 MCP tools, GitHub Tree API integration, PyPI
  verification for ecosystem packages.
