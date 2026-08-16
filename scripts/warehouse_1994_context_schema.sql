PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (6,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        '1994 historical demographics, incumbency, finance coverage, and presidential context');

CREATE TABLE IF NOT EXISTS mart_historical_district_demographic_feature (
  cycle INTEGER NOT NULL, chamber TEXT NOT NULL, district INTEGER NOT NULL,
  census_vintage INTEGER NOT NULL, total_population REAL, white_population REAL,
  age25_population REAL, white_age25_population REAL, college_population REAL,
  white_college_population REAL, nonwhite_share REAL, college_share REAL,
  white_college_share REAL, allocation_method TEXT NOT NULL,
  source_population_coverage REAL NOT NULL,
  PRIMARY KEY(cycle,chamber,district)
);

CREATE TABLE IF NOT EXISTS source_historical_presidential_precinct (
  cycle INTEGER NOT NULL, county_key TEXT NOT NULL, precinct_key TEXT NOT NULL,
  dem_candidate TEXT NOT NULL, rep_candidate TEXT NOT NULL,
  dem_votes REAL NOT NULL, rep_votes REAL NOT NULL, source_file TEXT NOT NULL,
  PRIMARY KEY(cycle,county_key,precinct_key)
);

CREATE TABLE IF NOT EXISTS mart_historical_district_presidential_feature (
  cycle INTEGER NOT NULL, chamber TEXT NOT NULL, district INTEGER NOT NULL,
  source_year INTEGER NOT NULL, dem_votes REAL, rep_votes REAL,
  two_party_votes REAL, dem_margin REAL, fallback_share REAL,
  source_complete INTEGER NOT NULL, allocation_method TEXT NOT NULL,
  PRIMARY KEY(cycle,chamber,district,source_year)
);

CREATE TABLE IF NOT EXISTS mart_historical_candidate_incumbency (
  canonical_candidate_id TEXT PRIMARY KEY, cycle INTEGER NOT NULL,
  chamber TEXT NOT NULL, district INTEGER NOT NULL, party TEXT NOT NULL,
  candidate TEXT NOT NULL, incumbent INTEGER NOT NULL,
  prior_candidate_name TEXT, prior_party TEXT, match_method TEXT NOT NULL,
  match_confidence TEXT NOT NULL, review_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_historical_candidate_finance_coverage (
  canonical_candidate_id TEXT PRIMARY KEY, cycle INTEGER NOT NULL,
  chamber TEXT NOT NULL, district INTEGER NOT NULL, party TEXT NOT NULL,
  candidate TEXT NOT NULL, total_resources_raised REAL,
  observation_status TEXT NOT NULL, source_name TEXT,
  coverage_note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mart_historical_cmo_context_feature (
  cycle INTEGER NOT NULL, chamber TEXT NOT NULL, district INTEGER NOT NULL,
  nonwhite_share REAL, college_share REAL, white_college_share REAL,
  demographics_method TEXT, dem_incumbent INTEGER NOT NULL,
  rep_incumbent INTEGER NOT NULL, finance_complete INTEGER NOT NULL,
  log_resource_ratio_d_to_r REAL, pres_1992_dem_margin REAL,
  pres_1992_fallback_share REAL, pres_1992_source_complete INTEGER NOT NULL,
  PRIMARY KEY(cycle,chamber,district)
);
