PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version, applied_at_utc, description)
VALUES (24, strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Audited Southern presidential provider-conversion corrections');

CREATE TABLE IF NOT EXISTS qa_southern_presidential_result_correction (
  correction_id TEXT PRIMARY KEY,
  build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  evidence_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  state_code TEXT NOT NULL,
  election_cycle INTEGER NOT NULL,
  county_key TEXT NOT NULL,
  correction_method TEXT NOT NULL,
  affected_result_rows INTEGER NOT NULL,
  pre_dem_votes REAL NOT NULL,
  pre_rep_votes REAL NOT NULL,
  post_dem_votes REAL NOT NULL,
  post_rep_votes REAL NOT NULL,
  expected_dem_votes REAL NOT NULL,
  expected_rep_votes REAL NOT NULL,
  validation_status TEXT NOT NULL CHECK (validation_status IN ('passed','review')),
  note TEXT NOT NULL
);
