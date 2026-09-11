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
