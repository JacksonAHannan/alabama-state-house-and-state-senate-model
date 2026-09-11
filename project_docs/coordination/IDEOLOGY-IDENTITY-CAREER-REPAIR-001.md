# Task contract: IDEOLOGY-IDENTITY-CAREER-REPAIR-001

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Repair candidate-to-legislator identity coverage and publish distinct leakage-safe pre-election and career-through-2026 ideology staging marts.
- Non-goals: No canonical warehouse schema change and no public-page publication before independent validation.
- Upstream snapshot: Current election candidate universe, unified roll-call warehouse through 2026, reviewed frontier ontology v3, Ballotpedia crosswalks, and manual candidate aliases as of 2026-08-22.
- Read scope: `data/processed/elections/`; `data/processed/legislative/`; `data/processed/ideology/ballotpedia_*`; `data/manual/ideology/`; relevant ideology scripts and tests.
- Write scope: `scripts/build_full_candidate_legislative_ideology.py`; `scripts/repair_candidate_legislator_identities.py`; `scripts/tests/test_candidate_legislator_identity_repair.py`; `data/processed/ideology/candidate_legislator_identity_crosswalk.csv`; `data/processed/ideology/candidate_legislator_identity_review.csv`; `data/processed/ideology/candidate_ideology_full_universe.csv`; `data/processed/ideology/candidate_career_ideology_through_2026.csv`; `data/processed/ideology/long_service_ideology_coverage_audit.csv`; `project_docs/audits/CANDIDATE_LEGISLATOR_IDENTITY_REPAIR.md`; `project_docs/coordination/IDEOLOGY-IDENTITY-CAREER-REPAIR-001.md`.
- Warehouse mode: `read-only`
- Inputs: Candidate election rows; verified Ballotpedia name crosswalk; manual aliases; LegiScan member identities; unified member votes; reviewed ontology-v3 roll-call mappings.
- Outputs: Stable reviewed-evidence identity staging, repaired pre-election candidate ideology, separate career ideology, ambiguity queue, and four-session coverage audit.
- Acceptance checks: All 2022 ballot codes with verified crosswalk evidence decode; legislative district strings parse correctly; no duplicate candidate/member assignments within cycle; pre-election evidence never exceeds election year; career evidence is labeled through 2026; every member with at least four sessions has raw/classified counts; ambiguous identities stay unresolved; focused tests pass.
- Handoff recipient: `validation_release`, followed by separate analysis and web-product tasks.
- Known risks: Aliases and chamber switches; successor/predecessor district changes; post-election evidence must never leak into election analysis.
