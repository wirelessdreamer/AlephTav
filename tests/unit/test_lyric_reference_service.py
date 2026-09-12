from __future__ import annotations

from app.services import lyric_reference_service


def test_reference_payload_summarizes_local_lyric_corpus(tmp_path, monkeypatch) -> None:
    psalm_dir = tmp_path / "Psalm 6"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "\n".join(
            [
                "[INTRO - piano]",
                "Please, God, no more yelling,",
                "Help me now?",
                "Break in, God, and break up this fight;",
                "Break in, God, and break up this fight;",
                "My bed is floating on tears.",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))

    payload = lyric_reference_service.build_reference_payload("lyric")

    assert payload["available"] is True
    assert payload["file_count"] == 1
    assert payload["observed_metrics"]["duplicate_line_count"] == 1
    assert payload["observed_metrics"]["direct_address_line_count"] >= 1
    assert payload["observed_metrics"]["petition_opening_line_count"] >= 1
    assert payload["observed_metrics"]["question_line_count"] == 1
    assert any(
        "short" in trait.lower() or "singable" in trait.lower() for trait in payload["style_traits"]
    )
    assert any("3-8 words" in pattern for pattern in payload["delivery_patterns"])
    assert any(
        "Petitions often start with active verbs" in pattern
        for pattern in payload["delivery_patterns"]
    )
    assert "Style reference only; never source text." in payload["usage_policy"]


def test_reference_guidance_is_style_only_and_not_source_text(tmp_path, monkeypatch) -> None:
    psalm_dir = tmp_path / "Psalm 5"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "Listen, God! Please, pay attention!\nEvery morning\nEvery morning\n", encoding="utf-8"
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))

    guidance = lyric_reference_service.reference_guidance("concept")

    assert "Lyric reference corpus: sampled 1 lyrics.txt files" in guidance
    assert "Delivery patterns:" in guidance
    assert "Repetition may become a refrain or pressure echo" in guidance
    assert "Style reference only; never source text." in guidance
    assert "Do not copy completed lyrics" in guidance
    assert "Listen, God" not in guidance


def test_candidate_quality_flags_archaism_performance_leak_and_reference_echo(
    tmp_path, monkeypatch
) -> None:
    psalm_dir = tmp_path / "Psalm 6"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "Break in, God, and break up this fight;\nMy bed is floating on tears.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))

    archaic = lyric_reference_service.evaluate_candidate_quality(
        "Nor standeth in the way of sinners", "lyric"
    )
    performance = lyric_reference_service.evaluate_candidate_quality(
        "[INTRO - piano]\nBreak in, God", "lyric"
    )
    echo = lyric_reference_service.evaluate_candidate_quality(
        "Break in, God, and break up this fight;", "lyric"
    )
    translationese = lyric_reference_service.evaluate_candidate_quality(
        "In your anger me rebuke don't", "concept"
    )
    series_connector = lyric_reference_service.evaluate_candidate_quality(
        "And doesn't stand with sinners", "lyric"
    )

    assert any(issue["code"] == "archaic_diction" for issue in archaic["issues"])
    assert any(issue["code"] == "performance_direction_leak" for issue in performance["issues"])
    assert any(issue["code"] == "lyric_reference_echo" for issue in echo["issues"])
    assert any(issue["code"] == "translationese_syntax" for issue in translationese["issues"])
    assert any(
        issue["code"] == "unsingable_series_connector" for issue in series_connector["issues"]
    )
    assert series_connector["score"] < lyric_reference_service.MIN_SURFACED_PRODUCTION_QUALITY
    assert (
        min(
            archaic["score"],
            performance["score"],
            echo["score"],
            translationese["score"],
            series_connector["score"],
        )
        < 1.0
    )


def test_candidate_quality_flags_near_copy_of_reference_lyrics(tmp_path, monkeypatch) -> None:
    psalm_dir = tmp_path / "Psalm 6"
    psalm_dir.mkdir()
    (psalm_dir / "lyrics.txt").write_text(
        "Break in, God, and break up this fight;\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALEPHTAV_LYRIC_REFERENCE_ROOT", str(tmp_path))

    near_echo = lyric_reference_service.evaluate_candidate_quality(
        "Break in God and break up the fight",
        "lyric",
    )
    distinct = lyric_reference_service.evaluate_candidate_quality(
        "God, tear this pattern open",
        "lyric",
    )

    assert any(issue["code"] == "lyric_reference_near_echo" for issue in near_echo["issues"])
    assert near_echo["score"] < lyric_reference_service.MIN_SURFACED_PRODUCTION_QUALITY
    assert not any(
        issue["code"] in {"lyric_reference_echo", "lyric_reference_near_echo"}
        for issue in distinct["issues"]
    )


def test_candidate_quality_flags_unsmoothed_musical_heading_fragments() -> None:
    phrase_quality = lyric_reference_service.evaluate_candidate_quality("To the flutes", "phrase")
    lyric_quality = lyric_reference_service.evaluate_candidate_quality("To the flutes", "lyric")
    smooth_quality = lyric_reference_service.evaluate_candidate_quality(
        "For the choir director, with flutes",
        "lyric",
    )

    assert not any(
        issue["code"] == "unsmoothed_musical_heading_fragment" for issue in phrase_quality["issues"]
    )
    assert any(
        issue["code"] == "unsmoothed_musical_heading_fragment" for issue in lyric_quality["issues"]
    )
    assert lyric_quality["score"] < lyric_reference_service.MIN_SURFACED_PRODUCTION_QUALITY
    assert smooth_quality["score"] == 1.0


def test_repair_candidate_delivery_fixes_reversible_translation_defects() -> None:
    assert (
        lyric_reference_service.repair_candidate_delivery(
            "Nor standeth in the way of sinners", "lyric"
        )
        == "Doesn't stand in the way of sinners"
    )
    assert (
        lyric_reference_service.repair_candidate_delivery(
            "In your anger me rebuke don't", "concept"
        )
        == "Don't rebuke me in your anger"
    )
    assert (
        lyric_reference_service.repair_candidate_delivery("To the flutes", "lyric") == "With flutes"
    )
    assert (
        lyric_reference_service.repair_candidate_delivery("To the flutes", "phrase")
        == "To the flutes"
    )
