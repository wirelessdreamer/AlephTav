from __future__ import annotations

from app.db.session import get_connection, init_db
from app.services import registry_service


def rebuild_indexes() -> dict[str, int]:
    init_db()
    units = registry_service.list_units()
    token_count = 0
    rendering_count = 0
    alignment_count = 0
    with get_connection() as connection:
        connection.execute("DELETE FROM token_index")
        connection.execute("DELETE FROM unit_index")
        connection.execute("DELETE FROM rendering_index")
        connection.execute("DELETE FROM alignment_index")
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
                        morph_code, morph_readable, part_of_speech, syntax_role, semantic_role, referent, word_sense
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        token.get("syntax_role"),
                        token.get("semantic_role"),
                        token.get("referent"),
                        token.get("word_sense"),
                    ),
                )
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
    }
