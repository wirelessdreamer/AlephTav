#!/usr/bin/env python3
"""UserPromptSubmit hook: when the user mentions canonical/promote/merge/release,
inject a one-line reminder of the canonical-vs-alternate policy.

Reads the prompt text from stdin payload; prints a short context block to
stdout (which Claude Code includes as additional context for the turn).
Always exits 0.
"""
from __future__ import annotations

import json
import re
import sys

TRIGGERS = re.compile(
    r"\b(canonical|promote|promotion|merge\s+to\s+main|release\b|alternate)\b",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    if not isinstance(prompt, str) or not TRIGGERS.search(prompt):
        return 0

    print(
        "POLICY REMINDER: canonical promotions or modifications require 2 "
        "qualified reviewer approvals (lexical / Hebrew / alignment / lyric / "
        "theology / release roles). Alternates need 1. Every content "
        "mutation must produce an AuditRecord (schemas/audit_record.schema.json). "
        "data/raw/ is read-only. See CLAUDE.md > 'Things you must never do'."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
