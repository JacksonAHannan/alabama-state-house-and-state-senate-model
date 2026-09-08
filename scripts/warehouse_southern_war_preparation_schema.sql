PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (15,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Finance-free Southern WAR outcome, context, training, and 2026 incumbency marts');

CREATE TABLE IF NOT EXISTS mart_southern_war_outcome (
    war_outcome_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    election_stage TEXT NOT NULL,
    election_date TEXT,
    district_plan_id TEXT,
    geography_vintage TEXT NOT NULL,
    observation_set_id TEXT NOT NULL,
    canonical_observation_set_id TEXT,
    dem_candidate_result_id TEXT NOT NULL,
    rep_candidate_result_id TEXT NOT NULL,
    dem_candidate_name TEXT NOT NULL,
    rep_candidate_name TEXT NOT NULL,
    dem_votes INTEGER NOT NULL CHECK (dem_votes>0),
    rep_votes INTEGER NOT NULL CHECK (rep_votes>0),
    two_party_votes INTEGER NOT NULL CHECK (two_party_votes>0),
    third_party_votes INTEGER NOT NULL CHECK (third_party_votes>=0),
    legislative_dem_margin REAL NOT NULL CHECK (legislative_dem_margin BETWEEN -100 AND 100),
    source_provider TEXT NOT NULL,
    source_family TEXT NOT NULL,
    source_file_id TEXT,
    authority_rank INTEGER NOT NULL,
    source_quality_flags_json TEXT NOT NULL,
    selection_status TEXT NOT NULL
      CHECK (selection_status IN ('canonical_model_eligible','model_eligible_fallback',
                                  'external_validated_panel_fallback')),
    validation_status TEXT NOT NULL CHECK (validation_status='passed'),
    UNIQUE(state_code,cycle,chamber,district)
);

CREATE TABLE IF NOT EXISTS mart_southern_war_context_feature (
    context_feature_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    source_file_id TEXT NOT NULL REFERENCES warehouse_source_file(source_file_id),
    state_code TEXT NOT NULL CHECK (length(state_code)=2),
    cycle INTEGER NOT NULL,
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    baseline_dem_margin REAL,
    baseline_source TEXT,
    baseline_office TEXT,
    baseline_class TEXT,
    baseline_quality TEXT,
    baseline_coverage REAL CHECK (baseline_coverage IS NULL OR baseline_coverage BETWEEN 0 AND 1),
    baseline_source_path TEXT,
    strict_baseline_eligible INTEGER NOT NULL CHECK (strict_baseline_eligible IN (0,1)),
    research_baseline_eligible INTEGER NOT NULL CHECK (research_baseline_eligible IN (0,1)),
    dem_incumbent INTEGER CHECK (dem_incumbent IS NULL OR dem_incumbent IN (0,1)),
    rep_incumbent INTEGER CHECK (rep_incumbent IS NULL OR rep_incumbent IN (0,1)),
    incumbency_balance INTEGER CHECK (incumbency_balance IS NULL OR incumbency_balance IN (-1,0,1)),
    incumbency_source TEXT,
    incumbency_quality TEXT NOT NULL,
    strict_incumbency_eligible INTEGER NOT NULL CHECK (strict_incumbency_eligible IN (0,1)),
    source_panel_observation_id TEXT,
    UNIQUE(state_code,cycle,chamber,district)
);

CREATE TABLE IF NOT EXISTS mart_alabama_2026_incumbency_roster (
    roster_id TEXT PRIMARY KEY,
    build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
    incumbency_evidence_id TEXT NOT NULL
      REFERENCES source_southern_incumbency_evidence(incumbency_evidence_id),
    cycle INTEGER NOT NULL CHECK (cycle=2026),
    state_code TEXT NOT NULL CHECK (state_code='AL'),
    chamber TEXT NOT NULL CHECK (chamber IN ('lower','upper')),
    district TEXT NOT NULL,
    incumbent_name TEXT NOT NULL,
    party_family TEXT NOT NULL,
    incumbent_ran INTEGER NOT NULL CHECK (incumbent_ran IN (0,1)),
    open_seat INTEGER NOT NULL CHECK (open_seat IN (0,1)),
    dem_incumbent INTEGER NOT NULL CHECK (dem_incumbent IN (0,1)),
    rep_incumbent INTEGER NOT NULL CHECK (rep_incumbent IN (0,1)),
    incumbency_balance INTEGER NOT NULL CHECK (incumbency_balance IN (-1,0,1)),
    existing_roster_status TEXT,
    comparison_status TEXT NOT NULL
      CHECK (comparison_status IN ('agrees','workbook_supported_correction','existing_roster_unavailable')),
    review_status TEXT NOT NULL CHECK (review_status IN ('proposed','approved')),
    resolution_rationale TEXT NOT NULL,
    evidence_method TEXT NOT NULL,
    evidence_url TEXT,
    UNIQUE(cycle,state_code,chamber,district)
);

DROP VIEW IF EXISTS mart_southern_war_training_no_finance;
CREATE VIEW mart_southern_war_training_no_finance AS
SELECT
  o.*,
  c.context_feature_id,
  c.baseline_dem_margin,
  c.baseline_source,
  c.baseline_office,
  c.baseline_class,
  c.baseline_quality,
  c.baseline_coverage,
  c.baseline_source_path,
  COALESCE(c.strict_baseline_eligible,0) AS strict_baseline_eligible,
  COALESCE(c.research_baseline_eligible,0) AS research_baseline_eligible,
  c.dem_incumbent,
  c.rep_incumbent,
  c.incumbency_balance,
  c.incumbency_source,
  COALESCE(c.incumbency_quality,'missing') AS incumbency_quality,
  COALESCE(c.strict_incumbency_eligible,0) AS strict_incumbency_eligible,
  CASE WHEN c.baseline_dem_margin IS NOT NULL
       THEN o.legislative_dem_margin-c.baseline_dem_margin END AS direct_overperformance,
  CASE
    WHEN c.context_feature_id IS NULL THEN 'missing_context'
    WHEN c.baseline_dem_margin IS NULL THEN 'missing_baseline'
    WHEN c.incumbency_balance IS NULL THEN 'missing_incumbency'
    WHEN c.strict_baseline_eligible=1 AND c.strict_incumbency_eligible=1
      THEN 'strict_war_ready_no_finance'
    WHEN c.research_baseline_eligible=1
      THEN 'research_war_ready_no_finance'
    WHEN c.strict_baseline_eligible=0 AND c.research_baseline_eligible=0
      THEN 'baseline_not_eligible'
    WHEN c.strict_incumbency_eligible=0 THEN 'experimental_incumbency_only'
    ELSE 'other_gate_failure'
  END AS training_status,
  'excluded_not_ready' AS finance_status
FROM mart_southern_war_outcome o
LEFT JOIN mart_southern_war_context_feature c
  ON c.state_code=o.state_code AND c.cycle=o.cycle AND c.chamber=o.chamber
 AND c.district=o.district;

DROP VIEW IF EXISTS qa_southern_war_training_no_finance_coverage;
CREATE VIEW qa_southern_war_training_no_finance_coverage AS
SELECT state_code,cycle,chamber,
       COUNT(*) AS model_valid_outcomes,
       SUM(context_feature_id IS NOT NULL) AS context_rows,
       SUM(training_status='strict_war_ready_no_finance') AS strict_ready,
       SUM(training_status='research_war_ready_no_finance') AS research_ready,
       SUM(training_status='missing_context') AS missing_context,
       SUM(training_status='missing_baseline') AS missing_baseline,
       SUM(training_status='missing_incumbency') AS missing_incumbency,
       SUM(selection_status IN ('model_eligible_fallback','external_validated_panel_fallback'))
         AS model_source_fallbacks
FROM mart_southern_war_training_no_finance
GROUP BY state_code,cycle,chamber;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (16,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Southern WAR training interface with explicit candidate-cycle finance coverage');

DROP VIEW IF EXISTS mart_southern_war_training_with_finance;
CREATE VIEW mart_southern_war_training_with_finance AS
SELECT
  w.*,
  f.democratic_candidate_result_id AS finance_dem_candidate_result_id,
  f.republican_candidate_result_id AS finance_rep_candidate_result_id,
  CASE WHEN f.finance_complete=1 THEN f.democratic_fundraising END AS democratic_fundraising,
  CASE WHEN f.finance_complete=1 THEN f.republican_fundraising END AS republican_fundraising,
  f.democratic_finance_status,
  f.republican_finance_status,
  COALESCE(f.finance_complete,0) AS finance_complete,
  CASE WHEN f.finance_complete=1 THEN f.log_fundraising_ratio_d_to_r END AS log_fundraising_ratio_d_to_r,
  f.smoothing_constant AS finance_smoothing_constant,
  COALESCE(f.race_finance_status,'no_finance_race_observation') AS race_finance_status,
  CASE
    WHEN w.training_status='strict_war_ready_no_finance' AND COALESCE(f.finance_complete,0)=1
      THEN 'strict_war_ready_with_finance'
    WHEN w.training_status='research_war_ready_no_finance' AND COALESCE(f.finance_complete,0)=1
      THEN 'research_war_ready_with_finance'
    WHEN w.training_status IN ('strict_war_ready_no_finance','research_war_ready_no_finance')
      THEN 'war_ready_finance_unobserved'
    ELSE w.training_status
  END AS evaluation_status
FROM mart_southern_war_training_no_finance w
LEFT JOIN mart_southern_race_finance f
  ON f.state_code=w.state_code AND f.cycle=w.cycle AND f.chamber=w.chamber
 AND f.district=w.district;

DROP VIEW IF EXISTS qa_southern_war_training_with_finance_coverage;
CREATE VIEW qa_southern_war_training_with_finance_coverage AS
SELECT state_code,cycle,chamber,
       COUNT(*) AS model_valid_outcomes,
       SUM(training_status='strict_war_ready_no_finance') AS strict_war_ready,
       SUM(training_status='research_war_ready_no_finance') AS research_war_ready,
       SUM(finance_complete=1) AS finance_complete_outcomes,
       SUM(evaluation_status='strict_war_ready_with_finance') AS strict_finance_ready,
       SUM(evaluation_status='research_war_ready_with_finance') AS research_finance_ready,
       SUM(evaluation_status='war_ready_finance_unobserved') AS war_ready_finance_unobserved
FROM mart_southern_war_training_with_finance
GROUP BY state_code,cycle,chamber;
