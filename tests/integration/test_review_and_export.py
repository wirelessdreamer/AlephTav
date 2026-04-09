import pytest

from app.core.errors import ReviewRequiredError
from app.services import export_service, rendering_service


def test_review_gate_blocks_unreviewed_canonical_promotion() -> None:
    with pytest.raises(ReviewRequiredError):
        rendering_service.promote_rendering(
            "rnd.ps023.v001.a.lyric.alt.0001",
            reviewer="tester",
            reviewer_role="release reviewer",
        )


def test_release_export_generates_bundle() -> None:
    destination = export_service.export_release("v0.1.0")
    assert (destination / "text.json").exists()
    assert (destination / "AUDIT_REPORT.json").exists()
    assert (destination / "OPEN_CONCERNS.md").exists()
