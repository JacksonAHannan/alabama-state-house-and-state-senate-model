PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (10,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Official Southern election source registry and normalized candidate-election facts');

CREATE TABLE IF NOT EXISTS source_southern_election_file (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER,
    election_date TEXT,
    election_stage_original TEXT,
    geography_vintage TEXT NOT NULL,
    license_or_terms TEXT NOT NULL,
    authoritative_scope TEXT NOT NULL,
    ingest_status TEXT NOT NULL
      CHECK (ingest_status IN ('discovered','acquired','parsed','rejected','superseded')),
    coverage_original TEXT,
    parser_name TEXT,
    parser_message TEXT
);

CREATE TABLE IF NOT EXISTS source_southern_candidate_election (
    candidate_election_id TEXT PRIMARY KEY,
    election_id TEXT NOT NULL,
    contest_id TEXT NOT NULL,
    contract_version INTEGER NOT NULL,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER NOT NULL,
    election_date TEXT NOT NULL,
    election_date_status TEXT NOT NULL CHECK (election_date_status IN ('observed','derived')),
    election_stage TEXT NOT NULL
      CHECK (election_stage IN ('primary','primary_runoff','general','special','special_runoff','other')),
    election_stage_original TEXT NOT NULL,
    office_code TEXT NOT NULL CHECK (office_code IN ('USP','USS','USH','GOV','SLDL','SLDU')),
    office_original TEXT NOT NULL,
    chamber TEXT CHECK (chamber IN ('lower','upper')),
    district_plan_id TEXT,
    geography_vintage TEXT NOT NULL,
    district TEXT,
    district_original TEXT,
    candidate_name TEXT NOT NULL,
    candidate_name_originals_json TEXT NOT NULL,
    party_family TEXT NOT NULL
      CHECK (party_family IN ('democratic','republican','independent','other','unknown')),
    party_original TEXT,
    votes INTEGER NOT NULL CHECK (votes >= 0),
    vote_share REAL CHECK (vote_share IS NULL OR (vote_share >= 0 AND vote_share <= 1)),
    vote_value_status TEXT NOT NULL CHECK (vote_value_status IN ('observed','derived','imputed','unknown','not_applicable')),
    contest_status TEXT NOT NULL,
    observed_candidate_count INTEGER NOT NULL CHECK (observed_candidate_count >= 1),
    reported_geography_count INTEGER NOT NULL CHECK (reported_geography_count >= 1),
    source_coverage TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('passed','review')),
    as_of_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_southern_candidate_result_source (
    candidate_election_id TEXT NOT NULL
      REFERENCES source_southern_candidate_election(candidate_election_id) ON DELETE CASCADE,
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    dependency_role TEXT NOT NULL CHECK (dependency_role IN ('reports','component')),
    PRIMARY KEY(candidate_election_id,source_file_id)
);

CREATE TABLE IF NOT EXISTS qa_southern_election_reconciliation (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    parser_name TEXT NOT NULL,
    input_candidate_rows INTEGER NOT NULL CHECK (input_candidate_rows >= 0),
    output_candidate_rows INTEGER NOT NULL CHECK (output_candidate_rows >= 0),
    input_votes INTEGER CHECK (input_votes >= 0),
    output_votes INTEGER CHECK (output_votes >= 0),
    vote_delta INTEGER,
    reconciliation_status TEXT NOT NULL
      CHECK (reconciliation_status IN ('exact','not_available','rejected')),
    note TEXT
);

CREATE TABLE IF NOT EXISTS qa_southern_election_coverage (
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER,
    acquisition_status TEXT NOT NULL,
    normalization_status TEXT NOT NULL,
    source_files INTEGER NOT NULL CHECK (source_files >= 0),
    candidate_results INTEGER NOT NULL CHECK (candidate_results >= 0),
    limitation TEXT,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    PRIMARY KEY(state_code,cycle)
);

CREATE INDEX IF NOT EXISTS southern_candidate_contest_lookup
  ON source_southern_candidate_election(state_code,cycle,election_stage,office_code,district);
CREATE INDEX IF NOT EXISTS southern_candidate_party_lookup
  ON source_southern_candidate_election(state_code,cycle,party_family);

DROP VIEW IF EXISTS fact_southern_candidate_election;
CREATE VIEW fact_southern_candidate_election AS
SELECT * FROM source_southern_candidate_election
WHERE validation_status='passed';
