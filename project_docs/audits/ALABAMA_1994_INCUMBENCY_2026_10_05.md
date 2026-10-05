# 1994 incumbency into historical WAR: Wikipedia research, adjudications and rebuild

Task contract: `coordination/ALABAMA-1994-INCUMBENCY-20261005.md`.

- **Owner instruction (2026-10-05):** "Fix the older problems" and "research on wikipedia with the mcp server who the incumbents for 1994 would be".
- **Status:** applied locally. Independent review is pending, and nothing has been published.

## 1. Defects found

1. **No 1994 incumbency reached WAR.**
   - In `scripts/build_canonical_cmo_features.py`, the 1994 block selected rows with `demographics_method.notna()`.
   - The merge stores the 1994 context's method under the suffixed name `demographics_method_historical`, so that mask was always empty.
   - The 1994 context incumbency was therefore never applied: every 1994 race had `incumbency_balance = 0`.
   - The 1998–2006 block already handled the suffix. The 1994 block now mirrors it: it tests the suffixed column, copies the method into `demographics_method`, and drops the suffixed column.
2. **Candidate-level incumbency labels were blank before 2010.**
   - Historical WAR's candidate rows took `incumbent` from the canonical candidate flag, which is populated only from 2010.
   - Every 1994–2006 candidate was therefore labelled a non-incumbent, even though the backcast used race-level incumbency in those cycles (1998–2006 before this task; 1994 after it).
   - `build_alabama_historical_war_v1.build_candidate_rows()` now sets each candidate's flag from the race-level flags the backcast uses.
   - Where both sources exist (2010–2022) they agree exactly, and the build refuses any canonical incumbent that the race context does not confirm.
   - Race WAR is byte-identical. Only the candidate labels change. Incumbents per cycle, 1994 / 1998 / 2002 / 2006, went from 0 / 0 / 0 / 0 to 44 / 71 / 60 / 56.
3. **The 1994 surname matcher's incumbency was incomplete.**
   - It made one false match (HD75 Holley).
   - It missed about 18 incumbents with non-unique surnames, plus every 1991–94 special-election winner.

## 2. Wikipedia research (owner-directed)

### Coverage

- A research agent used the Wikipedia MCP server to examine all 206 candidates in 1994 `canonical_candidates`. Its sources were:
  - all 35 Senate district "District officeholders" lists;
  - 72 legislator biographies.
- **Snapshots:** 115 JSON files and a manifest are under `data/raw/wikipedia/alabama_1994_incumbency/`. The manifest records title, URL, page ID, article timestamp, retrieval time, sha256 and license (CC BY-SA 4.0).
  - `data/raw/**` is git-ignored, so the snapshots are not tracked.
- **Evidence tables:**
  - `data/manual/elections/alabama_1994_incumbency_wikipedia_evidence.csv`: 206 rows, with Wikipedia, matcher and Klarner values, the quoted evidence and a proposal.
  - `data/manual/elections/alabama_1994_incumbency_disagreements.csv`: 30 rows.

### Results

| Incumbent = true | All 206 | D-vs-R (132) |
|---|---|---|
| Wikipedia | 64 (87 unknown) | 30 (61 unknown) |
| Matcher | 73 | 36 |
| Klarner | 90 (12 missing) | 42 |
| **Adopted** | **96** (1 unknown) | **44** |

Pairwise agreement where both values are known:

| Pair | Agreement |
|---|---|
| Wikipedia vs Klarner | 95.3% |
| Wikipedia vs matcher | 88.2% |
| Matcher vs Klarner | 90.2% |

### Limits

- **House coverage.** House district articles' officeholder tables are not returned by the tool, so House evidence rests on biographies. 87 House candidates have no usable Wikipedia evidence, and where Wikipedia is silent the adopted value is the agreeing matcher and Klarner value. That value can still hide a special-election entrant.
- **How the snapshots were saved.** They were transcribed by the agent's Write tool, not saved byte-for-byte from the server; the classifier blocked a scripted capture.
  - Every quoted string was verified verbatim.
  - Two snapshots with link-field transcription errors are flagged `DEFECTIVE_TRANSCRIPTION_DO_NOT_USE` and have verified re-captures.
- **Senate list gaps.** The Senate officeholder lists omit at least one special election (SD20). Senate "false" values that rest only on a candidate's absence from a list are therefore medium-high confidence.

## 3. Adjudications

`data/manual/elections/alabama_1994_incumbency_adjudications.csv` now holds 26 records: the existing SD31 Ellis record plus 25 new ones. Each new record carries:

- a stable ID;
- the matcher's paired 1990 winner (empty when there is none);
- the decision and its evidence: the Wikipedia quote, Klarner's value, the prior seat and the snapshot manifest;
- the rationale and confidence;
- `reviewer_status = owner-approved method 2026-10-05 (owner directed that 1994 incumbency follow Wikipedia research); record compiled by a research agent, not individually reviewed`.

`build_1994_context_features.incumbency()` applies the records through the existing stale-checked override.

### Changes from the matcher

- **Changed to incumbent:**
  - HD3 Black, HD9 Parker, HD19 Hall, HD22 Hall, HD29 Page, HD33 Johnson, HD40 Knight, HD42 Smith, HD51 Rogers, HD52 Rogers, HD53 Newton, HD55 Minnifield, HD60 Hilliard, HD63 Parker, HD69 Thomas, HD71 Black, HD77 Knight, HD84 Clark, HD90 Newton, HD98 Clark, HD99 Buskey, HD105 Harper.
  - SD20 Escott-Russell.
  - SD32 Lipscomb (ballot spelling "Lipsocomb").
  - The six special-election winners in this list (HD19, HD29, HD55, HD60, HD77 and SD20) are documented only by Wikipedia.
- **Changed to not an incumbent:** HD75 Holley.
  - The matched 1990 winner, Jimmy Holley, is a Coffee County member.
  - The 1994 HD75 seat was held by Claud Walker.
  - Klarner also shows no incumbent.
- **Review queue:** HD10 Haney stays at the matcher's 0 and is listed as `unknown`.
  - A 1991 HD10 vacancy is documented, but not who filled it.
  - The incumbency override and the warehouse schema hold only 0 or 1, so the 0 is a matcher value, not evidence.
  - HD10 is uncontested and outside the WAR universe.

Incumbents: 73 → 96 candidates. District flags are now 74 D and 22 R.

## 4. Rebuild (foreground, 1994-scoped)

1. `build_1994_context_features.py`: only `dem_incumbent` (23 districts) and `rep_incumbent` (2 districts) changed. Presidential and demographic inputs are identical.
2. `build_canonical_cmo_features.py`:
   - 1994 now carries 74 D and 22 R incumbency flags.
   - Rows outside 1994 are identical on shared columns. The redundant `demographics_method_historical` column is gone; the WAR page falls back to it only when `demographics_method` is empty.
3. `rebuild_cmo_candidate_quality_v5.py` and `build_alabama_historical_war_v1.py`:
   - Run `AL-HIST-WAR-V1-F9DF2D2E6C12C696A705`.
   - Non-1994 WAR is identical; the maximum difference is 0.
   - 42 of the 66 1994 races now carry incumbency.
   - 1994 WAR moves by up to ±6.16 points, the model's incumbency effect; the mean change is −2.18.
   - The 1994 mean WAR goes from 15.6 to 13.4.
   - The candidate-label fix above was applied in a second build. Race WAR is byte-identical, and the run ID is unchanged because it hashes inputs, not code.
4. Career WAR, the caucus run (`AL-DEM-CAUCUS-V1-DFA0C1C5015D988804CF`, k=2, approved labels, same groups), the caucus page and the WAR page were rebuilt.
5. Forecast:
   - `build_forecast_candidate_history.py` outputs are byte-identical, so the forecast is unaffected.
   - The forecast page passes its input gate.

## 5. Tests

- **Command:** each file run with `-p no:cacheprovider`.
- **Updated test:** `test_1994_context_features` expects 96 incumbents after the research records.
- **Results:** 1 expected failure; every other test passes:

| Test file | Result |
|---|---|
| `test_1994_context_features` | 12 passed |
| `test_1994_cmo_baseline` | 3 passed |
| `test_alabama_historical_war_v1` | 6 passed |
| `test_cmo_candidate_quality_v5` | 7 passed |
| `test_alabama_career_war` | 3 passed |
| `test_democratic_caucus_page` | 10 passed |
| `test_historical_war_story_page` | 7 passed |
| `test_forecast_dashboard` | 24 passed |
| `test_alabama_seats_by_cycle` | 16 passed |
| Repair, adapter and identity tests | all pass |
| `test_published_site_consistency::test_publication_exports_match_current_model_outputs` | expected failure: published `docs/data` lags the rebuilt historical WAR until republication |

## 6. Open items

- **Confirm the Wikipedia-only special-election winners against official records:** HD10 (unknown), HD19, HD29, HD55, HD60, HD77, SD20, and the HD7 Letson identity.
  - The fall-1994 pre-election roster PDF (`data/raw/ideology/alabama_1994_archival_sources/`) marks incumbents with an asterisk and could serve as a cross-check for House candidates.
- **Party labels the research found:**
  - The 1994 workbook prints "L. Hall (R)", but HD19 Hall is a Democrat; the owner already adjudicated HD19 as D.
  - Gerald Allen (HD62) ran as a Democrat in 1994, although his Wikipedia article calls him a Republican.
- **Run IDs.** The historical WAR run ID hashes inputs, not code, so a code-only change keeps the same run ID with different candidate outputs. The manifest's output hashes record the change.
- **Not done:** independent review of the incumbency adjudications and of the rebuilt 1994 WAR; republication.
