from __future__ import annotations

from pathlib import Path

from app.services import registry_service


GOLDEN_PSALMS = ("ps001", "ps019", "ps023", "ps051")
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_seeded_psalm_goldens_match_snapshots() -> None:
    for psalm_id in GOLDEN_PSALMS:
        expected = (FIXTURES_DIR / f"{psalm_id}.json").read_text(encoding="utf-8")
        actual = registry_service.deterministic_json(registry_service.load_psalm(psalm_id))
        assert actual == expected, f"golden snapshot drifted for {psalm_id}"
