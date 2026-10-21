"""Recover missing source evidence from completed Codex runs without inventing it."""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Any

from app.services import (
    codex_translation_service,
    generation_service,
    registry_service,
    rendering_service,
)

_ANCHOR_VALIDATOR = generation_service.OUTPUT_VALIDATOR.evolve(
    schema=generation_service.OUTPUT_VALIDATOR.schema["properties"]["candidates"]["items"][
        "properties"
    ]["source_anchor"]
)


def _anchor_problem(candidate: dict[str, Any], unit: dict[str, Any]) -> str | None:
    anchor = candidate.get("source_anchor")
    if not isinstance(anchor, dict):
        return "Cached candidate has no source anchor"
    error = next(_ANCHOR_VALIDATOR.iter_errors(anchor), None)
    if error is not None:
        return f"Cached source anchor fails its contract: {error.message}"
    basis = candidate.get("translation_basis") or {}
    if basis.get("basis_type") == "septuagint_greek_to_english":
        flags = generation_service._source_basis_drift_flags(basis, anchor)
        if flags:
            return flags[0]["message"]
    else:
        # Historical Codex Hebrew labels/source IDs are deliberately permissive, as
        # in run validation. Recover evidence, rather than rewriting those labels.
        if anchor.get("source_language") not in {"he", "hebrew", "Hebrew"}:
            return "Cached candidate does not identify a Hebrew anchor"
        if not any(
            ch.isalpha() and "HEBREW" in unicodedata.name(ch, "")
            for ch in str(anchor.get("source_text") or "")
        ):
            return "Cached candidate has no Hebrew source text"
    token_ids = anchor.get("token_ids", [])
    if not isinstance(token_ids, list) or any(
        token_id not in unit.get("token_ids", []) for token_id in token_ids
    ):
        return "Cached anchor names tokens outside the saved unit"
    return None


def recover_source_anchors(*, apply: bool = False) -> dict[str, Any]:
    """Inventory Codex evidence gaps; optionally repair uniquely evidenced proposals.

    Reviewed renderings are reported for qualified review, never modified here.
    Every repair uses the rendering service and consequently writes an AuditRecord.
    """
    runs = codex_translation_service._read_store()["runs"]
    rows: list[dict[str, Any]] = []
    invalid_greek: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        for rendering in unit.get("renderings", []):
            basis = rendering.get("translation_basis") or {}
            if basis.get("basis_type") == "septuagint_greek_to_english":
                flags = generation_service._source_basis_drift_flags(
                    basis, rendering.get("source_anchor") or {}
                )
                if flags:
                    invalid_greek.append(
                        {"rendering_id": rendering["rendering_id"], "problems": flags}
                    )
            provenance = rendering.get("provenance") or {}
            if rendering.get("source_anchor") or provenance.get("provider") != "codex-app-server":
                continue
            row: dict[str, Any] = {
                "unit_id": unit["unit_id"],
                "rendering_id": rendering["rendering_id"],
                "rendering_status": rendering["status"],
                "run_id": provenance.get("run_id"),
                "action": "unresolved",
            }
            rows.append(row)
            run = runs.get(provenance.get("run_id")) or {}
            if (
                run.get("status") != "completed"
                or run.get("kind") != "translation"
                or run.get("run_id") != provenance.get("run_id")
                or run.get("translation_id") != rendering.get("translation_id")
            ):
                row["reason"] = "Matching completed translation run is unavailable"
                continue
            payload = run.get("payload") or {}
            entries = payload.get("units", [payload])
            candidates = [
                candidate
                for entry in entries
                if entry.get("unit_id") == unit["unit_id"]
                and entry.get("layer", run.get("layer")) == rendering["layer"]
                for candidate in entry.get("candidates", [])
                if candidate.get("text") == rendering["text"]
                and candidate.get("translation_basis") == basis
            ]
            if len(candidates) != 1:
                row["reason"] = "Cached candidate does not match uniquely by unit, layer, and text"
                continue
            problem = _anchor_problem(candidates[0], unit)
            if problem:
                row["reason"] = problem
                continue
            if rendering["status"] != "proposed":
                row["action"] = "review_required"
                row["reason"] = "Existing reviewed rendering requires qualified approval"
                continue
            row["action"] = "recoverable"
            if apply:
                rendering_service.update_rendering(
                    rendering["rendering_id"],
                    {
                        "source_anchor": candidates[0]["source_anchor"],
                    },
                    created_by="codex-source-anchor-recovery",
                    audit_rationale=f"Recover original source anchor from {run['run_id']}",
                )
                row["action"] = "recovered"
    return {
        "applied": apply,
        "counts": dict(Counter(row["action"] for row in rows)),
        "missing_anchors": rows,
        "invalid_greek_bases": invalid_greek,
    }
