from __future__ import annotations

import json

import pytest

from app.services import swete_package_service as swete
from app.services.greek_package_intake_service import validate_greek_units

pytestmark = pytest.mark.no_seeded_repo

TEXT = "1:1\tΜΑΚΑΡΙΟΣ ἀνὴρ ὃς οὐκ, δικαιοσύνης·\n151:1\tΜικρὸς ἤμην.\n"
WORDS = (
    "psalm\tverse\tposition\tword\tleaf\tpage\tline\tstrip\n"
    "1\t1\t1\tΜΑΚΑΡΙΟΣ\t231\t213\t2\t0231_00.png\n"
    "1\t1\t2\tἀνὴρ\t231\t213\t2\t0231_00.png\n"
    "1\t1\t3\tὃς\t231\t213\t2\t0231_00.png\n"
    "1\t1\t4\tοὐκ\t231\t213\t2\t0231_00.png\n"
    "1\t1\t6\tδικαιοσύνης\t231\t213\t2\t0231_00.png\n"
    "151\t1\t1\tΜικρὸς\t433\t415\t1\t0433_00.png\n"
    "151\t1\t2\tἤμην\t433\t415\t1\t0433_00.png\n"
)
SPANS = (
    json.dumps(
        {
            "psalm": 1,
            "verse": "1",
            "position": 6,
            "word": "δικαιοσύνης",
            "fragments": [
                {"text": "δικαιο-", "leaf": 231, "page": "213", "line": 2, "strip": "a.png"},
                {"text": "σύνης", "leaf": 231, "page": "213", "line": 3, "strip": "b.png"},
            ],
        },
        ensure_ascii=False,
    )
    + "\n"
)


def exports(**overrides: str) -> dict[str, bytes]:
    files = {"text": TEXT, "words": WORDS, "spans": SPANS, **overrides}
    return {name: value.encode("utf-8") for name, value in files.items()}


@pytest.mark.parametrize(
    ("mt", "lxx"),
    [
        ((8, 3), (8, 3)),
        ((9, 21), (9, 21)),
        ((10, 1), (9, 22)),
        ((25, 2), (24, 2)),
        ((114, 8), (113, 8)),
        ((115, 1), (113, 9)),
        ((116, 9), (114, 9)),
        ((116, 10), (115, 1)),
        ((117, 1), (116, 1)),
        ((147, 11), (146, 11)),
        ((147, 12), (147, 1)),
        ((150, 6), (150, 6)),
    ],
)
def test_standard_hebrew_greek_numbering(mt, lxx):
    assert swete.lxx_reference(*mt) == lxx


def test_units_renumber_words_and_keep_export_locators():
    units = swete.build_units(exports(), "r0001")
    validate_greek_units(units)
    first = units[0]
    assert first["unit_id"] == "lxx.swete1896.r0001.ps001.v001.a"
    assert [t["position"] for t in first["tokens"]] == [1, 2, 3, 4, 5]
    joined = first["tokens"][4]
    assert joined["token_id"] == "lxx.swete1896.r0001.ps001.v001.t005"
    assert first["source_greek"][joined["text_span"]["start"] : joined["text_span"]["end"]] == (
        "δικαιοσύνης"
    )
    # The export's own position (which counts the comma) stays the locator.
    assert joined["source_locator"]["locator"] == "1:1#6"
    assert [f["line"] for f in joined["source_locator"]["fragments"]] == [2, 3]
    assert first["tokens"][0]["source_locator"]["fragments"] == [
        {"leaf": "231", "page": "213", "line": "2", "strip": "0231_00.png"}
    ]


def test_word_absent_from_verse_text_is_refused():
    with pytest.raises(ValueError, match="not found"):
        swete.build_units(exports(text=TEXT.replace("ἀνὴρ", "ἀνήρ")), "r0001")


def test_map_is_proposed_and_reports_what_the_rule_cannot_place():
    units = swete.build_units(exports(), "r0001")
    mt_units = [
        {"unit_id": "ps001.v001.a", "ref": "Psalm 1:1"},
        {"unit_id": "ps001.v002.a", "ref": "Psalm 1:2"},
    ]
    verse_map, gaps = swete.build_map(units, mt_units, "r0001")
    assert {record["status"] for record in verse_map["records"]} == {"proposed"}
    by_relation = {record["relation"]: record for record in verse_map["records"]}
    assert by_relation["equivalent"]["sources"][0]["unit_id"] == "ps001.v001.a"
    assert by_relation["equivalent"]["targets"][0]["unit_id"] == units[0]["unit_id"]
    assert by_relation["greek_only"]["sources"] == []
    assert gaps == {"unmapped_mt": ["MT 1:2 -> Swete 1:2"], "untargeted_greek": []}
