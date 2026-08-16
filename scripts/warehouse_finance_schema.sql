PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (3,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'DIME finance source, canonical candidate matches, and harmonized resource marts');

CREATE TABLE IF NOT EXISTS source_dime_recipient (
    dime_recipient_cycle_id TEXT PRIMARY KEY,
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    cycle INTEGER NOT NULL,
    bonica_recipient_id TEXT,
    bonica_candidate_id TEXT,
    recipient_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    party_code TEXT,
    party TEXT,
    state TEXT NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('house','senate')),
    district INTEGER NOT NULL,
    total_receipts REAL,
    total_disbursements REAL,
    individual_contributions REAL,
    unitemized_contributions REAL,
    pac_contributions REAL,
    party_contributions REAL,
    candidate_contributions REAL,
    number_givers REAL,
    recipient_cfscore REAL
);

CREATE TABLE IF NOT EXISTS canonical_candidate_finance_match (
    source_name TEXT NOT NULL,
    dime_recipient_cycle_id TEXT NOT NULL REFERENCES source_dime_recipient(dime_recipient_cycle_id),
    canonical_candidate_id TEXT NOT NULL,
    match_method TEXT NOT NULL,
    match_score REAL NOT NULL,
    match_margin REAL NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN ('accepted','review','rejected')),
    PRIMARY KEY (source_name,dime_recipient_cycle_id,canonical_candidate_id)
);

CREATE TABLE IF NOT EXISTS mart_candidate_resources (
    canonical_candidate_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    chamber TEXT NOT NULL,
    district INTEGER NOT NULL,
    party TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    total_resources_raised REAL,
    resource_observation_status TEXT NOT NULL,
    source_name TEXT,
    source_measure TEXT,
    source_candidate_name TEXT,
    match_method TEXT,
    source_authority_rule TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_race_resource_features (
    year INTEGER NOT NULL,
    chamber TEXT NOT NULL,
    district INTEGER NOT NULL,
    dem_resources REAL,
    rep_resources REAL,
    dem_source TEXT,
    rep_source TEXT,
    finance_complete INTEGER NOT NULL CHECK (finance_complete IN (0,1)),
    log_resource_ratio_d_to_r REAL,
    smoothing_constant REAL NOT NULL,
    PRIMARY KEY (year,chamber,district)
);
