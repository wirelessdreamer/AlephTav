from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import catalog_path  # noqa: E402

# Keep missing outputs distinct from an unexpected Python exit (status 1).
MISSING_OUTPUTS = 3


def cmd_check(mode: str) -> int:
    try:
        settings = get_settings()
        first_psalm = settings.psalms_dir / "ps001"
        required = [
            settings.project_file,
            catalog_path(),
            first_psalm / "ps001.meta.json",
            first_psalm / "ps001.v001.a.json",
        ]
        if mode == "fixture":
            required.append(settings.indexes_dir / "vector" / "visual_flow_index.json")
        else:
            required.append(settings.psalms_dir / "ps150" / "ps150.meta.json")

        missing = [path for path in required if not path.is_file()]
    except (ImportError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"unable to check {mode} data outputs: {error}", file=sys.stderr)
        return 2

    if missing:
        names = ", ".join(path.relative_to(settings.root_dir).as_posix() for path in missing)
        print(f"missing {mode} data outputs: {names}")
        return MISSING_OUTPUTS
    print(f"required {mode} data outputs are present")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check which required setup outputs are missing.")
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--mode", choices=("full", "fixture"), required=True)
    return cmd_check(parser.parse_args().mode)


if __name__ == "__main__":
    raise SystemExit(main())
