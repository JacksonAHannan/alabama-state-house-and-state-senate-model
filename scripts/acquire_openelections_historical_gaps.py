#!/usr/bin/env python3
"""Acquire commit-pinned OpenElections files for verified historical gaps."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/openelections_historical_gaps"
MANIFEST = ROOT / "data/processed/source_audits/openelections_historical_gap_manifest.csv"
REPOSITORIES = {
    "AR": ("openelections-data-ar", "834ccef3cdcf64c8a381811e4d3ad02ec72ba336"),
    "GA": ("openelections-data-ga", "86bf341e68775bae06a54538dae0311fb6201872"),
    "MS": ("openelections-data-ms", "ed58cb2d2480744f02aac7a285b47d10676ff14d"),
    "MO": ("openelections-data-mo", "9d0ea2824c558a468ee8b44a11fc9910634a0379"),
    "SC": ("openelections-data-sc", "5e05b67e15f3614a20d31144df83248235cba6f2"),
}
EXPECTED_CYCLES = {
    "AR": {2008}, "GA": {2012, 2014, 2016},
    "MS": {2012},
    "MO": set(range(2000, 2019, 2)), "SC": {2006, 2020},
}
MO_DATES = {2000: "20001107", 2002: "20021105", 2004: "20041102", 2006: "20061107",
            2008: "20081104", 2010: "20101102", 2012: "20121106", 2014: "20141104",
            2016: "20161108", 2018: "20181106"}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def selected_member(state: str, path: str) -> bool:
    normalized = path.lower()
    if not normalized.endswith(".csv") or "general" not in normalized or "primary" in normalized or "special" in normalized:
        return False
    year = int(normalized[:4]) if normalized[:4].isdigit() else -1
    if year not in EXPECTED_CYCLES[state]:
        return False
    if state == "AR":
        return path == "2008/20081104__ar__general__precinct.csv"
    if state == "SC":
        return path in {
            "2006/20061107__sc__general__precinct.csv",
            "2020/20201103__sc__general__precinct.csv",
        }
    if state == "MO":
        return path == f"{year}/{MO_DATES[year]}__mo__general__precinct.csv"
    if state == "MS":
        return path == "2012/20121106__ms__general__precinct.csv"
    if state == "GA" and year == 2012:
        return path == "2012/20121106__ga__general.csv"
    if state == "GA" and year == 2014:
        return path == "2014/20141104__ga__general__precinct-level_UNOFFICIAL.csv"
    if state == "GA" and year == 2016:
        return path.startswith("2016/20161108__ga__general__") and path.endswith("__precinct.csv")
    return False


def repository_tree(repo: str, commit: str) -> list[str]:
    url = f"https://api.github.com/repos/openelections/{repo}/git/trees/{commit}"
    response = requests.get(url, params={"recursive": "1"}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if payload.get("truncated"):
        raise RuntimeError(f"GitHub tree response truncated for {repo}@{commit}")
    return [entry["path"] for entry in payload["tree"] if entry.get("type") == "blob"]


def acquire() -> pd.DataFrame:
    old = pd.read_csv(MANIFEST) if MANIFEST.exists() else pd.DataFrame()
    old_times = dict(zip(old.get("local_path", []), old.get("retrieved_at", [])))
    rows = []
    for state, (repo, commit) in REPOSITORIES.items():
        members = [path for path in repository_tree(repo, commit) if selected_member(state, path)]
        found_cycles = {int(path[:4]) for path in members}
        if found_cycles != EXPECTED_CYCLES[state]:
            raise RuntimeError(f"{state}: expected cycles {EXPECTED_CYCLES[state]}, found {found_cycles}")
        for source_path in sorted(members):
            year = int(source_path[:4])
            raw_url = f"https://raw.githubusercontent.com/openelections/{repo}/{commit}/{source_path}"
            response = requests.get(raw_url, timeout=120)
            response.raise_for_status()
            content = response.content
            target = RAW / state / source_path
            local = str(target.relative_to(ROOT)).replace("\\", "/")
            if target.exists():
                existing = target.read_bytes()
                if existing != content:
                    raise RuntimeError(f"Refusing to overwrite unequal immutable raw file: {target}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            retrieved = old_times.get(local) or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            rows.append({
                "state": state, "election_year": year, "election_stage": "general",
                "granularity": "precinct", "provider": "OpenElections", "repository": repo,
                "commit": commit, "source_path": source_path, "raw_url": raw_url,
                "retrieved_at": retrieved, "local_path": local, "size_bytes": len(content),
                "sha256": sha256_bytes(content),
                "authority_status": "secondary_validation_source",
                "source_status": "unofficial_label" if "UNOFFICIAL" in source_path else "repository_normalized",
            })
    frame = pd.DataFrame(rows).sort_values(["state", "election_year", "source_path"])
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(MANIFEST, index=False)
    return frame


def main() -> None:
    frame = acquire()
    print(f"OpenElections historical acquisition: files={len(frame):,}, state_cycles={frame[['state','election_year']].drop_duplicates().shape[0]}")


if __name__ == "__main__":
    main()
