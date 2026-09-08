# Task contract: SOUTHERN-RELEASE-STATUS-GUARD-20260908

- Accountable role: `validation_release`
- Owner: `/root`
- Status: `complete`
- Objective: Prevent the Southern historical and map builders from consuming the exact pending v3 run as though it had release approval.
- Product/layer and checklist IDs: Southern historical WAR validation/release integration; supports `southern-06`, `southern-07` and `southern-12` without completing them.
- Dependencies: v3 run `WAR-POST2016-V3-8BB52074EC806C5BF6BF`, independent review `SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_07.md`, and current readiness audit.
- Non-goals: No warehouse mutation, source promotion, model fit, candidate rating, probability, generated model output, public-site rebuild or publication.
- Upstream snapshot: v3 manifest SHA256 `0ea558730b9e953d95853d552960886c855b8bb3f9fb9cb2ee0a3c44a47c7638`; decision `blocked_insufficient_evidence`.
- Read scope: Southern v3 and historical manifests, existing builders, focused tests, review/readiness evidence and the Alabama 2018 official source.
- Write scope: `scripts/southern_war_release_gate.py`; `scripts/build_southern_historical_war_v1.py`; `scripts/build_southern_war_map.py`; `scripts/tests/test_southern_war_release_gate.py`; `scripts/tests/test_southern_historical_war_v1.py`; `scripts/tests/test_southern_war_map.py`; `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json`; `project_docs/audits/SOUTHERN_RELEASE_READINESS_2026_09_07.md`; `project_docs/model/SOUTHERN_HISTORICAL_WAR_V1.md`; `project_docs/CANONICAL_PIPELINES.md`; this contract and active-task row.
- Warehouse mode: `read-only`
- Inputs: Exact manifest/review hashes and query-only readiness evidence.
- Outputs: Exact release-decision gate, downstream pre-read enforcement, focused tests and documented empty-slice/source limitations.
- Acceptance checks: Current blocked decision is exact and rejected before model rows are read; an exact approved fixture passes; changed manifest/run/review hashes fail; workflow validation passes; no model builder executes. Accepted with 15 focused tests passing in 12.60 seconds.
- Review requirement: Focused self-checks. A future approval file still requires an independent scientific reviewer and exact source evidence.
- Publication authority: `none`
- Recovery/replay: Code and documentation only. Remove the guard imports/calls to roll back; no warehouse or model artifact requires restoration.
- Handoff recipient: `validation_release`
- Known risks: Existing generated historical/public artifacts retain their old bytes and stale status claim; the gate prevents regeneration but does not retroactively rewrite them.

## Handoff

The exact v3 decision is now an enforced pre-read dependency for both downstream
builders. Current execution stops at `blocked_insufficient_evidence`; the tests
prove the warehouse/model rows are not read after that decision. The official
Alabama 2018 canvass was acquired and visually verified, but remains unregistered
and unintegrated. Source reconciliation and independent scientific acceptance
must produce a new exact review record before the decision can be approved.

A direct historical-builder preflight exited 1 at the release gate. SHA256 checks
before and after the attempt matched for the historical manifest and all four
data outputs, confirming that the blocked command produced no rating artifact.
