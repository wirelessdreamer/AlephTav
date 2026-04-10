from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.errors import NotFoundError
from app.db.session import get_connection

LEXICAL_STATE_ID = "global"
CONCORDANCE_FIELDS = {
    "surface": "surface",
    "exact_form": "surface",
    "normalized": "normalized",
    "lemma": "lemma",
    "strong": "strong",
    "morphology": "morph_code",
    "stem": "stem",
    "binyan": "stem",
    "syntax_role": "syntax_role",
}


def _occurrence_groups(token: dict[str, Any]) -> dict[str, Any]:
    same_psalm = token.get("same_psalm_occurrence_refs", [])
    same_psalms = token.get("psalms_occurrence_refs", [])
    wider_corpus = token.get("corpus_occurrence_refs", [])
    return {
        "same_psalm": same_psalm,
        "same_psalms": same_psalms,
        "wider_corpus": wider_corpus,
        "counts": {
            "same_psalm": len(same_psalm),
            "same_psalms": len(same_psalms),
            "wider_corpus": len(wider_corpus),
        },
    }


def _gloss_list(token: dict[str, Any]) -> list[str]:
    return [item for item in [token.get("word_sense"), token.get("referent")] if item]


def _token_summary(token: dict[str, Any]) -> dict[str, Any]:
    return {
        "token_id": token["token_id"],
        "unit_id": token["unit_id"],
        "psalm_id": token["psalm_id"],
        "ref": token["ref"],
        "surface": token["surface"],
        "normalized": token["normalized"],
        "transliteration": token.get("transliteration"),
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        "morph_code": token.get("morph_code"),
        "morph_readable": token.get("morph_readable"),
        "part_of_speech": token.get("part_of_speech"),
        "stem": token.get("stem"),
        "syntax_role": token.get("syntax_role"),
        "semantic_role": token.get("semantic_role"),
        "referent": token.get("referent"),
        "word_sense": token.get("word_sense"),
        "occurrence_index": token.get("occurrence_index"),
    }


def _lexicon_entry(value: str, field: str, label: str) -> dict[str, Any]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT token_id, unit_id, psalm_id, ref, surface, normalized, transliteration, lemma, strong,
                   morph_code, morph_readable, part_of_speech, stem, syntax_role, semantic_role, referent,
                   word_sense, occurrence_index
            FROM token_index
            WHERE COALESCE(%s, '') = ?
            ORDER BY ref, occurrence_index, token_id
            """
            % field,
            (value,),
        ).fetchall()
    matches = [dict(row) for row in rows]
    return {
        label: value,
        "match_count": len(matches),
        "matches": [
            {
                **_token_summary(token),
                "gloss_list": _gloss_list(token),
            }
            for token in matches
        ],
    }


def _load_token_row(token_id: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM token_index WHERE token_id = ?", (token_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Token not found: {token_id}")
        token = dict(row)
        enrichment_rows = connection.execute(
            """
            SELECT source_id, status, available_fields, missing_fields
            FROM token_enrichment_index
            WHERE token_id = ?
            ORDER BY source_id
            """,
            (token_id,),
        ).fetchall()
        occurrence_rows = connection.execute(
            """
            SELECT scope, occurrence_ref
            FROM token_occurrence_index
            WHERE token_id = ?
            ORDER BY scope, occurrence_ref
            """,
            (token_id,),
        ).fetchall()
    token["enrichment_sources"] = {
        row["source_id"]: {
            "status": row["status"],
            "available_fields": json.loads(row["available_fields"]),
            "missing_fields": json.loads(row["missing_fields"]),
        }
        for row in enrichment_rows
    }
    token["missing_enrichments"] = sorted(
        f"{source_id}:{field_name}"
        for source_id, field_name in (
            (source_id, field_name)
            for source_id, fields in (
                (source_id, payload["missing_fields"])
                for source_id, payload in token["enrichment_sources"].items()
            )
            for field_name in fields
        )
    )
    token["same_psalm_occurrence_refs"] = [row["occurrence_ref"] for row in occurrence_rows if row["scope"] == "same_psalm"]
    token["psalms_occurrence_refs"] = [row["occurrence_ref"] for row in occurrence_rows if row["scope"] == "psalms"]
    token["corpus_occurrence_refs"] = [row["occurrence_ref"] for row in occurrence_rows if row["scope"] == "corpus"]
    return token


def get_token(token_id: str) -> dict[str, Any]:
    return _load_token_row(token_id)


def token_occurrences(token_id: str) -> dict[str, Any]:
    token = get_token(token_id)
    groups = _occurrence_groups(token)
    return {
        "token_id": token_id,
        "ref": token["ref"],
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        **groups,
    }


def lexical_card(token_id: str) -> dict[str, Any]:
    token = get_token(token_id)
    groups = _occurrence_groups(token)
    lemma_entry = _lexicon_entry(token["lemma"], "lemma", "lemma") if token.get("lemma") else {"lemma": None, "match_count": 0, "matches": []}
    strong_entry = _lexicon_entry(token["strong"], "strong", "strong") if token.get("strong") else {"strong": None, "match_count": 0, "matches": []}
    return {
        **token,
        **groups,
        "gloss_list": _gloss_list(token),
        "nearby_usage_examples": groups["same_psalms"][:3] or groups["wider_corpus"][:3],
        "copy_reference": f"{token['ref']} • {token['surface']} • {token['token_id']}",
        "concordance_entry": {
            "lemma": {
                "value": token.get("lemma"),
                "match_count": lemma_entry["match_count"],
            },
            "strong": {
                "value": token.get("strong"),
                "match_count": strong_entry["match_count"],
            },
        },
    }


def search_concordance(query: str, field: str = "lemma") -> list[dict[str, Any]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []
    sql_field = CONCORDANCE_FIELDS.get(field, "lemma")
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT token_id, unit_id, psalm_id, ref, surface, normalized, transliteration, lemma, strong,
                   morph_code, morph_readable, part_of_speech, stem, syntax_role, semantic_role, referent,
                   word_sense, occurrence_index
            FROM token_index
            WHERE COALESCE({sql_field}, '') LIKE ?
            ORDER BY ref, occurrence_index, token_id
            """,
            (f"%{normalized_query}%",),
        ).fetchall()
    return [
        {
            **_token_summary(dict(row)),
            "gloss_list": _gloss_list(dict(row)),
            "query_field": field,
        }
        for row in rows
    ]


def lemma_occurrences(lemma: str) -> dict[str, Any]:
    return _lexicon_entry(lemma, "lemma", "lemma")


def strong_occurrences(strong: str) -> dict[str, Any]:
    return _lexicon_entry(strong, "strong", "strong")


def get_pinned_lexical_card() -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT token_id, updated_at FROM lexical_card_state WHERE state_id = ?",
            (LEXICAL_STATE_ID,),
        ).fetchone()
    if row is None or row["token_id"] is None:
        return {"token_id": None, "updated_at": row["updated_at"] if row else None, "token": None}
    token = lexical_card(row["token_id"])
    return {"token_id": row["token_id"], "updated_at": row["updated_at"], "token": token}


def set_pinned_lexical_card(token_id: str | None) -> dict[str, Any]:
    if token_id is not None:
        get_token(token_id)
    updated_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO lexical_card_state(state_id, token_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(state_id) DO UPDATE SET token_id = excluded.token_id, updated_at = excluded.updated_at
            """,
            (LEXICAL_STATE_ID, token_id, updated_at),
        )
    return get_pinned_lexical_card()
