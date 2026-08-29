#!/usr/bin/env python3
"""Render one validated repository-local Breadcrumb ADR from JSON stdin."""

from __future__ import annotations

from internal.cli import run_renderer
from internal.rendering import render_adr


if __name__ == "__main__":
    raise SystemExit(run_renderer(render_adr))
