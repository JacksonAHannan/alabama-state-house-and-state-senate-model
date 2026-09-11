# Southern WAR preparation with parallel finance interfaces

## Purpose

This pipeline prepares auditable Southern legislative outcomes, baseline and
incumbency context, the Alabama 2026 incumbency roster, and an exact-key
campaign-finance overlay. It does not fit or describe a forecast.

## Inputs

- `fact_southern_legislative_final_candidate_election` and
  `all_southern_legislative_candidate_election_observations` in the central
  warehouse.
- `data/processed/war/southern_war_panel_v1/southern_war_panel.csv`, including
  its versioned manifest, for previously validated baseline and incumbency
  context.
- `data/raw/candidates/southern_state_legislative_incumbents_2016_2026.xlsx`.
- `data/processed/war/2026_race_incumbency.csv` for comparison only.
- `data/processed/incumbency/southern_incumbency_race_roster_2016_2024.csv`.
- `data/processed/polling/virginia_generic_ballot_environment.csv`.
- `mart_southern_race_finance` for the optional finance overlay.

Every file input is SHA-256 hashed and registered. The workbook's populated
`Incumbents` sheet contains Alabama 2026 only. Its historical and other-state
source maps are acquisition leads, not incumbent observations.

## Outcome selection

The outcome unit is one state, cycle, chamber, and district. A source
observation is model-valid only when it has exactly one Democrat and one
Republican with positive votes, every candidate vote is observed, and the
provider does not mark the contest unusable or uncontested. One complete
provider observation is selected; candidate rows are never combined across
sources.

The final regular-stage key follows the warehouse rule. Louisiana selects the
November runoff when one exists for the district and otherwise retains the
October first round. Canonical observations are preferred. A lower-ranked
valid observation remains visibly labeled `model_eligible_fallback`. The sole
external fallback permission is for validated Texas official companion-panel
contests missing from the central regular-stage key.

## Context and training gates

The context table is unique on the same four-field race key. The training view
declares a 1:0..1 left join from outcome to context and computes direct
overperformance only when a baseline exists. Readiness is one of strict,
research, missing context, missing baseline, missing incumbency, or another
explicit gate failure. Missing input is never converted to zero.

The finance-free interface retains `finance_status=excluded_not_ready` and has
no finance amounts. The finance-included interface joins `mart_southern_race_finance`
at exact state/cycle/chamber/district grain. It publishes amounts and the D/R
log ratio only when both candidate observations and identities are complete;
otherwise they remain null and the row is `war_ready_finance_unobserved`.

Same-year observed ticket context is used when available. Virginia 2019 and
2023 have no same-year statewide/federal ticket and therefore use the national
generic congressional ballot polling average dated on election day. Prior-
cycle governor returns are not substituted. Virginia 2017 and 2021 use their
same-year governor context but remain research-only where allocation uses
cross-election precinct membership.

## Alabama 2026 incumbency

The populated workbook rows are verified against their normalized source
evidence in the warehouse. Each of Alabama's 105 House and 35 Senate seats is
materialized with incumbent-running, open-seat, party, and review fields.
Differences from the earlier race roster are proposed review items with a
rationale and stable identifier; they are not silently adjudicated.

## Outputs

Warehouse objects:

- `mart_southern_war_outcome`
- `mart_southern_war_context_feature`
- `mart_southern_war_training_no_finance`
- `qa_southern_war_training_no_finance_coverage`
- `mart_southern_war_training_with_finance`
- `qa_southern_war_training_with_finance_coverage`
- `mart_alabama_2026_incumbency_roster`

Versioned compatibility exports are under
`data/processed/war/finance_free_southern_war/`, with a build manifest that
identifies the code version, run ID, hashes, and validation totals.

## Reproduction

```powershell
python scripts/load_southern_war_preparation_warehouse.py
python -m pytest scripts/tests/test_southern_war_preparation_warehouse.py -q
```
