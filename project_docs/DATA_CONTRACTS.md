# Data contracts

## Required source manifest fields

Every raw input must register:

| Field | Meaning |
|---|---|
| `source_file_id` | Stable namespaced identifier |
| `provider` | Publishing organization |
| `source_url` | Retrieval location |
| `retrieved_at` | UTC retrieval timestamp |
| `sha256` | Exact artifact hash |
| `media_type` | File/media type |
| `license_or_terms` | Known reuse terms or review status |
| `state_code` | Two-letter postal code |
| `cycle` | Election/legislative cycle when applicable |
| `geography_vintage` | District/Census vintage when applicable |
| `authoritative_scope` | Facts for which the source is authoritative |
| `ingest_status` | discovered, acquired, parsed, rejected, or superseded |

## Canonical election grain

The core candidate-election interface is one candidate-party-contest record.
It must distinguish chamber, district plan, district, election stage, election
date, party, votes, vote share, incumbency evidence, contest status, and source
coverage. Uncontested is a contest property; it is not inferred merely from a
missing opposing row.

## Common enums

- `chamber`: `lower`, `upper`
- `election_stage`: `primary`, `primary_runoff`, `general`, `special`,
  `special_runoff`, `other`
- `party_family`: `democratic`, `republican`, `independent`, `other`, `unknown`
- `review_status`: `proposed`, `approved`, `rejected`, `superseded`
- `value_status`: `observed`, `derived`, `imputed`, `unknown`, `not_applicable`

Original provider values must also be retained.

## Election-source bootstrap lifecycle

`build_election_database.py` creates a new election-source database, not a
complete central warehouse rebuild. Its default target and an explicit
`--output` must both be absent. An existing target raises `FileExistsError`
before source loading; a target created during the build must also survive
publication unchanged. Source hashes and normalized election interfaces are
unchanged. Existing domain tables, source registrations, adjudications, and
build history must never be discarded by this bootstrap command.

## Source-data repair contract (2026-09-05)

SOS county summaries are reconciliation evidence, not additive precinct rows.
The 2002 adapter locates candidate and party columns from their printed headers;
the contest column immediately precedes party, including Marshall's duplicated
`Contest Title` heading. The 1994 provider precinct number is retained separately
from its display name and supplies the county-scoped precinct key when present.
`AG1`/`AG2` are first/second attorney-general ballot codes, not A/B-prefixed
district codes. Other historical party inferences remain explicitly inferred.
Workbook member, sheet, one-based row/column, original ballot code, and parsing
method survive normalization where the repaired adapters provide them.
For contest-per-sheet 2010/2012 workbooks, retain the sheet, one-based numeric
result cell row/column, and exact `printed_precinct`/`printed_candidate` labels
through observation normalization. Distinct physical columns with the same
candidate label and distinct rows whose labels differ only by whitespace remain
separate source observations. These locators explain source grain; they do not
adjudicate duplicate reporting units, relabel a printed answer or alter votes.

A historical office-only correction may update `office` and `district` on an
existing source row only after a unique match at the unchanged source/year/
county/precinct/candidate/party/vote grain and exact printed contest-title
evidence. Keep rowids, votes, identities and ambiguous matches untouched.
Retain before/after labels and physical source locators in repair QA. Correcting
labels changes dynamic source views; dependent materializations remain stale
until separately reconciled. It does not authorize regenerating analyses.

After source-supported office correction, physical provenance may be filled
only through a unique match including the now-correct office and district and
exact parity of all substantive source fields. The entire source cohort must
reconcile as a multiset before individual rows are paired. Fill only previously
null member/sheet/one-based row/column and verified registered source-file ID;
preserve rowids, votes, identities and original ingestion run IDs. Record the
provenance repair run separately, with before/after evidence. Ambiguous matches
retain every candidate physical cell without assigning by row order or stripping
printed-label differences. A physical locator does not establish that a provider
reported a unique geographic unit, and does not authorize deduplication.

Reported source vote counts must be finite nonnegative integers before accepted
aggregation; an observed integer zero is valid and a missing count is unknown.
An unresolved fractional reported value must cause affected input slices to fail
before aggregation or output writes, with its source locator exposed for review.
Do not round, drop or null the value and then present an ordinary sum as complete.
Diagnostic source inspection may retain the original value explicitly. This
rule applies to reported observations, not derived allocation values or weights,
whose separate contracts may legitimately permit fractions. An authority-selected
view alone is not evidence that its source counts passed this quality check.

Repairs must preserve a pre-repair SQLite backup and append before-images and
source reconciliation evidence under a registered repair run. Source-level
contradictions (including fractional reported votes and inconsistent roll-call
summaries) remain review items; no rounding or invented member votes is allowed.
Dependent materializations not rebuilt must be explicitly listed as stale in
the repair QA, and existing model outputs are not certified by a source repair.

Precinct identity repair matches existing IDs only on exact
`year/source/county_key/precinct_key`. Surviving keys retain IDs; new keys receive
IDs above the previous maximum, never IDs recycled from removed keys. Changed
keys or fingerprints invalidate affected county/year match suggestions; those
suggestions remain review data and do not inherit acceptance. A staging manifest
is not authority to replace live tables or reuse stale geographic links.

A scoped identity application must back up and verify the exact staged inputs
under a write lock. Retired generated references are removed from active linkage
tables, with their before-images retained. Source-transfer geography evidence
loses acceptance when its source link is withdrawn; canonical/conflict rows are
then recomputed from retained evidence for affected IDs only. Direct 2014
geography is name/code based, so surviving direct links may be retained only
when those inputs and their geographic identity still agree. Unrelated geography,
manual evidence and source domains stay untouched. Saved allocation and
conflict-impact exports remain explicitly stale pending their own reconciliation.

VEST geometries must be valid, nonempty polygonal WGS84 features at serialization,
not merely before reprojection. Canonical topology repair retains polygonal
components of `make_valid`; collapsed zero-area lines/points are not precinct
area. Source geometry and source result totals remain unchanged.

LegiScan reconciliation compares each reported category and total with recorded
member votes. A canonical complete-roll-call interface excludes disagreements;
both original representations remain in source tables and QA exposes the reason.
Consumer caches, reviewed queues and manual issue approvals cannot override
source reconciliation. Consumers must use canonical member-vote contents, not
just canonical IDs applied to unchecked CSV contents. A standalone roll-call
snapshot must pass provider-content parity against the current canonical source
before it is used downstream. Source loaders and diagnostic audits may inspect
unrestricted observations explicitly as source/QA data, not accepted evidence.
Unknown acquisition time remains null; registration time is not retrieval time.
File verification/check times (including Census `checked_utc`) are not retrieval
times either: a cached artifact may be checked long after acquisition. Retain the
check in its original manifest, but do not promote it into `retrieved_at_utc`.
Correct an existing copied check time only against exact provider/path/hash and
timestamp evidence, retaining a verified backup and repair-run before-images.
An independently recorded retrieval time must not be erased merely because a
manifest lacks that field. Neither correction nor registration establishes reuse
terms or changes the source's authoritative scope.

## Join contracts

### Alabama 2022 contest totals versus allocation inputs

Official SOS general-election precinct workbook cells supply observed 2022
legislative vote subtotals. Completeness requires independent reconciliation
against the certified canvass; summing observed cells alone does not establish it.
RDH split precinct layers remain
allocation inputs; their documented removed votes must not reduce a candidate's
contest total. Changing the contest-total source must not change geographic
weights or allocated statewide-office baselines.

Keep archive hash, member, sheet, one-based row/column, printed candidate/party
and precinct for the official cells. Named candidate votes, write-ins, overvotes,
undervotes and source summary cells remain distinct categories. An unknown or
malformed nonempty numeric cell fails reconciliation; it never becomes zero.
Blank cells remain unknown, with observed and unknown cell counts retained;
all-null candidate groups fail rather than becoming zero-vote candidates.
Candidate vote totals exclude over/under ballots. A D/R-only compatibility
interface does not establish zero write-ins or complete all-candidate coverage.

Existing opaque candidate codes may survive as compatibility identifiers only
through unique same-chamber/district/party source-name evidence. Preserve names
and stable person/candidate IDs during a numerical repair. Complete official
totals and geographically allocated RDH observations must remain distinguishable
in lineage, and every dependent materialization needs scoped reconciliation.

The scoped certified-canvass load appends Alabama 2022 source observations only
to the existing Southern legislative source tables. It does not select a new
canonical source or change person, candidate, finance, allocation or model IDs.
Source observation IDs are namespaced by the registered artifact and contest;
candidate observation IDs use the physical certified total cell, not a name or
input row order. Write-in totals remain aggregate categories, not named people.
This source-only load retains literal certified vote counts and leaves vote
shares null; it records the all-named-candidate-plus-write-in denominator as
source metadata, excluding overvotes and undervotes. Original precinct blanks remain unknown.
Per-contest metadata retains source-cell locators and reconciliation evidence.
The source sets remain `review` for canonical promotion, despite exact source
reconciliation, until identity and downstream denominator integration is reviewed.
The shared history refresh must preserve separately owned source sets and QA.

The Alabama 2018 certified load follows the same source-only contract with two
recorded differences. Thirty certified rows whose observed precinct subtotal falls
below the certified total (blank cells are unknown, not zero) are retained with
row-level `review` status and their reconciliation reason, observed subtotal and
cell counts in evidence; the certified total is still the observed vote value.
The canvass registry row is inserted inside the same guarded transaction when it
is absent. The row-level evidence pin is
`audits/ALABAMA_2018_CERTIFIED_SOURCE_ROWS.json`.

### Alabama certified canvass authority and canonical bridge (2026-09-08)

The certified State Canvassing Board canvass is the authoritative source for
Alabama 2018 and 2022 general-election legislative contest totals. The Alabama
canonical candidate route remains the Southern outcome source family so stable
candidate identifiers, names and finance identity links survive. Authority is
implemented through `bridge_alabama_canonical_candidate_certified_result`
(schema version 27): exactly one approved bridge row per canonical candidate,
joined `1:1` to one certified named-candidate cell at exact
cycle/chamber/district/party grain, with explicit name evidence recorded as the
`match_method`: an exact normalized name, an opaque 2022 ballot code decoded
through the accepted README decoder, surname agreement at the already-unique
race/party grain (the 2018 canvass prints surnames), or an exact normalized match
to the same provider's precinct-workbook candidate aligned to that cell when the
printed canvass label disagrees. No fuzzy matching, no bridge without evidence,
and a bridge failure stops the repair rather than bridging part of a cycle.

A canonical total that disagrees with its bridged certified cell is corrected to
the certified value under a registered repair run with before-images in
`qa_warehouse_source_repair`; the bridge row records `canonical_votes_before`,
`certified_votes`, `vote_delta` and `correction_status`. The materialized
`canonical_southern_legislative_candidate_election` votes and shares for the
affected contests are updated in the same transaction; winner flags may not
change. Consumers holding copies of the pre-certified totals
(`race_candidate_results.csv` and its producer, identity alias evidence tables,
CMO compatibility exports, Alabama WAR and forecast bundles) are recorded as
stale and are not silently rewritten.

For an `alabama_canonical` outcome in `mart_southern_war_outcome`, a scalar
`source_file_id` means every contributing canonical candidate bridges to the
same certified observation set and file with an equal vote total; the value is
that certified canvass file. The outcome's `third_party_votes` is the certified
set total minus the bridged Democratic and Republican totals, so it includes
other named candidates and the certified write-in total; the components are
recorded in `source_quality_flags_json`. When the bridge table is absent the
producer records `alabama_certified_bridge: absent` and leaves the scalar null;
when a bridged canonical total disagrees with the canvass the preparation build
fails instead of propagating a stale total.

Each production join documents:

- left and right grain;
- expected cardinality (`1:1`, `1:m`, `m:1`);
- unmatched-row policy;
- duplicate-key failure behavior;
- temporal and geographic validity conditions;
- reconciliation metric and tolerance.

Many-to-many joins require an explicit bridge or allocation-weight table.

## Cross-state exports

Validated state repositories should eventually publish versioned tables for:

- contests and candidate results;
- district-plan metadata;
- candidate and legislator identities;
- district demographic features;
- finance/resource features;
- legislative ideology features;
- model forecasts and uncertainty;
- run metadata and validation summaries.

Every export includes `contract_version`, `state_code`, `build_run_id`, and the
relevant as-of/cutoff date.

## Official Southern election result contract

`source_southern_candidate_election` is one official candidate-party-contest
observation aggregated to the contest geography reported by the provider. Its
stable key is `candidate_election_id`; `contest_id` and `election_id` do not
depend on display names or row order. The table retains original candidate,
party, office, district, and election-stage labels, and every row has an
explicit many-to-many bridge to all contributing `source_file_id` values.

The interface does not infer an uncontested race from one observed candidate.
It records `contest_status = unknown`, preserves regular Louisiana first-round
and runoff observations as separate stages, and never adds those stages. A
district-plan identifier ending in `reported-unknown-vintage` distinguishes
state, cycle, and chamber without claiming a verified plan vintage. Consumers
requiring plan-specific joins must stop until that vintage is adjudicated.

The 14-state QA coverage table distinguishes parsed results, registered but
unparsed artifacts, unavailable automated downloads, Alabama's existing
canonical facts, Texas's external companion-repository data, and PDF-only
review queues. Missing states, cycles, candidates, parties, and contests never
become zeroes.

## Comprehensive Southern legislative history contract

Schema version 11 adds provider-specific legislative observation sets so that
official state returns, Alabama canonical results, MEDSL precinct returns, and
Klarner candidate-contest records can coexist without adding overlapping vote
totals. `source_southern_legislative_observation_set` is one provider-specific
contest and `source_southern_legislative_candidate_result` is one
candidate-party observation within that set. A source null vote remains
`vote_value_status = unknown`; it is never converted to zero.

`fact_southern_legislative_candidate_election` selects an entire observation
set per state, cycle, stage, chamber, and district. Authority order is Alabama
canonical, direct official state results, official-derived modern gap files,
MEDSL individual-state releases, MEDSL national releases, then Klarner. If a
higher-ranked source omits a contest, a lower-ranked observed contest remains
available. Candidates from different providers are never mixed within one
selected contest. `all_southern_legislative_candidate_election_observations`
retains every competing observation and its source family.

`fact_southern_legislative_final_candidate_election` is the regular-cycle
modeling interface. For Louisiana's validated official two-stage series from
1995 forward, it selects the runoff when a district appears
in the runoff and otherwise selects the first round; the stages are never added.
For other states it selects the regular general-election observation. Specials
remain in the stage-level fact and do not silently enter the regular-cycle
training universe. `qa_southern_legislative_final_competition_coverage`
separately reports observed competitions and WAR-eligible contests. WAR
eligibility requires exactly one Democratic and one Republican candidate with
positive observed votes in the selected final contest; a complete seat roster
is not required and is not inferred from contested-only files.

## Finance-free Southern WAR preparation contract

The 2016-2024 regular-election schedule is prespecified as 116
state/cycle/chamber keys for AL, AR, FL, GA, KY, LA, MO, MS, NC, OK, SC, TN,
TX, and VA. DE, MD, and WV are outside this project scope. Odd-year regular
elections in LA, MS, and VA and staggered upper chambers are represented in
their actual election years; special-election-only slices are excluded. A
validated release must find all 116 keys in the final-election warehouse and
must not publish an outcome slice outside this schedule.

`mart_southern_war_outcome` is one final regular-cycle D-versus-R contest. It
selects one whole provider observation set and never combines candidates or
votes across sources. The model-specific authority rule first requires exactly
one positive-vote Democrat and one positive-vote Republican, observed votes,
and no provider `dontuse` or `uncont` flag; it then applies the canonical source
authority order. A lower-authority set may therefore be selected when a more
authoritative observation cannot identify a model-valid D-versus-R contest.
The canonical and selected observation-set identifiers are both retained.
The validated Texas companion-panel result may fill a contest absent from the
regular-stage central fact, with its panel source file and fallback status
retained; this does not authorize generic panel fallbacks for other states.

For an official-state outcome, a scalar `source_file_id` means that every
contributing candidate observation has exactly one registered bridge source and
all those sources agree. Include third-party observations in this check, not
only the two selected major-party rows. Missing, unregistered, multiple or
disagreeing bridge sources keep the scalar null; the many-to-many bridge remains
authoritative. Other provider observation sets likewise require complete scalar
agreement rather than copying an arbitrary first row. The shared history view
may remain bridge-backed without claiming a singleton source file.

A provenance-only repair may fill an existing null official-state outcome field
only after checking observation identity/scope, complete source consensus and
registered artifact hashes. It must preserve every other field, all eligibility
states, source/bridge records and unrelated domains, with a verified separate
backup, transaction and repair-run evidence. Such a repair does not reconstruct
legacy transformation lineage or certify derived exports; unchanged exports
remain explicitly stale in provenance until separately refreshed.

`mart_southern_war_context_feature` is one state/cycle/chamber/district row of
realized ticket baseline and incumbency evidence from the versioned Southern
WAR panel. Its join to `mart_southern_war_outcome` is `1:0..1`; duplicate keys
fail the build and unmatched outcomes remain explicit.

Candidate-level positive incumbency evidence joins to a WAR outcome at exact
state, cycle, chamber, district, and major-party scope. The outcome must contain
exactly one candidate for the evidence party, and identity must additionally
agree through normalized name/surname evidence or an independently resolved
opaque-ballot-code roster. Exact party alone is not sufficient: a departing
incumbent and same-party successor may share the same district, and a same-
surname retirement conflict remains open/review evidence rather than being
silently attached to the successor. The original evidence name and attachment
method remain in lineage. Unknown-party evidence requires a full candidate-name
match. Duplicate race-party targets fail, and a generated incumbency roster
must never be consumed as evidence for its own rebuild.

`mart_southern_war_training_no_finance` is the `1:0..1` outcome/context join.
Strict readiness requires an observed model-valid outcome, a strict observed
same-year ticket baseline or an election-day national generic-ballot
environment when no same-year ticket exists, and accepted incumbency. Research-only baselines or
experimental incumbency remain labeled and cannot become strict through
imputation. Finance fields are absent and the row-level finance status is
`excluded_not_ready`; missing finance is never converted to zero.

`mart_southern_war_training_with_finance` is a `1:0..1` exact race-key join
from the finance-free training view to `mart_southern_race_finance`. It retains
all WAR outcomes. `finance_complete=1` requires both major-party source
observations and accepted identities; otherwise amounts and the fundraising
ratio remain null. WAR readiness and finance completeness are separate gates.

The compatibility finance CSV may be refreshed independently with
`load_southern_war_preparation_warehouse.py --export-finance-only`. This reads
the existing warehouse without initialization or writes, rejects duplicate keys
and unmasked incomplete features, and writes only that CSV and its
`.manifest.json` sidecar. The sidecar records the query, view/code/output hashes,
generation time and source row run IDs; it supersedes the old bundle manifest
only for this file and does not revalidate upstream inputs or sibling outputs.

`mart_alabama_2026_incumbency_roster` is one Alabama legislative seat. The
supplied workbook is positive evidence for incumbent identity, running status,
and open-seat status only where its `Incumbents` sheet is populated.
The current workbook's populated observations cover Alabama 2026; its
`Election_Cycles` schedule rows are not historical candidate-incumbency
evidence. Source-mapped but unpopulated historical rows are not evidence. Conflicts with
the existing candidate-derived roster retain both observations and a documented
resolution status.

## Southern candidate-finance warehouse contract

`source_southern_candidate_cycle_finance` retains one observation per modeled
state, cycle, chamber, district, and party. Only `observed_positive` and
`observed_zero` set `finance_observed = 1`; an unmatched committee, unreadable
filing, inaccessible report, or incompatible source measure remains null.

`bridge_southern_finance_candidate_identity` is a `1:0..1` join from a finance
observation to the final-stage Southern candidate fact. State, cycle, chamber,
and district must agree exactly. Party must agree unless the election warehouse
explicitly reports `unknown`; names then provide the remaining evidence.
Incumbency can strengthen a scoped name match, but missing incumbency evidence
never implies challenger status and does not authorize a match. Ambiguous
matches remain in the review queue.

Provider identities that fail conservative automatic matching may be supplied
only through `data/manual/finance/southern_finance_identity_adjudications.csv`.
Every approved row must have a stable adjudication ID, exact state/cycle/
chamber/district/party scope, provider identity, source path and URL, quoted
evidence, rationale, and reviewer. The builder fails on scope drift, overlapping
decisions, a missing provider identity, or a conflict with an existing automatic
match. The adjudication file and its immutable official evidence are registered
as source dependencies; an adjudication never authorizes a zero unless the
provider's source contract establishes an explicit no-activity observation.

For Tennessee, an official full-report XLS workbook may replace an unreadable
HTML report summary only for that same report ID. The immutable error response
and workbook are both retained, and the workbook-derived amount remains subject
to the same two-calendar-year cycle window. A filer page returning no reports
does not establish zero activity and remains `unknown`.

`mart_southern_candidate_cycle_finance` contains only accepted identity links.
`mart_southern_race_finance` publishes a Democratic/Republican log fundraising
ratio only when both source observations are usable and both candidate links
are accepted. Candidate observation coverage, identity-link coverage, and
complete-race coverage are separate QA measures.

`southern_race_finance_model_features.csv` is the file-facing interface to the
race mart at `state/year/chamber/district` grain. It carries all warehouse race
keys plus `finance_missing` and `finance_model_eligible`. Candidate amounts and
the log ratio must be null whenever `finance_complete=0`. Same-cycle finance is
permitted only as a contemporaneous explanatory feature; training/evaluation
code must not use filings dated after the modeled election cutoff.

The canonical cycle amount covers January 1 of the calendar year preceding the
election through December 31 of the election year. Georgia and North Carolina
therefore require 2015 transactions for the 2016 cycle. Georgia's refreshed
2024 Record Search collection is a versioned replacement source; the defective
first response set remains immutable and is excluded by the adapter rather than
overwritten.

Florida uses the complete, recursively partitioned official candidate
transaction exports as the authoritative cycle-window source after the
acquisition audit verifies every election/office/type dimension and excludes
capped parent queries. Candidate election summaries are independent
reconciliation evidence, not a prerequisite for promoting a transaction total:
a disagreement is retained in `source_reported_total` and
`aggregation_status` but does not erase a fully classified transaction sum.
An empty detail result is usable only when the accepted official summary is an
explicit zero. Invalid or unrecognized nonzero contribution codes and a net
negative monetary cycle remain review items.

Georgia candidate-name and official campaign-committee aliases are grouped by
legacy/Record Search filer ID within the exact cycle window before ambiguity
is evaluated. Committee boilerplate is removed for identity scoring, but the
stable filer ID remains the aggregation key. A filer identity is accepted only
when it reciprocally resolves to one modeled candidate; all safe IDs for that
candidate are then summed. A same-surname return that lacks independent
given-name, committee-name, or uniqueness evidence remains unknown.
Georgia identity resolution prefers the final election warehouse's candidate
display name on the exact modeled key so that stale concatenated panel aliases
do not suppress otherwise exact official filer matches. Common given-name
equivalence is usable only with compatible surname evidence and reciprocal
uniqueness; it never authorizes a surname-only match.

For current-system and migrated Georgia registrations, the official Record
Search candidate endpoint may resolve a filer when its election cycle,
legislative office, district, and major party agree exactly with the modeled
candidate and the candidate name is the unique compatible name in that scope.
As a conservative redistricting/office-change fallback, a current or prior-cycle
registration may differ in district or legislative chamber only when it does
not postdate the target, retains the same major party, and has strong unique
person-name evidence. The endpoint's
stable filing-entity ID is joined to the already acquired transaction exports;
its displayed cumulative financial fields are identity/reconciliation evidence
only and a positive displayed value is not substituted for the canonical
two-calendar-year transaction window. An explicit displayed zero is usable as
zero because zero is invariant to a wider cumulative period.

For legacy Georgia registrations, the official name-search detail page may
resolve one or more legacy filer IDs when the displayed candidate name and
legislative office/district uniquely agree with the modeled candidate. A
registration whose filer-ID creation year does not postdate the target may
also support a different district or legislative chamber when the displayed
person name is a strong unique match. Only transactions dated inside the
target window are aggregated from those IDs. The portal phrase `No Reports
Filed` is retained as source evidence but does not by itself establish zero.

For either Georgia system, a resolved filer with no monetary receipt rows is
`observed_zero` only when every authoritative contribution-export partition
covering both calendar years is present and recorded in the source manifest.
This is an explicit reported-activity zero for a known filer, not an assumption
that a missing candidate raised nothing. A missing filer identity or an
incomplete export window remains unknown.

Arkansas uses the Secretary of State's current candidate financial summary for
2024 and the public legacy-report index or predecessor filing archive for
2016-2022.  For a matched legacy candidate, the cumulative `Total Monetary
Contributions` value on the latest usable report in the election year is the
preferred cycle total; loans and nonmoney contributions remain separate.  A
provider report link that returns an error page, an unreadable PDF, or a report
without a parseable cumulative value remains unknown and is never converted to
zero.  Because the predecessor archive currently lists many 2016 filings whose
PDF images are unavailable, the public FollowTheMoney candidate-cycle table
may fill only otherwise missing or unusable Arkansas observations.  That
secondary row must agree exactly on cycle, legislative chamber, district, and
major party and pass the conservative person-name match.  Its displayed
candidate-cycle `Total $` is retained as a secondary aggregation of reports
filed with the state, explicitly labeled in lineage, and never supersedes a
usable official observation.  A displayed zero in that complete candidate-
cycle table is observed zero; an absent or ambiguous candidate remains unknown.

Kentucky uses the official candidate-election registration total for the
modeled cycle, legislative chamber, and district. The regular general-election
registration is preferred. When the general index contains no compatible
registration, an exact official candidate-name search may supply the same-
cycle primary registration for that same chamber and district; a prior/future
cycle or different legislative scope is never substituted. Duplicate provider
rows are compared as person identities before ambiguity is evaluated, and the
registration with the closest full displayed name is retained. Ballot/formal-
name differences that cannot pass the conservative automatic threshold require
an approved evidence-bearing identity adjudication. A provider-reported zero
on the selected registration is observed zero; no registration is unknown.

North Carolina uses exact official candidate-committee (`CNC`) and joint
candidate-committee (`JNT`) queries over the complete two-calendar-year cycle.
The adapter retains the modeled WAR keys but prefers the final election-
warehouse candidate name for directory matching and canonical display.
Explicit congressional, judicial, county, and municipal committees are
excluded. Surname-only acceptance requires that the substantive committee name
reduce exactly to the surname and that surname be unique in the modeled cycle.
Because the portal classifies historical transactions under a committee's
current office, candidate resolution searches both House and Senate exports;
duplicate committee/year observations retain the more complete export. After
the official committee directory has resolved an exact committee and the exact
committee query has returned no monetary receipt records for the full window,
fundraising is `observed_zero`. An unresolved committee or incomplete query is
unknown, never zero. Each row cites only the immutable exact-query batch or
batches containing its accepted committee IDs.

Virginia candidate discovery may combine surname, given-name, prior first/last,
versioned exact first/last searches, and standard legal committee-title forms
for unresolved candidates, but only legislative-compatible committees with
conservative person-name evidence are accepted. Coincidental full-name initials
are not identity evidence, and known nonlegislative committees are excluded.
When every accepted committee has an acquired official report index and those
indexes contain no filing whose declared period overlaps the two-calendar-year
cycle, reported fundraising is `observed_zero`. An unresolved committee, a
missing committee index, or a listed report without its structured XML remains
unknown.
Within one committee, an amended reporting period whose single endpoint moves
by no more than one day supersedes the older version when the opposite endpoint
is equal; larger overlaps within that committee remain review items. Reporting
periods from distinct, independently accepted committee IDs may overlap because
they represent separate legal accounts; their receipts are summed. This does
not relax candidate-identity evidence or the exclusion of nonlegislative
committees.

Tennessee uses the official candidate report list and current report-summary
pages, partitioned by modeled candidate and report. The portal's statewide
transaction CSV is not authoritative for completeness because it exports only
the active server-side result batch. For each election grouping, current
reports named for the preceding or election calendar year are summed after the
portal has resolved amendments. Fundraising is total contributions plus
contribution adjustments and interest, excluding loans and in-kind receipts.
A valid report page that omits the entire receipt section is an observed zero
for those receipt categories; a malformed or inaccessible report remains
unknown.

South Carolina uses the official `electionCycleTotal` receipt categories
embedded in every report detail rather than adding potentially overlapping
`filingPeriod` amounts. Within each exact accepted campaign ID, the greatest
complete cumulative monetary-receipts snapshot is the cycle total; its cash,
personal, account-credit, debt-setoff, in-kind, loan, and expenditure components
are retained from that same report. Distinct campaign IDs attached to the same
accepted exact provider identity are separate official campaign registrations
and their selected cumulative totals are summed. Declared filing periods remain
audit evidence but do not create overlap or boundary failures for this
cumulative measure. A missing category or report detail remains unknown.

Texas follows the TEC `CFS-ReadMe.txt` numeric-field contract: the database mask
is “Blank When Zero.” Thus, a blank `totalContribAmount` on an otherwise valid
report cover is an observed zero, while absence of a report cover or unresolved
filer identity remains unknown. Zero-dollar report rows may be removed when
they overlap another report because their removal cannot change a cycle total;
positive or missing boundary/overlap amounts remain review items. The same
zero-dollar-only overlap rule applies to Virginia. South Carolina's cumulative
election-cycle measure is governed by the separate rule above.

Mississippi embedded-text and RapidOCR-derived summary totals retain their
parse method. OCR text is cached outside `data/raw/` with the source hash, OCR
engine, render configuration, generation time, and build-code hash. A form that
cannot yield both calendar-year summaries remains unknown. Oklahoma annual
bulk files are exhaustive. The adapter preserves the modeled key but prefers
the final election warehouse candidate display name, which retains meaningful
initials and filing-name aliases suppressed by older panel labels. After one or
more unique reciprocal name aliases
resolve a candidate identity from receipt or expenditure records, all accepted
aliases are aggregated by provider transaction ID. No compatible receipt
records in the complete window is then an observed fundraising zero. Louisiana
reads every contribution, expenditure, and loan bulk block that intersects the
modeled window, including `2024_to_2027` for the 2024 cycle. Once a Louisiana
filer ID is independently resolved from those exhaustive official blocks, an
empty monetary-contribution category in the complete window is an
`observed_zero`; in-kind-only, loan-only, or expenditure-only activity is not
treated as missing fundraising. An unresolved filer remains unknown.

## Southern historical WAR map contract

The public Southern WAR explorer covers the prespecified regular-election
schedule from 2016 through 2024 for AL, AR, FL, GA, KY, LA, MO, MS, NC, OK,
SC, TN, TX, and VA. State-specific odd-year elections and staggered chambers
retain their actual election years. A map slice is uniquely keyed by
`state_code`, `cycle`, and `chamber`; a scored race is additionally keyed by
the normalized provider district identifier.

WAR remains a race residual in Democratic two-party margin points:
`raw_gap = legislative_dem_margin - baseline_dem_margin` and
`war = raw_gap - fitted_structural_expected_gap`. Strict races after 2016 use
the published Southern WAR v3 same-cycle fitted residual. Strict 2016 races are
descriptive backward applications of the selected post-2016 Southern
`decaying_lag` ridge model with alpha 100; the model is fit only on races after
2016. Candidate-cycle views are exact party orientations of the same race
score. Research-only context rows, uncontested races, non-D/R races, and
districts without a model-valid outcome remain unscored and are never assigned
WAR zero.

Election-year Census cartographic-boundary files supply display geometry. Each
raw ZIP is immutable and registered with its URL, retrieval time, SHA-256,
terms, state, chamber, election year, and geographic vintage. Geometry joins
are `1:0..1` from a scored race to one district feature within the exact
state/year/chamber file. Duplicate geometry identifiers or an unmatched scored
race fail publication. Census display geometry does not adjudicate the
warehouse's provider-reported district-plan vintage; both provenance statements
remain visible.

Finance is an optional descriptive overlay joined `1:0..1` on the exact race
key. Amounts and ratios are published only where the finance mart marks the
race complete. Missing finance remains `unknown`, not zero. Fundraising does
not enter headline WAR because the prespecified nested time-forward finance
gate failed; state-level coverage limitations are published alongside the map.

## Central Southern election-context and geography contract

Schema version 17 centralizes presidential results at their actual source
geography and versioned legislative boundary features. Raw archives remain
immutable external assets registered by URL, retrieval time, SHA-256, terms,
vintage, and authoritative scope; the SQLite database stores normalized rows
and WGS84 WKB features rather than duplicate ZIP bytes.

`source_southern_presidential_geography_result` is one wide presidential
result per provider geographic unit. Provider-reported precinct totals retain
`vote_value_status = observed`; the Redistricting Data Hub nationwide 2020
block file retains `vote_value_status = derived` and
`allocation_method = rdh_vap_disaggregation`. Democratic, Republican, other,
and total votes must reconcile on every row. A source-level reconciliation
failure remains `validation_status = review` and is excluded from
`fact_southern_presidential_geography_result`.

`dim_southern_geography_layer` is one immutable state/cycle/chamber source
layer and `dim_southern_geography_unit` is one unique feature within that
layer. Source CRS is retained, storage geometry is normalized to EPSG:4326,
and each WKB feature is hashed. The result-to-geography relationship is many
to many only through `bridge_southern_result_geography`, whose rows require an
explicit match method and allocation weight. An empty bridge means the source
results and boundary layers are centrally available but not yet safe to join;
file presence or coincident names never imply a geographic match.

Schema version 18 adds explicit Census-block membership in election-year state
legislative plans. `source_southern_assignment_file` registers each immutable
national assignment archive. `bridge_southern_block_district_assignment` is
unique on assignment source, state, and 15-digit block GEOID and retains lower-
and upper-chamber assignments separately; an unavailable assignment is null
and labeled `unassigned`, never converted to a district zero.

`mart_southern_presidential_district_result` aggregates one validated
provider-grain presidential result through one exact block-assignment source.
Its reusable natural key is result source, assignment source, state, election
cycle, plan cycle, chamber, and district. The source-to-assignment join is
many-to-one on exact state and block GEOID; the resulting district row joins
`1:0..1` to the boundary feature for the same state, plan cycle, chamber, and
district. `fact_southern_presidential_district_result` excludes any allocation
whose state/chamber reconciliation is under review.

`qa_southern_presidential_district_allocation` must demonstrate source and
allocated Democratic and Republican vote conservation separately for every
state, plan, and chamber. Coverage shortfalls remain review data. A successful
load does not imply that another presidential year has been allocated to the
same plan.

Schema version 19 adds 2016 Voting and Election Science Team archives as a
combined result-and-geometry source family. `source_southern_vest_context_file`
is one manifest-backed archive per state. Every normalized 2016 presidential
precinct row has exactly one same-archive precinct geometry link in
`bridge_southern_result_geography` with weight 1; that link identifies the
source precinct and is not itself a district allocation.

Provider identifiers are scoped by state and county. Where Georgia, Tennessee,
or Virginia reports multiple named result pieces under one precinct ID, the
canonical geography key retains both provider ID and provider name. Repeated
Florida and Missouri zero-vote geometry fragments may be dissolved only after
all presidential vote fields agree. Invalid source polygons are repaired only
in normalized storage, with the count retained in
`qa_southern_vest_context_ingest`; raw archives remain immutable.

Schema version 20 allocates those VEST precincts to the enacted 2022 plan.
`source_southern_census_block_file` registers one immutable official TIGER2020
block archive per state. Block VAP is joined by exact 15-digit GEOID from the
registered RDH 2020 block source, and legislative membership is joined by the
same exact GEOID from `bridge_southern_block_district_assignment`. A missing
assignment is tolerated only for a zero-VAP block and is excluded, never
imputed.

`bridge_southern_vest_precinct_district_weight` is unique on VEST result,
assignment source, chamber, and district. Its reusable join is many-to-one
from 2020 Census blocks to a VEST precinct and then many-to-many from precinct
to district only through explicit normalized weights. Representative-point
matches are resolved by maximum intersection area when ambiguous. Weights use
2020 modified VAP. Geometry-intersection area is an explicit fallback only for
a vote-bearing precinct with no positive-VAP block match.

Every vote-bearing precinct must receive weights summing to one within
`1e-10`. `qa_southern_vest_precinct_plan_allocation` must also show no missing
vote-bearing precinct, unmatched positive VAP at or below 0.1%, and fallback
two-party votes at or below 0.1% for each state/chamber. District results enter
`fact_southern_presidential_district_result` only when both that audit and the
separate Democratic/Republican vote-conservation audit pass.

Schema version 23 extends exact-plan allocation to 2012 presidential context.
An election-vintage precinct geometry is joined to its own validated 2012
result source before any overlay. Non-geographic absentee, provisional, and
other provider-reported mode rows may be distributed only within their
reported county or locality, separately by party. Each prepared precinct is
then allocated to the exact 2018--2020 legislative plan using 2020 modified
VAP, with a separately labeled geometry-area fallback. Source votes must
reconcile, precinct weights must sum to one within `1e-10`, unmatched positive
VAP and fallback votes must each remain at or below 0.1%, and every
state/plan/chamber cell must pass before it enters the central fact.

Provider conversion corrections require an independent registered evidence
source and a row in `qa_southern_presidential_result_correction`; they may not
be hidden as unexplained value edits. The correction records pre/post totals,
the expected evidence totals, affected county and row count, method, status,
and build run. Corrected normalized rows retain the immutable original source
file ID and identify the correction method. Schema version 24 applies this
contract to the transposed 2012 Harrison County Democratic/Republican columns
in the Mississippi precinct conversion.

Schema version 25 permits a narrower district-specific readiness decision when
an historical precinct-name crosswalk remains incomplete. This is not a waiver
of statewide reconciliation. The state/plan/chamber allocation stays
`review`, and every unresolved result remains in
`qa_southern_presidential_precinct_match` with its within-county plausible
donor set and two-party vote count. An unresolved row may be allocated only if
all plausible donor geometries collapse to one district for that chamber. A
district may receive `allocation_status = passed` only when no other unresolved
row has ambiguous plausible exposure to it; all affected districts remain
`review`. `qa_southern_presidential_district_readiness` records this decision
for every district, and the central fact view continues to expose only passed
mart rows.

For Mississippi 2012, accepted name matches are one-to-one within county.
Exact 2012 names, exact ballot/VTD codes, and later names tied to the same VTD
code outrank conservative fuzzy matches. A later-name alias based on geometry
is allowed only where the older and later polygons are mutually at least 90%
coincident. The hash-registered 2019 RDH/VEST archive is corroborating alias
evidence only: its votes are never substituted for 2012 returns. Allocation to
the exact plan used in 2019 uses 2020 modified VAP, with geometry-area fallback
only for a donor having no positive-VAP Census block. This exception does not
turn an unresolved statewide allocation into a completed one.

For Alabama 2012, the official SOS presidential archive is authoritative for
county and statewide totals. Existing OpenElections rows provide precinct
distribution where available, and the official SOS county workbook provides
Montgomery precinct detail, which OpenElections omits. Each party's precinct
values are scaled within county to its certified SOS total, with the factor and
detail provider retained. A workbook that explicitly reports `Precinct Results
Unavailable` and has no OpenElections detail is represented only by its SOS
county-total row. Such a row retains `geography_type=county` and is distributed
through the target plan as an explicit county-level batch; it is never
represented as an observed precinct. Candidate-name mapping identifies the
Democratic and Republican presidential tickets because some SOS workbooks omit
party labels. All 67 county components and statewide Democratic and Republican
totals must reconcile to the official archive before a complete Alabama source
flag may be emitted.
