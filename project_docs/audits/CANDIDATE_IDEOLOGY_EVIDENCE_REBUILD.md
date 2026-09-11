# Candidate ideology evidence rebuild

Date: 2026-08-24  
Task: `IDEOLOGY-CANDIDATE-EVIDENCE-REBUILD-004`

## Result

Candidate legislative evidence and ontology-v3 issue assignments have been
rebuilt from the repaired person identities and complete final-vote ontology.
The canonical CMO compatibility export contains 1,564 unique candidate-cycles;
1,119 now have at least one ontology-v3 position source.

No website page, caucus cluster, overperformance hypothesis estimate, or
forecast was rebuilt in this task.

## Direct legislative evidence

| Cycle | Candidates before | Candidates after | Evidence rows before | Evidence rows after |
|---:|---:|---:|---:|---:|
| 1998 | 23 | 39 | 184 | 361 |
| 2002 | 53 | 53 | 1,383 | 1,803 |
| 2006 | 50 | 50 | 1,648 | 2,176 |
| 2010 | 111 | 113 | 307 | 282 |
| 2014 | 108 | 111 | 3,818 | 3,923 |
| 2018 | 96 | 103 | 3,238 | 3,475 |
| 2022 | 81 | 80 | 1,614 | 1,595 |
| **Total** | **522** | **549** | **12,192** | **13,615** |

The evidence-row decline in 2010 and the one-candidate decline in 2022 are
expected corrections, not lost source coverage. They remove the false John
Jody Letson/Bill Dukes, Greg Reed/historical-member, and Ben Alford/Kirk
Hatcher assignments. The corrected pipeline now gives direct legislative issue
evidence to every candidate-cycle that has a behavioral roll-call score.

## Combined ideology layer

- Direct legislative evidence: 13,615 rows.
- Combined questionnaire plus legislative evidence ledger: 24,560 rows.
- All reviewed candidate evidence used by issue valence: 25,696 rows.
- Candidate-issue profiles: 9,920 across 1,119 candidates.
- Scored candidate-issue profiles: 8,383.
- Broad family profiles: 3,405.
- Adjudicated issue profiles: 9,920, with zero unresolved statuses.

Canonical candidate coverage by cycle:

| Cycle | Candidates | Any v3 evidence | Model-eligible breadth |
|---:|---:|---:|---:|
| 1994 | 211 | 9 | 0 |
| 1998 | 170 | 126 | 64 |
| 2002 | 213 | 148 | 42 |
| 2006 | 194 | 140 | 34 |
| 2010 | 203 | 186 | 22 |
| 2014 | 196 | 166 | 4 |
| 2018 | 204 | 185 | 15 |
| 2022 | 173 | 159 | 2 |

“Model-eligible breadth” retains the existing conservative gate of at least
three scored issues and two independently estimated broad families. A
candidate can have useful issue evidence without passing that broad-composite
gate.

## Integrity checks

- All 60,704 roll calls have a terminal ontology output.
- All mapped primitive/pole pairs validate and no rollcall-axis has
  contradictory poles.
- Legislative evidence IDs are globally unique.
- Candidate issue profiles are unique by candidate-cycle and primitive axis.
- Scored candidates have no duplicate `(year, chamber, member_source_id)`
  assignment.
- Cross-chamber candidates retain their actual source-vote chamber.
- No future-window vote is admitted to the pre-election behavioral mart.
- All 264 long-service legislators remain covered by raw, classified, and
  career-score evidence.

Focused pipeline validation passed 53 tests. The frontier integration gate
passed all 12 checks.

## Remaining limits

- No 1994 roll-call archive is available.
- The 2000 Senate is absent from the normalized archive.
- The 1998 Senate has unusually low roll-call volume and only 92.97% identified
  member-vote coverage.
- Historical journal actions lack exact calendar dates; regular-session votes
  use the existing transparent session-year temporal convention.
- Sponsorship, amendment-direction, and committee-action analysis remains
  deferred. Amendments are explicitly excluded rather than assigned the final
  bill's ideology.

## Downstream action

The hypothesis tournaments, caucus clustering, ideology/public page, and any
forecast features that consume ideology are now stale relative to this rebuilt
candidate evidence. They should be rerun as a separate model task and undergo
independent validation before publication.

