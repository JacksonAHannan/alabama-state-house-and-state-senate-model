# Finance feature specification

> **Documentation status — 2026-09-05:** Superseded source-selection snapshot. The blanket historical-source and committee-selection rules below are not the current central finance authority policy. Use the [warehouse architecture](../WAREHOUSE_ARCHITECTURE.md), [data contracts](../DATA_CONTRACTS.md) and [Southern finance pipeline](../pipelines/SOUTHERN_FINANCE_WAREHOUSE.md). Preserve the dated snapshot; unknown finance remains distinct from zero.

## Frozen sources

- **2010–2022:** FollowTheMoney candidate totals are the definitive historical fundraising source. The modeled field is `Total $`, matched within cycle, chamber, district, and party.
- **2026:** Alabama state candidate fundraising summaries are the definitive prospective source. One main committee row is selected per candidate: an active committee is preferred, followed by the row with the largest monetary contributions.
- **Snapshot cutoff:** 2026-08-14. Files currently in `data/raw/finance/alabama` constitute the frozen snapshot.

Fundraising, expenditures, beginning cash, and ending cash remain separate variables. FTM fundraising and state transaction expenditures are not combined into a single total.

## Missing values

A missing matched committee is recorded as unknown with a missingness indicator. It is not an observed zero. A zero-filled field may be produced for sensitivity analysis, but it is never the primary published value.

Finance is excluded from headline historical Total CMO. It appears only in fundraising-adjusted or expenditure-adjusted sensitivity specifications. Prospective model selection is based on forward-cycle performance against simpler non-finance benchmarks.
