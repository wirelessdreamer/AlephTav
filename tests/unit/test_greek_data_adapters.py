from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest
from jsonschema import ValidationError

from app.services import greek_analysis_service as analysis
from app.services import greek_dictionary_service as dictionary
from app.services import greek_package_intake_service as intake

pytestmark = pytest.mark.no_seeded_repo

# These are authored format fixtures, not licensed upstream dictionary extracts.
ATTRIBUTION = {
    "source_id": "authored-fixture",
    "package_revision": "r0001",
    "license": "CC0",
    "license_text_sha256": "1" * 64,
    "required_attribution": "Authored test fixture",
}
HEADER = "eStrong\tdStrong\tuStrong\tGreek\tTransliteration\tMorph\tGloss\tDefinition"


def row(
    identifier: str,
    *,
    dstrong: str | None = None,
    ustrong: str | None = None,
    headword: str = "λόγος",
    body: str = "<b>Authored</b> definition",
) -> str:
    return "\t".join(
        [
            identifier,
            dstrong or identifier + " =",
            ustrong or identifier,
            headword,
            "fixture",
            "G:N",
            "authored gloss",
            body,
        ]
    )


def parse_step(text: str) -> dictionary.AdapterResult:
    return dictionary.parse_step_dictionary(
        text, package_id="fixture.r0001", source_file="fixture.tsv", attribution=ATTRIBUTION
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("G3107", "G3107"),
        ("3107", "G3107"),
        ("G0001", "G1"),
        ("G6908", "G6908"),
        ("G21502", "G21502"),
        ("G2264G", "G2264G"),
        ("G2264H", "G2264H"),
        ("G2264I", "G2264I"),
        ("H0175", "H175"),
    ],
)
def test_external_identifiers_preserve_scheme_suffix_and_extended_range(value, expected):
    assert dictionary.normalize_external_id(value, default_prefix="G") == expected


@pytest.mark.parametrize("value", ["", "G", "G0", "G1/G10", "G-1", "G1<script>", "xG1"])
def test_malformed_external_identifier_is_rejected(value):
    with pytest.raises(ValueError):
        dictionary.normalize_external_id(value)


def test_step_bom_preamble_repeated_estrong_and_line_accounting():
    text = (
        "\ufeffAuthored documentary preamble\n\n"
        + HEADER
        + "\n"
        + "\n".join(
            row("G2264", dstrong=f"G2264{suffix} =", ustrong=f"G2264{suffix}") for suffix in "GHI"
        )
    )
    result = parse_step(text).require_valid()
    assert len(result.entries) == 3
    assert len({entry["entry_id"] for entry in result.entries}) == 3
    assert [entry["identifiers"][0]["value"] for entry in result.entries] == ["G2264"] * 3
    assert sum(value for key, value in result.accounting.items() if key != "input_lines") == 6
    assert result.accounting["input_lines"] == 6
    assert result.entries[0]["attribution"] == ATTRIBUTION
    assert result.entries[0]["lexical_pos_raw"] == "G:N"


def test_step_malformed_rows_are_accounted_without_silently_dropping_them():
    result = parse_step(HEADER + "\n" + row("G1") + "\nG2\tbroken\n" + row("G3"))
    assert result.accounting["data_rows"] == 2
    assert result.accounting["invalid_rows"] == 1
    with pytest.raises(ValueError, match="invalid rows"):
        result.require_valid()


def test_step_separator_and_unkeyed_cross_reference_are_accounted_without_inventing_a_headword():
    text = HEADER + "\n====\n" + row("G1") + "\n" + row("G2", headword="")
    result = parse_step(text).require_valid()
    assert len(result.entries) == 1
    assert result.accounting["unkeyed_rows"] == 1
    assert result.findings[0]["raw_fields"][0] == "G2"
    assert sum(v for k, v in result.accounting.items() if k != "input_lines") == 4


def test_tflsj_both_files_and_empty_extra_rejection():
    result = dictionary.parse_tflsj(
        HEADER + "\n" + row("G1"),
        HEADER + "\n" + row("G6908"),
        package_id="fixture.r0001",
        attribution=ATTRIBUTION,
    ).require_valid()
    assert {entry["dictionary"] for entry in result.entries} == {"tflsj_main", "tflsj_extra"}
    with pytest.raises(ValueError):
        dictionary.parse_tflsj(
            HEADER + "\n" + row("G1"), "", package_id="fixture", attribution=ATTRIBUTION
        ).require_valid()


def test_typed_combination_is_not_an_equivalent_identifier_alias():
    entry = parse_step(
        row(
            "G1508",
            dstrong="G1508 = a Combination of",
            ustrong="G1487G (G1487G+G3361)",
            headword="εἰ μή",
        )
    ).entries[0]
    components = [
        item for item in entry["identifiers"] if item["relation"] == "combination_component"
    ]
    assert [item["value"] for item in components] == ["G1487G", "G3361"]
    assert all(item["scheme"] == "uStrong" for item in components)


def test_hostile_markup_is_safe_tree_data_and_findings():
    tree, _, findings = dictionary.safe_presentation(
        '<script>alert(1)</script><b onclick="bad()">bold</b>'
        '<a href="javascript:bad()">bad</a><a href="https://example.org">safe</a>'
        '<img src="bad" onerror="bad()"><unknown>text</unknown>',
        entry_id="entry",
        baseline="unknown",
    )

    def walk(node):
        yield node
        for child in node.get("children", []):
            yield from walk(child)

    nodes = list(walk(tree))
    assert {node["type"] for node in nodes} <= {"root", "text", "strong", "link"}
    assert [node["href"] for node in nodes if node["type"] == "link"] == ["https://example.org"]
    assert all("onclick" not in node and "onerror" not in node for node in nodes)
    assert {finding["code"] for finding in findings} >= {
        "unsafe_link",
        "event_attribute_removed",
        "unsupported_markup",
    }


@pytest.mark.parametrize(
    "identifier,reference,label,target",
    [
        ("G0020", "Psa.45.15", "Ps 44(45):15", "lxx.swete1896.r0001.ps044.v016.a"),
        ("G0082", "Psa.51.6", "Ps 50 (51):6", "lxx.swete1896.r0001.ps050.v008.a"),
    ],
)
def test_citation_baseline_and_title_offsets_are_explicit(identifier, reference, label, target):
    entry = parse_step(row(identifier, body=f"<ref='{reference}'>{label}</ref>")).entries[0]
    citation = entry["citations"][0]
    assert citation["original_label"] == label
    assert citation["baseline"] == "english_kjv"
    assert citation["target"] is None
    mappings = [
        {
            "baseline": "english_kjv",
            "machine_reference": reference,
            "edition_id": "swete1896",
            "text_revision_id": "r0001",
            "target": target,
        }
    ]
    resolved = dictionary.resolve_citation(
        citation, mappings, edition_id="swete1896", text_revision_id="r0001"
    )
    assert resolved["target"] == target
    assert (
        dictionary.resolve_citation(
            {**citation, "baseline": "unknown"},
            mappings,
            edition_id="swete1896",
            text_revision_id="r0001",
        )["target"]
        is None
    )


def test_namespaced_tei_and_entries_without_g_number():
    text = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
      <entry n="λόγος|G3056"><form><orth>λόγος</orth></form>
      <sense><def>Authored word</def><ref osisRef="Ps.1.1">Ps 1:1</ref></sense></entry>
      <entry xml:id="fixture-no-strong"><form><orth>ἄδοξος</orth></form></entry>
    </body></text></TEI>"""
    result = dictionary.parse_abbott_smith(
        text, package_id="fixture", source_file="fixture.xml", attribution=ATTRIBUTION
    ).require_valid()
    assert len(result.entries) == 2
    assert result.entries[0]["identifiers"][0]["value"] == "G3056"
    assert result.entries[1]["identifiers"] == []
    assert result.entries[0]["citations"][0]["machine_reference"] == "Ps.1.1"


@pytest.mark.parametrize(
    "declaration",
    [
        '<!DOCTYPE x SYSTEM "https://example.org/remote">',
        '<!DOCTYPE x [<!ENTITY x SYSTEM "file:///secrets">]>',
        '<!ENTITY x "bad">',
    ],
)
def test_tei_refuses_all_dtd_and_entity_declarations(declaration):
    with pytest.raises(ValueError, match="forbidden"):
        dictionary.parse_abbott_smith(
            declaration + "<TEI/>",
            package_id="fixture",
            source_file="fixture.xml",
            attribution=ATTRIBUTION,
        )


def test_unicode_normalization_preserves_source_distinctions_and_finds_confusables():
    original = "ὁδῷ Σςσ ᾿ ῃ"
    nfd = unicodedata.normalize("NFD", original)
    assert analysis.normalize_greek(original) == analysis.normalize_greek(nfd)
    assert analysis.normalize_greek(analysis.normalize_greek(nfd)) == analysis.normalize_greek(nfd)
    assert analysis.normalize_greek("Σςσ") == "σσσ"
    assert analysis.normalize_greek("ῃ", mark_insensitive=True) != analysis.normalize_greek(
        "η", mark_insensitive=True
    )
    assert analysis.normalize_greek("ἀλλ᾿") != analysis.normalize_greek("ἀλλ'")
    assert analysis.normalize_greek("ἀλλ᾿", normalize_elision=True) == analysis.normalize_greek(
        "ἀλλ'", normalize_elision=True
    )
    assert [finding["character"] for finding in analysis.unicode_findings("λόγοs А")] == ["s", "А"]


def unit(words: list[str], psalm: int = 1, verse: int = 1) -> dict:
    unit_id = f"lxx.swete1896.r0001.ps{psalm:03d}.v{verse:03d}.a"
    text = " ".join(words)
    tokens = []
    start = 0
    for position, word in enumerate(words, 1):
        tokens.append(
            {
                "token_id": unit_id.rsplit(".", 1)[0] + f".t{position:03d}",
                "position": position,
                "surface": word,
                "normalized": unicodedata.normalize("NFC", word),
                "text_span": {"start": start, "end": start + len(word)},
                "source_locator": {
                    "file": "authored.txt",
                    "locator": str(position),
                    "fragments": [{"page": "1", "line": 1}],
                },
            }
        )
        start += len(word) + 1
    return {
        "schema_version": "1.0",
        "unit_id": unit_id,
        "corpus": "lxx",
        "edition_id": "swete1896",
        "text_revision_id": "r0001",
        "psalm_id": f"ps{psalm:03d}",
        "ref": f"Psalms {psalm}:{verse}",
        "source_greek": text,
        "tokens": tokens,
    }


def test_quantforge_raw_errors_and_synthetic_guess_stay_proposed():
    rows = analysis.parse_quantforge(
        "024001001 N- ----DSM- ὁδῷ ὁδῷ ὁδῷ ὁδός grc morpheus\n"
        "024001001 NP -------- Σιών Σιών σιών Σιών grc morpheus-proper",
        package_id="fixture",
    )
    source = unit(["Σιών", "ὁδῷ", "ἀναντιστοίχητος"])
    result = analysis.propose_analyses(
        [source],
        rows,
        verse_map={"024001001": [source["unit_id"]]},
        analysis_set_id="analysis.fixture",
    )
    annotations = result["annotations"]
    assert annotations[0]["analyses"][0]["synthetic"] is True
    masculine = annotations[1]["analyses"][0]
    assert masculine["features"]["gender"] == "masculine"
    assert masculine["status"] == "proposed"
    assert annotations[1]["selected_analysis_id"] is None
    assert annotations[2]["status"] == "unresolved"
    assert result["coverage"] == {
        "total_tokens": 3,
        "proposed_tokens": 2,
        "unresolved_tokens": 1,
        "reviewed_tokens": 0,
    }
    assert all(
        candidate["identifiers"] == [] for item in annotations for candidate in item["analyses"]
    )


def test_verse_surface_split_join_and_ambiguity_never_ordinal_zip():
    rows = analysis.parse_quantforge(
        "024001001 C- -------- καὶ καὶ καὶ καί grc morpheus\n"
        "024001001 C- -------- καὶ καὶ καὶ καί grc morpheus\n"
        "024001001 N- ----NSM- αβ αβ αβ αβ grc morpheus",
        package_id="fixture",
    )
    source = unit(["α", "β", "καὶ"])
    result = analysis.propose_analyses(
        [source], rows, verse_map={"024001001": [source["unit_id"]]}, analysis_set_id="fixture"
    )
    assert result["annotations"][0]["analyses"][0]["lemma"] == "αβ"
    assert result["annotations"][2]["ambiguous"] is True
    assert len(result["annotations"][2]["analyses"]) == 2
    unmapped = analysis.propose_analyses([source], rows, verse_map={}, analysis_set_id="fixture")
    assert unmapped["coverage"]["unresolved_tokens"] == 3
    assert len(unmapped["unmatched_source_row_ids"]) == 3


def test_morphgnt_unknown_features_are_retained():
    parsing = analysis.parse_morphgnt("ZZ", "-Z------")
    assert parsing["raw_tag"] == "-Z------"
    assert parsing["features"]["tense"] is None
    assert {item["field"] for item in parsing["unknowns"]} == {"part_of_speech", "tense"}
    with pytest.raises(ValueError, match="nine fields"):
        analysis.parse_quantforge("024001001 N- -------- x", package_id="fixture")


def test_expression_and_crasis_physical_cardinality_and_opt_in_expansion():
    occurrences = [
        {
            "occurrence_id": "except",
            "unit_id": "verse1",
            "token_ids": ["ei", "me"],
            "identifiers": [{"scheme": "Strong", "value": "G1508"}],
            "component_identifiers": [{"scheme": "Strong", "value": "G1487"}],
        },
        {
            "occurrence_id": "crasis",
            "unit_id": "verse1",
            "token_ids": ["kago"],
            "identifiers": [{"scheme": "Strong", "value": "G2504"}],
            "component_identifiers": [{"scheme": "Strong", "value": "G2532"}],
        },
    ]
    expression = analysis.expression_matches(occurrences, scheme="Strong", value="G1508")
    assert (
        expression["total_matches"],
        expression["total_tokens"],
        expression["total_verses"],
    ) == (1, 2, 1)
    crasis = analysis.expression_matches(occurrences, scheme="Strong", value="G2504")
    assert (crasis["total_matches"], crasis["total_tokens"]) == (1, 1)
    assert (
        analysis.expression_matches(occurrences, scheme="Strong", value="G2532")["total_matches"]
        == 0
    )
    assert (
        analysis.expression_matches(
            occurrences, scheme="Strong", value="G2532", expand_components=True
        )["total_tokens"]
        == 1
    )


def package(root: Path, source: dict | None = None) -> Path:
    source = source or unit(["Λόγος", "λόγος"])
    root.mkdir()
    raw = intake.canonical_bytes(source)
    path = root / "psalms" / "ps001" / (source["unit_id"] + ".json")
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    license_text = b"Authored offline fixture license: CC0.\n"
    (root / "LICENSE.txt").write_bytes(license_text)
    manifest = {
        "schema_version": "1.0",
        "package_id": "authored-greek",
        "source_id": "fixture",
        "package_revision": "r0001",
        "kind": "source_text",
        "dependencies": [],
        "review_status": "pending",
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": intake._sha256(raw),
                "size_bytes": len(raw),
            },
            {
                "path": "LICENSE.txt",
                "sha256": intake._sha256(license_text),
                "size_bytes": len(license_text),
            },
        ],
        "provenance": {
            "upstream_url": "https://example.org/authored",
            "upstream_revision": "fixture",
            "license": "CC0",
            "license_text_sha256": intake._sha256(license_text),
            "attribution": "Authored tests",
        },
    }
    (root / "package.json").write_bytes(intake.canonical_bytes(manifest))
    return root


def test_intake_dry_run_zero_writes_and_staging_idempotence(tmp_path):
    original = package(tmp_path / "input")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    inspection = intake.inspect_package(original, require_full_psalter=False)
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert inspection["dry_run"]["token_count"] == 2
    assert inspection["dry_run"]["activation"] == "not_requested"
    first = intake.stage_package(original, tmp_path / "staging", require_full_psalter=False)
    second = intake.stage_package(original, tmp_path / "staging", require_full_psalter=False)
    assert first["changed"] is True
    assert second["changed"] is False
    assert (
        json.loads((Path(first["path"]) / "package.json").read_text())["review_status"] == "pending"
    )
    with pytest.raises(ValueError, match="Psalm coverage"):
        intake.inspect_package(original)


def test_intake_checksum_revision_reuse_and_unaccounted_files(tmp_path):
    original = package(tmp_path / "input")
    intake.stage_package(original, tmp_path / "staging", require_full_psalter=False)
    altered = package(tmp_path / "altered", unit(["ἕτερος"]))
    with pytest.raises(ValueError, match="cannot be reused"):
        intake.stage_package(altered, tmp_path / "staging", require_full_psalter=False)
    (original / "unaccounted.txt").write_text("unaccounted")
    with pytest.raises(ValueError, match="Unaccounted"):
        intake.inspect_package(original, require_full_psalter=False)
    (original / "unaccounted.txt").unlink()
    next((original / "psalms").rglob("*.json")).write_text("tampered")
    with pytest.raises(ValueError, match="Checksum"):
        intake.inspect_package(original, require_full_psalter=False)


@pytest.mark.parametrize("bad_path", ["../escape", "C:/escape", "/escape", "a\\b", "a/../b"])
def test_package_lock_paths_cannot_escape(tmp_path, bad_path):
    with pytest.raises(ValueError):
        intake._relative_file(tmp_path, bad_path)


def test_source_span_letter_accounting_and_swete_edition_absence():
    source = unit(["λόγος"])
    assert intake.validate_greek_units([source])["token_count"] == 1
    source["tokens"][0]["text_span"]["end"] -= 1
    with pytest.raises(ValueError, match="surface"):
        intake.validate_greek_units([source])
    source = unit(["λόγος"])
    source["tokens"] = []
    with pytest.raises(ValueError, match="not accounted"):
        intake.validate_greek_units([source])
    with pytest.raises(ValueError, match="edition-absent"):
        intake.validate_greek_units([unit(["λόγος"], 135, 23)])


def test_versification_preserves_many_to_many_titles_ps151_alias_and_split_witnesses():
    sources = [unit(["α", "β"], 137, 6), unit(["γ"], 151, 1)]
    first, last = [source["unit_id"] for source in sources]
    mapping = {
        "schema_version": "1.0",
        "edition_id": "swete1896",
        "text_revision_id": "r0001",
        "records": [
            {
                "mapping_id": "title-overlap",
                "relation": "title",
                "status": "proposed",
                "sources": [
                    {"baseline": "mt", "reference": "Ps.138.title"},
                    {"baseline": "mt", "reference": "Ps.138.1"},
                ],
                "targets": [{"baseline": "swete1896", "reference": "Ps.137.6", "unit_id": first}],
                "provenance": "Authored fixture",
            },
            {
                "mapping_id": "151",
                "relation": "greek_only",
                "status": "proposed",
                "sources": [],
                "targets": [
                    {
                        "baseline": "swete1896",
                        "reference": "PSA 151",
                        "alias": "PS2",
                        "unit_id": last,
                    }
                ],
                "provenance": "Authored fixture",
            },
            {
                "mapping_id": "absent",
                "relation": "edition_absent",
                "status": "proposed",
                "sources": [{"baseline": "generic_lxx", "reference": "Ps.135.23"}],
                "targets": [],
                "provenance": "Authored fixture",
            },
        ],
        "witness_spans": [
            {
                "unit_id": first,
                "start": 0,
                "end": 1,
                "witness": "S",
                "provenance": "Authored fixture",
            },
            {
                "unit_id": first,
                "start": 2,
                "end": 3,
                "witness": "B",
                "provenance": "Authored fixture",
            },
        ],
    }
    assert intake.validate_versification_map(mapping, sources) == {
        "record_count": 3,
        "witness_span_count": 2,
    }
    assert len(mapping["records"][0]["sources"]) == 2
    mapping["records"][0]["targets"][0]["unit_id"] = first.replace("r0001", "r0002")
    with pytest.raises(ValueError, match="revision"):
        intake.validate_versification_map(mapping, sources)


def test_generated_dictionary_and_analysis_payloads_satisfy_strict_contracts():
    from app.services.foundation_contract_service import validate_contract

    result = parse_step(HEADER + "\n" + row("G1"))
    files = dictionary.normalized_dictionary_files(result)
    assert files == dictionary.normalized_dictionary_files(result)
    entry = json.loads(files["entries.jsonl"])
    validate_contract("greek_dictionary_entry.schema.json", entry)
    entry["presentation"] = {"type": "script", "text": "bad()"}
    with pytest.raises(ValidationError, match="not valid"):
        validate_contract("greek_dictionary_entry.schema.json", entry)
    source = unit(["λόγος"])
    rows = analysis.parse_quantforge(
        "024001001 N- ----NSM- λόγος λόγος λόγος λόγος grc morpheus", package_id="fixture"
    )
    proposed = analysis.propose_analyses(
        [source], rows, verse_map={"024001001": [source["unit_id"]]}, analysis_set_id="fixture"
    )
    validate_contract("greek_analysis_set.schema.json", proposed)
    proposed["annotations"][0]["selected_analysis_id"] = "invented-acceptance"
    with pytest.raises(ValidationError, match="not of type 'null'"):
        validate_contract("greek_analysis_set.schema.json", proposed)


def test_homographs_crosswalk_schemes_and_explicit_lexeme_replacements():
    lexemes = {
        "schema_version": "1.0",
        "lexeme_set_id": "lexemes.r0002",
        "language": "grc",
        "lexemes": [
            {
                "lexeme_id": "lex.person",
                "headword": "Ἡρῴδης",
                "distinction": "person one",
                "status": "proposed",
                "replaces": ["lex.legacy"],
            },
            {
                "lexeme_id": "lex.person2",
                "headword": "Ἡρῴδης",
                "distinction": "person two",
                "status": "proposed",
                "replaces": ["lex.legacy"],
            },
        ],
    }
    crosswalks = {
        "schema_version": "1.0",
        "crosswalk_set_id": "crosswalks.r0002",
        "lexeme_set_id": "lexemes.r0002",
        "assignments": [
            {
                "assignment_id": "assignment.1",
                "lexeme_id": "lex.person",
                "scheme": "eStrong",
                "value": "G2264",
                "relation": "entry",
                "source_entry_id": "entry.1",
                "status": "proposed",
            },
            {
                "assignment_id": "assignment.2",
                "lexeme_id": "lex.person2",
                "scheme": "eStrong",
                "value": "G2264",
                "relation": "entry",
                "source_entry_id": "entry.2",
                "status": "proposed",
            },
        ],
    }
    assert analysis.validate_lexical_graph(
        lexemes,
        crosswalks,
        source_entry_ids={"entry.1", "entry.2"},
        previous_lexeme_ids={"lex.legacy"},
    ) == {"lexemes": 2, "assignments": 2}
    with pytest.raises(ValueError, match="predecessor"):
        analysis.validate_lexical_graph(
            lexemes, crosswalks, source_entry_ids={"entry.1", "entry.2"}
        )
    with pytest.raises(ValueError, match="missing"):
        analysis.validate_lexical_graph(
            lexemes, crosswalks, source_entry_ids={"entry.1"}, previous_lexeme_ids={"lex.legacy"}
        )


def test_install_gate_cannot_turn_pending_or_self_declared_approval_into_permission(tmp_path):
    original = package(tmp_path / "input")
    with pytest.raises(ValueError, match="review is pending"):
        intake.install_staged_greek_package(
            original, created_by="test", rationale="authored test", require_full_psalter=False
        )
    path = original / "package.json"
    manifest = json.loads(path.read_text())
    manifest["review_status"] = "approved"
    path.write_bytes(intake.canonical_bytes(manifest))
    from app.services.source_capability_service import SourceUnavailableError

    with pytest.raises(SourceUnavailableError):
        intake.install_staged_greek_package(
            original, created_by="test", rationale="authored test", require_full_psalter=False
        )


def test_failed_staging_copy_preserves_existing_candidate(tmp_path, monkeypatch):
    original = package(tmp_path / "input")
    staged = intake.stage_package(original, tmp_path / "staging", require_full_psalter=False)
    first_manifest = (Path(staged["path"]) / "package.json").read_bytes()
    second = package(tmp_path / "second")
    manifest_path = second / "package.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["package_revision"] = "r0002"
    manifest_path.write_bytes(intake.canonical_bytes(manifest))

    def disk_full(*args, **kwargs):
        raise OSError("authored disk-full injection")

    monkeypatch.setattr(intake.shutil, "copyfile", disk_full)
    with pytest.raises(OSError, match="disk-full"):
        intake.stage_package(second, tmp_path / "staging", require_full_psalter=False)
    assert first_manifest == (Path(staged["path"]) / "package.json").read_bytes()
    assert not (tmp_path / "staging" / "authored-greek" / "r0002").exists()
    assert not list((tmp_path / "staging" / "authored-greek").glob(".candidate-*"))


def test_dictionary_candidate_lock_and_full_attribution_closure(tmp_path):
    root = tmp_path / "dictionary"
    root.mkdir()
    license_bytes = b"Authored dictionary fixture license: CC0.\n"
    attribution = {**ATTRIBUTION, "license_text_sha256": intake._sha256(license_bytes)}
    parsed = dictionary.parse_step_dictionary(
        row("G6908"),
        package_id="fixture.r0001",
        source_file="authored.tsv",
        attribution=attribution,
    )
    files = {**dictionary.normalized_dictionary_files(parsed), "LICENSE.txt": license_bytes}
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    manifest = {
        "schema_version": "1.0",
        "package_id": "fixture.r0001",
        "source_id": "authored-fixture",
        "package_revision": "r0001",
        "kind": "dictionary",
        "dependencies": [],
        "review_status": "pending",
        "files": [
            {"path": name, "sha256": intake._sha256(raw), "size_bytes": len(raw)}
            for name, raw in files.items()
        ],
        "provenance": {
            "upstream_url": "https://example.org/authored",
            "upstream_revision": "fixture",
            "license": "CC0",
            "license_text_sha256": intake._sha256(license_bytes),
            "attribution": "Authored fixture",
        },
    }
    (root / "package.json").write_bytes(intake.canonical_bytes(manifest))
    inspection = intake.inspect_package(root)
    assert inspection["dry_run"]["dictionary_entry_count"] == 1
    manifest["provenance"]["license_text_sha256"] = "0" * 64
    (root / "package.json").write_bytes(intake.canonical_bytes(manifest))
    with pytest.raises(ValueError, match="attribution"):
        intake.inspect_package(root)


def test_staging_refuses_canonical_and_raw_destinations(tmp_path):
    from app.core.config import get_settings

    source = package(tmp_path / "input")
    for destination in (get_settings().content_dir / "staging", get_settings().raw_dir / "staging"):
        assert not destination.exists()
        with pytest.raises(ValueError, match="separate"):
            intake.stage_package(source, destination, require_full_psalter=False)
        assert not destination.exists()


def test_crasis_has_typed_component_relationships_without_equivalent_aliases():
    entry = parse_step(
        row(
            "G2504",
            dstrong="G2504 = a Combination of",
            ustrong="G1473 (G2532+G1473)",
            headword="κἀγώ",
        )
    ).entries[0]
    assert [
        item["value"] for item in entry["identifiers"] if item["relation"] == "crasis_component"
    ] == ["G2532", "G1473"]


def test_hebrew_identifier_is_a_typed_cross_reference():
    entry = parse_step(row("G0002", dstrong="G0002 = the Greek of", ustrong="H0175")).entries[0]
    assert entry["identifiers"][-1]["scheme"] == "uStrong"
    assert entry["identifiers"][-1]["value"] == "H175"
    assert entry["identifiers"][-1]["relation"] == "hebrew_cross_reference"


def test_combining_marks_cannot_be_dropped_from_token_spans():
    source = unit(["α"])
    source["source_greek"] += "\u0313"
    with pytest.raises(ValueError, match="not accounted"):
        intake.validate_greek_units([source])
