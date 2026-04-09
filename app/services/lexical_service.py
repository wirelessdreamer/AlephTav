from __future__ import annotations

import json

from app.core.errors import NotFoundError
from app.db.session import get_connection


def _load_token_row(token_id: str) -> dict:
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


def get_token(token_id: str) -> dict:
    return _load_token_row(token_id)


def token_occurrences(token_id: str) -> dict:
    token = get_token(token_id)
    return {
        "token_id": token_id,
        "same_psalm": token.get("same_psalm_occurrence_refs", []),
        "same_psalms": token.get("psalms_occurrence_refs", []),
        "wider_corpus": token.get("corpus_occurrence_refs", []),
    }


def lexical_card(token_id: str) -> dict:
    token = get_token(token_id)
    return {
        **token,
        "gloss_list": [token.get("word_sense"), token.get("referent")],
        "nearby_usage_examples": token.get("psalms_occurrence_refs", [])[:3],
        "copy_reference": f"{token['ref']} ({token['token_id']})",
    }


def search_concordance(query: str, field: str = "lemma") -> list[dict]:
    sql_field = {
        "surface": "surface",
        "exact_form": "surface",
        "normalized": "normalized",
        "lemma": "lemma",
        "strong": "strong",
        "morphology": "morph_code",
        "stem": "stem",
        "binyan": "stem",
        "syntax_role": "syntax_role",
    }.get(field, "lemma")
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT token_id, unit_id, ref, surface, normalized, lemma, strong, morph_code, stem, syntax_role
            FROM token_index
            WHERE COALESCE({sql_field}, '') LIKE ?
            ORDER BY ref
            """,
            (f"%{query}%",),
        ).fetchall()
    return [dict(row) for row in rows]
