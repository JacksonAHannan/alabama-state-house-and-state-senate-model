# Candidate Finance Rebuild on FollowTheMoney Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `build_candidate_finance_features.py`'s FCPA-extract +
fuzzy-name-matching candidate-finance pipeline (81.2% match rate) with
FollowTheMoney's Ask Anything API, which gives district assignment directly
via `Office_Sought` and includes losing general-election candidates —
verified live against real Alabama 2022 Senate races during design.

**Architecture:** A one-off fetch script caches raw FollowTheMoney JSON per
election year to `data/raw/followthemoney/` (committed, not re-fetched on
every pipeline run). A build script parses the cached JSON — regex-parsing
`Office_Sought` into `(chamber, district)` and filtering to
`Election_Status` in `{Won-General, Lost-General}` — and pivots directly to
the same `race_finance_features.csv` schema the retired script produced, so
none of the 6 downstream consumers need to change.

**Tech Stack:** Python 3.9, pandas, numpy, requests, pytest.

## Global Constraints

- Match existing code style: `from __future__ import annotations`;
  Path-based I/O anchored at `Path(__file__).resolve().parents[1]` with a
  `--root` CLI override.
- Output column names are fixed and must not change: `dem_candidate_spending`,
  `rep_candidate_spending`, `log_spending_ratio_d_to_r`, `spending_constant`,
  `finance_complete` — these are read by `fit_preliminary_war_model.py`,
  `compare_war_specifications.py`, `assemble_war_features.py`,
  `build_war_review_queue.py`, `audit_cycle_shift.py`, and
  `validate_war_outputs.py`, none of which this plan touches.
- The `+500` log-ratio constant and formula
  (`log((dem + 500) / (rep + 500))`) are preserved exactly from the retired
  script, for continuity with prior WAR fits.
- `race_finance_features.csv` must have unique `(cycle, chamber, district)`
  keys — `assemble_war_features.py` merges onto it with
  `validate="one_to_one"`.
- The FollowTheMoney API key is read from `token.env`
  (`FTM_API_KEY=<key>`), via the exact same read pattern as
  `scripts/download_acs_sld_demographics.py`'s `api_key()` function
  (`CENSUS_API_KEY=`) — read the file, find the matching `KEY=` line, else
  fall back to `os.environ.get(...)`.
- TLS verification (`verify=False`) is disabled **only** inside the fetch
  script's HTTP calls, because FollowTheMoney's certificate is currently
  expired site-wide (confirmed live during design, not a local trust-store
  issue) — scoped narrowly, with a comment explaining why and a note to
  remove it once fixed. No other script in this plan touches the network.
- Every new pure-logic function gets pytest unit tests in `scripts/tests/`
  using synthetic in-memory fixtures — the fetch script's HTTP layer must be
  dependency-injected so its retry/pagination/validation logic is testable
  without a real network call.
- `pytest.ini` already points at `scripts/tests`; no new test config needed.

---

## File Structure

**Create:**
- `token.env` (gitignored, not committed) — holds `FTM_API_KEY=<key>`.
- `scripts/fetch_followthemoney_candidates.py` — one-off fetch/cache script.
- `scripts/tests/test_fetch_followthemoney_candidates.py`
- `scripts/build_followthemoney_finance_features.py` — parse/aggregate script.
- `scripts/tests/test_build_followthemoney_finance_features.py`
- `data/raw/followthemoney/{2010,2014,2018,2022}_al_candidates.json` — fetched, committed raw data.

**Modify:**
- `MODEL_READINESS.md` — "Rebuild and validate" script list (swap
  `build_candidate_finance_features.py` for
  `build_followthemoney_finance_features.py`, note the fetch script is a
  manual/occasional step run separately), and the finance-coverage figure
  in "Current result"/"Remaining work" once the real coverage number is
  known.

**Delete (Task 4, after diff validation only):**
- `scripts/build_candidate_finance_features.py`
- `data/processed/war/finance_candidate_cycle_totals.csv`,
  `candidate_finance_matches.csv`, `candidate_finance_review.csv`,
  `candidate_finance_coverage.csv`

---

### Task 1: Fetch and cache FollowTheMoney candidate records

**Files:**
- Create: `scripts/fetch_followthemoney_candidates.py`
- Create: `scripts/tests/test_fetch_followthemoney_candidates.py`
- Create: `token.env` (not committed — gitignored)
- Create: `data/raw/followthemoney/{2010,2014,2018,2022}_al_candidates.json` (committed)

**Interfaces:**
- Produces: `api_key(root: Path) -> str`,
  `fetch_year(year: int, key: str, max_retries: int = 3, sleep_seconds: float = 2.0, fetch_page: Callable[[int, int, str], dict | None] = _fetch_page_json) -> list[dict]`
  (the `fetch_page` injection point is what makes this testable without a
  real network call — it returns one page's already-parsed JSON dict, or
  `None` to simulate FollowTheMoney's observed empty-response flakiness).

- [ ] **Step 1: Create `token.env`**

Create the file at the repo root (this file is already covered by the
existing `.gitignore` entry `token.env` — verify with `git check-ignore
token.env` after creating it, expect it to print `token.env` confirming
it's ignored):

```text
FTM_API_KEY=801e27a22d7172156e44dd9e50fff8da
```

- [ ] **Step 2: Write the failing tests**

Create `scripts/tests/test_fetch_followthemoney_candidates.py`:

```python
import pytest

from fetch_followthemoney_candidates import api_key, fetch_year


def test_api_key_reads_from_token_env(tmp_path):
    (tmp_path / "token.env").write_text("FTM_API_KEY=abc123\n")
    assert api_key(tmp_path) == "abc123"


def test_api_key_falls_back_to_env_var_when_not_in_file(tmp_path, monkeypatch):
    (tmp_path / "token.env").write_text("OTHER_KEY=xyz\n")
    monkeypatch.setenv("FTM_API_KEY", "from-env")
    assert api_key(tmp_path) == "from-env"


def _page(records, current_page, max_page, total_records):
    return {
        "metaInfo": {"paging": {"currentPage": current_page, "maxPage": max_page,
                                 "totalRecords": str(total_records)}},
        "records": records,
    }


def test_fetch_year_single_page():
    calls = []

    def fake_fetch_page(year, page, key):
        calls.append((year, page, key))
        return _page([{"id": 1}, {"id": 2}], current_page=0, max_page=0, total_records=2)

    records = fetch_year(2022, "k", sleep_seconds=0, fetch_page=fake_fetch_page)

    assert records == [{"id": 1}, {"id": 2}]
    assert calls == [(2022, 0, "k")]


def test_fetch_year_pages_until_max_page():
    pages = {
        0: _page([{"id": 1}], current_page=0, max_page=2, total_records=3),
        1: _page([{"id": 2}], current_page=1, max_page=2, total_records=3),
        2: _page([{"id": 3}], current_page=2, max_page=2, total_records=3),
    }

    def fake_fetch_page(year, page, key):
        return pages[page]

    records = fetch_year(2022, "k", sleep_seconds=0, fetch_page=fake_fetch_page)

    assert [r["id"] for r in records] == [1, 2, 3]


def test_fetch_year_retries_on_empty_response_then_succeeds():
    attempts = {"count": 0}

    def fake_fetch_page(year, page, key):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return None
        return _page([{"id": 1}], current_page=0, max_page=0, total_records=1)

    records = fetch_year(2022, "k", max_retries=3, sleep_seconds=0, fetch_page=fake_fetch_page)

    assert records == [{"id": 1}]
    assert attempts["count"] == 3


def test_fetch_year_raises_after_exhausting_retries():
    def fake_fetch_page(year, page, key):
        return None

    with pytest.raises(RuntimeError, match="empty response"):
        fetch_year(2022, "k", max_retries=2, sleep_seconds=0, fetch_page=fake_fetch_page)


def test_fetch_year_raises_on_record_count_mismatch():
    def fake_fetch_page(year, page, key):
        return _page([{"id": 1}], current_page=0, max_page=0, total_records=5)

    with pytest.raises(RuntimeError, match="expected 5"):
        fetch_year(2022, "k", sleep_seconds=0, fetch_page=fake_fetch_page)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest scripts/tests/test_fetch_followthemoney_candidates.py -v`
Expected: `ModuleNotFoundError: No module named 'fetch_followthemoney_candidates'`.

- [ ] **Step 4: Write `scripts/fetch_followthemoney_candidates.py`**

```python
"""Fetch and cache FollowTheMoney Alabama candidate finance records.

Manual/occasional step: run this only when adding a new election year, not
as part of the regular rebuild pipeline (see MODEL_READINESS.md). Requires
FTM_API_KEY in token.env, following the same pattern as
download_acs_sld_demographics.py's CENSUS_API_KEY.

FollowTheMoney's TLS certificate is currently expired site-wide (confirmed
via direct connection during design, not a local trust-store issue), so
this script disables certificate verification -- scoped to this one script
only. Remove verify=False once FollowTheMoney's certificate is fixed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

YEARS = [2010, 2014, 2018, 2022]
BASE_URL = "https://api.followthemoney.org/"


def api_key(root: Path) -> str:
    for line in (root / "token.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("FTM_API_KEY="):
            return line.split("=", 1)[1].strip()
    import os
    return os.environ.get("FTM_API_KEY", "")


def _fetch_page_json(year: int, page: int, key: str) -> dict | None:
    """Return one page's parsed JSON, or None if the response body was empty."""
    params = {"dt": 1, "s": "AL", "y": year, "gro": "c-t-id", "p": page,
              "APIKey": key, "mode": "json"}
    response = requests.get(BASE_URL, params=params, timeout=60, verify=False)
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def fetch_year(
    year: int,
    key: str,
    max_retries: int = 3,
    sleep_seconds: float = 2.0,
    fetch_page: Callable[[int, int, str], dict | None] = _fetch_page_json,
) -> list[dict]:
    records: list[dict] = []
    page = 0
    total_records: int | None = None
    while True:
        data = None
        for _ in range(max_retries):
            data = fetch_page(year, page, key)
            if data is not None:
                break
            if sleep_seconds:
                time.sleep(sleep_seconds)
        if data is None:
            raise RuntimeError(f"year {year} page {page}: empty response after {max_retries} retries")
        paging = data["metaInfo"]["paging"]
        if total_records is None:
            total_records = int(paging["totalRecords"])
        records.extend(data["records"])
        if int(paging["currentPage"]) >= int(paging["maxPage"]):
            break
        page += 1
    if len(records) != total_records:
        raise RuntimeError(f"year {year}: fetched {len(records)} records, expected {total_records}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root
    key = api_key(root)
    output_dir = root / "data" / "raw" / "followthemoney"
    output_dir.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        records = fetch_year(year, key)
        (output_dir / f"{year}_al_candidates.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )
        print(f"{year}: {len(records)} candidate records")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest scripts/tests/test_fetch_followthemoney_candidates.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 6: Run the real fetch**

Run: `.\.venv\Scripts\python.exe scripts\fetch_followthemoney_candidates.py`
Expected: prints 4 lines (2010, 2014, 2018, 2022) with record counts each in
the low hundreds (the 2022 count should be in the same ballpark as the 355
records seen live during design). This makes real network calls to
`api.followthemoney.org` with TLS verification disabled — if it fails with
a connection error rather than empty responses, retry once; FollowTheMoney's
site has been observed to be intermittently unreliable. If it fails
consistently after retrying, stop and report BLOCKED — do not fabricate
cached data.

- [ ] **Step 7: Commit**

```bash
git add scripts/fetch_followthemoney_candidates.py scripts/tests/test_fetch_followthemoney_candidates.py \
        data/raw/followthemoney/2010_al_candidates.json \
        data/raw/followthemoney/2014_al_candidates.json \
        data/raw/followthemoney/2018_al_candidates.json \
        data/raw/followthemoney/2022_al_candidates.json
git commit -m "Fetch and cache FollowTheMoney Alabama candidate records"
```

(`token.env` is gitignored and must NOT appear in `git status` as
untracked-to-be-added — verify this before committing.)

---

### Task 2: Parse and aggregate race-level finance features

**Files:**
- Create: `scripts/build_followthemoney_finance_features.py`
- Create: `scripts/tests/test_build_followthemoney_finance_features.py`

**Interfaces:**
- Consumes: `data/raw/followthemoney/{year}_al_candidates.json` (Task 1's output).
- Produces: `load_cycle(json_path: Path) -> pd.DataFrame` with columns
  `chamber, district, party, total`;
  `build_race_finance_features(cycle_frames: dict[int, pd.DataFrame]) -> pd.DataFrame`
  with columns `cycle, chamber, district, dem_candidate_spending,
  rep_candidate_spending, log_spending_ratio_d_to_r, spending_constant,
  finance_complete, dem_finance_matched, rep_finance_matched`. Writes
  `data/processed/war/race_finance_features.csv`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_build_followthemoney_finance_features.py`:

```python
import json

import numpy as np
import pandas as pd

from build_followthemoney_finance_features import build_race_finance_features, load_cycle


def _record(office, status, party, total, candidate="X"):
    def field(name, value):
        return {"token": "t", "id": value, name: value}

    return {
        "record_id": 1,
        "Candidate": field("Candidate", candidate),
        "Office_Sought": field("Office_Sought", office),
        "Election_Status": field("Election_Status", status),
        "Specific_Party": field("Specific_Party", party),
        "Total_$": {"Total_$": str(total)},
    }


def test_load_cycle_parses_house_and_senate_offices(tmp_path):
    records = [
        _record("HOUSE DISTRICT 038", "Won-General", "REPUBLICAN", 50000.0),
        _record("SENATE DISTRICT 027", "Lost-General", "DEMOCRATIC", 13000.0),
    ]
    path = tmp_path / "2022_al_candidates.json"
    path.write_text(json.dumps(records))

    result = load_cycle(path)

    assert len(result) == 2
    house = result[result.chamber == "house"].iloc[0]
    assert house.district == 38
    assert house.party == "R"
    assert house.total == 50000.0
    senate = result[result.chamber == "senate"].iloc[0]
    assert senate.district == 27
    assert senate.party == "D"


def test_load_cycle_skips_non_legislative_offices(tmp_path):
    records = [_record("GOVERNOR", "Won-General", "REPUBLICAN", 1000000.0)]
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(records))

    result = load_cycle(path)

    assert result.empty


def test_load_cycle_drops_primary_only_candidates(tmp_path):
    # A same-party primary loser with a larger total than the actual nominee
    # must not leak into the output -- this is the exact scenario found live
    # in AL Senate District 27, 2022.
    records = [
        _record("SENATE DISTRICT 027", "Lost-Primary", "REPUBLICAN", 1368546.0, "WHATLEY"),
        _record("SENATE DISTRICT 027", "Won-General", "REPUBLICAN", 799660.0, "HOVEY"),
    ]
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(records))

    result = load_cycle(path)

    assert len(result) == 1
    assert result.iloc[0].total == 799660.0


def test_load_cycle_drops_third_party_candidates(tmp_path):
    records = [_record("HOUSE DISTRICT 038", "Won-General", "LIBERTARIAN", 500.0)]
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(records))

    result = load_cycle(path)

    assert result.empty


def test_build_race_finance_features_computes_ratio_and_completeness():
    frame_2022 = pd.DataFrame([
        {"chamber": "house", "district": 38, "party": "R", "total": 50000.0},
        {"chamber": "house", "district": 38, "party": "D", "total": 10000.0},
        {"chamber": "senate", "district": 27, "party": "R", "total": 799660.0},
        # District 27 has no Democratic row at all -> finance_complete False.
    ])

    race = build_race_finance_features({2022: frame_2022})
    race = race.set_index(["chamber", "district"])

    house38 = race.loc[("house", 38)]
    assert house38.dem_candidate_spending == 10000.0
    assert house38.rep_candidate_spending == 50000.0
    assert house38.finance_complete
    assert round(house38.log_spending_ratio_d_to_r, 4) == round(
        np.log((10000.0 + 500.0) / (50000.0 + 500.0)), 4
    )

    senate27 = race.loc[("senate", 27)]
    assert senate27.dem_candidate_spending == 0.0
    assert senate27.rep_candidate_spending == 799660.0
    assert not senate27.finance_complete
    assert pd.isna(senate27.log_spending_ratio_d_to_r)


def test_build_race_finance_features_has_unique_keys_across_cycles():
    frame_2018 = pd.DataFrame([{"chamber": "house", "district": 1, "party": "R", "total": 100.0}])
    frame_2022 = pd.DataFrame([{"chamber": "house", "district": 1, "party": "R", "total": 200.0}])

    race = build_race_finance_features({2018: frame_2018, 2022: frame_2022})

    assert not race.duplicated(["cycle", "chamber", "district"]).any()
    assert len(race) == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest scripts/tests/test_build_followthemoney_finance_features.py -v`
Expected: `ModuleNotFoundError: No module named 'build_followthemoney_finance_features'`.

- [ ] **Step 3: Write `scripts/build_followthemoney_finance_features.py`**

```python
"""Build race-level candidate finance features from cached FollowTheMoney data.

Replaces build_candidate_finance_features.py's FCPA-extract + fuzzy-name-
matching pipeline. Office_Sought + Election_Status identify the general-
election nominee per party per district directly -- no candidate-name
matching needed. Output columns are kept identical to the retired script's
(dem_candidate_spending/rep_candidate_spending/log_spending_ratio_d_to_r/
spending_constant/finance_complete) even though the underlying quantity is
now FollowTheMoney's Total_$ (contributions raised), not AL FCPA
expenditures -- see
docs/superpowers/specs/2026-08-12-followthemoney-finance-rebuild-design.md.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

YEARS = [2010, 2014, 2018, 2022]
OFFICE_RE = re.compile(r"^(HOUSE|SENATE) DISTRICT (\d+)$", re.IGNORECASE)
GENERAL_STATUSES = {"Won-General", "Lost-General"}
PARTY_MAP = {"REPUBLICAN": "R", "DEMOCRATIC": "D"}


def _field(record: dict, name: str) -> object:
    return record[name][name]


def load_cycle(json_path: Path) -> pd.DataFrame:
    records = json.loads(json_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for record in records:
        office = str(_field(record, "Office_Sought")).strip()
        match = OFFICE_RE.match(office)
        if not match:
            continue
        status = _field(record, "Election_Status")
        if status not in GENERAL_STATUSES:
            continue
        party = PARTY_MAP.get(str(_field(record, "Specific_Party")).strip().upper())
        if party is None:
            continue
        rows.append(
            {
                "chamber": "house" if match.group(1).upper() == "HOUSE" else "senate",
                "district": int(match.group(2)),
                "party": party,
                "total": float(_field(record, "Total_$")),
            }
        )
    return pd.DataFrame(rows, columns=["chamber", "district", "party", "total"])


def build_race_finance_features(cycle_frames: dict[int, pd.DataFrame]) -> pd.DataFrame:
    parts = [frame.assign(cycle=cycle) for cycle, frame in cycle_frames.items() if not frame.empty]
    combined = pd.concat(parts, ignore_index=True)
    keys = ["cycle", "chamber", "district"]

    totals = (
        combined.groupby(keys + ["party"], as_index=False)["total"].sum()
        .pivot(index=keys, columns="party", values="total")
        .reset_index()
    )
    for party in ("D", "R"):
        if party not in totals:
            totals[party] = np.nan
    totals = totals.rename(columns={"D": "dem_candidate_spending", "R": "rep_candidate_spending"})

    race = totals.copy()
    race["dem_finance_matched"] = race["dem_candidate_spending"].notna()
    race["rep_finance_matched"] = race["rep_candidate_spending"].notna()
    race["dem_candidate_spending"] = race["dem_candidate_spending"].fillna(0.0)
    race["rep_candidate_spending"] = race["rep_candidate_spending"].fillna(0.0)

    constant = 500.0
    race["log_spending_ratio_d_to_r"] = np.log(
        (race["dem_candidate_spending"] + constant) / (race["rep_candidate_spending"] + constant)
    )
    race["spending_constant"] = constant
    race["finance_complete"] = race["dem_finance_matched"] & race["rep_finance_matched"]
    race.loc[~race["finance_complete"], "log_spending_ratio_d_to_r"] = np.nan

    return race[
        keys
        + [
            "dem_candidate_spending",
            "rep_candidate_spending",
            "log_spending_ratio_d_to_r",
            "spending_constant",
            "finance_complete",
            "dem_finance_matched",
            "rep_finance_matched",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root
    raw = root / "data" / "raw" / "followthemoney"
    cycle_frames = {year: load_cycle(raw / f"{year}_al_candidates.json") for year in YEARS}
    race = build_race_finance_features(cycle_frames)

    output = root / "data" / "processed" / "war"
    output.mkdir(parents=True, exist_ok=True)
    race.to_csv(output / "race_finance_features.csv", index=False)

    coverage = race.groupby("cycle", as_index=False)["finance_complete"].mean()
    print(coverage.to_string(index=False))
    print(f"Total races: {len(race)}; complete: {int(race['finance_complete'].sum())}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest scripts/tests/test_build_followthemoney_finance_features.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Run it for real**

Run: `.\.venv\Scripts\python.exe scripts\build_followthemoney_finance_features.py`
Expected: prints a per-cycle `finance_complete` rate table (2014/2018/2022 —
2010 will have no matching WAR races since the model doesn't cover that
cycle, which is fine, its rows just won't be used downstream) and a total
race count. The 2014/2018/2022 completion rate should be visibly higher
than the retired script's 81.2% figure — if it isn't, treat that as a real
finding to investigate (e.g. an `Office_Sought` format assumption that
doesn't hold for an older year), not something to note and move past.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_followthemoney_finance_features.py scripts/tests/test_build_followthemoney_finance_features.py
git commit -m "Build race-level finance features from FollowTheMoney data"
```

(Do not commit the regenerated `data/processed/war/race_finance_features.csv`
yet — Task 3 diffs it against the committed baseline first.)

---

### Task 3: Diff against the retired pipeline and validate downstream

**Files:**
- None created — this task runs the new pipeline, diffs it, and re-runs
  the downstream WAR assembly/fit to confirm nothing broke.

**Interfaces:**
- Consumes: Task 2's `build_followthemoney_finance_features.py`.

- [ ] **Step 1: Snapshot the pre-rebuild finance features**

Run: `git show HEAD:data/processed/war/race_finance_features.csv > "$env:TEMP\race_finance_features_before.csv"`

- [ ] **Step 2: Confirm the new output is already in the working tree**

`data/processed/war/race_finance_features.csv` should already be present
and modified (from Task 2 Step 5's real run). Run: `git diff --stat
data/processed/war/race_finance_features.csv` to see the size of the change.

- [ ] **Step 3: Compare coverage and sanity-check magnitudes**

Run (PowerShell):
```powershell
python -c "
import pandas as pd
before = pd.read_csv(r'$env:TEMP\race_finance_features_before.csv')
after = pd.read_csv('data/processed/war/race_finance_features.csv')
print('before rows:', len(before), 'complete:', before.finance_complete.sum())
print('after rows:', len(after), 'complete:', after.finance_complete.sum())
before_rate = before.finance_complete.mean()
after_rate = after.finance_complete.mean()
print(f'before completion rate: {before_rate:.1%}')
print(f'after completion rate: {after_rate:.1%}')
merged = before.merge(after, on=['cycle','chamber','district'], suffixes=('_before','_after'), how='outer', indicator=True)
print('rows only in before:', (merged._merge=='left_only').sum())
print('rows only in after:', (merged._merge=='right_only').sum())
"
```
Expected: the after-completion-rate is visibly higher than the retired
script's 81.2% (before-completion-rate should roughly match that figure,
confirming the baseline snapshot is right). Dollar magnitudes will differ
between before/after (expenditures vs. contributions-raised are different
quantities) — that's expected, not a regression. Rows only in one side are
plausible (the FollowTheMoney-based pipeline may cover districts the FCPA
extract missed, or vice versa for the rare case a district's FollowTheMoney
data doesn't resolve to House/Senate cleanly) but should be a small
minority, not most of the table — if it's most of the table, investigate
before proceeding.

- [ ] **Step 4: Re-run the downstream assembly and model fit**

Run:
```powershell
python scripts\assemble_war_features.py
python scripts\fit_preliminary_war_model.py
```
Expected: both complete without error. Compare
`assemble_war_features.py`'s printed `Complete finance coverage: N/420`
line against the currently-committed number (check
`git show HEAD:MODEL_READINESS.md` or rerun on the pre-change data if
unsure) — it should increase, consistent with the coverage improvement
from Step 3. Confirm the model fit's R-squared/MAE are in the same general
ballpark as `MODEL_READINESS.md`'s current documented numbers — a
wildly different fit signals a real problem in the new finance feature,
not an expected consequence of a data-source swap for one feature among
many.

- [ ] **Step 5: Do not commit yet**

Leave `data/processed/war/race_finance_features.csv`,
`war_model_features.csv`, and any other regenerated
`preliminary_war_*.csv` files as uncommitted working-tree changes — Task 4
commits everything together alongside the retirement of the old script.

---

### Task 4: Retire the old finance script and finalize

**Files:**
- Delete: `scripts/build_candidate_finance_features.py`,
  `data/processed/war/finance_candidate_cycle_totals.csv`,
  `data/processed/war/candidate_finance_matches.csv`,
  `data/processed/war/candidate_finance_review.csv`,
  `data/processed/war/candidate_finance_coverage.csv`
- Modify: `MODEL_READINESS.md`

**Interfaces:** None — this is cleanup after Task 3's diff has been
reviewed and accepted.

- [ ] **Step 1: Delete the superseded script and its outputs**

```bash
git rm scripts/build_candidate_finance_features.py \
       data/processed/war/finance_candidate_cycle_totals.csv \
       data/processed/war/candidate_finance_matches.csv \
       data/processed/war/candidate_finance_review.csv \
       data/processed/war/candidate_finance_coverage.csv
```

- [ ] **Step 2: Update `MODEL_READINESS.md`'s "Rebuild and validate" section**

In the fenced script-list block, replace the line
```
python scripts\build_candidate_finance_features.py
```
with
```
python scripts\build_followthemoney_finance_features.py
```
Add one sentence above the block noting that candidate finance data now
comes from FollowTheMoney (fetched separately and occasionally via
`scripts\fetch_followthemoney_candidates.py`, not part of the routine
rebuild — see the script's own docstring), replacing the retired
FCPA-extract + fuzzy-matching approach.

- [ ] **Step 3: Update `MODEL_READINESS.md`'s finance-coverage figure**

Find the sentence describing "Both major candidates are matched in 125 of
154 contested races (81.2%)" (or wherever it currently lives after the
precinct rebuild's edits) and replace it with the actual coverage figure
from Task 3 Step 3/4's real run.

- [ ] **Step 4: Stage everything together**

```bash
git add -A data/processed/war MODEL_READINESS.md
git status
```
Review the output: it should show Task 3's regenerated finance/WAR files as
modified, this task's deletions, `MODEL_READINESS.md` as modified, and
nothing unexpected (no `.venv`, no stray `__pycache__`).

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Retire FCPA-extract finance pipeline in favor of FollowTheMoney

Candidate finance data now comes from FollowTheMoney's Ask Anything API
instead of raw AL FCPA expenditure extracts matched by fuzzy candidate-
name matching. Office_Sought and Election_Status identify the general-
election nominee per party per district directly, improving match
coverage past the retired pipeline's 81.2% and including losing
candidates the old approach sometimes missed.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
