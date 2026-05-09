#!/usr/bin/env python3
"""PostToolUse hook: run scripts/validate_content.py after edits to content/ or schemas/.

Exits 2 on validation failure so Claude sees the problem and stops.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WATCHED_PREFIXES = ("content/", "schemas/")


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
    relative = Path(file_path).as_posix()
    if not any(seg in relative for seg in WATCHED_PREFIXES):
        return 0
    if Path(file_path).suffix.lower() not in {".json", ".yaml", ".yml"}:
        return 0

    result = subprocess.run(
        [sys.executable, "scripts/validate_content.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("[validate_content] failed:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
