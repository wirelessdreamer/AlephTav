from __future__ import annotations

from app.llm.base import GenerationResponse
from app.services import generation_service, ingest_service, registry_service


class FakeGenerationAdapter:
    name = "fake-generation"

    def __init__(self, profile: dict) -> None:
        self.profile = profile

    def generate_json(self, generation_request) -> GenerationResponse:
        unit_id = generation_request.metadata["unit_id"]
        layer = generation_request.metadata["layer"]
        return GenerationResponse(
            payload={
                "unit_id": unit_id,
                "layer": layer,
                "candidates": [
                    {
                        "text": "The heavens declare",
                        "rationale": "Hebrew-grounded fixture",
                        "alignment_hints": ["aln.fixture.0001"],
                        "drift_flags": [],
                        "metrics": {"grounding_score": 0.88},
                        "variation_basis": ["source_grounded_rendering"],
                        "preserved_source_images": [{"label": "heavens", "source_id": "uxlc"}],
                        "differentiator": "best grounded English",
                        "grounding_confidence": 0.88,
                        "translation_basis": {
                            "basis_type": "hebrew_to_english",
                            "source_ids": ["uxlc", "oshb", "macula"],
                            "source_language": "he",
                            "source_version": "fixture-2026.04",
                            "basis_note": "Fixture Hebrew basis",
                        },
                    },
                    {
                        "text": "The heavens proclaim",
                        "rationale": "Septuagint-grounded fixture",
                        "alignment_hints": ["aln.fixture.0002"],
                        "drift_flags": [],
                        "metrics": {"grounding_score": 0.88},
                        "variation_basis": ["emphasis_shift"],
                        "preserved_source_images": [{"label": "heavens", "source_id": "lxx"}],
                        "differentiator": "Septuagint pressure",
                        "grounding_confidence": 0.88,
                        "translation_basis": {
                            "basis_type": "septuagint_greek_to_english",
                            "source_ids": ["lxx", "macula"],
                            "source_language": "grc",
                            "source_version": "fixture-2026.04",
                            "basis_note": "Fixture Septuagint basis",
                        },
                    },
                    {
                        "text": "The heavens declare",
                        "rationale": "Duplicate should be removed",
                        "alignment_hints": ["aln.fixture.0003"],
                        "drift_flags": [],
                        "metrics": {"grounding_score": 0.7},
                        "variation_basis": ["source_grounded_rendering"],
                        "preserved_source_images": [{"label": "heavens", "source_id": "uxlc"}],
                        "differentiator": "duplicate",
                        "grounding_confidence": 0.7,
                        "translation_basis": {
                            "basis_type": "hebrew_to_english",
                            "source_ids": ["uxlc", "oshb", "macula"],
                            "source_language": "he",
                            "source_version": "fixture-2026.04",
                            "basis_note": "Fixture Hebrew basis",
                        },
                    },
                ],
            },
            raw_text="{}",
            runtime_metadata={"provider": "fake"},
        )


def test_generate_for_unit_prefers_hebrew_on_ties_and_suppresses_duplicates(monkeypatch) -> None:
    monkeypatch.setattr("app.services.generation_service.build_adapter", lambda profile: FakeGenerationAdapter(profile))

    job = generation_service.generate_for_unit("ps019.v001.a", layer="phrase", style_profile="study_literal", candidate_count=3, force=True)

    assert [candidate["text"] for candidate in job["output"]["candidates"]] == ["The heavens declare", "The heavens proclaim"]
    assert job["output"]["candidates"][0]["translation_basis"]["basis_type"] == "hebrew_to_english"
    assert job["output"]["candidates"][1]["translation_basis"]["basis_type"] == "septuagint_greek_to_english"
    assert job["output"]["candidates"][1]["metrics"]["distinctness_score"] > 0


def test_locked_inputs_include_septuagint_witness_for_vendored_import() -> None:
    try:
        ingest_service.import_vendored_psalms()
        unit = registry_service.load_unit("ps001.v001.a")
        locked_inputs = generation_service._locked_inputs(unit, "gloss")

        assert "septuagint_greek_witness" in locked_inputs
        assert locked_inputs["septuagint_greek_witness"]["language"] == "grc"
        assert locked_inputs["septuagint_greek_tokens"]
    finally:
        from tests.support import bootstrap_fixture_repo

        bootstrap_fixture_repo()


class FakeLyricGenerationAdapter:
    name = "fake-lyric-generation"

    def __init__(self, profile: dict) -> None:
        self.profile = profile

    def generate_json(self, generation_request) -> GenerationResponse:
        unit_id = generation_request.metadata["unit_id"]
        layer = generation_request.metadata["layer"]
        return GenerationResponse(
            payload={
                "unit_id": unit_id,
                "layer": layer,
                "candidates": [
                    {
                        "text": "My bones—\nshake inside me",
                        "rationale": "Fixture lyric with lineation",
                        "alignment_hints": ["aln.fixture.lyric.0001"],
                        "drift_flags": [],
                        "metrics": {"grounding_score": 0.84},
                        "variation_basis": ["cadence_or_emphasis_shift"],
                        "preserved_source_images": [{"label": "bones", "source_id": "uxlc"}],
                        "differentiator": "sparse lineation",
                        "grounding_confidence": 0.84,
                        "translation_basis": {
                            "basis_type": "hebrew_to_english",
                            "source_ids": ["uxlc", "oshb", "macula"],
                            "source_language": "he",
                            "source_version": "fixture-2026.04",
                            "basis_note": "Fixture Hebrew basis",
                        },
                    }
                ],
            },
            raw_text="{}",
            runtime_metadata={"provider": "fake"},
        )


def test_generate_for_unit_preserves_lyric_line_breaks(monkeypatch) -> None:
    monkeypatch.setattr("app.services.generation_service.build_adapter", lambda profile: FakeLyricGenerationAdapter(profile))
    monkeypatch.setattr("app.services.generation_service._locked_inputs", lambda unit, layer: {"hebrew_tokens": []})

    job = generation_service.generate_for_unit("ps019.v001.a", layer="lyric", style_profile="performative_free", candidate_count=1, force=True)

    assert job["output"]["candidates"][0]["text"] == "My bones—\nshake inside me"
