from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.services import registry_service, source_translation_map_service

pytestmark = pytest.mark.no_seeded_repo


def _token(token_id: str, lemma: str, surface: str, gloss: str) -> dict[str, object]:
    return {
        "token_id": token_id,
        "lemma": lemma,
        "surface": surface,
        "normalized": surface,
        "display_gloss": gloss,
        "word_sense": gloss,
        "referent": None,
        "gloss_parts": gloss.split(),
        "part_of_speech": "noun",
        "syntax_role": None,
        "semantic_role": None,
    }


def _unit(
    unit_id: str,
    ref: str,
    tokens: list[dict[str, object]],
    text: str,
    alignments: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "unit_id": unit_id,
        "psalm_id": "ps001",
        "ref": ref,
        "source_hebrew": "מָשָׁל",
        "source_transliteration": "mashal",
        "tokens": tokens,
        "alignments": alignments,
        "renderings": [
            {
                "rendering_id": f"rnd.{unit_id}.literal.can.0001",
                "layer": "literal",
                "status": "canonical",
                "text": text,
                "target_spans": [
                    {
                        "span_id": f"spn.{unit_id}.literal.0001",
                        "text": text,
                        "token_start": 0,
                        "token_end": 1,
                    }
                ],
                "drift_flags": [],
                "rationale": "fixture",
                "provenance": {"source_ids": ["uxlc"], "generator": "fixture"},
            }
        ],
    }


def test_source_translation_map_exposes_structural_evidence_repetition_and_review_cues(
    monkeypatch,
) -> None:
    first_token = _token("ps001.v001.t001", "אָהַב", "אָהַב", "love")
    divine_token = _token("ps001.v001.t002", "יהוה", "יהוה", "Yahweh")
    first = _unit(
        "ps001.v001.a",
        "Psalm 1:1",
        [first_token, divine_token],
        "Love Yahweh",
        [
            {
                "alignment_id": "aln.ps001.v001.a.literal.0001",
                "layer": "literal",
                "source_token_ids": ["ps001.v001.t001"],
                "target_span_ids": ["spn.ps001.v001.a.literal.0001"],
                "alignment_type": "direct",
                "confidence": 1.0,
                "notes": "Direct lexical correspondence.",
            },
            {
                "alignment_id": "aln.ps001.v001.a.literal.0002",
                "layer": "literal",
                "source_token_ids": ["ps001.v001.t002"],
                "target_span_ids": ["spn.ps001.v001.a.literal.0001"],
                "alignment_type": "conceptual",
                "confidence": 0.9,
                "notes": "Uses a compact conceptual rendering.",
            },
        ],
    )
    second = _unit(
        "ps001.v002.a",
        "Psalm 1:2",
        [_token("ps001.v002.t001", "אָהַב", "אָהַב", "love")],
        "Love the Lord",
        [],
    )
    monkeypatch.setattr(
        registry_service,
        "load_psalm",
        lambda _: {"psalm_id": "ps001", "title": "Psalm 1", "units": [first, second]},
    )

    result = source_translation_map_service.get_source_translation_map("ps001", "literal")

    assert result["summary"]["translated_units"] == 2
    assert result["summary"]["explicitly_mapped_tokens"] == 2
    assert result["units"][0]["tokens"][0]["status"] == "explicit"
    assert result["units"][1]["tokens"][0]["status"] == "lexical_estimate"
    assert any(
        item["kind"] == "structural_turn" for item in result["units"][0]["creative_liberties"]
    )
    repetition = next(item for item in result["repetitions"] if item["lemma"] == "אָהַב")
    assert repetition["preservation"] == "lexically_visible"
    assert repetition["visible_anchor_count"] == 2


def test_source_translation_map_rejects_unknown_layers() -> None:
    with pytest.raises(ValidationError, match="Unknown rendering layer"):
        source_translation_map_service.get_source_translation_map("ps001", "freeform")


def test_source_translation_map_can_target_an_attached_witness(monkeypatch) -> None:
    first = _unit(
        "ps001.v001.a",
        "Psalm 1:1",
        [_token("ps001.v001.t001", "אָהַב", "אָהַב", "love")],
        "Love Yahweh",
        [],
    )
    second = _unit(
        "ps001.v002.a",
        "Psalm 1:2",
        [_token("ps001.v002.t001", "אָהַב", "אָהַב", "love")],
        "Love the Lord",
        [],
    )
    for unit in (first, second):
        unit["witnesses"] = [
            {
                "source_id": "kjv",
                "versionTitle": "King James Version",
                "language": "en",
                "ref": unit["ref"],
                "source_url": "https://example.test/kjv",
                "text": "Love the Lord",
            }
        ]
    monkeypatch.setattr(
        registry_service,
        "load_psalm",
        lambda _: {"psalm_id": "ps001", "title": "Psalm 1", "units": [first, second]},
    )

    result = source_translation_map_service.get_source_translation_map(
        "ps001",
        "literal",
        translation_source="witness",
        witness_source_id="kjv",
    )

    assert result["translation_target"]["label"] == "KJV · King James Version"
    assert result["translation_target"]["read_only"] is True
    assert result["summary"]["explicitly_mapped_tokens"] == 0
    assert result["units"][0]["rendering"]["source_kind"] == "witness"
    assert result["units"][0]["tokens"][0]["status"] == "lexical_estimate"
