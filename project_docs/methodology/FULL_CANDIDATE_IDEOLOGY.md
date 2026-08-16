# Full-candidate ideology layer

## Comprehensive legislative processing

`python scripts/run_legislative_ideology_pipeline.py` runs archive-wide
classification, legislative-action aggregation, candidate scoring, and focused
tests in dependency order. Every archived roll call receives a processing
status. Topic detection is separate from ideological direction: a measure is
scored only when a human-reviewed anchor or a deliberately narrow deterministic
rule supports the direction of a yea vote. Procedural motions and amendments do
not automatically inherit the parent bill's direction.

The audit products are `comprehensive_bill_classifications.csv`,
`comprehensive_rollcall_classifications.csv`,
`comprehensive_rollcall_direction_review_queue.csv`,
`comprehensive_bill_sponsor_positions.csv`, and
`comprehensive_amendment_classification_queue.csv`. Sponsorship remains a
separate expressive-position signal. Amendments remain unscored until
amendment-specific text establishes the direction of the revision.

Historical journal synopses are recovered in three exact-measure stages: the
stored roll-call context, an adjacent-page window in the original PDF, and (for
final passage only) the complete daily journal. Formal journal markers also
supersede incidental bill citations inside a synopsis. The recovery audit is
written to `historical_rollcall_synopsis_recovery.csv`; unresolved procedural
motions and resolutions are labeled separately from genuine bill-synopsis
failures.

This layer provides one coverage row for every canonical Alabama legislative
candidate from 1994 through 2022. Universal coverage does not mean universal
scoring: missing legislative service and missing questionnaires remain missing.

## Evidence hierarchy

1. Candidate-supplied, exact-election Vote Smart PCT dimensions.
2. Reviewed issue directions from the candidate's recorded pre-election
   legislative votes.
3. A chamber/window-relative behavioral ideal point from contested HB/SB roll
   calls in the unified legislative archive.

Party averages are never substituted for candidate evidence.

## Pre-election windows

The unified archive supplies 1998 itself for the 1998 election, then the prior
quadrennium for 2002 through 2022. Only recorded Yea/Nay votes on HB/SB measures
with at least two votes in the minority and a minority share of at least 2.5%
enter the behavioral score. Members need at least 20 recorded votes. PCA's first
component is oriented so Republicans score more conservatively where both
parties are observed. Scores and percentiles are relative to that chamber and
window, not a universal scale across decades.

Candidate matches require an exact normalized name, a unique same-party surname
within the chamber/window, or—only for an incumbent—a unique same-party district
match. Ambiguous identities remain unscored.

## Issue dimensions

Reviewed anchor votes retain their issue-specific direction, with `+1`
conservative and `-1` progressive. Broad legislative social, economic, and
governance dimensions require evidence in at least two component issue families.
The best-available social and economic fields prefer candidate-supplied Vote
Smart responses and otherwise use reviewed legislative dimensions. Each has an
explicit provenance column.

## Current coverage

The current universe contains 1,566 candidate-election rows. Behavioral
legislative scores are available for 653; any legislative or Vote Smart ideology
evidence exists for 792. Best-available social scores cover 350 rows and economic
scores cover 378. The 1994 archive has neither Vote Smart profiles nor journal
roll calls, so all 1994 candidates remain explicitly unavailable. Candidates who
never held legislative office will often remain unscored unless they completed a
Vote Smart questionnaire or another candidate-supplied source is added.

Primary outputs:

- `data/processed/ideology/candidate_ideology_full_universe.csv`
- `data/processed/ideology/candidate_ideology_full_coverage.csv`
- `data/processed/ideology/legislator_pre_election_window_scores.csv`
