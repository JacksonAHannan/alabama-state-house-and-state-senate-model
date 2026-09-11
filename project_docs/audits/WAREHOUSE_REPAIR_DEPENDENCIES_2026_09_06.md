# Warehouse repair dependency inventory — 2026-09-06

Internal, read-only audit for `warehouse-02`. This inventory is not a repair,
analytical validation, or publication approval. No sources, warehouse contents,
models, or public pages were changed. The simplicity rule kept this work to the
existing lineage, implementation, and manifests; no orchestration infrastructure
or replacement metadata system was introduced.

## Snapshot and interpretation

- Source repair: `RUN-40A033B9854141F6B05A76173E66D17B`, completed
  `2026-09-05T21:34:14.194451+00:00`.
- Provenance repair: `RUN-C7DE0A0267EC4445938D1CA0CB5C4BD3`, completed
  `2026-09-05T21:35:27.638360+00:00`; this remains the latest registered build.
- [Machine-readable evidence](WAREHOUSE_REPAIR_DEPENDENCIES_2026_09_06.json)
  records the live repair rows, five latest builds, catalog counts, and 76
  manifest-declared input/code/output/report SHA256 comparisons at
  `2026-09-06T16:54:51.705918+00:00`.
- Central database SHA256:
  `2dfcdcb81079605b9ac36f5670d30957500f8cec74ddafa1da18b3eccd613377`.
  Size 5,768,613,888 bytes; size/mtime unchanged across that inspection.
  Reads used SQLite URI `mode=ro` and `PRAGMA query_only=ON`.

**Confirmed stale** means an observed incompatibility with the repaired input or
contract. **Unrevalidated** means a dependency predates its repaired input and
lacks subsequent reconciliation. **Unresolved impact** means reachability or a
numerical/output difference is not established. **Current for this defect** is
deliberately narrower than overall correctness. A matching file hash proves
bytes, not upstream scientific freshness. A whole-database mismatch can reflect
unrelated domains; an old build ID need not describe every later view definition.

The [source repair audit](WAREHOUSE_SOURCE_REPAIRS_2026_09_05.md) remains the
authority for what was repaired. `WQA-dependencies` still says `stale_review`.
The catalog now contains 103 assets and 99 edges, not the older audit's 98/93.
It contains no asset locators for the four named precinct-identity tables.
Its legacy CMO route also does not describe all four current products. Therefore
the inventory supplements catalog edges with actual readers; missing edges do
not mean independence. No registry records were edited during this audit.

## Dependency inventory

Paths below are repository-relative; script line references identify the
inspected implementation, not a guarantee against subsequent edits.

| Repair / branch | Actual dependency and evidence | Disposition | Next bounded action, requiring separate repair authority where applicable |
|---|---|---|---|
| WQA-01/02/03/04: precinct identity | `vote_observations` → `build_precinct_identity.py:119` → `precinct_nodes`, `precinct_vote_fingerprints`, `precinct_source_links`, `precinct_match_candidates`, `precinct_link_review.csv`. Stored/current SOS distinct county/precinct keys: 1994 2,617/3,081; 2002 2,759/2,758; 2014 2,312/2,311. 2,950 current 1994 keys are absent from nodes; Jefferson's deleted 2014 summary persists as node 24475. | Nodes confirmed stale; fingerprint/link/match materializations unrevalidated against the corrected node universe. | Compare staged keys and all node-ID consumers before any replacement. Preserve adjudications and match evidence. |
| Identity → modern geography | `build_precinct_geography_links.py:112` reads nodes, fingerprints, accepted source links and `precinct_vtd_link_evidence`; outputs geographic nodes/fingerprints, geography candidates/links, canonical geography evidence/links/conflicts and review CSV. `build_canonical_geographic_weights.py:29` then produces canonical district weights and QA for 2010/2014/2018/2022. | Unrevalidated; later years are not automatically insulated from identity rebuilds. | Reconcile `geographic_precinct_vtd_matches.csv` and all stored `source_node_id` references together. The identity builder uses sequential `np.arange` IDs (`:35`) and reloads that saved CSV (`:134`); changed early-year cardinality can renumber later-year nodes. |
| WQA-03/04: 1994 weights and baselines | `build_1994_cmo_baseline.py:34` reads repaired observations plus canonical candidates; writes historical weight, office-baseline and race-feature tables/CSVs. Latest run `RUN-ADA16D76E1BB4520ABA370CED9922828`, completed Aug 16 19:08:30 UTC. 2,457 stored weight keys are absent from current source; 2,916 current legislative keys are absent from stored weights. | Confirmed key staleness; downstream district-value impact unresolved. | Reconcile source/candidate keys and allocation evidence before updating derived baselines. Do not reinterpret missing matches as zero. |
| WQA-02/03/04: historical context | `build_1994_context_features.py:147` uses saved 1994 weights while reparsing separate 1992 presidential files. `build_1998_2006_context_features.py:162,186,225` builds 2002 weights from normalized observations and separately reads 2000 presidential workbooks. | Existing affected allocation/context outputs unrevalidated. Rereading an unchanged presidential source does not refresh saved repaired-year weights. | Assess the affected allocation inputs first. Do not label independently sourced demographic or other context components defective without evidence. |
| WQA-01–04: federal baselines | `build_historical_federal_baselines.py:39,63–84` mixes normalized returns, stored nodes, saved 1994 weights, directly constructed intervening-cycle weights and saved modern weights. Latest run `RUN-F1A4FADA01DC4386A7BE91B86A3A30C5`, completed Aug 21 14:50:08 UTC. Produces historical district baselines, contest components and the historical federal-baseline mart. | Unrevalidated mixed snapshot. | Compare affected keys and source totals after identity/weight reconciliation; retain the current historical artifacts until replacement evidence is accepted. |
| WQA-01–04: candidate identity and compatibility exports | `build_candidate_identity.py:134,199–201` derives aliases/totals from normalized returns but can substitute independent consolidated results. Latest identity run `RUN-872E84CE49F34E46A3B71A275F9C8890`, Sept 2 02:51:42 UTC. Canonical source labels: 1994 211 SOS rows; 2002 213 SOS rows; 2014 196 consolidated-result rows. Identity tables feed `dim_person`, `fact_candidate_election`, `bridge_person_alias`. | Aliases/source evidence unrevalidated; no blanket finding that all candidate totals are wrong. | Compare identities and alias evidence to independent official totals; determine whether identity rows, aliases, or both need correction. |
| Compatibility → current consumers | `build_canonical_cmo_features.py:24–30,60,199,215` reads candidates, normalized returns, nodes, modern weights and historical context. Its exports and federal baselines feed retained `cmo_v5` compatibility inputs; current historical Alabama builder reads these (`:26–28`). Historical renderer also reads canonical context (`build_war_story_page.py:102`). | Matching compatibility/output hashes do not resolve the stale source chain. | Preserve these live dependencies; they are not deletable merely because their names are legacy. Record an accepted source/export comparison before claiming freshness. |
| WQA-05: Arkansas stored geometry | Stored `dim_southern_geography_unit.geometry_wkb` → `bridge_southern_result_geography` → `build_southern_2016_vest_plan_allocation.py:53–70` → VEST weights → presidential district mart/fact and allocation exports. Arkansas retains 5,362 weights (2,761 lower / 2,601 upper), all run `RUN-F1AF08B0478A4B34BA87DE80E91F1CAF`, completed Sept 4 01:13:08 UTC. Nine repaired units join to 21 retained weights across 18 chamber/district keys. | Allocations unrevalidated after stored-geometry repair; numerical differences unresolved. Manifest has run identity but no consumed geometry hashes. | Compare only affected geometry/allocation inputs under the same source snapshot in isolated staging. Do not blindly run the existing builder: it deletes all states' VEST allocation rows (`:391–400`) and has no Arkansas-only scope. |
| WQA-05: downstream reachability | Research v4 reads `fact_southern_presidential_district_result` (`retrain_post2016_southern_war_v4.py:152,182`). Current v3/historical routes read prepared context/outcome tables and separate saved context files. `load_southern_war_preparation_warehouse.py:298–340` copies context from `southern_war_panel_v1/southern_war_panel.csv`, not the repaired geometry directly. | Direct research dependency established; indirect current-public impact unresolved. | Recover panel/source-level lineage where absent. Do not equate research-v4 reachability with a current-public defect or promote v4. |
| WQA-06: roll-call eligibility | Current legacy gate in `build_alabama_legislative_ideology.py:44–51` checks reported total against member count, not every canonical category. Standalone loader filters that cached eligibility (`build_unified_legislative_rollcall_warehouse.py:40–41`). All 24 known QA conflicts also fail this old total check. | Current exclusion for these 24; full canonical-gate equivalence and reproducible lineage unresolved. | Characterize both eligibility interfaces and preserve exclusions. Do not automatically recalculate downstream analyses solely because the canonical view was added. |
| WQA-07: compatibility finance export | `finance_free_southern_war/southern_war_training_with_finance.csv`: 4,582 rows, 675 incomplete, 110 incomplete rows retaining numeric finance features. SHA256 `89cf801469168f47174bb6533a3431ce9ffad79a4e05d89211f4d8f9fef3e595`. Exporter `load_southern_war_preparation_warehouse.py:452–472` reads the repaired SQL view; adjacent manifest retains `RUN-85A4692E481448B6BB1380D76E07742B` without output hashes. | Confirmed stale export. Exact-name runtime search found no reader beyond exporter/catalog references. | Refresh only this export with accurate provenance, after checking side effects and authority; do not rerun the whole preparation loader, which replaces shared marts. |
| WQA-07: other finance interfaces | Finance-model CSV: 7,976 rows / 4,068 incomplete / zero unmasked. Current Southern historical and corresponding public race CSV: each 4,280 / 645 / zero unmasked. Exporter (`:43–58`), historical builder (`:273–277`) and map (`:159,190–192`) have defensive masks. | Current for incomplete-feature masking, not full finance quality certification. | Preserve existing masks; verify only affected export consumers. A pre-repair date alone does not establish this defect. |
| WQA-08: DIME/registry provenance | DIME manifest Sept 4 22:11:31 UTC, run `RUN-E2FDFA0669F34C03955335EA54632137`, already has `retrieved_at: null`. All six declared CSV hashes match. Three grain-description changes and three restored SOS URLs correct metadata; raw sources were unchanged. | Corrected metadata; no demonstrated numerical invalidation from this correction. Acquisition time remains unknown. | Keep unknown acquisition time explicit. Recover missing original terms/scope and legacy build evidence separately; never infer them from registration time. |

### Roll-call consumer evidence

The 31,257-row eligibility CSV retains all 24 conflicts explicitly marked
ineligible. None of those IDs occurs in the standalone `rollcall` table or these
inspected downstream files (row counts in parentheses): comprehensive
classifications (60,704), frontier ontology (60,789), legislative position
evidence (13,617), combined position evidence (25,698), reviewed candidate
roll-call evidence (378), issue-bill review queue (2,319).

The current route is standalone member votes plus accepted classification and
identity evidence → legislative evidence → combined issue evidence → existing
analysis/payload helpers → `build_democratic_transition_page_v2.py`. That page
also reads combined evidence directly and joins historical Alabama candidate
exports separately. The standalone database records an Aug 16 build timestamp,
schema and scope, but no input hashes. Several intervening CSV builders lack
run-bound input/output manifests. The Aug 24
[earlier coverage audit](LEGISLATIVE_IDEOLOGY_POST_REPAIR_COVERAGE.md) deferred
downstream work; it is not evidence that September's 24 conflicts contaminated
the current page. Their exclusion does not close those separate older gaps.

## Four product routes: byte consistency versus freshness

The [pipeline index](../CANONICAL_PIPELINES.md) identifies the current entry
points. This is an inventory of file/database consumers, not a model evaluation.

| Route | Fresh manifest checks | Remaining dependency disposition |
|---|---|---|
| Shared modern Southern v3 input bundle | Sept 2 manifest: 23/25 declared comparisons match. Whole warehouse hash differs, and `2018_district_presidential_features.csv` differs. All declared output/code/report hashes match. | Input snapshot drift established, cause/consumed-field effect unresolved. Do not rewrite its manifest to make it match. |
| Historical Alabama | Sept 2 historical manifest 11/11; modern Alabama bundle 6/6. | Source identity/weight/context chain remains unrevalidated despite unchanged immediate files. Historical page also directly consumes canonical context. |
| Southern historical 2016–2024 | Sept 5 22:15:37 UTC manifest 18/18, including current database bytes. This file build happened after source repair even though there is no later registered warehouse build. | Post-repair file creation is not evidence that old identity/allocation materializations were repaired. Stored-geometry direct dependency is established for research v4; current-public indirect reachability remains unresolved. |
| 2026 forecast | Sept 2 manifest 16/16 declared comparisons. Its renderer also reads canonical 2022 candidates for display. | Listed-file parity does not cover transitive warehouse/context drift. The builder directly uses the shared loader; the manifest's listed inputs do not fully capture that read. No forecast was recalculated or assessed here. |
| Ideology/caucuses | Known conflicting IDs excluded in inspected evidence outputs; no single run-bound manifest spans the whole current page route. | Complete lineage unresolved; historical Alabama join inherits its source-chain caveat. No new September conflict contamination demonstrated. |

The modern bundle's changed 2018 file has recorded SHA256
`53ac22998689c1a1a69d93cb9e6388ab4d4b1bb01895c70859cff6a6c43b2694`
versus current
`064c89b51842a26fa108da0b1ad7278f464b9a1c5faaa01aa44e8fffb5dc2d90`.
The audit has not established when or why it changed, whether consumed columns
changed, or whether that difference arose from September's repairs. Recover the
recorded snapshot and inspect its provenance before deciding on any repair.

No browser/page rebuild or comprehensive public-download parity audit was run.
The public Southern race-file masking check above is narrower than page/payload
agreement. Renderer dependencies are traced, but HTML bytes are not certified.
The historical/current manifests also omit some transitive dependencies, so
their 74 matching comparisons cannot close the warehouse's stale-review flag.

## Safe handoff order

1. Obtain scoped authority for the small stale finance-export correction; keep
   shared loader/model/publication steps out of that write.
2. Prepare a read-only or isolated staging comparison of precinct identities,
   retained adjudications, all node-ID consumers and affected historical weights.
   Do not mix new node IDs with old geographic-link evidence.
3. Reconcile candidate/source aliases and historical allocation evidence against
   preserved sources; retain disagreements and unknowns.
4. Compare the nine Arkansas geometry dependencies in isolation, and recover the
   changed 2018 input's recorded snapshot. These are separate uncertainties.
5. Document canonical roll-call gate equivalence and missing transitive lineage.
   Publication or analytical changes require their own authorization and gates.

Residual source conflicts (including the disputed fractional Morgan cells),
unadjudicated natural-key collisions, missing terms/scope, and old `running`
records remain open as documented in the source audit. A run's `running` status
is not proof a process is alive. This inventory neither repairs nor closes them.

## Verification and acceptance

- Fresh read-only SQL: repair records, latest builds, catalog counts, key
  anti-joins, affected geometry/weight reachability, and known roll-call ID
  exclusion. Bounded reader agents returned evidence without edits.
- SHA256: 76 comparisons in the linked JSON, 74 matching and two input
  mismatches; mismatches are findings, not failed audit execution. Additional
  finance export and DIME manifest checks are described above.
- No pipeline/test-suite execution was needed for this documentation-only
  inventory. No claim is made about a full-suite pass or product release.
- Independent read-only inventory review: PASS. Reviewer reproduced repair/run
  identities, catalog and precinct-key findings, the 110 unmasked export rows
  versus zero in the repaired SQL interface, exclusion of all 24 conflicts by
  the legacy total gate, and all 74 non-database comparison hashes recorded in
  the JSON. Those 74 checks include the changed 2018 file's actual hash; they
  are not 74 assertions of equality to the original manifests.
- Report links and JSON comparison counts verified. Existing browser checks
  passed scope/IDs, toggling/persistence/counter/history, filters, safe export
  and viewport checks, restoring test edits. Final repository snapshot checks
  are recorded in the handoff.

Only `warehouse-02` may be closed after inventory review. Stale dependencies
remain open; none of the four products is declared complete by this report.
