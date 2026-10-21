from __future__ import annotations

import hashlib
import json

import pytest

from app.services import greek_lexical_preview_service as lexical
from app.services.greek_analysis_service import parse_quantforge
from app.services.greek_lexical_lookup_service import LexicalIndex

pytestmark = pytest.mark.no_seeded_repo


def test_non_psalm_book_uses_its_own_reference_without_inventing_a_psalm():
    row = parse_quantforge(
        "001050001 N- ----NSM- λόγος λόγος λόγος λόγος grc morpheus",
        package_id="authored.genesis",
        book_code=1,
    )[0]
    assert row["book_code"] == 1
    assert row["chapter"] == 50
    assert "psalm" not in row
    with pytest.raises(ValueError, match="reference"):
        parse_quantforge(
            "001001001 N- ----NSM- λόγος λόγος λόγος λόγος grc morpheus",
            package_id="authored.psalms",
        )


def test_upstream_split_lemma_is_flagged_and_original_field_is_retained():
    row = parse_quantforge(
        "022004004 N- ----GSM- ἀνοίκτου ἀνοίκτου ἀνοίκτου ἀνο ͂ίκτης grc morpheus",
        package_id="authored.3macc",
        book_code=22,
    )[0]
    assert row["raw_lemma"] == "ἀνο ͂ίκτης"
    assert row["lemma"] == "ἀνο͂ίκτης"
    assert row["findings"] == ["lemma_whitespace"]
    assert row["surface"] == "ἀνοίκτου"


def test_chapter_zero_material_is_preserved_in_its_source_book():
    row = parse_quantforge(
        "017000001 N- ----NSM- λόγος λόγος λόγος λόγος grc morpheus",
        package_id="authored.esther",
        book_code=17,
    )[0]
    assert row["reference"] == "017000001"
    assert row["chapter"] == 0


def test_another_book_supplies_form_context_without_copying_its_verse_grammar():
    rows = parse_quantforge(
        "001001001 N- ----ASF- φωνὴν φωνὴν φωνὴν φωνή grc morpheus",
        package_id="authored.genesis",
        book_code=1,
    )
    token_id = "lxx.authored.r0001.ps025.v001.t001"
    result = lexical.lexical_candidates(
        [
            {
                "unit_id": "lxx.authored.r0001.ps025.v001.a",
                "tokens": [{"token_id": token_id, "surface": "φωνήν"}],
            }
        ],
        [{"entry_id": "authored.voice", "headword": "φωνή", "gloss": "voice"}],
        rows,
    )[token_id]
    assert result[0]["features"] == {}
    assert result[0]["dictionary_entries"][0]["gloss"] == "voice"
    assert result[0]["evidence"]["source_row_ids"] == ["authored.genesis:row:1"]


@pytest.mark.parametrize(
    "surface,word,lemma",
    [
        ("ἐπ’,", "ἐπ", "ἐπί"),
        ("μεθ’", "μεθ", "μετά"),
        ("καθ’", "καθ", "κατά"),
        ("ἐφ’", "ἐφ", "ἐπί"),
    ],
)
def test_elision_uses_printed_apostrophe_even_when_upstream_word_column_omits_it(
    surface,
    word,
    lemma,
):
    entry = {"entry_id": "authored", "headword": lemma, "gloss": "authored gloss"}
    result = LexicalIndex([entry], []).fallback(
        {"token_id": "authored.genesis.token", "surface": surface, "lookup_word": word}
    )
    assert result[0]["lemma"] == lemma
    assert result[0]["features"] == {}


def test_corpus_audit_counts_every_book_and_retains_unmatched_words(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    entries = [{"entry_id": "fixture", "headword": "λόγος", "gloss": "word"}]
    root, approval = lexical._paths()
    root.mkdir(parents=True)
    approval.parent.mkdir(parents=True)
    books = []
    files = {}
    for code, word in [(1, "λόγος"), (55, "ἀλύτως")]:
        name = f"corpus/{code:03}-fixture.txt"
        raw = f"{code:03}001001 N- ----NSM- {word} {word} {word} {word} grc morpheus"
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(raw, encoding="utf-8")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        books.append(
            {
                "book_code": code,
                "filename": path.name,
                "name": str(code),
                "sha256": sha,
                "tokens": 1,
            }
        )
        files[name] = ("https://example.invalid/" + name, sha)
    monkeypatch.setattr(lexical, "FILES", files)
    monkeypatch.setattr(lexical, "CORPUS_CATALOG", {"books": books})
    monkeypatch.setattr(lexical, "_require_policy", lambda: None)
    monkeypatch.setattr(lexical.policy, "policy_revision", lambda: "fixture")
    monkeypatch.setattr(lexical, "_parsed", lambda _: ({"entries": entries}, []))
    approval.write_text(
        json.dumps(
            {
                "decision": "approve",
                "scope": "local_display_preview",
                "role": "owner",
                "sources": lexical.SOURCES,
                "resolver_sha256": lexical._resolver_hash(),
                "files": {name: {"url": url, "sha256": sha} for name, (url, sha) in files.items()},
            }
        )
    )
    result = lexical.audit_corpus_lookups()
    assert result["book_count"] == 2
    assert result["counts"]["total_tokens"] == 2
    assert result["counts"]["with_dictionary_context"] == 1
    assert result["counts"]["unmatched"] == 1
    report = json.loads(
        (tmp_path / "reports/greek/corpus_lexical_lookup_audit.json").read_text(encoding="utf-8")
    )
    assert report["books"][1]["book_code"] == 55
    assert report["unmatched_forms"][0]["word"] == "ἀλύτως"
    assert report["unmatched_forms"][0]["references"][0]["reference"] == "055001001"


def test_pinned_corpus_catalog_accounts_for_all_55_books():
    books = lexical.CORPUS_CATALOG["books"]
    assert [b["book_code"] for b in books] == list(range(1, 56))
    assert sum(b["tokens"] for b in books) == 564842
    assert all(len(b["sha256"]) == 64 for b in books)


def test_psalm_source_reading_suggestions_are_not_global_spelling_corrections():
    entry = {"entry_id": "authored.place", "headword": "τόπος", "gloss": "place"}
    index = LexicalIndex([entry], [])
    token = {"token_id": "authored", "surface": "τόπαν", "source_reference": "001001001"}
    assert index.fallback(token) == []
    token["source_reference"] = "024025008"
    assert index.fallback(token)[0]["lookup_status"] == "possible_variant"


def test_supplemental_dictionary_does_not_hide_a_recorded_source_reading_warning():
    token_id = "lxx.authored.r0001.ps025.v008.t001"
    rows = parse_quantforge(
        "024025008 N- ----ASM- τόπαν τόπαν τόπαν τόπαν grc morpheus", package_id="fixture"
    )
    entries = [
        {"entry_id": "place", "headword": "τόπος", "gloss": "place"},
        {
            "entry_id": "other",
            "headword": "τόπαν",
            "gloss": "authored other sense",
            "fallback_dictionary": True,
        },
    ]
    result = lexical.lexical_candidates(
        [
            {
                "unit_id": "lxx.authored.r0001.ps025.v008.a",
                "tokens": [{"token_id": token_id, "surface": "τόπαν"}],
            }
        ],
        entries,
        rows,
    )[token_id]
    assert result[0]["lookup_status"] == "possible_variant"
    assert result[0]["dictionary_entries"][0]["gloss"] == "place"
