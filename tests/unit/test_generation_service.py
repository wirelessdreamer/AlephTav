from __future__ import annotations

from copy import deepcopy

from app.llm.base import GenerationResponse
from app.services import generation_service, ingest_service, registry_service


def _source_anchor(
    source_language: str = "he",
    anchor_text: str = "fixture",
    source_text: str = "fixture source",
) -> dict:
    return {
        "anchor_text": anchor_text,
        "source_language": source_language,
        "source_text": source_text,
        "basis_note": "Fixture source anchor",
    }


def _required_candidate_metadata(
    source_language: str = "he",
    delivery_profile: str = "source_grounded_phrase",
    anchor_text: str = "fixture",
    source_text: str = "fixture source",
) -> dict:
    return {
        "delivery_profile": delivery_profile,
        "source_anchor": _source_anchor(source_language, anchor_text, source_text),
    }


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
                        **_required_candidate_metadata(
                            "he", anchor_text="heavens", source_text="הַשָּׁמַיִם"
                        ),
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
                        **_required_candidate_metadata(
                            "grc", anchor_text="heavens", source_text="Οἱ οὐρανοὶ"
                        ),
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
                        **_required_candidate_metadata(
                            "he", anchor_text="heavens", source_text="הַשָּׁמַיִם"
                        ),
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


class FakeBasisBlurGenerationAdapter:
    name = "fake-basis-blur-generation"

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
                        "text": "The heavens announce",
                        "rationale": "Mismatched LXX label over Hebrew source metadata",
                        "alignment_hints": ["aln.fixture.blur.0001"],
                        "drift_flags": [],
                        "metrics": {"grounding_score": 0.99},
                        "variation_basis": ["source_grounded_rendering"],
                        "preserved_source_images": [{"label": "heavens", "source_id": "uxlc"}],
                        "differentiator": "blurred source basis",
                        "grounding_confidence": 0.99,
                        **_required_candidate_metadata(
                            "he", anchor_text="heavens", source_text="הַשָּׁמַיִם"
                        ),
                        "translation_basis": {
                            "basis_type": "septuagint_greek_to_english",
                            "source_ids": ["uxlc"],
                            "source_language": "he",
                            "source_version": "fixture-2026.04",
                            "basis_note": "Bad fixture: Greek basis label with Hebrew metadata",
                        },
                    },
                    {
                        "text": "The heavens declare",
                        "rationale": "Clean Hebrew-grounded fixture",
                        "alignment_hints": ["aln.fixture.blur.0002"],
                        "drift_flags": [],
                        "metrics": {"grounding_score": 0.84},
                        "variation_basis": ["source_grounded_rendering"],
                        "preserved_source_images": [{"label": "heavens", "source_id": "uxlc"}],
                        "differentiator": "clean Hebrew source basis",
                        "grounding_confidence": 0.84,
                        **_required_candidate_metadata(
                            "he", anchor_text="heavens", source_text="הַשָּׁמַיִם"
                        ),
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
    monkeypatch.setattr(
        "app.services.generation_service.build_adapter",
        lambda profile: FakeGenerationAdapter(profile),
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a", layer="phrase", style_profile="study_literal", candidate_count=3, force=True
    )

    assert [candidate["text"] for candidate in job["output"]["candidates"]] == [
        "The heavens declare",
        "The heavens proclaim",
    ]
    assert job["output"]["candidates"][0]["translation_basis"]["basis_type"] == "hebrew_to_english"
    assert (
        job["output"]["candidates"][1]["translation_basis"]["basis_type"]
        == "septuagint_greek_to_english"
    )
    assert job["output"]["candidates"][0]["delivery_profile"] == "source_grounded_phrase"
    assert job["output"]["candidates"][0]["source_anchor"]["source_language"] == "he"
    assert job["output"]["candidates"][0]["source_anchor"]["source_text"]
    assert job["output"]["candidates"][1]["source_anchor"]["source_language"] == "grc"
    assert job["output"]["candidates"][1]["metrics"]["distinctness_score"] > 0

    unit = registry_service.load_unit("ps019.v001.a")
    generated_renderings = [
        rendering
        for rendering in unit["renderings"]
        if rendering["layer"] == "phrase" and rendering["status"] == "proposed"
    ]
    assert generated_renderings[0]["delivery_profile"] == "source_grounded_phrase"
    assert generated_renderings[0]["source_anchor"]["source_language"] == "he"


def test_generate_for_unit_suppresses_basis_blur_when_clean_alternative_exists(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.generation_service.build_adapter",
        lambda profile: FakeBasisBlurGenerationAdapter(profile),
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a",
        layer="phrase",
        style_profile="study_literal",
        candidate_count=2,
        force=True,
    )

    candidates = job["output"]["candidates"]
    assert [candidate["text"] for candidate in candidates] == ["The heavens declare"]
    assert job["runtime_metadata"]["quality_filter"] == {
        "threshold": 0.85,
        "candidate_count_before_filter": 2,
        "surfaceable_candidate_count": 1,
        "suppressed_candidate_count": 1,
        "production_ready": True,
        "rejection_reason": None,
        "fallback_used": False,
    }
    assert job["runtime_metadata"]["production_ready"] is True
    assert candidates[0]["translation_basis"]["basis_type"] == "hebrew_to_english"
    assert candidates[0]["source_anchor"]["source_language"] == "he"


def test_generation_prompts_include_production_lyric_quality_rules() -> None:
    phrase_prompt = generation_service._load_prompt("phrase")[1]
    concept_prompt = generation_service._load_prompt("concept")[1]
    lyric_prompt = generation_service._load_prompt("lyric")[1]
    metered_prompt = generation_service._load_prompt("metered_lyric")[1]
    parallelism_prompt = generation_service._load_prompt("parallelism_lyric")[1]

    assert "Production quality standard" in phrase_prompt
    assert "completed Psalm lyric drafts" in concept_prompt
    assert "Production lyric standard" in lyric_prompt
    assert "4/4 direct" in metered_prompt
    assert "production-ready Psalm lyric" in parallelism_prompt
    assert "Do not copy those lyrics or treat them as source witnesses" in concept_prompt


def test_generation_input_contract_requires_lyric_reference_payload() -> None:
    payload = generation_service._job_payload(
        "ps019.v001.a",
        layer="phrase",
        style_profile="study_literal",
        model_profile=None,
        seed=42,
        candidate_count=2,
    )

    assert payload["lyric_reference"]["delivery_patterns"]
    missing_reference = dict(payload)
    missing_reference.pop("lyric_reference")

    errors = sorted(
        generation_service.INPUT_VALIDATOR.iter_errors(missing_reference),
        key=lambda item: list(item.path),
    )

    assert errors
    assert errors[0].validator == "required"
    assert "lyric_reference" in str(errors[0].message)


def test_generation_output_contract_requires_auditable_delivery_metadata() -> None:
    payload = {
        "unit_id": "ps019.v001.a",
        "layer": "phrase",
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
                **_required_candidate_metadata("he", anchor_text="heavens", source_text="הַשָּׁמַיִם"),
                "translation_basis": {
                    "basis_type": "hebrew_to_english",
                    "source_ids": ["uxlc", "oshb", "macula"],
                    "source_language": "he",
                    "source_version": "fixture-2026.04",
                    "basis_note": "Fixture Hebrew basis",
                },
            }
        ],
    }
    assert not list(generation_service.OUTPUT_VALIDATOR.iter_errors(payload))

    missing_delivery_profile = deepcopy(payload)
    missing_delivery_profile["candidates"][0].pop("delivery_profile")
    missing_source_anchor = deepcopy(payload)
    missing_source_anchor["candidates"][0].pop("source_anchor")

    delivery_errors = sorted(
        generation_service.OUTPUT_VALIDATOR.iter_errors(missing_delivery_profile),
        key=lambda item: list(item.path),
    )
    anchor_errors = sorted(
        generation_service.OUTPUT_VALIDATOR.iter_errors(missing_source_anchor),
        key=lambda item: list(item.path),
    )

    assert delivery_errors
    assert delivery_errors[0].validator == "required"
    assert "delivery_profile" in str(delivery_errors[0].message)
    assert anchor_errors
    assert anchor_errors[0].validator == "required"
    assert "source_anchor" in str(anchor_errors[0].message)


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
                        **_required_candidate_metadata(
                            "he",
                            delivery_profile="4_4_direct",
                            anchor_text="bones",
                            source_text="עֲצָמַי",
                        ),
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


class FakeQualityGenerationAdapter:
    name = "fake-quality-generation"

    def __init__(self, profile: dict) -> None:
        self.profile = profile

    def generate_json(self, generation_request) -> GenerationResponse:
        unit_id = generation_request.metadata["unit_id"]
        layer = generation_request.metadata["layer"]
        base_candidate = {
            "rationale": "fixture",
            "alignment_hints": [],
            "drift_flags": [],
            "variation_basis": ["fixture"],
            "preserved_source_images": [{"label": "fixture", "source_id": "uxlc"}],
            "differentiator": "fixture",
            **_required_candidate_metadata(),
            "translation_basis": {
                "basis_type": "hebrew_to_english",
                "source_ids": ["uxlc", "oshb", "macula"],
                "source_language": "he",
                "source_version": "fixture-2026.04",
                "basis_note": "Fixture Hebrew basis",
            },
        }
        return GenerationResponse(
            payload={
                "unit_id": unit_id,
                "layer": layer,
                "candidates": [
                    {
                        **base_candidate,
                        "text": "Behold, unto thee",
                        "metrics": {"grounding_score": 0.99},
                        "grounding_confidence": 0.99,
                    },
                    {
                        **base_candidate,
                        "text": "And doesn't stand with sinners",
                        "metrics": {"grounding_score": 0.82},
                        "grounding_confidence": 0.82,
                    },
                    {
                        **base_candidate,
                        "text": "Doesn't stand with sinners",
                        "metrics": {"grounding_score": 0.84},
                        "grounding_confidence": 0.84,
                    },
                ],
            },
            raw_text="{}",
            runtime_metadata={"provider": "fake"},
        )


class FakeAllBadQualityGenerationAdapter(FakeQualityGenerationAdapter):
    def generate_json(self, generation_request) -> GenerationResponse:
        unit_id = generation_request.metadata["unit_id"]
        layer = generation_request.metadata["layer"]
        base_candidate = {
            "rationale": "fixture",
            "alignment_hints": [],
            "drift_flags": [],
            "variation_basis": ["fixture"],
            "preserved_source_images": [{"label": "fixture", "source_id": "uxlc"}],
            "differentiator": "fixture",
            **_required_candidate_metadata(delivery_profile="4_4_direct"),
            "translation_basis": {
                "basis_type": "hebrew_to_english",
                "source_ids": ["uxlc", "oshb", "macula"],
                "source_language": "he",
                "source_version": "fixture-2026.04",
                "basis_note": "Fixture Hebrew basis",
            },
        }
        return GenerationResponse(
            payload={
                "unit_id": unit_id,
                "layer": layer,
                "candidates": [
                    {
                        **base_candidate,
                        "text": "Behold, unto thee",
                        "metrics": {"grounding_score": 0.99},
                        "grounding_confidence": 0.99,
                    },
                    {
                        **base_candidate,
                        "text": "[INTRO - piano]\nBreak in, God",
                        "metrics": {"grounding_score": 0.98},
                        "grounding_confidence": 0.98,
                    },
                ],
            },
            raw_text="{}",
            runtime_metadata={"provider": "fake"},
        )


class FakeRepairableGenerationAdapter(FakeQualityGenerationAdapter):
    def generate_json(self, generation_request) -> GenerationResponse:
        unit_id = generation_request.metadata["unit_id"]
        layer = generation_request.metadata["layer"]
        base_candidate = {
            "rationale": "fixture",
            "alignment_hints": [],
            "drift_flags": [],
            "variation_basis": ["fixture"],
            "preserved_source_images": [{"label": "fixture", "source_id": "uxlc"}],
            "differentiator": "fixture",
            **_required_candidate_metadata(delivery_profile="4_4_direct"),
            "translation_basis": {
                "basis_type": "hebrew_to_english",
                "source_ids": ["uxlc", "oshb", "macula"],
                "source_language": "he",
                "source_version": "fixture-2026.04",
                "basis_note": "Fixture Hebrew basis",
            },
        }
        return GenerationResponse(
            payload={
                "unit_id": unit_id,
                "layer": layer,
                "candidates": [
                    {
                        **base_candidate,
                        "text": "Nor standeth in the way of sinners",
                        "metrics": {"grounding_score": 0.99},
                        "grounding_confidence": 0.99,
                    },
                    {
                        **base_candidate,
                        "text": "In your anger me rebuke don't",
                        "metrics": {"grounding_score": 0.98},
                        "grounding_confidence": 0.98,
                    },
                ],
            },
            raw_text="{}",
            runtime_metadata={"provider": "fake"},
        )


class CapturingLyricGenerationAdapter(FakeLyricGenerationAdapter):
    def __init__(self, profile: dict) -> None:
        super().__init__(profile)
        self.requests = []

    def generate_json(self, generation_request) -> GenerationResponse:
        self.requests.append(generation_request)
        return super().generate_json(generation_request)


def test_generate_for_unit_preserves_lyric_line_breaks(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.generation_service.build_adapter",
        lambda profile: FakeLyricGenerationAdapter(profile),
    )
    monkeypatch.setattr(
        "app.services.generation_service._locked_inputs", lambda unit, layer: {"hebrew_tokens": []}
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a",
        layer="lyric",
        style_profile="performative_free",
        candidate_count=1,
        force=True,
    )

    assert job["output"]["candidates"][0]["text"] == "My bones—\nshake inside me"


def test_generate_for_unit_suppresses_low_quality_when_clean_alternative_exists(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.generation_service.build_adapter",
        lambda profile: FakeQualityGenerationAdapter(profile),
    )
    monkeypatch.setattr(
        "app.services.generation_service._locked_inputs", lambda unit, layer: {"hebrew_tokens": []}
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a",
        layer="lyric",
        style_profile="performative_free",
        candidate_count=2,
        force=True,
    )
    candidates = job["output"]["candidates"]

    assert [candidate["text"] for candidate in candidates] == ["Doesn't stand with sinners"]
    assert candidates[0]["metrics"]["production_quality_score"] == 1.0
    assert job["runtime_metadata"]["quality_filter"] == {
        "threshold": 0.85,
        "candidate_count_before_filter": 3,
        "surfaceable_candidate_count": 1,
        "suppressed_candidate_count": 2,
        "production_ready": True,
        "rejection_reason": None,
        "fallback_used": False,
    }
    assert job["runtime_metadata"]["production_ready"] is True


def test_generate_for_unit_repairs_reversible_delivery_defects_before_scoring(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.generation_service.build_adapter",
        lambda profile: FakeRepairableGenerationAdapter(profile),
    )
    monkeypatch.setattr(
        "app.services.generation_service._locked_inputs", lambda unit, layer: {"hebrew_tokens": []}
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a",
        layer="lyric",
        style_profile="performative_free",
        candidate_count=2,
        force=True,
    )
    candidates = job["output"]["candidates"]

    assert [candidate["text"] for candidate in candidates] == [
        "Doesn't stand in the way of sinners",
        "Don't rebuke me in your anger",
    ]
    assert all(candidate["metrics"]["production_quality_score"] == 1.0 for candidate in candidates)
    assert all(not candidate["drift_flags"] for candidate in candidates)


def test_generate_for_unit_withholds_candidates_when_every_option_fails_quality(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.generation_service.build_adapter",
        lambda profile: FakeAllBadQualityGenerationAdapter(profile),
    )
    monkeypatch.setattr(
        "app.services.generation_service._locked_inputs", lambda unit, layer: {"hebrew_tokens": []}
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a",
        layer="lyric",
        style_profile="performative_free",
        candidate_count=2,
        force=True,
    )
    candidates = job["output"]["candidates"]

    assert candidates == []
    assert job["runtime_metadata"]["candidate_count"] == 0
    assert job["runtime_metadata"]["quality_filter"] == {
        "threshold": 0.85,
        "candidate_count_before_filter": 2,
        "surfaceable_candidate_count": 0,
        "suppressed_candidate_count": 2,
        "production_ready": False,
        "rejection_reason": "no_surfaceable_candidates",
        "fallback_used": False,
    }
    assert job["runtime_metadata"]["production_ready"] is False


def test_generate_for_unit_injects_local_lyric_reference_guidance(tmp_path, monkeypatch) -> None:
    psalm_dir = tmp_path / "Psalm 6"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "Please, God, no more yelling,\n"
        "Break in, God, and break up this fight;\n"
        "Break in, God, and break up this fight;\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))
    adapter = CapturingLyricGenerationAdapter({})
    monkeypatch.setattr("app.services.generation_service.build_adapter", lambda profile: adapter)
    monkeypatch.setattr(
        "app.services.generation_service._locked_inputs", lambda unit, layer: {"hebrew_tokens": []}
    )

    job = generation_service.generate_for_unit(
        "ps019.v001.a",
        layer="lyric",
        style_profile="performative_free",
        candidate_count=1,
        force=True,
    )
    prompt = adapter.requests[0].prompt

    assert job["runtime_metadata"]["candidate_count"] == 1
    assert "Lyric reference guidance:" in prompt
    assert "Lyric reference corpus: sampled 1 lyrics.txt files" in prompt
    assert "Delivery patterns:" in prompt
    assert "Style reference only; never source text." in prompt
    assert "Do not copy completed lyrics" in prompt
    assert (
        "Candidate metadata: every candidate must include delivery_profile and source_anchor"
        in prompt
    )
    assert "Please, God" not in prompt
