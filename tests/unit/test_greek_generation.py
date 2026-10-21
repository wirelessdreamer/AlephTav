from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.core.errors import LicensePolicyError
from app.services import greek_generation_service as greek
from app.services import source_basis_service as basis
from app.services import source_capability_service as policy
from app.services import study_snapshot_service
from tests.unit.test_greek_preview import staged  # noqa: F401

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def approved(staged, tmp_path):  # noqa: F811
    approval = json.loads((tmp_path / "content/study_snapshots/preview.json").read_text())
    capabilities = dict.fromkeys(policy.CAPABILITIES, False)
    capabilities.update(display=True, generation=True)
    hashes = {"swete1896.text": approval["manifest_sha256"]}
    digest = policy.approval_payload_hash("swete1896", "text", capabilities, hashes)
    registry = {
        "schema_version": "1.0",
        "policy_revision_id": "test-generation",
        "sources": [
            {
                "source_id": "swete1896",
                "components": {
                    "text": {
                        "status": "approved",
                        "capabilities": capabilities,
                        "package_hashes": hashes,
                        "approvals": [
                            {
                                "role": role,
                                "reviewer_id": role,
                                "decision": "approve",
                                "payload_hash": digest,
                            }
                            for role in ("owner", "license")
                        ],
                    }
                },
            }
        ],
    }
    study_snapshot_service.publish_source_policy(
        registry,
        expected_revision=policy.policy_revision(),
        created_by="test",
        rationale="Authored test approvals",
    )
    evidence = greek.context("ps001")
    unit = evidence["by_mt_unit"]["ps001.v001.a"]["units"][0]
    return {
        "translation_basis": {
            "basis_type": "septuagint_greek_to_english",
            "source_language": "grc",
            "source_ids": ["lxx", "swete1896"],
            "source_version": evidence["source_version"],
        },
        "source_anchor": {
            "source_language": "grc",
            "source_text": unit["source_greek"],
            "token_ids": [t["token_id"] for t in unit["tokens"]],
        },
    }


def test_exact_approved_source_resolves_and_carries_attribution(approved):
    result = basis.require_generation_basis_available(approved, "ps001.v001.a")
    assert result["greek_unit_id"] == "lxx.swete1896.r0001.ps001.v001.a"
    assert result["source_attribution"][0]["license"] == "CC BY-SA 4.0"
    assert "source_version" in greek.prompt_evidence("ps001", ["ps001.v001.a"])
    assert policy.effective_capabilities("swete1896")["export"] is False


def test_codex_accepts_exact_greek_basis_and_records_it_on_creation(approved, monkeypatch):
    from app.services import codex_translation_service as translation

    candidate = {**approved, "text": "Blessed is the man"}
    payload = {"unit_id": "ps001.v001.a", "candidates": [candidate]}
    assert translation._septuagint_basis_errors(payload) == []
    monkeypatch.setattr(translation.rendering_service, "create_rendering", lambda **kw: kw)
    monkeypatch.setattr(translation, "get_guidance", lambda *args: "")
    rendering = translation._create_rendering(
        {
            "layer": "lyric",
            "thread_id": "test",
            "run_id": "test",
            "prompt_template_version": "test",
        },
        "ps001.v001.a",
        candidate,
        "test",
    )
    assert rendering["status"] == "proposed"
    assert rendering["provenance"]["greek_generation_source"]["manifest_sha256"]


def test_source_switch_during_context_read_is_rejected(approved, monkeypatch):
    load = greek.greek_preview_service.load_preview

    def switched():
        result = load()
        result["manifest_sha256"] = "0" * 64
        return result

    monkeypatch.setattr(greek.greek_preview_service, "load_preview", switched)
    with pytest.raises(LicensePolicyError, match="approval changed"):
        greek.context("ps001")


@pytest.mark.parametrize("change", ["revision", "text", "tokens", "language", "identity", "target"])
def test_mismatched_provenance_is_rejected(approved, change):
    candidate = deepcopy(approved)
    target = "ps001.v001.a"
    if change == "revision":
        candidate["translation_basis"]["source_version"] = "r0002"
    elif change == "text":
        candidate["source_anchor"]["source_text"] += " invented"
    elif change == "tokens":
        candidate["source_anchor"]["token_ids"].pop()
    elif change == "language":
        candidate["translation_basis"]["source_language"] = "he"
    elif change == "identity":
        candidate["translation_basis"]["source_ids"] = ["lxx"]
    else:
        target = "ps001.v002.a"
    with pytest.raises(LicensePolicyError):
        basis.require_generation_basis_available(candidate, target)


def test_revocation_and_warm_source_tampering_block_saved_candidate(approved, staged, tmp_path):  # noqa: F811
    basis.require_generation_basis_available(approved, "ps001.v001.a")
    unit_file = next((staged / "psalms").rglob("*.json"))
    original = unit_file.read_bytes()
    unit_file.write_bytes(original + b" ")
    with pytest.raises((ValueError, LicensePolicyError)):
        basis.require_generation_basis_available(approved, "ps001.v001.a")
    unit_file.write_bytes(original)
    path = tmp_path / "content/source_registry.json"
    registry = json.loads(path.read_text())
    registry["sources"][0]["components"]["text"]["status"] = "revoked"
    study_snapshot_service.publish_source_policy(
        registry,
        expected_revision=policy.policy_revision(),
        created_by="test",
        rationale="Withdraw test permission",
    )
    with pytest.raises(LicensePolicyError):
        basis.require_generation_basis_available(approved, "ps001.v001.a")
