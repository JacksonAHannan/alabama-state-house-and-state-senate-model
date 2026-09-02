# Data contracts

## Required source manifest fields

Every raw input must register:

| Field | Meaning |
|---|---|
| `source_file_id` | Stable namespaced identifier |
| `provider` | Publishing organization |
| `source_url` | Retrieval location |
| `retrieved_at` | UTC retrieval timestamp |
| `sha256` | Exact artifact hash |
| `media_type` | File/media type |
| `license_or_terms` | Known reuse terms or review status |
| `state_code` | Two-letter postal code |
| `cycle` | Election/legislative cycle when applicable |
| `geography_vintage` | District/Census vintage when applicable |
| `authoritative_scope` | Facts for which the source is authoritative |
| `ingest_status` | discovered, acquired, parsed, rejected, or superseded |

## Canonical election grain

The core candidate-election interface is one candidate-party-contest record.
It must distinguish chamber, district plan, district, election stage, election
date, party, votes, vote share, incumbency evidence, contest status, and source
coverage. Uncontested is a contest property; it is not inferred merely from a
missing opposing row.

## Common enums

- `chamber`: `lower`, `upper`
- `election_stage`: `primary`, `primary_runoff`, `general`, `special`,
  `special_runoff`, `other`
- `party_family`: `democratic`, `republican`, `independent`, `other`, `unknown`
- `review_status`: `proposed`, `approved`, `rejected`, `superseded`
- `value_status`: `observed`, `derived`, `imputed`, `unknown`, `not_applicable`

Original provider values must also be retained.

## Join contracts

Each production join documents:

- left and right grain;
- expected cardinality (`1:1`, `1:m`, `m:1`);
- unmatched-row policy;
- duplicate-key failure behavior;
- temporal and geographic validity conditions;
- reconciliation metric and tolerance.

Many-to-many joins require an explicit bridge or allocation-weight table.

## Cross-state exports

Validated state repositories should eventually publish versioned tables for:

- contests and candidate results;
- district-plan metadata;
- candidate and legislator identities;
- district demographic features;
- finance/resource features;
- legislative ideology features;
- model forecasts and uncertainty;
- run metadata and validation summaries.

Every export includes `contract_version`, `state_code`, `build_run_id`, and the
relevant as-of/cutoff date.

## Southern historical WAR map contract

The public Southern WAR explorer covers the prespecified regular-election
schedule from 2016 through 2022 for AL, AR, FL, GA, KY, LA, MO, MS, NC, OK,
SC, TN, TX, and VA. State-specific odd-year elections and staggered chambers
retain their actual election years. A map slice is uniquely keyed by
`state_code`, `cycle`, and `chamber`; a scored race is additionally keyed by
the normalized provider district identifier.

WAR remains a race residual in Democratic two-party margin points:
`raw_gap = legislative_dem_margin - baseline_dem_margin` and
`war = raw_gap - fitted_structural_expected_gap`. Strict races after 2016 use
the published Southern WAR v3 same-cycle fitted residual. Strict 2016 races are
descriptive backward applications of the selected post-2016 Southern
`decaying_lag` ridge model with alpha 100; the model is fit only on races after
2016. Candidate-cycle views are exact party orientations of the same race
score. Research-only context rows, uncontested races, non-D/R races, and
districts without a model-valid outcome remain unscored and are never assigned
WAR zero.

Election-year Census cartographic-boundary files supply display geometry. Each
raw ZIP is immutable and registered with its URL, retrieval time, SHA-256,
terms, state, chamber, election year, and geographic vintage. Geometry joins
are `1:0..1` from a scored race to one district feature within the exact
state/year/chamber file. Duplicate geometry identifiers or an unmatched scored
race fail publication. Census display geometry does not adjudicate the
warehouse's provider-reported district-plan vintage; both provenance statements
remain visible.

Finance is an optional descriptive overlay joined `1:0..1` on the exact race
key. Amounts and ratios are published only where the finance mart marks the
race complete. Missing finance remains `unknown`, not zero. Fundraising does
not enter headline WAR because the prespecified nested time-forward finance
gate failed; state-level coverage limitations are published alongside the map.
