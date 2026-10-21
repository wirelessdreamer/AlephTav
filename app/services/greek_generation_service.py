"""Exact, currently permitted Greek source evidence for proposed translations."""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import LicensePolicyError
from app.services import greek_preview_service, registry_service, source_capability_service


def context(psalm_id: str) -> dict[str, Any] | None:
    # Preview consent alone never confers generation permission.
    path = greek_preview_service._approval_path()
    if not path.exists():
        return None
    approval_bytes = path.read_bytes()
    approval = json.loads(approval_bytes)
    if not source_capability_service.effective_capabilities(approval["source_id"])["generation"]:
        return None
    policy_id = source_capability_service.policy_revision()
    source_capability_service.require_package_capability(
        approval["source_id"], approval["package_id"], approval["manifest_sha256"], "generation"
    )
    preview = greek_preview_service.load_preview()
    if preview is None:
        return None
    from app.services.briefing_source_service import _by_mt_unit

    mappings, _ = _by_mt_unit(
        preview["records"],
        registry_service.load_psalm(psalm_id)["units"],
        {u["unit_id"]: u for u in preview["units"]},
        {},
        {},
        statuses={"proposed", "reviewed"},
    )
    if (
        source_capability_service.policy_revision() != policy_id
        or path.read_bytes() != approval_bytes
        or preview["manifest_sha256"] != approval["manifest_sha256"]
    ):
        raise LicensePolicyError("Greek source approval changed during generation evidence read")
    return {
        "source_id": approval["source_id"],
        "package_id": approval["package_id"],
        "manifest_sha256": preview["manifest_sha256"],
        "edition_id": preview["edition_id"],
        "text_revision_id": preview["text_revision_id"],
        "source_version": (
            f"{preview['edition_id']}:{preview['text_revision_id']}:{preview['manifest_sha256']}"
        ),
        "policy_revision": policy_id,
        "source_attribution": preview["source_attribution"],
        "map_status": "proposed_or_reviewed",
        "by_mt_unit": mappings,
    }


def prompt_evidence(psalm_id: str, unit_ids: list[str]) -> str:
    evidence = context(psalm_id)
    if evidence is None:
        return ""
    units = {
        mt_id: [
            {
                key: unit[key]
                for key in ("unit_id", "ref", "source_greek", "tokens", "partial", "mapped_spans")
            }
            for unit in evidence["by_mt_unit"].get(mt_id, {}).get("units", [])
        ]
        for mt_id in unit_ids
    }
    # Dictionary display permission does not license dictionary inputs to a model.
    for mapped in units.values():
        for unit in mapped:
            unit["tokens"] = [
                {key: token[key] for key in ("token_id", "surface", "text_span")}
                for token in unit["tokens"]
            ]
    return "\n".join(
        [
            "## Approved Greek generation source (retain attribution in provenance)",
            "Use Hebrew and Greek together; follow the saved decisions. If the English setting "
            "adopts a Greek variant, mark its basis septuagint_greek_to_english, both language "
            "fields grc, source_ids [lxx, " + evidence["source_id"] + "]. Copy source_version "
            "exactly. Copy the full mapped Greek source_greek into source_anchor.source_text "
            "and ALL its token_ids into source_anchor.token_ids. Never quote Hebrew as Greek. "
            "Keep Hebrew alignment_hints separately. Describe differences in accuracy_note. "
            "The verse map is proposed; outputs are proposed and require review.",
            json.dumps(
                {**{k: v for k, v in evidence.items() if k != "by_mt_unit"}, "by_mt_unit": units},
                ensure_ascii=False,
            ),
        ]
    )


def resolve(candidate: dict[str, Any], unit_id: str | None) -> dict[str, Any]:
    if not unit_id:
        raise LicensePolicyError("Greek source anchor requires its target Hebrew unit")
    evidence = context(unit_id.split(".")[0])
    if evidence is None:
        from app.services.source_basis_service import GreekGenerationUnavailableError

        raise GreekGenerationUnavailableError("Greek generation has no current source approval")
    basis = candidate.get("translation_basis") or {}
    anchor = candidate.get("source_anchor") or {}
    if (
        basis.get("basis_type") != "septuagint_greek_to_english"
        or basis.get("source_language") != "grc"
        or anchor.get("source_language") != "grc"
        or set(basis.get("source_ids", [])) != {"lxx", evidence["source_id"]}
        or basis.get("source_version") != evidence["source_version"]
    ):
        raise LicensePolicyError("Greek basis must identify the exact approved edition/revision")
    token_ids = anchor.get("token_ids") or []
    for unit in evidence["by_mt_unit"].get(unit_id, {}).get("units", []):
        tokens = unit["tokens"]
        if token_ids != [t["token_id"] for t in tokens]:
            continue
        if anchor.get("source_text") != unit["source_greek"]:
            continue
        # Full-verse anchors cannot claim an unrelated part of a split verse map.
        if unit["partial"] and unit["mapped_spans"]:
            if not any(
                s["start"] == 0 and s["end"] == len(unit["source_greek"])
                for s in unit["mapped_spans"]
            ):
                raise LicensePolicyError("Partial Greek mapping needs a reviewed full-verse map")
        return {
            **{k: v for k, v in evidence.items() if k != "by_mt_unit"},
            "greek_unit_id": unit["unit_id"],
            "mt_unit_id": unit_id,
            "token_ids": token_ids,
        }
    raise LicensePolicyError("Greek anchor text/tokens do not resolve to the target verse map")
