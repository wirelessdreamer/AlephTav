from app.core.ids import alignment_id, ensure_id, issue_link_id, pr_link_id, rendering_id


def test_id_patterns_accept_expected_values() -> None:
    assert ensure_id("project_id", "proj.main") == "proj.main"
    assert ensure_id("psalm_id", "ps023") == "ps023"
    assert ensure_id("unit_id", "ps023.v001.a") == "ps023.v001.a"


def test_generated_ids_follow_required_formats() -> None:
    assert alignment_id("ps023.v001.a", "literal", []) == "aln.ps023.v001.a.literal.0001"
    assert rendering_id("ps023.v001.a", "lyric", "alt", []) == "rnd.ps023.v001.a.lyric.alt.0001"
    assert issue_link_id(123) == "iss.000123"
    assert pr_link_id(456) == "pr.000456"
