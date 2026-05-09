from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.composer_quality_support import KNOWN_BAD_PATTERNS, build_composer_outputs, bootstrap_vendored_repo


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
COMPOSER_FIXTURE = FIXTURES_DIR / "composer_quality.json"
pytestmark = pytest.mark.no_seeded_repo


def _load_fixture() -> dict[str, object]:
    return json.loads(COMPOSER_FIXTURE.read_text(encoding="utf-8"))


def test_curated_composer_outputs_match_exact_snapshots(tmp_path_factory) -> None:
    fixture = _load_fixture()
    exact_units = fixture["exact_units"]
    unit_ids = list(exact_units.keys())

    bootstrap_vendored_repo()
    outputs = build_composer_outputs(unit_ids, tmp_path_factory.mktemp("composer-exact"))

    for unit_id, expected in exact_units.items():
        actual = {
            "phrase": [choice.label for choice in outputs[unit_id].phrase],
            "concept": [choice.label for choice in outputs[unit_id].concept],
            "lyric": [choice.label for choice in outputs[unit_id].lyric],
        }
        assert actual == expected, f"composer snapshot drifted for {unit_id}"


def test_curated_composer_quality_subset_blocks_known_artifacts(tmp_path_factory) -> None:
    fixture = _load_fixture()
    exact_units = fixture["exact_units"]
    quality_units = fixture["quality_units"]
    unit_ids = [*exact_units.keys(), *quality_units.keys()]

    bootstrap_vendored_repo()
    outputs = build_composer_outputs(unit_ids, tmp_path_factory.mktemp("composer-quality"))

    for unit_id in unit_ids:
        rows = outputs[unit_id]
        assert rows.phrase, f"{unit_id} should emit phrase rows"
        assert rows.concept, f"{unit_id} should emit concept rows"
        assert rows.lyric, f"{unit_id} should emit lyric rows"
        assert len(rows.phrase) == len(rows.concept) == len(rows.lyric), f"{unit_id} chunk counts diverged"

        for stage, lines in {
            "phrase": [choice.label for choice in rows.phrase],
            "concept": [choice.label for choice in rows.concept],
            "lyric": [choice.label for choice in rows.lyric],
        }.items():
            assert all(line.strip() for line in lines), f"{unit_id} {stage} emitted blank text"
            joined = " || ".join(lines)
            for pattern in KNOWN_BAD_PATTERNS:
                assert re.search(pattern, joined, flags=re.IGNORECASE) is None, (
                    f"{unit_id} {stage} regressed with artifact pattern {pattern!r}: {joined}"
                )

    for unit_id, expectations in quality_units.items():
        phrase_text = " || ".join(choice.label for choice in outputs[unit_id].phrase)
        for needle in expectations.get("phrase_contains", []):
            assert needle.lower() in phrase_text.lower(), f"{unit_id} phrase lost expected anchor {needle!r}"
        minimum_chunk_count = expectations.get("min_chunk_count")
        if minimum_chunk_count is not None:
            assert len(outputs[unit_id].phrase) >= minimum_chunk_count, (
                f"{unit_id} phrase collapsed below {minimum_chunk_count} chunks: {[choice.label for choice in outputs[unit_id].phrase]}"
            )
