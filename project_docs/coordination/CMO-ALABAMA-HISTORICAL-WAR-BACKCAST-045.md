# Task contract: CMO-ALABAMA-HISTORICAL-WAR-BACKCAST-045 — restore historical WAR explorer

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Restore the complete 1994–2022 Alabama historical performance map and candidate-race display, using the corrected race-residual WAR definition and a post-2016 Southern structural model to evaluate pre-2016 elections.
- Non-goals: Do not pool WAR by candidate, use finance in WAR, replace exact 2018/2022 Alabama WAR, infer scores for uncontested races, or use finance/provider committee names as candidate display names.
- Upstream snapshot: Southern residual run `WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`; Alabama WAR run `AL-WAR-V1-E1F8E11BF2853322239F`; validated 1994–2022 Alabama CMO race and map inputs.
- Read scope: Strict post-2016 Southern WAR training mart; selected v3 structural specification; Alabama historical race, ticket, incumbency, presidential-context, candidate identity, map, and office-baseline products; current and former WAR page builders.
- Write scope: `scripts/build_alabama_historical_war_v1.py`; `scripts/build_war_story_page.py`; focused tests; `data/processed/war/alabama_historical_war_v1/`; WAR methodology/audit documents; generated `docs/` and `artifacts/site/` WAR pages and publication data; this contract.
- Warehouse mode: `read-only`
- Join contracts: Historical race-to-context is `1:1` on cycle/chamber/district; race-to-candidate is `1:2`; published modern Alabama WAR override is `1:1`; candidate display identity is `1:1` on canonical election candidate ID. Duplicate keys fail.
- Acceptance checks: All 509 contested D–R races and 1,018 candidate-cycle orientations from 1994–2022 are present; 1994–2014 use the post-2016 modern-model backcast; 2018/2022 exactly equal published Alabama WAR; candidate signs are exact opposites; finance and pooled candidate effects are absent; committee-like finance identities cannot enter display names; every historical cycle/chamber map is restored; tests and publication consistency pass.
- Handoff recipient: `validation_release`
- Known risks: Backcasting a modern relationship before its training era is extrapolation; missing validated prior-presidential context uses the model's documented zero-valued lag encoding while remaining explicitly labeled; historical ticket allocation and map vintages carry source uncertainty.
- Completion evidence: Historical run `AL-HIST-WAR-V1-2CD9D5044B91015A3749`; 509 race rows; 1,018 candidate-cycle rows; all 16 cycle/chamber map sections restored; exact 2018/2022 published residual override; zero committee-like display names; 65 focused release tests passed; broad suite 608 passed with only the pre-existing canonical-finance fixture count mismatch (352 expected versus 353 current).
