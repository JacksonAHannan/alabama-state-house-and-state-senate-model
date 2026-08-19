# 2026 Alabama legislative forecast methodology

## Public model views

The forecast publishes two views of the same candidate-margin-overperformance
(CMO) expectation:

`Basic = poll-adjusted presidential baseline + 20% × expected CMO`

`Fundamentals+ = poll-adjusted presidential baseline + 100% × expected CMO`

Basic is the default. Its partial pooling is a guardrail against overfitting and
structural change. Fundamentals+ shows the full historically estimated
relationship. Switching views updates district margins, ratings, intervals,
probabilities, and chamber simulations together.

## Poll-adjusted presidential baseline

The structural anchor is each district's allocated 2024 presidential margin.
The 2024-to-2026 adjustment uses national generic-ballot polls from pollsters
graded **B or better** in the supplied Nate Silver ratings file. The feed keeps
the newest eligible poll from each pollster in a rolling 60-day window, weights
likely-voter, registered-voter, and adult samples differently, and applies a
21-day recency half-life.

Reviewed race and education crosstabs, Catalist national vote history, Alabama
ecological-inference estimates, and ACS race-by-education district composition
transfer the national environment into Alabama. The modeled change is added to
the observed district result; a fitted demographic level never replaces the
observed 2024 vote.

Historical testing supports a post-2016 nationalization ramp: no national swing
is transferred through 2014, half is transferred in 2018, and the full swing is
transferred in 2022 and prospectively in 2026. A 125% continued-nationalization
case remains an experimental scenario rather than either public model view.

## CMO expected-performance model

The expectation predicts legislative margin residuals above the environment
baseline using contextual information known for every district:

- nonwhite share and white-college share;
- prior presidential trend and a flag identifying where it is available;
- House or Senate chamber;
- 2008 and 2016 era breaks; and
- years elapsed since those breaks.

Numeric fields are median-imputed inside the pipeline and standardized before
ridge estimation. Historical cycles receive equal total training weight.

Candidate incumbency, fundraising, ideology, and prior CMO are deliberately
excluded. They can be consequences of persistent candidate strength and
survival, so treating them as independent causes would subtract part of the
phenomenon that CMO is intended to capture. The expectation is contextual and
does not identify an individual candidate effect.

## Forward validation

Expanding-window tests train only on elections earlier than the held-out cycle.
The website reports cycle-balanced mean absolute error across all eligible
holdouts, the post-2016 holdouts, and 2022 separately. Fundamentals+ is the full
substantive estimate; Basic remains the default because only a small number of
election environments—and two after 2016—identify these relationships.

## Uncertainty and seats

Each public view uses 50,000 deterministic-seed simulations centered on its own
district margins. Error scales come from that view's expanding-window errors.
Each draw contains:

- one statewide error shared by every modeled district;
- one House or Senate error shared within the chamber; and
- one district-specific error.

Win probabilities, 80%/95% intervals, and chamber seat distributions are
empirical simulation quantities. Certified single-major-party districts are
fixed in chamber totals. Independent-only and unresolved districts remain
unmodeled.

The short historical series cannot establish durable calibration. Polling,
demographic-transfer, model-selection, and geographic-correlation uncertainty
are not yet modeled separately, so probabilities remain provisional.

## Automated polling and site refresh

The official YouGov/Economist archive is ingested automatically, with each PDF
stored alongside its URL, retrieval time, and SHA-256 hash. VoteHub remains the
broader discovery feed; locally archived releases supplement it when its API
lags or omits a document.

```powershell
python scripts/refresh_2026_forecast.py
```

That command refreshes poll discovery, the B-or-better quality gate, the
official YouGov feed, the polling environment, district baseline, both model
views, simulations, and website exports in dependency order.
