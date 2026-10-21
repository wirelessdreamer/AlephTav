from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.db.session import connect_catalog, init_catalog
from app.services import registry_service
from app.services.immutable_file_service import atomic_write, sha256_file, workspace_lock


def _populate_indexes(path: Path, units: list[dict[str, Any]]) -> dict[str, int]:
    token_count = 0
    rendering_count = 0
    alignment_count = 0
    occurrence_count = 0
    enrichment_count = 0
    missing_count = 0
    comparison_count = 0
    with connect_catalog(path, writable=True) as connection:
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
            # Assessments are committed content; this index is only a query
            # mirror, rebuilt from the unit JSON like everything else here.
            for assessment in unit.get("comparison_assessments", []):
                connection.execute(
                    """
                    INSERT INTO comparison_assessment_index(
                        comparison_id, unit_id, psalm_id, mt_reference, literal_rendering_id,
                        english_rendering_id, accuracy_rating, status, created_via,
                        generator_provider, reviewer_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment["comparison_id"],
                        unit["unit_id"],
                        assessment["psalm_id"],
                        assessment["mt_reference"],
                        assessment["literal_rendering_id"],
                        assessment["english_rendering_id"],
                        assessment["accuracy_rating"],
                        assessment["status"],
                        assessment["created_via"],
                        assessment["generator_provider"],
                        assessment["reviewer_id"],
                    ),
                )
                comparison_count += 1
    # Refresh the slim psalm-summary + corpus-layer caches now that the
    # SQLite indexes (specifically ``rendering_index``) are up to date.
    # This makes the post-build summary cache match the indexed corpus state.
    return {
        "units": len(units),
        "tokens": token_count,
        "renderings": rendering_count,
        "alignments": alignment_count,
        "occurrences": occurrence_count,
        "enrichment_rows": enrichment_count,
        "missing_enrichments": missing_count,
        "comparison_assessments": comparison_count,
    }


def rebuild_indexes() -> dict[str, int]:
    """Build privately, validate, then publish without touching the last catalog.

    Retained readers continue using their open immutable file on Windows. No
    operational tables are copied, dropped or stored in this catalog.
    """
    from app.services.mt_source_snapshot_service import capture_mt_source_snapshot

    settings = get_settings()
    pointer_path = settings.indexes_dir / "active_catalog.json"
    predecessor = pointer_path.read_bytes() if pointer_path.exists() else None
    units = registry_service.list_units()
    catalogs = settings.indexes_dir / "catalogs"
    catalogs.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix=".build-", suffix=".sqlite3", dir=catalogs)
    os.close(descriptor)
    staging = Path(filename)
    try:
        init_catalog(staging)
        counts = _populate_indexes(staging, units)
        with connect_catalog(staging) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Catalog SQLite integrity validation failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Catalog foreign-key validation failed")
            indexed_units = connection.execute("SELECT COUNT(*) FROM unit_index").fetchone()[0]
            if indexed_units != counts["units"]:
                raise RuntimeError("Catalog unit-count validation failed")
        digest = sha256_file(staging)
        published = catalogs / f"catalog.{digest}.sqlite3"
        with workspace_lock(settings.data_dir / "local" / "catalog-publication.lock"):
            current = pointer_path.read_bytes() if pointer_path.exists() else None
            if current != predecessor:
                raise RuntimeError("Stale catalog builder; active catalog changed")
            if published.exists():
                if sha256_file(published) != digest:
                    raise RuntimeError("Retained catalog bytes changed")
            else:
                os.replace(staging, published)
            mt_snapshot = capture_mt_source_snapshot(units)
            atomic_write(pointer_path, registry_service.deterministic_json({
                "path": published.relative_to(settings.root_dir).as_posix(),
                "sha256": digest, "catalog_revision_id": digest,
                "mt_source_snapshot": mt_snapshot,
            }).encode("utf-8"))
        registry_service.invalidate_summary_cache()
        registry_service.build_summary_cache()
        return counts
    finally:
        staging.unlink(missing_ok=True)
