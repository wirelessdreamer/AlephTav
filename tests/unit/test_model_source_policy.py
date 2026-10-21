from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from app.core.errors import LicensePolicyError
from app.services import codex_translation_service as codex
from app.services import composer_suggestion_service as composer
from app.services import generation_service as generation
from app.services import generation_source_policy_service as policy
from app.services import registry_service, source_basis_service

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def source_unit(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    project = registry_service.project_template()
    project["source_manifests"] = registry_service.manifest_template()
    registry_service.write_json(tmp_path / "content/project.json", project)
    unit = {
        "unit_id": "ps001.v001.a",
        "psalm_id": "ps001",
        "ref": "Psalm 1:1",
        "source_hebrew": "אַשְׁרֵי",
        "tokens": [
            {
                "token_id": "ps001.v001.t001",
                "surface": "אַשְׁרֵי",
                "lemma": "אשרי",
                "strong": "H835",
                "morph_code": "N",
                "display_gloss": "fortunate",
                "syntax_role": "predicate",
                "greek": "μακάριος",
                "greek_strong": "G3107",
                "same_psalm_occurrence_refs": ["Psalm 1:2"],
                "compiler_features": {"english_parts": ["fortunate"]},
            }
        ],
        "witnesses": [
            {
                "source_id": "lxx",
                "versionTitle": "Historical MACULA hint",
                "language": "grc",
                "ref": "Psalm 1:1",
                "text": "μακάριος ἀνήρ",
            }
        ],
        "renderings": [],
        "comparison_assessments": [],
    }
    monkeypatch.setattr(registry_service, "load_unit", lambda _: copy.deepcopy(unit))
    monkeypatch.setattr(
        registry_service,
        "load_psalm",
        lambda _: {"title": "Authored", "units": [copy.deepcopy(unit)]},
    )
    monkeypatch.setattr(codex, "get_guidance", lambda *args: "")
    monkeypatch.setattr("app.services.translation_context_service.history", lambda *args: [])
    monkeypatch.setattr(codex, "cached_suggestions", lambda *args: None)
    return unit


def test_generation_projection_removes_denied_greek_preserves_hebrew_enrichment(source_unit):
    before = copy.deepcopy(source_unit)
    payload = generation._locked_inputs(source_unit, "gloss")
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "μακάριος" not in encoded and "G3107" not in encoded
    token = payload["hebrew_tokens"][0]
    assert token["surface"] == "אַשְׁרֵי" and token["lemma"] == "אשרי"
    assert token["strong"] == "H835" and token["morph_code"] == "N"
    projected = policy.model_unit(source_unit)
    assert projected["tokens"][0]["display_gloss"] == "fortunate"
    assert projected["tokens"][0]["syntax_role"] == "predicate"
    assert source_unit == before


def test_composer_prompt_and_source_context_exclude_denied_greek(source_unit):
    chunks = [
        {
            "chunk_id": "c1",
            "start": 0,
            "end": 0,
            "text": "fortunate",
            "confidence": 1,
            "confidence_reasons": [],
        }
    ]
    enriched = composer._enrich_chunk_source_context(source_unit, chunks)
    assert enriched[0]["septuagint_greek_text"] == ""
    prompt = composer._prompt(source_unit, "phrase", enriched, 1, {"style_profile_id": "authored"})
    assert "μακάριος" not in prompt and "G3107" not in prompt
    assert "אַשְׁרֵי" in prompt and "fortunate" in prompt and "H835" in prompt


def test_codex_all_prompt_paths_strip_current_and_elsewhere_greek(source_unit, monkeypatch):
    monkeypatch.setattr(
        codex.comparisons,
        "occurrence_context",
        lambda *args: {
            "matches": [{"display_gloss": "fortunate", "greek": "κρυπτός"}],
            "english_text": "",
        },
    )
    prompts = [
        codex.build_translation_prompt(source_unit["unit_id"], "gloss"),
        codex.build_passage_prompt("ps001", [source_unit["unit_id"]], "gloss"),
        codex.build_suggestion_prompt(
            source_unit["unit_id"], [source_unit["tokens"][0]["token_id"]], "gloss"
        ),
    ]
    for prompt in prompts:
        assert "μακάριος" not in prompt and "κρυπτός" not in prompt and "G3107" not in prompt
        assert "אַשְׁרֵי" in prompt and "אשרי" in prompt


def greek_candidate():
    return {
        "translation_basis": {
            "basis_type": "septuagint_greek_to_english",
            "source_language": "grc",
            "source_ids": ["lxx"],
        },
        "source_anchor": {"source_language": "grc", "source_text": "μακάριος"},
    }


def test_new_greek_outputs_and_cached_codex_apply_are_blocked_without_rewriting_history(
    source_unit, monkeypatch
):
    candidate = greek_candidate()
    before = copy.deepcopy(candidate)
    # Historical script/quality checks remain deterministic and independent of permission.
    assert source_basis_service.greek_source_anchor_problem("μακάριος") is None
    with pytest.raises(LicensePolicyError, match="source|approval"):
        source_basis_service.require_generation_basis_available(candidate)
    assert candidate == before
    run = {
        "run_id": "historical",
        "status": codex.RUN_COMPLETED,
        "kind": codex.KIND_TRANSLATION,
        "unit_id": source_unit["unit_id"],
        "payload": {"candidates": [candidate]},
    }
    monkeypatch.setattr(codex, "get_run", lambda _: run)
    with pytest.raises(LicensePolicyError, match="source|approval"):
        codex.save_run_candidates("historical")
    assert codex._septuagint_basis_errors({"candidates": [candidate]})


@pytest.mark.parametrize("language", ["greek", "Greek", "ell"])
def test_alternate_greek_language_labels_do_not_bypass_generation_gate(source_unit, language):
    candidate = {
        "translation_basis": {
            "basis_type": "hebrew_to_english",
            "source_ids": ["uxlc"],
            "source_language": "he",
        },
        "source_anchor": {"source_language": language, "source_text": "μακάριος"},
    }
    with pytest.raises(source_basis_service.GreekGenerationUnavailableError):
        source_basis_service.require_generation_basis_available(candidate)


def test_composer_actual_response_boundary_drops_greek_candidates(source_unit, monkeypatch):
    candidate = {**greek_candidate(), "text": "authored candidate"}
    monkeypatch.setattr(
        composer,
        "build_adapter",
        lambda _: SimpleNamespace(
            generate_json=lambda _: SimpleNamespace(
                payload={
                    "unit_id": source_unit["unit_id"],
                    "stage": "phrase",
                    "chunks": [{"chunk_id": "c1", "candidates": [candidate]}],
                }
            )
        ),
    )
    result = composer.suggest_for_unit(
        source_unit["unit_id"],
        "phrase",
        [{"chunk_id": "c1", "start": 0, "end": 0, "text": "fortunate", "confidence": 1}],
        candidate_count=1,
    )
    assert result["blocked_source_candidate_count"] == 1
    assert not result["available"]
