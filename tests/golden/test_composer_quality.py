from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import lyric_reference_service
from tests.composer_quality_support import (
    KNOWN_BAD_PATTERNS,
    audit_composer_outputs,
    bootstrap_vendored_repo,
    build_composer_outputs,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
COMPOSER_FIXTURE = FIXTURES_DIR / "composer_quality.json"
COMPOSER_SOURCE = Path(__file__).resolve().parents[2] / "app/ui/src/lib/composerSynthesis.ts"
pytestmark = pytest.mark.no_seeded_repo


def _load_fixture() -> dict[str, object]:
    return json.loads(COMPOSER_FIXTURE.read_text(encoding="utf-8"))


def _all_fixture_unit_ids(fixture: dict[str, object]) -> list[str]:
    exact_units = fixture["exact_units"]
    quality_units = fixture["quality_units"]
    audit_clean_units = fixture["audit_clean_units"]
    return sorted({*exact_units.keys(), *quality_units.keys(), *audit_clean_units})


@pytest.fixture(scope="module")
def composer_outputs(tmp_path_factory):
    fixture = _load_fixture()
    bootstrap_vendored_repo()
    return build_composer_outputs(
        _all_fixture_unit_ids(fixture),
        tmp_path_factory.mktemp("composer-fixture"),
    )


def _covered_indexes(rows) -> set[int]:
    return {token_index for choice in rows for token_index in range(choice.start, choice.end + 1)}


def test_generic_composer_has_no_psalm_keyed_curated_table() -> None:
    source = COMPOSER_SOURCE.read_text(encoding="utf-8")
    forbidden_markers = [
        "REFERENCE_PSALM_CURATED_LINES",
        "CuratedComposerLine",
        "curatedChunk",
        "ps012.v002.a",
        "ps130.v001.a",
    ]
    for marker in forbidden_markers:
        assert marker not in source, f"composer should not hard-code psalm output marker {marker!r}"


def test_generic_composer_outputs_match_exact_snapshots(composer_outputs) -> None:
    fixture = _load_fixture()
    exact_units = fixture["exact_units"]

    for unit_id, expected in exact_units.items():
        actual = {
            "phrase": [choice.label for choice in composer_outputs[unit_id].phrase],
            "concept": [choice.label for choice in composer_outputs[unit_id].concept],
            "lyric": [choice.label for choice in composer_outputs[unit_id].lyric],
        }
        assert actual == expected, f"composer snapshot drifted for {unit_id}"


def test_generic_composer_quality_subset_blocks_known_artifacts(composer_outputs) -> None:
    fixture = _load_fixture()
    exact_units = fixture["exact_units"]
    quality_units = fixture["quality_units"]
    audit_clean_units = fixture["audit_clean_units"]
    unit_ids = sorted({*exact_units.keys(), *quality_units.keys(), *audit_clean_units})

    for unit_id in unit_ids:
        rows = composer_outputs[unit_id]
        assert rows.phrase, f"{unit_id} should emit phrase rows"
        assert rows.concept, f"{unit_id} should emit concept rows"
        assert rows.lyric, f"{unit_id} should emit lyric rows"
        expected_coverage = set(range(rows.token_count))
        assert (
            _covered_indexes(rows.phrase) == expected_coverage
        ), f"{unit_id} phrase token coverage diverged"
        assert (
            _covered_indexes(rows.concept) == expected_coverage
        ), f"{unit_id} concept token coverage diverged"
        assert (
            _covered_indexes(rows.lyric) == expected_coverage
        ), f"{unit_id} lyric token coverage diverged"

        for stage, lines in {
            "phrase": [choice.label for choice in rows.phrase],
            "concept": [choice.label for choice in rows.concept],
            "lyric": [choice.label for choice in rows.lyric],
        }.items():
            assert all(line.strip() for line in lines), f"{unit_id} {stage} emitted blank text"
            joined = " || ".join(lines)
            for pattern in KNOWN_BAD_PATTERNS:
                assert (
                    re.search(pattern, joined, flags=re.IGNORECASE) is None
                ), f"{unit_id} {stage} regressed with artifact pattern {pattern!r}: {joined}"
            for line in lines:
                quality = lyric_reference_service.evaluate_candidate_quality(line, stage)
                assert (
                    quality["score"] >= lyric_reference_service.MIN_SURFACED_PRODUCTION_QUALITY
                ), (
                    f"{unit_id} {stage} fell below lyric-reference production floor: "
                    f"{line!r} -> {quality}"
                )

    for unit_id, expectations in quality_units.items():
        phrase_text = " || ".join(choice.label for choice in composer_outputs[unit_id].phrase)
        for needle in expectations.get("phrase_contains", []):
            assert (
                needle.lower() in phrase_text.lower()
            ), f"{unit_id} phrase lost expected anchor {needle!r}"
        minimum_chunk_count = expectations.get("min_chunk_count")
        if minimum_chunk_count is not None:
            phrase_labels = [choice.label for choice in composer_outputs[unit_id].phrase]
            assert (
                len(composer_outputs[unit_id].phrase) >= minimum_chunk_count
            ), f"{unit_id} phrase collapsed below {minimum_chunk_count} chunks: {phrase_labels}"

    clean_outputs = {unit_id: composer_outputs[unit_id] for unit_id in audit_clean_units}
    report = audit_composer_outputs(clean_outputs)
    assert report["unit_count"] == len(audit_clean_units)
    assert report["flagged_unit_count"] == 0, report["flagged_units"][:5]
    assert report["issue_unit_counts"] == {}
