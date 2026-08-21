# Frontier legislative review

The existing small-model adjudications are provisional and never overwritten. The frontier review operates once per bill or materially distinct bill version, then propagates an approved final-passage interpretation to linked roll calls only when the motion relationship is known.

## Review order

1. Small-model mapped bills and known taxonomy conflicts.
2. Other currently mapped substantive bills.
3. Small-model exclusions, to recover false negatives.
4. Topic-only bills with roll calls.
5. Bills without roll calls or without a plausible ideological position.

## Current scope and status

As of 2026-08-18, all 8,006 previously unreviewed bills with recorded roll
calls have received a frontier adjudication. Together with the earlier review
tiers, 9,116 bills are reviewed. The remaining 19,717 bills have no recorded
roll call and are intentionally deferred: sponsorship, amendments, and
committee-only activity will be treated as a later evidence layer rather than
mixed into the behavioral roll-call analysis.

The full-text follow-up queue is exhausted except for two explicitly retained
unknowns. SJR8 (2010) disapproves a personnel layoff rule without reproducing
the rule, and SB48 (2014) has archive formatting that does not reliably expose
the operative unemployment-law amendment. Neither is assigned an invented
direction.

## Required judgment

Each bill receives one of: `map`, `multi_axis`, `mixed_no_scalar_direction`, `procedural`, `local_non_generalizable`, `symbolic`, or `insufficient_text`. A mapped decision records exact ontology axes and poles, the text version reviewed, a concise rationale, and confidence. Tax positions must identify incidence. Social policy must distinguish Christian sexual morality from racial civil rights. Gun rights and punitive law-and-order remain separate.

The synopsis may support a high-confidence judgment when it states the operative change unambiguously. Otherwise the reviewer must inspect the latest text effective at the roll call. Amendments do not inherit the parent bill's direction without amendment text.

## Files

- `research/cmo_ideology/frontier_legislative_review/bill_review_ledger.csv`: all 28,833 bills.
- `substantive_review_queue.csv`: mapped or high-priority bills requiring direct review.
- Existing `legislative_rollcall_ontology_v3_final_adjudications.csv`: preserved first-pass output.
