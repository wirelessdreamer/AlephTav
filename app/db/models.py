TOKEN_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS token_index (
    token_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL,
    psalm_id TEXT NOT NULL,
    ref TEXT NOT NULL,
    surface TEXT NOT NULL,
    normalized TEXT NOT NULL,
    transliteration TEXT,
    lemma TEXT,
    strong TEXT,
    morph_code TEXT,
    morph_readable TEXT,
    part_of_speech TEXT,
    syntax_role TEXT,
    semantic_role TEXT,
    referent TEXT,
    word_sense TEXT
);
"""

UNIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS unit_index (
    unit_id TEXT PRIMARY KEY,
    psalm_id TEXT NOT NULL,
    ref TEXT NOT NULL,
    status TEXT NOT NULL,
    source_hebrew TEXT NOT NULL
);
"""

RENDERING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rendering_index (
    rendering_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    status TEXT NOT NULL,
    text_value TEXT NOT NULL
);
"""

ALIGNMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS alignment_index (
    alignment_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    alignment_type TEXT NOT NULL,
    confidence REAL NOT NULL
);
"""

JOB_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    status TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    model_profile TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    seed INTEGER NOT NULL,
    runtime_metadata TEXT NOT NULL
);
"""
