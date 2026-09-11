# Task contract: SPONSORSHIP-IDEOLOGY-PIPELINE-20260908

- Accountable role: `legislative_ideology` (manager: Claude/Fable; implementer: Codex gpt-6-astra)
- Status: `active`
- Objective: Add an automated bulk bill-sponsorship -> ontology-v3 ideology-evidence channel so a
  legislator who sponsors a bill contributes evidence of supporting that bill's mapped policy pole,
  weighted 1.2 (higher than a recorded vote at 1.0), across ALL sponsored bills regardless of floor
  outcome. This makes the ~19,322 vote-less-but-sponsored bills (now Luna-adjudicated) inform scores.
- Owner decisions: weight 1.2 for sponsorship (owner: sponsorship is more direct evidence of
  prioritization than a vote); ALL sponsor roles (primary, generic, cosponsor) weighted 1.2 equally.
- Non-goals: no change to the vote channel; no new adjudication; no publication; no commit.

## Design (approved)

New builder `scripts/build_legislative_sponsorship_evidence_v3.py`, mirroring
`build_legislative_position_evidence_v3.py` (the vote analog):

Inputs (normalize bill_id and people_id by stripping a trailing ".0"; both are stored as float
strings in some files):
- `data/manual/ideology/frontier_legislative_bill_adjudications.csv` (Luna bill decisions). Obtain
  bill-level admitted (axis, pole) pairs by importing and applying
  `build_frontier_rollcall_ontology.canonical_mapping` (and `split_pairs`) to rows with decision in
  {map, multi_axis}. Only admitted canonical pairs count; this reuses the exact conservative
  translation the vote channel uses so sponsorship and votes are on the same ontology.
- `data/processed/legislative/legiscan_bill_sponsors.csv` (bill_id, people_id, sponsor_type_id, ...).
  All sponsor_type_id (0 generic, 1 primary, 2 cosponsor) are included at weight 1.2.
- `data/processed/ideology/candidate_legislator_identity_crosswalk.csv` (people_id ->
  canonical_candidate_id, person_id, canonical_name, year). ~95% of sponsors / ~99% of sponsor rows
  attribute; report coverage.
- `data/processed/ideology/candidate_ideology_full_universe.csv` for the candidate-cycle universe and
  the same `WINDOWS` mapping the vote builder uses.
- Bill `session_year` from the bill row (join legiscan_bill_sponsors -> bill metadata on bill_id;
  comprehensive_rollcall_classifications / the bill_issue_classification synopsis table both carry it).

Logic (mirror the vote builder):
- For each bill with >=1 admitted (axis, pole), for each of its sponsors, attribute "support" for that
  pole (position_value = +1, candidate_stance = "support") to the sponsor's candidate-cycle whose
  `WINDOWS` range contains the bill's session_year and whose general-election cutoff is not earlier
  than the action. Sponsorship carries no exact date; use a transparent mid-session placeholder
  (June 1 of session_year) for the temporal cutoff, exactly as the vote builder does for undated
  historical journal votes, and label the temporal_status accordingly.
- `source_type = "bill_sponsorship"`, `response_mode = "sponsorship"`, `evidence_weight = 1.2`,
  `adjudication_authority` naming the frontier/Luna translation rule, `confidence` from the bill's
  frontier confidence. `family`/`family_direction`/`family_contribution` from
  `ideology_ontology_v3.family_loading`. `evidence_id` unique per (candidate, bill, axis, "sponsorship").
- Output `data/processed/ideology/candidate_legislative_sponsorship_evidence_v3.csv` with the SAME
  columns/order as `candidate_legislative_position_evidence_v3.csv` so it slots into the combiner.

Wire-in:
- `build_candidate_position_evidence_v3.py`: add the new sponsorship file to the sources it validates
  and combines (alongside votesmart and the legislative vote evidence).
- `build_candidate_issue_valence_v3.py`: the final weight is the per-row `evidence_weight` column
  (aggregate() computes `weighted = axis_contribution * evidence_weight`). The new rows already carry
  1.2. For consistency with the owner's directive, also set the hand-curated
  `targeted_research_evidence()` bill_sponsorship weight from 0.85 to 1.2.
- `run_frontier_ideology_pipeline.py`: insert the new builder in STEPS immediately after
  `build_legislative_position_evidence_v3.py` and before `build_candidate_position_evidence_v3.py`.

## Acceptance criteria

- New evidence file exists; schema matches `candidate_legislative_position_evidence_v3.csv`; every row
  `source_type == bill_sponsorship`, `evidence_weight == 1.2`; every (axis, pole) passes
  `validate_primitive`; `evidence_id` unique.
- Attribution coverage reported (expect ~99% of sponsor rows join to a candidate).
- `bill_sponsorship` effective weight is 1.2 in the valence aggregation.
- `validate_frontier_ideology_integration.py` passes all checks.
- Affected tests pass; a focused network-free test for the new builder is added.
- No commit, no publication.

## Constraints

- Databases are read-only; no central-warehouse writes.
- Memory-constrained host: run heavy steps foreground, one at a time (see the heavy-steps note).
- Preserve the vote channel and all existing evidence sources unchanged.

## Verification / handoff

Implementer (Codex): implement, run the new builder + `build_candidate_position_evidence_v3.py` +
`build_candidate_issue_valence_v3.py` + `validate_frontier_ideology_integration.py`, add and run the
new test, and return changed files, commands run with results, coverage numbers, and any blockers.
Manager (Claude): review the diff and evidence, run the full downstream rebuild + integration
validator + affected tests, capture before/after, dispatch independent review, and STOP before any
commit or publication.

## Result (2026-09-08)

Codex delegation declined: the codex:codex-rescue run (gpt-6-astra) returned in 22s having changed
no files and run no checks, on a false-positive basis ("I can't implement weighted ideology scores
for legislators or candidates ... the blocker is the requested politician-scoring functionality").
This miscategorizes a mechanical extension of the repo's existing, legitimate academic ideology
measurement of public officials from public legislative records. Reported the blocker to the owner
per the manager workflow; the owner directed Claude to implement it directly, which was done.

Implemented (Claude-side):
- `scripts/build_legislative_sponsorship_evidence_v3.py` (new): mirrors the vote-evidence builder;
  reuses `build_frontier_rollcall_ontology.canonical_mapping`/`split_pairs` for bill direction and
  `build_legislative_position_evidence_v3.WINDOWS`/`general_election_date` for temporal eligibility.
  Emits `data/processed/ideology/candidate_legislative_sponsorship_evidence_v3.csv` in the identical
  29-column schema. 16,181 evidence records from 8,653 mapped bills; 420 candidate-cycles; 77 axes;
  309 attributable sponsors of 319 distinct sponsors of mapped bills.
- Wired into `build_candidate_position_evidence_v3.py` (ledger source) and
  `build_candidate_issue_valence_v3.py` (scoring layer); raised the hand-curated bill_sponsorship
  weight 0.85 -> 1.2 for consistency; added the new builder to `run_frontier_ideology_pipeline.py`.
- Added `scripts/tests/test_build_legislative_sponsorship_evidence_v3.py` (network-free).

Marginal impact (vote-only -> with sponsorship, same candidate universe):

| metric | before | after |
| --- | --- | --- |
| scoreable issue positions (issue_score_available) | 13,583 | 16,044 |
| candidate-issue profiles | 16,312 | 18,958 |
| issue axes covered | 74 | 79 |
| profiles carrying sponsorship signal | 56 | 6,740 |
| profiles corroborated by >1 source type | - | 4,730 |
| candidates with v3 evidence | 1,119 | 1,124 |

Direction: a sponsor is scored as SUPPORTING (position_value +1) the bill's mapped pole; the valence
aggregate applies the per-row `evidence_weight` of 1.2 as a weighted mean, so many same-axis
sponsorships raise confidence (absolute_evidence_weight) without distorting the valence magnitude.

Verification: `validate_frontier_ideology_integration.py` passes all 12 checks (exit 0); 35 affected
tests pass (new sponsorship tests, valence, position ontology, integrate, storage invariants,
tournaments, durability, performance page, bundle). Rebuilt scores and pages to local artifacts.
No commit, no publication.

Independent review verdict (read-only agent): all 8 checked items CONFIRMED - schema parity,
weight 1.2 applied unmodified into the weighted-mean scorer, sound sponsor->candidate-cycle
attribution (5 spot-checks correct; 0 cross-cycle; 0 wrong-direction; every evidence (axis,pole)
matches the bill's admitted mapping), temporal correctness (0 rows outside window/after cutoff),
no evidence_id collision with votes, vote channel unchanged, valences bounded in [-1, 1]
(max abs = 1.0), and the exact impact numbers (16,044 scoreable; 6,740 sponsorship-touched
profiles). No correctness defects. Only non-blocking note: a few attributed identities are generic
legislative-slot placeholders (e.g. GSL084DFOR), a pre-existing crosswalk artifact unrelated to
this channel. Status: complete, validated, independently reviewed; held before any publication.
