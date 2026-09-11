# Task contract: IDEOLOGY-IDENTITY-SCORE-REPAIR-002

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Repair proven candidate-to-legislator identities, chamber attribution, prior-officeholder inference, cross-chamber pre-election scoring, and candidate coverage labels without weakening ambiguity quarantines.
- Acceptance checks: Role determines service chamber; all manual overrides have evidence and valid member IDs; no duplicate candidate-cycle/member assignment survives; cross-chamber scores retain their source chamber; no score window extends beyond the election year; focused tests pass; before/after coverage is reported.
- Read scope: Canonical candidate elections; LegiScan roster and unified roll-call warehouse; current identity, score, and candidate ideology outputs; manual candidate identity evidence; completed coverage audit.
- Write scope: `data/manual/ideology/candidate_legislator_identity_overrides.csv`; `scripts/repair_candidate_legislator_identities.py`; `scripts/build_full_candidate_legislative_ideology.py`; `scripts/tests/test_candidate_legislator_identity_repair.py`; `scripts/tests/test_full_candidate_legislative_ideology.py`; `data/processed/ideology/candidate_legislator_identity_crosswalk.csv`; `data/processed/ideology/candidate_legislator_identity_review.csv`; `data/processed/ideology/candidate_ideology_full_universe.csv`; `data/processed/ideology/candidate_ideology_full_coverage.csv`; `data/processed/ideology/legislator_pre_election_window_scores.csv`; `data/processed/ideology/candidate_career_ideology_through_2026.csv`; `data/processed/ideology/long_service_ideology_coverage_audit.csv`; `project_docs/audits/CANDIDATE_LEGISLATOR_IDENTITY_SCORE_REPAIR.md`; this contract; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: `IDEOLOGY-ROLLCALL-COVERAGE-AUDIT-001`; canonical candidate records; unified roll-call warehouse; reviewed candidate identity sources.
- Expected outputs: Reviewable identity overrides, corrected crosswalk, corrected cycle-valid scores with explicit score chamber, coverage comparison, and tests.
- Warehouse mode: `read-only`
- Handoff recipient: `legislative_ideology` historical final-vote coverage task, then `validation_release`.
- Known risks: Cross-chamber transitions can be confused with same-number districts; a future district label can appear on a prior House roster row; historical incumbency flags are incomplete; manual identities must not be inferred from party/district alone.
