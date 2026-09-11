#!/usr/bin/env python3
"""Acquire and select election-day generic-ballot national environment.

Raw downloads are content-addressed and never replaced.  Each acquisition
writes a timestamped manifest containing the source locator, retrieval time,
hash, terms locator, cycle scope, and authoritative scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/polling/generic_ballot_environment"
OUT = ROOT / "data/processed/polling/virginia_generic_ballot_environment.csv"
AUDIT = ROOT / "data/processed/source_audits/virginia_generic_ballot_environment_manifest.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/128 Safari/537.36"
)
SOURCES = (
    {
        "source_id": "fivethirtyeight_old_model",
        "url": (
            "https://raw.githubusercontent.com/fivethirtyeight/data/master/"
            "polls/old_model/generic_ballot_averages_old_model.csv"
        ),
        "provider": "FiveThirtyEight",
        "terms": "https://github.com/fivethirtyeight/data/blob/master/LICENSE",
        "scope": "FiveThirtyEight generic-ballot polling averages through the 2022 cycle",
    },
    {
        "source_id": "fivethirtyeight_2023_archived_snapshot",
        "url": (
            "https://raw.githubusercontent.com/kr0710/Data607/"
            "0c5c987e9715020c9f0d88d0ca1bc067358ac55e/"
            "generic_ballot_averages.csv"
        ),
        "provider": "FiveThirtyEight data, commit-pinned third-party archive",
        "terms": "https://github.com/fivethirtyeight/data/blob/master/LICENSE",
        "scope": "Archived copy of FiveThirtyEight generic-ballot averages including 2023",
    },
)
ELECTION_DATES = {2019: "2019-11-05", 2023: "2023-11-07"}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def acquire() -> tuple[list[dict], dict[str, Path]]:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "manifests").mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    records: list[dict] = []
    paths: dict[str, Path] = {}
    for source in SOURCES:
        response = session.get(source["url"], timeout=60)
        response.raise_for_status()
        digest = sha256_bytes(response.content)
        path = RAW / f"{source['source_id']}_{digest[:16]}.csv"
        if path.exists() and sha256_file(path) != digest:
            raise ValueError(f"Immutable raw path has unexpected content: {path}")
        if not path.exists():
            path.write_bytes(response.content)
        paths[source["source_id"]] = path
        records.append(
            {
                **source,
                "retrieved_at_utc": retrieved,
                "sha256": digest,
                "local_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "media_type": response.headers.get("content-type", "text/csv"),
                "geographic_vintage": "national polling environment",
                "election_cycle": "2018-2024",
                "authoritative_scope": source["scope"],
            }
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest = RAW / "manifests" / f"acquisition_{stamp}.csv"
    pd.DataFrame(records).to_csv(manifest, index=False)
    return records, paths


def build(records: list[dict], paths: dict[str, Path]) -> pd.DataFrame:
    official = pd.read_csv(paths["fivethirtyeight_old_model"])
    archive = pd.read_csv(paths["fivethirtyeight_2023_archived_snapshot"])
    inputs = {
        2019: (official, "fivethirtyeight_old_model"),
        2023: (archive, "fivethirtyeight_2023_archived_snapshot"),
    }
    source_map = {record["source_id"]: record for record in records}
    rows = []
    for cycle, election_date in ELECTION_DATES.items():
        frame, source_id = inputs[cycle]
        dated = frame.copy()
        dated["date"] = pd.to_datetime(dated["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        selected = dated[dated.date.eq(election_date)].copy()
        estimates = selected.groupby("candidate").pct_estimate.first().to_dict()
        dem = estimates.get("Democrats")
        rep = estimates.get("Republicans")
        if dem is None or rep is None:
            raise ValueError(f"No complete D/R generic-ballot average for {election_date}")
        source = source_map[source_id]
        rows.append(
            {
                "cycle": cycle,
                "as_of_date": election_date,
                "democratic_estimate": float(dem),
                "republican_estimate": float(rep),
                "democratic_margin": float(dem) - float(rep),
                "polling_measure": "FiveThirtyEight generic congressional ballot polling average",
                "source_id": source_id,
                "source_url": source["url"],
                "source_local_path": source["local_path"],
                "source_sha256": source["sha256"],
                "temporal_rule": "estimate dated on the state legislative general-election date",
                "geographic_scope": "United States national",
                "validation_status": "passed",
            }
        )
    result = pd.DataFrame(rows).sort_values("cycle")
    if result.duplicated("cycle").any() or set(result.cycle) != set(ELECTION_DATES):
        raise AssertionError("Generic-ballot environment violates cycle uniqueness")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pipeline": "scripts/acquire_generic_ballot_environment.py",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "baseline_policy": (
                    "Use a same-year observed ticket baseline when one exists; otherwise use "
                    "the election-day national generic congressional ballot polling average."
                ),
                "inputs": records,
                "output": str(OUT.relative_to(ROOT)).replace("\\", "/"),
                "output_sha256": sha256_file(OUT),
                "rows": len(result),
                "missing_value_policy": "No interpolation and no zero fill.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    records, paths = acquire()
    result = build(records, paths)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
