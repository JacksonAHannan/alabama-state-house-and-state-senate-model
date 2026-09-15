# Site release, 2026-09-14

Single republish covering the three products changed in this session. The
Southern WAR map is republished unchanged by the same command.

## What shipped

| Product | Published state |
|---|---|
| Ideology and caucuses (`docs/ideology-performance.html`) | Person-level run `AL-DEM-CAUCUS-V1-675DE69CDA4A3D5513AF`: five owner-approved groups over the eight ontology issue families, coverage funnel, per-group unscored share and the full cluster-sensitivity panel. `docs/caucuses.html` is now a redirect. |
| 2026 forecast (`docs/index.html`, `docs/methodology.html`) | Build `08feb2c9669842846d3f`: WAR structure plus carried-forward candidate WAR on 23 of 48 modeled races, generic-ballot snapshot as of 2026-09-08, all three holdout MAEs published. |
| Historical Alabama WAR (`docs/cmo.html`) | `AL-HIST-WAR-V1-0E018273EBEDEEEFAD75` with the new career cumulative WAR section and download, and fixed-reference wording in place of backcast framing. |
| Southern WAR (`docs/southern-war.html`) | Unchanged; rebuilt by the site command (116 slices, 4,280 races, payload sha256 `143305d4…`). |

## What changed for readers

- The caucus page no longer shows the stale 2026-08-24 three-group clusters or
  any CMO v4 value. It shows five groups built from the current evidence layer,
  what each group's issue profile is, how many people back each family, how many
  of its candidate-cycles had no contested general election, and an explicit
  panel of how much the grouping moves under alternative reasonable choices.
- The forecast now uses a candidate's own demonstrated WAR where one exists. The
  page says which races that applies to, what the persistence coefficient is,
  and that the owner-selected model still trails the generic-ballot benchmark on
  the single available holdout.
- The Alabama WAR page gained career cumulative WAR, which is the measure of
  sustained overperformance, and stopped describing pre-2016 scores as a
  backcast; they are scored against one fixed 2018–24 reference model, with the
  by-construction caveat stated.

## Verification

- Warehouse integrity before publishing: `quick_check ok`, 0 foreign-key
  violations, 120 tables, 5.82 GB.
- Release gate caught a stale declared input (the forecast field contract was
  edited after the manifest hashed it) and refused to publish until the forecast
  was rebuilt. Working as intended.
- Browser passes on the published pages at 1280 px and 390 px: caucus page
  (measure toggle, member search, group filter, row selection, era-normalized
  disclosure, no overflow); forecast dashboard (polling chip 2026-09-08, 105
  House rows, no console errors); Alabama map (district click and keyboard Enter
  populate the detail, districts without a record show an accurate empty state,
  candidate search filters, every download target resolves).
- Focused suites for every changed area pass; the full repository suite result
  is recorded in the coordination checkpoint.

## Known limitations carried into the release

- Cluster membership is sensitive to imputation (ARI 0.44), evidence channel
  (0.19) and era normalization (0.33); the groups are descriptive tendencies,
  not formal caucus membership.
- 22 Democratic people have 2022 canonical records with only a source stub; they
  appear by seat, flagged unresolved, and their careers cannot be linked to
  earlier cycles.
- Candidate-history persistence is measured over 2-to-6-year gaps and applied up
  to 8 years; 2026 matches older than that are recorded but not carried.
- One direct Alabama forward holdout exists, with 6 carry-eligible races in it.
