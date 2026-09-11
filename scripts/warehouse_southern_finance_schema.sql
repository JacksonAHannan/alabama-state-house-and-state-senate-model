PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (14,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Southern candidate-cycle finance, incumbency evidence, identity bridge, and race marts');

CREATE TABLE IF NOT EXISTS source_southern_finance_file (
    finance_source_registration_id TEXT PRIMARY KEY,
    warehouse_source_file_id TEXT NOT NULL
      REFERENCES warehouse_source_file(source_file_id),
    manifest_name TEXT NOT NULL,
    manifest_source_file_id TEXT NOT NULL,
    state_code TEXT CHECK (state_code IS NULL OR length(state_code)=2),
    cycle TEXT,
    data_kind TEXT NOT NULL,
    geography_vintage TEXT NOT NULL,
    authoritative_scope TEXT NOT NULL,
    ingest_status TEXT NOT NULL,
    UNIQUE(manifest_name,manifest_source_file_id)
);

CREATE TABLE IF NOT EXISTS source_southern_incumbency_evidence (
    incumbency_evidence_id TEXT PRIMARY KEY,
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    contract_version INTEGER NOT NULL,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    cycle INTEGER NOT NULL,
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    incumbent_name TEXT NOT NULL,
    party_family TEXT NOT NULL
      CHECK (party_family IN ('democratic','republican','independent','other','unknown')),
    incumbent_ran INTEGER CHECK (incumbent_ran IS NULL OR incumbent_ran IN (0,1)),
    open_seat INTEGER CHECK (open_seat IS NULL OR open_seat IN (0,1)),
    election_status TEXT,
    won_general INTEGER CHECK (won_general IS NULL OR won_general IN (0,1)),
    method TEXT NOT NULL,
    roster_source_url TEXT,
    ballotpedia_url TEXT,
    wikipedia_url TEXT,
    coverage_status TEXT NOT NULL,
    notes TEXT,
    UNIQUE(source_file_id,cycle,state_code,chamber,district,incumbent_name)
);

CREATE TABLE IF NOT EXISTS source_southern_candidate_cycle_finance (
    finance_candidate_cycle_id TEXT PRIMARY KEY,
    contract_version INTEGER NOT NULL,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    party_family TEXT NOT NULL
      CHECK (party_family IN ('democratic','republican','independent','other','unknown')),
    candidate_name TEXT NOT NULL,
    candidate_name_original TEXT NOT NULL,
    provider_candidate_name TEXT,
    committee_id TEXT,
    total_fundraising REAL,
    cash_contributions REAL,
    other_receipts REAL,
    in_kind_contributions REAL,
    loans_received REAL,
    expenditures REAL,
    ending_cash REAL,
    report_count INTEGER,
    period_start TEXT,
    period_end TEXT,
    finance_observation_status TEXT NOT NULL,
    finance_observed INTEGER NOT NULL CHECK (finance_observed IN (0,1)),
    aggregation_status TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_measure TEXT NOT NULL,
    provider_source_path TEXT,
    source_reported_total REAL,
    upstream_data_run_id TEXT,
    upstream_generated_at_utc TEXT,
    upstream_code_sha256 TEXT,
    upstream_config_id TEXT,
    UNIQUE(state_code,cycle,chamber,district,party_family)
);

CREATE TABLE IF NOT EXISTS bridge_southern_finance_record_source (
    finance_candidate_cycle_id TEXT NOT NULL
      REFERENCES source_southern_candidate_cycle_finance(finance_candidate_cycle_id)
      ON DELETE CASCADE,
    finance_source_registration_id TEXT NOT NULL
      REFERENCES source_southern_finance_file(finance_source_registration_id),
    dependency_role TEXT NOT NULL CHECK (dependency_role IN ('canonical_input','raw_evidence')),
    PRIMARY KEY(finance_candidate_cycle_id,finance_source_registration_id,dependency_role)
);

CREATE TABLE IF NOT EXISTS bridge_southern_finance_candidate_identity (
    finance_candidate_cycle_id TEXT PRIMARY KEY
      REFERENCES source_southern_candidate_cycle_finance(finance_candidate_cycle_id)
      ON DELETE CASCADE,
    candidate_result_id TEXT NOT NULL
      REFERENCES canonical_southern_legislative_candidate_election(candidate_result_id),
    incumbency_evidence_id TEXT
      REFERENCES source_southern_incumbency_evidence(incumbency_evidence_id),
    match_method TEXT NOT NULL,
    name_score REAL NOT NULL CHECK (name_score BETWEEN 0 AND 100),
    match_margin REAL NOT NULL,
    incumbency_support INTEGER NOT NULL CHECK (incumbency_support IN (0,1)),
    review_status TEXT NOT NULL CHECK (review_status IN ('accepted','review','rejected')),
    rationale TEXT NOT NULL,
    UNIQUE(candidate_result_id)
);

CREATE TABLE IF NOT EXISTS mart_southern_candidate_cycle_finance (
    candidate_result_id TEXT PRIMARY KEY
      REFERENCES canonical_southern_legislative_candidate_election(candidate_result_id),
    finance_candidate_cycle_id TEXT NOT NULL UNIQUE
      REFERENCES source_southern_candidate_cycle_finance(finance_candidate_cycle_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL,
    district TEXT NOT NULL,
    party_family TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    total_fundraising REAL,
    cash_contributions REAL,
    other_receipts REAL,
    in_kind_contributions REAL,
    loans_received REAL,
    expenditures REAL,
    ending_cash REAL,
    finance_observation_status TEXT NOT NULL,
    finance_observed INTEGER NOT NULL CHECK (finance_observed IN (0,1)),
    source_name TEXT NOT NULL,
    source_measure TEXT NOT NULL,
    match_method TEXT NOT NULL,
    match_score REAL NOT NULL,
    incumbency_support INTEGER NOT NULL CHECK (incumbency_support IN (0,1))
);

CREATE TABLE IF NOT EXISTS mart_southern_race_finance (
    state_code TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL,
    district TEXT NOT NULL,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    democratic_candidate_result_id TEXT
      REFERENCES canonical_southern_legislative_candidate_election(candidate_result_id),
    republican_candidate_result_id TEXT
      REFERENCES canonical_southern_legislative_candidate_election(candidate_result_id),
    democratic_finance_candidate_cycle_id TEXT
      REFERENCES source_southern_candidate_cycle_finance(finance_candidate_cycle_id),
    republican_finance_candidate_cycle_id TEXT
      REFERENCES source_southern_candidate_cycle_finance(finance_candidate_cycle_id),
    democratic_fundraising REAL,
    republican_fundraising REAL,
    democratic_finance_status TEXT,
    republican_finance_status TEXT,
    finance_complete INTEGER NOT NULL CHECK (finance_complete IN (0,1)),
    log_fundraising_ratio_d_to_r REAL,
    smoothing_constant REAL NOT NULL,
    race_finance_status TEXT NOT NULL,
    PRIMARY KEY(state_code,cycle,chamber,district)
);

CREATE TABLE IF NOT EXISTS qa_southern_finance_coverage (
    state_code TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_candidate_rows INTEGER NOT NULL,
    observed_candidate_rows INTEGER NOT NULL,
    accepted_identity_matches INTEGER NOT NULL,
    review_identity_matches INTEGER NOT NULL,
    unmatched_identity_rows INTEGER NOT NULL,
    observed_accepted_matches INTEGER NOT NULL,
    candidate_finance_coverage REAL NOT NULL,
    identity_match_coverage REAL NOT NULL,
    warehouse_observed_coverage REAL NOT NULL,
    democratic_republican_races INTEGER NOT NULL,
    finance_complete_races INTEGER NOT NULL,
    race_finance_coverage REAL,
    PRIMARY KEY(state_code,cycle)
);

CREATE INDEX IF NOT EXISTS southern_finance_candidate_scope
  ON source_southern_candidate_cycle_finance(state_code,cycle,chamber,district,party_family);
CREATE INDEX IF NOT EXISTS southern_incumbency_scope
  ON source_southern_incumbency_evidence(state_code,cycle,chamber,district,party_family);
CREATE INDEX IF NOT EXISTS southern_finance_identity_candidate
  ON bridge_southern_finance_candidate_identity(candidate_result_id,review_status);

DROP VIEW IF EXISTS fact_southern_candidate_cycle_finance;
CREATE VIEW fact_southern_candidate_cycle_finance AS
SELECT * FROM mart_southern_candidate_cycle_finance;

DROP VIEW IF EXISTS fact_southern_race_finance;
CREATE VIEW fact_southern_race_finance AS
SELECT * FROM mart_southern_race_finance;
