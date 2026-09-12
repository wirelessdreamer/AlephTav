from __future__ import annotations

import sqlite3

from app.core.config import get_settings
from app.db.models import (
    ALIGNMENT_TABLE_SQL,
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

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool | None:
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.db_path, factory=_ScopedConnection)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS missing_enrichment_index;
            DROP TABLE IF EXISTS token_enrichment_index;
            DROP TABLE IF EXISTS token_occurrence_index;
            DROP TABLE IF EXISTS token_index;
            DROP TABLE IF EXISTS unit_index;
            DROP TABLE IF EXISTS rendering_index;
            DROP TABLE IF EXISTS alignment_index;
            DROP TABLE IF EXISTS lexical_card_state;
            """
            + TOKEN_TABLE_SQL
            + UNIT_TABLE_SQL
            + RENDERING_TABLE_SQL
            + ALIGNMENT_TABLE_SQL
            + TOKEN_OCCURRENCE_TABLE_SQL
            + TOKEN_ENRICHMENT_TABLE_SQL
            + MISSING_ENRICHMENT_TABLE_SQL
            + JOB_TABLE_SQL
            + LEXICAL_STATE_TABLE_SQL
        )
