# Alabama FCPA principal campaign committee finance audit

## Finding

The previous finance pipeline substantially overstated missingness because it
matched transaction extracts and political-race summaries to candidate display
names. Alabama's authoritative filing unit is the Principal Campaign Committee
(PCC), identified by a persistent committee ID and a separate internal record
ID. Candidate legal names, committee renewals, dissolved committees, nicknames,
and roster formatting can all prevent a candidate-name-only match.

The committee search audited all 761 modeled candidate-cycles covered by the
electronic FCPA system: 2014, 2018, 2022, and 2026. Search results were required
to agree on legislative chamber, district, and party before name evidence was
considered.

| Cycle | Candidate-cycles | PCC recovered | Coverage |
|---:|---:|---:|---:|
| 2014 | 197 | 184 | 93.4% |
| 2018 | 204 | 196 | 96.1% |
| 2022 | 173 | 170 | 98.3% |
| 2026 | 187 | 183 | 97.9% |
| **Total** | **761** | **733** | **96.3%** |

Among candidates called unmatched by the transaction-name pipeline, the PCC
search recovered 11 of 14 in 2014, 17 of 19 in 2018, 14 of 15 in 2022, and 21
of 22 in 2026. More importantly, it recovered 121 of the 123 candidates absent
from the current 2026 political-race summary export.

## Multiple committees

Sixty candidate-cycles have more than one PCC record. This usually represents
renewed, duplicate, or dissolved registrations rather than simultaneous money:
only two candidate-cycles have positive financial activity in more than one PCC
record. Those two remain explicitly marked
`multiple_active_pcc_records_review`; the pipeline does not silently choose a
committee or assume that duplicate records are interchangeable.

## Financial window

For each election, the official committee financial-summary page is read for
the election calendar year and preceding calendar year: 2013-14, 2017-18,
2021-22, and 2025-26. The candidate-cycle mart separately preserves monetary
contributions, other receipts, in-kind contributions, and expenditures.
`fundraising_total` is monetary contributions plus other receipts; in-kind
contributions remain separate.

The retrieved summaries contain positive two-year activity for 652 of 733
matched candidate-cycles. A committee found with no activity is labeled as
such and is not conflated with a candidate for whom no committee was found.

## Outputs

- `fcpa_candidate_committee_inventory.csv`: every candidate search, PCC record,
  official committee ID, legal candidate name, registration date, status, and
  source URL.
- `fcpa_candidate_committee_financial_summaries.csv`: one row per
  candidate-cycle/PCC record with official two-year financial totals.
- `fcpa_candidate_cycle_finance.csv`: candidate-level aggregation with committee
  counts and an explicit multiple-active-committee flag.
- `fcpa_candidate_committee_review.csv`: ambiguous legal-name matches,
  unresolved candidates, and multi-record cases requiring review.

## Recommendation

Make `fcpa_candidate_cycle_finance.csv` the primary Alabama finance source for
2014 onward. Use transaction extracts for reconciliation and transaction-level
analysis, not as the authority for whether a candidate filed. Preserve
FollowTheMoney and DIME as secondary historical sources. Before promoting the
new totals into the public forecast, adjudicate the review queue and rerun the
finance-model forward validation using committee-ID totals.

Reproduce with `python scripts/build_fcpa_candidate_committee_finance.py`.
