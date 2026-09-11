# MEDSL Southern gap acquisition

10 individual-state files were acquired from MEDSL's official GitHub repositories. Source ZIP bytes are preserved unchanged under `data/raw/historical_statewide_elections/medsl_github/`.

| State | Year | Required offices verified | Rows | Local file | SHA-256 |
| --- | ---: | --- | ---: | --- | --- |
| KY | 2016 | STATE HOUSE, STATE SENATE, US PRESIDENT | 97,714 | `data/raw/historical_statewide_elections/medsl_github/2016/2016-ky-precinct.zip` | `3589caab54bee885809e8f6d178c68e5bcc965b58563904baad3c152de2d6c6a` |
| KY | 2022 | STATE HOUSE, STATE SENATE, US SENATE | 197,236 | `data/raw/historical_statewide_elections/medsl_github/2022/2022-ky-local-precinct-general.zip` | `af2e2ad9ee83268f3ccd22f6d3ad4e93db297dc80324750df66bd268d085a36d` |
| MO | 2022 | STATE HOUSE, STATE SENATE, US SENATE | 111,742 | `data/raw/historical_statewide_elections/medsl_github/2022/2022-mo-local-precinct-general.zip` | `f44de8fd7d2a11bfc0eed71b13ea7359bededd15174d71d48e85819c60f281e0` |
| OK | 2022 | STATE HOUSE, STATE SENATE, GOVERNOR | 319,389 | `data/raw/historical_statewide_elections/medsl_github/2022/2022-ok-local-precinct-general.zip` | `9526b85ec712c66e50ce039564166a0f34c39933f563cb20d949bba1d44ce7d9` |
| SC | 2022 | STATE HOUSE, GOVERNOR | 543,298 | `data/raw/historical_statewide_elections/medsl_github/2022/2022-sc-local-precinct-general.zip` | `3f0ca616aa8768cd1126d8f372bab13161973c8c2af0eb466380d40175687a19` |
| AR | 2024 | STATE HOUSE, STATE SENATE, US PRESIDENT | 214,708 | `data/raw/historical_statewide_elections/medsl_github/2024/ar24.zip` | `22b54a19a514588c6f8b23f4975464baf659d6a22d469ba3b6b369461b9dce06` |
| KY | 2024 | STATE HOUSE, STATE SENATE, US PRESIDENT | 113,536 | `data/raw/historical_statewide_elections/medsl_github/2024/ky24.zip` | `6d23baa797cb794aa05e842558fc2b78314f4fef39ab9aafd9822833f73cefa9` |
| OK | 2024 | STATE HOUSE, STATE SENATE, US PRESIDENT | 325,196 | `data/raw/historical_statewide_elections/medsl_github/2024/ok24.zip` | `8ff2595d40fc86748ab4e8f908276c0dc12adc06f58e9ad261859998e7c7588b` |
| SC | 2024 | STATE HOUSE, STATE SENATE, US PRESIDENT | 338,046 | `data/raw/historical_statewide_elections/medsl_github/2024/sc24.zip` | `0a55d286d4a1034b801e27e7ca120c67cd98aa93b31510878da58a00866af599` |
| TN | 2024 | STATE HOUSE, STATE SENATE, US PRESIDENT | 34,865 | `data/raw/historical_statewide_elections/medsl_github/2024/tn24.zip` | `363f8de018de7afa39843c4e09ad3f661966323a7286911f3852dc1a2706e2ca` |

Each ZIP passed archive integrity checks, contained the expected standardized CSV schema, included every required legislative/ticket office, and contained both major parties for the selected ticket office. GitHub blob identifiers and retrieval timestamps are retained in `manifest.csv`.

These files are source evidence only. They are not considered integrated until a downstream normalization task reconciles precinct identifiers, aggregates ticket votes into legislative districts, validates statewide totals, and publishes an approved analytical mart.
