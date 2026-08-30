#!/usr/bin/env python3
"""Render one validated Breadcrumb pull-request title and body from JSON stdin."""

from __future__ import annotations

from internal.cli import run_renderer
from internal.rendering import render_pull_request


if __name__ == "__main__":
    raise SystemExit(run_renderer(render_pull_request))
