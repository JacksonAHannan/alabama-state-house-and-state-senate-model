# Caucus reclustering validation

**Task:** `VALIDATE-CAUCUS-RECLUSTER-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The party-specific clustering is outcome-blind, deterministic, exactly joined
to current CMO v4, and interpreted in proportion to its stability diagnostics.
Both prior release blockers are resolved: the report now gives the required
Republican robustness warning and the stale duplicate test module no longer
breaks collection.

## Outcome-blind assignment

`issue_columns()` selects only columns prefixed
`primitive_conservative_`. Its coverage, variance, and two-sided-pole rules use
issue-position values alone. The current panel supplies 17 Democratic and 13
Republican dimensions.

CMO, election results, winner status, incumbency, finance, demographics,
district partisanship, and era do not enter KMeans. Era appears only in a
post-fit sensitivity specification. Performance outcomes are attached after
assignment for descriptive summaries.

## Current CMO v4 equality

`cluster_cmo_v4_check.csv` contains all 281 clustered candidate-cycles: 117
Democrats and 164 Republicans. Every row matches a canonical candidate ID in
`cmo_v4_candidates.csv`; the maximum absolute difference between attached
`candidate_cmo` and current `candidate_war_cmo` is `3.55e-15`. The production
join is one-to-one and raises on missing or mismatched v4 values.

## Determinism and k selection

The implementation fixes all KMeans and bootstrap seeds. Two independent
in-memory fits for each party produced identical candidate assignments,
identical selected k, and zero numerical difference across diagnostics.

`choose_k()` first enforces at least 12 candidate-cycles and an 8-percent share
in the smallest cluster, then maximizes the declared
silhouette-plus-bootstrap score with lower k as the deterministic tiebreaker.
Reapplying the rule selects the published two Democratic clusters and three
Republican clusters.

| Party | k | Silhouette | Bootstrap ARI | Smallest cluster |
|---|---:|---:|---:|---:|
| Democratic | 2 | 0.212 | 0.829 | 41 (35.0%) |
| Republican | 3 | 0.222 | 0.866 | 48 (29.3%) |

## Proportional interpretation

The rebuilt report displays all three relevant Republican sensitivity results:

- KNN versus median-imputation ARI: **0.239**;
- absolute versus within-era ARI: **0.198**; and
- position versus missingness ARI: **0.220**.

Immediately after the Republican performance summary it now warns that the
discrete solution changes substantially under alternate imputation or
within-era normalization and that labels describe historical tendencies, not
stable caucus membership. Its general limitations also identify low
silhouettes, nonrandom issue-evidence missingness, repeated people, and the
descriptive—not causal—status of performance differences. The report therefore
does not overstate the three named Republican groupings.

## Tests

Commands run:

```text
python -m pytest scripts/tests/test_democratic_ideological_clusters.py -q
python -m pytest -q
python scripts/validate_agent_workflow.py
```

Results:

- focused reclustering suite: **2 passed**;
- full suite: **380 passed**, 11 existing pandas/SWIG warnings;
- agent workflow validation: passed.

The obsolete `tests/test_democratic_ideological_clusters.py` file is absent.
The active test module checks issue-only inputs, selected-k fidelity, the weak
Republican KNN/median result, and presence of the robustness/missingness text.

## Release decision

**PASS.** The analytical outputs and their interpretation satisfy the release
contract. No blocking or nonblocking reclustering finding remains.
