from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import registry_service
from tests.support import bootstrap_fixture_repo


GOLDEN_PSALMS = ("ps001", "ps019", "ps023", "ps051")
FIXTURES_DIR = ROOT / "tests" / "golden" / "fixtures"
COMPOSER_FIXTURE = FIXTURES_DIR / "composer_quality.json"


def refresh_psalm_goldens() -> None:
    bootstrap_fixture_repo()
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for psalm_id in GOLDEN_PSALMS:
        payload = registry_service.load_psalm(psalm_id)
        (FIXTURES_DIR / f"{psalm_id}.json").write_text(
            registry_service.deterministic_json(payload),
            encoding="utf-8",
        )


def refresh_composer_quality() -> None:
    from tests.composer_quality_support import bootstrap_vendored_repo, build_composer_outputs

    fixture = json.loads(COMPOSER_FIXTURE.read_text(encoding="utf-8"))
    exact_unit_ids = list(fixture["exact_units"].keys())
    if not exact_unit_ids:
        return

    bootstrap_vendored_repo()
    with tempfile.TemporaryDirectory(prefix="composer-refresh-") as temp_dir:
        outputs = build_composer_outputs(exact_unit_ids, Path(temp_dir))

    fixture["exact_units"] = {
        unit_id: {
            "phrase": [choice.label for choice in outputs[unit_id].phrase],
            "concept": [choice.label for choice in outputs[unit_id].concept],
            "lyric": [choice.label for choice in outputs[unit_id].lyric],
        }
        for unit_id in exact_unit_ids
    }
    COMPOSER_FIXTURE.write_text(
        json.dumps(fixture, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh committed golden fixtures.")
    parser.add_argument(
        "--composer-quality",
        action="store_true",
        help="Refresh tests/golden/fixtures/composer_quality.json exact_units block.",
    )
    parser.add_argument(
        "--skip-psalms",
        action="store_true",
        help="Skip refreshing the per-psalm fixtures.",
    )
    args = parser.parse_args()

    if not args.skip_psalms:
        refresh_psalm_goldens()
    if args.composer_quality:
        refresh_composer_quality()


if __name__ == "__main__":
    main()
