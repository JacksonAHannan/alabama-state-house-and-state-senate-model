# Southern candidate-finance acquisition

## Decision: summary first

The production target is one auditable finance observation per modeled
candidate and election cycle, not a regional transaction warehouse. Acquisition
therefore follows this order:

1. official candidate/election totals when the reported measure is compatible;
2. official periodic-report or report-cover summaries, selecting the latest
   amendment for each exact filing period and rejecting overlaps;
3. transaction records only to reconcile source categories, resolve an
   ambiguity, or cover a source with no usable summary layer.

The transaction files already acquired under
`data/raw/finance/southern/<STATE>/` remain immutable fallback evidence. They
are not the preferred production input.

## Candidate-cycle contract

The comparable target is monetary receipts reported by an identified candidate
committee from January 1 of the year before the election through December 31 of
the election year. Cash contributions and compatible other monetary receipts
may be combined. Loans, in-kind receipts, expenditures, refunds, and balances
remain separate.

A provider's label such as `Total Raised` or `Total Contributions` is retained
as `source_reported_total`. It becomes canonical `total_fundraising` only when
the source contract establishes compatible categories and periods. Missing,
paper-only, boundary-spanning, overlapping, or category-incompatible records
remain explicit review/unknown states; they are never converted to zero.

## Implemented official summary adapters

| State | Official summary layer | Current result | Canonical treatment |
| --- | --- | --- | --- |
| Alabama | Existing FCPA candidate-cycle summary table | 2018: 197/204 usable; 2022: 170/173 usable | Cash contributions plus other receipts; usable |
| Arkansas | Candidate index `Total Raised`, `Total Spent`, and balance by election | 2024: 97/108 automatic matches; 89 usable after paper/duplicate checks | Electronic, unambiguous rows usable; legacy 2016-2022 remains unknown |
| Florida | Candidate contribution-total summary query by election and chamber | 1,206/1,209 automatic matches across 2016-2024 | Stored as `source_reported_total`; not canonical because the total includes in-kind and loan-related record types |
| Georgia | Legacy annual contribution exports through 2021 plus Record Search transaction exports from 2022 | 1,385 / 1,528 usable candidate-cycle totals across 2016-2024; 360 / 474 D/R races complete | Monetary contributions and compatible other receipts; loans and in-kind remain separate. The 2015 window and refreshed immutable 2024 collection are present; official candidate/committee aliases are grouped by stable filer ID before reciprocal cycle-scoped identity resolution |
| Kentucky | Candidates-by-election table with total campaign receipts and expenses | 820/871 automatic matches; 820 usable totals across 2016-2024 | Official election-registration `Total Receipts`; usable as the provider's candidate-election total |
| Louisiana | Complete multiyear contribution, expenditure, and loan bulk extracts already acquired | 95/100 candidate-cycle identities produce usable totals; 38 / 41 D/R races complete | Contributions, anonymous receipts, and other monetary receipts; loans and in-kind contributions remain separate/excluded. Reviewed legal-name/nickname bridges retain official filer evidence |
| Mississippi | Legislative candidate index, candidate filing history, and selected year-end disclosure PDFs | 93/213 automatic electronic-portal matches; 142 selected PDFs; readable two-year coverage is reported by the canonical build | Sum of the two `Current Contributions - Aggregate YTD` values; scans/unrecognized PDFs remain unknown |
| Missouri | Candidates-by-election table and committee MEC-ID resolution | Current portal: 734/778 automatic matches for 2020-2024; 2016-2018 legacy index unavailable | Candidate committees are identified, but report download is reCAPTCHA-blocked; totals remain unknown, never zero |
| North Carolina | Official committee directory plus exact candidate/joint-candidate committee transaction queries | 1,456 / 1,475 usable candidate-cycle totals across 2016-2024; 646 / 663 D/R races complete | Candidate and joint-candidate committees only; final election-warehouse names and explicit nonlegislative exclusions prevent unsafe same-surname matches. Contributions, interest, and outside income are included, while refunds, loans, nonmonetary gifts, and expenditures remain excluded or separate. An accepted exact committee query with no monetary receipts is an explicit zero |
| Oklahoma | Guardian annual contribution/loan and expenditure bulk extracts already acquired | 811/830 candidate identities produce usable 2016-2024 monetary totals; 278 / 296 D/R races complete | Deduplicated monetary and other receipts across unique reciprocal provider aliases; loans, in-kind, and forgiveness categories remain separate/excluded |
| South Carolina | Candidate report index plus report-detail overview totals | 865 / 941 candidate totals usable; 222 / 284 D/R races complete | Filing-period cash, personal contributions, account credits, and debt-setoff funds; strictly contained interim periods are excluded, while partial overlaps/boundaries stay under review |
| Texas | Complete TEC CSV archive, `cover.csv` filing summaries, and existing filer crosswalk | Usable cover-derived totals range from 65% to 76% by cycle | Latest cover per exact period; blank amounts remain unknown unless the filing explicitly says no activity |
| Virginia | Candidate committee searches, scheduled-report indexes, and selected report XML | 706 / 775 automatic candidate matches; 9,311 selected report XML files; 657 usable candidate-cycle totals; 237 / 335 D/R races complete | Versioned exact first/last searches supplement capped surname/given-name results. Latest amendment per exact period; Schedule A plus unitemized cash plus Schedule C other receipts, excluding in-kind and loans. Multiple committees, substantive overlaps, and unsafe identities remain review/unknown |

South Carolina candidate matching collapses duplicate campaign/filer records
only when the normalized provider identity, office, and district agree. The raw
version-one and version-two selections are both preserved; the builder uses the
newest complete selection version.

For Texas, blank cover totals were checked against every regular contribution
detail shard. The affected reports also lacked itemized contribution records
and explicit unitemized amounts. That evidence is cached in
`texas_report_contribution_detail_fallback.csv`, but the totals remain unknown:
absence of detail is not silently converted to zero when the cover did not
assert zero or no activity.

## Remaining state inventory

- Arkansas 2016-2022 is a legacy-report problem; the current electronic
  candidate summary API begins with the 2024 election records.
- Georgia and North Carolina transaction fallbacks are integrated for complete
  two-year windows. Georgia groups legacy and modern aliases before reciprocal
  identity resolution. North Carolina uses exact committee batches because the
  portal's current-office classification can place historical House activity in
  a Senate export (or vice versa). Tennessee's acquired annual exports remain
  far too small to represent statewide candidate activity and are not promoted.
- Kentucky and Virginia now have validated summary/XML adapters. Virginia's
  remaining queue is dominated by multiple historical committees, overlapping
  periods, or candidates for whom the official search did not yield a safe
  legislative committee. Mississippi has a conservative mixed electronic/PDF
  adapter with a large explicit paper gap. Missouri candidate committees are
  acquired for 2020-2024, but the official report download gate prevents
  automated summary extraction and the current election index no longer exposes
  2016-2018.
- Delaware, Maryland, and West Virginia were in the supplied source inventory
  but are not present in the current Southern WAR candidate panel. They require
  a candidate-universe decision before acquisition can produce canonical keys.
- Mississippi and West Virginia may retain unavoidable paper-filing gaps.

Portal reachability, a downloaded file, an automatic name match, a provider
summary total, and a canonical usable total are distinct coverage stages.

## Provenance and outputs

Raw summary artifacts are immutable and record official URL, request
parameters, retrieval time, SHA-256, byte size, record count, and authoritative
scope in:

- `data/raw/finance/southern_summaries/<STATE>/`
- `data/processed/source_audits/southern_finance_summary_manifest.csv`
- `data/processed/source_audits/southern_finance_summary_candidate_matches.csv`
- `data/processed/source_audits/southern_finance_summary_coverage.csv`

Canonical and review outputs are:

- `data/processed/finance/southern_candidate_cycle_finance.csv`
- `data/processed/finance/southern_candidate_finance_report_periods.csv`
- `data/processed/finance/southern_candidate_cycle_finance_coverage.csv`
- `data/processed/finance/southern_candidate_cycle_finance_review.csv`

The canonical panel is loaded into warehouse schema version 14 by
`scripts/load_southern_finance_warehouse.py`. The loader preserves all source
rows, creates an evidence-bearing link to final-stage election candidates, and
only publishes D/R race features when both identities and totals are complete.
The supplied incumbency workbook is registered and queryable, but its
`Incumbents` sheet currently contains Alabama 2026 only. Positive historical
incumbent flags already present in the election warehouse are separately
registered as evidence and can support identity matching; blank workbook tabs
do not imply non-incumbency.

Acquisition is implemented in
`scripts/acquire_southern_candidate_finance_summaries.py`; canonical assembly
is implemented in `scripts/build_southern_candidate_cycle_finance.py`.

## Legacy transaction acquisition

The older transaction-first script and its manifest remain available for
reconciliation. The principal holdings are complete direct bulk for Louisiana
and Oklahoma; query acquisitions for Florida, North Carolina, South Carolina,
and Tennessee; a hybrid Georgia acquisition; and current-system Arkansas files
for 2022-2024. These holdings do not by themselves certify candidate identity,
amendment handling, comparable periods, or model eligibility.
