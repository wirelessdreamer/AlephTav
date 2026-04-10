from app.services import registry_service
from scripts.validate_content import validate_all_content


def test_seeded_content_validates_without_errors() -> None:
    result = validate_all_content()
    assert result["errors"] == []
    assert any(item.endswith("content/project.json") for item in result["validated_files"])


def test_validation_rejects_canonical_high_severity_drift() -> None:
    _, unit = registry_service.update_unit("ps023.v001.a", lambda existing: existing)
    for rendering in unit["renderings"]:
        if rendering["rendering_id"] == "rnd.ps023.v001.a.lyric.alt.0001":
            rendering["status"] = "canonical"
            rendering["metrics"] = {
                "syllables": 7,
                "syllable_count": 7,
                "stress_approximation": 0.58,
                "line_length": 6,
                "repetition_score": 0.0,
                "singability_score": 0.74,
                "parallelism_preservation_score": 0.81,
            }
            rendering["drift_flags"] = [
                {
                    "code": "added_doctrine",
                    "severity": "high",
                    "confidence": 0.99,
                    "message": "Injected doctrine absent from source.",
                }
            ]
    registry_service.save_unit(unit)

    result = validate_all_content()

    assert any("unresolved high-severity drift" in error for error in result["errors"])
