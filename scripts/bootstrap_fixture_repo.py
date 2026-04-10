from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.support import bootstrap_fixture_repo


def main() -> None:
    bootstrap_fixture_repo()


if __name__ == "__main__":
    main()
