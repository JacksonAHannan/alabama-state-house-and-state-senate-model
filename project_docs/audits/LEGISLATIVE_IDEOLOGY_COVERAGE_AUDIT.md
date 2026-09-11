# Legislative roll-call and candidate ideology coverage audit

Date: 2026-08-24  
Task: `IDEOLOGY-ROLLCALL-COVERAGE-AUDIT-001`

## Result

The repository has much more raw legislative evidence than the current
candidate issue layer exposes. The principal gaps are not wholesale loss of
LegiScan data. They are concentrated in four places: historical journal
classification coverage, candidate-to-legislator identity, chamber-changing
incumbents, and the unavailable 1994/2000 Senate archives.

The audit is read-only with respect to source and canonical warehouse data.
Its generated ledgers are under
`data/processed/ideology/legislative_ideology_coverage_audit_*.csv`.

## End-to-end funnel

| Stage | Rows or candidate-cycles |
|---|---:|
| Expected session/chamber cells, 1998-2026 | 58 |
| Present session/chamber cells | 57 |
| Normalized roll calls | 60,704 |
| Normalized member-vote observations | 3,994,500 |
| Identified member-vote observations | 3,953,481 |
| Roll calls mapped to an ontology-v3 issue pole | 918 |
| Roll calls absent from the classification table | 18,337 |
| Canonical candidate-cycles | 1,564 |
| LegiScan person identity resolved | 761 |
| Any pre-election voting identity resolved, including journal IDs | 832 |
| Behavioral legislative score available | 523 |
| Direct legislative issue evidence available | 522 |

The difference between 761 and 832 is expected: journal-era member IDs are
resolved inside the applicable pre-election window and are not LegiScan person
IDs. Earlier reports that treated every missing LegiScan crosswalk row as an
unresolved candidate materially overstated the identity gap.

## Source coverage

- The only completely absent expected chamber-year is the 2000 Senate.
- The 1998 Senate contains only 207 recorded roll calls and identifies 92.97%
  of member-vote observations; it is both low-volume and incomplete.
- The 2008 Senate identifies 94.64% of member-vote observations.
- No usable 1994 roll-call archive is presently available. Candidates in that
  cycle can still receive Vote Smart or other evidence, but not a pre-election
  roll-call score from this archive.

## Classification loss

All 31,233 LegiScan roll calls are represented in the classification table.
The 18,337 omitted records are journal-derived. Most are intentionally
non-final motions:

| Omitted motion | Roll calls |
|---|---:|
| Budget isolation resolution | 9,406 |
| Amendment or concurrence | 4,626 |
| Substitute | 1,562 |
| Other recorded motion | 1,011 |
| Confirmation | 869 |
| Final passage | 538 |
| Conference report | 153 |

The current historical queue keeps one representative roll call per
`session_year + bill_type + bill_number` across both chambers. That is too
aggressive for direct-vote ideology: it can retain one chamber's final vote
while dropping the other chamber's vote on the same bill. Of the 691 omitted
final-passage or conference-report votes, 642 have a classified counterpart on
the same measure and 46 have a counterpart already mapped to an issue pole.

The repair should propagate a reviewed/recovered measure classification only
to substantive final-passage and conference-report votes on the same measure.
Amendments, substitutes, budget-isolation votes, and procedural motions must
remain excluded until their own direction is adjudicated; the final bill's
direction cannot safely be assigned to them.

## Candidate coverage

| Cycle | Candidates | Pre-election identity | Behavioral score | Direct issue evidence |
|---:|---:|---:|---:|---:|
| 1994 | 211 | 27 | 0 | 0 |
| 1998 | 170 | 57 | 24 | 23 |
| 2002 | 213 | 67 | 53 | 53 |
| 2006 | 194 | 120 | 50 | 50 |
| 2010 | 203 | 158 | 111 | 111 |
| 2014 | 196 | 147 | 108 | 108 |
| 2018 | 204 | 137 | 96 | 96 |
| 2022 | 173 | 119 | 81 | 81 |

There are 39 inferred prior officeholders without a usable pre-election
identity. Thirty-one are in the especially weak 1998 archive. The modern
deterministic repair set contains:

- Cam Ward, 2014 and 2018 Senate, to LegiScan person 3405 (`Robert Ward`)
- Billy Beasley, 2018 Senate, to person 3386 (`William Beasley`)
- Lynn Greer, 2018 House, to person 12488
- Bill Poole, 2010 House, to person 12530
- Bill Roberts, 2010 House, to person 12487
- Marc Keahey, 2010 Senate, to person 3485

Cam Ward's 2010 Senate candidacy and Billy Beasley's 2010 Senate candidacy are
cross-chamber transitions. Their pre-election votes are House votes. A matcher
that requires the score chamber to equal the candidate's election chamber will
miss them even after the person identity is correct. Johnny Mack Morrow's 2018
House-to-Senate transition has the same problem.

The audit also found a concrete chamber bug: `legiscan_alabama_legislators.csv`
can carry a future Senate district label on a member's last House-session row.
Role must determine the service chamber; district prefix is only a fallback.
Otherwise identical House/Senate district numbers can produce false matches.

Finally, the public coverage label in
`build_full_candidate_legislative_ideology.py` checks the score-side member ID
after renaming the identity-side ID. A verified identity with no score can
therefore be labeled as having no verified identity. The status logic must use
`identity_member_source_id` for identity coverage and preserve the distinct
case `verified identity, no scored pre-election service`.

## Repair order

1. Add a reviewable candidate-to-legislator override ledger for proven legal,
   nickname, and cross-chamber identities.
2. Make role authoritative for service chamber and constrain district fallback
   to the same chamber before considering a documented cross-chamber identity.
3. Infer prior-officeholder eligibility from prior canonical wins, because the
   canonical incumbent field is absent in several historical cycles.
4. Allow a resolved person to receive the unique pre-election score from a
   prior chamber, while retaining both candidate chamber and score chamber.
5. Correct the coverage-status field and quarantine all duplicate
   candidate-cycle/member assignments.
6. Expand historical classification to every final-passage and conference
   report vote on a classified measure; do not propagate direction to motions
   or amendments.
7. Rebuild direct legislative evidence and all downstream ideology analyses.
8. Compare before/after coverage by cycle, inspect every newly recovered
   candidate manually, and run an independent validation before publication.

## Acceptance checks

- `python scripts/audit_legislative_ideology_coverage.py`
- `python -m pytest scripts/tests/test_legislative_ideology_coverage_audit.py -q`
- Result: 6 passed.

