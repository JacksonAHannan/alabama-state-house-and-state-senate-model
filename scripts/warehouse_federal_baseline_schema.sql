PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (8,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Same-cycle contested federal baselines for historical CMO research');

DROP TABLE IF EXISTS mart_historical_federal_district_baseline;
CREATE TABLE mart_historical_federal_district_baseline (
  cycle INTEGER NOT NULL, chamber TEXT NOT NULL, district INTEGER NOT NULL,
  us_house_dem_margin REAL, us_senate_dem_margin REAL,
  us_house_two_party_votes REAL, us_senate_two_party_votes REAL,
  federal_index_margin REAL, federal_components INTEGER NOT NULL,
  contested_federal_votes REAL NOT NULL, all_federal_major_votes REAL NOT NULL,
  federal_contested_coverage REAL, federal_allocation_method TEXT NOT NULL,
  PRIMARY KEY(cycle,chamber,district)
);
