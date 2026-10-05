"""National generic-ballot environment from the Silver Bulletin polling average.

Owner decision 2026-10-05: the 2026 forecast's national environment is the Silver
Bulletin generic congressional ballot average, as published in the tracker's public
daily-average chart.

`--fetch` downloads the chart's current dataset and stores it as a new dated raw
snapshot. An existing snapshot is never overwritten. Every snapshot is recorded in
the manifest with its URL, retrieval time and hash. Without `--fetch`, the latest
registered snapshot is used.

The tracker reports Democratic and Republican shares. The forecast's environment
is a two-party margin, matching its 2024 anchor, so the margin here is
100 * (D - R) / (D + R). Only the public chart data is used. The tracker's poll-level
spreadsheet is a subscriber download and is not read.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "polling" / "silver_bulletin_generic_ballot"
MANIFEST = RAW / "manifest.csv"
OUT = ROOT / "data" / "processed" / "polling"
PAGE = "https://www.natesilver.net/p/generic-ballot-average-2026-nate-silver-bulletin-congress-polls"
CHART = "https://datawrapper.dwcdn.net/rfiFi/"
SOURCE = "Silver Bulletin generic congressional ballot average (public daily-average chart)"
COLUMNS = ["modeldate", "dem", "rep", "dem_lo", "dem_hi", "rep_lo", "rep_hi"]
MANIFEST_FIELDS = ["file", "source_page", "chart_url", "dataset_url", "retrieved_at_utc", "sha256", "rows",
                   "first_date", "last_date", "terms", "note"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_series(path: Path) -> pd.DataFrame:
    """The daily average, one row per model date, with the two-party margin."""
    frame = pd.read_csv(path)
    if list(frame.columns[:len(COLUMNS)]) != COLUMNS:
        raise ValueError(f"Unexpected Silver Bulletin chart columns: {list(frame.columns)}")
    frame["date"] = pd.to_datetime(frame.modeldate, format="%m/%d/%Y")
    if frame.date.duplicated().any():
        raise ValueError("Silver Bulletin series repeats a model date")
    for column in ("dem", "rep"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not frame[column].between(0, 100).all():
            raise ValueError(f"Silver Bulletin {column} share outside 0-100")
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["dem_raw_margin"] = frame.dem - frame.rep
    frame["dem_two_party_share"] = frame.dem / (frame.dem + frame.rep)
    frame["dem_two_party_margin"] = 100 * (frame.dem - frame.rep) / (frame.dem + frame.rep)
    return frame


def fetch() -> Path:
    """Download the chart's current dataset as a new dated snapshot and register it."""
    session = requests.Session()
    session.headers["User-Agent"] = "Jackson-Hannan-Alabama-forecast/1.0 (polling environment)"
    page = session.get(CHART, timeout=60)
    page.raise_for_status()
    versions = re.findall(r"datawrapper\.dwcdn\.net/rfiFi/(\d+)", page.text)
    version = max(map(int, versions)) if versions else None
    dataset_url = f"{CHART}{version}/dataset.csv" if version else f"{CHART}dataset.csv"
    response = session.get(dataset_url, timeout=60)
    response.raise_for_status()
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / f"silver_bulletin_generic_ballot_average_retrieved_{retrieved[:10]}.csv"
    if target.exists():
        if target.read_bytes() == response.content:
            return target
        target = RAW / f"silver_bulletin_generic_ballot_average_retrieved_{retrieved.replace(':', '')}.csv"
    target.write_bytes(response.content)
    series = parse_series(target)
    row = {"file": target.name, "source_page": PAGE, "chart_url": f"{CHART}{version}/" if version else CHART,
           "dataset_url": dataset_url, "retrieved_at_utc": retrieved, "sha256": sha256(target),
           "rows": len(series), "first_date": series.date.min().date().isoformat(),
           "last_date": series.date.max().date().isoformat(),
           "terms": "Silver Bulletin public chart data; terms not reviewed; data/raw is git-ignored and not redistributed",
           "note": "Daily topline average shown on the tracker page; subscriber poll-level data not used"}
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow(row)
    return target


def latest_snapshot() -> tuple[Path, dict]:
    if not MANIFEST.exists():
        raise FileNotFoundError("No registered Silver Bulletin snapshot; run with --fetch")
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    row = max(rows, key=lambda r: r["retrieved_at_utc"])
    path = RAW / row["file"]
    if sha256(path) != row["sha256"]:
        raise ValueError(f"Registered Silver Bulletin snapshot changed on disk: {path.name}")
    return path, row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="download and register a new dated snapshot first")
    args = parser.parse_args()
    if args.fetch:
        fetch()
    path, registered = latest_snapshot()
    series = parse_series(path)
    latest = series.iloc[-1]
    OUT.mkdir(parents=True, exist_ok=True)
    series[["date", "dem", "rep", "dem_raw_margin", "dem_two_party_share", "dem_two_party_margin"]].assign(
        date=series.date.dt.date.astype(str)).to_csv(OUT / "silver_bulletin_generic_ballot_series.csv", index=False)
    environment = pd.DataFrame([{
        "as_of": latest.date.date().isoformat(), "dem_pct": float(latest.dem), "rep_pct": float(latest.rep),
        "dem_raw_margin": float(latest.dem_raw_margin), "dem_two_party_share": float(latest.dem_two_party_share),
        "dem_two_party_margin": float(latest.dem_two_party_margin), "source": SOURCE,
        "source_page": registered["source_page"], "snapshot_file": registered["file"],
        "snapshot_sha256": registered["sha256"], "retrieved_at_utc": registered["retrieved_at_utc"],
    }])
    environment.to_csv(OUT / "silver_bulletin_generic_ballot_environment.csv", index=False)
    (OUT / "silver_bulletin_generic_ballot_manifest.json").write_text(json.dumps({
        "source": SOURCE, "snapshot": registered,
        "outputs": {name: sha256(OUT / name) for name in (
            "silver_bulletin_generic_ballot_series.csv", "silver_bulletin_generic_ballot_environment.csv")},
        "two_party_margin_rule": "100 * (dem - rep) / (dem + rep)",
    }, indent=2) + "\n", encoding="utf-8")
    print(environment.drop(columns=["source_page", "snapshot_sha256"]).to_string(index=False))


if __name__ == "__main__":
    main()
