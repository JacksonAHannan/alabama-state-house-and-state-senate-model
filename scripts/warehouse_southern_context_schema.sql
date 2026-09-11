PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (17,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Central Southern presidential-result and versioned legislative-geography warehouse');

CREATE TABLE IF NOT EXISTS source_southern_context_file (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    manifest_source_file_id TEXT NOT NULL UNIQUE,
    state_code TEXT NOT NULL,
    cycle TEXT NOT NULL,
    asset_role TEXT NOT NULL CHECK(asset_role IN ('result','geometry','index')),
    geography_type TEXT,
    geography_vintage TEXT NOT NULL,
    authoritative_scope TEXT NOT NULL,
    manifest_ingest_status TEXT NOT NULL,
    normalization_status TEXT NOT NULL
      CHECK(normalization_status IN ('normalized','registered_unparsed','not_applicable')),
    parser_name TEXT,
    parser_message TEXT
);

CREATE TABLE IF NOT EXISTS source_southern_presidential_geography_result (
    result_observation_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    contract_version INTEGER NOT NULL,
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    cycle INTEGER NOT NULL,
    election_date TEXT NOT NULL,
    election_stage TEXT NOT NULL CHECK(election_stage='general'),
    office_code TEXT NOT NULL CHECK(office_code='USP'),
    geography_type TEXT NOT NULL CHECK(geography_type IN ('precinct','census_block')),
    geography_id TEXT NOT NULL,
    county_fips TEXT,
    county_name_original TEXT,
    county_key TEXT,
    precinct_name_original TEXT,
    precinct_key TEXT,
    dem_candidate TEXT NOT NULL,
    rep_candidate TEXT NOT NULL,
    other_candidates_json TEXT NOT NULL,
    dem_votes REAL NOT NULL CHECK(dem_votes>=0),
    rep_votes REAL NOT NULL CHECK(rep_votes>=0),
    other_votes REAL NOT NULL CHECK(other_votes>=0),
    total_votes REAL NOT NULL CHECK(total_votes>=0),
    two_party_dem_margin REAL,
    vote_value_status TEXT NOT NULL CHECK(vote_value_status IN ('observed','derived')),
    allocation_method TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
    UNIQUE(source_file_id,state_code,cycle,geography_type,geography_id)
);

CREATE TABLE IF NOT EXISTS dim_southern_geography_layer (
    geography_layer_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    contract_version INTEGER NOT NULL,
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    cycle INTEGER NOT NULL,
    geography_type TEXT NOT NULL CHECK(geography_type IN ('state_legislative_district','precinct')),
    chamber TEXT CHECK(chamber IN ('lower','upper')),
    geography_vintage TEXT NOT NULL,
    source_crs TEXT,
    storage_crs TEXT NOT NULL,
    feature_count INTEGER NOT NULL CHECK(feature_count>=0),
    validation_status TEXT NOT NULL CHECK(validation_status IN ('passed','review')),
    UNIQUE(source_file_id,state_code,cycle,chamber)
);

CREATE TABLE IF NOT EXISTS dim_southern_geography_unit (
    geography_unit_id TEXT PRIMARY KEY,
    geography_layer_id TEXT NOT NULL REFERENCES dim_southern_geography_layer(geography_layer_id)
      ON DELETE CASCADE,
    state_code TEXT NOT NULL CHECK(length(state_code)=2),
    cycle INTEGER NOT NULL,
    geography_type TEXT NOT NULL,
    chamber TEXT CHECK(chamber IN ('lower','upper')),
    district TEXT,
    source_geoid TEXT,
    source_name TEXT,
    county_fips TEXT,
    county_name TEXT,
    geometry_wkb BLOB NOT NULL,
    geometry_crs TEXT NOT NULL,
    geometry_sha256 TEXT NOT NULL CHECK(length(geometry_sha256)=64),
    min_x REAL NOT NULL,
    min_y REAL NOT NULL,
    max_x REAL NOT NULL,
    max_y REAL NOT NULL,
    area_sq_km REAL,
    UNIQUE(geography_layer_id,source_geoid)
);

CREATE TABLE IF NOT EXISTS bridge_southern_result_geography (
    result_observation_id TEXT NOT NULL
      REFERENCES source_southern_presidential_geography_result(result_observation_id) ON DELETE CASCADE,
    geography_unit_id TEXT NOT NULL
      REFERENCES dim_southern_geography_unit(geography_unit_id) ON DELETE CASCADE,
    match_method TEXT NOT NULL,
    allocation_weight REAL NOT NULL CHECK(allocation_weight>0 AND allocation_weight<=1),
    review_status TEXT NOT NULL CHECK(review_status IN ('accepted','review')),
    PRIMARY KEY(result_observation_id,geography_unit_id)
);

CREATE TABLE IF NOT EXISTS qa_southern_context_ingest (
    source_file_id TEXT PRIMARY KEY REFERENCES warehouse_source_file(source_file_id),
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    asset_role TEXT NOT NULL,
    input_rows INTEGER,
    output_rows INTEGER NOT NULL CHECK(output_rows>=0),
    input_votes REAL,
    output_votes REAL,
    vote_delta REAL,
    reconciliation_status TEXT NOT NULL
      CHECK(reconciliation_status IN ('exact','within_rounding','review','not_applicable')),
    note TEXT
);

CREATE INDEX IF NOT EXISTS southern_presidential_result_lookup
  ON source_southern_presidential_geography_result(state_code,cycle,geography_type,county_fips);
CREATE INDEX IF NOT EXISTS southern_presidential_block_lookup
  ON source_southern_presidential_geography_result(cycle,geography_id)
  WHERE geography_type='census_block';
CREATE INDEX IF NOT EXISTS southern_geography_district_lookup
  ON dim_southern_geography_unit(state_code,cycle,chamber,district);

DROP VIEW IF EXISTS fact_southern_presidential_geography_result;
CREATE VIEW fact_southern_presidential_geography_result AS
SELECT *
FROM source_southern_presidential_geography_result
WHERE validation_status='passed';

DROP VIEW IF EXISTS qa_southern_context_coverage;
CREATE VIEW qa_southern_context_coverage AS
SELECT state_code,cycle,geography_type,
       COUNT(*) AS geography_rows,
       SUM(CASE WHEN validation_status='passed' THEN 1 ELSE 0 END) AS validated_rows,
       SUM(total_votes) AS total_votes
FROM source_southern_presidential_geography_result
GROUP BY state_code,cycle,geography_type;
