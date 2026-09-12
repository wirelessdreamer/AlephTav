"""The committed psalm versification table and its Greek numbering mapping.

``display_verse_offset`` is derived from the vendored English witness, so it is
checked structurally. The Masoretic -> Septuagint mapping cannot be derived from
anything in the repo, so it is asserted boundary by boundary.
"""

from __future__ import annotations

import json

import pytest

from scripts.build_versification import ROOT, greek_numbers

pytestmark = pytest.mark.no_seeded_repo


def _table() -> dict:
    # Read the committed table from the real repo, not the fixture workspace,
    # which holds only a handful of psalms.
    return json.loads((ROOT / "content" / "versification.json").read_text(encoding="utf-8"))


def test_table_covers_the_whole_psalter() -> None:
    psalms = _table()["psalms"]

    assert len(psalms) == 150
    assert psalms["ps001"]["mt"] == 1
    assert psalms["ps150"]["mt"] == 150


def test_every_display_offset_is_a_plausible_superscription_length() -> None:
    psalms = _table()["psalms"]

    offsets = {pid: entry["display_verse_offset"] for pid, entry in psalms.items()}
    assert set(offsets.values()) <= {0, 1, 2}, "an offset outside 0-2 means the derivation broke"

    # A psalm with no superscription, one with a one-verse heading, and one with
    # a long historical heading.
    assert offsets["ps001"] == 0
    assert offsets["ps003"] == 1
    assert offsets["ps051"] == 2


def test_offset_is_mt_verses_minus_english_verses() -> None:
    for entry in _table()["psalms"].values():
        assert entry["display_verse_offset"] == entry["mt_verses"] - entry["english_verses"]


@pytest.mark.parametrize(
    ("mt", "greek"),
    [
        (1, [1]),
        (8, [8]),
        # The Septuagint joins MT 9 and 10 into a single psalm.
        (9, [9]),
        (10, [9]),
        # From here the Greek numbering runs one behind.
        (11, [10]),
        (51, [50]),
        (113, [112]),
        # MT 114 and 115 are joined as Greek 113.
        (114, [113]),
        (115, [113]),
        # MT 116 is split into Greek 114 and 115, which resynchronises the run.
        (116, [114, 115]),
        (117, [116]),
        (146, [145]),
        # MT 147 is split, restoring alignment for the final doxology.
        (147, [146, 147]),
        (148, [148]),
        (150, [150]),
    ],
)
def test_masoretic_to_septuagint_boundaries(mt: int, greek: list[int]) -> None:
    assert greek_numbers(mt) == greek


def test_the_joins_and_splits_balance_across_the_psalter() -> None:
    import collections

    seen: collections.Counter[int] = collections.Counter()
    for mt in range(1, 151):
        seen.update(greek_numbers(mt))

    # No Greek psalm in 1-150 is dropped.
    assert set(seen) == set(range(1, 151))

    # Exactly two Greek psalms are shared by two Masoretic ones: the LXX joins
    # MT 9+10 and MT 114+115.
    assert {n for n, count in seen.items() if count > 1} == {9, 113}

    # And exactly two Masoretic psalms split in two (MT 116, MT 147), so the
    # 150 MT psalms emit 152 Greek numbers overall.
    assert sum(seen.values()) == 152


def test_committed_table_matches_the_mapping() -> None:
    for pid, entry in _table()["psalms"].items():
        assert entry["septuagint"] == greek_numbers(entry["mt"]), pid
        assert entry["vulgate"] == entry["septuagint"], pid


def test_numbers_outside_the_psalter_are_rejected() -> None:
    for bad in (0, 151, -1):
        with pytest.raises(ValueError):
            greek_numbers(bad)
