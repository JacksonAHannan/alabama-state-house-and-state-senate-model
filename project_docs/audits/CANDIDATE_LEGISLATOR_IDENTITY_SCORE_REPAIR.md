# Candidate-legislator identity and scoring repair

Date: 2026-08-24  
Task: `IDEOLOGY-IDENTITY-SCORE-REPAIR-002`

## Result

The identity layer now prioritizes chamber and district evidence before global
name similarity, treats the recorded legislative role as the authoritative
service chamber, supports documented chamber transitions, and distinguishes a
verified identity from a scored pre-election service record.

## Coverage change

| Metric | Before | After | Net |
|---|---:|---:|---:|
| Resolved LegiScan candidate identities | 761 | 765 | +4 |
| Candidate-cycles with behavioral roll-call score | 523 | 549 | +26 |

The net figures conceal necessary corrections. Seven reviewed modern
identities were added, while three same-number House/Senate ballot-code links
were removed. Twenty-nine candidate scores were added and three false scores
were removed.

Score change by cycle:

| Cycle | Before | After | Net |
|---:|---:|---:|---:|
| 1994 | 0 | 0 | 0 |
| 1998 | 24 | 39 | +15 |
| 2002 | 53 | 53 | 0 |
| 2006 | 50 | 50 | 0 |
| 2010 | 111 | 113 | +2 |
| 2014 | 108 | 111 | +3 |
| 2018 | 96 | 103 | +7 |
| 2022 | 81 | 80 | -1 |

## Identity corrections

- Cam Ward is linked to LegiScan person 3405 (`Robert Ward`) in 2010, 2014,
  and 2018.
- Billy Beasley is linked to person 3386 (`William Beasley`) in 2010 and 2018.
- Johnny Mack Morrow's 2018 Senate candidacy is linked to person 3402.
- Lynn Greer's 2018 House candidacy is linked to person 12488.
- House member Phil Williams (person 3437, HD-6) and Senator Phillip Williams
  (person 12498, SD-10) are now disambiguated. The old statewide exact-name
  priority attached the Senate candidate to the House member.
- Merika Coleman / Merika Coleman-Evans and Linda Coleman / Linda
  Coleman-Madison remain linked through first-name, surname-token,
  same-chamber, district, and party agreement.

The reviewable source-backed overrides are stored in
`data/manual/ideology/candidate_legislator_identity_overrides.csv`.

## False links removed

The old district fallback treated an identical House and Senate district
number as if it were person evidence. It incorrectly linked:

- 2022 HD-26 Democrat Ben Alford to SD-26 Senator Kirk Hatcher;
- 2022 HD-32 Republican Evan Jackson to SD-32 Senator Chris Elliott;
- 2022 HD-33 Democrat Fred Crum to SD-33 Senator Vivian Figures.

The Ben Alford/Kirk Hatcher error had propagated a false behavioral score and
is the one-cycle decline visible in 2022. The rebuild also removed false
historical score assignments from 2010 HD-7 candidate John Jody Letson to Bill
Dukes's journal identity and from 2010 SD-5 candidate Greg Reed to an unrelated
historical Senate identity.

## Cross-chamber scoring

Nine candidates now receive a unique pre-election score from their actual
prior chamber while retaining `score_chamber = house` and their election
`chamber = senate`: Tammy Irons, Gerald Allen, Cam Ward, Billy Beasley, Jim
McClendon, Johnny Mack Morrow, Donnie Chesteen, Jack Williams, and David
Sessions.

The score window still ends no later than the election year. Candidate chamber
and score chamber are never conflated.

## Historical recovery

Prior-officeholder inference now uses prior canonical wins in addition to the
incomplete incumbent flag. A historical district-party fallback is accepted
only when surname identity also agrees. This recovered 15 net 1998 scores and
rejected the apparent HD-11 `White -> Drake` district-only match.

## Storage and labels

`coverage_status` now checks the identity-side member ID separately from the
score-side member ID. The output distinguishes:

- 549 scored pre-election legislative records;
- 269 verified identities without scored pre-election service;
- 535 candidates without a verified legislative identity;
- 211 candidates in the unavailable 1994 roll-call archive.

## Validation

- Identity and scoring tests: 19 passed.
- Candidate ideology storage invariants: 4 passed.
- No duplicate `(year, chamber, member_source_id)` score assignment survives.
- Every scored row has a valid `score_chamber` and a pre-election window ending
  no later than the election year.

The direct candidate legislative-evidence ledger and ideology analyses have
not yet been rebuilt from these repaired identities. That is the next task.

