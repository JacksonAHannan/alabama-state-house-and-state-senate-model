# Legislative ideology post-repair coverage

Date: 2026-08-24  
Task: `IDEOLOGY-POSTREPAIR-COVERAGE-005`

## Final coverage

| Metric | Initial audit | Final | Change |
|---|---:|---:|---:|
| Normalized roll calls | 60,704 | 60,704 | 0 |
| Roll calls with classification disposition | 42,367 in-warehouse | 60,704 | +18,337 |
| Ontology-mapped roll calls | 918 | 987 | +69 |
| LegiScan candidate identities resolved | 761 | 768 | +7 net |
| Any pre-election voting identity resolved | 832 | 848 | +16 |
| Behavioral score available | 523 | 550 | +27 |
| Direct legislative issue evidence available | 522 | 550 | +28 |
| Direct legislative evidence rows | 12,192 | 13,617 | +1,425 |
| Expected officeholder identity unresolved | 39 | 24 | -15 |
| High-confidence deterministic identity queue | 7 after chamber correction | 0 | -7 |

The final score and direct-issue counts agree exactly: every candidate-cycle
with a behavioral roll-call score has at least one mapped direct legislative
position.

## Final deterministic identities

The last review queue linked source-backed ballot/legal-name variants:

- Bill Poole III to William Poole, LegiScan person 12530;
- Bill Roberts to William Roberts, person 12487;
- Marc Keahey to George Keahey, person 3485.

Poole and Roberts remain correctly unscored in 2010 because they have no
eligible pre-election Yea/Nay record in that window. Keahey adds one valid 2010
behavioral score and two mapped legislative evidence rows.

## What remains unresolved

Twenty-four inferred prior officeholders still lack a verified pre-election
legislative identity. Twenty-two are in the weak 1998 journal era; the two
modern cases are 2014 HD-10 `Means` and 2014 HD-29 Michael J. Gladden. Neither
has enough current source evidence for automatic promotion.

Source limits are unchanged:

- the 2000 Senate archive is absent;
- 1998 Senate roll-call volume is unusually low and member identification is
  92.97%;
- 2008 Senate member identification is 94.64%;
- no 1994 roll-call archive is available.

These are now explicit source/identity gaps rather than silent zeroes.

## Validation

- Current coverage audit tests: 6 passed.
- Full identity, classification, ontology, evidence, issue, storage, and audit
  suite: 59 passed after the final deterministic links.
- Frontier integration: all 12 gates passed.
- Workflow scope validation passed.
- No high-confidence identity recovery remains.
- No roll call is absent from the classification table.
- No contradictory mapped pole survives.

The hypothesis analyses, caucus clusters, ideology page, and any forecast
features remain intentionally stale pending a separate downstream rerun and
independent release validation.
