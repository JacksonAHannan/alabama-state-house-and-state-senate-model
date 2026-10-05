# Task contract: ALABAMA-SEATS-BY-CYCLE-20261003 seats won by party per regular general election

- Accountable role: `elections_geography`
- Owner: `/root/seats_by_cycle` (delegated worker; parent `/root` owns integration)
- Status: `complete`
- Objective: Build a reproducible, reconciled dataset of Alabama House (105) and Senate (35) seats won by party at each regular general election, 1994–2022, for the forecast page's historical context chart.
- Product/layer and checklist IDs: 2026 forecast presentation context; derived election mart; `roadmap-07`.
- Dependencies: reads the populated central warehouse as it stands; unblocks the historical seat chart in `WEB-VISUAL-REDESIGN-20261003`.
- Non-goals: no warehouse writes, no source repairs, no changes to WAR, forecast, ideology or identity products, no public-page edits. "Seats won at the general election" is not chamber composition at session start: special elections, appointments and party switches are out of scope and must be labelled as such.
- Upstream snapshot: working tree on 2026-10-03 (HEAD `178d6f48` plus uncommitted candidate-identity work, which this task must not edit); warehouse `data/processed/elections/alabama_elections.sqlite` read-only.
- Read scope: warehouse tables and views; `data/raw/` (read-only); `project_docs/`.
- Write scope: `scripts/build_alabama_seats_by_cycle.py`; `scripts/tests/test_alabama_seats_by_cycle.py`; `data/processed/elections/alabama_seats_by_cycle_v1/`; `project_docs/audits/ALABAMA_SEATS_BY_CYCLE_V1.md`.
- Warehouse mode: `read-only` (`mode=ro` URI connections only).
- Inputs: final-stage regular general-election legislative results for Alabama, 1994–2022, including uncontested seats; independent references already registered under `data/raw/` for reconciliation.
- Outputs: district-cycle winners with source lineage; seats by cycle, chamber and party with explicit `unknown` counts; reconciliation against independent references; review queue for unresolved or conflicting districts; manifest with code version, warehouse run id, input hashes and row counts; audit note.
- Acceptance checks: one row per chamber-district-cycle (105 House, 35 Senate per cycle) with tested uniqueness; seat counts sum to chamber size with unknowns explicit, never imputed; every seat total either reconciles with an independent reference or is listed in the review queue with evidence; focused tests pass via `.venv/Scripts/python.exe -m pytest scripts/tests/test_alabama_seats_by_cycle.py -q`.
- Review requirement: parent inspects the outputs and reconciliation before the chart consumes them.
- Publication authority: none. Owner chose a local build only on 2026-10-03.
- Recovery/replay: deterministic script; outputs overwritten only inside the owned directory; safe to rerun.
- Handoff recipient: `web_product` (parent).
- Known risks: missing or mislabelled uncontested seats; runoffs or contested certifications; districts whose canonical rows lack a final-stage marker; 1994 plan vintage.

## Completion (2026-10-03)

- Run `AL-SEATS-V1-44C73422B2A2A12D733C` from `fact_southern_legislative_final_candidate_election` (Alabama canonical final-stage rows plus 64 Klarner gap fills), read-only. Outputs, reconciliation and the 51-item review queue (34 blocking) are in `data/processed/elections/alabama_seats_by_cycle_v1/`; method and open items in `project_docs/audits/ALABAMA_SEATS_BY_CYCLE_V1.md`.
- Parent acceptance: re-ran `scripts/tests/test_alabama_seats_by_cycle.py` (16 passed); confirmed 1,120 unique cycle-chamber-district rows and that every total sums to chamber size with unknowns explicit.
- Material finding for the owner: every 1994 State House and Senate row in `vote_observations` takes its party from ballot position (`party_method = ballot_order_with_export_code`). In 19 districts the canonical party conflicts with Klarner (HD91's winner flips), so those seats are `unknown`. This likely affects 1994 historical WAR orientation as well and needs a source adjudication; this task made no repair.
- Consumer: the forecast page's "Seats won since 1994" chart shows unknown seats hatched and flags totals not matched to an independent reference.
