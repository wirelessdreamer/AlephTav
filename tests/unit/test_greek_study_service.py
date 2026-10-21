from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.errors import ValidationError
from app.services.greek_study_service import ConcordanceQuery, StaleStudyError, StudyView

pytestmark = pytest.mark.no_seeded_repo


def view(count: int = 1003) -> StudyView:
    tokens = [
        {
            "token_id": f"token-{i:04d}",
            "unit_id": f"unit-{i // 5}",
            "psalm": i // 500 + 1,
            "verse": i // 5,
            "position": i % 5,
            "surface": "λόγος",
        }
        for i in range(count)
    ]
    analyses = [
        {
            "token_id": token["token_id"],
            "analysis_id": f"a-{i}",
            "lexeme_id": "word",
            "lemma": "λόγος",
            "status": "proposed",
            "identifiers": [{"scheme": "strong", "value": "G1"}],
        }
        for i, token in enumerate(tokens)
    ]
    # A competing candidate must not create an extra physical occurrence.
    analyses.append({**analyses[0], "analysis_id": "competing"})
    return StudyView(
        {"study_snapshot_id": "snapshot-1"},
        {
            "tokens": tokens,
            "analyses": analyses,
            "expressions": [
                {
                    "occurrence_id": "expression-1",
                    "token_ids": [tokens[0]["token_id"], tokens[1]["token_id"]],
                    "surface": "εἰ μή",
                    "analyses": [
                        {
                            "analysis_id": "expr-a",
                            "status": "proposed",
                            "identifiers": [{"scheme": "strong", "value": "G1508"}],
                            "component_identifiers": [{"scheme": "strong", "value": "G1"}],
                        }
                    ],
                }
            ],
        },
        "policy-1",
    )


def query(**kwargs: object) -> ConcordanceQuery:
    return ConcordanceQuery(
        study_snapshot_id="snapshot-1",
        policy_revision_id="policy-1",
        query_kind="identifier",
        value="G1",
        identifier_scheme="strong",
        **kwargs,
    )


def test_complete_bounded_traversal_exact_identifiers_and_shared_counts() -> None:
    study = view()
    cursor = None
    ids = []
    while True:
        result = study.concordance(query(), page_size=51, cursor=cursor)
        assert result["total_matches"] == result["total_tokens"] == 1003
        ids.extend(row["occurrence_id"] for row in result["matches"])
        cursor = result["next_cursor"]
        if not cursor:
            break
    assert len(ids) == len(set(ids)) == 1003
    assert study.concordance(replace(query(), value="G10"))["total_matches"] == 0
    assert study.concordance(replace(query(), identifier_scheme="estrong"))["total_matches"] == 0
    card = study.card("token-0000")
    assert card["counts"]["total_matches"] == 1003
    assert study.concordance(ConcordanceQuery(**card["query"]))["total_matches"] == 1003


def test_first_page_and_cursor_bind_policy_snapshot_and_query() -> None:
    study = view()
    first = study.concordance(query(), page_size=1)
    for stale in (
        replace(query(), study_snapshot_id="new"),
        replace(query(), policy_revision_id="new"),
    ):
        with pytest.raises(StaleStudyError):
            study.concordance(stale)
    with pytest.raises(StaleStudyError):
        study.concordance(replace(query(), value="G10"), cursor=first["next_cursor"])
    with pytest.raises(ValidationError):
        study.concordance(query(), page_size=201)


def test_expression_count_and_explicit_components() -> None:
    study = view(2)
    expression = replace(query(), value="G1508", match_unit="expression")
    result = study.concordance(expression)
    assert (result["total_matches"], result["total_tokens"], result["total_verses"]) == (1, 2, 1)
    component = replace(expression, value="G1")
    assert study.concordance(component)["total_matches"] == 0
    assert study.concordance(replace(component, expand_components=True))["total_matches"] == 1
    assert study.concordance(query(analysis_selection="selected"))["total_matches"] == 0
    assert study.concordance(query(analysis_scope="reviewed"))["total_matches"] == 0


def test_local_lexeme_query_does_not_merge_homographs_and_unresolved_surface_is_indexed() -> None:
    study = view(3)
    study.analyses["token-0001"][0]["lexeme_id"] = "homograph"
    study.analyses.pop("token-0002")
    q = replace(query(), query_kind="lexeme_id", value="word", identifier_scheme=None)
    assert study.concordance(q)["total_matches"] == 1
    assert study.concordance(q)["coverage"]["unresolved"] == 1
    surface = replace(q, query_kind="surface", value="λόγος")
    assert study.concordance(surface)["total_matches"] == 3
    assert study.concordance(surface)["counts_by_analysis_status"]["proposed"] == 2
    assert study.concordance(replace(surface, analysis_scope="reviewed"))["total_matches"] == 0
    assert study.concordance(replace(surface, analysis_scope="proposed"))["total_matches"] == 2
    assert study.concordance(replace(surface, analysis_selection="selected"))["total_matches"] == 0
    study.analyses["token-0000"][0]["status"] = "reviewed"
    study.tokens["token-0000"]["selected_analysis_id"] = "a-0"
    reviewed = study.concordance(replace(surface, analysis_scope="reviewed"))
    selected = study.concordance(replace(surface, analysis_selection="selected"))
    assert reviewed["total_matches"] == selected["total_matches"] == 1
    assert selected["counts_by_analysis_status"]["reviewed"] == 1


def test_identifier_relationships_do_not_become_direct_entry_or_token_assignments() -> None:
    study = view(2)
    study.payload["entries"] = [
        {
            "entry_id": "direct",
            "identifiers": [{"scheme": "eStrong", "value": "G1", "relation": "entry"}],
        },
        {
            "entry_id": "related",
            "identifiers": [
                {"scheme": "eStrong", "value": "G1", "relation": "combination_component"}
            ],
        },
    ]
    result = study.identifiers("eStrong", "G1")
    assert [entry["entry_id"] for entry in result["entries"]] == ["direct"]
    assert result["relationships"][0]["entry_id"] == "related"
    assert study.identifiers("Strong", "G1")["total_entries"] == 0
    study.analyses["token-0000"][0]["identifiers"][0]["relation"] = "combination_component"
    # Competing candidate retains a direct assignment on token 0; remove it here.
    study.analyses["token-0000"] = study.analyses["token-0000"][:1]
    assert study.concordance(query())["total_matches"] == 1
    assert study.concordance(replace(query(), expand_components=True))["total_matches"] == 2
