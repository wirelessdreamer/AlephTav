from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from app.core.errors import LicensePolicyError
from app.services import greek_analysis_service as analysis
from app.services import greek_lexical_preview_service as lexical
from app.services import greek_preview_service

pytestmark = pytest.mark.no_seeded_repo
UNIT_ID = "lxx.authored.r0001.ps025.v001.a"
TOKEN_ID = "lxx.authored.r0001.ps025.v001.t001"
TEXT_HASH = "a" * 64


def unit(surface="λόγος"):
    return {
        "unit_id": UNIT_ID,
        "source_greek": surface,
        "tokens": [{"token_id": TOKEN_ID, "surface": surface, "gloss": None}],
        "literal_text": "?",
    }


def morph(surface="λόγος", lemma="λόγος", reference="024025001", method="morpheus"):
    return analysis.parse_quantforge(
        f"{reference} N- ----NSM- {surface} {surface} {surface} {lemma} grc {method}",
        package_id="authored.morph",
    )


def test_matches_verse_and_surface_not_word_position_and_preserves_accent_distinctions():
    entries = [
        {"entry_id": "no", "headword": "οὐ", "gloss": "no"},
        {"entry_id": "where", "headword": "οὗ", "gloss": "where"},
    ]
    rows = morph("ἄλλος", "ἄλλος") + morph("οὐ", "οὐ")
    result = lexical.lexical_candidates([unit("οὐ")], entries, rows)[TOKEN_ID]
    assert [entry["entry_id"] for item in result for entry in item["dictionary_entries"]] == ["no"]
    assert result[0]["status"] == "proposed"
    elsewhere = lexical.lexical_candidates([unit("οὐ")], entries, morph("οὐ", "οὐ", "024026001"))[
        TOKEN_ID
    ]
    assert elsewhere[0]["scheme"] == "Inflected form lookup"
    assert elsewhere[0]["features"] == {}  # Never copy another verse's grammar.
    assert elsewhere[0]["dictionary_entries"][0]["entry_id"] == "no"


def test_synthetic_proper_noun_guesses_do_not_become_dictionary_matches():
    entries = [{"entry_id": "word", "headword": "λόγος", "gloss": "word"}]
    candidates = lexical.lexical_candidates([unit()], entries, morph(method="morpheus-proper"))[
        TOKEN_ID
    ]
    assert candidates[0]["scheme"] == "Dictionary headword"
    assert candidates[0]["features"] == {}  # Definition is independent of the synthetic parse.
    assert (
        lexical.lexical_candidates([unit("ἄγνωστος")], entries, morph(method="morpheus-proper"))[
            TOKEN_ID
        ]
        == []
    )


def test_heading_words_use_explicit_dictionary_spelling_variants_without_invented_morphology():
    entries = [
        {
            "entry_id": "name",
            "headword": "Δαυείδ, Δαυίδ, Δαβίδ",
            "gloss": "David",
            "lexical_pos_raw": "N:N-M-P",
        }
    ]
    for spelling in ("Δαυείδ", "Δαυίδ", "Δαβίδ"):
        result = lexical.lexical_candidates([unit(spelling)], entries, morph())[TOKEN_ID]
        assert result[0]["dictionary_entries"][0]["gloss"] == "David"
        assert result[0]["scheme"] == "Dictionary headword"
        assert result[0]["features"] == {}
        assert result[0]["evidence"]["method"] == "dictionary_headword"
    # No broad spelling substitution or accent stripping for direct surface lookup.
    assert lexical.lexical_candidates([unit("Δαυέδ")], entries, morph())[TOKEN_ID] == []
    assert (
        lexical.lexical_candidates(
            [unit("οὗ")],
            [
                {"entry_id": "no", "headword": "οὐ", "gloss": "no"},
            ],
            morph(),
        )[TOKEN_ID]
        == []
    )


def test_surface_lookup_does_not_choose_a_pronoun_sense_for_an_unanalysed_article():
    entries = [{"entry_id": "his", "headword": "τοῦ", "gloss": "his", "lexical_pos_raw": "G:D"}]
    assert lexical.lexical_candidates([unit("Τοῦ")], entries, morph())[TOKEN_ID] == []


def test_dictionary_variants_also_resolve_existing_lemma_candidates():
    entries = [{"entry_id": "name", "headword": "Δαυείδ, Δαυίδ", "gloss": "David"}]
    result = lexical.lexical_candidates([unit("Δαυίδ")], entries, morph("Δαυίδ", "Δαυίδ"))[TOKEN_ID]
    assert result[0]["dictionary_entries"][0]["gloss"] == "David"
    assert result[0]["scheme"] == "MorphGNT"


def test_dictionary_alternatives_and_unresolved_words_are_preserved():
    entries = [
        {"entry_id": "one", "headword": "λόγος", "gloss": "word"},
        {"entry_id": "two", "headword": "λόγος", "gloss": "account"},
    ]
    result = lexical.lexical_candidates([unit()], entries, morph())[TOKEN_ID]
    assert [entry["gloss"] for entry in result[0]["dictionary_entries"]] == ["word", "account"]
    assert lexical.lexical_candidates([unit("ἄγνωστος")], entries, morph())[TOKEN_ID] == []


@pytest.fixture
def enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    shutil.copytree(Path(__file__).resolve().parents[2] / "schemas", tmp_path / "schemas")
    inputs = {
        "tbesg.txt": (
            "G1\tG1\tG1\tλόγος\tlogos\tN\tword\tAn authored definition\n"
            "G2\tG2\tG2\tτόπος\ttopos\tN\tplace\tAuthored place definition"
        ).encode(),
        "step-readme.txt": b"Authored dictionary license fixture",
        "morphology.txt": b"024025001 N- ----NSM- "
        + "λόγος λόγος λόγος λόγος".encode()
        + b" grc morpheus",
        "morph-license.txt": b"Authored morphology license fixture",
        "tipnr.txt": b"Example@Gen.1.1=H9999\tAuthored name fixture",
        "nt/license.txt": b"Authored NT public domain fixture",
        "lsj/README.md": b"Authored LSJ license fixture",
    }
    files = {
        name: (f"https://example.invalid/{name}", hashlib.sha256(raw).hexdigest())
        for name, raw in inputs.items()
    }
    sources = deepcopy(lexical.SOURCES)
    for source, name in zip(
        sources,
        (
            "step-readme.txt",
            "morph-license.txt",
            "step-readme.txt",
            "nt/license.txt",
            "lsj/README.md",
        ),
        strict=True,
    ):
        source["license_text_sha256"] = files[name][1]
    monkeypatch.setattr(lexical, "FILES", files)
    monkeypatch.setattr(lexical, "SOURCES", sources)
    monkeypatch.setattr(lexical, "CORPUS_CATALOG", {"books": []})
    monkeypatch.setattr(
        greek_preview_service, "load_preview", lambda: {"manifest_sha256": TEXT_HASH}
    )
    root, approval = lexical._paths()
    root.mkdir(parents=True)
    for name, raw in inputs.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(raw)
    lexical._parsed.cache_clear()
    report = lexical.enable(reviewer_id="owner.fixture", rationale="Authored local display request")
    yield root, approval, report
    lexical._parsed.cache_clear()


def test_explicit_activation_is_audited_and_supplies_literal_and_hover_data(enabled, tmp_path):
    _, _, report = enabled
    units = [unit()]
    result = lexical.enrich(units, TEXT_HASH)
    assert result["lexical_preview"] is True
    assert units[0]["literal_text"] == "word"
    token = units[0]["tokens"][0]
    assert token["dictionary_entries"][0]["gloss"] == "word"
    assert token["analyses"][0]["lemma"] == "λόγος"
    assert token["analyses"][0]["status"] == "proposed"
    audit = json.loads(next((tmp_path / "content/audit/packages").glob("*.json")).read_text())
    assert audit["audit_id"] == report["audit_id"]
    assert audit["created_by"] == "owner.fixture"
    assert not (tmp_path / "data/raw").exists()


@pytest.mark.parametrize(
    "change", ["source", "name_source", "resolver", "text_revision", "withdrawal", "policy"]
)
def test_warm_cache_cannot_leak_glosses_after_a_change(enabled, monkeypatch, change):
    root, approval, _ = enabled
    assert lexical.enrich([unit()], TEXT_HASH)["lexical_preview"] is True
    text_hash = TEXT_HASH
    if change == "source":
        (root / "tbesg.txt").write_bytes(b"changed")
    elif change == "name_source":
        (root / "tipnr.txt").write_bytes(b"changed")
    elif change == "resolver":
        monkeypatch.setattr(lexical, "_resolver_hash", lambda: "changed")
    elif change == "text_revision":
        text_hash = "b" * 64
    elif change == "withdrawal":
        record = json.loads(approval.read_text())
        record["decision"] = "withdraw"
        approval.write_text(json.dumps(record))
    else:

        def blocked():
            raise LicensePolicyError("revoked")

        monkeypatch.setattr(lexical, "_require_policy", blocked)
    units = [unit()]
    result = lexical.enrich(units, text_hash)
    assert not result.get("lexical_preview")
    assert units[0]["tokens"][0]["gloss"] is None
    assert "dictionary_entries" not in units[0]["tokens"][0]


def test_possible_reading_is_bracketed_in_literal_and_explained_for_hover(enabled):
    units = [unit("τόπαν")]
    units[0]["unit_id"] = "lxx.authored.r0001.ps025.v008.a"
    lexical.enrich(units, TEXT_HASH)
    assert units[0]["source_greek"] == "τόπαν"
    assert units[0]["literal_text"] == "[place?]"
    assert units[0]["tokens"][0]["lookup_status"] == "possible_variant"
    assert "possible reading τόπον" in units[0]["tokens"][0]["analyses"][0]["lookup_note"]


def test_accent_variant_context_is_bracketed_and_not_presented_as_an_exact_match(
    enabled, monkeypatch
):
    entries = [
        {"entry_id": "fixture.that", "headword": "ἵνα", "gloss": "so that", "attribution": {}}
    ]
    index = lexical.LexicalIndex(entries, [])
    monkeypatch.setattr(lexical, "_lookup_index", lambda _: index)
    units = [unit("ἰνα")]
    lexical.enrich(units, TEXT_HASH)
    assert units[0]["literal_text"] == "[so that?]"
    assert units[0]["tokens"][0]["lookup_status"] == "mark_variant"
    assert units[0]["source_greek"] == "ἰνα"


def test_coverage_audit_counts_context_and_review_flags_separately(enabled, tmp_path, monkeypatch):
    source = [
        unit(),
        {
            **unit("τόπαν"),
            "unit_id": "lxx.authored.r0001.ps025.v008.a",
            "ref": "Greek Psalm 25:8",
            "tokens": [
                {
                    "token_id": "lxx.authored.r0001.ps025.v002.t001",
                    "surface": "τόπαν",
                    "gloss": None,
                }
            ],
        },
    ]
    source[0]["ref"] = "Greek Psalm 25:1"
    monkeypatch.setattr(
        greek_preview_service,
        "load_preview",
        lambda: {
            "manifest_sha256": TEXT_HASH,
            "edition_id": "authored",
            "text_revision_id": "r0001",
            "units": deepcopy(source),
        },
    )
    report = lexical.audit_lookups()
    assert report["counts"]["with_dictionary_context"] == 2
    assert report["counts"]["unmatched"] == 0
    assert report["counts"]["possible_variant"] == 1
    saved = json.loads(
        (tmp_path / "reports/greek/lexical_lookup_audit.json").read_text(encoding="utf-8")
    )
    assert saved["review_items"][0]["surface"] == "τόπαν"
    assert len(saved["resolver_sha256"]) == 64
    assert source[1]["source_greek"] == "τόπαν"


def test_policy_change_during_projection_discards_result(enabled, monkeypatch):
    calls = iter(["before", "after"])
    monkeypatch.setattr(lexical.policy, "policy_revision", lambda: next(calls))
    units = [unit()]
    assert "lexical_message" in lexical.enrich(units, TEXT_HASH)
    assert units[0]["tokens"][0]["gloss"] is None
