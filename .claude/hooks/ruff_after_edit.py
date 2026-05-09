#!/usr/bin/env python3
"""PostToolUse hook: run ruff check --fix and ruff format on an edited Python file.

Exits 2 if ruff still reports errors after auto-fix so Claude sees the failure.
Silent for non-Python files.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _file_path(payload: dict) -> str | None:
    tool = payload.get("tool_name")
    if tool not in {"Edit", "Write", "MultiEdit"}:
        return None
    return (payload.get("tool_input") or {}).get("file_path")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = _file_path(payload)
    if not file_path:
        return 0
    path = Path(file_path)
    if path.suffix != ".py":
        return 0
    # Skip vendored / generated paths.
    parts = set(path.parts)
    if parts & {".venv", "node_modules", "data", ".pytest_cache"}:
        return 0
    if not path.exists():
        return 0

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    fix = subprocess.run(["ruff", "check", "--fix", str(path)], capture_output=True, text=True, env=env)
    fmt = subprocess.run(["ruff", "format", str(path)], capture_output=True, text=True, env=env)
    check = subprocess.run(["ruff", "check", str(path)], capture_output=True, text=True, env=env)

    if check.returncode != 0:
        print(f"[ruff] {path}: remaining errors after auto-fix:", file=sys.stderr)
        print(check.stdout, file=sys.stderr)
        print(check.stderr, file=sys.stderr)
        return 2
    # Silent on success; only chatter on suppressed failures.
    if fix.returncode not in (0, 1) or fmt.returncode != 0:
        print(f"[ruff] {path}: tooling produced an unexpected exit code", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
