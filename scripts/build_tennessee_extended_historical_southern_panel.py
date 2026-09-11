#!/usr/bin/env python3
"""Append strictly gated Tennessee 1998 rows to the validated Southern panel."""

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
PANEL = ROOT / "data/processed/forecast_calibration/historical_southern_extended_panel.csv"
PANEL_MANIFEST = ROOT / "data/processed/forecast_calibration/historical_southern_extended_manifest.json"
TN_DIR = ROOT / "data/processed/precinct_history/tennessee_1998"
TN_MANIFEST = TN_DIR / "tennessee_1998_manifest.json"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
OUTPUT = ROOT / "data/processed/forecast_calibration"
KEYS = ["state", "year", "chamber", "district"]


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


def key(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.upper().str.replace(r"[^A-Z0-9]+", "", regex=True)


def allocate(legislative: pd.DataFrame, governor: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for frame in [legislative, governor]:
        frame["precinct_key"] = key(frame["precinct"])
    geo = ["state", "year", "county", "precinct_key"]
    mapping = legislative.groupby(geo + ["chamber", "district"], as_index=False)["legislative_turnout"].sum()
    source = mapping.groupby(["state", "year", "chamber", "district"], as_index=False)["legislative_turnout"].sum()
    # A zero-turnout legislative OCR row contains no defensible allocation
    # signal. Retain it in source coverage, but never use it to allocate votes.
    mapping = mapping.loc[mapping["legislative_turnout"].gt(0)].copy()
    mapping["mapping_total"] = mapping.groupby(geo + ["chamber"])["legislative_turnout"].transform("sum")
    mapping["allocation_weight"] = mapping["legislative_turnout"] / mapping["mapping_total"].where(mapping["mapping_total"] > 0)
    context = governor.melt(id_vars=geo, value_vars=["dem_votes", "rep_votes"], var_name="party", value_name="votes")
    context["party"] = context["party"].map({"dem_votes": "D", "rep_votes": "R"})
    context = context.groupby(geo + ["party"], as_index=False)["votes"].sum()
    joined = mapping.merge(context, on=geo, how="inner", validate="many_to_many")
    joined["allocated_votes"] = joined["votes"] * joined["allocation_weight"]

    allocation_audit = joined.groupby(geo + ["chamber", "party"], as_index=False).agg(
        source_votes=("votes", "first"),
        allocated_votes=("allocated_votes", "sum"),
        allocation_weight_sum=("allocation_weight", "sum"),
    )
    allocation_audit["allocation_difference"] = (
        allocation_audit["allocated_votes"] - allocation_audit["source_votes"]
    )

    district = joined.groupby(KEYS + ["party"], as_index=False)["allocated_votes"].sum()
    wide = district.pivot(index=KEYS, columns="party", values="allocated_votes").reset_index()
    wide = wide.rename(columns={"D": "baseline_dem_votes", "R": "baseline_rep_votes"})
    denom = wide["baseline_dem_votes"] + wide["baseline_rep_votes"]
    wide["baseline_dem_margin"] = 100 * (wide["baseline_dem_votes"] - wide["baseline_rep_votes"]) / denom.where(denom > 0)
    wide["baseline_office"] = "GOV"

    matched = joined.drop_duplicates(geo + ["chamber", "district"])
    matched = matched.groupby(["state", "year", "chamber", "district"], as_index=False)["legislative_turnout"].sum()
    matched = matched.rename(columns={"legislative_turnout": "matched_legislative_turnout"})
    coverage = source.merge(matched, on=KEYS, how="left")
    coverage["matched_legislative_turnout"] = coverage["matched_legislative_turnout"].fillna(0)
    coverage["legislative_turnout_join_coverage"] = (
        coverage["matched_legislative_turnout"] / coverage["legislative_turnout"].where(coverage["legislative_turnout"] > 0)
    )
    wide = wide.merge(coverage, on=KEYS, how="left")
    return wide, coverage, allocation_audit


def build(panel_path: Path, tn_dir: Path, klarner_path: Path, output: Path) -> dict:
    legislative = pd.read_csv(tn_dir / "tennessee_1998_legislative_precinct_turnout.csv", low_memory=False)
    governor = pd.read_csv(tn_dir / "tennessee_1998_governor_precinct.csv", low_memory=False)
    reconciliation = pd.read_csv(tn_dir / "tennessee_1998_legislative_reconciliation.csv", low_memory=False)
    baselines, coverage, allocation_audit = allocate(legislative, governor)
    outcomes = klarner_metadata(klarner_path)
    outcomes = outcomes.loc[outcomes["state"].eq("TN") & outcomes["year"].eq(1998)]
    tn = outcomes.merge(baselines, on=KEYS, how="left", validate="one_to_one")
    gate = reconciliation[KEYS + ["model_eligible", "reconciliation_status"]].rename(
        columns={"model_eligible": "staging_reconciliation_gate"}
    )
    tn = tn.merge(gate, on=KEYS, how="left", validate="one_to_one")
    tn["dem_votes"] = tn["klarner_dem_votes"]
    tn["rep_votes"] = tn["klarner_rep_votes"]
    denom = tn["dem_votes"] + tn["rep_votes"]
    tn["legislative_dem_margin"] = 100 * (tn["dem_votes"] - tn["rep_votes"]) / denom.where(denom > 0)
    tn["raw_overperformance_vs_baseline"] = tn["legislative_dem_margin"] - tn["baseline_dem_margin"]
    tn["incumbency_balance"] = tn["dinc"].fillna(0) - tn["rinc"].fillna(0)
    tn["contested_two_party"] = tn["dem_votes"].gt(0) & tn["rep_votes"].gt(0)
    tn["coverage_gate"] = tn["legislative_turnout_join_coverage"].ge(0.95)
    tn["model_eligible_permissive"] = tn["contested_two_party"] & tn["baseline_dem_margin"].notna()
    tn["model_eligible"] = (tn["model_eligible_permissive"] & tn["coverage_gate"]
                            & tn["staging_reconciliation_gate"].fillna(False))
    tn["baseline_allocation_quality"] = np.where(tn["coverage_gate"], "tn_ocr_turnout_join_95pct", "partial_unresolved")
    tn["panel_source"] = "Tennessee SOS OCR context + Klarner outcome"

    panel = pd.read_csv(panel_path, low_memory=False)
    strict = tn.loc[tn["model_eligible"]].copy()
    overlap = pd.MultiIndex.from_frame(panel[KEYS])
    strict = strict.loc[~pd.MultiIndex.from_frame(strict[KEYS]).isin(overlap)]
    extended = pd.concat([panel, strict], ignore_index=True, sort=False).sort_values(KEYS).reset_index(drop=True)

    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "tennessee_candidates": output / "historical_southern_extended_tn_candidates.csv",
        "tennessee_coverage": output / "historical_southern_extended_tn_coverage.csv",
        "tennessee_allocation_audit": output / "historical_southern_extended_tn_allocation_audit.csv",
        "panel": output / "historical_southern_extended_v2_panel.csv",
    }
    tn.to_csv(paths["tennessee_candidates"], index=False)
    coverage.to_csv(paths["tennessee_coverage"], index=False)
    allocation_audit.to_csv(paths["tennessee_allocation_audit"], index=False)
    extended.to_csv(paths["panel"], index=False)
    inputs = [
        panel_path,
        PANEL_MANIFEST,
        tn_dir / "tennessee_1998_legislative_precinct_turnout.csv",
        tn_dir / "tennessee_1998_governor_precinct.csv",
        tn_dir / "tennessee_1998_legislative_reconciliation.csv",
        tn_dir / "tennessee_1998_manifest.json",
        klarner_path,
    ]
    script_path = Path(__file__).resolve()
    manifest = {"schema_version": 1, "pipeline": script_path.relative_to(ROOT).as_posix(), "code_commit": git_commit(),
                "inputs": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in inputs],
                "configuration": {"minimum_legislative_turnout_join_coverage": 0.95,
                                  "baseline_office": "GOV", "existing_panel_precedence": True,
                                  "precinct_join": "canonical county + alphanumeric OCR label"},
                "row_counts": {"panel_input": len(panel),
                               "tennessee_reconciled": int(tn["staging_reconciliation_gate"].fillna(False).sum()),
                               "tennessee_strict": len(strict), "extended": len(extended)}}
    manifest["outputs"] = [{"name": name, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                            "sha256": sha256(path)} for name, path in paths.items()]
    manifest["build_id"] = hashlib.sha256(
        (":".join(item["sha256"] for item in manifest["inputs"]) + ":" + sha256(script_path)).encode()
    ).hexdigest()[:20]
    (output / "historical_southern_extended_v2_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PANEL)
    parser.add_argument("--tennessee-dir", type=Path, default=TN_DIR)
    parser.add_argument("--klarner", type=Path, default=KLARNER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(args.panel, args.tennessee_dir, args.klarner, args.output)
    print("Tennessee-extended Southern panel:", result["row_counts"])


if __name__ == "__main__":
    main()
