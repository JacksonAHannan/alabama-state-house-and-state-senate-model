PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (9,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Historical precinct chronology, DOJ Section 5 notices, snapshots, versions and lineage');

CREATE TABLE IF NOT EXISTS source_doj_section5_notice (
  notice_id TEXT PRIMARY KEY,
  notice_date TEXT NOT NULL,
  source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  source_url TEXT NOT NULL,
  source_format TEXT NOT NULL CHECK(source_format IN ('html','xls')),
  parsed_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_doj_section5_entry (
  entry_id TEXT PRIMARY KEY,
  notice_id TEXT NOT NULL REFERENCES source_doj_section5_notice(notice_id),
  row_order INTEGER NOT NULL,
  activity_date TEXT,
  submission_number TEXT,
  state TEXT NOT NULL,
  county TEXT,
  subjurisdiction TEXT,
  activity TEXT,
  change_description TEXT,
  raw_text TEXT NOT NULL,
  UNIQUE(notice_id,row_order)
);

CREATE INDEX IF NOT EXISTS doj_section5_submission_lookup
  ON source_doj_section5_entry(submission_number,activity_date);
CREATE INDEX IF NOT EXISTS doj_section5_state_lookup
  ON source_doj_section5_entry(state,county);

CREATE TABLE IF NOT EXISTS canonical_doj_section5_submission (
  submission_number TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  county TEXT,
  subjurisdiction TEXT,
  first_activity_date TEXT,
  last_activity_date TEXT,
  first_notice_date TEXT,
  last_notice_date TEXT,
  descriptions TEXT,
  activities TEXT,
  notice_count INTEGER NOT NULL,
  entry_count INTEGER NOT NULL,
  withdrawn INTEGER NOT NULL CHECK(withdrawn IN (0,1)),
  objected INTEGER NOT NULL CHECK(objected IN (0,1)),
  precinct_candidate INTEGER NOT NULL CHECK(precinct_candidate IN (0,1)),
  precinct_terms TEXT,
  classification_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS precinct_change_event (
  event_id TEXT PRIMARY KEY,
  county_fips TEXT,
  county_name TEXT,
  resolution_number TEXT,
  adoption_date TEXT,
  effective_date TEXT,
  change_type TEXT NOT NULL,
  geometry_changed INTEGER,
  designation_changed INTEGER,
  polling_place_changed INTEGER,
  description TEXT,
  doj_submission_number TEXT REFERENCES canonical_doj_section5_submission(submission_number),
  doj_status TEXT,
  source_file_id TEXT REFERENCES warehouse_source_file(source_file_id),
  confidence TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  CHECK(change_type IN ('create','abolish','split','consolidate','boundary_adjustment',
    'countywide_realignment','rename','renumber','redesignate','polling_place_change','unknown')),
  CHECK(verification_status IN ('confirmed','documentary_candidate','inferred_from_snapshot_diff','needs_review'))
);

CREATE TABLE IF NOT EXISTS precinct_change_event_type (
  event_id TEXT NOT NULL REFERENCES precinct_change_event(event_id),
  change_type TEXT NOT NULL,
  PRIMARY KEY(event_id,change_type),
  CHECK(change_type IN ('create','abolish','split','consolidate','boundary_adjustment',
    'countywide_realignment','rename','renumber','redesignate','polling_place_change','unknown'))
);

CREATE TABLE IF NOT EXISTS precinct_snapshot (
  snapshot_id TEXT PRIMARY KEY,
  snapshot_date TEXT,
  election_date TEXT,
  source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
  source_type TEXT NOT NULL,
  coverage TEXT,
  apparent_valid_from TEXT,
  apparent_valid_to TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS precinct_version (
  precinct_version_id TEXT PRIMARY KEY,
  county_fips TEXT NOT NULL,
  county_name TEXT,
  precinct_name TEXT,
  precinct_code TEXT,
  valid_from TEXT,
  valid_to TEXT,
  geometry_source_file_id TEXT REFERENCES warehouse_source_file(source_file_id),
  geometry_feature_id TEXT,
  geometry_confidence TEXT,
  geometry_wkb BLOB,
  verification_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_precinct (
  snapshot_id TEXT NOT NULL REFERENCES precinct_snapshot(snapshot_id),
  precinct_version_id TEXT NOT NULL REFERENCES precinct_version(precinct_version_id),
  PRIMARY KEY(snapshot_id,precinct_version_id)
);

CREATE TABLE IF NOT EXISTS precinct_lineage (
  event_id TEXT REFERENCES precinct_change_event(event_id),
  old_precinct_version_id TEXT NOT NULL REFERENCES precinct_version(precinct_version_id),
  new_precinct_version_id TEXT NOT NULL REFERENCES precinct_version(precinct_version_id),
  relationship TEXT NOT NULL,
  overlap_area REAL,
  overlap_pct_old REAL,
  overlap_pct_new REAL,
  intersection_over_union REAL,
  PRIMARY KEY(old_precinct_version_id,new_precinct_version_id,relationship),
  CHECK(relationship IN ('unchanged','renamed_to','renumbered_to','split_into','merged_into',
    'boundary_adjusted_to','replaced_by'))
);

CREATE TABLE IF NOT EXISTS precinct_county_coverage (
  county_fips TEXT NOT NULL,
  county_name TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  document_completeness TEXT NOT NULL,
  geometry_completeness TEXT NOT NULL,
  source_completeness TEXT NOT NULL,
  notes TEXT,
  PRIMARY KEY(county_fips,start_date,end_date)
);
