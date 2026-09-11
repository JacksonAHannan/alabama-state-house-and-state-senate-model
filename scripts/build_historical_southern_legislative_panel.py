#!/usr/bin/env python3
"""Build an experimental historical Southern legislative comparison panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HEDA = ROOT / "data/processed/precinct_history/heda"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
OUTPUT = ROOT / "data/processed/forecast_calibration"
STATE_NAMES = {
    "Alabama": "AL", "Arkansas": "AR", "Florida": "FL", "Georgia": "GA",
    "Kentucky": "KY", "Louisiana": "LA", "Mississippi": "MS", "Missouri": "MO",
    "North Carolina": "NC", "Oklahoma": "OK", "South Carolina": "SC",
    "Tennessee": "TN", "Texas": "TX", "Virginia": "VA",
}
BASELINE_PRIORITY = {"USP": 1, "USS": 2, "GOV": 3}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def allocate_context(legislative: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    """Allocate precinct context to legislative fragments using legislative turnout shares."""
    keys = ["state", "year", "source_member", "source_row"]
    fragments = legislative.copy()
    party_sum = fragments[["dem_votes", "rep_votes"]].sum(axis=1, min_count=1)
    fragments["allocation_proxy"] = fragments["total_votes"].where(fragments["total_votes"].gt(0), party_sum)
    precinct_chamber = keys + ["chamber"]
    fragments["fragment_count"] = fragments.groupby(precinct_chamber)["district_slot"].transform("size")
    fragments["proxy_sum"] = fragments.groupby(precinct_chamber)["allocation_proxy"].transform("sum", min_count=1)
    fragments["allocation_weight"] = fragments["allocation_proxy"] / fragments["proxy_sum"].where(
        fragments["proxy_sum"].gt(0)
    )
    fragments.loc[fragments["fragment_count"].eq(1), "allocation_weight"] = 1.0
    keep = keys + ["chamber", "district", "district_slot", "fragment_count", "allocation_weight"]
    selected = context.loc[context["office"].isin(BASELINE_PRIORITY)].copy()
    if "contest_slot" not in selected:
        selected["contest_slot"] = 1
    merged = fragments[keep].merge(selected, on=keys, how="inner", validate="many_to_many", suffixes=("", "_context"))
    context_group = keys + ["chamber", "office", "contest_slot"]
    merged["context_group_weight_sum"] = merged.groupby(context_group)["allocation_weight"].transform("sum", min_count=1)
    merged["context_group_missing_weight"] = merged.groupby(context_group)["allocation_weight"].transform(
        lambda values: values.isna().any()
    )
    merged["allocation_complete"] = (
        ~merged["context_group_missing_weight"]
        & merged["context_group_weight_sum"].sub(1).abs().le(1e-9)
    )
    merged["context_group_id"] = merged[context_group].astype(str).agg("|".join, axis=1)
    for party in ("dem", "rep", "total"):
        merged[f"allocated_{party}_votes"] = merged[f"{party}_votes"] * merged["allocation_weight"]
    merged["allocation_method"] = np.select(
        [~merged["allocation_complete"], merged["fragment_count"].eq(1)],
        ["unallocatable", "whole_precinct"], default="legislative_turnout_share"
    )
    return merged


def aggregate_baselines(allocated: pd.DataFrame) -> pd.DataFrame:
    group = ["state", "year", "chamber", "district", "office"]
    sums = allocated.groupby(group, as_index=False).agg(
        baseline_dem_votes=("allocated_dem_votes", lambda values: values.sum(min_count=1)),
        baseline_rep_votes=("allocated_rep_votes", lambda values: values.sum(min_count=1)),
        context_fragment_rows=("source_row", "size"),
        split_context_rows=("fragment_count", lambda values: int((values > 1).sum())),
        expected_context_groups=("context_group_id", "nunique"),
    )
    # The groupby lambda above counts rows for completeness; replace the
    # allocated-group count with an explicit distinct complete-group count.
    complete = (allocated.loc[allocated["allocation_complete"]]
                .groupby(group)["context_group_id"].nunique().rename("allocated_context_groups"))
    incomplete = (allocated.loc[~allocated["allocation_complete"]]
                  .groupby(group)["context_group_id"].nunique().rename("incomplete_context_groups"))
    sums = sums.merge(complete, on=group, how="left").merge(incomplete, on=group, how="left")
    sums["allocated_context_groups"] = sums["allocated_context_groups"].fillna(0).astype(int)
    sums["incomplete_context_groups"] = sums["incomplete_context_groups"].fillna(0).astype(int)
    denominator = sums["baseline_dem_votes"] + sums["baseline_rep_votes"]
    sums["baseline_dem_margin"] = 100 * (sums["baseline_dem_votes"] - sums["baseline_rep_votes"]) / denominator.where(
        denominator > 0
    )
    sums["baseline_priority"] = sums["office"].map(BASELINE_PRIORITY)
    sums = sums.sort_values(["state", "year", "chamber", "district", "baseline_priority"])
    preferred = sums.drop_duplicates(["state", "year", "chamber", "district"], keep="first").copy()
    preferred["baseline_allocation_quality"] = np.select(
        [preferred["incomplete_context_groups"].gt(0), preferred["split_context_rows"].eq(0)],
        ["partial_unresolved", "whole_precincts"], default="includes_turnout_share_allocation"
    )
    return preferred.drop(columns="baseline_priority")


def klarner_metadata(path: Path) -> pd.DataFrame:
    with ZipFile(path) as bundle:
        contests = pd.read_csv(bundle.open("202slers_uoa_contest20230810.csv"), low_memory=False)
        candidates = pd.read_csv(bundle.open("208slers_uoa_cand_contest20230810.csv"), low_memory=False)
    contests = contests.loc[contests["state"].isin(STATE_NAMES) & contests["year"].between(1994, 2016)].copy()
    contests["state"] = contests["state"].map(STATE_NAMES)
    contests["chamber"] = contests["sen"].map({0: "house", 1: "senate"})
    contests["district"] = pd.to_numeric(contests["dno"], errors="coerce").astype("Int64")
    keys = ["state", "year", "chamber", "district"]
    contests["klarner_dem_votes"] = pd.to_numeric(contests["dvote"], errors="coerce")
    contests["klarner_rep_votes"] = pd.to_numeric(contests["rvote"], errors="coerce")
    metadata = contests[keys + ["klarner_dem_votes", "klarner_rep_votes", "dinc", "rinc", "dswitch", "rswitch", "uncont", "dontuse", "bigthird"]]
    metadata = metadata.dropna(subset=["chamber", "district"]).drop_duplicates(keys)

    candidates = candidates.loc[
        candidates["state"].isin(STATE_NAMES)
        & candidates["year"].between(1994, 2016)
        & candidates["partyt"].isin(["d", "r"])
    ].copy()
    candidates["state"] = candidates["state"].map(STATE_NAMES)
    candidates["chamber"] = candidates["sen"].map({0: "house", 1: "senate"})
    candidates["district"] = pd.to_numeric(candidates["dno"], errors="coerce").astype("Int64")
    candidates["vote_sort"] = pd.to_numeric(candidates["vote"], errors="coerce").fillna(-1)
    candidates = candidates.sort_values("vote_sort", ascending=False).drop_duplicates(keys + ["partyt"])
    names = candidates.pivot(index=keys, columns="partyt", values="cand").reset_index().rename(
        columns={"d": "dem_candidate", "r": "rep_candidate"}
    )
    return metadata.merge(names, on=keys, how="outer", validate="one_to_one")


def build(heda_dir: Path, klarner_path: Path, output_dir: Path) -> dict[str, int]:
    heda_dir, klarner_path, output_dir = heda_dir.resolve(), klarner_path.resolve(), output_dir.resolve()
    legislative = pd.read_csv(heda_dir / "heda_legislative_precinct_fragments.csv.gz", low_memory=False)
    context = pd.read_csv(heda_dir / "heda_precinct_context.csv.gz", low_memory=False)
    districts = pd.read_csv(heda_dir / "heda_legislative_district_totals.csv")
    legislative = legislative.loc[legislative["year"].between(1994, 2016)].copy()
    context = context.loc[context["year"].between(1994, 2016)].copy()
    districts = districts.loc[districts["year"].between(1994, 2016)].copy()

    allocated = allocate_context(legislative, context)
    baselines = aggregate_baselines(allocated)
    metadata = klarner_metadata(klarner_path)
    keys = ["state", "year", "chamber", "district"]
    districts = districts.rename(columns={
        "dem_votes": "heda_dem_votes", "rep_votes": "heda_rep_votes",
        "total_votes": "heda_total_votes", "dem_margin": "heda_dem_margin",
    })
    panel = districts.merge(baselines, on=keys, how="left", validate="one_to_one")
    panel = panel.merge(metadata, on=keys, how="left", validate="one_to_one")
    # HEDA district sums remain reconciliation evidence. Model outcomes use the
    # independent contest totals and never infer a held contest from stray
    # precinct fragments in an uncontested or staggered district.
    panel["dem_votes"] = panel["klarner_dem_votes"]
    panel["rep_votes"] = panel["klarner_rep_votes"]
    denominator = panel["dem_votes"] + panel["rep_votes"]
    panel["legislative_dem_margin"] = 100 * (panel["dem_votes"] - panel["rep_votes"]) / denominator.where(denominator > 0)
    panel["raw_overperformance_vs_baseline"] = panel["legislative_dem_margin"] - panel["baseline_dem_margin"]
    panel["incumbency_balance"] = panel["dinc"].fillna(0) - panel["rinc"].fillna(0)
    panel["contested_two_party"] = panel["dem_votes"].gt(0) & panel["rep_votes"].gt(0)
    panel["model_eligible_permissive"] = panel["contested_two_party"] & panel["baseline_dem_margin"].notna()
    panel["model_eligible"] = panel["model_eligible_permissive"] & panel["incomplete_context_groups"].fillna(0).eq(0)
    panel["heda_dem_vote_delta"] = panel["heda_dem_votes"] - panel["klarner_dem_votes"]
    panel["heda_rep_vote_delta"] = panel["heda_rep_votes"] - panel["klarner_rep_votes"]
    panel["result_source"] = "Klarner district contest totals"
    panel["baseline_source"] = "HEDA precinct context allocated to legislative districts"

    coverage = panel.groupby(["state", "year", "chamber"], as_index=False).agg(
        district_rows=("district", "size"),
        contested_two_party=("contested_two_party", "sum"),
        baseline_rows=("baseline_dem_margin", "count"),
        candidate_name_rows=("dem_candidate", lambda values: int(values.notna().sum())),
        split_allocated_rows=("baseline_allocation_quality", lambda values: int(values.eq("includes_turnout_share_allocation").sum())),
        model_eligible=("model_eligible", "sum"),
    )
    coverage["baseline_coverage"] = coverage["baseline_rows"] / coverage["district_rows"]

    output_dir.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_dir / "historical_southern_heda_panel.csv", index=False)
    coverage.to_csv(output_dir / "historical_southern_heda_coverage.csv", index=False)
    allocated.groupby(["state", "year", "chamber", "office", "allocation_method"], as_index=False).agg(
        rows=("source_row", "size"), allocated_dem_votes=("allocated_dem_votes", "sum"),
        allocated_rep_votes=("allocated_rep_votes", "sum")
    ).to_csv(output_dir / "historical_southern_heda_allocation_audit.csv", index=False)
    output_files = [
        output_dir / "historical_southern_heda_panel.csv",
        output_dir / "historical_southern_heda_coverage.csv",
        output_dir / "historical_southern_heda_allocation_audit.csv",
    ]
    heda_manifest = heda_dir / "build_manifest.json"
    script_path = Path(__file__).resolve()
    manifest = {
        "schema_version": 1,
        "build_id": hashlib.sha256(
            f"{sha256(heda_manifest)}:{sha256(klarner_path)}:{sha256(script_path)}".encode()
        ).hexdigest()[:20],
        "code_commit": git_commit(),
        "pipeline": display_path(script_path),
        "configuration": {"years": [1994, 2016], "baseline_priority": BASELINE_PRIORITY,
                          "strict_eligibility_rejects_partial_allocation": True},
        "inputs": [
            {"path": display_path(heda_manifest), "sha256": sha256(heda_manifest)},
            {"path": display_path(klarner_path), "sha256": sha256(klarner_path)},
        ],
        "outputs": [{"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in output_files],
        "row_counts": {"panel": len(panel), "coverage": len(coverage), "model_eligible": int(panel["model_eligible"].sum()),
                       "permissive_eligible": int(panel["model_eligible_permissive"].sum())},
    }
    (output_dir / "historical_southern_heda_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "panel_rows": len(panel),
        "baseline_rows": int(panel["baseline_dem_margin"].notna().sum()),
        "contested_rows": int(panel["contested_two_party"].sum()),
        "model_eligible_rows": int(panel["model_eligible"].sum()),
        "coverage_rows": len(coverage),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heda-dir", type=Path, default=HEDA)
    parser.add_argument("--klarner", type=Path, default=KLARNER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    counts = build(args.heda_dir, args.klarner, args.output)
    print("Historical Southern HEDA panel:", ", ".join(f"{key}={value:,}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
