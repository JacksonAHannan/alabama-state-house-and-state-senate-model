# Task contract: IDEOLOGY-COVERAGE-RERUN-001

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild all cycle-valid legislative evidence, ontology-v3 candidate features, absolute ideology/CMO analysis, and Democratic caucus clusters from the repaired identity staging.
- Read scope: Validated identity staging; reviewed ontology/manual evidence; canonical CMO/election exports; current analysis scripts and tests.
- Write scope: `data/processed/ideology/candidate_legislative_position_evidence_v3.csv`; `data/processed/ideology/candidate_position_evidence_v3_all_sources.csv`; `data/processed/ideology/candidate_position_evidence_v3_unmatched.csv`; `data/processed/ideology/candidate_issue_valence_v3.csv`; `data/processed/ideology/candidate_family_valence_v3_all_sources.csv`; `data/processed/ideology/candidate_ideology_v3_model_features.csv`; `data/processed/ideology/candidate_issue_valence_v3_coverage.csv`; `data/processed/elections/canonical_cmo_candidates_with_ideology_v3.csv`; `research/cmo_ideology/absolute_rebuild_*`; `research/cmo_ideology/democratic_clusters/`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; this contract and ledger row.
- Warehouse mode: `read-only`
- Upstream inputs: `IDEOLOGY-IDENTITY-CAREER-REPAIR-001` review candidate and current validated CMO.
- Expected outputs: Fresh pre-election evidence, feature panels, hypothesis estimates, and natural-cluster assignments with no stale rows.
- Acceptance checks: Pipeline completes; stable candidate IDs reconcile; temporal eligibility holds; analysis and cluster tests pass; outputs are newer than repaired identity mart.
- Handoff recipient: `validation_release`, then `web_product`.
