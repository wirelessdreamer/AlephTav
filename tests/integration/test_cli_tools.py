"""`psalms-workbench tool`: every MCP tool from the command line, stamped as CLI work."""

from __future__ import annotations

import json
from typing import Any

import anyio
import pytest
from typer.testing import CliRunner

from app.api import mcp_server
from app.cli import app
from app.core.config import get_settings
from app.services import registry_service

runner = CliRunner()
PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    get_settings().collections_file.unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)
    get_settings().collections_file.unlink(missing_ok=True)


def _tool(name: str, *arguments: str) -> Any:
    result = runner.invoke(app, ["tool", "call", name, *arguments])
    assert result.exit_code == 0, result.exception or result.output
    return json.loads(result.output)


def test_every_mcp_tool_is_listed() -> None:
    result = runner.invoke(app, ["tool", "list"])

    assert result.exit_code == 0, result.exception or result.output
    listed = {line.split()[0] for line in result.output.splitlines()}
    assert listed == {tool.name for tool in anyio.run(mcp_server.server.list_tools)}


def test_describe_shows_a_tools_arguments() -> None:
    result = runner.invoke(app, ["tool", "describe", "get_unit"])

    assert result.exit_code == 0, result.exception or result.output
    assert '"unit_id"' in result.output


def test_writes_and_reviews_are_stamped_as_cli_not_mcp() -> None:
    rendering = _tool(
        "create_rendering",
        f"unit_id={UNIT_ID}",
        "layer=lyric",
        "text=Happy the one",
        "rationale=r",
        "created_by=claude",
    )
    decision = _tool(
        "review_rendering",
        f"target_id={rendering['rendering_id']}",
        "decision=approve",
        "reviewer=alice",
        "reviewer_role=lyric reviewer",
    )

    assert decision["reviewer"] == "cli:alice"
    audit = _tool("get_unit_audit", f"unit_id={UNIT_ID}")
    assert any(
        record["entity_id"] == rendering["rendering_id"] and record["created_by"] == "cli:claude"
        for record in audit
    )
    # The CLI's stamp does not leak into later MCP calls in the same process.
    assert mcp_server._mcp("claude") == "mcp:claude"


def test_refusals_exit_nonzero_with_their_reason() -> None:
    refused = runner.invoke(app, ["tool", "call", "get_unit", "unit_id=nope"])
    assert refused.exit_code == 1
    assert "nope" in refused.output

    malformed = runner.invoke(app, ["tool", "call", "get_unit", "nope"])
    assert malformed.exit_code == 2

    unknown = runner.invoke(app, ["tool", "describe", "no_such_tool"])
    assert unknown.exit_code == 1
