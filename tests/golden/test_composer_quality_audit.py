from __future__ import annotations

from pathlib import Path

import pytest

from tests.composer_quality_support import (
    audit_composer_outputs,
    bootstrap_vendored_repo,
    build_composer_outputs,
    collect_all_unit_ids,
    write_audit_reports,
)


pytestmark = [pytest.mark.no_seeded_repo, pytest.mark.corpus_audit]


def test_full_psalter_composer_audit_writes_report(tmp_path_factory) -> None:
    bootstrap_vendored_repo()
    unit_ids = collect_all_unit_ids()

    outputs = build_composer_outputs(unit_ids, tmp_path_factory.mktemp("composer-audit"))
    report = audit_composer_outputs(outputs)

    json_path = Path("reports/audit/composer_quality_full.json")
    md_path = Path("reports/audit/composer_quality_full.md")
    write_audit_reports(report, json_path, md_path)

    assert report["psalm_count"] == 150
    assert report["unit_count"] >= 2400
    assert json_path.exists()
    assert md_path.exists()
