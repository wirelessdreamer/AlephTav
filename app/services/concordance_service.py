from __future__ import annotations

import json

from app.db.session import get_connection, init_db
from app.services import registry_service


def rebuild_indexes() -> dict[str, int]:
    init_db()
    units = registry_service.list_units()
    token_count = 0
    rendering_count = 0
    alignment_count = 0
    occurrence_count = 0
    enrichment_count = 0
    missing_count = 0
    with get_connection() as connection:
        for unit in units:
            connection.execute(
                "INSERT INTO unit_index(unit_id, psalm_id, ref, status, source_hebrew) VALUES (?, ?, ?, ?, ?)",
                (unit["unit_id"], unit["psalm_id"], unit["ref"], unit["status"], unit["source_hebrew"]),
            )
            for token in unit.get("tokens", []):
                connection.execute(
                    """
                    INSERT INTO token_index(
                        token_id, unit_id, psalm_id, ref, surface, normalized, transliteration, lemma, strong,
                        morph_code, morph_readable, part_of_speech, stem, syntax_role, semantic_role, referent, word_sense,
                        gloss_parts, display_gloss, compiler_features, occurrence_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        token["token_id"],
                        unit["unit_id"],
                        unit["psalm_id"],
                        token["ref"],
                        token["surface"],
                        token["normalized"],
                        token.get("transliteration"),
                        token.get("lemma"),
                        token.get("strong"),
                        token.get("morph_code"),
                        token.get("morph_readable"),
                        token.get("part_of_speech"),
                        token.get("stem"),
                        token.get("syntax_role"),
                        token.get("semantic_role"),
                        token.get("referent"),
                        token.get("word_sense"),
                        json.dumps(token.get("gloss_parts", []), sort_keys=True),
                        token.get("display_gloss"),
                        json.dumps(token.get("compiler_features", {}), sort_keys=True),
                        token["occurrence_index"],
                    ),
                )
                for scope, refs in (
                    ("same_psalm", token.get("same_psalm_occurrence_refs", [])),
                    ("psalms", token.get("psalms_occurrence_refs", [])),
                    ("corpus", token.get("corpus_occurrence_refs", [])),
                ):
                    for occurrence_ref in refs:
                        connection.execute(
                            "INSERT INTO token_occurrence_index(token_id, scope, occurrence_ref) VALUES (?, ?, ?)",
                            (token["token_id"], scope, occurrence_ref),
                        )
                        occurrence_count += 1
                for source_id, payload in token.get("enrichment_sources", {}).items():
                    connection.execute(
                        """
                        INSERT INTO token_enrichment_index(token_id, source_id, status, available_fields, missing_fields)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            token["token_id"],
                            source_id,
                            payload["status"],
                            json.dumps(payload.get("available_fields", []), sort_keys=True),
                            json.dumps(payload.get("missing_fields", []), sort_keys=True),
                        ),
                    )
                    enrichment_count += 1
                for item in token.get("missing_enrichments", []):
                    source_id, field_name = item.split(":", maxsplit=1)
                    connection.execute(
                        "INSERT INTO missing_enrichment_index(token_id, source_id, field_name) VALUES (?, ?, ?)",
                        (token["token_id"], source_id, field_name),
                    )
                    missing_count += 1
                token_count += 1
            for rendering in unit.get("renderings", []):
                connection.execute(
                    "INSERT INTO rendering_index(rendering_id, unit_id, layer, status, text_value) VALUES (?, ?, ?, ?, ?)",
                    (rendering["rendering_id"], unit["unit_id"], rendering["layer"], rendering["status"], rendering["text"]),
                )
                rendering_count += 1
            for alignment in unit.get("alignments", []):
                connection.execute(
                    "INSERT INTO alignment_index(alignment_id, unit_id, layer, alignment_type, confidence) VALUES (?, ?, ?, ?, ?)",
                    (alignment["alignment_id"], unit["unit_id"], alignment["layer"], alignment["alignment_type"], alignment["confidence"]),
                )
                alignment_count += 1
    return {
        "units": len(units),
        "tokens": token_count,
        "renderings": rendering_count,
        "alignments": alignment_count,
        "occurrences": occurrence_count,
        "enrichment_rows": enrichment_count,
        "missing_enrichments": missing_count,
    }
