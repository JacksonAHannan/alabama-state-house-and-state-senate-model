"""Run the canonical identity build against a scratch copy of the warehouse and diff.

Investigation only: the live warehouse is opened read-only for the copy and the
diff; every write goes to the scratch copy or this artifacts directory.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
HERE = Path(__file__).resolve().parent
LIVE = ROOT / "data/processed/elections/alabama_elections.sqlite"
SCRATCH = HERE / "scratch_warehouse.sqlite"
KEYS = ["year", "chamber", "district", "canonical_party"]

started = time.time()
if not SCRATCH.exists():
    source = sqlite3.connect(f"file:{LIVE.as_posix()}?mode=ro", uri=True)
    source.execute("PRAGMA query_only=ON")
    destination = sqlite3.connect(SCRATCH)
    source.backup(destination)
    assert destination.execute("PRAGMA quick_check").fetchall() == [("ok",)]
    destination.close(); source.close()
print(f"scratch ready {time.time() - started:.0f}s")

import build_candidate_identity as bci  # noqa: E402

bci.DB = SCRATCH
bci.OUT = HERE / "identity_outputs"
bci.OUT.mkdir(exist_ok=True)
import warehouse  # noqa: E402

warehouse.DEFAULT_DB = SCRATCH
import os  # noqa: E402

os.environ["ALABAMA_WAREHOUSE_PATH"] = str(SCRATCH)
bci.main()
print(f"identity build on scratch done {time.time() - started:.0f}s")

live = sqlite3.connect(f"file:{LIVE.as_posix()}?mode=ro", uri=True)
live.execute("PRAGMA query_only=ON")
before = pd.read_sql_query("SELECT * FROM canonical_candidates", live)
live.close()
after = pd.read_sql_query("SELECT * FROM canonical_candidates", sqlite3.connect(f"file:{SCRATCH.as_posix()}?mode=ro", uri=True))
before["district"] = before.district.astype(int); after["district"] = after.district.astype(int)
merged = before.merge(after, on=KEYS, how="outer", indicator=True, suffixes=("_live", "_scratch"))
added = merged[merged._merge == "right_only"]
removed = merged[merged._merge == "left_only"]
both = merged[merged._merge == "both"].copy()
both["votes_delta"] = both.canonical_votes_scratch - both.canonical_votes_live
changed_votes = both[both.votes_delta.abs() > 1e-9]
changed_name = both[both.canonical_name_live != both.canonical_name_scratch]
changed_id = both[both.canonical_candidate_id_live != both.canonical_candidate_id_scratch]
changed_inc = both[both.incumbent_live != both.incumbent_scratch]
summary = {
    "live_rows": len(before), "scratch_rows": len(after),
    "added": added[KEYS + ["canonical_name_scratch", "canonical_votes_scratch", "canonical_source_scratch"]].to_dict("records"),
    "removed": removed[KEYS + ["canonical_name_live", "canonical_votes_live", "canonical_source_live"]].to_dict("records"),
    "changed_votes": changed_votes[KEYS + ["canonical_name_live", "canonical_votes_live", "canonical_votes_scratch", "votes_delta"]].sort_values("votes_delta", key=abs, ascending=False).to_dict("records"),
    "changed_votes_by_year": changed_votes.groupby("year").size().to_dict(),
    "changed_name_count": len(changed_name), "changed_id_count": len(changed_id), "changed_incumbent_count": len(changed_inc),
    "changed_ids_by_year": changed_id.groupby("year").size().to_dict(),
    "elapsed_seconds": round(time.time() - started, 1),
}
(HERE / "identity_rebuild_diff.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
merged.to_csv(HERE / "identity_rebuild_diff_full.csv", index=False)
print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, indent=1, default=str))
print("added", len(added), "removed", len(removed), "changed_votes", len(changed_votes))
