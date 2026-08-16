# Historical Alabama House and Senate roll-call pipeline

## Scope

The pipeline extracts named Alabama House votes from ADAH House journals for
1998–2009, the period immediately before the structured LegiScan archive. It
also indexes Alabama Acts volumes for 1986–1998. These are deliberately
separate evidence types:

- journals establish recorded motions and named votes;
- Acts establish enacted measures and their originating bill or resolution;
- an Act does not, by itself, establish how any legislator voted.

## Commands

```powershell
python scripts/extract_historical_house_journal_rollcalls.py
python scripts/extract_historical_senate_journal_rollcalls.py
python scripts/index_historical_alabama_acts.py
python scripts/link_historical_rollcalls_to_acts.py
```

The extractor accepts only semicolon-form House vote anchors (`Yeas N; Nays
N`) because comma-form tallies in these journals commonly quote Senate
messages. Parsed names must reproduce every printed tally. Failed parses remain
available with `count_valid = false` and are excluded from analytical use.

The Senate extractor uses its chamber's space-delimited format (`Yeas N Nays
N`) and handles `Abstaining` lists. Its Section 63 audit begins with detected
third-reading passage language, pairs each event to the subsequent named vote,
and separately verifies the measure identity and printed member totals. The
ADAH 2000 Senate collection contains indexes but no daily journals, so 2000 is
reported as a source gap rather than zero legislative activity.

The Act linker currently has genuine temporal overlap only in 1998. It reports
unique, ambiguous, and absent matches and does not reinterpret every linked
motion as final passage. Act text can be used later to classify the issue and
policy direction of a linked measure; the journal's `motion_type` determines
what the member vote meant procedurally.

## Concurrency boundary

These outputs live only under `data/processed/legislative/`. The pipeline does
not read or write Vote Smart collection files and does not rebuild the central
warehouse. Loading should occur only after concurrent collectors finish and a
transactional warehouse migration is ready.
