PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (21,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Spatial presidential allocation to post-2016 historical legislative plans');

CREATE TABLE IF NOT EXISTS source_southern_spatial_plan_assignment (
    assignment_source_file_id TEXT PRIMARY KEY
      REFERENCES source_southern_assignment_file(source_file_id) ON DELETE CASCADE,
    geography_layer_id TEXT NOT NULL UNIQUE
      REFERENCES dim_southern_geography_layer(geography_layer_id),
    block_geometry_source_file_id TEXT NOT NULL
      REFERENCES source_southern_census_block_file(source_file_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    plan_cycle INTEGER NOT NULL CHECK(plan_cycle BETWEEN 2017 AND 2020),
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    assignment_method TEXT NOT NULL
      CHECK(assignment_method='2020_block_representative_point_with_intersection_resolution'),
    validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
    UNIQUE(state_code,plan_cycle,chamber)
);

CREATE TABLE IF NOT EXISTS bridge_southern_vest_historical_plan_weight (
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    result_source_file_id TEXT NOT NULL
      REFERENCES source_southern_vest_context_file(source_file_id),
    result_observation_id TEXT NOT NULL
      REFERENCES source_southern_presidential_geography_result(result_observation_id),
    assignment_source_file_id TEXT NOT NULL
      REFERENCES source_southern_spatial_plan_assignment(assignment_source_file_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL CHECK(election_cycle=2016),
    plan_cycle INTEGER NOT NULL CHECK(plan_cycle BETWEEN 2017 AND 2020),
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    allocation_weight REAL NOT NULL CHECK(allocation_weight>0 AND allocation_weight<=1),
    weight_basis TEXT NOT NULL CHECK(weight_basis IN ('2020_vap','geometry_intersection_area')),
    contributing_blocks INTEGER NOT NULL CHECK(contributing_blocks>0),
    contributing_vap REAL NOT NULL CHECK(contributing_vap>=0),
    PRIMARY KEY(result_observation_id,assignment_source_file_id,district)
);

CREATE TABLE IF NOT EXISTS qa_southern_historical_plan_allocation (
    result_source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    assignment_source_file_id TEXT NOT NULL
      REFERENCES source_southern_spatial_plan_assignment(assignment_source_file_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    election_cycle INTEGER NOT NULL CHECK(election_cycle IN (2016,2020)),
    plan_cycle INTEGER NOT NULL CHECK(plan_cycle BETWEEN 2017 AND 2020),
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    result_grain TEXT NOT NULL CHECK(result_grain IN ('precinct','census_block')),
    result_rows INTEGER NOT NULL CHECK(result_rows>=0),
    assigned_result_rows INTEGER NOT NULL CHECK(assigned_result_rows>=0),
    split_result_rows INTEGER NOT NULL CHECK(split_result_rows>=0),
    ambiguous_plan_blocks_resolved INTEGER NOT NULL CHECK(ambiguous_plan_blocks_resolved>=0),
    intersection_plan_blocks_resolved INTEGER NOT NULL CHECK(intersection_plan_blocks_resolved>=0),
    unmatched_plan_positive_vap REAL NOT NULL CHECK(unmatched_plan_positive_vap>=0),
    total_positive_vap REAL NOT NULL CHECK(total_positive_vap>=0),
    fallback_two_party_votes REAL NOT NULL CHECK(fallback_two_party_votes>=0),
    total_two_party_votes REAL NOT NULL CHECK(total_two_party_votes>=0),
    unmatched_two_party_votes REAL NOT NULL,
    max_result_weight_error REAL NOT NULL CHECK(max_result_weight_error>=0),
    validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
    note TEXT,
    PRIMARY KEY(result_source_file_id,assignment_source_file_id)
);

CREATE INDEX IF NOT EXISTS southern_vest_historical_plan_lookup
  ON bridge_southern_vest_historical_plan_weight(plan_cycle,state_code,chamber,district);

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (22,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Detailed-plan geometry overlay validation for historical spatial assignments');

CREATE TABLE IF NOT EXISTS qa_southern_spatial_plan_geometry_overlay (
    assignment_source_file_id TEXT PRIMARY KEY
      REFERENCES source_southern_spatial_plan_assignment(assignment_source_file_id),
    reference_geography_layer_id TEXT NOT NULL
      REFERENCES dim_southern_geography_layer(geography_layer_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    plan_cycle INTEGER NOT NULL CHECK(plan_cycle=2020),
    chamber TEXT NOT NULL CHECK(chamber IN ('lower','upper')),
    common_assigned_blocks INTEGER NOT NULL CHECK(common_assigned_blocks>=0),
    common_disagreement_blocks INTEGER NOT NULL CHECK(common_disagreement_blocks>=0),
    common_disagreement_vap REAL NOT NULL CHECK(common_disagreement_vap>=0),
    total_positive_vap REAL NOT NULL CHECK(total_positive_vap>=0),
    cartographic_only_blocks INTEGER NOT NULL CHECK(cartographic_only_blocks>=0),
    cartographic_only_vap REAL NOT NULL CHECK(cartographic_only_vap>=0),
    detailed_only_blocks INTEGER NOT NULL CHECK(detailed_only_blocks>=0),
    detailed_only_vap REAL NOT NULL CHECK(detailed_only_vap>=0),
    detailed_unmatched_positive_vap REAL NOT NULL CHECK(detailed_unmatched_positive_vap>=0),
    validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review'))
);
