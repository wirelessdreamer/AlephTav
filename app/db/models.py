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
    stem TEXT,
    syntax_role TEXT,
    semantic_role TEXT,
    referent TEXT,
    word_sense TEXT,
    occurrence_index INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_token_index_lemma ON token_index(lemma);
CREATE INDEX IF NOT EXISTS idx_token_index_strong ON token_index(strong);
CREATE INDEX IF NOT EXISTS idx_token_index_surface ON token_index(surface);
CREATE INDEX IF NOT EXISTS idx_token_index_normalized ON token_index(normalized);
CREATE INDEX IF NOT EXISTS idx_token_index_morph_code ON token_index(morph_code);
CREATE INDEX IF NOT EXISTS idx_token_index_stem ON token_index(stem);
CREATE INDEX IF NOT EXISTS idx_token_index_syntax_role ON token_index(syntax_role);
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

TOKEN_OCCURRENCE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS token_occurrence_index (
    token_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    occurrence_ref TEXT NOT NULL,
    PRIMARY KEY(token_id, scope, occurrence_ref)
);

CREATE INDEX IF NOT EXISTS idx_token_occurrence_scope ON token_occurrence_index(scope, occurrence_ref);
"""

TOKEN_ENRICHMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS token_enrichment_index (
    token_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL,
    available_fields TEXT NOT NULL,
    missing_fields TEXT NOT NULL,
    PRIMARY KEY(token_id, source_id)
);
"""

MISSING_ENRICHMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS missing_enrichment_index (
    token_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    PRIMARY KEY(token_id, source_id, field_name)
);

CREATE INDEX IF NOT EXISTS idx_missing_enrichment_source ON missing_enrichment_index(source_id, field_name);
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
    runtime_metadata TEXT NOT NULL,
    output_payload TEXT
);
"""
