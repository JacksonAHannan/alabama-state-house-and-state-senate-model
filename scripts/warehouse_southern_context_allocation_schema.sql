PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (18,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'National block-to-legislative-district assignments and presidential district aggregates');

CREATE TABLE IF NOT EXISTS source_southern_assignment_file (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    manifest_source_file_id TEXT NOT NULL UNIQUE,
    plan_cycle INTEGER NOT NULL,
    geography_vintage TEXT NOT NULL,
    authoritative_scope TEXT NOT NULL,
    ingest_status TEXT NOT NULL CHECK(ingest_status IN ('acquired','parsed','review')),
    parser_name TEXT,
    parser_message TEXT
);

CREATE TABLE IF NOT EXISTS bridge_southern_block_district_assignment (
    source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id)
      ON DELETE CASCADE,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    plan_cycle INTEGER NOT NULL,
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    block_geoid TEXT NOT NULL CHECK(length(block_geoid)=15),
    lower_district TEXT,
    upper_district TEXT,
    lower_assignment_status TEXT NOT NULL CHECK(lower_assignment_status IN ('assigned','unassigned')),
    upper_assignment_status TEXT NOT NULL CHECK(upper_assignment_status IN ('assigned','unassigned')),
    PRIMARY KEY(source_file_id,state_code,block_geoid)
);

CREATE TABLE IF NOT EXISTS mart_southern_presidential_district_result (
    district_result_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    assignment_source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id),
    contract_version INTEGER NOT NULL,
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL,
    plan_cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    geography_unit_id TEXT REFERENCES dim_southern_geography_unit(geography_unit_id),
    dem_votes REAL NOT NULL CHECK(dem_votes>=0),
    rep_votes REAL NOT NULL CHECK(rep_votes>=0),
    other_votes REAL NOT NULL CHECK(other_votes>=0),
    total_votes REAL NOT NULL CHECK(total_votes>=0),
    two_party_dem_margin REAL,
    allocated_result_geographies INTEGER NOT NULL CHECK(allocated_result_geographies>=0),
    allocation_method TEXT NOT NULL,
    allocation_status TEXT NOT NULL CHECK(allocation_status IN ('passed','review')),
    UNIQUE(result_source_file_id,assignment_source_file_id,state_code,election_cycle,plan_cycle,chamber,district)
);

CREATE TABLE IF NOT EXISTS qa_southern_presidential_district_allocation (
    result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    assignment_source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL,
    plan_cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    result_geography_rows INTEGER NOT NULL CHECK(result_geography_rows>=0),
    assigned_result_geographies INTEGER NOT NULL CHECK(assigned_result_geographies>=0),
    source_dem_votes REAL NOT NULL,
    allocated_dem_votes REAL NOT NULL,
    source_rep_votes REAL NOT NULL,
    allocated_rep_votes REAL NOT NULL,
    unmatched_two_party_votes REAL NOT NULL,
    allocation_coverage REAL,
    reconciliation_status TEXT NOT NULL CHECK(reconciliation_status IN ('exact','within_rounding','review')),
    PRIMARY KEY(result_source_file_id,assignment_source_file_id,state_code,chamber)
);

CREATE INDEX IF NOT EXISTS southern_block_assignment_lookup
  ON bridge_southern_block_district_assignment(plan_cycle,state_code,block_geoid);
CREATE INDEX IF NOT EXISTS southern_block_lower_lookup
  ON bridge_southern_block_district_assignment(plan_cycle,state_code,lower_district);
CREATE INDEX IF NOT EXISTS southern_block_upper_lookup
  ON bridge_southern_block_district_assignment(plan_cycle,state_code,upper_district);
CREATE INDEX IF NOT EXISTS southern_presidential_district_lookup
  ON mart_southern_presidential_district_result(election_cycle,plan_cycle,state_code,chamber,district);

DROP VIEW IF EXISTS fact_southern_presidential_district_result;
CREATE VIEW fact_southern_presidential_district_result AS
SELECT * FROM mart_southern_presidential_district_result
WHERE allocation_status='passed';
