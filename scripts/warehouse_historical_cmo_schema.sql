PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (4,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Historical CMO source results, candidate aggregates, and cycle input coverage');

CREATE TABLE IF NOT EXISTS source_historical_legislative_county_result (
    result_id TEXT PRIMARY KEY,
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    year INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('house','senate')),
    district INTEGER NOT NULL,
    county TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    party TEXT NOT NULL CHECK (party IN ('D','R')),
    votes REAL NOT NULL CHECK (votes >= 0),
    source_sheet TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_historical_statewide_county_result (
    result_id TEXT PRIMARY KEY,
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    year INTEGER NOT NULL,
    office TEXT NOT NULL,
    county TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    party TEXT NOT NULL CHECK (party IN ('D','R')),
    votes REAL NOT NULL CHECK (votes >= 0),
    source_sheet TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_historical_candidate_result (
    historical_candidate_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    chamber TEXT NOT NULL,
    district INTEGER NOT NULL,
    party TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    votes REAL NOT NULL,
    winner INTEGER NOT NULL CHECK (winner IN (0,1)),
    counties_reported INTEGER NOT NULL,
    source_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_historical_incumbency_evidence (
    historical_candidate_id TEXT PRIMARY KEY REFERENCES mart_historical_candidate_result(historical_candidate_id),
    incumbent_status TEXT NOT NULL CHECK (incumbent_status IN ('supported_prior_winner','not_supported','unknown')),
    prior_year INTEGER,
    prior_candidate_name TEXT,
    match_method TEXT,
    evidence_note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_cmo_cycle_input_coverage (
    cycle INTEGER NOT NULL,
    input_domain TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('available','partial','missing','not_applicable')),
    source_locator TEXT,
    warehouse_object TEXT,
    limitation TEXT,
    required_for_specification TEXT NOT NULL,
    PRIMARY KEY (cycle,input_domain)
);

