"""Pydantic models for structured tool outputs (mcp 2.x renders these as
output schemas automatically)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FletVersionInfo(BaseModel):
    flet_version: str
    package_path: str
    source: str
    error: str | None = None


class Diagnostic(BaseModel):
    line: int | None = None
    severity: Literal["error", "warning"]
    code: str
    message: str
    hint: str | None = None


class VerifyReport(BaseModel):
    status: Literal["passed", "errors", "timeout"]
    flet_version: str
    checks: list[str]
    controls_verified: int
    duration_ms: int
    diagnostics: list[Diagnostic]
