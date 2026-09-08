# Southern VEST 2016 warehouse validation

## Result

Schema version 19 centralizes the VEST 2016 presidential precinct results and
their matching polygons for all 14 Southern model states.

- Build run: `RUN-0FB41102683B421BBCDB98FAD04D1462`
- Harvard Dataverse dataset: `doi:10.7910/DVN/NH5S2I`, version 97.0
- License: CC BY 4.0
- State archives: 14
- Source features: 46,065
- Normalized precinct result/geometry pairs: 45,990
- Accepted one-to-one result/geometry links: 45,990
- Invalid source geometries repaired in canonical storage: 15
- Review states: 0

Each archive is registered with its Dataverse file ID, direct source URL,
retrieval time, SHA-256, upstream MD5, byte size, terms, state, election cycle,
and geography vintage. The acquisition script refuses to replace an existing
raw file whose bytes differ from the pinned version-97.0 metadata.

## Normalization decisions

The Democratic and Republican fields are VEST's `G16PREDCLI` and
`G16PRERTRU`; all other `G16PRE*` fields remain explicit other-candidate vote
components. The total is calculated only from those observed presidential
fields. Every stored result has one same-archive precinct geometry and every
stored geometry has one result.

Florida and Missouri include repeated zero-vote geometry fragments. They are
dissolved only after every presidential field agrees. Georgia and Tennessee
contain distinct named precincts under repeated provider IDs, while Virginia
contains named congressional-district pieces of precincts; their canonical
keys retain both provider ID and name. Fifteen invalid polygons are repaired
after reading and before WGS84 normalization. The immutable archives preserve
the original geometry.

## Scope limit

The one-to-one bridge is a result-to-source-precinct identity, not a claim that
the precinct belongs wholly to a later legislative district. V4 remains
unchanged until a population-weighted precinct-to-2022-plan crosswalk passes
coverage, split-precinct, vote-conservation, and geographic-vintage checks.

## Reproduction

```powershell
python scripts/acquire_southern_2016_precinct_geography.py --offline
python scripts/load_southern_2016_vest_warehouse.py
python -m pytest scripts/tests/test_southern_2016_vest_warehouse.py -q
```
