# Southern release readiness — 2026-09-08 continuation

Status: source lineage resolved; independent scientific review of the retrained v3
run pending or recorded in `SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_08.md`; release
decision in `SOUTHERN_V3_RELEASE_DECISION.json`. Supersedes the accounting in
`SOUTHERN_RELEASE_READINESS_2026_09_07.md`, which remains history.

## Warehouse checkpoint

Outcome and context run `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`, rebuilt after the
Alabama certified-canvass integration (`ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.md`).
`scripts/audit_southern_release_readiness.py` output is
`SOUTHERN_RELEASE_READINESS_2026_09_08.json`.

| Measure | Value |
|---|---|
| Existing outcome rows | 4,582 |
| Recorded strict rows | 4,280 |
| Excluded research-only rows | 302 |
| Missing scalar source-file IDs | 0 |
| Scheduled slices | 116 |
| Empty scheduled slices | 2 (VA 2017 lower, VA 2021 lower) |

## Exclusion disposition

The 302 excluded outcomes are unchanged and remain reason-coded, not scored:

- 151 `baseline_not_strict`: Virginia lower-chamber outcomes (60 in 2017, 91 in 2021)
  whose governor baseline uses 2019-plan cross-election precinct membership with
  locality fallback. Retained as explicit exclusions; recovery requires registered
  contemporaneous plan/membership and allocation reconciliation. No substitute
  comparator was introduced.
- 151 `incumbency_experimental`: rows across ten states in 2019, 2023 and 2024 whose
  incumbency rests on experimental prior-winner continuity without roster evidence in
  `source_southern_incumbency_evidence`. No source-backed evidence exists in the
  warehouse to recover them; a prior-winner non-match cannot establish an open seat.
  Retained as explicit exclusions.

Both classes are published per state in the historical builder's
`state_release_coverage.csv` and the map methodology's limitations section.

## Alabama source lineage

All 97 Alabama strict outcomes now carry the certified canvass source file through
the reviewed canonical/certified bridge (377 rows, 21 corrections). Third-party
totals for Alabama come from the certified sets. Details, hashes and stale
dependencies are in `ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.md`.

## Model and evidence

- Retrained v3 `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` on the rebuilt warehouse:
  3,660 strict races, `decaying_lag` alpha 100, lag added-value gate passed, finance
  nested gate fails (finance stays outside headline WAR). Against the archived run
  `WAR-POST2016-V3-8BB52074EC806C5BF6BF`, WAR moved by at most 0.076 points, all in
  Alabama; no `war_party` sign changed; inputs changed only for the seven corrected
  strict races and the 97 Alabama third-party totals.
- Sensitivity and uncertainty audit `SOUTHERN_V3_CONTEXT_SENSITIVITY.md` (machine
  outputs in `data/processed/war/post2016_southern_war_v3_sensitivity/`): parity gate
  passed on the exact run; 2,376 of 3,660 races lack validated lag context; the
  no-lag same-cycle alternative moves missing-context WAR by MAE 0.332 with 1.8%
  sign changes; within-cycle bootstrap median expected-gap SE 0.759 points and
  79.2% of 5–95 WAR intervals exclude zero. These are descriptive same-cycle
  diagnostics, not predictive validation.

## Remaining acceptance

- Independent review decision for the exact retrained run.
- Only after approval: historical and map builders, browser and download checks,
  state-level limitations, documentation and checklist updates. Publication remains
  a separate authorized action.
