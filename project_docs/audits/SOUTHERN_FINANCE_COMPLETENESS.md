# Southern finance completeness, 2016-2024

The canonical panel contains 12,559 candidate-cycle rows and 9,620 observed
fundraising totals. Warehouse build `RUN-DD652884AEA04C10A7181E496DFDB826`
accepts 12,515 candidate identities, retains 9,587 observed totals after
identity gating, and publishes 3,305 complete D/R race features. The 2016-2024
WAR universe contains 3,304 finance-complete outcomes out of 4,582; the one-row
difference is a finance-mart race outside the selected WAR outcome universe.

| State | Observed / target candidates | Candidate coverage | Complete / modeled D/R WAR outcomes | Main remaining gap |
| --- | ---: | ---: | ---: | --- |
| AL | 374 / 377 | 99.2% | 94 / 97 | three candidates with no compatible FCPA committee |
| AR | 82 / 764 | 10.7% | 31 / 223 | legacy 2016-2022 reports |
| FL | 1,137 / 1,211 | 93.9% | 434 / 489 | residual reconciliation review |
| GA | 1,323 / 1,528 | 86.6% | 318 / 474 | residual candidate transaction identity |
| KY | 820 / 871 | 94.1% | 301 / 344 | residual registrations |
| LA | 93 / 100 | 93.0% | 36 / 41 | residual filer identities |
| MO | 0 / 1,346 | 0.0% | 0 / 502 | report download reCAPTCHA and missing legacy index |
| MS | 19 / 263 | 7.2% | 0 / 65 | paper filings and candidates absent from the electronic index |
| NC | 1,472 / 1,475 | 99.8% | 661 / 663 | three candidates without same-cycle committee evidence |
| OK | 741 / 830 | 89.3% | 241 / 296 | residual committee identities |
| SC | 849 / 941 | 90.2% | 205 / 284 | positive overlaps/boundaries and residual identities |
| TN | 831 / 834 | 99.6% | 299 / 302 | one malformed report, one no-summary filer, one absent committee |
| TX | 1,228 / 1,244 | 98.7% | 450 / 467 | positive boundary/overlap review and three unresolved filers |
| VA | 651 / 775 | 84.0% | 234 / 335 | residual committee/XML and period review |

Georgia and North Carolina include the required 2015 source year. Georgia 2024
uses the immutable refreshed `recordsearch_v2` collection and reciprocal
cycle-scoped alias/filer matching. North Carolina uses exact official candidate
and joint-candidate committee batches and is candidate-observed for 1,472 of
1,475 rows. Complete annual exports recover historical committees omitted by
the current directory; reviewed exact-scope decisions cover only source-backed
nickname/legal-name cases. Virginia's refreshed
conservative committee search supplies 651
usable totals from 9,165 selected XML reports; unsafe same-surname committees
and unresolved overlaps remain review/unknown. Tennessee uses official
candidate-report summaries rather than the truncated statewide transaction
query and adds immutable report collections for approved historical identities.
Texas applies TEC's documented blank-when-zero numeric contract and reviewed
exact-scope TEC filer identities. Alabama's candidate-level completion path
retains official FCPA search responses and calendar-year summary payloads for
duplicate historical committee records; missing committee searches remain
unknown rather than zero.
Mississippi 2023 OCR retains page-level source hashes and parser provenance;
unreadable forms remain unknown.

All release checks pass: SQLite integrity, foreign keys, source and mart
cardinality, unknown-not-zero semantics, observed-total retention, and no
numeric feature on an incomplete race. The machine-readable next-action queue
is `data/processed/source_audits/southern_finance_remaining_gap_queue.csv`; it
never authorizes zero filling.

The model-facing file is
`data/processed/finance/southern_race_finance_model_features.csv`. Its grain is
one warehouse race, and its numeric finance fields are null unless both major-
party totals and both identities are complete. Finance remains an optional
same-cycle covariate and is not used to redefine WAR.
