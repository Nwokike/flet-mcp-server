"""Introspection over the installed Flet package — the source of truth.

Flet's API evolves faster than model training data, so these helpers let an AI
read the *actual* source of the flet install this server carries (or, when
FLET_MCP_VENV is set, the user's own project venv) instead of guessing.

Everything file-based (read/search/icons/colors) works purely on disk so it
stays correct even when the target flet was built for a different Python.
Only control introspection imports flet at runtime.
"""

from __future__ import annotations

import ast
import difflib
import io
import json
import re
import sys
from dataclasses import MISSING, fields as dataclass_fields
from functools import lru_cache
from pathlib import Path
from typing import Any, get_type_hints

from flet_mcp.exceptions import SourceError, SymbolNotFoundError

VENV_ENV_VAR = "FLET_MCP_VENV"
MAX_OUTPUT_CHARS = 16_000
MAX_LINES_DEFAULT = 400

_STYLE_RE = re.compile(r"\x1b\[[0-9;]*m")


class ResolvedFlet:
    """Location and metadata of the flet install every tool below reads."""

    def __init__(self, pkg_dir: Path, version: str, source: str) -> None:
        self.pkg_dir = pkg_dir
        self.version = version
        self.source = source  # "bundled" or e.g. "FLET_MCP_VENV=/path/.venv"

    @property
    def banner(self) -> str:
        return f"[flet {self.version} — {self.source}]"

    def rel(self, abs_path: Path) -> str:
        return abs_path.resolve().relative_to(self.pkg_dir.resolve()).as_posix()


_resolved: ResolvedFlet | None = None


def _reset_resolution() -> None:
    """Forget the cached resolution (used by tests and env changes)."""
    global _resolved
    _resolved = None


def _site_packages(venv: Path) -> Path | None:
    for pattern in ("lib/python*/site-packages", "Lib/site-packages"):
        matches = sorted(venv.glob(pattern), reverse=True)
        if matches:
            return matches[0]
    return None


def _version_from_dist_info(site_parent: Path) -> str | None:
    for d in sorted(site_parent.glob("flet-*.dist-info"), reverse=True):
        m = re.match(r"flet-(.+)\.dist-info$", d.name)
        if m:
            return m.group(1)
    return None


def resolve_flet() -> ResolvedFlet:
    """Locate flet once: the FLET_MCP_VENV venv if configured, else bundled."""
    global _resolved
    if _resolved is not None:
        return _resolved

    venv = __import__("os").environ.get(VENV_ENV_VAR, "").strip()
    if venv:
        venv_path = Path(venv).expanduser()
        if not venv_path.is_dir():
            raise SourceError(f"{VENV_ENV_VAR} points to '{venv}', which is not a directory.")
        sp = _site_packages(venv_path)
        if sp is None or not (sp / "flet").is_dir():
            raise SourceError(
                f"No 'flet' package found in the venv at '{venv}'. "
                "Unset the variable to use the bundled flet instead."
            )
        sys.path.insert(0, str(sp))
        source = f"{VENV_ENV_VAR}={venv}"
    else:
        source = "bundled"

    try:
        import flet  # noqa: PLC0415 — deliberately late so Local Mode wins
    except ImportError as exc:  # pragma: no cover - env corruption
        raise SourceError(f"Could not import flet: {exc}") from exc

    pkg_dir = Path(flet.__file__).resolve().parent
    version = _version_from_dist_info(pkg_dir.parent) or getattr(flet, "__version__", "unknown")
    _resolved = ResolvedFlet(pkg_dir, str(version), source)
    return _resolved


@lru_cache(maxsize=1)
def _py_files(pkg_dir: str) -> tuple[str, ...]:
    files = [p for p in Path(pkg_dir).rglob("*.py") if "__pycache__" not in p.parts]
    return tuple(sorted(str(p) for p in files))


def _normalize_module(module: str) -> str:
    s = module.strip().replace("\\", "/")
    for prefix in ("flet/", "flet."):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    s = s.removeprefix("./")
    if s.endswith(".py"):
        s = s[:-3]
    return s.replace(".", "/")


def _resolve_module_path(module: str) -> Path:
    r = resolve_flet()
    rel = _normalize_module(module)
    candidate = (r.pkg_dir / rel).with_suffix(".py")
    if not candidate.exists() and (r.pkg_dir / rel / "__init__.py").exists():
        candidate = r.pkg_dir / rel / "__init__.py"
    if not candidate.exists():
        known = [r.rel(Path(p)) for p in _py_files(str(r.pkg_dir))]
        close = difflib.get_close_matches(rel + ".py", known, n=5, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise SourceError(
            f"No module '{module}' in flet {r.version}.{hint} "
            "Use search_flet_source to explore available files."
        )
    resolved = candidate.resolve()
    if not resolved.is_relative_to(r.pkg_dir.resolve()):
        raise SourceError("Path escapes the flet package directory.")
    return resolved


def _numbered(lines: list[str], start: int = 1) -> str:
    width = len(str(start + len(lines) - 1))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, start))


def _find_symbol_node(tree: ast.Module, symbol: str) -> ast.AST | None:
    parts = symbol.split(".")
    targets = [tree] if len(parts) == 1 else []
    node = None
    for top in ast.iter_child_nodes(tree):
        if isinstance(top, ast.ClassDef) and top.name == parts[0]:
            node = top
            break
        if (
            len(parts) == 1
            and isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and top.name == parts[0]
        ):
            return top
    if node is None and len(parts) > 1:
        return None
    for part in parts[1:]:
        node = next(
            (
                c
                for c in ast.iter_child_nodes(node)
                if isinstance(c, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and c.name == part
            ),
            None,
        )
        if node is None:
            return None
    if targets or node is not None:
        return node
    return None


def read_source(module: str, symbol: str | None = None, max_lines: int = MAX_LINES_DEFAULT) -> str:
    """Read the installed source of a flet module, or one symbol inside it."""
    r = resolve_flet()
    path = _resolve_module_path(module)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    rel = r.rel(path)

    if symbol:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*", symbol):
            raise SourceError(f"Invalid symbol name: '{symbol}'")
        try:
            tree = ast.parse(text)
        except SyntaxError:  # pragma: no cover - shipped sources parse
            raise SourceError(f"Could not parse {rel} to extract '{symbol}'.")
        node = _find_symbol_node(tree, symbol)
        if node is None:
            defined = [
                n.name
                for n in ast.iter_child_nodes(tree)
                if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            close = difflib.get_close_matches(symbol, defined, n=5, cutoff=0.5)
            hint = f" Close matches: {', '.join(close)}." if close else ""
            raise SymbolNotFoundError(
                f"No class/function '{symbol}' in flet/{rel}.{hint} Defined: {', '.join(defined[:40])}"
            )
        segment = lines[node.lineno - 1 : node.end_lineno]
        header = f"{r.banner} {rel}:{node.lineno}-{node.end_lineno} — {symbol}\n\n"
        if len(segment) > 1200:
            segment = segment[:1200]
            trunc = "\n… (truncated; read the file directly for the rest)"
        else:
            trunc = ""
        return header + _numbered(segment, node.lineno) + trunc

    shown = lines[:max_lines]
    note = (
        f"\n… ({len(lines) - max_lines} more lines — pass a symbol name to extract one)"
        if len(lines) > max_lines
        else ""
    )
    return f"{r.banner} flet/{rel} ({len(lines)} lines)\n\n" + _numbered(shown) + note


def search_source(query: str, max_results: int = 25) -> list[str]:
    """Case-insensitive search across the installed flet sources, best matches first."""
    r = resolve_flet()
    q = query.strip()
    if not q:
        raise SourceError("Empty query.")
    ql = q.lower()
    decl_re = re.compile(rf"\b(class|def)\s+\w*{re.escape(ql)}\w*", re.IGNORECASE)
    assign_re = re.compile(rf"^\s*\w*{re.escape(ql)}\w*\s*[:=]", re.IGNORECASE)

    hits: list[tuple[int, str, int, str]] = []  # (-score, rel_path, lineno, line)
    for fp in _py_files(str(r.pkg_dir)):
        rel = r.rel(Path(fp))
        try:
            content = Path(fp).read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover - unreadable file
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            if ql not in line.lower():
                continue
            if decl_re.search(line):
                score = 3
            elif assign_re.match(line):
                score = 2
            else:
                score = 1
            hits.append((-score, rel, lineno, line.strip()[:160]))

    hits.sort()
    total = len(hits)
    results = [
        f"{rel}:{lineno} | {_STYLE_RE.sub('', snippet)}"
        for _, rel, lineno, snippet in hits[:max_results]
    ]
    used = sum(len(x) for x in results)
    while results and used > MAX_OUTPUT_CHARS:
        used -= len(results.pop())
    if total > len(results):
        results.append(f"… {total - len(results)} more matches not shown (refine the query)")
    if not results:
        return [
            f"No matches for '{query}' in flet {r.version}. "
            "Try a shorter substring, e.g. 'drag' instead of 'drag_target'."
        ]
    return results


def _enum_members_from_source(path: Path, class_name: str) -> dict[str, str]:
    """Extract `NAME = "value"` enum members from a module's AST (no import)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            members: dict[str, str] = {}
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    members[stmt.targets[0].id] = stmt.value.value
                elif (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    members[stmt.target.id] = stmt.value.value
            return members
    return {}


@lru_cache(maxsize=4)
def _icons_map(pkg_dir: str, icon_set: str) -> dict[str, int]:
    r = resolve_flet()
    rel = (
        "controls/material/icons.json"
        if icon_set == "material"
        else "controls/cupertino/cupertino_icons.json"
    )
    path = r.pkg_dir / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceError(
            f"Icon data not available in flet {r.version} ({exc}). "
            "Fall back to search_flet_source(query='icon')."
        ) from exc
    return {name: int(code) for name, code in data.items()}


def search_icons(query: str, icon_set: str = "material", max_results: int = 50) -> list[str]:
    """Search Material (Icons.*) / Cupertino (CupertinoIcons.*) icon names."""
    if icon_set not in ("material", "cupertino"):
        raise SourceError("icon_set must be 'material' or 'cupertino'.")
    r = resolve_flet()
    q = query.strip().upper().replace(" ", "_")
    data = _icons_map(str(r.pkg_dir), icon_set)
    prefix = "Icons." if icon_set == "material" else "CupertinoIcons."

    exact = [n for n in data if n == q]
    starts = [n for n in data if n.startswith(q) and n != q]
    contains = [n for n in data if q in n and not n.startswith(q)]
    fuzzy = difflib.get_close_matches(q, [n for n in data if q not in n], n=max_results, cutoff=0.7)
    ranked = exact + starts + sorted(contains) + fuzzy

    seen: set[str] = set()
    ordered = [n for n in ranked if not (n in seen or seen.add(n))]
    shown = ordered[:max_results]
    results = [f"{prefix}{n}  (0x{data[n]:X})" for n in shown]
    if len(ordered) > len(shown):
        results.append(f"… {len(ordered) - len(shown)} more matches not shown")
    if not results:
        return [f"No {icon_set} icons match '{query}' in flet {r.version}."]
    return results


def search_colors(query: str, max_results: int = 50) -> list[str]:
    """Search named Material colors (Colors.*) — includes shades like AMBER_500."""
    r = resolve_flet()
    q = query.strip().upper().replace(" ", "_")

    material = _enum_members_from_source(r.pkg_dir / "controls" / "colors.py", "Colors")
    cupertino = _enum_members_from_source(
        r.pkg_dir / "controls" / "cupertino" / "cupertino_colors.py", "CupertinoColors"
    )

    def rank(items: dict[str, str], prefix: str) -> list[str]:
        exact = [n for n in items if n == q]
        starts = [n for n in items if n.startswith(q) and n != q]
        contains = sorted(n for n in items if q in n and not n.startswith(q))
        fuzzy = difflib.get_close_matches(
            q, [n for n in items if q not in n], n=max_results, cutoff=0.7
        )
        ranked, seen = [], set()
        for n in exact + starts + contains + fuzzy:
            if n not in seen:
                seen.add(n)
                ranked.append(f'{prefix}{n} = "{items[n]}"')
        return ranked

    results = rank(material, "Colors.")
    results += rank(cupertino, "CupertinoColors.")
    total = len(results)
    results = results[:max_results]
    if total > len(results):
        results.append(f"… {total - len(results)} more matches not shown")
    if not results:
        return [f"No colors match '{query}' in flet {r.version}."]
    return results


def _module_to_rel(module: str) -> str:
    """flet.controls.material.button -> controls/material/button (no .py suffix)."""
    r = resolve_flet()
    rel = module.replace("flet.", "", 1) if module.startswith("flet.") else module
    path = r.pkg_dir / Path(*rel.split("."))
    return (
        r.rel(path)
        if (path.with_suffix(".py")).exists() or (path / "__init__.py").exists()
        else rel.replace(".", "/")
    )


def _default_repr(f: Any) -> str:
    if f.default is not MISSING:
        return repr(f.default)
    if f.default_factory is not MISSING:  # type: ignore[misc]
        factory = f.default_factory  # type: ignore[misc]
        if factory is list:
            return "[]"
        if factory is dict:
            return "{}"
        if factory is set:
            return "set()"
        if factory is tuple:
            return "()"
        return "<factory>"
    return "required"


def _fmt_type(tp: Any) -> str:
    """Human/LLM-friendly rendering: Annotated metadata stripped, unions as
    `X | Y | None`, bare class names instead of reprs, flet module prefixes
    and ForwardRef wrappers cleaned up."""
    import types as _types
    import typing as _typing

    if isinstance(tp, str):
        rendered = tp
    elif tp is None or tp is type(None):
        rendered = "None"
    else:
        origin = _typing.get_origin(tp)
        if origin is _typing.Annotated:
            args = _typing.get_args(tp)
            rendered = _fmt_type(args[0]) if args else str(tp)
        elif isinstance(tp, _typing.ForwardRef):
            rendered = tp.__forward_arg__
        elif origin in (_typing.Union, _types.UnionType):
            rendered = " | ".join(_fmt_type(a) for a in _typing.get_args(tp))
        elif origin is not None:
            name = getattr(origin, "__name__", None) or str(origin)
            args = _typing.get_args(tp)
            rendered = f"{name}[{', '.join(_fmt_type(a) for a in args)}]" if args else name
        elif isinstance(tp, type):
            rendered = tp.__name__
        else:
            rendered = str(tp)

    rendered = re.sub(r"\bflet\.(?:controls|components|utils)\.(?:\w+\.)*", "", rendered)
    rendered = re.sub(r"<class '([\w.]+)'>", lambda m: m.group(1).rsplit(".", 1)[-1], rendered)
    return re.sub(r"ForwardRef\('(\w+)'\)", r"\1", rendered)


def inspect_control(name: str) -> str:
    """Full, exact API report for a flet control: fields, types, defaults,
    events, deprecations and the class source — straight from the installed flet."""
    r = resolve_flet()
    import flet  # noqa: PLC0415

    target = None
    if hasattr(flet, name):
        target = getattr(flet, name)
    else:
        public = [n for n in getattr(flet, "__all__", []) if n.lower() == name.lower()]
        if public:
            target = getattr(flet, public[0])
    if target is None:
        close = difflib.get_close_matches(name, list(getattr(flet, "__all__", [])), n=5, cutoff=0.5)
        hint = f" Close matches: {', '.join(close)}." if close else ""
        raise SymbolNotFoundError(
            f"'{name}' is not exported by flet {r.version}.{hint} "
            "Use list_flet_api() to see every public name."
        )
    if not isinstance(target, type):
        mod = getattr(target, "__module__", "")
        rel = _module_to_rel(mod) if mod else ""
        return (
            f"{r.banner} '{name}' is a {type(target).__name__}, not a class — "
            f"defined in flet/{rel}.py. Use read_flet_source('{rel}', '{name}') "
            "to read its implementation."
        )

    cls = target
    try:
        source, lineno = _class_source(cls)
    except (OSError, TypeError) as exc:
        raise SourceError(f"Could not read source of {name}: {exc}") from exc

    mro = [c for c in cls.__mro__ if c.__module__.startswith("flet")]
    out = io.StringIO()
    out.write(f"{r.banner} # {cls.__name__}\n\n")
    out.write(f"module: {cls.__module__}  (flet/{_module_to_rel(cls.__module__)}.py:{lineno})\n")
    out.write(
        "inherits: "
        + " → ".join(
            f"{c.__name__} (flet/{_module_to_rel(c.__module__)}.py)" for c in reversed(mro[1:])
        )
        + "\n\n"
    )

    if "@deprecated_class" in source:
        m = re.search(r'deprecated_class\(\s*reason="([^"]+)"', source)
        reason = m.group(1) if m else "see source"
        v = re.search(r'version="([^"]+)"', source)
        out.write(f"⚠ DEPRECATED since flet {v.group(1) if v else '?'}: {reason}\n\n")

    events: list[str] = []
    rows: list[tuple[str, str, str, str]] = []
    origin: dict[str, str] = {}
    for klass in reversed(mro):
        try:
            for f in dataclass_fields(klass):
                # Base-first iteration: the first (most base) class defining a
                # field is its true origin — dataclass_fields() also returns
                # inherited fields, so don't overwrite.
                origin.setdefault(f.name, klass.__name__)
        except TypeError:
            pass
    if dataclass_fields_safe(cls):
        try:
            hints = get_type_hints(cls, include_extras=True)
        except Exception:  # noqa: BLE001 - exotic annotations degrade gracefully
            hints = {}
        for f in dataclass_fields(cls):
            if f.name.startswith("_"):
                continue  # private machinery (_values, _dirty, ...)
            ftype = _fmt_type(hints.get(f.name, f.type))
            rows.append((f.name, ftype, _default_repr(f), origin.get(f.name, "?")))
            if f.name.startswith("on_"):
                events.append(f.name)

    if rows:
        out.write(f"## Properties ({len(rows)}, incl. inherited — exact for flet {r.version})\n\n")
        out.write("| Property | Type | Default | Inherits from |\n|---|---|---|---|\n")
        for n, t, d, o in rows:
            cell = lambda v: str(v).replace("|", "\\|")  # noqa: E731
            out.write(f"| `{n}` | {cell(t)} | {cell(d)} | {o} |\n")
        out.write("\n")
    else:
        out.write(
            "Not a dataclass control — read the source below or its __init__ signature"
            " for parameters.\n\n"
        )

    if events:
        out.write(f"## Events\n\n{', '.join(f'`{e}`' for e in events)}\n\n")

    src_lines = source.splitlines()
    if len(src_lines) > 800:
        src_lines = src_lines[:800]
        src_note = "\n… (source truncated at 800 lines)"
    else:
        src_note = ""
    out.write(
        f"## Source (flet/{_module_to_rel(cls.__module__)}.py:{lineno} — "
        "field docstrings included)\n\n"
    )
    out.write(_numbered(src_lines, lineno))
    out.write(src_note)

    result = out.getvalue()
    return (
        result
        if len(result) <= MAX_OUTPUT_CHARS * 2
        else result[: MAX_OUTPUT_CHARS * 2] + "\n… (truncated)"
    )


def dataclass_fields_safe(cls: type) -> bool:
    try:
        dataclass_fields(cls)
        return True
    except TypeError:
        return False


def _class_source(cls: type) -> tuple[str, int]:
    import inspect  # noqa: PLC0415

    lines, lineno = inspect.getsourcelines(cls)
    return "".join(lines), lineno


_CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("flet.components", "Components & hooks"),
    ("flet.controls.services", "Services"),
    ("flet.controls.material", "Material controls"),
    ("flet.controls.cupertino", "Cupertino controls"),
    ("flet.controls.canvas", "Canvas"),
    ("flet.app", "App runtime"),
    ("flet.messaging", "Runtime & internals"),
    ("flet.pubsub", "Runtime & internals"),
    ("flet.utils", "Runtime & internals"),
    ("flet.security", "Runtime & internals"),
    ("flet.fastapi", "Runtime & internals"),
    ("flet.testing", "Runtime & internals"),
    ("flet.auth", "Runtime & internals"),
)


def list_api() -> dict[str, Any]:
    """Every public flet name, grouped by category, from the installed version."""
    r = resolve_flet()
    import flet  # noqa: PLC0415

    lazy: dict[str, str] = dict(getattr(flet, "_LAZY", {}) or {})
    names = [n for n in (getattr(flet, "__all__", []) or dir(flet)) if not n.startswith("_")]

    if not lazy:
        return {
            "flet_version": r.version,
            "note": "ungrouped (this flet version has no module registry)",
            "names": sorted(n for n in names if not n.startswith("_")),
        }

    groups: dict[str, list[str]] = {}
    for n in names:
        module = lazy.get(n, "")
        for prefix, category in _CATEGORY_RULES:
            if module.startswith(prefix):
                groups.setdefault(category, []).append(n)
                break
        else:
            groups.setdefault("Core controls & types", []).append(n)

    return {
        "flet_version": r.version,
        **{k: sorted(v) for k, v in sorted(groups.items())},
    }
