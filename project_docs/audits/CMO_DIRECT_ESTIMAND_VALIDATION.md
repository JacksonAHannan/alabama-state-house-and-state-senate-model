# CMO v3 direct-estimand validation

- Task: `VALIDATE-CMO-DIRECT-001`
- Reviewer: `/root/blue_oxblood_validation`
- Candidate: `CMO-DIRECT-ESTIMAND-001`
- Decision: **PASS**

The CMO v3 race and candidate outputs implement the documented direct,
source-aware ticket-overperformance estimand. All headline values, alternative
ticket comparisons, candidate orientations, and uncertainty intervals reconcile
independently.

## Coverage and keys

- `cmo_v3_races.csv`: 509 unique cycle/chamber/district races.
- `cmo_v3_candidates.csv`: 1,018 unique race/party rows.
- Every race has exactly one Democratic and one Republican candidate row.
- No duplicate reusable keys were found.

## Selected source baseline

The declared source policy is internally exact:

| Selected source | Races | Independent reconstruction |
|---|---:|---|
| `state_ticket_vote_weighted` | 413 | selected baseline equals state-ticket margin |
| `state_ticket_70_federal_30` | 96 | selected baseline equals 70% state + 30% federal |

All blended rows occur in 2018 or 2022. Earlier cycles remain on the state
ticket, as documented. The 2018 cycle has one state-only row where the federal
gate did not select the blend. No undeclared source label or presidential
fallback row appears in the scored output.

The five-row baseline tournament was independently reconstructed from the race
file. Race counts, mean absolute gaps, median gaps, and 95th-percentile absolute
gaps agree with every published tournament value to below `1e-12`.

## Race arithmetic

For all available observations:

```text
headline CMO     = legislative D margin - selected source-aware baseline
state-ticket CMO = legislative D margin - state-ticket baseline
federal CMO      = legislative D margin - federal baseline
presidential CMO = legislative D margin - previous presidential baseline
```

Reconciliation counts are 509 headline, 509 state-ticket, 449 federal, and 488
presidential observations. Null patterns also agree exactly. Maximum differences
were `1.42e-14`, ordinary CSV floating-point precision.

## Candidate orientation and zero-sum structure

For every candidate and every available ticket comparison, the candidate score
equals the Democratic-oriented race score times +1 for Democrats and -1 for
Republicans. Within all 509 races, Democratic plus Republican headline CMO is
exactly zero. State, federal, and presidential candidate comparisons are also
zero-sum wherever observed.

Uncertainty endpoints are correctly reversed for Republicans:

```text
Republican low  = - Democratic high
Republican high = - Democratic low
```

Career means and partial-pooled career values remain separately labeled
secondary summaries; they do not replace election-level candidate CMO.

## Uncertainty reconstruction

All 509 uncertainty records independently reproduce:

```text
specification SD = sample SD(state, federal, presidential ticket CMO)
quality penalty  = 5 * (1 - baseline reliability)
contest penalty  = 0 meaningful, 2 marginal, 5 nominal
radius           = max(2, 1.96 * specification SD + quality + contest penalty)
low/high         = headline CMO -/+ radius
```

Baseline reliability also equals `1 - baseline_fallback_share`, clipped to
zero–one, for every race. Maximum reconstruction differences are at most
`2.13e-14`. Every interval strictly contains its headline score. The output has
508 meaningful contests and one nominal contest.

## Morrow 1998 HD-18

The direct reconciliation is:

| Quantity | Democratic margin |
|---|---:|
| Legislative result | +15.598886 |
| Selected state-ticket baseline | +15.088573 |
| Headline CMO | **+0.510313** |

The Democratic candidate row for Morrow is +0.510313; Britnell's Republican row
is -0.510313. The superseded regression-context score of -52.802 is not used.

## Regression-context isolation

No `context_cmo`, `expected_margin_context`, `within_cycle_cmo`, or context-
extrapolation field appears in the v3 race, candidate, or baseline-tournament
outputs. Those fields occur only in `cmo_v3_context_pathology_audit.csv`.

The audit contains exactly 37 rows, all with an absolute context-versus-direct
delta above 20 points. Its context fields reconcile to the v2 diagnostic inputs,
and `context_extrapolation_delta = context_cmo - headline_cmo` for every row.
This confirms regression context is audit-only.

## Tests

```text
5 passed in 0.51s
Agent workflow validation passed.
```

Commands:

```powershell
python -m pytest scripts/tests/test_cmo_direct_estimand.py -q
python scripts/validate_agent_workflow.py
```

## Release decision

**PASS.** The v3 direct ticket-overperformance outputs satisfy the contracted
arithmetic, source-selection, orientation, uncertainty, Morrow, and
regression-isolation gates.

Non-blocking follow-up: expand `cmo_v3_provenance.csv` beyond its current v2
race-input hash to include code/configuration and output hashes under the
project-wide generated-artifact contract.
