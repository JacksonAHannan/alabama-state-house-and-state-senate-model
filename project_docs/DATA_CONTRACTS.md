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

