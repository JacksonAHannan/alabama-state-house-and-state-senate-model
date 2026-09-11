# Southern legislative WAR panel v1

> **Current release note (2026-08-30):** The canonical 2016-2024 completeness
> result is generated in
> `project_docs/audits/SOUTHERN_WAR_2016_2024_COMPLETENESS.md`. The release
> schedule contains 116 regular state-cycle-chamber slices for AL, AR, FL, GA,
> KY, LA, MO, MS, NC, OK, SC, TN, TX, and VA; DE, MD, and WV are outside scope.
> All 116 slices are loaded in the election warehouse. Every model-valid
> outcome has a baseline and context row in the validated finance-free mart.
> Remaining non-strict observations are preserved as research-only, principally
> because modern incumbency is experimental or Virginia requires an off-year
> baseline policy. The counts below document the earlier broad 1994-2024 v1
> development snapshot and are superseded for 2016-2024 release decisions.

## Scope

This experimental mart assembles every locally available Southern legislative
outcome and baseline source without publishing a canonical warehouse change.
The target states are Alabama, Arkansas, Florida, Georgia, Kentucky, Louisiana,
Mississippi, Missouri, North Carolina, Oklahoma, South Carolina, Tennessee,
Texas, and Virginia. The nominal period is 1994-2024.

The build inventories every top-level raw source family and separately catalogs
the 5,374 files under the repository's historical statewide, Southern SOS,
OpenElections, normalized precinct-history, and read-only Texas upstream source
trees. Source
files that cannot yet support a comparable WAR observation remain in the
inventory and exclusion ledger.

## Three deliberately separate layers

1. **Outcome universe:** 28,182 race observations, including uncontested and
   otherwise ineligible contests. Of these, 13,088 are usable contested
   Democratic-versus-Republican outcomes across all 14 states, 197 state-years,
   and 379 state-year-chambers.
2. **Research panel:** 6,338 rows across all 14 states and 88 state-years. This
   tier may use a partial baseline, a synthetic presidential-environment
   baseline, or experimental incumbency inference. It is not a common-scale
   headline WAR training set.
3. **Strict panel:** 5,396 rows across 13 states, 75 state-years, and 145
   state-year-chambers. Every row has a contested outcome, named Democratic and
   Republican candidates, an observed same-cycle ticket baseline, and an
   accepted incumbency observation.

Missing observations are never converted to zero. Synthetic baselines never
receive strict eligibility.

Incumbency identity uses exact race-party scope plus normalized person-name or
surname evidence. Independently decoded Alabama ballot codes and documented
Texas surname-only result labels are supported, but party scope by itself is
not identity evidence. This preserves valid provider aliases without attaching
a retiring incumbent to a same-party successor. Evidence without a major-party
label requires a full candidate-name match. Generated roster outputs are
excluded from their own evidence inputs, and source conflicts remain review
items.

## Strict coverage

| State | Races | Cycles | First | Last |
|---|---:|---:|---:|---:|
| Alabama | 509 | 8 | 1994 | 2022 |
| Arkansas | 201 | 5 | 1994 | 2020 |
| Florida | 270 | 3 | 2010 | 2020 |
| Georgia | 301 | 4 | 2012 | 2020 |
| Kentucky | 234 | 3 | 2010 | 2020 |
| Missouri | 1,032 | 10 | 2000 | 2020 |
| Mississippi | 39 | 1 | 2019 | 2019 |
| North Carolina | 639 | 6 | 2002 | 2020 |
| Oklahoma | 237 | 4 | 2010 | 2020 |
| South Carolina | 161 | 3 | 2010 | 2020 |
| Tennessee | 453 | 9 | 1998 | 2020 |
| Texas | 1,185 | 16 | 1994 | 2024 |
| Virginia | 135 | 3 | 2005 | 2013 |

Louisiana now contributes 90 research-tier observations from 2003, 2007, 2019,
and 2023. Both stages of all eight regular legislative cycles from 1995 through
2023 are retained. The final result uses November when a district appears in
the runoff and otherwise uses October; the stages are never added together.
The parser accepts a WAR outcome only when exactly one Democratic and one
Republican candidate appear, rather than combining multiple candidates of one
party into a fictional candidate. Louisiana remains outside the strict panel
because its incumbency evidence is currently an exact-name inference from
prior official final-stage winners rather than a reviewed or source-observed
flag.

## Baseline hierarchy

The selection hierarchy is explicit and source observations are retained:

1. Canonical Alabama selected same-cycle ticket context.
2. Texas official district totals paired with district-allocated governor or
   presidential context, plus the 2022 statewide-office index. The 2024 rows
   explicitly use the presidential margin rather than the Texas compatibility
   export's non-presidential statewide-office average.
3. Louisiana stage-matched statewide context. In 2019 this is first-round or
   runoff governor; in 2023 it is first-round governor or runoff attorney
   general. Official contest membership assigns the 2019 RDH/VEST context,
   using legislative-turnout weights only where a VTD is split.
4. MEDSL ballot-first same-cycle presidential, U.S. Senate, governor, or U.S.
   House context with at least 95% legislative-turnout coverage.
5. Previously validated HEDA, OpenElections, Arkansas SOS, or Tennessee SOS
   same-cycle context.
6. HEDA context with unresolved allocation, research only.
7. Prior presidential margin plus realized national swing, research only.

The new MEDSL pass removed an earlier six-state hard-code. It reads all target
state files for 2018, 2020, and 2024, assigns context through the legislative
ballot rows in the same precinct, and uses legislative turnout shares only for
split precinct records.

The repository's Mississippi 2019 RDH/VEST package supplies district-split
officially validated legislative and governor returns. Virginia's official
precinct CSVs supply governor context for 2005, 2009, and 2013 House elections.

## Source disposition

- **Directly integrated:** canonical Alabama exports; Klarner contest and
  candidate archives; MEDSL 2018, 2020, and 2024 precinct archives; historical
  validated HEDA/OpenElections/SOS panel; Mississippi 2019 RDH/VEST package;
  Virginia official gubernatorial-year precinct files; Louisiana official
  two-stage open-primary files and modern RDH/VEST statewide context; current
  2024 incumbency review output; and the sibling
  Texas project's official candidate totals, canonical incumbency, TLC
  VTD-normalized ticket allocations, and RED-206 district context.
- **Retained as research-only:** partial HEDA allocations and the modern
  presidential-plus-national-swing probability panel.
- **Catalogued for subsequent normalization:** the remaining official Southern
  SOS downloads, historical district shapefiles, raw OpenElections gap files,
  Census/RDH geography, and election-specific archives that do not yet have a
  validated district ticket allocation.
- **Not used to define WAR:** finance, demographics, ideology, polling, and
  candidate-position sources. They are inventoried as supporting covariates and
  must remain downstream explanatory or forecast features unless separately
  validated.

## Remaining work

The principal gap is no longer legislative outcomes. The repository already
contains 13,088 eligible contested outcomes. The bottleneck is observed ticket
context: 6,750 contested outcomes still lack a selected baseline.

Texas is now nearly complete: 1,185 of 1,187 contested D/R races across all 16
cycles are strict-ready. Five 1994 races and 1998 HD-51 were recovered by using
the legislative ballot rows only to identify their observed precinct/VTD set,
then allocating governor votes across that set. The only remaining Texas gaps
are 1996 HD-54 and HD-108, whose legislative ballot rows are absent from the TLC
normalized precinct export; their outcomes remain available but their district
ticket context remains missing.

Next work should prioritize state-cycle batches where official precinct files
contain legislative and statewide/federal contests together. The same
ballot-first allocator used here can promote those batches without requiring a
perfect precinct shapefile. Louisiana incumbency needs review; Virginia Senate
and non-gubernatorial House cycles require a prespecified off-year baseline;
and 2022/2024 cycles need additional observed context rather than the current
synthetic environment fallback.

## Outputs

All outputs are under `data/processed/war/southern_war_panel_v1/`:

- `southern_war_panel.csv`
- `southern_war_panel_coverage.csv`
- `southern_war_exclusions.csv`
- `race_outcome_observation_audit.csv`
- `baseline_observations.csv`
- `medsl_ballot_first_audit.csv`
- `louisiana_legislative_stage_candidates.csv`
- `louisiana_legislative_stage_contests.csv`
- `louisiana_modern_baseline_audit.csv`
- `texas_upstream_reconciliation.csv`
- `repository_raw_source_families.csv`
- `repository_election_source_files.csv`
- `build_manifest.json`

This is an experimental research mart. It does not replace canonical warehouse
views or any current public Alabama WAR or forecast output.

The incumbency overlay also consumes the dedicated Alabama candidate roster at
`data/processed/war/incumbency_roster.csv`; its hash is recorded in the
incumbency manifest. This closes opaque 2022 ballot-code identities without
using a name-free inference or altering the election-result source.
