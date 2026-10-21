from __future__ import annotations

import pytest

from app.services.greek_analysis_service import parse_quantforge
from app.services.greek_dictionary_service import parse_tipnr_names
from app.services.greek_lexical_lookup_service import LexicalIndex, tonal_key

pytestmark = pytest.mark.no_seeded_repo


def entry(headword, gloss="authored meaning", **extra):
    return {"entry_id": headword, "headword": headword, "gloss": gloss, **extra}


def word(surface):
    return {"token_id": "lxx.authored.r0001.ps025.v001.t001", "surface": surface}


def test_stress_variants_do_not_erase_breathing_or_iota_distinctions():
    assert tonal_key("μή") == tonal_key("μὴ")
    assert tonal_key("οὐ") != tonal_key("οὗ")
    assert tonal_key("ῃ") != tonal_key("η")


def test_unmarked_form_context_is_opt_in_and_explicitly_needs_review():
    index = LexicalIndex([entry("ἵνα", "so that")], [])
    token = word("ἰνα")
    assert index.fallback(token) == []
    result = index.fallback(token, allow_mark_variants=True)
    assert result[0]["lookup_status"] == "mark_variant"
    assert result[0]["features"] == {}
    assert result[0]["dictionary_entries"][0]["gloss"] == "so that"
    assert "not a source correction" in result[0]["lookup_note"]
    assert token["surface"] == "ἰνα"


def test_unmarked_suggestions_preserve_alternatives_and_never_drop_iota_or_change_letters():
    rows = parse_quantforge(
        "024001001 A- ----GSM- ἑνός ἑνός ἑνός εἷς grc morpheus\n"
        "024001002 N- ----NSN- ἔνος ἔνος ἔνος ἔνος grc morpheus",
        package_id="fixture",
    )
    index = LexicalIndex([entry("εἷς", "one"), entry("ἔνος", "year"), entry("ᾠδή", "song")], rows)
    result = index.fallback(word("ενος"), allow_mark_variants=True)
    assert {item["lemma"] for item in result} == {"εἷς", "ἔνος"}
    assert index.fallback(word("ὠδή"), allow_mark_variants=True) == []
    assert index.fallback(word("λόγοξ"), allow_mark_variants=True) == []
    assert (
        LexicalIndex([entry("οὐ", "no")], []).fallback(word("οὗ"), allow_mark_variants=True) == []
    )


def test_only_leading_dictionary_citation_forms_become_lemma_aliases():
    original = entry(
        "ἀπολλύω",
        raw_fields=[
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "<b>ἀπ-όλλυμι and ἀπολλύω</b> An authored definition. "
            "<b>μισέω</b> is a later quotation.",
        ],
    )
    index = LexicalIndex([original], [])
    assert index.lemma("ἀπόλλυμι") == [original]
    assert index.lemma("μισέω") == []


def test_a_heading_article_can_use_an_attested_form_without_borrowing_grammar():
    rows = parse_quantforge(
        "024001001 RA ----GSM- τοῦ τοῦ τοῦ ὁ grc morpheus", package_id="fixture"
    )
    index = LexicalIndex(
        [entry("ὁ", "article"), entry("τοῦ", "possessive", lexical_pos_raw="G:D")], rows
    )
    result = index.fallback(word("Τοῦ"))
    assert [e["headword"] for e in result[0]["dictionary_entries"]] == ["ὁ"]
    assert result[0]["features"] == {}
    assert result[0]["scheme"] == "Inflected form lookup"
    assert "grammar in this verse is unresolved" in result[0]["lookup_note"]


def test_all_lexical_alternatives_for_an_attested_form_are_retained():
    rows = parse_quantforge(
        "024001001 N- ----NSM- λόγος λόγος λόγος λόγος grc morpheus\n"
        "024001002 V- 3PAI-S-- λόγος λόγος λόγος λέγω grc morpheus",
        package_id="fixture",
    )
    result = LexicalIndex([entry("λόγος"), entry("λέγω")], rows).fallback(word("λόγος"))
    assert {item["lemma"] for item in result} == {"λόγος", "λέγω"}
    assert all(not item["features"] for item in result)


@pytest.mark.parametrize(
    "surface,headword",
    [
        ("παρ’", "παρά"),
        ("ἐκέκραξα", "κράζω"),
        ("εὐηρέστησα", "εὐαρεστέω"),
        ("ζωήν", "ζωή"),
        ("χερουβείμ", "χερουβίμ"),
    ],
)
def test_context_aids_for_elisions_and_irregular_forms(surface, headword):
    rows = parse_quantforge(
        "024001001 N- ----ASF- ζωὴν ζωὴν ζωὴν ζωή grc morpheus", package_id="fixture"
    )
    result = LexicalIndex([entry(headword)], rows).fallback(word(surface))
    assert result[0]["dictionary_entries"][0]["headword"] == headword
    assert result[0]["status"] == "proposed"


def test_compound_verbs_keep_the_compound_dictionary_meaning():
    index = LexicalIndex(
        [
            entry("ἐσθίω", "eat"),
            entry("συνεσθίω", "eat with"),
            entry("ἐξαίρω", "expel"),
            entry("ἐξέρπω", "creep forth"),
        ],
        [],
    )
    assert index.fallback(word("συνήσθιον"))[0]["dictionary_entries"][0]["gloss"] == "eat with"
    assert index.fallback(word("ἐξῆρψεν"))[0]["dictionary_entries"][0]["gloss"] == "creep forth"


@pytest.mark.parametrize(
    "surface,name,wrong",
    [
        ("Βηρσάβεε", "Bathsheba", "Beersheba"),
        ("Αἰθιοπία", "Cush", "Egypt"),
        ("Σηὼν", "Sihon", "Zion"),
    ],
)
def test_name_links_do_not_conflate_similar_names(surface, name, wrong):
    index = LexicalIndex(
        [entry(name, name_record="fixture.one"), entry(wrong, name_record="fixture.two")], []
    )
    result = index.fallback(word(surface))
    assert result[0]["dictionary_entries"][0]["headword"] == name
    assert result[0]["features"] == {}
    assert "Proposed identification" in result[0]["lookup_note"]


def test_possible_reading_remains_explicit_and_does_not_replace_source_text():
    token = word("τόπαν")
    result = LexicalIndex([entry("τόπος", "place")], []).fallback(token)
    assert token["surface"] == "τόπαν"
    assert result[0]["lookup_status"] == "possible_variant"
    assert "Printed τόπαν; possible reading τόπον" in result[0]["lookup_note"]


def test_tipnr_names_preserve_homonyms_and_exclude_biographies():
    text = (
        "Example@Gen.1.1=H9999\tAuthored context\n"
        "@Article= Generated biography must never become a gloss.\n"
        "Example@Exo.1.1=H9998\tAnother individual\n"
        "– Group\tExample@Exo.1.1\tH9998\tExampleites =ESV; Examplites =KJV\n"
    )
    entries = parse_tipnr_names(text, attribution={"required_attribution": "Authored fixture"})
    assert len([e for e in entries if e["headword"] == "Example"]) == 2
    assert len({e["entry_id"] for e in entries}) == len(entries)
    assert {e["gloss"] for e in entries} == {"Example", "Exampleites", "Examplites"}
    assert all("biography" not in e["gloss"] for e in entries)
