PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS warehouse_schema_version (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse_build_run (
    build_run_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'validated', 'failed')),
    code_commit TEXT,
    configuration_json TEXT NOT NULL,
    validation_json TEXT
);

CREATE TABLE IF NOT EXISTS warehouse_source_file (
    source_file_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    local_path TEXT NOT NULL UNIQUE,
    original_url TEXT,
    retrieved_at_utc TEXT,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    media_type TEXT,
    license TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'registered'
      CHECK (extraction_status IN ('registered', 'normalized', 'failed', 'not_applicable')),
    authoritative_scope TEXT
);

CREATE TABLE IF NOT EXISTS warehouse_table_registry (
    table_name TEXT PRIMARY KEY,
    layer TEXT NOT NULL CHECK (layer IN ('control', 'source', 'canonical', 'mart', 'qa', 'publication')),
    owner_script TEXT NOT NULL,
    primary_key_description TEXT,
    authority_policy TEXT,
    lifecycle TEXT NOT NULL CHECK (lifecycle IN ('append', 'replace', 'view', 'export')),
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse_asset (
    asset_id TEXT PRIMARY KEY,
    asset_kind TEXT NOT NULL CHECK (asset_kind IN ('raw_file', 'database_table', 'database_view', 'csv_export', 'publication')),
    layer TEXT NOT NULL CHECK (layer IN ('raw', 'source', 'canonical', 'mart', 'qa', 'publication')),
    locator TEXT NOT NULL UNIQUE,
    owner_script TEXT,
    key_description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'compatibility', 'planned', 'retired')),
    replacement_asset_id TEXT REFERENCES warehouse_asset(asset_id),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS warehouse_asset_lineage (
    upstream_asset_id TEXT NOT NULL REFERENCES warehouse_asset(asset_id),
    downstream_asset_id TEXT NOT NULL REFERENCES warehouse_asset(asset_id),
    dependency_type TEXT NOT NULL CHECK (dependency_type IN ('normalizes', 'reconciles', 'features', 'exports', 'validates')),
    PRIMARY KEY (upstream_asset_id, downstream_asset_id, dependency_type)
);

CREATE TABLE IF NOT EXISTS warehouse_manual_adjudication (
    adjudication_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    evidence_locator TEXT,
    review_status TEXT NOT NULL CHECK (review_status IN ('proposed', 'approved', 'rejected', 'superseded')),
    decided_at_utc TEXT NOT NULL,
    supersedes_adjudication_id TEXT REFERENCES warehouse_manual_adjudication(adjudication_id)
);

INSERT OR IGNORE INTO warehouse_schema_version(version, applied_at_utc, description)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
        'Initial project warehouse control plane and data contracts');

