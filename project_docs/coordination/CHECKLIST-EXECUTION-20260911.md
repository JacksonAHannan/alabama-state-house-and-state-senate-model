# Checklist execution — 2026-09-11 (post-release)

Owner: primary session / orchestrator. Status: active. Follows the closed
release umbrella `CHECKLIST-EXECUTION-20260910.md` (checkpoint 4, commit
`f407b9d0`). Authority: owner "Proceed" on the listed next steps. Standing
constraints: no publication without a separate authorization, no warehouse
writes without a staged and reviewed proposal, preserve unrelated work.

## Ordered work

1. `WEB-MOBILE-SHELL-OVERFLOW-20260911` — `release-05` mobile overflow (local proof; publication asked separately).
2. `WAREHOUSE-05-SOURCE-ADJUDICATION-EVIDENCE-20260911` — evidence packet for the owner's adjudication of 2002 HD26/HD27 and 2014 party labels.
3. `ALABAMA-BACKCAST-SENSITIVITY-20260911` — `alabama-07/08`.
4. `FORECAST-POLLING-SNAPSHOT-POLICY-20260911` — `forecast-04`.
5. `IDEOLOGY-EVIDENCE-LAYER-VALIDATION-20260911` — `ideology-04..07` and the classification-file provenance.

All read the published lineage; none rebuilds a published export. Acceptance
is recorded per task below.

## Checkpoints

### Checkpoint 1 (2026-09-11 15:16Z)

Session crashed mid-wave; state reconciled from on-disk deliverables (all five
slices had written their files; two had not reported). All five accepted after
primary verification: mobile overflow proven at 390/1258 px on themed
candidates; 35 fixture tests across the new audit suites pass. Checklist
39/82, revision `2026-09-11T15:15:48Z`.

Material finding: backcast WAR levels are not transportable across eras (mean
−20.5 pp vs a same-era fit; rank order preserved). Disclosed in the release
card and the methodology template; the public page will carry it at the next
publication together with the mobile fix.

Awaiting owner: (1) republication of the methodology shells and Alabama card
text; (2) `warehouse-05` dispositions — 2002 HD26 (A1 adopt the county-complement
district total / A2 keep DeKalb-only and flag / A3 exclude), 2002 HD27 (B1
rebuild identity and canonical from the repaired warehouse / B2 keep excluded
with a recorded gap / B3 canonical+features only), 2014 party labels (C1
preserve as source fact with warning / C2 auditable repair of the x2
duplication and printed labels / C3 quarantine from precinct allocation).
Any A1/B1 choice invalidates the Alabama compat chain, the historical export
and the pages, and re-enters the Southern panel (Alabama 2002 is a backcast
cycle, outside the v3 training frame, so v3 itself is unaffected).

### Checkpoint 2 (2026-09-11 16:10Z) — second release

Owner dispositions: HD26 A1, HD27 B1, 2014 C1, publish once after rebuild.
Scratch identity rebuild against a warehouse copy surfaced SD9 as a third
Marshall casualty and proved a full rebuild would revert the 21 certified
corrections; the scoped repair `RUN-DFB1D093D7594AB68A264292050E924D` applied
after independent review PASS. Compat chain, `cmo_v6` legacy, panel and
`AL-HIST-WAR-V1-44F191EB8D939EF062CC` rebuilt; ten pages republished with the
mobile fix, era disclosure and release-card link; 20 renders clean. Checklist
41/82; `alabama-02`, `release-05` accepted.

Commits `29c1b3df` (release), `29a2739e` and `1396e0ee` (untracking staging
copies and geopackages that `git add -A` re-included; ~600 MB of blobs remain
in history — owner may request a history rewrite). Rollback reference for the
published site: `f407b9d0`.

Open follow-ups: `ideology-04` (queue 17 low-confidence mappings), blast
radius of the 2002 legacy Marshall parse and the 2014 x2 duplication
(`warehouse-05`), stale `candidate_research_final_status.csv` (26 cycles),
polling refresh (`forecast-04`, needs authoritative-source terms), orphaned
`docs/data` legacy downloads (`release-01`).

### Checkpoint 3 (2026-09-11 17:06Z)

Wave 3 accepted: low-confidence review-queue invariant (`ideology-04` ✓),
closure restatement (`ideology-06` caveat closed), blast-radius audit (no
further 2002 casualties; 2014 "duplication" corrected to dual-source-by-design,
erratum added to the packet), docs/data inventory (30-file removal proposal),
forecast selection/calibration audit (`forecast-07` ✓). Checklist 43/82.

Escalated to owner: (1) forecast probability scale sits at the grid boundary
(2.0) and under-covers (18% at nominal 80%); options in
`audits/FORECAST_SELECTION_AND_CALIBRATION_INDEPENDENCE_2026_09_11.md`;
(2) removal of 30 superseded `docs/data` downloads (publication action);
(3) optional git history rewrite for ~600 MB of accidentally committed blobs.

### Checkpoint 4 (2026-09-11 21:14Z) — third release

Owner decisions executed: probability scale by residual likelihood (build
`b76d607f2d81e54697a3`, scale 8.0, 80% coverage 0.85; margins and seat distributions
unchanged); 30 superseded `docs/data` downloads removed; git history left as
is. Catalog updated. Ten pages republished, 20 renders clean. Checklist 45/82;
`forecast-08`, `forecast-09` accepted.

Open: `warehouse-05` broad collision census; `warehouse-04` Arkansas geometries
and 1994/2002 allocation reconciliation card; `forecast-02/03/10/11/12`;
`alabama-04/05/06`; `ideology-08..13`; Phase 7 release items. External:
polling refresh terms (`forecast-04`).

### Checkpoint 5 (2026-09-11 22:03Z)

Wave 4 accepted: roster/universe (contract now states seat treatment), 2024
baseline certification (exact conservation), Alabama plan certification, scale
comparability (page block + source attribution), source terms and hygiene;
dead story-page publisher code removed. Checklist 48/82; `forecast-03/10`,
`ideology-08` accepted. Page candidates (ideology attribution and scale block)
await the next publication.

Escalated to owner: (1) `alabama-04` — the compat builder substitutes the
legacy OpenElections-derived `district_baseline_office.csv` for its own
SOS-conserving 2014 state-ticket allocation (AG 49/67 counties; Governor 17%
short); 26 backcast races affected by mean −0.04 / max 2.6 pp; fix = drop the
2014 override (keep 2018/2022, which conserve) and rebuild the compat chain,
historical export and pages. (2) `release-08` — terms completion: register
Catalist workbook and Vote Smart with terms; resolve NYT precinct and SOS
canvass redistribution status; 2,153 registrations lack a license string (the
Alabama Legislature, DOJ Section 5 and ADAH archive families account for
2,091); decide whether the 14 tracked raw files stay in git.

### Checkpoint 6 (2026-09-11 22:59Z) — fourth release

Owner: accept 2014 repair; sourcing not a priority. Executed the repair and
downstream chain, republished all pages (`audits/SITE_RELEASE_2026_09_11.md`,
fourth release). Checklist 50/82; `alabama-04`, `release-08` accepted.
