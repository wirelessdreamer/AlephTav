from __future__ import annotations

from copy import deepcopy

import pytest

from app.core.errors import ValidationError
from app.services.greek_bridge_service import distribution, validate_endpoints

pytestmark = pytest.mark.no_seeded_repo


def evidence() -> tuple[dict, dict, dict]:
    mt = {
        "h1": {"lexeme_id": "H"},
        "h2": {"lexeme_id": "H"},
        "h3": {"lexeme_id": "H"},
        "h4": {"lexeme_id": "H"},
    }
    greek = {"g1": {"lexeme_id": "G"}, "g2": {"lexeme_id": "G"}, "g3": {"lexeme_id": "J"}}
    bridge = {
        "set_id": "bridge-1",
        "mt_snapshot_id": "mt-1",
        "study_snapshot_id": "study-1",
        "groups": [
            {
                "group_id": "many",
                "status": "accepted",
                "observation": "linked",
                "mt_token_ids": ["h1", "h2"],
                "greek_token_ids": ["g1", "g2", "g3"],
            },
            {
                "group_id": "minus",
                "status": "accepted",
                "observation": "hebrew_minus",
                "mt_token_ids": ["h3"],
                "greek_token_ids": [],
            },
            {
                "group_id": "proposal",
                "status": "proposed",
                "mt_token_ids": ["h4"],
                "greek_token_ids": ["g1"],
            },
        ],
    }
    return bridge, mt, greek


def test_distribution_counts_groups_and_multisets_not_cartesian_pairs() -> None:
    bridge, mt, greek = evidence()
    result = distribution(
        bridge,
        mt,
        greek,
        mt_snapshot_id="mt-1",
        study_snapshot_id="study-1",
        source_side="mt",
        lexeme_id="H",
    )
    assert result["alignment_group_count"] == 2
    assert result["distinct_source_tokens"] == 3
    assert result["distinct_opposite_tokens"] == 3
    assert result["coverage"] == {
        "source_lexeme_tokens": 4,
        "accepted_source_lexeme_tokens": 3,
        "unresolved_source_lexeme_tokens": 1,
    }
    assert result["hebrew_minus_groups"] == result["proposed_groups"] == 1
    assert result["outcomes"] == [
        {"opposite_lexeme_multiset": [], "group_count": 1},
        {
            "opposite_lexeme_multiset": [
                {"lexeme_id": "G", "multiplicity": 2},
                {"lexeme_id": "J", "multiplicity": 1},
            ],
            "group_count": 1,
        },
    ]


def test_endpoint_and_accepted_ownership_validation() -> None:
    bridge, mt, greek = evidence()
    mutations = []
    wrong = deepcopy(bridge)
    wrong["mt_snapshot_id"] = "mt-2"
    mutations.append(wrong)
    duplicate = deepcopy(bridge)
    duplicate["groups"][1]["mt_token_ids"] = ["h1"]
    mutations.append(duplicate)
    missing = deepcopy(bridge)
    missing["groups"][0]["greek_token_ids"] = ["nonexistent"]
    mutations.append(missing)
    incomplete = deepcopy(bridge)
    incomplete["aligned"] = True
    mutations.append(incomplete)
    for invalid in mutations:
        with pytest.raises(ValidationError):
            validate_endpoints(
                invalid, mt, greek, mt_snapshot_id="mt-1", study_snapshot_id="study-1"
            )
