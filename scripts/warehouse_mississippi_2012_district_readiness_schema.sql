PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version, applied_at_utc, description)
VALUES (25, strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'District-specific readiness for incomplete historical presidential precinct crosswalks');

CREATE TABLE IF NOT EXISTS qa_southern_presidential_precinct_match (
  build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  result_observation_id TEXT NOT NULL,
  result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  geometry_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  state_code TEXT NOT NULL CHECK(length(state_code)=2),
  election_cycle INTEGER NOT NULL,
  county_key TEXT NOT NULL,
  precinct_name_original TEXT NOT NULL,
  donor_precinct_id TEXT,
  donor_name TEXT,
  match_method TEXT NOT NULL,
  match_score REAL NOT NULL,
  row_score_margin REAL NOT NULL,
  plausible_donor_ids_json TEXT NOT NULL,
  two_party_votes REAL NOT NULL CHECK(two_party_votes>=0),
  validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
  PRIMARY KEY(build_run_id,result_observation_id)
);

CREATE TABLE IF NOT EXISTS qa_southern_presidential_district_readiness (
  build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  geometry_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  assignment_source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id),
  state_code TEXT NOT NULL CHECK(length(state_code)=2),
  election_cycle INTEGER NOT NULL,
  plan_cycle INTEGER NOT NULL,
  chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
  district TEXT NOT NULL,
  ambiguous_result_rows INTEGER NOT NULL CHECK(ambiguous_result_rows>=0),
  ambiguous_two_party_votes REAL NOT NULL CHECK(ambiguous_two_party_votes>=0),
  validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
  note TEXT NOT NULL,
  PRIMARY KEY(result_source_file_id,assignment_source_file_id,state_code,chamber,district)
);

CREATE INDEX IF NOT EXISTS southern_presidential_district_readiness_lookup
  ON qa_southern_presidential_district_readiness(state_code,election_cycle,plan_cycle,chamber,district);
