# Task contract: IDEOLOGY-POSTREPAIR-COVERAGE-005

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Refresh the end-to-end coverage audit after the identity, historical final-vote, and candidate-evidence rebuilds, resolve the remaining source-backed deterministic identity queue, and verify the documented deltas.
- Acceptance checks: Audit classification count equals 60,704; no roll call remains outside the classification table; score and direct-evidence candidate counts agree; known false identities remain quarantined; no high-confidence deterministic identity recovery remains; audit tests and workflow validator pass.
- Read scope: Completed ideology repair outputs, normalized roll-call warehouse, canonical candidate roster, and prior audit snapshots.
- Write scope: `data/manual/ideology/candidate_legislator_identity_overrides.csv`; `scripts/tests/test_legislative_ideology_coverage_audit.py`; `data/processed/ideology/candidate_`; `data/processed/ideology/legislator_pre_election_window_scores.csv`; `data/processed/ideology/long_service_ideology_coverage_audit.csv`; `data/processed/elections/canonical_cmo_candidates_with_ideology_v3.csv`; `project_docs/audits/FRONTIER_IDEOLOGY_VALIDATION.csv`; `data/processed/ideology/legislative_ideology_coverage_audit_`; `project_docs/audits/LEGISLATIVE_IDEOLOGY_POST_REPAIR_COVERAGE.md`; this contract; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: `IDEOLOGY-CANDIDATE-EVIDENCE-REBUILD-004` and prior audit baseline.
- Expected outputs: Current coverage funnel and concise before/after audit.
- Warehouse mode: `read-only`.
- Handoff recipient: user; a separate model-analysis task is required before hypothesis/page updates.
