#!/usr/bin/env python3
"""PostToolUse hook: warn (non-blocking) when a prompt under app/llm/prompts/ is edited.

Prompt edits invalidate goldens; this surfaces the next steps. Always exits 0.
"""
from __future__ import annotations

import json
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
    relative = Path(file_path).as_posix()
    if "app/llm/prompts/" not in relative:
        return 0

    print(
        "[prompt-change] You edited a prompt under app/llm/prompts/. "
        "Goldens are likely now stale. Suggested next steps: "
        "(1) /test-golden to confirm impact, "
        "(2) /refresh-goldens only if the change is intentional and reviewed, "
        "(3) commit goldens together with the prompt change.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
