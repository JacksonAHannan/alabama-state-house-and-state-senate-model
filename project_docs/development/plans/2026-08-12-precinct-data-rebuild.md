# Precinct Data Rebuild (OpenElections Source) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four different per-cycle vote-count sources currently
feeding the WAR model's precinct data (raw SoS zips, a bespoke VTD crosswalk,
VEST-shapefile polygon overlay, and manually-copied OpenElections CSVs) with
OpenElections precinct CSVs as the single canonical vote source for every
cycle OE covers (2012, 2014, 2016, 2018, 2020), while leaving the 2022 RDH
pipeline untouched.

**Architecture:** A shared normalization module centralizes party/precinct
string handling. An explicit sync script vendors OE CSVs from the sibling
`openelections-data-al` checkout. One generalized precinct-name-matching
function (already proven for 2012->2014 in the current code) replaces the
VTD-crosswalk and VEST-polygon-overlay approaches for all four
presidential-to-legislative-cycle trend allocations. Old scripts and their
derived crosswalk artifacts are deleted only after a before/after diff of
the model's feature output confirms no unintended regression.

**Tech Stack:** Python 3.9, pandas, numpy, rapidfuzz, geopandas (unchanged
2022 path only), pytest.

## Global Constraints

- Match the existing code style: `from __future__ import annotations` at the
  top of every script; Path-based I/O anchored at
  `Path(__file__).resolve().parents[1]` (repo root) with a `--root` CLI
  override, matching every existing `scripts/*.py`.
- New scripts that need sibling modules use
  `sys.path.insert(0, str(Path(__file__).resolve().parent))` then a plain
  `from oe_normalize import ...`, matching the pattern already used in
  `build_2012_president_on_2018_map.py` and `build_vest_presidential_districts.py`.
- Precinct/county join keys are always the uppercased, stripped
  `county_key`/`precinct_key` columns already established by
  `data/processed/war/precinct_district_allocation_weights.csv` — every new
  module produces and consumes those exact column names, not `county`/`precinct`.
- Precinct name fuzzy-match acceptance threshold is `rapidfuzz.fuzz.WRatio`
  score >= 92 and margin over the second-best candidate >= 4 — this is the
  existing, currently-trusted threshold from `build_2012_presidential_districts.py`.
  Do not change it as part of this rebuild.
- Every new pure-logic module gets pytest unit tests in `scripts/tests/`
  using synthetic in-memory fixtures — never a dependency on real data files
  in a unit test.
- Everything under `data/` is tracked in git (not gitignored), so
  `git status` / `git diff` against regenerated CSVs is the mechanism for
  every before/after validation step in this plan — no manual backups needed.
- `openelections-data-al` is a sibling checkout at
  `C:\Users\User\Documents\GitHub\openelections-data-al` (i.e. `../openelections-data-al`
  relative to this repo's root). Scripts must not hardcode this absolute path;
  use a `--source-repo` CLI argument defaulting to the relative sibling path.

---

## File Structure

**Create:**
- `requirements.txt` — pins every third-party package imported anywhere in `scripts/`.
- `pytest.ini` — points pytest at `scripts/tests`.
- `scripts/oe_normalize.py` — shared party/precinct-name normalization and the OE CSV loader.
- `scripts/tests/conftest.py` — puts `scripts/` on `sys.path` for test imports.
- `scripts/tests/test_oe_normalize.py`
- `scripts/sync_openelections_data.py` — vendors OE CSVs from the sibling repo.
- `scripts/tests/test_sync_openelections_data.py`
- `scripts/build_oe_president_precinct.py` — extracts precinct-level President votes from an OE CSV.
- `scripts/tests/test_build_oe_president_precinct.py`
- `scripts/validate_oe_precinct_totals.py` — checksum validation (component rows sum to reported `Total` rows).
- `scripts/tests/test_validate_oe_precinct_totals.py`
- `scripts/build_presidential_district_features.py` — generalized precinct-to-district allocation, replacing four retired scripts.
- `scripts/tests/test_build_presidential_district_features.py`

**Modify:**
- `scripts/build_war_database.py` — import `PARTY_MAP`/`norm_party`/`load_oe`/`is_pseudocandidate` from `oe_normalize` instead of defining them locally.
- `.gitignore` — add `.venv/`.
- `project_docs/model/MODEL_READINESS.md` — update the "Rebuild and validate" script list.

**Delete (Task 9, after diff validation only):**
- `scripts/normalize_2012_president.py`
- `scripts/build_2012_president_vtd_crosswalk.py`
- `scripts/build_2012_president_on_2018_map.py`
- `scripts/build_2012_presidential_districts.py`
- `scripts/build_vest_presidential_districts.py`
- `scripts/build_2014_precinct_crosswalk.py`
- `scripts/build_2014_multisource_crosswalk.py`
- `scripts/validate_2014_precinct_crosswalk.py`
- `data/manual/2014_precinct_geometry_overrides.csv`
- `data/derived/crosswalks/2012_president_vtd_crosswalk.csv`, `2012_president_vtd_summary.csv`, `2012_president_vtd_vote_qa.csv`
- `data/derived/crosswalks/2014_precinct_geometry_crosswalk_by_county.csv`, `2014_precinct_geometry_crosswalk_consolidated.csv`, `2014_precinct_geometry_crosswalk_summary.csv`, `2014_precinct_geometry_unresolved.csv`
- `data/derived/crosswalks/2014_precinct_legislative_district_activity.csv`
- `data/derived/crosswalks/2014_precinct_vest16_crosswalk_validated.csv`
- `data/derived/crosswalks/2014_precinct_vtd_crosswalk.csv`, `2014_precinct_vtd_crosswalk_validated.csv`, `2014_precinct_vtd_review.csv`, `2014_precinct_vtd_review_enhanced.csv`, `2014_precinct_vtd_summary.csv`, `2014_precinct_vtd_summary_by_county.csv`, `2014_precinct_vtd_validation_by_county.csv`, `2014_precinct_vtd_validation_summary.csv`

---

### Task 1: Environment setup

**Files:**
- Create: `requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: a working Python virtual environment at `.venv` with every package the plan's scripts need.

- [ ] **Step 1: Write `requirements.txt`**

```text
pandas>=2.2
numpy>=1.26
geopandas>=0.14
rapidfuzz>=3.6
pyogrio>=0.7
shapely>=2.0
beautifulsoup4>=4.12
requests>=2.31
scikit-learn>=1.4
pytest>=8.0
```

- [ ] **Step 2: Add `.venv/` to `.gitignore`**

Append a line `.venv/` to the existing `.gitignore` (which currently contains only `token.env`).

- [ ] **Step 3: Create the virtual environment and install dependencies**

Run (PowerShell, from repo root):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Expected: all packages install without error. `geopandas` on Windows can be
slow to resolve (GDAL/pyogrio wheels); if it fails, retry with
`pip install --only-binary=:all: geopandas pyogrio shapely` before the
general install.

- [ ] **Step 4: Verify the environment**

Run: `.\.venv\Scripts\python.exe -c "import pandas, numpy, geopandas, rapidfuzz, pyogrio, sklearn, pytest; print('deps ok')"`
Expected: prints `deps ok` with no `ModuleNotFoundError`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "Add requirements.txt and .venv to .gitignore for the precinct rebuild"
```

*(Use `.\.venv\Scripts\python.exe` for every subsequent "Run:" instruction in this plan — abbreviated below as `python` for brevity.)*

---

### Task 2: Shared normalization module

**Files:**
- Create: `scripts/oe_normalize.py`
- Create: `scripts/tests/conftest.py`
- Create: `scripts/tests/test_oe_normalize.py`
- Test: `scripts/tests/test_oe_normalize.py`

**Interfaces:**
- Produces: `PARTY_MAP: dict[str, str]`, `norm_party(value: object) -> str`,
  `is_pseudocandidate(candidate: object) -> bool`,
  `normalize_name(value: object) -> str`,
  `normalize_for_match(value: object) -> str`,
  `load_oe(path: Path) -> pd.DataFrame` (adds `votes` as float, `district` as
  float/NaN, `party_norm`, `county_key`, `precinct_key` columns to the raw
  OE CSV).

- [ ] **Step 1: Create `pytest.ini`**

```ini
[pytest]
testpaths = scripts/tests
```

- [ ] **Step 2: Create `scripts/tests/conftest.py`**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 3: Write the failing tests**

Create `scripts/tests/test_oe_normalize.py`:

```python
from io import StringIO

import pandas as pd

from oe_normalize import (
    is_pseudocandidate,
    load_oe,
    normalize_for_match,
    normalize_name,
    norm_party,
)


def test_norm_party_maps_known_variants():
    assert norm_party("D") == "D"
    assert norm_party("dem") == "D"
    assert norm_party("Democrat") == "D"
    assert norm_party("R") == "R"
    assert norm_party("rep") == "R"
    assert norm_party("Republican") == "R"


def test_norm_party_defaults_unknown_to_other():
    assert norm_party("IND") == "O"
    assert norm_party("") == "O"
    assert norm_party(None) == "O"


def test_is_pseudocandidate_matches_known_labels():
    assert is_pseudocandidate("Over Votes")
    assert is_pseudocandidate("Under Votes")
    assert is_pseudocandidate("Write-in")
    assert is_pseudocandidate("Write-ins")
    assert not is_pseudocandidate("Jane Smith")


def test_normalize_name_expands_abbreviations_and_strips_punctuation():
    assert normalize_name("St. Mark's Ch") == "SAINT MARKS CHURCH"
    assert normalize_name("1st Baptist Ch") == "FIRST BAPTIST CHURCH"
    assert normalize_name("Smith & Jones VFD") == "SMITH AND JONES VOLUNTEER FIRE DEPARTMENT"


def test_normalize_for_match_strips_leading_codes_and_machine_suffixes():
    assert normalize_for_match("101 - Midway Baptist Church") == "MIDWAY BAPTIST CHURCH"
    assert normalize_for_match("Midway Baptist Church #2") == "MIDWAY BAPTIST CHURCH"
    assert normalize_for_match("Midway Baptist Church Box 3") == "MIDWAY BAPTIST CHURCH"


def test_load_oe_normalizes_types_and_keys(tmp_path):
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,State House,10,DEM,Jane Smith,120\n"
        "Autauga,Precinct 1,State House,10,REP,John Doe,\n"
        "Autauga,Precinct 1,President,,DEM,Joe Biden,150\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    data = load_oe(path)

    assert data.loc[0, "votes"] == 120.0
    assert data.loc[1, "votes"] == 0.0  # blank vote count coerced to 0
    assert data.loc[0, "district"] == 10.0
    assert pd.isna(data.loc[2, "district"])
    assert data.loc[0, "party_norm"] == "D"
    assert data.loc[1, "party_norm"] == "R"
    assert data.loc[0, "county_key"] == "AUTAUGA"
    assert data.loc[0, "precinct_key"] == "PRECINCT 1"
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_oe_normalize.py -v`
Expected: `ModuleNotFoundError: No module named 'oe_normalize'` (or collection error) for every test.

- [ ] **Step 5: Write `scripts/oe_normalize.py`**

```python
"""Shared normalization for Alabama OpenElections precinct CSVs.

Every cycle sourced from openelections-data-al goes through this module so
party mapping, pseudo-candidate detection, and precinct-name normalization
are identical across cycles instead of being redefined per script.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

PARTY_MAP = {
    "D": "D",
    "DEM": "D",
    "DEMOCRAT": "D",
    "R": "R",
    "REP": "R",
    "REPUBLICAN": "R",
}

PSEUDOCANDIDATE_RE = re.compile(r"Over Votes|Under Votes|Write", re.IGNORECASE)

NON_GEOGRAPHIC_RE = re.compile(
    r"\b(ABSENTEE|PROVISIONAL|FAILSAFE|OVERSEAS|UOCAVA|TOTAL|TOTALS|ELECTION SYSTEMS)\b"
)

TOKEN_REPLACEMENTS = {
    "1ST": "FIRST",
    "CTR": "CENTER",
    "CNTR": "CENTER",
    "COMM": "COMMUNITY",
    "DEPT": "DEPARTMENT",
    "DEPTMENT": "DEPARTMENT",
    "FD": "FIRE DEPARTMENT",
    "VFD": "VOLUNTEER FIRE DEPARTMENT",
    "VOL": "VOLUNTEER",
    "BAPT": "BAPTIST",
    "CH": "CHURCH",
    "CHUR": "CHURCH",
    "ELEM": "ELEMENTARY",
    "SCH": "SCHOOL",
    "MT": "MOUNT",
    "ST": "SAINT",
    "CO": "COUNTY",
    "CTY": "COUNTY",
    "REC": "RECREATION",
    "BLDG": "BUILDING",
}


def norm_party(value: object) -> str:
    return PARTY_MAP.get(str(value).strip().upper(), "O")


def is_pseudocandidate(candidate: object) -> bool:
    return bool(PSEUDOCANDIDATE_RE.search(str(candidate)))


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = text.upper().replace("&", " AND ")
    text = re.sub(r"[_/\\\-]+", " ", text)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    tokens: list[str] = []
    for token in text.split():
        token = str(int(token)) if token.isdigit() else token
        tokens.extend(TOKEN_REPLACEMENTS.get(token, token).split())
    return " ".join(tokens)


def normalize_for_match(value: object) -> str:
    """Normalize a precinct name while stripping codes and machine suffixes."""
    text = str(value).strip()
    text = re.sub(r"^\s*\d{3,4}\s*[-:]?\s*", "", text)
    text = re.sub(r"\s*#\s*\d+\s*$", "", text)
    text = re.sub(r"\s+(?:BOX|BX)\s*\d+\s*$", "", text, flags=re.I)
    text = re.sub(r"\s+[123]\s*$", "", text)
    return normalize_name(text)


def load_oe(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, low_memory=False)
    data["votes"] = pd.to_numeric(data["votes"], errors="coerce").fillna(0.0)
    data["district"] = pd.to_numeric(data["district"], errors="coerce")
    data["party_norm"] = data["party"].map(norm_party)
    data["county_key"] = data["county"].astype(str).str.upper().str.strip()
    data["precinct_key"] = data["precinct"].astype(str).str.upper().str.strip()
    return data
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_oe_normalize.py -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add pytest.ini scripts/oe_normalize.py scripts/tests/conftest.py scripts/tests/test_oe_normalize.py
git commit -m "Add shared OpenElections normalization module"
```

---

### Task 3: Sync script for OpenElections source CSVs

**Files:**
- Create: `scripts/sync_openelections_data.py`
- Test: `scripts/tests/test_sync_openelections_data.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (stdlib only).
- Produces: `CYCLES: list[tuple[int, str]]`, `sync(source_repo: Path, dest_dir: Path) -> list[dict[str, object]]`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_sync_openelections_data.py`:

```python
from pathlib import Path

import pytest

from sync_openelections_data import CYCLES, sync


def _make_fake_source_repo(root: Path) -> Path:
    source_repo = root / "openelections-data-al"
    for _cycle, relpath in CYCLES:
        path = source_repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"county,precinct,office,district,party,candidate,votes\nFake,P1,President,,DEM,X,{relpath}\n")
    return source_repo


def test_sync_copies_every_cycle_file(tmp_path):
    source_repo = _make_fake_source_repo(tmp_path)
    dest_dir = tmp_path / "data" / "raw" / "openelections"

    report = sync(source_repo, dest_dir)

    assert len(report) == len(CYCLES)
    for cycle, relpath in CYCLES:
        dest_path = dest_dir / Path(relpath).name
        assert dest_path.exists()
        assert dest_path.read_text() == (source_repo / relpath).read_text()


def test_sync_raises_when_source_file_missing(tmp_path):
    source_repo = _make_fake_source_repo(tmp_path)
    (source_repo / CYCLES[0][1]).unlink()
    dest_dir = tmp_path / "dest"

    with pytest.raises(FileNotFoundError):
        sync(source_repo, dest_dir)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_sync_openelections_data.py -v`
Expected: `ModuleNotFoundError: No module named 'sync_openelections_data'`.

- [ ] **Step 3: Write `scripts/sync_openelections_data.py`**

```python
"""Vendor OpenElections Alabama precinct CSVs from the sibling data repo.

This replaces the previous silent manual copy of these files into
data/raw/openelections/: running this script is the explicit, logged sync
step, and it fails loudly if the sibling checkout or a source file is
missing rather than silently leaving a stale copy in place.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

CYCLES: list[tuple[int, str]] = [
    (2012, "2012/20121106__al__general__precinct.csv"),
    (2014, "2014/20141104__al__general__precinct.csv"),
    (2016, "2016/20161108__al__general__precinct.csv"),
    (2018, "2018/20181106__al__general__precinct.csv"),
    (2020, "2020/20201103__al__general__precinct.csv"),
]


def sync(source_repo: Path, dest_dir: Path) -> list[dict[str, object]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, object]] = []
    for cycle, relpath in CYCLES:
        source_path = source_repo / relpath
        if not source_path.exists():
            raise FileNotFoundError(f"missing OpenElections source file for {cycle}: {source_path}")
        dest_path = dest_dir / Path(relpath).name
        shutil.copyfile(source_path, dest_path)
        report.append({"cycle": cycle, "source": str(source_path), "dest": str(dest_path),
                        "bytes": dest_path.stat().st_size})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-repo", type=Path, default=None,
                         help="Path to the openelections-data-al checkout "
                              "(default: ../openelections-data-al next to this repo)")
    args = parser.parse_args()
    root = args.root
    source_repo = args.source_repo or (root.parent / "openelections-data-al")
    if not source_repo.exists():
        raise FileNotFoundError(f"openelections-data-al checkout not found at {source_repo}")
    report = sync(source_repo, root / "data" / "raw" / "openelections")
    for row in report:
        print(f"{row['cycle']}: {row['dest']} ({row['bytes']:,} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_sync_openelections_data.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run the sync for real**

Run: `python scripts/sync_openelections_data.py`
Expected: prints 5 lines (2012, 2014, 2016, 2018, 2020) with byte counts. Then run
`git status data/raw/openelections/` — expect the 2014 and 2018 files to show
**no changes** (already confirmed byte-identical to the source repo during
design), and three new untracked files for 2012, 2016, 2020.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_openelections_data.py scripts/tests/test_sync_openelections_data.py \
        data/raw/openelections/20121106__al__general__precinct.csv \
        data/raw/openelections/20161108__al__general__precinct.csv \
        data/raw/openelections/20201103__al__general__precinct.csv
git commit -m "Add explicit OpenElections sync script; vendor 2012/2016/2020 precinct CSVs"
```

---

### Task 4: Rewire `build_war_database.py` onto the shared normalization module

**Files:**
- Modify: `scripts/build_war_database.py:1-50, 115-118`

**Interfaces:**
- Consumes: `PARTY_MAP`, `norm_party`, `load_oe`, `is_pseudocandidate` from `oe_normalize` (Task 2).
- Produces: no change to any output schema — this task is a pure refactor, validated by diffing output before/after.

- [ ] **Step 1: Record the current output as the diff baseline**

Run: `python scripts/build_war_database.py`
Then: `git status data/processed/war/` — expect **no changes** (this confirms
the script runs cleanly before the refactor; it's the baseline the refactor
must reproduce exactly).

- [ ] **Step 2: Edit the top of `scripts/build_war_database.py`**

Replace lines 1-50 (from the module docstring through the `load_oe`
function) with:

```python
"""Build WAR-ready Alabama legislative race and district-baseline tables.

2014 and 2018 use normalized OpenElections copies of official precinct returns.
2022 uses RDH precinct and legislative-district split layers. Geometry is not
required: legislative contest activity supplies weights for split precincts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import is_pseudocandidate, load_oe, norm_party  # noqa: E402


CORE_BASELINE_OFFICES = {"Governor", "Attorney General"}
EXECUTIVE_OFFICES = {
    "Governor",
    "Lieutenant Governor",
    "Attorney General",
    "Secretary of State",
    "State Auditor",
    "State Treasurer",
    "Commissioner of Agriculture and Industries",
}
MAP_VINTAGE = {2014: "2012_enacted", 2018: "2017_remedial", 2022: "2021_enacted"}
```

- [ ] **Step 3: Replace the inline pseudo-candidate check**

Find (currently around line 117):

```python
        named = legislative[
            legislative["party_norm"].isin(["D", "R"])
            & ~legislative["candidate"].astype(str).str.contains("Over Votes|Under Votes|Write", case=False, regex=True)
        ]
```

Replace with:

```python
        named = legislative[
            legislative["party_norm"].isin(["D", "R"])
            & ~legislative["candidate"].map(is_pseudocandidate)
        ]
```

- [ ] **Step 4: Verify `load_jefferson_2014_legislative` still uses the shared helpers**

Confirm the function (now below the constants) still calls `norm_party` — it
already does (`data["party_norm"] = data["party"].map(norm_party)`), and
`norm_party` now resolves via the `oe_normalize` import from Step 2. No
change needed to the function body itself.

- [ ] **Step 5: Re-run and diff against the baseline**

Run: `python scripts/build_war_database.py`
Then: `git status data/processed/war/` and `git diff data/processed/war/`
Expected: **no changes** — every output file byte-identical to the Task 4
Step 1 baseline. If anything differs, stop and investigate before proceeding
(the refactor must be behavior-preserving).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_war_database.py
git commit -m "Rewire build_war_database.py onto the shared oe_normalize module"
```

---

### Task 5: OE presidential precinct extractor

**Files:**
- Create: `scripts/build_oe_president_precinct.py`
- Test: `scripts/tests/test_build_oe_president_precinct.py`

**Interfaces:**
- Consumes: `load_oe(path: Path) -> pd.DataFrame` from `oe_normalize` (Task 2).
- Produces: `extract_president_precinct_votes(oe_csv_path: Path) -> pd.DataFrame`
  with columns `county_key, precinct_key, dem_votes, rep_votes, two_party_votes, pres_dem_margin`.
  Writes `data/processed/presidential/{year}_president_precinct.csv`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_build_oe_president_precinct.py`:

```python
from build_oe_president_precinct import extract_president_precinct_votes


def test_extract_pivots_president_votes_by_precinct(tmp_path):
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,President,,DEM,Biden,100\n"
        "Autauga,Precinct 1,President,,REP,Trump,150\n"
        "Autauga,Precinct 1,President,,GRN,Other,5\n"
        "Autauga,Precinct 2,President,,REP,Trump,80\n"
        "Autauga,Precinct 1,State House,10,DEM,Smith,40\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    result = extract_president_precinct_votes(path)
    result = result.set_index(["county_key", "precinct_key"])

    assert result.loc[("AUTAUGA", "PRECINCT 1"), "dem_votes"] == 100
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "rep_votes"] == 150
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "two_party_votes"] == 250
    assert round(result.loc[("AUTAUGA", "PRECINCT 1"), "pres_dem_margin"], 2) == -20.0

    # Precinct with only Republican votes: Democratic column fills with 0.
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "dem_votes"] == 0
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "rep_votes"] == 80

    # Only 2 precincts total: the State House row and the Green candidate
    # row must not leak into the President pivot.
    assert len(result) == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_build_oe_president_precinct.py -v`
Expected: `ModuleNotFoundError: No module named 'build_oe_president_precinct'`.

- [ ] **Step 3: Write `scripts/build_oe_president_precinct.py`**

```python
"""Extract precinct-level President vote totals from an OpenElections CSV.

Replaces normalize_2012_president.py's raw Secretary-of-State-zip parsing:
2012, 2016, and 2020 President results all come from the same normalized
OpenElections format as the 2014/2018 legislative data, so one function
handles every year.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import load_oe  # noqa: E402

YEAR_FILENAMES = {
    2012: "20121106__al__general__precinct.csv",
    2016: "20161108__al__general__precinct.csv",
    2020: "20201103__al__general__precinct.csv",
}


def extract_president_precinct_votes(oe_csv_path: Path) -> pd.DataFrame:
    data = load_oe(oe_csv_path)
    president = data[data["office"] == "President"]
    pivot = (
        president[president["party_norm"].isin(["D", "R"])]
        .groupby(["county_key", "precinct_key", "party_norm"], as_index=False)["votes"]
        .sum()
        .pivot(index=["county_key", "precinct_key"], columns="party_norm", values="votes")
        .fillna(0)
        .reset_index()
    )
    for column in ["D", "R"]:
        if column not in pivot:
            pivot[column] = 0.0
    pivot = pivot.rename(columns={"D": "dem_votes", "R": "rep_votes"})
    pivot["two_party_votes"] = pivot["dem_votes"] + pivot["rep_votes"]
    pivot["pres_dem_margin"] = 100 * (pivot["dem_votes"] - pivot["rep_votes"]) / pivot[
        "two_party_votes"
    ].where(pivot["two_party_votes"] > 0)
    return pivot[["county_key", "precinct_key", "dem_votes", "rep_votes", "two_party_votes", "pres_dem_margin"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--year", type=int, required=True, choices=sorted(YEAR_FILENAMES))
    args = parser.parse_args()
    source = args.root / "data" / "raw" / "openelections" / YEAR_FILENAMES[args.year]
    result = extract_president_precinct_votes(source)
    output_dir = args.root / "data" / "processed" / "presidential"
    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_dir / f"{args.year}_president_precinct.csv", index=False)
    print(f"{args.year}: {len(result)} precincts, "
          f"{result.dem_votes.sum():,.0f} D / {result.rep_votes.sum():,.0f} R")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_build_oe_president_precinct.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run it for real, for all three years**

Run:
```powershell
python scripts/build_oe_president_precinct.py --year 2012
python scripts/build_oe_president_precinct.py --year 2016
python scripts/build_oe_president_precinct.py --year 2020
```
Expected: three files written to `data/processed/presidential/`:
`2012_president_precinct.csv`, `2016_president_precinct.csv`,
`2020_president_precinct.csv`. Each print line's total D/R votes should be
in the tens-of-thousands-to-millions range (statewide presidential totals),
not zero.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_oe_president_precinct.py scripts/tests/test_build_oe_president_precinct.py \
        data/processed/presidential/2012_president_precinct.csv \
        data/processed/presidential/2016_president_precinct.csv \
        data/processed/presidential/2020_president_precinct.csv
git commit -m "Extract 2012/2016/2020 presidential precinct votes from OpenElections"
```

---

### Task 6: Precinct total-checksum validation

**Files:**
- Create: `scripts/validate_oe_precinct_totals.py`
- Test: `scripts/tests/test_validate_oe_precinct_totals.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pandas only).
- Produces: `check_totals(data: pd.DataFrame, group_columns: list[str], total_column: str) -> pd.DataFrame`,
  `validate_file(path: Path) -> pd.DataFrame`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_validate_oe_precinct_totals.py`:

```python
import pandas as pd

from validate_oe_precinct_totals import check_totals, validate_file


def test_check_totals_flags_a_mismatched_reported_total():
    data = pd.DataFrame(
        [
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Biden", "votes": 10},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Trump", "votes": 20},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Total", "votes": 999},
        ]
    )
    mismatches = check_totals(data, ["county", "office", "district", "precinct"], "candidate")
    assert len(mismatches) == 1
    assert mismatches.iloc[0]["reported_total"] == 999
    assert mismatches.iloc[0]["calculated_total"] == 30


def test_check_totals_passes_when_total_reconciles():
    data = pd.DataFrame(
        [
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Biden", "votes": 10},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Trump", "votes": 20},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Total", "votes": 30},
        ]
    )
    mismatches = check_totals(data, ["county", "office", "district", "precinct"], "candidate")
    assert mismatches.empty


def test_validate_file_checks_both_directions(tmp_path):
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,P1,President,,DEM,Biden,10\n"
        "Autauga,P1,President,,REP,Trump,20\n"
        "Autauga,P1,President,,,Total,30\n"
        "Autauga,Total,President,,,Biden,10\n"
        "Autauga,Total,President,,,Trump,20\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    mismatches = validate_file(path)
    assert mismatches.empty
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_validate_oe_precinct_totals.py -v`
Expected: `ModuleNotFoundError: No module named 'validate_oe_precinct_totals'`.

- [ ] **Step 3: Write `scripts/validate_oe_precinct_totals.py`**

```python
"""Validate that per-precinct/candidate vote totals reconcile to reported Total rows.

Mirrors the checksum logic in openelections-data-al's src/total_checksum.py:
every (county, office, district, precinct) group's Total-candidate row, and
every (county, office, district, candidate) group's Total-precinct row, must
equal the sum of the non-Total component rows. This runs as an explicit
pipeline step against every synced OpenElections CSV instead of being a
one-off manual check.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def check_totals(data: pd.DataFrame, group_columns: list[str], total_column: str) -> pd.DataFrame:
    """Return rows where a reported Total does not match the summed components.

    group_columns identifies one contest, e.g. ["county", "office",
    "district", "precinct"] to check candidate totals per precinct, or
    ["county", "office", "district", "candidate"] to check precinct totals
    per candidate. total_column is the *other* column: the one whose value
    is the literal string "Total" on the reported-total row.
    """
    working = data.copy()
    working["votes"] = pd.to_numeric(working["votes"], errors="coerce")
    reported = working[working[total_column] == "Total"].set_index(group_columns)
    components = working[(working[total_column] != "Total") & (working["precinct"] != "Total")]
    calculated = components.groupby(group_columns, dropna=False)["votes"].sum()
    comparison = reported[["votes"]].rename(columns={"votes": "reported_total"}).join(
        calculated.rename("calculated_total"), how="inner"
    )
    mismatches = comparison[comparison["reported_total"] != comparison["calculated_total"]].reset_index()
    return mismatches


def validate_file(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, low_memory=False, dtype={"precinct": str})
    candidate_totals = check_totals(data, ["county", "office", "district", "precinct"], "candidate")
    candidate_totals["check"] = "candidate_total_per_precinct"
    precinct_totals = check_totals(data, ["county", "office", "district", "candidate"], "precinct")
    precinct_totals["check"] = "precinct_total_per_candidate"
    return pd.concat([candidate_totals, precinct_totals], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    any_mismatch = False
    for path in args.paths:
        mismatches = validate_file(path)
        if mismatches.empty:
            print(f"{path.name}: OK, all totals reconcile")
        else:
            any_mismatch = True
            print(f"{path.name}: {len(mismatches)} mismatch(es)")
            print(mismatches.to_string(index=False))
    if any_mismatch:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_validate_oe_precinct_totals.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run it against all five synced OE files**

Run:
```powershell
python scripts/validate_oe_precinct_totals.py data/raw/openelections/20121106__al__general__precinct.csv `
  data/raw/openelections/20141104__al__general__precinct.csv `
  data/raw/openelections/20161108__al__general__precinct.csv `
  data/raw/openelections/20181106__al__general__precinct.csv `
  data/raw/openelections/20201103__al__general__precinct.csv
```
Expected: `OK, all totals reconcile` for each file, exit code 0. If any file
reports mismatches, record them — that is real, actionable information about
the OE source data's quality (this is one of the exact problems the rebuild
is meant to surface, not hide), and should be written up rather than
silenced.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_oe_precinct_totals.py scripts/tests/test_validate_oe_precinct_totals.py
git commit -m "Add automated total-checksum validation for synced OpenElections CSVs"
```

---

### Task 7: Generalized presidential-to-legislative-district allocation

**Files:**
- Create: `scripts/build_presidential_district_features.py`
- Test: `scripts/tests/test_build_presidential_district_features.py`

**Interfaces:**
- Consumes: `normalize_name`, `normalize_for_match` from `oe_normalize` (Task 2);
  `data/processed/war/precinct_district_allocation_weights.csv` (produced by
  `build_war_database.py`, Task 4); `data/processed/presidential/{year}_president_precinct.csv`
  (produced by Task 5) with columns `county_key, precinct_key, dem_votes, rep_votes, two_party_votes, pres_dem_margin`.
- Produces: `data/processed/presidential/{target_cycle}_district_presidential_features.csv`
  for `target_cycle` in `{2014, 2018, 2022}`, with columns `cycle, chamber, district,
  pres_{year}_dem_votes, pres_{year}_rep_votes, pres_{year}_two_party_votes,
  pres_{year}_dem_margin, pres_{year}_fallback_share` per source year, plus
  `pres_swing_2016_2020` for 2022 — matching exactly what
  `assemble_war_features.py` already reads.

This generalizes the precinct-name-matching algorithm already proven in the
current `build_2012_presidential_districts.py` (matching source-year precinct
names directly against the target cycle's own
`precinct_district_allocation_weights.csv`) to all four source/target pairs,
replacing that script plus `build_2012_president_vtd_crosswalk.py`,
`build_2012_president_on_2018_map.py`, and `build_vest_presidential_districts.py`
(whose live `build_spatial` used VEST-shapefile polygon overlay, and whose
unused `build` function was dead fuzzy-matching code — this task keeps only
the fuzzy-matching *technique*, applied uniformly, and drops the shapefile
dependency entirely for this feature).

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_build_presidential_district_features.py`:

```python
import pandas as pd

from build_presidential_district_features import allocate_to_districts, load_target_weights


def _weights_frame() -> pd.DataFrame:
    # Two precincts in one county, split between two House districts by
    # legislative-contest activity, mirroring precinct_district_allocation_weights.csv.
    return pd.DataFrame(
        [
            {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA", "precinct_key": "PRECINCT 1",
             "district": 10, "district_activity": 80, "precinct_activity": 100, "allocation_weight": 0.8},
            {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA", "precinct_key": "PRECINCT 1",
             "district": 11, "district_activity": 20, "precinct_activity": 100, "allocation_weight": 0.2},
            {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA", "precinct_key": "PRECINCT 2",
             "district": 11, "district_activity": 50, "precinct_activity": 50, "allocation_weight": 1.0},
        ]
    )


def _prepared_weights() -> pd.DataFrame:
    from build_presidential_district_features import _prepare_weights

    return _prepare_weights(_weights_frame(), target_cycle=2018)


def test_prepare_weights_filters_cycle_and_computes_share():
    weights = _prepared_weights()
    row10 = weights[(weights.target_match_norm == "PRECINCT 1") & (weights.district == 10)].iloc[0]
    assert round(row10.activity_share, 2) == 0.8


def test_allocate_to_districts_splits_precinct_by_activity_share():
    weights = _prepared_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "PRECINCT 1", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "PRECINCT 2", "dem_votes": 40.0, "rep_votes": 60.0},
        ]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2016)
    district = district.set_index(["chamber", "district"])

    # Precinct 1 (150 two-party votes) splits 80/20 across districts 10/11.
    assert round(district.loc[("house", 10), "pres_2016_dem_votes"], 2) == 80.0
    assert round(district.loc[("house", 10), "pres_2016_rep_votes"], 2) == 40.0
    # District 11 gets precinct 1's 20% share plus all of precinct 2.
    assert round(district.loc[("house", 11), "pres_2016_dem_votes"], 2) == 20.0 + 40.0
    assert round(district.loc[("house", 11), "pres_2016_rep_votes"], 2) == 10.0 + 60.0
    assert (matches.match_method == "exact").all()


def test_allocate_to_districts_falls_back_for_unmatched_precinct():
    weights = _prepared_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "PRECINCT 1", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "SOME BRAND NEW PRECINCT NAME", "dem_votes": 10.0, "rep_votes": 10.0},
        ]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2016)

    # The unmatched precinct's votes must still show up somewhere (as
    # fallback), not silently vanish.
    total_dem = district["pres_2016_dem_votes"].sum()
    assert round(total_dem, 2) == 110.0
    assert "unmatched" in matches.match_method.values
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest scripts/tests/test_build_presidential_district_features.py -v`
Expected: `ModuleNotFoundError: No module named 'build_presidential_district_features'`.

- [ ] **Step 3: Write `scripts/build_presidential_district_features.py`**

```python
"""Allocate precinct-level presidential votes onto legislative districts.

For each (source_year, target_cycle) pair, precinct names from the source
year's OpenElections President results are matched (county-scoped, exact or
high-confidence fuzzy) against the target cycle's own precinct
legislative-activity weights. Unmatched votes are distributed within county
according to the directly matched district shares and flagged as fallback.
This is the technique already used and trusted for the 2012-to-2014
allocation, generalized to every source/target pair so all four use the same
method instead of three different ones.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import normalize_for_match, normalize_name  # noqa: E402

TARGET_SOURCES: dict[int, list[int]] = {2014: [2012], 2018: [2016], 2022: [2016, 2020]}


def _prepare_weights(raw_weights: pd.DataFrame, target_cycle: int) -> pd.DataFrame:
    weights = raw_weights[raw_weights["cycle"].eq(target_cycle)].copy()
    weights["county_norm"] = weights["county_key"].map(normalize_name)
    weights["target_match_norm"] = weights["precinct_key"].map(normalize_for_match)
    weights["office"] = weights["chamber"].map({"house": "State House", "senate": "State Senate"})
    weights = (
        weights.groupby(["county_norm", "target_match_norm", "office", "district"], as_index=False)
        ["district_activity"].sum()
    )
    weights["target_activity"] = weights.groupby(
        ["county_norm", "target_match_norm", "office"]
    )["district_activity"].transform("sum")
    weights["activity_share"] = weights["district_activity"] / weights["target_activity"].where(
        weights["target_activity"] > 0
    )
    return weights


def load_target_weights(weights_path: Path, target_cycle: int) -> pd.DataFrame:
    raw_weights = pd.read_csv(weights_path)
    return _prepare_weights(raw_weights, target_cycle)


def _match_precincts(votes: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    targets = {
        county: sorted(group["target_match_norm"].dropna().unique())
        for county, group in weights.groupby("county_norm")
    }
    rows = []
    for row in votes.itertuples(index=False):
        choices = targets.get(row.county_norm, [])
        target = None
        method = "unmatched"
        score = margin = 0.0
        if row.match_norm in choices:
            target, method, score, margin = row.match_norm, "exact", 100.0, 100.0
        elif choices and row.match_norm:
            found = process.extract(row.match_norm, choices, scorer=fuzz.WRatio, limit=2)
            score = float(found[0][1])
            second = float(found[1][1]) if len(found) > 1 else 0.0
            margin = score - second
            if score >= 92 and margin >= 4:
                target, method = found[0][0], "fuzzy"
        rows.append({"source_row_id": row.source_row_id, "target_match_norm": target,
                     "match_method": method, "match_score": score, "score_margin": margin})
    return pd.DataFrame(rows)


def allocate_to_districts(
    votes: pd.DataFrame, weights: pd.DataFrame, source_year: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate precinct votes to legislative districts.

    votes: columns county_key, precinct_key, dem_votes, rep_votes (one row
    per source precinct). weights: output of load_target_weights()/`_prepare_weights`.
    Returns (district_features, matches): district_features has one row per
    (chamber, district) with pres_{source_year}_dem_votes/rep_votes/
    two_party_votes/dem_margin/fallback_share; matches is the per-precinct
    match diagnostic frame.
    """
    votes = votes.copy()
    votes["county_norm"] = votes["county_key"].map(normalize_name)
    votes["match_norm"] = votes["precinct_key"].map(normalize_for_match)
    votes["source_row_id"] = range(1, len(votes) + 1)

    matches = _match_precincts(votes[["county_norm", "match_norm", "source_row_id"]], weights)
    keyed = votes.merge(matches, on="source_row_id", validate="one_to_one")

    direct = keyed[keyed["target_match_norm"].notna()].merge(
        weights[["county_norm", "target_match_norm", "office", "district", "activity_share"]],
        on=["county_norm", "target_match_norm"], how="inner",
    )
    direct["dem_allocated"] = direct["dem_votes"] * direct["activity_share"]
    direct["rep_allocated"] = direct["rep_votes"] * direct["activity_share"]
    direct["allocation_method"] = "direct_precinct_activity"

    shares = (
        direct.groupby(["county_norm", "office", "district"], as_index=False)
        [["dem_allocated", "rep_allocated"]].sum()
    )
    shares["activity"] = shares["dem_allocated"] + shares["rep_allocated"]
    shares["county_activity"] = shares.groupby(["county_norm", "office"])["activity"].transform("sum")
    shares["fallback_share"] = shares["activity"] / shares["county_activity"].where(shares["county_activity"] > 0)

    expected = keyed.assign(_join=1).merge(
        pd.DataFrame({"office": ["State House", "State Senate"], "_join": [1, 1]}), on="_join"
    ).drop(columns="_join")
    direct_keys = direct[["source_row_id", "office"]].drop_duplicates().assign(_allocated=True)
    residual = expected.merge(direct_keys, on=["source_row_id", "office"], how="left")
    residual = residual[residual["_allocated"].isna()].drop(columns="_allocated")
    fallback = residual.merge(
        shares[["county_norm", "office", "district", "fallback_share"]],
        on=["county_norm", "office"], how="inner",
    )
    fallback["dem_allocated"] = fallback["dem_votes"] * fallback["fallback_share"]
    fallback["rep_allocated"] = fallback["rep_votes"] * fallback["fallback_share"]
    fallback["allocation_method"] = "county_distribution_fallback"

    allocations = pd.concat(
        [
            direct[["county_norm", "precinct_key", "office", "district", "dem_allocated", "rep_allocated", "allocation_method"]],
            fallback[["county_norm", "precinct_key", "office", "district", "dem_allocated", "rep_allocated", "allocation_method"]],
        ],
        ignore_index=True,
    )
    district = allocations.groupby(["office", "district"], as_index=False).agg(
        **{
            f"pres_{source_year}_dem_votes": ("dem_allocated", "sum"),
            f"pres_{source_year}_rep_votes": ("rep_allocated", "sum"),
        }
    )
    district[f"pres_{source_year}_two_party_votes"] = (
        district[f"pres_{source_year}_dem_votes"] + district[f"pres_{source_year}_rep_votes"]
    )
    district[f"pres_{source_year}_dem_margin"] = 100 * (
        district[f"pres_{source_year}_dem_votes"] - district[f"pres_{source_year}_rep_votes"]
    ) / district[f"pres_{source_year}_two_party_votes"]

    fallback_by_district = (
        allocations.assign(two_party=lambda x: x["dem_allocated"] + x["rep_allocated"])
        .query("allocation_method == 'county_distribution_fallback'")
        .groupby(["office", "district"], as_index=False)["two_party"].sum()
        .rename(columns={"two_party": "fallback_votes"})
    )
    district = district.merge(fallback_by_district, on=["office", "district"], how="left")
    district["fallback_votes"] = district["fallback_votes"].fillna(0)
    district[f"pres_{source_year}_fallback_share"] = (
        district["fallback_votes"] / district[f"pres_{source_year}_two_party_votes"]
    )
    district = district.drop(columns="fallback_votes")
    district["chamber"] = district["office"].map({"State House": "house", "State Senate": "senate"})
    district = district.drop(columns="office")
    return district, matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root
    weights_path = root / "data" / "processed" / "war" / "precinct_district_allocation_weights.csv"
    pres_dir = root / "data" / "processed" / "presidential"

    for target_cycle, source_years in TARGET_SOURCES.items():
        weights = load_target_weights(weights_path, target_cycle)
        combined: pd.DataFrame | None = None
        for source_year in source_years:
            votes = pd.read_csv(pres_dir / f"{source_year}_president_precinct.csv")
            district, matches = allocate_to_districts(votes, weights, source_year)
            matches.to_csv(pres_dir / f"{source_year}_to_{target_cycle}_precinct_match.csv", index=False)
            print(f"{source_year}->{target_cycle}: {matches.match_method.value_counts().to_dict()}")
            combined = district if combined is None else combined.merge(
                district, on=["chamber", "district"], how="outer", validate="one_to_one"
            )
        combined["cycle"] = target_cycle
        if target_cycle == 2022:
            combined["pres_swing_2016_2020"] = (
                combined["pres_2020_dem_margin"] - combined["pres_2016_dem_margin"]
            )
        combined.to_csv(pres_dir / f"{target_cycle}_district_presidential_features.csv", index=False)
        print(f"{target_cycle}: {len(combined)} district rows written")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_build_presidential_district_features.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run it for real**

Run: `python scripts/build_presidential_district_features.py`
Expected: prints match-method breakdowns and row counts for 2012->2014,
2016->2018, 2016->2022, 2020->2022, then writes
`data/processed/presidential/2014_district_presidential_features.csv`,
`2018_district_presidential_features.csv`, `2022_district_presidential_features.csv`
(140 rows each: 105 House + 35 Senate). Check the printed match-method
breakdown for each pair — a large `unmatched`/fallback share (compare against
the `fallback_votes`/`two_party_votes` ratio already implicit in prior QA
files such as `2012_president_district_allocation_qa.csv`) signals a
precinct-naming mismatch worth a closer look, especially for 2020->2022
(the cross-map-vintage case flagged as lower-confidence in the design doc).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_presidential_district_features.py scripts/tests/test_build_presidential_district_features.py \
        data/processed/presidential/2014_district_presidential_features.csv \
        data/processed/presidential/2018_district_presidential_features.csv \
        data/processed/presidential/2022_district_presidential_features.csv \
        data/processed/presidential/2012_to_2014_precinct_match.csv \
        data/processed/presidential/2016_to_2018_precinct_match.csv \
        data/processed/presidential/2016_to_2022_precinct_match.csv \
        data/processed/presidential/2020_to_2022_precinct_match.csv
git commit -m "Replace VTD-crosswalk and VEST-overlay presidential trend allocation with one matching method"
```

---

### Task 8: End-to-end rebuild and before/after diff

**Files:**
- None created — this task runs the full pipeline and produces a diff report.

**Interfaces:**
- Consumes: every script from Tasks 1-7, plus the unmodified downstream
  scripts `assemble_war_features.py` and `fit_preliminary_war_model.py`.

- [ ] **Step 1: Snapshot the pre-rebuild feature output**

Run: `git show HEAD:data/processed/war/war_model_features.csv > "$env:TEMP\war_model_features_before.csv"`
(or the Bash equivalent `git show HEAD:data/processed/war/war_model_features.csv > /tmp/war_model_features_before.csv`)

- [ ] **Step 2: Run the full rebuild pipeline in order**

Run:
```powershell
python scripts/build_war_database.py
python scripts/build_incumbency_features.py
python scripts/build_candidate_finance_features.py
python scripts/assemble_war_features.py
```
Expected: each script prints its normal summary output (coverage counts,
row counts) with no unhandled exceptions.

- [ ] **Step 3: Diff the feature table**

Run (PowerShell):
```powershell
python -c "
import pandas as pd
before = pd.read_csv(r'$env:TEMP\war_model_features_before.csv')
after = pd.read_csv('data/processed/war/war_model_features.csv')
key = ['cycle', 'chamber', 'district']
merged = before.merge(after, on=key, suffixes=('_before', '_after'), how='outer', indicator=True)
print('Rows only in before:', (merged._merge == 'left_only').sum())
print('Rows only in after:', (merged._merge == 'right_only').sum())
pres_cols = [c for c in before.columns if c.startswith('pres_')]
for col in pres_cols:
    if f'{col}_before' in merged.columns:
        diff = (merged[f'{col}_before'] - merged[f'{col}_after']).abs()
        print(f'{col}: max abs diff = {diff.max():.4f}, rows with diff > 0.5 = {(diff > 0.5).sum()}')
"
```
Expected: no rows only in before/after (same 420 district-cycle keys), and
report the max absolute difference for every `pres_*` column. Differences of
a few points are plausible and expected (the vote source changed from
VEST/raw-SoS-zip to OE for 2012/2016/2020); differences should be
concentrated in counties/districts with high `fallback_share`, not spread
uniformly across every district. Write the printed summary into this task's
completion notes for the code review step.

- [ ] **Step 4: Run the model fit and compare validation output**

Run: `python scripts/fit_preliminary_war_model.py`
Then: `git diff --stat data/processed/war/` to see the full list of changed
output files.
Expected: the script completes and reports fit statistics in the same
ballpark as `project_docs/model/MODEL_READINESS.md`'s current numbers (R-squared ~0.2,
MAE ~7-8 points) — a wildly different fit (e.g. R-squared collapsing to
near zero) signals a real problem in the rebuilt data, not an
acceptable consequence of switching sources.

- [ ] **Step 5: Do not commit yet**

Leave the working tree as-is (regenerated files, uncommitted) — Task 9
reviews and finalizes this in the same change set as the retirements.

---

### Task 9: Retire superseded scripts and derived artifacts

**Files:**
- Delete: the 8 scripts and 18 derived/manual data files listed in the File
  Structure section above.
- Modify: `project_docs/model/MODEL_READINESS.md`

**Interfaces:** None — this is cleanup after Task 8's diff has been reviewed
and accepted.

- [ ] **Step 1: Delete the superseded scripts**

```bash
git rm scripts/normalize_2012_president.py \
       scripts/build_2012_president_vtd_crosswalk.py \
       scripts/build_2012_president_on_2018_map.py \
       scripts/build_2012_presidential_districts.py \
       scripts/build_vest_presidential_districts.py \
       scripts/build_2014_precinct_crosswalk.py \
       scripts/build_2014_multisource_crosswalk.py \
       scripts/validate_2014_precinct_crosswalk.py
```

- [ ] **Step 2: Delete the now-orphaned derived/manual data files**

```bash
git rm data/manual/2014_precinct_geometry_overrides.csv \
       data/derived/crosswalks/2012_president_vtd_crosswalk.csv \
       data/derived/crosswalks/2012_president_vtd_summary.csv \
       data/derived/crosswalks/2012_president_vtd_vote_qa.csv \
       data/derived/crosswalks/2014_precinct_geometry_crosswalk_by_county.csv \
       data/derived/crosswalks/2014_precinct_geometry_crosswalk_consolidated.csv \
       data/derived/crosswalks/2014_precinct_geometry_crosswalk_summary.csv \
       data/derived/crosswalks/2014_precinct_geometry_unresolved.csv \
       data/derived/crosswalks/2014_precinct_legislative_district_activity.csv \
       data/derived/crosswalks/2014_precinct_vest16_crosswalk_validated.csv \
       data/derived/crosswalks/2014_precinct_vtd_crosswalk.csv \
       data/derived/crosswalks/2014_precinct_vtd_crosswalk_validated.csv \
       data/derived/crosswalks/2014_precinct_vtd_review.csv \
       data/derived/crosswalks/2014_precinct_vtd_review_enhanced.csv \
       data/derived/crosswalks/2014_precinct_vtd_summary.csv \
       data/derived/crosswalks/2014_precinct_vtd_summary_by_county.csv \
       data/derived/crosswalks/2014_precinct_vtd_validation_by_county.csv \
       data/derived/crosswalks/2014_precinct_vtd_validation_summary.csv
```

- [ ] **Step 3: Delete the stale intermediate presidential files no longer produced**

The old pipeline wrote several intermediate files that the new one doesn't
produce (superseded by `{year}_president_precinct.csv` and the
`{source}_to_{target}_precinct_match.csv` files from Tasks 5 and 7):

```bash
git rm data/processed/presidential/2012_on_2018_spatial_qa.csv \
       data/processed/presidential/2012_president_county_qa.csv \
       data/processed/presidential/2012_president_district_allocation_qa.csv \
       data/processed/presidential/2012_president_district_allocations.csv \
       data/processed/presidential/2016_spatial_allocation_qa.csv \
       data/processed/presidential/2018_district_presidential_2012_features.csv \
       data/processed/presidential/2018_district_presidential_2016_features.csv \
       data/processed/presidential/2020_spatial_allocation_qa.csv \
       data/processed/presidential/2022_district_presidential_2016_features.csv \
       data/processed/presidential/2022_district_presidential_2020_features.csv
```

- [ ] **Step 4: Update `project_docs/model/MODEL_READINESS.md`'s "Rebuild and validate" section**

Replace the script list (the fenced block under "## Rebuild and validate")
with:

```powershell
python scripts\sync_openelections_data.py
python scripts\validate_oe_precinct_totals.py data\raw\openelections\*.csv
python scripts\build_war_database.py
python scripts\build_oe_president_precinct.py --year 2012
python scripts\build_oe_president_precinct.py --year 2016
python scripts\build_oe_president_precinct.py --year 2020
python scripts\build_presidential_district_features.py
python scripts\build_incumbency_features.py
python scripts\build_candidate_finance_features.py
python scripts\assemble_war_features.py
python scripts\fit_preliminary_war_model.py
python scripts\compare_war_specifications.py
python scripts\build_war_review_queue.py
python scripts\validate_2018_official_legislative_totals.py
python scripts\validate_2022_wikipedia_legislative_totals.py
python scripts\audit_cycle_shift.py
python scripts\validate_war_outputs.py
```

Add one sentence above the block noting that precinct-level vote data for
2012, 2014, 2016, 2018, and 2020 now comes from a single source
(`openelections-data-al`, synced explicitly rather than copied by hand), with
2022 unchanged on the RDH pipeline.

- [ ] **Step 5: Stage the Task 8 regenerated outputs and this task's deletions together**

```bash
git add -A data/processed data/derived data/manual project_docs/model/MODEL_READINESS.md
git status
```
Review the output: it should show the Task 8 regenerated files as modified,
the Task 9 files as deleted, and nothing unexpected.

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
Retire superseded precinct/presidential pipeline scripts and derived crosswalks

Presidential trend features for 2012-2014, 2016-2018, 2016-2022, and
2020-2022 now go through the single build_presidential_district_features.py
matching technique instead of three different approaches (raw-SoS-zip
parsing, a VTD/polygon-overlay crosswalk, and VEST-shapefile overlay).
Regenerates data/processed/war and data/processed/presidential end to end.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Update `project_docs/model/MODEL_READINESS.md`'s "Current result" section**

Read the freshly printed output from Task 8 Steps 2 and 4 (row counts, fit
R-squared/MAE) and update the numbers in the "Current result" and
"Validation status" sections if they changed from what's currently written.
If they're unchanged within rounding, no edit is needed.

- [ ] **Step 8: Commit if Step 7 made changes**

```bash
git add project_docs/model/MODEL_READINESS.md
git commit -m "Update project_docs/model/MODEL_READINESS.md with post-rebuild validation numbers"
```
