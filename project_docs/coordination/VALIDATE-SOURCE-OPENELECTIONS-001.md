# Task contract: VALIDATE-SOURCE-OPENELECTIONS-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the commit-pinned OpenElections historical acquisition bundle and manifest.
- Non-goals: No source, parser, warehouse, model, or website changes.
- Upstream snapshot: `SOURCE-OPENELECTIONS-HISTORICAL-001` review candidate dated 2026-08-22.
- Read scope: Acquisition pipeline/tests, raw OpenElections gap directory, manifest, and source note.
- Write scope: `project_docs/audits/OPENELECTIONS_HISTORICAL_ACQUISITION_VALIDATION.md`; `project_docs/coordination/VALIDATE-SOURCE-OPENELECTIONS-001.md`
- Warehouse mode: `read-only`
- Inputs: 172 acquired files across fourteen state-cycle combinations.
- Outputs: Pass/fail provenance and coverage report.
- Acceptance checks: Recompute all hashes/sizes; verify pinned paths exist upstream; verify fourteen expected combinations, general-stage filtering, and no primary/special contamination; focused tests pass.
- Handoff recipient: `elections_geography`
- Known risks: Georgia 2014 is explicitly unofficial; OpenElections remains secondary.
