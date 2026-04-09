from __future__ import annotations

import sqlite3

from app.core.config import get_settings
from app.db.models import ALIGNMENT_TABLE_SQL, JOB_TABLE_SQL, RENDERING_TABLE_SQL, TOKEN_TABLE_SQL, UNIT_TABLE_SQL


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(TOKEN_TABLE_SQL + UNIT_TABLE_SQL + RENDERING_TABLE_SQL + ALIGNMENT_TABLE_SQL + JOB_TABLE_SQL)
