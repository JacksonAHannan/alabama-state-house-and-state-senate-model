-- Alabama canonical candidate to certified canvass cell bridge (schema version 27).
-- Statements are executed one at a time inside the repair transaction; do not use
-- executescript, which would commit the surrounding transaction.

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (27,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Alabama canonical candidate to certified canvass cell bridge with vote-agreement evidence');

CREATE TABLE IF NOT EXISTS bridge_alabama_canonical_candidate_certified_result (
    bridge_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    canonical_candidate_id TEXT NOT NULL UNIQUE,
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    canonical_party TEXT NOT NULL CHECK (canonical_party IN ('D','R')),
    canonical_name TEXT NOT NULL,
    decoded_canonical_name TEXT,
    observation_set_id TEXT NOT NULL REFERENCES source_southern_legislative_observation_set(observation_set_id),
    source_candidate_result_id TEXT NOT NULL UNIQUE
      REFERENCES source_southern_legislative_candidate_result(source_candidate_result_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    certified_candidate_name TEXT NOT NULL,
    match_method TEXT NOT NULL,
    canonical_votes_before INTEGER NOT NULL CHECK (canonical_votes_before >= 0),
    certified_votes INTEGER NOT NULL CHECK (certified_votes >= 0),
    vote_delta INTEGER NOT NULL,
    correction_status TEXT NOT NULL
      CHECK (correction_status IN ('agrees','corrected_to_certified')),
    review_status TEXT NOT NULL CHECK (review_status IN ('approved')),
    evidence_json TEXT NOT NULL,
    recorded_at_utc TEXT NOT NULL,
    UNIQUE(cycle,chamber,district,canonical_party)
);
