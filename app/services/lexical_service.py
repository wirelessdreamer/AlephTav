from __future__ import annotations

from app.core.errors import NotFoundError
from app.db.session import get_connection
from app.services import registry_service


def get_token(token_id: str) -> dict:
    for unit in registry_service.list_units():
        for token in unit.get("tokens", []):
            if token["token_id"] == token_id:
                return {**token, "unit_id": unit["unit_id"], "psalm_id": unit["psalm_id"]}
    raise NotFoundError(f"Token not found: {token_id}")


def token_occurrences(token_id: str) -> dict:
    token = get_token(token_id)
    return {
        "token_id": token_id,
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
        "normalized": "normalized",
        "lemma": "lemma",
        "strong": "strong",
        "morphology": "morph_code",
    }.get(field, "lemma")
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT token_id, unit_id, ref, surface, normalized, lemma, strong FROM token_index WHERE {sql_field} LIKE ? ORDER BY ref",
            (f"%{query}%",),
        ).fetchall()
    return [dict(row) for row in rows]
