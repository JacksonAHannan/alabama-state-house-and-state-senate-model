# Candidate finance rebuild on FollowTheMoney

## Problem

The WAR model's candidate-finance feature (`dem_candidate_spending`,
`rep_candidate_spending`, `log_spending_ratio_d_to_r`, `finance_complete`)
is currently built by `scripts/build_candidate_finance_features.py` from raw
Alabama FCPA expenditure extracts (`Candidate Financial Information/*.zip`),
matched to race candidates by fuzzy name matching (`rapidfuzz`, plus
surname/canonical-name fallbacks). Coverage is incomplete: both major
candidates are matched in only 125 of 154 contested races (81.2%), per
`MODEL_READINESS.md`.

FollowTheMoney (`followthemoney.org`, operated by the National Institute on
Money in Politics / OpenSecrets) exposes an "Ask Anything" table-export API
that returns one summarized row per candidate per election, including
`Office_Sought` (e.g. `"HOUSE DISTRICT 038"`, `"SENATE DISTRICT 027"`),
`Election_Status` (`Won-General`, `Lost-General`, `Lost-Primary`, etc.),
party, and `Total_$` (contributions raised). This was verified live: a
query for `s=AL&y=2022&gro=c-t-id` returns losing general-election
candidates as well as winners (e.g. Senate District 27: HOVEY [R,
Won-General, $799K] vs. REESE [D, Lost-General, $13K]), and district
assignment comes directly from `Office_Sought` — no fuzzy precinct/candidate
matching required for the race-level aggregate.

## Goals

1. Replace `build_candidate_finance_features.py`'s FCPA-extract +
   fuzzy-name-matching pipeline with FollowTheMoney's `Total_$` per
   candidate, for election years 2010, 2014, 2018, and 2022.
2. Derive `(chamber, district)` directly from `Office_Sought` (regex parse),
   and select the general-election nominee per party via `Election_Status`
   in `{Won-General, Lost-General}` — not fuzzy string matching.
3. Keep the existing output column names
   (`dem_candidate_spending`/`rep_candidate_spending`/
   `log_spending_ratio_d_to_r`/`finance_complete`) even though the
   underlying quantity changes from expenditures to contributions raised,
   so the 6 downstream consumers (`fit_preliminary_war_model.py`,
   `compare_war_specifications.py`, `assemble_war_features.py`,
   `build_war_review_queue.py`, `audit_cycle_shift.py`,
   `validate_war_outputs.py`) don't need to change. Document the semantic
   change in the new script's docstring/comments instead.
4. Fetch once, cache raw JSON, commit it — not a live API call on every
   pipeline run. FollowTheMoney's site is unreliable (their own
   documentation warns of bugs; live testing hit a site-wide expired TLS
   certificate and flaky empty-page responses that needed retries).

## Non-goals

- No change to the WAR model's feature schema, fitting, or validation logic
  beyond what's needed to consume the same column names from a new source.
- Not attempting to reconcile FollowTheMoney's `Total_$` (contributions) with
  Alabama's own FCPA "TOTAL RECEIPTS" bookkeeping figure — they're related
  but not identical concepts; `Total_$` is what gets used.
- 2026 is out of scope (no legislative cycle to model yet).

## Design

### Fetch and cache (new: `scripts/fetch_followthemoney_candidates.py`)

For each year in `{2010, 2014, 2018, 2022}`, page through
`https://api.followthemoney.org/?dt=1&s=AL&y={year}&gro=c-t-id&APIKey={key}&mode=json`
(`p=0,1,2,...` until `paging.currentPage == paging.maxPage`), retrying each
page up to 3 times on an empty/short response (observed live: page fetches
intermittently return `HTTP 200` with a zero-byte body). After paging
completes, validate the total record count collected equals
`paging.totalRecords` from the first page's response; raise loudly if not.
Write the raw concatenated records to
`data/raw/followthemoney/{year}_al_candidates.json`, committed to git the
same way `Candidate Financial Information/` and the OpenElections CSVs are
committed raw sources — this script is a manual/occasional step, not part
of the regular rebuild pipeline, and only needs rerunning when a new year is
added.

The API key is read from `token.env` (`FTM_API_KEY=...`), following the
existing `CENSUS_API_KEY` pattern in `scripts/download_acs_sld_demographics.py`.

**TLS verification is disabled in this one script only**, because
FollowTheMoney's certificate is currently expired site-wide (confirmed via
direct connection, not a local trust-store issue). This is scoped
deliberately narrowly: no other network call in the repository disables
verification, and the script carries a comment explaining why, with a note
to re-enable once FollowTheMoney's certificate is fixed.

### Parse and aggregate (new: `scripts/build_followthemoney_finance_features.py`)

For each cached year's records:

1. Parse `Office_Sought` display value with
   `r"^(HOUSE|SENATE) DISTRICT (\d+)$"` (case-insensitive); skip records
   that don't match (statewide/judicial/PSC/school-board races).
2. Filter to `Election_Status` in `{"Won-General", "Lost-General"}` — this
   is required, not optional: districts routinely carry extra same-party
   primary-loser rows with unrelated dollar totals (verified live: AL
   Senate District 27, 2022, had a `Lost-Primary` Republican with a *larger*
   `Total_$` than the actual `Won-General` nominee).
3. Map `Specific_Party`/`General_Party` to `D`/`R` (everything else
   excluded — matches `oe_normalize.norm_party` conventions, reused where
   it applies).
4. Pivot to one row per `(cycle, chamber, district)` with `dem_candidate_spending`/`rep_candidate_spending`
   from `Total_$`, `log_spending_ratio_d_to_r` (same `+500` constant and
   log-ratio formula as the current script, preserved for continuity), and
   `finance_complete` (both D and R rows present).

No fuzzy name matching against `race_candidate_results.csv` is needed for
the race-level aggregate, since `Office_Sought` + `Election_Status` already
identifies the general-election nominee per party per district directly.

### Retired

- `scripts/build_candidate_finance_features.py`
- Its outputs: `data/processed/war/finance_candidate_cycle_totals.csv`,
  `candidate_finance_matches.csv`, `candidate_finance_review.csv`,
  `candidate_finance_coverage.csv` (replaced by the new script's own
  coverage/QA output).
- `Candidate Financial Information/` raw FCPA extracts become unused by this
  feature (left in place — not deleting a large raw-data directory as part
  of this change; revisit separately if truly dead).

### Kept unchanged

- `race_finance_features.csv`'s column names and the 6 downstream scripts
  that consume them.

## Rollout

Same pattern as the precinct-data rebuild: build the new pipeline, diff its
`race_finance_features.csv` output against the currently committed one
(coverage should visibly improve past 81.2%; dollar magnitudes will differ
since the quantity changed from expenditures to receipts — that's expected,
not a regression), review before deleting the old script.

## Open risks

- FollowTheMoney's `Total_$` conflates several transaction types
  (contributions, in-kind, etc.) into one contributions-raised figure; it is
  not the same accounting concept as AL's FCPA "TOTAL RECEIPTS" line, though
  it's the right measure for "how much did this candidate raise."
- The TLS certificate workaround is a live operational risk: if
  FollowTheMoney's certificate is still expired whenever a new year needs
  fetching, the workaround remains necessary; if their site is fixed, the
  `verify=False` should be removed at that point rather than left in place
  indefinitely.
- 2010 candidate data will need matching against a legislative-district map
  vintage even further back than this rebuild otherwise touches, if it's
  ever used as a model feature rather than just being fetched for future
  availability — out of scope for this task since no WAR model cycle uses
  2010 yet.
