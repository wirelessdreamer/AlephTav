from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_settings
from app.services import concordance_service, ingest_service, registry_service, report_service


def bootstrap_fixture_repo() -> Path:
    settings = get_settings()
    for path in (settings.content_dir, settings.reports_dir):
        shutil.rmtree(path, ignore_errors=True)
    settings.db_path.unlink(missing_ok=True)
    registry_service.bootstrap_project()
    ingest_service.import_fixture_psalms()
    concordance_service.rebuild_indexes()
    report_service.generate_audit_reports()
    return settings.root_dir
