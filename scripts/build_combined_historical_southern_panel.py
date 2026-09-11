#!/usr/bin/env python3
"""Combine validated HEDA and strictly gated OpenElections historical panels."""

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
HEDA_PANEL = ROOT / "data/processed/forecast_calibration/historical_southern_heda_panel.csv"
HEDA_MANIFEST = ROOT / "data/processed/forecast_calibration/historical_southern_heda_manifest.json"
OE_DIR = ROOT / "data/processed/precinct_history/openelections"
OE_MANIFEST = OE_DIR / "build_manifest.json"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
OUTPUT = ROOT / "data/processed/forecast_calibration"
KEYS = ["state", "year", "chamber", "district"]
PRIORITY = {"USP": 1, "USS": 2, "GOV": 3}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def clean_key(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().str.replace(r"[^a-z0-9]+", "", regex=True)


def allocate_oe_baselines(legislative: pd.DataFrame, context: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    geo = ["state", "year", "county_key", "ward_key", "precinct_key"]
    mapping = legislative.groupby(geo + ["office", "district"], as_index=False)["votes"].sum().rename(
        columns={"office": "chamber", "votes": "legislative_turnout"}
    )
    mapping["mapping_total"] = mapping.groupby(geo + ["chamber"])["legislative_turnout"].transform("sum")
    mapping["allocation_weight"] = mapping["legislative_turnout"] / mapping["mapping_total"].where(mapping["mapping_total"] > 0)
    context_party = context.loc[context["party"].isin(["D", "R"])].groupby(
        geo + ["office", "party"], as_index=False
    )["votes"].sum()
    joined = mapping.merge(context_party, on=geo, how="inner", validate="many_to_many")
    joined["allocated_votes"] = joined["votes"] * joined["allocation_weight"]
    district = joined.groupby(KEYS + ["office", "party"], as_index=False)["allocated_votes"].sum()
    district = district.rename(columns={"office": "baseline_office"})
    wide = district.pivot(index=KEYS + ["baseline_office"], columns="party", values="allocated_votes").reset_index()
    wide = wide.rename(columns={"D": "baseline_dem_votes", "R": "baseline_rep_votes"})
    for field in ("baseline_dem_votes", "baseline_rep_votes"):
        if field not in wide:
            wide[field] = pd.NA
    denom = wide["baseline_dem_votes"] + wide["baseline_rep_votes"]
    wide["baseline_dem_margin"] = 100 * (wide["baseline_dem_votes"] - wide["baseline_rep_votes"]) / denom.where(denom > 0)

    total = context_party.groupby(["state", "year", "office", "party"], as_index=False)["votes"].sum()
    allocated = joined.groupby(["state", "year", "chamber", "office", "party"], as_index=False)["allocated_votes"].sum()
    coverage = allocated.merge(total, left_on=["state", "year", "office", "party"],
                               right_on=["state", "year", "office", "party"], how="left")
    coverage["vote_coverage"] = coverage["allocated_votes"] / coverage["votes"].where(coverage["votes"] > 0)
    coverage_summary = coverage.groupby(["state", "year", "chamber", "office"], as_index=False).agg(
        minimum_party_vote_coverage=("vote_coverage", "min"), allocated_votes=("allocated_votes", "sum"),
        source_votes=("votes", "sum"),
    ).rename(columns={"office": "baseline_office"})
    mapping_totals = mapping.groupby(["state", "year", "chamber"], as_index=False)["legislative_turnout"].sum().rename(
        columns={"legislative_turnout": "source_legislative_turnout"}
    )
    matched_keys = geo + ["chamber", "district", "office"]
    matched = joined.drop_duplicates(matched_keys).groupby(
        ["state", "year", "chamber", "office"], as_index=False
    )["legislative_turnout"].sum().rename(
        columns={"office": "baseline_office", "legislative_turnout": "matched_legislative_turnout"}
    )
    coverage_summary = coverage_summary.merge(mapping_totals, on=["state", "year", "chamber"], how="left")
    coverage_summary = coverage_summary.merge(matched, on=["state", "year", "chamber", "baseline_office"], how="left")
    coverage_summary["legislative_turnout_join_coverage"] = (
        coverage_summary["matched_legislative_turnout"] / coverage_summary["source_legislative_turnout"].where(
            coverage_summary["source_legislative_turnout"] > 0
        )
    )
    wide = wide.merge(coverage_summary, on=["state", "year", "chamber", "baseline_office"], how="left")
    wide["priority"] = wide["baseline_office"].map(PRIORITY)
    preferred = wide.sort_values(KEYS + ["priority"]).drop_duplicates(KEYS).drop(columns="priority")
    return preferred, coverage_summary


def strict_cycle_gate(row: pd.Series) -> bool:
    if row["state"] == "MO" and row["year"] != 2014:
        if row["year"] == 2012 and row["chamber"] == "house" and row["district"] == 150:
            return False
        return True
    if row["state"] == "GA" and row["year"] in {2012, 2016}:
        if row["chamber"] == "senate" and ((row["year"] == 2012 and row["district"] == 30)
                                             or (row["year"] == 2016 and row["district"] == 13)):
            return False
        return True
    return False


def build(heda_path: Path, oe_dir: Path, klarner_path: Path, output: Path) -> dict[str, int]:
    legislative = pd.read_csv(oe_dir / "openelections_legislative_precinct_candidate.csv.gz", low_memory=False)
    context = pd.read_csv(oe_dir / "openelections_context_precinct_candidate.csv.gz", low_memory=False)
    for frame in (legislative, context):
        frame["county_key"] = clean_key(frame["county"])
        frame["ward_key"] = clean_key(frame["ward"])
        frame["precinct_key"] = clean_key(frame["precinct"])
    baselines, coverage = allocate_oe_baselines(legislative, context)
    outcomes = klarner_metadata(klarner_path)
    oe = outcomes.merge(baselines, on=KEYS, how="inner", validate="one_to_one")
    oe["dem_votes"] = oe["klarner_dem_votes"]
    oe["rep_votes"] = oe["klarner_rep_votes"]
    denom = oe["dem_votes"] + oe["rep_votes"]
    oe["legislative_dem_margin"] = 100 * (oe["dem_votes"] - oe["rep_votes"]) / denom.where(denom > 0)
    oe["raw_overperformance_vs_baseline"] = oe["legislative_dem_margin"] - oe["baseline_dem_margin"]
    oe["incumbency_balance"] = oe["dinc"].fillna(0) - oe["rinc"].fillna(0)
    oe["contested_two_party"] = oe["dem_votes"].gt(0) & oe["rep_votes"].gt(0)
    oe["cycle_gate"] = oe.apply(strict_cycle_gate, axis=1)
    oe["coverage_gate"] = oe["legislative_turnout_join_coverage"].ge(0.95)
    oe["model_eligible_permissive"] = oe["contested_two_party"] & oe["baseline_dem_margin"].notna()
    oe["model_eligible"] = oe["model_eligible_permissive"] & oe["cycle_gate"] & oe["coverage_gate"]
    oe["baseline_allocation_quality"] = np.where(oe["coverage_gate"], "oe_legislative_turnout_join_95pct", "partial_unresolved")
    oe["panel_source"] = "OpenElections context + Klarner outcome"

    heda = pd.read_csv(heda_path, low_memory=False)
    heda = heda.loc[heda["model_eligible"].eq(True)].copy()
    heda["panel_source"] = "HEDA context + Klarner outcome"
    oe_strict = oe.loc[oe["model_eligible"]].copy()
    overlap = pd.MultiIndex.from_frame(heda[KEYS])
    oe_strict = oe_strict.loc[~pd.MultiIndex.from_frame(oe_strict[KEYS]).isin(overlap)].copy()
    combined = pd.concat([heda, oe_strict], ignore_index=True, sort=False).sort_values(KEYS).reset_index(drop=True)

    output.mkdir(parents=True, exist_ok=True)
    paths = [output / "historical_southern_combined_oe_candidates.csv",
             output / "historical_southern_combined_oe_coverage.csv",
             output / "historical_southern_combined_panel.csv"]
    oe.to_csv(paths[0], index=False)
    coverage.to_csv(paths[1], index=False)
    combined.to_csv(paths[2], index=False)
    script_path = Path(__file__).resolve()
    manifest = {
        "schema_version": 1,
        "build_id": hashlib.sha256(f"{sha256(HEDA_MANIFEST)}:{sha256(OE_MANIFEST)}:{sha256(script_path)}".encode()).hexdigest()[:20],
        "code_commit": git_commit(), "pipeline": str(script_path.relative_to(ROOT)).replace("\\", "/"),
        "inputs": [{"path": str(HEDA_MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(HEDA_MANIFEST)},
                   {"path": str(OE_MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(OE_MANIFEST)}],
        "configuration": {"oe_minimum_legislative_turnout_join_coverage": 0.95, "heda_precedence_on_overlap": True,
                          "strict_cycle_exclusions": ["GA2014 unofficial", "AR2008 context-only", "SC2006 context-only",
                                                      "MO2014 no context", "MO2012 HD150", "GA2012 SD30", "GA2016 SD13"]},
        "row_counts": {"heda_strict": len(heda), "oe_strict_before_overlap": int(oe["model_eligible"].sum()),
                       "oe_added": len(oe_strict), "combined": len(combined)},
        "outputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size,
                     "sha256": sha256(path)} for path in paths],
    }
    (output / "historical_southern_combined_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest["row_counts"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heda", type=Path, default=HEDA_PANEL)
    parser.add_argument("--oe-dir", type=Path, default=OE_DIR)
    parser.add_argument("--klarner", type=Path, default=KLARNER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    counts = build(args.heda, args.oe_dir, args.klarner, args.output)
    print("Combined historical Southern panel:", ", ".join(f"{key}={value:,}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
