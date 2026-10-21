"""Inventory missing Codex anchors, or recover evidenced proposals with --apply."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.codex_source_anchor_recovery_service import recover_source_anchors  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = recover_source_anchors(apply=args.apply)
    output = args.output or get_settings().audit_reports_dir / "codex_source_anchor_recovery.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "report": str(output)}))


if __name__ == "__main__":
    main()
