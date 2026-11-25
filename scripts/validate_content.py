from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The checks live in the app so the installed CLI and API can import them.
from app.services.content_validation_service import validate_all_content  # noqa: E402

__all__ = ["validate_all_content"]


def main() -> None:
    result = validate_all_content()
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
