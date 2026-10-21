from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Literal

from app.core.config import get_settings
from app.db.models import (
    ALIGNMENT_TABLE_SQL,
    COMPARISON_TABLE_SQL,
    JOB_TABLE_SQL,
    LEXICAL_STATE_TABLE_SQL,
    MISSING_ENRICHMENT_TABLE_SQL,
    RENDERING_TABLE_SQL,
    TOKEN_ENRICHMENT_TABLE_SQL,
    TOKEN_OCCURRENCE_TABLE_SQL,
    TOKEN_TABLE_SQL,
    UNIT_TABLE_SQL,
)


class _ScopedConnection(sqlite3.Connection):
    """Connection whose ``with`` block also closes the handle.

    ``sqlite3.Connection.__exit__`` only commits or rolls back; it leaves the
    handle open. On Windows that keeps a lock on the database file, so a later
    ``Path.unlink()`` (as the fixture bootstrap does) raises WinError 32.
    """

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def catalog_path() -> Path:
    settings = get_settings()
    pointer = settings.indexes_dir / "active_catalog.json"
    if pointer.exists():
        from app.services.foundation_contract_service import workspace_path

        return workspace_path(json.loads(pointer.read_text(encoding="utf-8"))["path"])
    return settings.db_path


def connect_catalog(path: Path, *, writable: bool = False) -> sqlite3.Connection:
    if writable:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, factory=_ScopedConnection)
    else:
        connection = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro", uri=True, factory=_ScopedConnection
        )
    connection.row_factory = sqlite3.Row
    return connection


def get_connection() -> sqlite3.Connection:
    """Read-only catalog connection; published files are never replaced/deleted."""
    return connect_catalog(catalog_path())


def init_catalog(path: Path) -> None:
    with connect_catalog(path, writable=True) as connection:
        connection.executescript(
            TOKEN_TABLE_SQL
            + UNIT_TABLE_SQL
            + RENDERING_TABLE_SQL
            + ALIGNMENT_TABLE_SQL
            + COMPARISON_TABLE_SQL
            + TOKEN_OCCURRENCE_TABLE_SQL
            + TOKEN_ENRICHMENT_TABLE_SQL
            + MISSING_ENRICHMENT_TABLE_SQL
        )


def init_db() -> None:
    """Compatibility initializer; catalog rebuilding uses a fresh staging file."""
    init_catalog(get_settings().db_path)


class _OperationalConnection(_ScopedConnection):
    _workspace_lock: object

    def close(self) -> None:
        try:
            super().close()
        finally:
            lock = getattr(self, "_workspace_lock", None)
            if lock is not None:
                self._workspace_lock = None
                lock.__exit__(None, None, None)


def _operational_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        JOB_TABLE_SQL
        + LEXICAL_STATE_TABLE_SQL
        + """
        CREATE TABLE IF NOT EXISTS operational_migrations (
            migration_id TEXT PRIMARY KEY, source_path TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL
        );
    """
    )


def get_operational_connection() -> sqlite3.Connection:
    from app.services.immutable_file_service import workspace_lock

    settings = get_settings()
    lock = workspace_lock(settings.data_dir / "local" / "operational-migration.lock")
    lock.__enter__()
    connection = None
    try:
        # Preserve the old authority until an explicit offline cutover. New
        # catalog publication retains this file, so existing jobs/card state
        # remain usable while operators arrange writer quiescence.
        legacy_mode = False
        if settings.db_path.exists():
            with connect_catalog(settings.db_path) as legacy:
                tables = {
                    r[0]
                    for r in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                legacy_mode = bool(tables & {"generation_jobs", "lexical_card_state"})
        if legacy_mode and settings.operational_db_path.exists():
            with connect_catalog(settings.operational_db_path) as durable:
                tables = {
                    r[0]
                    for r in durable.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if "operational_migrations" in tables:
                    legacy_mode = (
                        durable.execute(
                            "SELECT 1 FROM operational_migrations WHERE migration_id='mixed-v1'"
                        ).fetchone()
                        is None
                    )
        target = settings.db_path if legacy_mode else settings.operational_db_path
        settings.operational_db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(target, factory=_OperationalConnection)
        connection.row_factory = sqlite3.Row
        connection._workspace_lock = lock
        _operational_tables(connection)
        return connection
    except BaseException:
        if connection is not None:
            connection.close()
        else:
            lock.__exit__(None, None, None)
        raise


def migrate_operational_state(*, writers_quiesced: bool = False) -> dict[str, int]:
    """Explicit offline cutover; SQLite write lock blocks legacy mixed-DB writers.

    Callers must stop old API/job processes first. Updated operational connections
    hold the same OS lock for their lifetime, so their writes cannot race copying.
    A durable transaction marker makes retry after interruption idempotent.
    """
    from app.services.immutable_file_service import workspace_lock

    if not writers_quiesced:
        raise RuntimeError("Stop API/job writers before operational-state migration")
    settings = get_settings()
    with workspace_lock(settings.data_dir / "local" / "operational-migration.lock"):
        settings.operational_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.operational_db_path) as destination:
            _operational_tables(destination)
            if destination.execute(
                "SELECT 1 FROM operational_migrations WHERE migration_id='mixed-v1'"
            ).fetchone():
                return {"migrated": 0}
            if not settings.db_path.exists():
                destination.execute(
                    "INSERT INTO operational_migrations VALUES ('mixed-v1', ?, 'empty')",
                    (str(settings.db_path),),
                )
                return {"migrated": 0}
            with sqlite3.connect(settings.db_path) as source:
                source.execute("BEGIN IMMEDIATE")
                backup = settings.operational_db_path.with_name("legacy-workbench.backup.sqlite3")
                if not backup.exists():
                    # Back up through a separate read connection while this one
                    # holds the writer lock, retaining an internally coherent DB.
                    with (
                        sqlite3.connect(settings.db_path) as reader,
                        sqlite3.connect(backup) as target,
                    ):
                        reader.backup(target)
                destination.execute("BEGIN IMMEDIATE")
                tables = {
                    r[0]
                    for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                copied = 0
                for table in ("generation_jobs", "lexical_card_state"):
                    if table not in tables:
                        continue
                    rows = source.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                    if destination.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                        raise RuntimeError(
                            "Operational destination is populated without a migration marker"
                        )
                    if rows:
                        placeholders = ",".join("?" for _ in rows[0])
                        destination.executemany(
                            f"INSERT INTO {table} VALUES ({placeholders})", rows
                        )
                    if destination.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall() != rows:
                        raise RuntimeError("Operational migration verification failed")
                    copied += len(rows)
                destination.execute(
                    "INSERT INTO operational_migrations VALUES ('mixed-v1', ?, ?)",
                    (str(settings.db_path), str(copied)),
                )
            return {"migrated": copied}
