from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from app.services import concordance_service, ingest_service, registry_service, report_service


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def seeded_repo() -> None:
    for relative in ["content", "data", "reports"]:
        shutil.rmtree(ROOT / relative, ignore_errors=True)
    registry_service.bootstrap_project()
    ingest_service.import_fixture_psalms()
    concordance_service.rebuild_indexes()
    report_service.generate_audit_reports()
