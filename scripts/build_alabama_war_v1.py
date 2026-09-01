#!/usr/bin/env python3
"""Publish Alabama-only race-residual WAR from the validated Southern v3 run."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/war/post2016_southern_war_v3"
OUT = ROOT / "data/processed/war/alabama_war_v1"
CONTRACT = ROOT / "project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md"
METHOD = ROOT / "project_docs/model/ALABAMA_WAR_V1.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    races = pd.read_csv(SOURCE / "race_war.csv", low_memory=False)
    candidates = pd.read_csv(SOURCE / "candidate_cycle_war.csv", low_memory=False)
    races = races[races.state_code.eq("AL")].sort_values(["cycle", "chamber", "district"]).reset_index(drop=True)
    candidates = candidates[candidates.state_code.eq("AL")].sort_values(
        ["cycle", "chamber", "district", "canonical_party"]
    ).reset_index(drop=True)

    if races.empty or set(races.cycle) != {2018, 2022}:
        raise RuntimeError("Alabama WAR must contain the strict 2018 and 2022 post-2016 cycles")
    if races.duplicated(["cycle", "chamber", "district"]).any():
        raise RuntimeError("Duplicate Alabama race key")
    if candidates.duplicated(["cycle", "chamber", "district", "canonical_party"]).any():
        raise RuntimeError("Duplicate Alabama candidate-cycle key")
    formula_error = (races.war - (races.raw_gap - races.fitted_structural_expected_gap)).abs().max()
    if float(formula_error) > 1e-9:
        raise RuntimeError(f"WAR formula error: {formula_error}")
    orientation = candidates.pivot(
        index=["cycle", "chamber", "district"], columns="canonical_party", values="candidate_cycle_war"
    )
    orientation_error = (orientation["D"] + orientation["R"]).abs().max()
    if len(candidates) != 2 * len(races) or float(orientation_error) > 1e-9:
        raise RuntimeError("Candidate-cycle WAR is not a complete, opposite-signed race differential")

    race_path = OUT / "race_war.csv"
    candidate_path = OUT / "candidate_cycle_war.csv"
    coverage_path = OUT / "coverage.csv"
    races.to_csv(race_path, index=False)
    candidates.to_csv(candidate_path, index=False)
    coverage = races.groupby(["cycle", "chamber"], as_index=False).agg(
        races=("district", "size"), mean_war=("war", "mean"), mean_absolute_war=("war", lambda x: x.abs().mean())
    )
    coverage.to_csv(coverage_path, index=False)

    generated = datetime.now(timezone.utc).isoformat()
    run_token = hashlib.sha256(
        (sha256(SOURCE / "race_war.csv") + sha256(SOURCE / "candidate_cycle_war.csv") + sha256(CONTRACT)).encode()
    ).hexdigest()[:20].upper()
    run_id = f"AL-WAR-V1-{run_token}"
    for frame in (races, candidates):
        frame["alabama_war_run_id"] = run_id
    # Keep the copied source rows byte-stable; the Alabama run id is recorded in the manifest.
    outputs = [race_path, candidate_path, coverage_path]
    manifest = {
        "methodology_version": "alabama_war_v1_race_residual",
        "alabama_war_run_id": run_id,
        "source_model_run_id": source_manifest["model_run_id"],
        "generated_at_utc": generated,
        "git_commit": git_commit(),
        "configuration": {
            "state_code": "AL",
            "cutoff_rule": "cycle > 2016",
            "war_definition": "raw_gap - fitted_structural_expected_gap",
            "candidate_pooling": False,
            "finance_in_war": False,
        },
        "diagnostics": {
            "race_rows": int(len(races)),
            "candidate_cycle_rows": int(len(candidates)),
            "cycles": sorted(races.cycle.astype(int).unique().tolist()),
            "max_war_formula_error": float(formula_error),
            "max_candidate_orientation_error": float(orientation_error),
        },
        "input_hashes": {
            str((SOURCE / "race_war.csv").relative_to(ROOT)).replace("\\", "/"): sha256(SOURCE / "race_war.csv"),
            str((SOURCE / "candidate_cycle_war.csv").relative_to(ROOT)).replace("\\", "/"): sha256(SOURCE / "candidate_cycle_war.csv"),
            str(CONTRACT.relative_to(ROOT)).replace("\\", "/"): sha256(CONTRACT),
        },
        "outputs": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "rows": int(sum(1 for _ in path.open(encoding="utf-8")) - 1),
                "sha256": sha256(path),
            }
            for path in outputs
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    METHOD.write_text(
        f"# Alabama WAR v1\n\n"
        f"Run: `{run_id}`\n\nSource Southern run: `{source_manifest['model_run_id']}`\n\nGenerated: `{generated}`\n\n"
        "Alabama WAR is the race-level residual from the post-2016 Southern structural model. "
        "For every contested Democratic-versus-Republican Alabama general election after 2016:\n\n"
        "`WAR = actual legislative-minus-federal gap - fitted structural expected gap`\n\n"
        "The Democratic candidate receives the race residual and the Republican receives its negative. "
        "There is no candidate pooling, career average, or fundraising adjustment in WAR. The same-cycle "
        "fit is a retrospective rating; cross-cycle forecast errors are separate.\n\n"
        f"Coverage is {len(races)} races and {len(candidates)} candidate-cycle rows across 2018 and 2022.\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(races)} Alabama race WAR rows and {len(candidates)} candidate-cycle rows ({run_id})")


if __name__ == "__main__":
    main()
