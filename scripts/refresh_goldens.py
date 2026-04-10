from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import registry_service
from tests.support import bootstrap_fixture_repo


GOLDEN_PSALMS = ("ps001", "ps019", "ps023", "ps051")


def main() -> None:
    bootstrap_fixture_repo()
    fixtures_dir = ROOT / "tests" / "golden" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    for psalm_id in GOLDEN_PSALMS:
        payload = registry_service.load_psalm(psalm_id)
        (fixtures_dir / f"{psalm_id}.json").write_text(
            registry_service.deterministic_json(payload),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
