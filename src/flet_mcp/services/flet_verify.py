"""verify_flet_code: check AI-written Flet code against the installed flet.

Two passes:
* Static (in-process AST): unknown `ft.X` names, invalid constructor kwargs,
  enum literal typos, undefined `on_*` handlers, deprecated class usage — all
  with line numbers and did-you-mean hints.
* Dynamic (subprocess via flet_mcp.sandbox_runner): executes the code with
  app-launchers neutralized, captures TypeErrors/DeprecationWarnings, then
  fires flet's deferred validators on every constructed control — catching
  errors flet only raises in its update cycle (e.g. Slider(min > max)).
"""

from __future__ import annotations

import ast
import asyncio
import difflib
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from flet_mcp.exceptions import SourceError
from flet_mcp.models import Diagnostic, VerifyReport
from flet_mcp.services import flet_source as fs

DEFAULT_TIMEOUT_SECS = 15


# --- Static pass -----------------------------------------------------------


def _diag(
    severity: str, code: str, message: str, line: int | None, hint: str | None = None
) -> Diagnostic:
    return Diagnostic(severity=severity, code=code, message=message, line=line, hint=hint)


def _suggest(name: str, candidates) -> str | None:
    close = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return f"Did you mean '{close[0]}'?" if close else None


@lru_cache(maxsize=2)
def _deprecated_classes(pkg_dir: str) -> frozenset[str]:
    """Class names carrying a @deprecated_class decorator in installed flet."""
    deprecated: set[str] = set()
    for fp in fs._py_files(pkg_dir):
        try:
            lines = Path(fp).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            m = re.match(r"class (\w+)", line)
            if not m:
                continue
            window = lines[max(0, i - 6) : i]
            if any("deprecated_class(" in w for w in window):
                deprecated.add(m.group(1))
    return frozenset(deprecated)


def _defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.withitem,)):
            if node.optional_vars is not None and isinstance(node.optional_vars, ast.Name):
                names.add(node.optional_vars.id)
    return names


def _unwrap_enum(tp: Any) -> type | None:
    import enum as _enum
    import typing as _typing

    origin = _typing.get_origin(tp)
    if origin in (_typing.Union, type(None)) or str(origin) == "types.UnionType":
        for arg in _typing.get_args(tp):
            found = _unwrap_enum(arg)
            if found is not None:
                return found
        return None
    return tp if isinstance(tp, type) and issubclass(tp, _enum.Enum) else None


def run_static(code: str) -> list[Diagnostic]:
    """AST checks against the installed flet. Never executes user code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [_diag("error", "syntax", f"SyntaxError: {exc.msg}", exc.lineno)]

    r = fs.resolve_flet()
    import flet  # noqa: PLC0415

    aliases: dict[str, str] = {}  # local module name -> "flet"
    imported_direct: set[str] = set()  # names from `from flet import X`
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "flet":
                    aliases[a.asname or "flet"] = "flet"
        elif isinstance(node, ast.ImportFrom) and node.module == "flet":
            imported_direct.update(a.name for a in node.names)

    if not aliases and not imported_direct:
        return [
            _diag(
                "warning",
                "no-import",
                "Snippet never imports flet; nothing Flet-specific to check statically.",
                None,
            )
        ]

    defined = _defined_names(tree)
    public = set(getattr(flet, "__all__", dir(flet)))
    deprecated = _deprecated_classes(str(r.pkg_dir))
    diags: list[Diagnostic] = []

    def check_class_call(cls_name: str, node: ast.Call, line: int) -> None:
        cls = getattr(flet, cls_name, None)
        if cls_name in deprecated:
            diags.append(
                _diag(
                    "warning",
                    "deprecated",
                    f"'{cls_name}' is deprecated in flet {r.version}.",
                    line,
                    hint=_suggest(cls_name, public - deprecated),
                )
            )
        if not isinstance(cls, type) or not hasattr(cls, "__dataclass_fields__"):
            return  # not a control: construction checks don't apply
        fields: dict = cls.__dataclass_fields__
        try:
            from typing import get_type_hints

            hints = get_type_hints(cls, include_extras=True)
        except Exception:  # noqa: BLE001 - degrade to no enum checks
            hints = {}
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if kw.arg not in fields:
                diags.append(
                    _diag(
                        "error",
                        "bad-kwarg",
                        f"'{cls_name}' has no property '{kw.arg}' in flet {r.version}.",
                        line,
                        hint=_suggest(kw.arg, fields.keys()),
                    )
                )
                continue
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                enum_cls = _unwrap_enum(hints.get(kw.arg, fields[kw.arg].type))
                if enum_cls is not None:
                    valid = {m.name for m in enum_cls} | {m.value for m in enum_cls}
                    if kw.value.value not in valid:
                        diags.append(
                            _diag(
                                "error",
                                "enum-value",
                                f"'{kw.arg}': '{kw.value.value}' is not a valid "
                                f"{enum_cls.__name__}.",
                                line,
                                hint=_suggest(kw.value.value, valid),
                            )
                        )
            if (
                kw.arg.startswith("on_")
                and isinstance(kw.value, ast.Name)
                and kw.value.id not in defined
            ):
                diags.append(
                    _diag(
                        "warning",
                        "undefined-handler",
                        f"Event handler '{kw.value.id}' is not defined in the snippet.",
                        line,
                    )
                )

    for node in ast.walk(tree):
        line = getattr(node, "lineno", None) or 0
        if isinstance(node, ast.ImportFrom) and node.module == "flet":
            for a in node.names:
                if a.name not in public and not hasattr(flet, a.name):
                    diags.append(
                        _diag(
                            "error",
                            "unknown-name",
                            f"Cannot import '{a.name}' from flet {r.version}: it does not exist.",
                            line,
                            hint=_suggest(a.name, public),
                        )
                    )
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            if node.attr not in public and not hasattr(flet, node.attr):
                diags.append(
                    _diag(
                        "error",
                        "unknown-name",
                        f"'{node.value.id}.{node.attr}' does not exist in flet {r.version}.",
                        line,
                        hint=_suggest(node.attr, public),
                    )
                )
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in aliases
            ):
                check_class_call(func.attr, node, line)
            elif isinstance(func, ast.Name) and func.id in imported_direct:
                check_class_call(func.id, node, line)

    return diags


# --- Dynamic pass ----------------------------------------------------------


async def run_dynamic(code: str, timeout_secs: int = DEFAULT_TIMEOUT_SECS) -> dict:
    """Execute the code in the sandbox subprocess and return its JSON report."""
    env = os.environ.copy()
    venv = os.environ.get(fs.VENV_ENV_VAR, "").strip()
    if venv:
        sp = fs._site_packages(Path(venv).expanduser())
        if sp is not None:
            env["PYTHONPATH"] = str(sp) + os.pathsep + env.get("PYTHONPATH", "")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "flet_mcp.sandbox_runner",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(code.encode()), timeout=timeout_secs)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "status": "timeout",
            "controls_verified": 0,
            "errors": [],
            "warnings": [],
        }

    import json as _json

    try:
        report = _json.loads(out.decode())
    except ValueError:
        return {
            "status": "errors",
            "controls_verified": 0,
            "errors": [
                {
                    "line": None,
                    "type": "SandboxError",
                    "message": (err.decode(errors="replace") or "sandbox produced no report")[
                        -500:
                    ],
                }
            ],
            "warnings": [],
        }
    return report


# --- Orchestration --------------------------------------------------------


async def verify_code(code: str, timeout_secs: int = DEFAULT_TIMEOUT_SECS) -> VerifyReport:
    start = time.monotonic()
    static = run_static(code)
    dynamic = await run_dynamic(code, timeout_secs)

    diagnostics = list(static)
    for err in dynamic.get("errors", []):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="runtime",
                message=f"{err.get('type', 'Error')}: {err.get('message', '')}",
                line=err.get("line"),
            )
        )
    for warn in dynamic.get("warnings", []):
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="deprecated",
                message=warn.get("message", ""),
                line=warn.get("line"),
            )
        )

    if dynamic.get("status") == "timeout":
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="timeout",
                message=f"Code did not finish within {timeout_secs}s (infinite loop or blocking call?).",
            )
        )
        status = "timeout"
    elif any(d.severity == "error" for d in diagnostics):
        status = "errors"
    else:
        status = "passed"

    return VerifyReport(
        status=status,
        flet_version=fs.resolve_flet().version,
        checks=["static", "dynamic"],
        controls_verified=dynamic.get("controls_verified", 0),
        duration_ms=int((time.monotonic() - start) * 1000),
        diagnostics=diagnostics,
    )


__all__ = ["run_static", "run_dynamic", "verify_code", "DEFAULT_TIMEOUT_SECS", "SourceError"]
