from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest

from app.core.errors import ValidationError
from app.services import registry_service
from app.services.review_payload_service import review_payload_digest, review_policy_revision

pytestmark = pytest.mark.no_seeded_repo
TARGET = "rnd.ps001.v001.a.lyric.alt.0001"
UNIT = "ps001.v001.a"
TOKEN = "ps001.v001.t001"
SPAN = "spn.ps001.v001.a.lyric.0001"


@pytest.fixture
def evidence() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    basis = {
        "basis_type": "hebrew_to_english",
        "source_ids": ["uxlc"],
        "source_language": "he",
        "source_version": "source-v1",
        "basis_note": "Hebrew basis",
    }
    target = {
        "rendering_id": TARGET,
        "unit_id": UNIT,
        "layer": "lyric",
        "status": "proposed",
        "text": "Blessed is the one",
        "rationale": "Preserve the source image",
        "style_tags": ["lyric", "formal"],
        "variation_basis": ["cadence"],
        "preserved_source_images": [{"label": "way", "token_ids": [TOKEN]}],
        "target_spans": [{"span_id": SPAN, "text": "Blessed", "token_start": 0, "token_end": 1}],
        "translation_basis": deepcopy(basis),
        "source_anchor": {
            "anchor_text": "blessed",
            "source_language": "he",
            "source_text": "אַשְׁרֵי",
            "token_ids": [TOKEN],
            "basis_note": "Source anchor",
        },
        "provenance": {
            "source_ids": ["uxlc"],
            "translation_basis": deepcopy(basis),
            "alignment_hints": [f"{TOKEN} -> Blessed"],
            "run_id": "run.original",
        },
        "alignment_ids": ["cache-only"],
        "review_signoff": {},
    }
    unit = {
        "unit_id": UNIT,
        "psalm_id": "ps001",
        "ref": "Psalm 1:1",
        "source_hebrew": "אַשְׁרֵי",
        "source_transliteration": "ashrei",
        "segmentation_type": "verse",
        "token_ids": [TOKEN],
        "tokens": [
            {
                "token_id": TOKEN,
                "surface": "אַשְׁרֵי",
                "normalized": "אשרי",
                "lemma": "אשר",
                "morph_code": "Ncmpc",
                "display_gloss": "blessed",
                "compiler_features": {"construct_state": True},
                "enrichment_sources": {"oshb": {"status": "partial", "missing_fields": ["stem"]}},
            }
        ],
        "renderings": [
            target,
            {
                "rendering_id": "rnd.ps001.v001.a.literal.can.0001",
                "unit_id": UNIT,
                "layer": "literal",
                "status": "canonical",
                "text": "Blessed the man",
                "rationale": "Literal baseline",
                "target_spans": [],
                "translation_basis": deepcopy(basis),
            },
        ],
        "alignments": [
            {
                "alignment_id": "aln.ps001.v001.a.lyric.0001",
                "unit_id": UNIT,
                "layer": "lyric",
                "source_token_ids": [TOKEN],
                "target_span_ids": [SPAN],
                "alignment_type": "direct",
                "confidence": 0.9,
                "notes": "Explicit source link",
                "created_by": "editor",
                "created_via": "manual",
            }
        ],
        "audit_records": [],
        "review_decisions": [],
    }
    project = {
        "title": "Study project",
        "divine_name_policy": "preserve distinctions",
        "review_policy": {
            "canonical_required_approvals": 2,
            "alternate_required_approvals": 1,
            "release_required_role": "release reviewer",
            "reviewer_roles": ["Hebrew reviewer", "alignment reviewer", "release reviewer"],
        },
        "allowed_sources": ["uxlc", "oshb"],
        "source_manifests": [
            {
                "source_id": source,
                "version": "v1",
                "import_hash": "a" * 64,
                "license": "Public Domain",
                "allowed_for_display": True,
                "allowed_for_generation": source == "uxlc",
                "allowed_for_export": True,
            }
            for source in ("uxlc", "oshb")
        ],
        "style_profiles": [{"style_profile_id": "formal", "target_syllables": 8}],
    }
    registry = {
        "schema_version": "1.0",
        "policy_revision_id": "global-label",
        "sources": [
            {
                "source_id": "uxlc",
                "components": {
                    "text": {
                        "status": "approved",
                        "capabilities": {"display": True, "export": True},
                        "package_hashes": {"uxlc.text": "a" * 64},
                        "approvals": [
                            {
                                "role": "owner",
                                "reviewer_id": "owner",
                                "decision": "approve",
                                "payload_hash": "b" * 64,
                            }
                        ],
                    }
                },
            }
        ],
    }
    return unit, project, registry


def test_binding_shape_is_deterministic_and_does_not_mutate_inputs(evidence) -> None:
    unit, project, registry = evidence
    before = deepcopy(evidence)

    first = review_payload_digest(unit, TARGET, project)
    second = review_payload_digest(deepcopy(unit), TARGET, deepcopy(project))
    revision = review_policy_revision(unit, TARGET, project, registry)

    assert first == second
    assert first["version"] == 2
    assert first["algorithm"] == "sha256"
    assert len(first["value"]) == len(revision) == 64
    int(first["value"], 16)
    int(revision, 16)
    assert evidence == before


@pytest.mark.parametrize(
    "change",
    [
        "text",
        "rationale",
        "style_order",
        "span_text",
        "span_boundary",
        "token_surface",
        "token_morphology",
        "token_gloss",
        "compiler",
        "source_text",
        "source_order",
        "basis",
        "provenance_basis",
        "anchor",
        "hint",
        "alignment",
        "literal",
        "style",
        "divine_name",
        "ownership",
        "source_image",
    ],
)
def test_substantive_changes_invalidate_the_payload(evidence, change: str) -> None:
    unit, project, _ = evidence
    before = review_payload_digest(unit, TARGET, project)
    target = unit["renderings"][0]
    if change in {"text", "rationale"}:
        target[change] += " changed"
    elif change == "style_order":
        target["style_tags"].reverse()
    elif change == "span_text":
        target["target_spans"][0]["text"] = "Happy"
    elif change == "span_boundary":
        target["target_spans"][0]["token_end"] = 2
    elif change == "token_surface":
        unit["tokens"][0]["surface"] += "א"
    elif change == "token_morphology":
        unit["tokens"][0]["morph_code"] = "Ncmsa"
    elif change == "token_gloss":
        unit["tokens"][0]["display_gloss"] = "happy"
    elif change == "compiler":
        unit["tokens"][0]["compiler_features"]["construct_state"] = False
    elif change == "source_text":
        unit["source_hebrew"] += "א"
    elif change == "source_order":
        unit["tokens"].append({"token_id": "ps001.v001.t002", "surface": "א"})
        unit["token_ids"].append("ps001.v001.t002")
    elif change == "basis":
        target["translation_basis"]["source_version"] = "v2"
    elif change == "provenance_basis":
        target["provenance"]["translation_basis"]["basis_note"] = "Other claim"
    elif change == "anchor":
        target["source_anchor"]["source_text"] += "א"
    elif change == "hint":
        target["provenance"]["alignment_hints"] = [f"{TOKEN} -> Happy"]
    elif change == "alignment":
        unit["alignments"][0]["notes"] = "An idiom rather than direct equivalence"
    elif change == "literal":
        unit["renderings"][1]["text"] = "Happy the man"
    elif change == "style":
        project["style_profiles"][0]["target_syllables"] = 9
    elif change == "divine_name":
        project["divine_name_policy"] = "use the title Lord"
    elif change == "ownership":
        target["translation_id"] = "tr.ps001.0001"
    elif change == "source_image":
        target["preserved_source_images"][0]["label"] = "path"
    assert review_payload_digest(unit, TARGET, project) != before


def test_unrelated_content_and_circular_caches_do_not_change_bindings(evidence) -> None:
    unit, project, registry = evidence
    payload = review_payload_digest(unit, TARGET, project)
    policy = review_policy_revision(unit, TARGET, project, registry)
    target = unit["renderings"][0]
    target.update(
        {
            "status": "canonical",
            "metrics": {"score": 1},
            "drift_flags": [],
            "review_signoff": {"approval_count": 2},
            "alignment_ids": ["refreshed"],
            "issue_links": ["#2"],
            "grounding_confidence": 0.99,
        }
    )
    target["provenance"].update({"run_id": "new", "generated_at": "tomorrow", "model": "new"})
    unit.update(
        {
            "audit_records": [{"rationale": "unrelated"}],
            "review_decisions": [{"decision": "approve"}],
            "current_layer_state": {},
        }
    )
    unit["tokens"][0].update({"occurrence_index": 99, "corpus_occurrence_refs": ["Psalm 2:1"]})
    unit["renderings"].append(
        {
            "rendering_id": "other",
            "layer": "phrase",
            "status": "proposed",
            "text": "Unrelated alternate",
            "target_spans": [],
        }
    )
    project["title"] = "Renamed"
    project["local_model_profiles"] = [{"model": "different"}]
    project["style_profiles"].append({"style_profile_id": "unused", "target_syllables": 3})
    project["source_manifests"].append({"source_id": "unused", "license": "unknown"})
    project["allowed_sources"].append("unused")
    registry["policy_revision_id"] = "unrelated global change"
    registry["sources"].append({"source_id": "unused", "components": {}})
    registry["sources"][0]["components"]["dictionary"] = {"status": "revoked"}
    assert review_payload_digest(unit, TARGET, project) == payload
    assert review_policy_revision(unit, TARGET, project, registry) == policy


def test_dictionary_order_is_not_semantic_but_source_order_is(evidence) -> None:
    unit, project, _ = evidence
    reordered = {key: unit[key] for key in reversed(unit)}
    assert review_payload_digest(unit, TARGET, project) == review_payload_digest(
        reordered, TARGET, dict(reversed(list(project.items())))
    )
    unit["tokens"].append({"token_id": "ps001.v001.t002", "surface": "א"})
    unit["token_ids"].append("ps001.v001.t002")
    before = review_payload_digest(unit, TARGET, project)
    unit["tokens"].reverse()
    unit["token_ids"].reverse()
    assert review_payload_digest(unit, TARGET, project) != before


def test_unrelated_alignment_changes_do_not_supply_target_coverage(evidence) -> None:
    unit, project, _ = evidence
    before = review_payload_digest(unit, TARGET, project)
    unit["renderings"].append(
        {
            "rendering_id": "unrelated",
            "layer": "lyric",
            "status": "proposed",
            "text": "Other",
            "target_spans": [{"span_id": "other-span"}],
        }
    )
    unit["alignments"].append(
        {
            "alignment_id": "other-link",
            "layer": "lyric",
            "unit_id": UNIT,
            "source_token_ids": [TOKEN],
            "target_span_ids": ["other-span"],
            "confidence": 0.5,
        }
    )
    assert review_payload_digest(unit, TARGET, project) == before
    unit["alignments"][-1]["source_token_ids"] = ["a-new-claim"]
    assert review_payload_digest(unit, TARGET, project) == before


def test_upstream_source_claims_participate_in_the_policy_fingerprint(evidence) -> None:
    unit, project, registry = evidence
    before = review_policy_revision(unit, TARGET, project, registry)
    unit["renderings"][1]["translation_basis"]["source_ids"] = ["new-source"]
    assert review_policy_revision(unit, TARGET, project, registry) != before


def test_parallelism_lyric_also_binds_the_literal_used_for_poetic_analysis(evidence) -> None:
    unit, project, _ = evidence
    unit["renderings"][0]["layer"] = "parallelism_lyric"
    unit["alignments"] = []
    before = review_payload_digest(unit, TARGET, project)
    unit["renderings"][1]["text"] = "Changed literal reference"
    assert review_payload_digest(unit, TARGET, project) != before


@pytest.mark.parametrize(
    "change", ["threshold", "role", "manifest", "permission", "package", "decision"]
)
def test_relevant_policy_and_source_authority_changes_change_revision(
    evidence, change: str
) -> None:
    unit, project, registry = evidence
    before = review_policy_revision(unit, TARGET, project, registry)
    component = registry["sources"][0]["components"]["text"]
    if change == "threshold":
        project["review_policy"]["canonical_required_approvals"] = 3
    elif change == "role":
        project["review_policy"]["reviewer_roles"].append("lyric reviewer")
    elif change == "manifest":
        project["source_manifests"][1]["import_hash"] = "c" * 64
    elif change == "permission":
        component["capabilities"]["export"] = False
    elif change == "package":
        component["package_hashes"]["uxlc.text"] = "c" * 64
    elif change == "decision":
        component["approvals"].append({**component["approvals"][0], "decision": "withdraw"})
    assert review_policy_revision(unit, TARGET, project, registry) != before


def test_roles_are_normalized_but_authority_decision_order_is_preserved(evidence) -> None:
    unit, project, registry = evidence
    before = review_policy_revision(unit, TARGET, project, registry)
    project["review_policy"]["reviewer_roles"].reverse()
    assert review_policy_revision(unit, TARGET, project, registry) == before
    approvals = registry["sources"][0]["components"]["text"]["approvals"]
    approvals.append({**approvals[0], "decision": "withdraw"})
    withdrawn = review_policy_revision(unit, TARGET, project, registry)
    approvals.reverse()
    assert review_policy_revision(unit, TARGET, project, registry) != withdrawn


def test_unknown_source_authority_is_explicit_and_not_a_default_grant(evidence) -> None:
    unit, project, _ = evidence
    absent = review_policy_revision(unit, TARGET, project)
    empty = review_policy_revision(unit, TARGET, project, {"sources": []})
    assert absent != empty
    project["source_manifests"].append({"source_id": "unused"})
    assert review_policy_revision(unit, TARGET, project) == absent


@pytest.mark.parametrize(
    "key",
    [
        "canonical_required_approvals",
        "alternate_required_approvals",
        "release_required_role",
        "reviewer_roles",
    ],
)
def test_missing_required_review_policy_is_rejected(evidence, key: str) -> None:
    unit, project, _ = evidence
    del project["review_policy"][key]
    with pytest.raises(ValidationError):
        review_policy_revision(unit, TARGET, project)


@pytest.mark.parametrize(
    "change",
    [
        "target_duplicate",
        "span_duplicate",
        "cross_owned",
        "bad_source",
        "nonfinite",
        "bad_text",
        "bad_source_text",
    ],
)
def test_malformed_or_ambiguous_semantics_are_rejected(evidence, change: str) -> None:
    unit, project, _ = evidence
    target = unit["renderings"][0]
    if change == "target_duplicate":
        unit["renderings"].append(deepcopy(target))
    elif change == "span_duplicate":
        unit["renderings"][1]["target_spans"] = deepcopy(target["target_spans"])
    elif change == "cross_owned":
        unit["alignments"][0]["target_span_ids"].append("other-span")
    elif change == "bad_source":
        unit["alignments"][0]["source_token_ids"] = ["missing-token"]
    elif change == "nonfinite":
        unit["alignments"][0]["confidence"] = float("nan")
    elif change == "bad_text":
        target["text"] = 3
    elif change == "bad_source_text":
        unit["source_hebrew"] = 3
    with pytest.raises(ValidationError):
        review_payload_digest(unit, TARGET, project)


def test_greek_package_and_map_identity_are_scoped_not_runtime_metadata(evidence) -> None:
    unit, project, _ = evidence
    descriptor = {
        "source_id": "swete1896",
        "package_id": "swete1896.text",
        "manifest_sha256": "a" * 64,
        "map_sha256": "b" * 64,
        "greek_unit_id": "lxx.swete1896.r0001.ps001.v001.a",
        "token_ids": ["greek-token"],
    }
    unit["renderings"][0]["provenance"]["greek_generation_source"] = descriptor
    before = review_payload_digest(unit, TARGET, project)
    descriptor["elapsed_ms"] = 500
    assert review_payload_digest(unit, TARGET, project) == before
    descriptor["map_sha256"] = "c" * 64
    assert review_payload_digest(unit, TARGET, project) != before


def test_missing_and_null_optional_evidence_are_distinct(evidence) -> None:
    unit, project, _ = evidence
    del unit["renderings"][0]["source_anchor"]
    missing = review_payload_digest(unit, TARGET, project)
    unit["renderings"][0]["source_anchor"] = None
    assert review_payload_digest(unit, TARGET, project) != missing


def test_source_authority_metadata_is_not_a_permission_revision(evidence) -> None:
    unit, project, registry = evidence
    before = review_policy_revision(unit, TARGET, project, registry)
    project["source_manifests"][0].update(
        {"name": "New label", "notes": "Note", "imported_at": "today"}
    )
    component = registry["sources"][0]["components"]["text"]
    component["notes"] = "A display note"
    component["approvals"][0]["timestamp"] = "now"
    assert review_policy_revision(unit, TARGET, project, registry) == before


@pytest.mark.parametrize("value", [True, "0.9", 10**500, float("inf")])
def test_invalid_alignment_confidence_fails_with_a_domain_error(evidence, value) -> None:
    unit, project, _ = evidence
    unit["alignments"][0]["confidence"] = value
    with pytest.raises(ValidationError):
        review_payload_digest(unit, TARGET, project)


def test_source_authority_missing_components_remains_explicit(evidence) -> None:
    unit, project, registry = evidence
    del registry["sources"][0]["components"]
    missing = review_policy_revision(unit, TARGET, project, registry)
    registry["sources"][0]["components"] = {}
    assert review_policy_revision(unit, TARGET, project, registry) != missing


def test_target_identity_cannot_transfer_a_review_to_another_rendering(evidence) -> None:
    unit, project, _ = evidence
    before = review_payload_digest(unit, TARGET, project)
    unit["renderings"][0]["rendering_id"] = "new-identity"
    assert review_payload_digest(unit, "new-identity", project) != before


def test_real_greek_generation_descriptor_preserves_structured_attribution(evidence) -> None:
    unit, project, _ = evidence
    descriptor = {
        "source_id": "swete1896",
        "package_id": "swete1896.text",
        "manifest_sha256": "a" * 64,
        "edition_id": "swete1896",
        "text_revision_id": "r0001",
        "source_version": "swete1896:r0001:" + "a" * 64,
        "policy_revision": "owner-approved:fixture",
        "source_attribution": [
            {
                "attribution": "H. B. Swete, The Old Testament in Greek, vol. 2, Psalms",
                "license": "CC BY-SA 4.0",
            }
        ],
        "map_status": "proposed_or_reviewed",
        "greek_unit_id": "lxx.swete1896.r0001.ps001.v001.a",
        "mt_unit_id": UNIT,
        "token_ids": ["lxx.swete1896.r0001.ps001.v001.t001"],
    }
    unit["renderings"][0]["provenance"]["greek_generation_source"] = descriptor
    before = review_payload_digest(unit, TARGET, project)
    descriptor["source_attribution"][0]["display_timestamp"] = "not linguistic evidence"
    assert review_payload_digest(unit, TARGET, project) == before
    descriptor["source_attribution"][0]["license"] = "Other license claim"
    assert review_payload_digest(unit, TARGET, project) != before


@pytest.mark.parametrize(
    "attribution", ["plain text", ["not an object"], [{"license": "CC BY-SA 4.0"}]]
)
def test_malformed_greek_attribution_is_a_domain_error(evidence, attribution) -> None:
    unit, project, _ = evidence
    unit["renderings"][0]["provenance"]["greek_generation_source"] = {
        "source_id": "swete1896",
        "source_attribution": attribution,
    }
    with pytest.raises(ValidationError):
        review_payload_digest(unit, TARGET, project)


def test_new_binding_does_not_change_historical_audit_hash_serialization() -> None:
    value = {"text": "א", "audit_records": []}
    expected = hashlib.sha256(
        (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    assert registry_service.file_hash(value) == expected


def test_excessive_evidence_nesting_is_a_domain_error(evidence) -> None:
    unit, project, _ = evidence
    nested: dict[str, Any] = {}
    for _ in range(600):
        nested = {"nested": nested}
    unit["tokens"][0]["compiler_features"] = nested

    with pytest.raises(ValidationError, match="nesting|finite JSON"):
        review_payload_digest(unit, TARGET, project)


def test_raw_object_hints_are_bound_after_the_actual_producer_stringifies_them(evidence) -> None:
    from app.services.codex_translation_service import _alignment_hints

    unit, project, _ = evidence
    raw_hint = {"source_token_ids": [TOKEN], "target_text": "Blessed"}
    stored = _alignment_hints({"alignment_hints": [raw_hint]})
    assert stored["alignment_hints"] == [str(raw_hint)]
    unit["renderings"][0]["provenance"].update(stored)
    before = review_payload_digest(unit, TARGET, project)
    raw_hint["target_text"] = "Happy"
    unit["renderings"][0]["provenance"].update(_alignment_hints({"alignment_hints": [raw_hint]}))
    assert review_payload_digest(unit, TARGET, project) != before


@pytest.mark.parametrize(
    "key,value",
    [
        ("canonical_required_approvals", 0),
        ("alternate_required_approvals", 0),
        ("canonical_required_approvals", True),
        ("reviewer_roles", []),
        ("reviewer_roles", ["Hebrew reviewer", "Hebrew reviewer"]),
    ],
)
def test_malformed_review_policy_cannot_create_a_revision(evidence, key: str, value) -> None:
    unit, project, _ = evidence
    project["review_policy"][key] = value
    with pytest.raises(ValidationError):
        review_policy_revision(unit, TARGET, project)
