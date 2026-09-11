PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version, applied_at_utc, description)
VALUES (23, strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Exact-vintage 2012 precinct preparation and allocation to historical SLD plans');

CREATE TABLE IF NOT EXISTS source_southern_precinct_geometry_file (
  source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
  state_code TEXT NOT NULL CHECK(length(state_code)=2),
  election_cycle INTEGER NOT NULL CHECK(election_cycle=2012),
  geography_vintage TEXT NOT NULL,
  shapefile_member TEXT NOT NULL,
  validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review'))
);

CREATE TABLE IF NOT EXISTS mart_southern_2012_precinct_vote_geometry (
  prepared_precinct_id TEXT PRIMARY KEY,
  build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  geometry_source_file_id TEXT NOT NULL REFERENCES source_southern_precinct_geometry_file(source_file_id),
  state_code TEXT NOT NULL CHECK(length(state_code)=2),
  county_key TEXT,
  precinct_key TEXT NOT NULL,
  source_result_ids_json TEXT NOT NULL,
  dem_votes REAL NOT NULL CHECK(dem_votes>=0),
  rep_votes REAL NOT NULL CHECK(rep_votes>=0),
  other_votes REAL NOT NULL CHECK(other_votes>=0),
  total_votes REAL NOT NULL CHECK(total_votes>=0),
  direct_two_party_votes REAL NOT NULL CHECK(direct_two_party_votes>=0),
  redistributed_two_party_votes REAL NOT NULL CHECK(redistributed_two_party_votes>=0),
  preparation_method TEXT NOT NULL,
  geometry_wkb BLOB NOT NULL,
  geometry_crs TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_southern_2012_precinct_plan_weight (
  build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  prepared_precinct_id TEXT NOT NULL REFERENCES mart_southern_2012_precinct_vote_geometry(prepared_precinct_id),
  assignment_source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id),
  state_code TEXT NOT NULL CHECK(length(state_code)=2),
  election_cycle INTEGER NOT NULL CHECK(election_cycle=2012),
  plan_cycle INTEGER NOT NULL,
  chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
  district TEXT NOT NULL,
  allocation_weight REAL NOT NULL CHECK(allocation_weight>0 AND allocation_weight<=1),
  weight_basis TEXT NOT NULL,
  contributing_blocks INTEGER NOT NULL CHECK(contributing_blocks>=0),
  contributing_vap REAL NOT NULL CHECK(contributing_vap>=0),
  PRIMARY KEY(prepared_precinct_id, assignment_source_file_id, district)
);

CREATE TABLE IF NOT EXISTS qa_southern_2012_plan_allocation (
  build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  geometry_source_file_id TEXT NOT NULL REFERENCES source_southern_precinct_geometry_file(source_file_id),
  assignment_source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id),
  state_code TEXT NOT NULL CHECK(length(state_code)=2),
  plan_cycle INTEGER NOT NULL,
  chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
  source_result_rows INTEGER NOT NULL,
  prepared_precincts INTEGER NOT NULL,
  direct_two_party_votes REAL NOT NULL,
  redistributed_mode_two_party_votes REAL NOT NULL,
  redistributed_unmatched_two_party_votes REAL NOT NULL,
  source_two_party_votes REAL NOT NULL,
  allocated_two_party_votes REAL NOT NULL,
  unmatched_plan_two_party_votes REAL NOT NULL,
  max_precinct_weight_error REAL NOT NULL,
  validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
  note TEXT,
  PRIMARY KEY(result_source_file_id, assignment_source_file_id, state_code, chamber)
);

CREATE INDEX IF NOT EXISTS southern_2012_plan_weight_lookup
  ON bridge_southern_2012_precinct_plan_weight(plan_cycle,state_code,chamber,district);
