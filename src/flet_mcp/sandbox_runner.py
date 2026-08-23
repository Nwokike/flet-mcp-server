"""Subprocess sandbox that executes Flet code for verification.

Run as ``python -m flet_mcp.sandbox_runner`` with the user's code on stdin.
The process execs the code with flet's app-launchers neutralized (so nothing
opens a window or starts a server), records deprecation warnings, then walks
every constructed control and fires flet's deferred validators
(``_before_update_safe`` — the same call flet's update cycle makes) to catch
errors that only appear at mount time. Prints a single JSON report on stdout.

This module must stay importable in a bare interpreter: it intentionally
imports everything lazily inside ``main()``.
"""

from __future__ import annotations

import gc
import io
import json
import sys
import traceback
import warnings
from typing import Any

USER_FILENAME = "<user_code>"


def _user_line(exc: BaseException) -> int | None:
    """Deepest frame of the exception that is inside the user's code."""
    line = None
    for frame in traceback.extract_tb(exc.__traceback__):
        if frame.filename == USER_FILENAME:
            line = frame.lineno
    return line


def _collect_warnings(caught: list[warnings.WarningMessage]) -> list[dict]:
    out = []
    seen: set[tuple[int | None, str]] = set()
    for w in caught:
        if not issubclass(w.category, (DeprecationWarning, PendingDeprecationWarning)):
            continue
        # flet attributes its deprecation warnings to user code via stacklevel;
        # only keep those (skip third-party noise).
        if w.filename != USER_FILENAME:
            continue
        # flet's deprecated_class wraps both __init__ AND __post_init__, so one
        # construction fires the same warning twice — collapse those.
        key = (w.lineno, str(w.message))
        if key in seen:
            continue
        seen.add(key)
        out.append({"line": w.lineno, "message": str(w.message)})
    return out


def main() -> None:
    code = sys.stdin.read()
    report: dict = {
        "status": "ok",
        "controls_verified": 0,
        "errors": [],
        "warnings": [],
    }

    import flet as ft

    # Neutralize anything that could launch a GUI/server from verified code.
    for runner in ("app", "run", "app_async", "run_async"):
        setattr(ft, runner, lambda *args, **kwargs: None)

    namespace = {"__name__": "__main__", "ft": ft, "flet": ft}

    user_stdout = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = user_stdout
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                exec(compile(code, USER_FILENAME, "exec"), namespace)  # noqa: S102
            except Exception as exc:  # noqa: BLE001 - report, don't crash
                report["errors"].append(
                    {
                        "line": _user_line(exc),
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )

            from flet.controls.base_control import BaseControl

            def live_controls() -> list:
                controls = [o for o in gc.get_objects() if isinstance(o, BaseControl)]
                controls.sort(key=lambda c: getattr(c, "_i", 0))
                return controls

            # Typical AI code defines main(page) and ends with ft.app(main).
            # ft.app is neutralized, so nothing would ever run — invoke main()
            # ourselves against a mock page so the controls get constructed.
            # Keep the page (and main's return value) referenced until after
            # the validation walk: CPython frees unreferenced controls
            # immediately, and freed controls are invisible to gc.get_objects().
            kept_alive: list[Any] = []
            if not live_controls():
                entry = namespace.get("main")
                if callable(entry):
                    import inspect

                    mock_page = _MockPage()
                    kept_alive.append(mock_page)
                    try:
                        if inspect.iscoroutinefunction(entry):
                            import asyncio

                            kept_alive.append(asyncio.run(entry(mock_page)))
                        else:
                            kept_alive.append(entry(mock_page))
                    except Exception as exc:  # noqa: BLE001
                        report["errors"].append(
                            {
                                "line": _user_line(exc),
                                "type": type(exc).__name__,
                                "message": str(exc),
                            }
                        )

            # Fire flet's deferred validators on every constructed control —
            # the update cycle normally does this; headless we do it ourselves.
            for ctl in live_controls():
                validate = getattr(ctl, "_before_update_safe", None)
                if not callable(validate):  # flet internals changed — degrade
                    continue
                try:
                    validate()
                except Exception as exc:  # noqa: BLE001
                    report["errors"].append(
                        {
                            "line": None,
                            "type": type(exc).__name__,
                            "message": f"{type(ctl).__name__}: {exc}",
                        }
                    )
            report["controls_verified"] = len(live_controls())
            report["warnings"].extend(_collect_warnings(caught))
    finally:
        sys.stdout = real_stdout

    if report["errors"]:
        report["status"] = "errors"
    json.dump(report, sys.stdout)


class _MockAny:
    """Permissive stand-in: any attribute or call is a harmless no-op."""

    def __call__(self, *args, **kwargs):
        return _MockAny()

    def __getattr__(self, name):
        return _MockAny()

    def append(self, *args, **kwargs):
        pass

    def __iter__(self):
        return iter(())


class _MockPage:
    """Headless page double: records added controls, tolerates everything else."""

    def __init__(self):
        self._added: list = []
        self.controls: list = []
        self.views: list = []

    def add(self, *controls):
        self.controls.extend(controls)
        self._added.extend(controls)

    def insert(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _MockAny()


if __name__ == "__main__":
    main()
