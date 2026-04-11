from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    content_dir: Path
    psalms_dir: Path
    data_dir: Path
    raw_dir: Path
    normalized_dir: Path
    derived_dir: Path
    indexes_dir: Path
    caches_dir: Path
    schemas_dir: Path
    reports_dir: Path
    audit_reports_dir: Path
    release_reports_dir: Path
    project_file: Path
    db_path: Path
    assistant_settings_file: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    settings = Settings(
        root_dir=root,
        content_dir=root / "content",
        psalms_dir=root / "content" / "psalms",
        data_dir=root / "data",
        raw_dir=root / "data" / "raw",
        normalized_dir=root / "data" / "normalized",
        derived_dir=root / "data" / "derived",
        indexes_dir=root / "data" / "derived" / "indexes",
        caches_dir=root / "data" / "derived" / "caches",
        schemas_dir=root / "schemas",
        reports_dir=root / "reports",
        audit_reports_dir=root / "reports" / "audit",
        release_reports_dir=root / "reports" / "release",
        project_file=root / "content" / "project.json",
        db_path=root / "data" / "derived" / "indexes" / "workbench.sqlite3",
        assistant_settings_file=root / "data" / "derived" / "caches" / "assistant_settings.json",
    )
    for path in (
        settings.content_dir,
        settings.psalms_dir,
        settings.raw_dir,
        settings.normalized_dir,
        settings.indexes_dir,
        settings.caches_dir,
        settings.audit_reports_dir,
        settings.release_reports_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return settings
