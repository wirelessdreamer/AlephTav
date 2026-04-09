from scripts.validate_content import validate_all_content


def test_seeded_content_validates_without_errors() -> None:
    result = validate_all_content()
    assert result["errors"] == []
    assert any(item.endswith("content/project.json") for item in result["validated_files"])
