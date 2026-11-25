from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app
from app.core.errors import ReviewRequiredError
from app.services import registry_service

runner = CliRunner()
UNIT_ID = "ps001.v001.a"


def test_add_alternate_creates_an_audited_unreviewed_proposal() -> None:
    before = registry_service.load_unit(UNIT_ID)
    result = runner.invoke(
        app,
        ["add-alternate", UNIT_ID, "literal", "Blessed is the man", "Another literal draft"],
    )

    assert result.exit_code == 0, result.exception or result.output
    rendering = json.loads(result.output)
    assert rendering["status"] == "proposed"
    assert rendering["rationale"] == "Another literal draft"
    assert rendering["provenance"]["generator"] == "cli:add-alternate"
    assert rendering["review_signoff"]["approval_count"] == 0
    assert rendering["review_signoff"]["publication_ready"] is False

    unit = registry_service.load_unit(UNIT_ID)
    assert rendering in unit["renderings"]
    assert rendering["rendering_id"] in unit["alternate_rendering_ids"]
    assert unit["canonical_rendering_ids"] == before["canonical_rendering_ids"]
    # Creation refreshes derived alignment/review summaries, not canonical content.
    for canonical_id in before["canonical_rendering_ids"]:
        prior = next(item for item in before["renderings"] if item["rendering_id"] == canonical_id)
        current = next(item for item in unit["renderings"] if item["rendering_id"] == canonical_id)
        derived_fields = {"alignment_ids", "review_signoff"}
        assert {key: value for key, value in current.items() if key not in derived_fields} == {
            key: value for key, value in prior.items() if key not in derived_fields
        }
    assert unit["alignments"] == before["alignments"]
    assert unit["review_decisions"] == before["review_decisions"]
    assert len(unit["audit_records"]) == len(before["audit_records"]) + 1
    audit = unit["audit_records"][-1]
    assert audit["entity_id"] == rendering["rendering_id"]
    assert audit["change_type"] == "create"
    assert audit["created_by"] == "cli:add-alternate"

    listed = runner.invoke(app, ["list-alternates", UNIT_ID])
    assert listed.exit_code == 0, listed.exception or listed.output
    assert rendering in json.loads(listed.output)


def test_demote_canonical_refuses_without_mutating_content_or_audit() -> None:
    unit = registry_service.load_unit(UNIT_ID)
    canonical_id = unit["canonical_rendering_ids"][0]
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    result = runner.invoke(app, ["demote-canonical", canonical_id])

    assert result.exit_code != 0
    assert isinstance(result.exception, ReviewRequiredError)
    assert path.read_bytes() == before


def test_promote_alternate_refuses_an_unreviewed_cli_proposal() -> None:
    created = runner.invoke(
        app,
        ["add-alternate", UNIT_ID, "literal", "Blessed is the man", "Unreviewed candidate"],
    )
    assert created.exit_code == 0, created.exception or created.output
    rendering_id = json.loads(created.output)["rendering_id"]
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    result = runner.invoke(app, ["promote-alternate", rendering_id])

    assert result.exit_code != 0
    assert isinstance(result.exception, ReviewRequiredError)
    assert path.read_bytes() == before
