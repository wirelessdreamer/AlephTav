from __future__ import annotations

import shutil
import os
from pathlib import Path

from app.core.config import get_settings
from app.services import concordance_service, ingest_service, registry_service, report_service, visual_flow_service

REAL_ROOT = Path(__file__).resolve().parents[1]


def _assert_not_real_workspace() -> None:
    settings = get_settings()
    if os.environ.get("PYTEST_CURRENT_TEST") and settings.root_dir.resolve() == REAL_ROOT.resolve():
        raise RuntimeError(
            "Refusing to bootstrap fixture data in the real workspace. "
            "Set ALEPHTAV_ROOT_DIR to an isolated test workspace before running tests."
        )


def bootstrap_fixture_repo() -> Path:
    _assert_not_real_workspace()
    settings = get_settings()
    for path in (settings.content_dir, settings.reports_dir):
        shutil.rmtree(path, ignore_errors=True)
    settings.db_path.unlink(missing_ok=True)
    settings.assistant_settings_file.unlink(missing_ok=True)
    registry_service.bootstrap_project()
    ingest_service.import_fixture_psalms()
    concordance_service.rebuild_indexes()
    visual_flow_service.rebuild_vector_index()
    report_service.generate_audit_reports()
    return settings.root_dir
