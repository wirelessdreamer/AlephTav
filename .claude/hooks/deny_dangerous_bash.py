#!/usr/bin/env python3
"""PreToolUse hook for Bash: block destructive commands that should never run.

Reads the Claude Code hook payload from stdin. Exits 2 with a stderr message
to block the tool call; exits 0 to allow.
"""
from __future__ import annotations

import json
import re
import sys

DENY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-[rfRF]+\b"), "rm -rf is denied. Delete files via the workspace, not bash."),
    (re.compile(r"\bgit\s+push\s+(--force|-f)\b"), "git push --force is denied."),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard is denied; use git stash/checkout."),
    (re.compile(r"(^|/|\s)data/raw(/|\s|$)"), "data/raw/ is the read-only vendored corpus."),
    (re.compile(r"(^|/|\s)\.venv(/|\s|$)"), "Do not modify .venv from bash; recreate via setup.sh."),
    (re.compile(r"\bnpm\s+publish\b"), "npm publish is denied for this project."),
    (re.compile(r"\bpip\s+install\s+(?!-e\s+\.\[dev\]\b)"), "Pin deps via pyproject.toml; ad-hoc pip install is denied."),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    for pattern, reason in DENY_PATTERNS:
        if pattern.search(command):
            print(f"[deny_dangerous_bash] {reason}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
