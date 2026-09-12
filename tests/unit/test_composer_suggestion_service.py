from __future__ import annotations

from app.services import composer_suggestion_service, registry_service


def _candidate(text: str, confidence: float = 0.9) -> dict[str, object]:
    return {
        "text": text,
        "rationale": "fixture",
        "alignment_hints": [],
        "drift_flags": [],
        "metrics": {"grounding_score": confidence},
        "variation_basis": ["fixture"],
        "preserved_source_images": [{"label": "fixture", "source_id": "uxlc"}],
        "differentiator": "fixture",
        "grounding_confidence": confidence,
        "translation_basis": {
            "basis_type": "hebrew_to_english",
            "source_ids": ["uxlc", "oshb", "macula"],
            "source_language": "he",
            "source_version": "fixture-2026.04",
            "basis_note": "Fixture Hebrew basis",
        },
        "delivery_profile": "source_clear_concept",
        "source_anchor": {
            "anchor_text": "fixture",
            "source_language": "he",
            "source_text": "דָּבָר",
            "basis_note": "Fixture anchor",
        },
    }


def test_composer_prompt_includes_production_lyric_quality_controls(tmp_path, monkeypatch) -> None:
    psalm_dir = tmp_path / "Psalm 5"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "Listen, God! Please, pay attention!\n"
        "Every morning\n"
        "Every morning\n"
        "My tears flood the bed.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))

    unit = registry_service.load_unit("ps051.v001.a")
    style = composer_suggestion_service._style_profile("doubter_lament")
    prompt = composer_suggestion_service._prompt(
        unit,
        "lyric",
        [
            {
                "chunk_id": "chunk.ps051.v001.a.1",
                "start": 0,
                "end": 3,
                "text": "Be gracious to me, O God",
                "source_text": "chaneni elohim",
                "confidence": 0.82,
                "confidence_reasons": ["fixture"],
            }
        ],
        3,
        style,
    )

    assert "completed Psalm lyric drafts" in prompt
    assert "ordinary direct speech" in prompt
    assert "Do not copy completed lyrics" in prompt
    assert "4/4_direct" in prompt
    assert "6/8_lament" in prompt
    assert "avoid pseudo-biblical diction" in prompt.lower()
    assert "Lyric reference corpus: sampled 1 lyrics.txt files" in prompt
    assert "Delivery patterns:" in prompt
    assert "Style reference only; never source text." in prompt
    assert "Listen, God" not in prompt


def test_composer_prompt_includes_full_line_delivery_context() -> None:
    unit = registry_service.load_unit("ps001.v001.a")
    style = composer_suggestion_service._style_profile("doubter_lament")
    prompt = composer_suggestion_service._prompt(
        unit,
        "lyric",
        [
            {
                "chunk_id": "chunk.ps001.v001.a.1",
                "start": 0,
                "end": 1,
                "text": "For the choir director",
                "source_text": "לַמְנַצֵּחַ",
                "confidence": 0.82,
                "confidence_reasons": ["fixture"],
            },
            {
                "chunk_id": "chunk.ps001.v001.a.2",
                "start": 2,
                "end": 3,
                "text": "To the flutes",
                "source_text": "אֶל־הַנְּחִילֹות",
                "confidence": 0.82,
                "confidence_reasons": ["fixture"],
            },
            {
                "chunk_id": "chunk.ps001.v001.a.3",
                "start": 4,
                "end": 6,
                "text": "A psalm of David",
                "source_text": "מִזְמֹור לְדָוִד",
                "confidence": 0.82,
                "confidence_reasons": ["fixture"],
            },
        ],
        3,
        style,
    )

    assert "line_delivery_context" in prompt
    assert "avoid isolated, unsingable fragments" in prompt
    assert "source_anchor.source_text must contain the Greek source span" in prompt
    assert "not a Hebrew span, English gloss, or existing English witness" in prompt
    assert "For the choir director | To the flutes | A psalm of David" in prompt
    assert "previous_chunk_seed" in prompt
    assert "next_chunk_seed" in prompt
    assert "For the choir director" in prompt
    assert "A psalm of David" in prompt
    assert "Do not import meaning from neighboring chunks" in prompt


def test_composer_response_suppresses_low_quality_when_clean_alternative_exists() -> None:
    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps006.v002.a",
            "stage": "lyric",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [
                        _candidate("Behold, unto thee", 0.99),
                        _candidate("And doesn't stand with sinners", 0.82),
                        _candidate("Doesn't stand with sinners", 0.84),
                        _candidate("[INTRO - piano]\nBreak in God", 0.98),
                    ],
                }
            ],
        },
        "ps006.v002.a",
        "lyric",
        3,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "do not rebuke me",
                "source_text": "",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    quality_filter = response["chunks"][0]["quality_filter"]
    assert quality_filter["candidate_count_before_filter"] == 4
    assert quality_filter["surfaceable_candidate_count"] == 1
    assert quality_filter["suppressed_candidate_count"] == 3
    assert quality_filter["production_ready"] is True
    assert quality_filter["rejection_reason"] is None
    assert quality_filter["fallback_used"] is False
    candidates = response["chunks"][0]["candidates"]
    assert [candidate["text"] for candidate in candidates] == ["Doesn't stand with sinners"]
    assert candidates[0]["metrics"]["production_quality_score"] == 1.0


def test_composer_response_suppresses_basis_blur_when_clean_alternative_exists() -> None:
    blurred = _candidate("The heavens announce", 0.99)
    blurred["translation_basis"] = {
        "basis_type": "septuagint_greek_to_english",
        "source_ids": ["uxlc"],
        "source_language": "he",
        "source_version": "fixture-2026.04",
        "basis_note": "Bad fixture: Greek basis label with Hebrew metadata",
    }
    blurred["source_anchor"] = {
        "anchor_text": "heavens",
        "source_language": "he",
        "source_text": "הַשָּׁמַיִם",
        "basis_note": "Bad fixture: Hebrew anchor on Greek basis",
    }
    clean = _candidate("The heavens declare", 0.84)

    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps019.v001.a",
            "stage": "phrase",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [blurred, clean],
                }
            ],
        },
        "ps019.v001.a",
        "phrase",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "heaven source phrase",
                "source_text": "הַשָּׁמַיִם מְסַפְּרִים",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    quality_filter = response["chunks"][0]["quality_filter"]
    assert quality_filter["candidate_count_before_filter"] == 2
    assert quality_filter["surfaceable_candidate_count"] == 1
    assert quality_filter["suppressed_candidate_count"] == 1
    assert quality_filter["production_ready"] is True
    assert quality_filter["rejection_reason"] is None
    assert quality_filter["fallback_used"] is False
    candidates = response["chunks"][0]["candidates"]
    assert [candidate["text"] for candidate in candidates] == ["The heavens declare"]
    assert candidates[0]["translation_basis"]["basis_type"] == "hebrew_to_english"
    assert candidates[0]["source_anchor"]["source_language"] == "he"


def test_composer_response_suppresses_lxx_candidate_with_non_greek_source_anchor() -> None:
    blurred = _candidate("The heavens speak", 0.99)
    blurred["translation_basis"] = {
        "basis_type": "septuagint_greek_to_english",
        "source_ids": ["lxx", "macula"],
        "source_language": "grc",
        "source_version": "fixture-2026.04",
        "basis_note": "Fixture Septuagint basis",
    }
    blurred["source_anchor"] = {
        "anchor_text": "heavens",
        "source_language": "grc",
        "source_text": "הַשָּׁמַיִם",
        "basis_note": "Bad fixture: Greek label with Hebrew source text",
    }
    clean = _candidate("The heavens announce", 0.84)
    clean["translation_basis"] = {
        "basis_type": "septuagint_greek_to_english",
        "source_ids": ["lxx", "macula"],
        "source_language": "grc",
        "source_version": "fixture-2026.04",
        "basis_note": "Fixture Septuagint basis",
    }
    clean["source_anchor"] = {
        "anchor_text": "heavens",
        "source_language": "grc",
        "source_text": "Οἱ οὐρανοὶ",
        "basis_note": "Fixture Greek anchor",
    }

    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps019.v001.a",
            "stage": "phrase",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [blurred, clean],
                }
            ],
        },
        "ps019.v001.a",
        "phrase",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "heaven source phrase",
                "source_text": "הַשָּׁמַיִם מְסַפְּרִים",
                "septuagint_greek_text": "Οἱ οὐρανοὶ διηγοῦνται",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    quality_filter = response["chunks"][0]["quality_filter"]
    assert quality_filter["candidate_count_before_filter"] == 2
    assert quality_filter["surfaceable_candidate_count"] == 1
    assert quality_filter["suppressed_candidate_count"] == 1
    candidates = response["chunks"][0]["candidates"]
    assert [candidate["text"] for candidate in candidates] == ["The heavens announce"]
    assert candidates[0]["source_anchor"]["source_text"] == "Οἱ οὐρανοὶ"


def test_composer_response_repairs_reversible_delivery_defects_before_scoring() -> None:
    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps006.v002.a",
            "stage": "lyric",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [
                        _candidate("Nor standeth in the way of sinners", 0.99),
                        _candidate("In your anger me rebuke don't", 0.98),
                    ],
                }
            ],
        },
        "ps006.v002.a",
        "lyric",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "do not rebuke me",
                "source_text": "",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    quality_filter = response["chunks"][0]["quality_filter"]
    assert quality_filter["surfaceable_candidate_count"] == 2
    candidates = response["chunks"][0]["candidates"]
    assert [candidate["text"] for candidate in candidates] == [
        "Doesn't stand in the way of sinners",
        "Don't rebuke me in your anger",
    ]
    assert all(candidate["metrics"]["production_quality_score"] == 1.0 for candidate in candidates)
    assert all(not candidate["drift_flags"] for candidate in candidates)


def test_composer_response_repairs_unsmoothed_musical_heading_fragments() -> None:
    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps005.v001.a",
            "stage": "lyric",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [
                        _candidate("To the flutes", 0.99),
                        _candidate("For the choir director, with flutes", 0.88),
                    ],
                }
            ],
        },
        "ps005.v001.a",
        "lyric",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "flute accompaniment",
                "source_text": "",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    quality_filter = response["chunks"][0]["quality_filter"]
    assert quality_filter["candidate_count_before_filter"] == 2
    assert quality_filter["surfaceable_candidate_count"] == 2
    assert quality_filter["suppressed_candidate_count"] == 0
    candidates = response["chunks"][0]["candidates"]
    assert [candidate["text"] for candidate in candidates] == [
        "With flutes",
        "For the choir director, with flutes",
    ]
    assert all(
        "unsmoothed_musical_heading_fragment" not in " ".join(candidate["drift_flags"])
        for candidate in candidates
    )


def test_composer_response_suppresses_near_copied_reference_lyrics(tmp_path, monkeypatch) -> None:
    psalm_dir = tmp_path / "Psalm 6"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "Break in, God, and break up this fight;\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))

    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps006.v002.a",
            "stage": "lyric",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [
                        _candidate("Break in God and break up the fight", 0.99),
                        _candidate("God, tear this pattern open", 0.84),
                    ],
                }
            ],
        },
        "ps006.v002.a",
        "lyric",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "save me",
                "source_text": "",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    quality_filter = response["chunks"][0]["quality_filter"]
    assert quality_filter["surfaceable_candidate_count"] == 1
    assert quality_filter["suppressed_candidate_count"] == 1
    candidates = response["chunks"][0]["candidates"]
    assert [candidate["text"] for candidate in candidates] == ["God, tear this pattern open"]
    assert all(
        "lyric_reference_near_echo" not in " ".join(candidate["drift_flags"])
        for candidate in candidates
    )


def test_composer_response_withholds_chunk_when_every_option_fails_quality() -> None:
    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps006.v002.a",
            "stage": "lyric",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [
                        _candidate("Behold, unto thee", 0.99),
                        _candidate("[INTRO - piano]\nBreak in, God", 0.98),
                    ],
                }
            ],
        },
        "ps006.v002.a",
        "lyric",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "do not rebuke me",
                "source_text": "",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    assert response["unit_id"] == "ps006.v002.a"
    assert response["stage"] == "lyric"
    assert response["available"] is False
    assert response["status"] == "rejected"
    assert response["chunks"][0]["chunk_id"] == "chunk.1"
    assert response["chunks"][0]["quality_filter"] == {
        "threshold": 0.85,
        "candidate_count_before_filter": 2,
        "surfaceable_candidate_count": 0,
        "suppressed_candidate_count": 2,
        "production_ready": False,
        "rejection_reason": "no_surfaceable_candidates",
        "fallback_used": False,
        "seed_match_used": False,
    }
    assert response["chunks"][0]["candidates"] == []


def test_composer_response_does_not_surface_low_quality_seed_match() -> None:
    response = composer_suggestion_service._normalize_response(
        {
            "unit_id": "ps006.v002.a",
            "stage": "lyric",
            "chunks": [
                {
                    "chunk_id": "chunk.1",
                    "candidates": [_candidate("Behold, to you", 0.99)],
                }
            ],
        },
        "ps006.v002.a",
        "lyric",
        2,
        [
            {
                "chunk_id": "chunk.1",
                "start": 0,
                "end": 3,
                "text": "Behold, to you",
                "source_text": "",
                "confidence": 0.8,
                "confidence_reasons": [],
            }
        ],
    )

    assert response["available"] is False
    assert response["status"] == "rejected"
    assert response["chunks"][0]["quality_filter"] == {
        "threshold": 0.85,
        "candidate_count_before_filter": 0,
        "surfaceable_candidate_count": 0,
        "suppressed_candidate_count": 0,
        "production_ready": False,
        "rejection_reason": "seed_match_failed_quality",
        "fallback_used": False,
        "seed_match_used": False,
    }
    assert response["chunks"][0]["candidates"] == []
