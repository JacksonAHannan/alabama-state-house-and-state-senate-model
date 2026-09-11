# Task contract: IDEOLOGY-ROLLCALL-COVERAGE-AUDIT-001

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Audit the complete path from archived Alabama member votes through roll-call classification, candidate identity resolution, pre-election scoring, and candidate issue evidence, and produce a prioritized repair queue.
- Non-goals: Change canonical warehouse tables, alter human roll-call adjudications, fabricate unrecorded votes, or publish website files.
- Upstream snapshot: Current unified 1998–2026 roll-call warehouse, LegiScan archives, historical journals, candidate identity staging, ontology-v3 classifications, and candidate ideology marts as of 2026-08-24.
- Read scope: `data/raw/legiscan/alabama/`; `data/processed/legislative/`; `data/processed/ideology/`; `data/processed/elections/`; legislative and identity pipeline scripts; existing manual identity evidence.
- Write scope: `scripts/audit_legislative_ideology_coverage.py`; `scripts/tests/test_legislative_ideology_coverage_audit.py`; `data/processed/ideology/legislative_ideology_coverage_audit_`; `project_docs/audits/LEGISLATIVE_IDEOLOGY_COVERAGE_AUDIT.md`; `project_docs/coordination/IDEOLOGY-ROLLCALL-COVERAGE-AUDIT-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Normalized member votes, roll-call metadata and ontology status, legislator rosters, canonical candidate elections, identity crosswalk, pre-election score mart, and candidate legislative evidence.
- Outputs: Coverage funnel, session/chamber audit, candidate identity/scoring audit, deterministic-recovery candidates, and a documented repair sequence.
- Acceptance checks: All source years/chambers reconcile to the unified warehouse; raw votes are never interpreted as ideological classifications; every incumbent or inferred repeat officeholder without an identity/score receives a reason; duplicate/cross-chamber risks are identified; audit outputs are deterministic and tests pass.
- Handoff recipient: `legislative_ideology` identity-repair task, then `validation_release`.
- Known risks: Canonical incumbency is incomplete outside 2010–2018; LegiScan legal names differ from ballot names; party switching is common; identical House/Senate district numbers can create false fallbacks; 1994 recorded-vote archives remain unavailable.
