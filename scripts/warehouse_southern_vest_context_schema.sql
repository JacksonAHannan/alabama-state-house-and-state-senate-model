PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (19,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'VEST 2016 precinct presidential results and matched precinct geometry');

CREATE TABLE IF NOT EXISTS source_southern_vest_context_file (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    manifest_source_file_id TEXT NOT NULL UNIQUE,
    dataset_doi TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    dataverse_file_id INTEGER NOT NULL UNIQUE,
    state_code TEXT NOT NULL UNIQUE CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL CHECK(election_cycle=2016),
    geography_vintage TEXT NOT NULL,
    authoritative_scope TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    normalization_status TEXT NOT NULL CHECK(normalization_status IN ('normalized','review'))
);

CREATE TABLE IF NOT EXISTS qa_southern_vest_context_ingest (
    source_file_id TEXT PRIMARY KEY REFERENCES source_southern_vest_context_file(source_file_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    input_features INTEGER NOT NULL CHECK(input_features>=0),
    normalized_precincts INTEGER NOT NULL CHECK(normalized_precincts>=0),
    repaired_input_geometries INTEGER NOT NULL CHECK(repaired_input_geometries>=0),
    dem_votes REAL NOT NULL CHECK(dem_votes>=0),
    rep_votes REAL NOT NULL CHECK(rep_votes>=0),
    other_votes REAL NOT NULL CHECK(other_votes>=0),
    result_geometry_links INTEGER NOT NULL CHECK(result_geometry_links>=0),
    reconciliation_status TEXT NOT NULL CHECK(reconciliation_status IN ('exact','review')),
    note TEXT
);
