# Southern 2024 incumbency staging validation

**Verdict: PASS for gated experimental modeling, with documented identity and succession caveats.**

The review candidate deterministically preserves all eligible 2024 races, reconstructs the staggered Tennessee Senate roster from 2020 winners, keeps ambiguous cases missing, and admits no race with two asserted incumbents. The 323 ready / 12 unresolved split and 246 incumbent-running / 77 inferred-open split reproduce exactly.

## Independent rebuild and tests

I redirected the module-level output directory to an isolated workspace and ran the unchanged implementation:

```powershell
$env:VALIDATION_INC_OUT = "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\southern_incumbency_2024"
@'
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
import build_southern_2024_incumbency as staging
staging.OUT = Path(os.environ["VALIDATION_INC_OUT"]).resolve()
staging.main()
'@ | python -X utf8 -

python -m pytest scripts/tests/test_southern_2024_incumbency.py -q
```

Two isolated rebuilds are deterministic. The temporary manifest SHA-256 remains `75aabf865b592b32f94223ba7538730b4b4c0b7c3c2958dfb90a5b5157525ecf`, and all five CSV outputs byte-match the release candidate. Focused tests pass 5/5. Build ID is `f25c602985ecc584f3ba`.

## Source verification

- The Klarner ZIP contains the declared `208slers_uoa_cand_contest20230810.csv` member.
- The MEDSL ZIP contains the declared `STATE_precinct_general.csv` member.
- The winner roster contains 825 unique normalized person/chamber records: 668 retained from 2022 and 157 from 2020.
- Both raw ZIP hashes and the current recent-panel hash match the manifest.
- The 2024 roster is restricted to regular general-election Democratic and Republican legislative candidates and then to the panel's eligible races.

All 335 eligible 2024 races are present with exactly two major-party candidate rows, for 670 candidates total. Race keys and race-party candidate keys are unique.

## Staggered chambers

The retained roster uses both 2020 and 2022 winner observations. Among candidates classified as incumbents, eight upper-chamber matches use 2020 and 27 use 2022.

Tennessee's ten 2024 Senate races are all model-ready. Its eight incumbent-running seats are matched to the 2020 winners in SD-6, 10, 14, 16, 18, 20, 22, and 28; the other two are inferred open. This confirms that staggered Senate service is not incorrectly limited to 2022 winners.

## Name matching and ambiguity

- Normalization uppercases, removes accents and punctuation, reverses comma-form names, and strips generational suffixes before comparison.
- Full-name exact matching is state/chamber constrained and party-neutral.
- One-token MEDSL names use surname comparison and are restricted to the same party. Among all accepted surname matches, there are zero cross-party assignments.
- District-supported and global fuzzy matches require the declared threshold and separation margin.
- Ten candidates are marked with an `ambiguous_*` method; every one retains missing `incumbent` rather than false.
- Those ambiguous candidates contribute to 12 unresolved races. Each unresolved race retains missing `incumbency_balance`.

One conservative conflict illustrates the intended gate. Texas HD-63 matches Republican Ben Bumgarner as the current incumbent but also links Democratic candidate Michelle Beckley to her 2020 HD-65 service. The race is rejected as conflicting rather than passed with two incumbents. This is safe for modeling, although restricting 2020 lower-chamber winners to sensitivity/review rather than the primary roster would recover this case more precisely.

## Race-level invariants and coverage

The independently reproduced coverage is:

| State/chamber | Races | Ready | Inferred open | Incumbent running |
|---|---:|---:|---:|---:|
| AR lower | 49 | 48 | 7 | 41 |
| AR upper | 5 | 5 | 0 | 5 |
| GA lower | 90 | 88 | 25 | 63 |
| GA upper | 23 | 23 | 9 | 14 |
| TN lower | 60 | 60 | 10 | 50 |
| TN upper | 10 | 10 | 2 | 8 |
| TX lower | 88 | 79 | 22 | 57 |
| TX upper | 10 | 10 | 2 | 8 |

Totals are 323 ready and 12 unresolved. Among ready races, 246 have an incumbent running and 77 have a complete two-party roster with neither candidate matched. Ready balances are limited to `-1`, `0`, and `+1`; no ready race asserts both Democratic and Republican incumbents.

The 77 zero-balance cases are correctly labeled `inferred_open_complete_roster`, not canonical open seats. Nonmatch is therefore distinguishable from authoritative vacancy evidence and remains subject to the special-election sensitivity noted below.

## Party switching

Exactly one accepted match changes party: Mesha K. Mainor in Georgia HD-56. It is supported by a district-constrained full-name fuzzy match (`0.923077`) from Democratic prior winner to Republican current candidate. It is not a surname-only match. No other candidate is labeled a party switch.

## Provenance and limitations

The production manifest is labeled `staging`. All three input hashes and all five output hashes/counts reproduce: 670 candidates, 335 races, ten review rows, eight coverage rows, and 825 winner-roster rows.

Approval is limited to the 323 `incumbency_model_ready` races and experimental model comparison. These records are evidence-bearing staging identities, not canonical people records. Post-2022 special-election succession is not represented, and the use of residual 2020 lower-chamber winners can conservatively create conflicts such as HD-63. Both should be tested as sensitivity cases before any production promotion.
