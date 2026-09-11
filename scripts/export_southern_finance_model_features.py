#!/usr/bin/env python3
"""Export leakage-safe, missingness-aware race finance features from the warehouse."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"
OUTPUT = ROOT / "data/processed/finance/southern_race_finance_model_features.csv"
MANIFEST = ROOT / "data/processed/finance/southern_race_finance_model_features_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(database: Path = DATABASE) -> pd.DataFrame:
    with sqlite3.connect(database) as connection:
        frame = pd.read_sql_query("""
            SELECT state_code AS state, cycle AS year,
                   CASE chamber WHEN 'lower' THEN 'house' WHEN 'upper' THEN 'senate' END AS chamber,
                   CAST(district AS INTEGER) AS district,
                   democratic_fundraising, republican_fundraising,
                   democratic_finance_status, republican_finance_status,
                   finance_complete, log_fundraising_ratio_d_to_r,
                   smoothing_constant, race_finance_status,
                   build_run_id AS finance_warehouse_run_id
            FROM fact_southern_race_finance
            ORDER BY state_code,cycle,chamber,CAST(district AS INTEGER)
        """, connection)
    complete = frame.finance_complete.eq(1)
    frame["finance_missing"] = (~complete).astype(int)
    frame["finance_model_eligible"] = complete.astype(int)
    feature_columns = [
        "democratic_fundraising", "republican_fundraising",
        "log_fundraising_ratio_d_to_r",
    ]
    frame.loc[~complete, feature_columns] = pd.NA
    if frame.duplicated(["state", "year", "chamber", "district"]).any():
        raise RuntimeError("model-facing finance race keys are not unique")
    if frame.loc[~complete, feature_columns].notna().any().any():
        raise RuntimeError("incomplete races received numeric finance features")
    return frame


def main() -> None:
    frame = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "pipeline": Path(__file__).relative_to(ROOT).as_posix(),
        "pipeline_sha256": sha256(Path(__file__)),
        "database": DATABASE.relative_to(ROOT).as_posix(),
        "warehouse_run_ids": sorted(frame.finance_warehouse_run_id.dropna().unique().tolist()),
        "output": OUTPUT.relative_to(ROOT).as_posix(),
        "output_sha256": sha256(OUTPUT),
        "rows": len(frame),
        "complete_races": int(frame.finance_complete.sum()),
        "feature_contract": "same-cycle two-calendar-year D/R finance; null unless both sides are observed and identity-accepted",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"finance model features: rows={len(frame):,}, complete={int(frame.finance_complete.sum()):,}")


if __name__ == "__main__":
    main()
