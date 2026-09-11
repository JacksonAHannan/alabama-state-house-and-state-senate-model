#!/usr/bin/env python3
"""Append strictly gated Arkansas 1994-1998 rows to the validated Southern panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from build_historical_southern_legislative_panel import klarner_metadata


ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "data/processed/forecast_calibration/historical_southern_combined_panel.csv"
COMBINED_MANIFEST = ROOT / "data/processed/forecast_calibration/historical_southern_combined_manifest.json"
AR_DIR = ROOT / "data/processed/precinct_history/arkansas_pre2000"
AR_MANIFEST = AR_DIR / "arkansas_pre2000_manifest.json"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
OUTPUT = ROOT / "data/processed/forecast_calibration"
KEYS = ["state", "year", "chamber", "district"]
PRIORITY = {1994: "GOV", 1996: "USP", 1998: "USS"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def allocate_context(observations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    geo = ["state", "year", "county", "precinct"]
    legislative = observations.loc[observations["office"].isin(["SLDL", "SLDU"])].copy()
    legislative["chamber"] = legislative["office"].map({"SLDL": "house", "SLDU": "senate"})
    mapping = (legislative.groupby(geo + ["chamber", "district"], as_index=False)["votes"].sum()
               .rename(columns={"votes": "legislative_turnout"}))
    mapping["mapping_total"] = mapping.groupby(geo + ["chamber"])["legislative_turnout"].transform("sum")
    mapping["allocation_weight"] = mapping["legislative_turnout"] / mapping["mapping_total"].where(mapping["mapping_total"] > 0)

    context = observations.loc[observations["party"].isin(["DEM", "REP"])].copy()
    context = context.loc[context.apply(lambda row: PRIORITY.get(int(row["year"])) == row["office"], axis=1)]
    context = context.groupby(geo + ["office", "party"], as_index=False)["votes"].sum()
    joined = mapping.merge(context, on=geo, how="inner", validate="many_to_many")
    joined["allocated_votes"] = joined["votes"] * joined["allocation_weight"]

    district = joined.groupby(KEYS + ["office", "party"], as_index=False)["allocated_votes"].sum()
    wide = district.pivot(index=KEYS + ["office"], columns="party", values="allocated_votes").reset_index()
    wide = wide.rename(columns={"office": "baseline_office", "DEM": "baseline_dem_votes", "REP": "baseline_rep_votes"})
    for column in ["baseline_dem_votes", "baseline_rep_votes"]:
        if column not in wide:
            wide[column] = np.nan
    denom = wide["baseline_dem_votes"] + wide["baseline_rep_votes"]
    wide["baseline_dem_margin"] = 100 * (wide["baseline_dem_votes"] - wide["baseline_rep_votes"]) / denom.where(denom > 0)

    mapping_total = mapping.groupby(["state", "year", "chamber"], as_index=False)["legislative_turnout"].sum()
    mapping_total = mapping_total.rename(columns={"legislative_turnout": "source_legislative_turnout"})
    matched = joined.drop_duplicates(geo + ["chamber", "district", "office"])
    matched = matched.groupby(["state", "year", "chamber", "office"], as_index=False)["legislative_turnout"].sum()
    matched = matched.rename(columns={"office": "baseline_office", "legislative_turnout": "matched_legislative_turnout"})
    coverage = matched.merge(mapping_total, on=["state", "year", "chamber"], how="left")
    coverage["legislative_turnout_join_coverage"] = (
        coverage["matched_legislative_turnout"] / coverage["source_legislative_turnout"].where(
            coverage["source_legislative_turnout"] > 0
        )
    )
    source_context = context.groupby(["state", "year", "office", "party"], as_index=False)["votes"].sum()
    allocated = joined.groupby(["state", "year", "chamber", "office", "party"], as_index=False)["allocated_votes"].sum()
    conservation = allocated.merge(source_context, on=["state", "year", "office", "party"], how="left")
    conservation["context_footprint_share"] = conservation["allocated_votes"] / conservation["votes"].where(conservation["votes"] > 0)
    coverage = coverage.merge(
        conservation.groupby(["state", "year", "chamber", "office"], as_index=False).agg(
            allocated_context_votes=("allocated_votes", "sum"), statewide_context_votes=("votes", "sum"),
            minimum_party_context_footprint_share=("context_footprint_share", "min")
        ).rename(columns={"office": "baseline_office"}),
        on=["state", "year", "chamber", "baseline_office"], how="left",
    )
    return wide.merge(coverage, on=["state", "year", "chamber", "baseline_office"], how="left"), coverage


def build(combined_path: Path, ar_dir: Path, klarner_path: Path, output: Path) -> dict:
    observations = pd.read_csv(ar_dir / "arkansas_pre2000_precinct_observations.csv", low_memory=False)
    reconciliation = pd.read_csv(ar_dir / "arkansas_pre2000_legislative_reconciliation.csv", low_memory=False)
    baselines, coverage = allocate_context(observations)
    outcomes = klarner_metadata(klarner_path)
    outcomes = outcomes.loc[outcomes["state"].eq("AR") & outcomes["year"].isin(PRIORITY)]
    ar = outcomes.merge(baselines, on=KEYS, how="left", validate="one_to_one")
    gate = reconciliation[KEYS + ["model_eligible", "reconciliation_status"]].rename(
        columns={"model_eligible": "staging_reconciliation_gate"}
    )
    ar = ar.merge(gate, on=KEYS, how="left", validate="one_to_one")
    ar["dem_votes"] = ar["klarner_dem_votes"]
    ar["rep_votes"] = ar["klarner_rep_votes"]
    denom = ar["dem_votes"] + ar["rep_votes"]
    ar["legislative_dem_margin"] = 100 * (ar["dem_votes"] - ar["rep_votes"]) / denom.where(denom > 0)
    ar["raw_overperformance_vs_baseline"] = ar["legislative_dem_margin"] - ar["baseline_dem_margin"]
    ar["incumbency_balance"] = ar["dinc"].fillna(0) - ar["rinc"].fillna(0)
    ar["contested_two_party"] = ar["dem_votes"].gt(0) & ar["rep_votes"].gt(0)
    ar["coverage_gate"] = ar["legislative_turnout_join_coverage"].ge(0.95)
    ar["model_eligible_permissive"] = ar["contested_two_party"] & ar["baseline_dem_margin"].notna()
    ar["model_eligible"] = (ar["model_eligible_permissive"] & ar["coverage_gate"]
                            & ar["staging_reconciliation_gate"].fillna(False))
    ar["baseline_allocation_quality"] = np.where(ar["coverage_gate"], "sos_legislative_turnout_join_95pct", "partial_unresolved")
    ar["panel_source"] = "Arkansas SOS context + Klarner outcome"

    combined = pd.read_csv(combined_path, low_memory=False)
    strict = ar.loc[ar["model_eligible"]].copy()
    overlap = pd.MultiIndex.from_frame(combined[KEYS])
    strict = strict.loc[~pd.MultiIndex.from_frame(strict[KEYS]).isin(overlap)]
    extended = pd.concat([combined, strict], ignore_index=True, sort=False).sort_values(KEYS).reset_index(drop=True)

    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "arkansas_candidates": output / "historical_southern_extended_arkansas_candidates.csv",
        "arkansas_coverage": output / "historical_southern_extended_arkansas_coverage.csv",
        "panel": output / "historical_southern_extended_panel.csv",
    }
    ar.to_csv(paths["arkansas_candidates"], index=False)
    coverage.to_csv(paths["arkansas_coverage"], index=False)
    extended.to_csv(paths["panel"], index=False)
    script_path = Path(__file__).resolve()
    inputs = [COMBINED_MANIFEST, AR_MANIFEST, klarner_path]
    manifest = {
        "schema_version": 1,
        "pipeline": script_path.relative_to(ROOT).as_posix(),
        "code_commit": git_commit(),
        "inputs": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in inputs],
        "configuration": {"minimum_legislative_turnout_join_coverage": 0.95,
                          "context_priority_by_year": PRIORITY, "existing_panel_precedence": True},
        "row_counts": {"combined_input": len(combined), "arkansas_reconciled": int(ar["staging_reconciliation_gate"].fillna(False).sum()),
                       "arkansas_strict": len(strict), "extended": len(extended)},
    }
    manifest["outputs"] = [{"name": name, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                            "sha256": sha256(path)} for name, path in paths.items()]
    manifest["build_id"] = hashlib.sha256(
        (":".join(item["sha256"] for item in manifest["inputs"]) + ":" + sha256(script_path)).encode()
    ).hexdigest()[:20]
    (output / "historical_southern_extended_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined", type=Path, default=COMBINED)
    parser.add_argument("--arkansas-dir", type=Path, default=AR_DIR)
    parser.add_argument("--klarner", type=Path, default=KLARNER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(args.combined, args.arkansas_dir, args.klarner, args.output)
    print("Extended historical Southern panel:", result["row_counts"])


if __name__ == "__main__":
    main()
