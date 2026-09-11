# Forecast roster universe and seat treatment — 2026-09-11

Internal execution evidence for checklist items `forecast-02` (certify the dated candidate roster and election universe) and `forecast-10` (clarify independent and single-major-party seat treatment).

This is a **read-only audit**. No data, model, warehouse, checklist or published export was modified. Machine-readable companion: `FORECAST_ROSTER_UNIVERSE_2026_09_11.json` in this directory.

- Roster: `data/processed/war/2026_final_candidate_roster.csv` SHA256 `d9ee34c1b7b37096503d5eebbea07cfc24cc2df0f9da3ffde9ef41def710388c`
- Audit script SHA256 `ed1e8fd7c8c9b816b7a4dfd70faab2e4219bd2d0566e775dde42f14a92d57c19`; generated 2026-09-11T22:01:12.371027+00:00 (0.22 s) at commit `d93dd8c63f9866cb9c93a74d11883d3fd3acc043`
- Forecast build `b76d607f2d81e54697a3` (manifest generated 2026-09-11T21:08:27.543428+00:00); final roster is a declared manifest input: True (hash match True)
- Commands: `.venv/Scripts/python.exe scripts/audit_forecast_roster_universe.py` and `.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_forecast_roster_universe.py -q`

## 1. The 140-seat partition

The 140 enumerated seats (House 105, Senate 35) partition into 48 modeled D-versus-R, 26 Democratic-only, 66 Republican-only, 0 independent-or-third-party-only, 0 no-candidate and 0 unresolved seats. Classes are exhaustive and mutually exclusive by construction: `modeled_d_r` requires exactly one Democratic and one Republican nominee (the `prospective_features` eligibility rule); a seat with both parties represented but more than one nominee in a party is `unresolved`.

| Chamber | Modeled D–R | D only | R only | Independent only | No candidate | Unresolved | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| house | 33 | 20 | 52 | 0 | 0 | 0 | 105 |
| senate | 15 | 6 | 14 | 0 | 0 | 0 | 35 |

Modeled reconciliation: classified 48, `prospective_features`-eligible 48, expected 48 (difference 0); classified and eligible sets equal: True. Each published scenario carries [48] races and the three scenario key sets are identical: True. Published `*_modeled_seats.csv` holds the headline distribution {'house': 9, 'senate': 6} rows by chamber with probability sums {'house': 1.0, 'senate': 1.0}. Ambiguous (unresolved) seats: none.

## 2. Roster source, as-of dates and per-row provenance

The final roster has 189 nominee rows: 168 OCR rows from the two official party certifications and 21 human-reviewed override rows. Every row is a **general-election nominee** (`election_stage_counts` {'general_nominee': 189}); the nomination path distinguishes certified nominee, primary-runoff winner, post-map-reversion special primary, conditional-certification replacement and independent reclassification ({'certified_party_nominee': 168, 'alias_confirmed_same_person': 9, 'primary_runoff_winner_certified': 4, 'certification_omission_retained': 1, 'ocr_name_corrected': 1, 'added_from_certification': 1, 'independent_reclassified': 1, 'misclassified_independent_corrected': 1, 'post_map_reversion_special_primary': 2, 'conditional_certification_replaced': 1}).

- Roster as-of: nomination effective after 2026-08-11 (primary runoff); source retrieval ['2026-08-14T23:24:09.224645+00:00', '2026-08-14T23:27:18.400601+00:00', '2026-08-14T23:47:01.425187+00:00', '2026-08-14T23:47:08.588485+00:00']; certification document date established: False.
- Certification document date: The scanned party-certification PDFs carry no recorded issuance date or acquisition manifest in the repository; only the filesystem retrieval timestamp is available.
- Nomination effective after: 2026-08-11 — The reconciliation row for senate 26 D reads 'Tabitha Isner (subject to August 11 Primary)*' and the runoff-certificate rows supersede earlier certification, so the roster is effective after the 2026-08-11 primary runoff.
- Roster source manifest recorded: False — No manifest under data/raw/candidates/ or data/processed/war/*roster*manifest* records the certification PDF URLs, retrieval times, hashes or terms. The forecast manifest declares the final roster as an input hash only.

Every roster row's per-source, per-row provenance record (source file, retrieval proxy, election stage, nomination path, prior-cycle identity, incumbency flag and source, plan membership) is carried verbatim in the JSON companion under `roster_rows`.

| Source | Role | Bytes | Filesystem mtime (UTC) | SHA256 |
| --- | --- | --- | --- | --- |
| data/processed/war/2026_final_candidate_roster.csv | roster | 30829 | 2026-08-20T18:22:33.109023+00:00 | d9ee34c1b7b37096503d5eebbea07cfc24cc2df0f9da3ffde9ef41def710388c |
| data/processed/war/2026_certified_candidate_roster.csv | roster | 31295 | 2026-08-15T00:31:08.004233+00:00 | 15dde6350d8e58df86ee5da73cc774744c64e0dd445d41f261293871f5555d41 |
| data/processed/war/2026_candidate_roster_provisional.csv | roster | 22897 | 2026-08-15T01:19:16.176509+00:00 | 269336d6f0f34dd536c321fb3afac938d3a51cbe4732aff8f78e9b38412e233e |
| data/processed/war/2026_certified_roster_ocr_raw.csv | roster | 15075 | 2026-08-15T00:31:07.994653+00:00 | fe30b3964c2b9d091118c831e934e24e7f3f4e8ff10f4f956720e6bc7a22acbd |
| data/processed/war/2026_certified_roster_reconciliation.csv | roster | 38258 | 2026-08-15T00:31:08.013490+00:00 | 5dde1df15fa4f5ccca275d8d9b70eb88bfcf1b5e8322221839c863efef8508ce |
| data/processed/war/2026_roster_manual_overrides.csv | roster | 4031 | 2026-08-20T18:22:26.459928+00:00 | 171c939787a1aa9a6b6a64e5c21fe5594f7872bbc5db9374bc74fdd4192c7eff |
| data/processed/war/2026_roster_override_application.csv | roster | 1577 | 2026-08-21T15:21:36.503566+00:00 | 30af256cb1696bb74dc0f0e29789dcaa753051b4adcf7eb0f8b69b08b2f40e3c |
| data/processed/war/2026_candidate_incumbency.csv | incumbency | 27733 | 2026-09-08T13:44:23.638573+00:00 | 9aae05a0e0ae8998754dc1ecbcdbae7da925f560f375f9eb32337d1c95cbc3c9 |
| data/processed/war/2026_race_incumbency.csv | incumbency | 5747 | 2026-09-08T13:44:23.645962+00:00 | b155abdb1c8405fa2332aab7812034394f486d5785691fe0805b2814f1441cbe |
| data/processed/war/2026_incumbency_review.csv | incumbency | 9714 | 2026-09-08T13:44:23.639407+00:00 | 85c7b7f3705582c41679e789b2848169db243193ad638f2ee62e2dfaf2f2fd63 |
| data/processed/war/2026_geography_source_manifest.csv | plan | 3050 | 2026-08-16T15:21:38.991866+00:00 | 87674816c916860a4fca1492c22b2b3834ba8cc46c5f7c723db119da2e060893 |
| data/processed/war/2026_geographic_crosswalk_qa.csv | plan | 89 | 2026-08-14T23:54:21.789125+00:00 | 95b73464c3693e75d07d02cf3da0d4d1f25ca05a756cc7dda552469b4d451697 |
| data/processed/forecast_calibration/alabama_war_forecast_v1_2026_scenarios.csv | forecast | 82125 | 2026-09-11T21:08:27.540921+00:00 | c0e33afcc26ff7de4c7acadb7456d2618e0318dc2aec79a0b6aa5d7146b5abb1 |
| data/processed/forecast_calibration/alabama_war_forecast_v1_2026_modeled_seats.csv | forecast | 392 | 2026-09-11T21:08:27.542428+00:00 | 03268141964abda597629c09af0501d0d975648adaa46e0201a3c89ce9581302 |
| data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json | forecast | 6158 | 2026-09-11T21:08:27.651354+00:00 | 6760a36d24fa851956d0c9eea4f5d3e7b365bc6f728a6bc9f48ba5359a54536c |
| data/raw/alabama_elections_and_geography/CertificationofDemocraticPartyCandidates-2026General.pdf | roster_source | 253447 | 2026-08-14T23:47:01.425187+00:00 | 0b036924d151fd3637914f518ee2e7f9f92c7679271b1300f0917208fb3040fc |
| data/raw/alabama_elections_and_geography/CertificationofRepublicanPartyCandidates-2026General.pdf | roster_source | 663215 | 2026-08-14T23:47:08.588485+00:00 | 2c4840a95fdab480aebf8aa59e5f13b97c366eba3646de4e4acb52b9d3149292 |
| data/raw/alabama_elections_and_geography/2026 Alabama House of Representatives election - Wikipedia.html | roster_source | 2622391 | 2026-08-14T23:24:09.224645+00:00 | 497e035eac2f4386d3ae406fc5a82371f532702f6a8f2779dae1a9610e98ee02 |
| data/raw/alabama_elections_and_geography/2026 Alabama Senate election - Wikipedia.html | roster_source | 1438158 | 2026-08-14T23:27:18.400601+00:00 | 9190e967e2a740c22a2202615eb37edd6dd070150047e92e50d606ec9df80742 |
| data/raw/alabama_elections_and_geography/tl_2025_01_sldl/tl_2025_01_sldl.dbf | plan_house | 20190 | 2026-08-14T23:44:06.713277+00:00 | d1b77402334cb1a1f0faa30240085ffce4213fbeed2b1096e9d9b127b6c10b65 |
| data/raw/alabama_elections_and_geography/tl_2025_01_sldu/tl_2025_01_sldu.dbf | plan_senate | 7030 | 2026-08-14T23:44:14.849806+00:00 | 1fab9ba4d9b77d45aae7ba4520e6509559c28a4abb1052f000ab145cf4ea534d |

Join and coverage checks: incumbency rows resolve 189/189 roster rows 1:1; 121 nominees carry `incumbent=true`. Prior-cycle identity is resolved for 112 rows (108 via the verified 2022 winner crosswalk and 68 via a same-district canonical prior-cycle name; the two channels overlap where an incumbent also ran in an earlier covered cycle) and is unresolved for 77 rows. Rows on the 2026 plan: 189/189; off-plan seat keys: none.

Plan evidence: dashboard maps read `data/raw/alabama_elections_and_geography/tl_2025_01_sldl/tl_2025_01_sldl.shp` and `data/raw/alabama_elections_and_geography/tl_2025_01_sldu/tl_2025_01_sldu.shp`; their dBASE district codes are {'house': 105, 'senate': 35} and contiguous: {'house': True, 'senate': True}. Declared geometry vintage: {'house': {'applicable_cycle': 2026, 'legislative_session_year': 2024, 'selection_basis': 'user_supplied_reinstated_original_2021_plan', 'sha256': 'f2840e15bca51803af064448c05fd719cc6565e36475729dfc1c92da73238333', 'sha256_matches_disk': True}, 'senate': {'applicable_cycle': 2026, 'legislative_session_year': 2024, 'selection_basis': 'user_supplied_reinstated_original_2021_plan', 'sha256': 'fbc4422076d5a119d51d5e1846d56d4e5b95d91d451cf5b54299a6a6093012b8', 'sha256_matches_disk': True}}. `prospective_features` does not read geometry: it joins roster eligibility to `2026_poll_adjusted_baseline.csv` (140 seat keys), so the modeled universe is the baseline's 2026-plan seat list. Roster seat keys equal the plan: True; equal the baseline: True.

## 3. Withdrawals, replacements and additions

Version sizes: provisional 181 rows / 180 seat keys, certified 185 rows, final 189 rows. Change counts: {'name_normalized': 7, 'provisional_nominee_differs_from_certified': 34, 'certified_only_not_in_provisional': 6, 'added_after_certification': 4, 'name_changed_same_surname': 1, 'provisional_nominee_materially_differs_from_certified': 1, 'replaced': 1}. Reconciliation review flags: 18 of 187 rows.

Roster-version key collisions (one seat key with two nominees in one source) — provisional: [{'chamber': 'senate', 'district': 10, 'party': 'R', 'candidates': ['Andrew Jones', 'Jesse Battles']}]; certified: none. The provisional snapshot listed both Andrew Jones and Jesse Battles as Republicans in Senate District 10; the certification resolved Jones as the Republican nominee and the human override recorded Battles as an independent. Every row of that seat remains visible here rather than being silently merged.

Changes that alter the nominee, the seat's party set or the source coverage:

| Chamber | District | Party | Provisional | Certified | Final | Change | Resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| house | 17 | R | unknown | Phil Segraves | Phil Segraves | certified_only_not_in_provisional | certification_add_runoff_winner |
| house | 37 | R | unknown | Jeff Monroe | Jeff Monroe | certified_only_not_in_provisional | certification_add_runoff_winner |
| house | 51 | R | Allen Treadaway | unknown | Allen Treadaway | added_after_certification | retain_wikipedia_certification_omission |
| house | 52 | D | unknown | GiGi Hayes | GiGi Hayes | certified_only_not_in_provisional | certification_add_runoff_winner |
| house | 70 | R | Ian Chwatuk | lan M. Chwatuk | Ian M. Chwatuk | name_changed_same_surname + provisional_nominee_differs_from_certified | ocr_correction_certified_name |
| house | 82 | D | unknown | Pebblin W. Warren | Pebblin W. Warren | certified_only_not_in_provisional | certification_add_runoff_winner |
| house | 95 | R | unknown | FrancesHolk-Jones | Frances Holk-Jones | name_normalized + certified_only_not_in_provisional | certification_add |
| senate | 10 | I | unknown | unknown | Jesse Battles | added_after_certification | reclassify_independent |
| senate | 10 | R | Jesse Battles | Andrew Jones | Andrew Jones | provisional_nominee_materially_differs_from_certified | certified_replaces_misclassified_independent |
| senate | 25 | D | unknown | unknown | Phadra Carson Foster | added_after_certification | post_map_reversion_special_primary_certification |
| senate | 25 | R | unknown | unknown | Will Barfoot | added_after_certification | post_map_reversion_special_primary_certification |
| senate | 26 | D | unknown | Tabitha Isner (subject to August 11 Primary)* | Kirk Hatcher | replaced + certified_only_not_in_provisional | replace_conditional_certification |

Identical-person name variants (punctuation, spacing, added initials or a fuller legal name) are evidence of alias normalisation, not of a nominee change:

| Chamber | District | Party | Provisional | Certified | Final | Change |
| --- | --- | --- | --- | --- | --- | --- |
| house | 3 | R | Kerry Underwood | KerryBubba Underwood | Kerry Bubba Underwood | name_normalized + provisional_nominee_differs_from_certified |
| house | 4 | R | Parker Moore | ParkerDuncanMoore | Parker Duncan Moore | name_normalized + provisional_nominee_differs_from_certified |
| house | 5 | R | Danny Crawford | Danny F. Crawford | Danny F. Crawford | provisional_nominee_differs_from_certified |
| house | 14 | R | Tim Wadsworth | Tim R.Wadsworth | Tim R.Wadsworth | provisional_nominee_differs_from_certified |
| house | 25 | D | Allison Montgomery | Allison T Montgomery | Allison T Montgomery | provisional_nominee_differs_from_certified |
| house | 25 | R | Phillip Rigsby | Phillip K. Rigsby | Phillip K. Rigsby | provisional_nominee_differs_from_certified |
| house | 28 | D | Robert Hunter | Robert Louis Hunter | Robert Louis Hunter | provisional_nominee_differs_from_certified |
| house | 28 | R | Mack Butler | Mack N Butler | Mack N Butler | provisional_nominee_differs_from_certified |
| house | 29 | R | Mark Gidley | Mark A. Gidley | Mark A. Gidley | provisional_nominee_differs_from_certified |
| house | 31 | R | Troy Stubbs | Troy B.Stubbs | Troy B.Stubbs | provisional_nominee_differs_from_certified |
| house | 32 | D | Debra Foster | Debra D Foster | Debra D Foster | provisional_nominee_differs_from_certified |
| house | 41 | D | David Morgan | David J.A. Morgan | David J. A. Morgan | name_normalized + provisional_nominee_differs_from_certified |
| house | 42 | R | Ivan Smith | Van Smith | Van Smith | provisional_nominee_differs_from_certified |
| house | 46 | R | David Faulkner | David L. Faulkner | David L. Faulkner | provisional_nominee_differs_from_certified |
| house | 56 | D | Ontario Tillman | Ontario J Tillman | Ontario J Tillman | provisional_nominee_differs_from_certified |
| house | 68 | D | Thomas Jackson | Thomas E "Action" Jackson | Thomas E. Action Jackson | name_normalized + provisional_nominee_differs_from_certified |
| house | 69 | D | Kelvin Lawrence | Kelvin J Lawrence | Kelvin J Lawrence | provisional_nominee_differs_from_certified |
| house | 70 | D | Christopher J. England | Christopher John England | Christopher John England | provisional_nominee_differs_from_certified |
| house | 71 | D | Artis J. McCampbell | Artis "A.J." McCampbell  | Artis "A.J." McCampbell  | provisional_nominee_differs_from_certified |
| house | 72 | D | Curtis Travis | Curtis L Travis | Curtis L Travis | provisional_nominee_differs_from_certified |
| house | 75 | D | Tisha Nickson | Tisha Dickson Nickson | Tisha Dickson Nickson | provisional_nominee_differs_from_certified |
| house | 76 | D | Patrice McClammy | Patrice "Penni” McClammy | Patrice Penni McClammy | name_normalized + provisional_nominee_differs_from_certified |
| house | 78 | D | Kenyatté Hassell | Kenyatte Hassell | Kenyatte Hassell | provisional_nominee_differs_from_certified |
| house | 83 | D | Jeremy Gray | Jeremy A. Gray | Jeremy A. Gray | provisional_nominee_differs_from_certified |
| house | 85 | D | Aristotle Kirkland | Aristotle Onassis Kirkland | Aristotle Onassis Kirkland | provisional_nominee_differs_from_certified |
| house | 89 | R | Marcus Paramore | MarcusB.Paramore | MarcusB.Paramore | provisional_nominee_differs_from_certified |
| house | 97 | D | Adline Clarke | Adline C. Clarke | Adline C. Clarke | provisional_nominee_differs_from_certified |
| senate | 11 | D | Donald Mottern | Donald J. Mottern | Donald J. Mottern | provisional_nominee_differs_from_certified |
| senate | 16 | R | Jabo Waggoner | J.T."Jabo"Waggoner | J.T."Jabo"Waggoner | provisional_nominee_differs_from_certified |
| senate | 18 | D | Rodger Smitherman | Rodger M. Smitherman  | Rodger M. Smitherman  | provisional_nominee_differs_from_certified |
| senate | 22 | R | Terry Waters | Terry L. Waters | Terry L. Waters | provisional_nominee_differs_from_certified |
| senate | 23 | R | Thayer Spencer | Thayer“Bear"Havard Spencer | Thayer Bear Havard Spencer | name_normalized + provisional_nominee_differs_from_certified |
| senate | 30 | R | Clyde Chambliss | Clyde Chambliss, Jr. | Clyde Chambliss, Jr. | provisional_nominee_differs_from_certified |

Substantive replacements are distinct from alias normalisation: `name_normalized` rows differ only by punctuation, spacing or a fuller legal name; `name_changed_same_surname` rows keep the same surname (for example the OCR correction of a single letter); `replaced` rows change the surname and therefore the person. Candidates that appear only in the provisional Wikipedia snapshot or only in the certification are flagged rather than silently merged; the `certified_only_not_in_provisional` row for senate 26 D carries the conditional certification text that the human override later replaced with the runoff nominee.

## 4. Seat-treatment policy and contract agreement

A seat is fixed in the chamber summaries when exactly one major party nominated a candidate and the other major party nominated none, regardless of independent or third-party candidates in that race. Districts with both major parties nominated are modeled as generic D-versus-R races in which independent candidates are not modeled. Districts with no D and no R nominee (independent-only, third-party-only, or no candidate) receive no margin or probability and stay visible as unmodeled.

Implementation evidence (substring present in the shipped sources/pages):

| Check | Present |
| --- | --- |
| fixed_dem_from_roster | True |
| modeled_seats_plus_fixed | True |
| single_major_party_status | True |
| unmodeled_status | True |
| unresolved_visibility | True |
| independent_not_modeled_copy | True |
| index_caveat_present | True |
| methodology_fixed_totals_present | True |
| index_independent_not_modeled_copy_present | True |
| artifact_independent_copy_present | True |

Field contract check: terms found ['major-party nominee', 'single-major-party', 'unmodeled']; states a single-major-party seat policy: True. Agreement result: **page_and_implementation_agree_contract_states_policy**.

Interpretation: the published forecast page and methodology page state the fixed-seat and independent treatment, and the shipped classifier, seat totals and rendered statuses match that statement; the field contract (declared as an input by the forecast manifest) does not describe seat treatment at all. The behaviour is therefore documented on the public pages but not pinned by the machine-readable contract, so a future change to the fixed-seat rule would not be caught by a contract test. Adding the rule to the contract is outside this audit's write scope and is recorded here as the remaining `forecast-10` evidence gap.

### Fixed-seat offset test

Recomputed from the roster: fixed Democratic seats {'house': 20, 'senate': 6}, fixed Republican seats {'house': 52, 'senate': 14}. Payload offset per chamber and model (published minimum Democratic seats minus the modeled minimum, where the scenario distributions start from zero modeled wins): {'house:headline': 20, 'house:environment_dem_favorable': 20, 'house:environment_rep_favorable': 20, 'senate:headline': 6, 'senate:environment_dem_favorable': 6, 'senate:environment_rep_favorable': 6}. Payload offset equals the roster-derived fixed Democratic count: True; headline distribution equals the published `*_modeled_seats.csv` support and probabilities: {'house': True, 'senate': True}. Unmodeled races in the rendered payload: {'house': 0, 'senate': 0}. Every seat's rendered status equals the class-implied status (modeled / unopposed-major-party / unmodeled): True; mismatches: none.

### Independent-candidate seats

| Chamber | District | Class | Other parties | Payload status | Payload D probability | Payload candidates |
| --- | --- | --- | --- | --- | --- | --- |
| senate | 10 | single_major_party_r | I | unopposed-major-party | 0.000 | [('Andrew Jones', 'R'), ('Jesse Battles', 'I')] |

Every independent-bearing seat that also has a major-party nominee is fixed in the chamber summaries with a 0.0 or 1.0 probability: True. Independent-only seats (no major-party nominee) stay `unmodeled` with a null probability and are counted in the published `unmodeled` statistic, so the seat is visible rather than silently assigned (independent-only check on the current roster: None; `None` means no independent-only seat exists, so that path is exercised only by the fixture tests).

## 5. Not established and limitations

- Absence of a prior-cycle identity match is not evidence that a candidate has no prior candidacy; the local identity products cover only selected cycles and the 2022 canonical names are anonymised codes.
- The party-certification PDFs are scanned images with no repository manifest, so their issuance date, source URL, license and recorded retrieval time are not established; the filesystem timestamp is used only as a retrieval proxy.
- Chamber seat distributions are the published headline simulation output; the audit verifies their fixed-seat offset, not the underlying simulation draws.
- The published page and methodology text are read as shipped; the field contract is checked for a seat-treatment statement rather than rewritten by this audit.

Reproduction: `scripts/run_alabama_war_generic_forecast.prospective_features()` pivots the final roster on `(chamber, district)` and `party` with `nunique` candidate counts and keeps `D == 1 and R == 1`; `scripts/build_2026_forecast_dashboard.build_payload()` fixes the chamber offset with `fixed_dem = len(D districts - R districts)`, labels every other seat `unopposed-major-party` or `unmodeled`, and `dashboard/forecast_dashboard.js::seatStats()` reports `unknown` as the count of races with a null probability.
