from app.core.license_rules import evaluate_manifest


def test_restricted_witness_is_not_allowed_for_export_when_flagged() -> None:
    result = evaluate_manifest(
        {
            "source_id": "sefaria",
            "license": "Custom-Restricted-Witness",
            "allowed_for_generation": False,
            "allowed_for_export": True,
        }
    )
    assert "forbidden_for_export" in result["warnings"]
    assert result["allowed"] is False


def test_known_public_license_passes() -> None:
    result = evaluate_manifest(
        {
            "source_id": "uxlc",
            "license": "Public Domain",
            "allowed_for_generation": True,
            "allowed_for_export": True,
        }
    )
    assert result["allowed"] is True
    assert result["warnings"] == []
