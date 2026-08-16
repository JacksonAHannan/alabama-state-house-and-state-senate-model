PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (5,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Auditable historical ballot-derived district weights and CMO baseline marts');

CREATE TABLE IF NOT EXISTS mart_historical_precinct_district_weight (
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('house','senate')),
    county_key TEXT NOT NULL,
    precinct_key TEXT NOT NULL,
    district INTEGER NOT NULL,
    district_activity REAL NOT NULL CHECK (district_activity >= 0),
    precinct_activity REAL NOT NULL CHECK (precinct_activity > 0),
    allocation_weight REAL NOT NULL CHECK (allocation_weight >= 0 AND allocation_weight <= 1),
    district_count INTEGER NOT NULL CHECK (district_count >= 1),
    allocation_method TEXT NOT NULL CHECK (allocation_method IN
      ('official_ballot_single_district','legislative_activity_split_provisional')),
    PRIMARY KEY (cycle,chamber,county_key,precinct_key,district)
);

CREATE TABLE IF NOT EXISTS mart_historical_district_office_baseline (
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('house','senate')),
    district INTEGER NOT NULL,
    office TEXT NOT NULL,
    dem_votes REAL NOT NULL CHECK (dem_votes >= 0),
    rep_votes REAL NOT NULL CHECK (rep_votes >= 0),
    two_party_votes REAL NOT NULL CHECK (two_party_votes >= 0),
    office_dem_margin REAL,
    baseline_allocation_method TEXT NOT NULL,
    PRIMARY KEY (cycle,chamber,district,office)
);

CREATE TABLE IF NOT EXISTS mart_historical_cmo_race_feature (
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('house','senate')),
    district INTEGER NOT NULL,
    dem_votes REAL NOT NULL,
    rep_votes REAL NOT NULL,
    two_party_votes REAL NOT NULL,
    legislative_dem_margin REAL,
    core_index_margin REAL,
    raw_overperformance REAL,
    core_index_offices INTEGER NOT NULL,
    core_index_complete INTEGER NOT NULL CHECK (core_index_complete IN (0,1)),
    contested_two_party INTEGER NOT NULL CHECK (contested_two_party IN (0,1)),
    baseline_allocation_method TEXT,
    score_status TEXT NOT NULL,
    PRIMARY KEY (cycle,chamber,district)
);

CREATE TABLE IF NOT EXISTS qa_historical_baseline_allocation (
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('house','senate')),
    office TEXT NOT NULL,
    party TEXT NOT NULL CHECK (party IN ('D','R')),
    source_votes REAL NOT NULL,
    allocated_votes REAL NOT NULL,
    unmatched_votes REAL NOT NULL,
    allocation_coverage REAL,
    PRIMARY KEY (cycle,chamber,office,party)
);
