PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (7,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Generalized historical CMO context for the 1998, 2002, and 2006 cycles');

CREATE TABLE IF NOT EXISTS mart_historical_cmo_context_feature_v2 (
  cycle INTEGER NOT NULL, chamber TEXT NOT NULL, district INTEGER NOT NULL,
  census_vintage INTEGER NOT NULL, nonwhite_share REAL, college_share REAL,
  white_college_share REAL, demographics_method TEXT NOT NULL,
  dem_incumbent INTEGER NOT NULL, rep_incumbent INTEGER NOT NULL,
  incumbency_complete INTEGER NOT NULL, finance_complete INTEGER NOT NULL,
  log_resource_ratio_d_to_r REAL, prior_presidential_year INTEGER NOT NULL,
  prior_pres_dem_margin REAL, prior_pres_fallback_share REAL,
  prior_pres_source_complete INTEGER NOT NULL, readiness_status TEXT NOT NULL,
  PRIMARY KEY(cycle,chamber,district)
);
