PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (11,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Provider-specific Southern legislative history and authority-ranked canonical view');

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (12,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Materialized authority-selected Southern legislative candidate history');

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (13,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Final-stage legislative outcomes and WAR competition coverage');

CREATE TABLE IF NOT EXISTS source_southern_legislative_observation_set (
    observation_set_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    source_member TEXT,
    provider TEXT NOT NULL,
    source_family TEXT NOT NULL,
    authority_rank INTEGER NOT NULL CHECK (authority_rank > 0),
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER NOT NULL,
    election_date TEXT,
    election_date_status TEXT NOT NULL CHECK (election_date_status IN ('observed','derived','unknown')),
    election_stage TEXT NOT NULL
      CHECK (election_stage IN ('primary','primary_runoff','general','special','special_runoff','other')),
    election_stage_original TEXT NOT NULL,
    office_code TEXT NOT NULL CHECK (office_code IN ('SLDL','SLDU')),
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district_plan_id TEXT NOT NULL,
    geography_vintage TEXT NOT NULL,
    district TEXT NOT NULL,
    district_original TEXT,
    source_coverage TEXT NOT NULL,
    contest_status TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    quality_flags_json TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('passed','review')),
    as_of_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_southern_legislative_candidate_result (
    source_candidate_result_id TEXT PRIMARY KEY,
    observation_set_id TEXT NOT NULL
      REFERENCES source_southern_legislative_observation_set(observation_set_id) ON DELETE CASCADE,
    candidate_source_id TEXT,
    candidate_name TEXT NOT NULL,
    candidate_name_original TEXT NOT NULL,
    party_family TEXT NOT NULL
      CHECK (party_family IN ('democratic','republican','independent','other','unknown')),
    party_original TEXT,
    votes INTEGER CHECK (votes IS NULL OR votes >= 0),
    vote_share REAL CHECK (vote_share IS NULL OR (vote_share >= 0 AND vote_share <= 1)),
    vote_value_status TEXT NOT NULL CHECK (vote_value_status IN ('observed','unknown')),
    writein_status TEXT NOT NULL CHECK (writein_status IN ('true','false','unknown')),
    incumbent_status INTEGER CHECK (incumbent_status IS NULL OR incumbent_status IN (0,1)),
    winner_status INTEGER CHECK (winner_status IS NULL OR winner_status IN (0,1)),
    validation_status TEXT NOT NULL CHECK (validation_status IN ('passed','review')),
    as_of_utc TEXT NOT NULL,
    UNIQUE(observation_set_id,candidate_name,party_family,party_original)
);

CREATE TABLE IF NOT EXISTS qa_southern_legislative_source_reconciliation (
    reconciliation_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    source_member TEXT,
    state_code TEXT,
    cycle INTEGER,
    parser_name TEXT NOT NULL,
    input_rows INTEGER NOT NULL CHECK (input_rows >= 0),
    output_candidate_rows INTEGER NOT NULL CHECK (output_candidate_rows >= 0),
    input_votes INTEGER,
    output_votes INTEGER,
    vote_delta INTEGER,
    unknown_vote_rows INTEGER NOT NULL CHECK (unknown_vote_rows >= 0),
    reconciliation_status TEXT NOT NULL
      CHECK (reconciliation_status IN ('exact','row_preserving','not_available','review')),
    note TEXT
);

CREATE INDEX IF NOT EXISTS southern_legislative_set_lookup
  ON source_southern_legislative_observation_set(state_code,cycle,election_stage,chamber,district);
CREATE INDEX IF NOT EXISTS southern_legislative_candidate_set_lookup
  ON source_southern_legislative_candidate_result(observation_set_id);

DROP VIEW IF EXISTS all_southern_legislative_candidate_election_observations;
CREATE VIEW all_southern_legislative_candidate_election_observations AS
SELECT
  r.candidate_election_id AS candidate_result_id,
  'OFFICIAL-' || r.contest_id AS observation_set_id,
  r.contract_version,
  r.build_run_id,
  r.state_code,
  r.cycle,
  r.election_date,
  r.election_date_status,
  r.election_stage,
  r.election_stage_original,
  r.office_code,
  r.chamber,
  r.district_plan_id,
  r.geography_vintage,
  r.district,
  r.candidate_name,
  json_extract(r.candidate_name_originals_json,'$[0]') AS candidate_name_original,
  r.party_family,
  r.party_original,
  r.votes,
  r.vote_share,
  r.vote_value_status,
  r.contest_status,
  'Official state election authority' AS source_provider,
  'official_state' AS source_family,
  NULL AS source_file_id,
  10 AS authority_rank,
  r.validation_status,
  r.as_of_utc
FROM source_southern_candidate_election r
WHERE r.office_code IN ('SLDL','SLDU')

UNION ALL

SELECT
  c.source_candidate_result_id,
  s.observation_set_id,
  2 AS contract_version,
  s.build_run_id,
  s.state_code,
  s.cycle,
  s.election_date,
  s.election_date_status,
  s.election_stage,
  s.election_stage_original,
  s.office_code,
  s.chamber,
  s.district_plan_id,
  s.geography_vintage,
  s.district,
  c.candidate_name,
  c.candidate_name_original,
  c.party_family,
  c.party_original,
  c.votes,
  c.vote_share,
  c.vote_value_status,
  s.contest_status,
  s.provider,
  s.source_family,
  s.source_file_id,
  s.authority_rank,
  CASE WHEN s.validation_status='passed' AND c.validation_status='passed' THEN 'passed' ELSE 'review' END,
  c.as_of_utc
FROM source_southern_legislative_candidate_result c
JOIN source_southern_legislative_observation_set s USING(observation_set_id)

UNION ALL

SELECT
  canonical_candidate_id,
  'ALCANON-' || year || '-' || chamber || '-' || district,
  1 AS contract_version,
  'legacy-alabama-canonical' AS build_run_id,
  'AL' AS state_code,
  year AS cycle,
  date(
    printf('%04d-11-01',year),
    printf('+%d days', ((8-CAST(strftime('%w',printf('%04d-11-01',year)) AS INTEGER)) % 7) + 1)
  ) AS election_date,
  'derived' AS election_date_status,
  'general' AS election_stage,
  'general' AS election_stage_original,
  CASE chamber WHEN 'house' THEN 'SLDL' ELSE 'SLDU' END AS office_code,
  CASE chamber WHEN 'house' THEN 'lower' ELSE 'upper' END AS chamber,
  'AL-' || year || '-' || chamber || '-reported-unknown-vintage' AS district_plan_id,
  'provider-reported; plan vintage unverified' AS geography_vintage,
  CAST(district AS TEXT),
  ballot_name,
  ballot_name,
  CASE party WHEN 'D' THEN 'democratic' WHEN 'R' THEN 'republican'
             WHEN 'I' THEN 'independent' ELSE 'other' END,
  party,
  votes,
  CASE WHEN SUM(votes) OVER (PARTITION BY year,chamber,district)>0
       THEN 1.0*votes/SUM(votes) OVER (PARTITION BY year,chamber,district) END,
  CASE WHEN votes IS NULL THEN 'unknown' ELSE 'observed' END,
  'unknown',
  'Alabama canonical candidate identity pipeline',
  'alabama_canonical',
  NULL,
  5,
  'passed',
  'legacy' AS as_of_utc
FROM fact_candidate_election;

DROP VIEW IF EXISTS resolved_southern_legislative_candidate_election;
CREATE VIEW resolved_southern_legislative_candidate_election AS
WITH eligible AS (
  SELECT *
  FROM all_southern_legislative_candidate_election_observations
  WHERE validation_status='passed'
), set_quality AS (
  SELECT observation_set_id,state_code,cycle,election_stage,chamber,district,
         authority_rank,source_family,
         SUM(CASE WHEN votes IS NOT NULL THEN 1 ELSE 0 END) AS observed_vote_rows,
         COUNT(*) AS candidate_rows
  FROM eligible
  GROUP BY observation_set_id,state_code,cycle,election_stage,chamber,district,
           authority_rank,source_family
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY state_code,cycle,election_stage,chamber,district
    ORDER BY authority_rank,observed_vote_rows DESC,candidate_rows DESC,observation_set_id
  ) AS authority_order
  FROM set_quality
)
SELECT e.*
FROM eligible e
JOIN ranked r USING(observation_set_id)
WHERE r.authority_order=1;

CREATE TABLE IF NOT EXISTS canonical_southern_legislative_candidate_election (
    candidate_result_id TEXT PRIMARY KEY,
    observation_set_id TEXT NOT NULL,
    contract_version INTEGER NOT NULL,
    build_run_id TEXT NOT NULL,
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER NOT NULL,
    election_date TEXT,
    election_date_status TEXT NOT NULL,
    election_stage TEXT NOT NULL,
    election_stage_original TEXT NOT NULL,
    office_code TEXT NOT NULL CHECK (office_code IN ('SLDL','SLDU')),
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district_plan_id TEXT,
    geography_vintage TEXT NOT NULL,
    district TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    candidate_name_original TEXT,
    party_family TEXT NOT NULL,
    party_original TEXT,
    votes INTEGER CHECK (votes IS NULL OR votes >= 0),
    vote_share REAL CHECK (vote_share IS NULL OR (vote_share >= 0 AND vote_share <= 1)),
    vote_value_status TEXT NOT NULL,
    contest_status TEXT NOT NULL,
    source_provider TEXT NOT NULL,
    source_family TEXT NOT NULL,
    source_file_id TEXT,
    authority_rank INTEGER NOT NULL,
    validation_status TEXT NOT NULL,
    as_of_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS canonical_southern_legislative_lookup
  ON canonical_southern_legislative_candidate_election(state_code,cycle,chamber,district);

DROP VIEW IF EXISTS fact_southern_legislative_candidate_election;
CREATE VIEW fact_southern_legislative_candidate_election AS
SELECT * FROM canonical_southern_legislative_candidate_election;

DROP VIEW IF EXISTS qa_southern_legislative_canonical_coverage;
CREATE VIEW qa_southern_legislative_canonical_coverage AS
SELECT state_code,cycle,chamber,
       COUNT(DISTINCT district) AS reported_districts,
       COUNT(*) AS candidate_results,
       SUM(CASE WHEN votes IS NOT NULL THEN 1 ELSE 0 END) AS observed_vote_results,
       GROUP_CONCAT(DISTINCT source_family) AS selected_source_families
FROM fact_southern_legislative_candidate_election
GROUP BY state_code,cycle,chamber;

-- A model must not treat Louisiana's October first round and November runoff
-- as two outcomes or add their votes. For each Louisiana district, the runoff
-- is final when present; otherwise the first round is final. Other states use
-- their regular general-election observation. Specials remain available in
-- the stage-level fact but are deliberately outside this regular-cycle view.
DROP VIEW IF EXISTS fact_southern_legislative_final_candidate_election;
CREATE VIEW fact_southern_legislative_final_candidate_election AS
WITH regular_sets AS (
  SELECT DISTINCT observation_set_id,state_code,cycle,chamber,district,
         election_stage,election_date
  FROM fact_southern_legislative_candidate_election
  WHERE (state_code='LA' AND cycle>=1995 AND election_stage IN ('general','other'))
     OR (state_code<>'LA' AND election_stage='general')
), ranked_sets AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY state_code,cycle,chamber,district
    ORDER BY
      CASE WHEN state_code='LA' AND election_stage='other' THEN 2 ELSE 1 END DESC,
      COALESCE(election_date,'') DESC,
      observation_set_id
  ) AS final_stage_order
  FROM regular_sets
)
SELECT f.*,
       CASE WHEN f.state_code='LA'
            THEN 'runoff_if_present_else_first_round'
            ELSE 'regular_general' END AS final_stage_rule
FROM fact_southern_legislative_candidate_election f
JOIN ranked_sets r USING(observation_set_id)
WHERE r.final_stage_order=1;

DROP VIEW IF EXISTS qa_southern_legislative_final_competition_coverage;
CREATE VIEW qa_southern_legislative_final_competition_coverage AS
WITH contests AS (
  SELECT state_code,cycle,chamber,district,observation_set_id,election_stage,
         COUNT(*) AS candidate_rows,
         SUM(CASE WHEN votes IS NULL THEN 1 ELSE 0 END) AS unknown_vote_rows,
         SUM(CASE WHEN votes>0 THEN 1 ELSE 0 END) AS positive_vote_candidates,
         SUM(CASE WHEN party_family='democratic' AND votes>0 THEN 1 ELSE 0 END) AS democratic_candidates,
         SUM(CASE WHEN party_family='republican' AND votes>0 THEN 1 ELSE 0 END) AS republican_candidates
  FROM fact_southern_legislative_final_candidate_election
  GROUP BY state_code,cycle,chamber,district,observation_set_id,election_stage
)
SELECT state_code,cycle,chamber,
       COUNT(*) AS final_contests,
       SUM(CASE WHEN positive_vote_candidates>=2 THEN 1 ELSE 0 END) AS observed_competitions,
       SUM(CASE WHEN democratic_candidates=1 AND republican_candidates=1
                 AND unknown_vote_rows=0 THEN 1 ELSE 0 END) AS war_eligible_dr_contests,
       SUM(CASE WHEN state_code='LA' AND election_stage='general' THEN 1 ELSE 0 END)
         AS louisiana_first_round_final_contests,
       SUM(CASE WHEN state_code='LA' AND election_stage='other' THEN 1 ELSE 0 END)
         AS louisiana_runoff_final_contests,
       SUM(unknown_vote_rows) AS unknown_vote_rows
FROM contests
GROUP BY state_code,cycle,chamber;
