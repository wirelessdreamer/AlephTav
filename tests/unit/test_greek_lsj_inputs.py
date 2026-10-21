from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.services.greek_lexical_lookup_service import LexicalIndex
from app.services.greek_lsj_input_service import (
    beta_headword,
    parse_lsj_spans,
    resolve_lsj_cross_references,
)

pytestmark = pytest.mark.no_seeded_repo


@pytest.mark.parametrize(
    "beta,greek",
    [
        ("lo/gos", "λόγος"),
        ("a)/nqrwpos", "ἄνθρωπος"),
        ("*)/anqrwpos", "Ἄνθρωπος"),
        ("o(1", "ὁ"),
        ("w(=|", "ᾧ"),
        ("a_^", "α"),
        ("a)po-pi/ptw", "ἀπο-πίπτω"),
    ],
)
def test_beta_code_lookup_keys_preserve_breathing_iota_and_case(beta, greek):
    assert beta_headword(beta) == greek


def test_lsj_adapter_uses_english_translation_spans_and_preserves_source_identity():
    text = """<!DOCTYPE TEI.2 SYSTEM "https://example.invalid/must-not-fetch">
      <entryFree id="n1" key="lo/gos"><orth>lo/gos</orth>
      <foreign lang="greek">not a definition</foreign><tr>word</tr><tr>account</tr></entryFree>"""
    entries, counts = parse_lsj_spans(
        text, source_file="fixture.xml", attribution={"license": "CC BY-SA 4.0"}
    )
    assert counts["entries"] == 1
    assert entries[0]["gloss"] == "word / account"
    assert entries[0]["source_key"] == "lo/gos"
    assert entries[0]["source_locator"] == {"file": "fixture.xml", "id": "n1"}
    assert entries[0]["headword"] == "λόγος"


def test_cross_references_resolve_without_inventing_glosses_for_untranslated_entries():
    text = """<entryFree id="n1" key="lo/gos"><tr>word</tr></entryFree>
      <entryFree id="n2" key="le/cis"><xr><ref lang="greek">lo/gos</ref></xr></entryFree>
      <entryFree id="n3" key="a)"><foreign lang="greek">lo/gos</foreign></entryFree>"""
    entries, counts = parse_lsj_spans(text, source_file="fixture.xml", attribution={})
    resolved = resolve_lsj_cross_references(entries)
    assert len(resolved) == 2
    assert resolved[1]["gloss"] == "see λόγος: word"
    assert resolved[1]["cross_reference_entry_ids"] == [resolved[0]["entry_id"]]
    assert counts["without_translation_spans"] == 1


def test_supplemental_lsj_does_not_displace_existing_brief_dictionary_meanings():
    brief = {"entry_id": "brief", "headword": "λόγος", "gloss": "word"}
    full = {
        "entry_id": "full",
        "headword": "λόγος",
        "gloss": "a longer definition",
        "fallback_dictionary": True,
    }
    extra = {
        "entry_id": "extra",
        "headword": "ἀαγής",
        "gloss": "unbroken, hard",
        "fallback_dictionary": True,
    }
    index = LexicalIndex([full, brief, extra], [])
    assert index.lemma("λόγος") == [brief]
    assert index.lemma("ἀαγής") == [extra]


def test_empty_brief_definition_does_not_mask_a_supplemental_meaning():
    blank = {"entry_id": "blank", "headword": "πλάνης", "gloss": ""}
    defined = {
        "entry_id": "full",
        "headword": "πλάνης",
        "gloss": "wanderer",
        "fallback_dictionary": True,
    }
    assert LexicalIndex([blank, defined], []).lemma("πλάνης") == [defined]
    assert LexicalIndex([blank], []).lemma("πλάνης") == []


def test_external_entity_references_are_never_resolved():
    with pytest.raises(ET.ParseError):
        parse_lsj_spans(
            '<entryFree id="n1" key="a)"><tr>&external;</tr></entryFree>',
            source_file="fixture.xml",
            attribution={},
        )
    with pytest.raises(ValueError, match="DTD/entity"):
        parse_lsj_spans(
            '<entryFree id="n1" key="a)"><!ENTITY external SYSTEM "file:///secret"></entryFree>',
            source_file="fixture.xml",
            attribution={},
        )


def test_incomplete_lsj_entry_is_an_accounting_error():
    with pytest.raises(ValueError, match="accounting"):
        parse_lsj_spans(
            '<entryFree id="n1" key="a)"><tr>authored', source_file="fixture.xml", attribution={}
        )
