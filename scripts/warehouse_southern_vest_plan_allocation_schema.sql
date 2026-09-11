PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (20,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Population-weighted VEST 2016 precinct allocation to 2022 legislative plans');

CREATE TABLE IF NOT EXISTS source_southern_census_block_file (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    manifest_source_file_id TEXT NOT NULL UNIQUE,
    state_code TEXT NOT NULL UNIQUE CHECK(length(state_code)=2),
    cycle INTEGER NOT NULL CHECK(cycle=2020),
    geography_vintage TEXT NOT NULL,
    authoritative_scope TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    normalization_status TEXT NOT NULL CHECK(normalization_status IN ('used_for_crosswalk','review'))
);

CREATE TABLE IF NOT EXISTS bridge_southern_vest_precinct_district_weight (
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    block_geometry_source_file_id TEXT NOT NULL
      REFERENCES source_southern_census_block_file(source_file_id) ON DELETE CASCADE,
    result_source_file_id TEXT NOT NULL REFERENCES source_southern_vest_context_file(source_file_id)
      ON DELETE CASCADE,
    result_observation_id TEXT NOT NULL
      REFERENCES source_southern_presidential_geography_result(result_observation_id) ON DELETE CASCADE,
    assignment_source_file_id TEXT NOT NULL
      REFERENCES source_southern_assignment_file(source_file_id) ON DELETE CASCADE,
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL CHECK(election_cycle=2016),
    plan_cycle INTEGER NOT NULL CHECK(plan_cycle=2022),
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    allocation_weight REAL NOT NULL CHECK(allocation_weight>0 AND allocation_weight<=1),
    weight_basis TEXT NOT NULL CHECK(weight_basis IN ('2020_vap','geometry_intersection_area')),
    contributing_blocks INTEGER NOT NULL CHECK(contributing_blocks>0),
    contributing_vap REAL NOT NULL CHECK(contributing_vap>=0),
    PRIMARY KEY(result_observation_id,assignment_source_file_id,chamber,district)
);

CREATE TABLE IF NOT EXISTS qa_southern_vest_precinct_plan_allocation (
    result_source_file_id TEXT NOT NULL REFERENCES source_southern_vest_context_file(source_file_id),
    assignment_source_file_id TEXT NOT NULL REFERENCES source_southern_assignment_file(source_file_id),
    block_geometry_source_file_id TEXT NOT NULL REFERENCES source_southern_census_block_file(source_file_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL CHECK(election_cycle=2016),
    plan_cycle INTEGER NOT NULL CHECK(plan_cycle=2022),
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    source_precincts INTEGER NOT NULL CHECK(source_precincts>=0),
    positive_vote_precincts INTEGER NOT NULL CHECK(positive_vote_precincts>=0),
    weighted_positive_vote_precincts INTEGER NOT NULL CHECK(weighted_positive_vote_precincts>=0),
    vap_weighted_precincts INTEGER NOT NULL CHECK(vap_weighted_precincts>=0),
    geometry_fallback_precincts INTEGER NOT NULL CHECK(geometry_fallback_precincts>=0),
    split_precincts INTEGER NOT NULL CHECK(split_precincts>=0),
    ambiguous_blocks_resolved INTEGER NOT NULL CHECK(ambiguous_blocks_resolved>=0),
    unmatched_positive_vap REAL NOT NULL CHECK(unmatched_positive_vap>=0),
    total_positive_vap REAL NOT NULL CHECK(total_positive_vap>=0),
    fallback_two_party_votes REAL NOT NULL CHECK(fallback_two_party_votes>=0),
    total_two_party_votes REAL NOT NULL CHECK(total_two_party_votes>=0),
    max_precinct_weight_error REAL NOT NULL CHECK(max_precinct_weight_error>=0),
    validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
    note TEXT,
    PRIMARY KEY(result_source_file_id,assignment_source_file_id,chamber)
);

CREATE INDEX IF NOT EXISTS southern_vest_precinct_plan_lookup
  ON bridge_southern_vest_precinct_district_weight(plan_cycle,state_code,chamber,district);
