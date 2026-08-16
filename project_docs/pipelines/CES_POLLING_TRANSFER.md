# CES demographic polling transfer

## Purpose

This experimental pipeline tests whether demographic movement in YouGov's
national generic-ballot tracker improves forecasts of Alabama Democratic
two-party House preference. It does not estimate candidate overperformance.
Polling changes the prospective partisan baseline; CMO remains a separate
candidate-level adjustment.

## Sources

- CES Cumulative Common Content v12, 2006-2025, DOI `10.7910/DVN/II2DB6`.
- YouGov Congressional Ballot Voting Intention tracker, weekly demographic
  crosstabs.

CES `voted_rep_party` is restricted to Democratic and Republican choices.
The primary series uses the year-specific `weight`, which is present in every
year. Estimates using `weight_post` are retained as sensitivity rows because
that weight exists only for 2012, 2016, 2018, 2020, and 2022.

## Forecast experiment

For demographic group *g* and target election *t*:

`logit(AL[t,g]) = logit(AL[t-2,g]) + beta * (logit(YouGov[t,g]) - logit(US CES[t-2,g]))`

The pooled beta is learned only from elections preceding each backtest and is
shrunk toward 1.0. Backtests cover 2018, 2020, 2022, and 2024. Benchmarks are a
carry-forward estimate and a uniform national swing.

## Current result and release gate

Across demographic groups, the pooled demographic transfer reduces weighted
MAE modestly versus carry-forward, but it beats carry-forward in only one of
four election years. The release gate requires improvement in at least three
of four cycles and positive pooled improvement. It therefore fails and the
2026 demographic output remains diagnostic.

Age, education, gender, and race are overlapping marginal distributions.
Their projections must not be added together. Production district use requires
joint demographic cells and multilevel regression/poststratification, or a
validated ensemble that treats each dimension as a separate forecast.

## Outputs

- `data/processed/polling/ces_house_vote_demographics.csv`
- `data/processed/polling/ces_alabama_house_vote_coverage.csv`
- `data/processed/polling/ces_yougov_transfer_backtest.csv`
- `data/processed/polling/ces_yougov_transfer_backtest_summary.csv`
- `data/processed/polling/2026_ces_yougov_demographic_projection_experimental.csv`
- `data/processed/polling/ces_yougov_transfer_release_gate.csv`
