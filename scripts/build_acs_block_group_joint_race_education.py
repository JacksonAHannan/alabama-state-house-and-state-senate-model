"""Derive block-group race x education cells from official ACS controls.

Race-specific education tables are tract-only. This script combines those
tract controls with block-group race and education marginals using IPF. Output
cells are modeled small-area estimates, not directly published ACS estimates.
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "acs" / "block_group_joint"
OUT = ROOT / "data" / "processed" / "demographics"
YEARS = (2022, 2024)
SPECS = {
    "b15003": ("1400000US01", "1500000US01"),
    "b03002": ("1500000US01",),
    "c15002b": ("1400000US01",),
    "c15002h": ("1400000US01",),
}
BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat"


def pull(year: int, table: str, prefixes: tuple[str, ...]) -> tuple[Path, dict]:
    url = BASE.format(year=year, table=table)
    response = requests.get(url, stream=True, timeout=180)
    response.raise_for_status(); response.encoding = "utf-8"
    lines = response.iter_lines(decode_unicode=True)
    kept = [next(lines)]
    for line in lines:
        if line.startswith(prefixes):
            kept.append(line)
    payload = ("\n".join(kept) + "\n").encode()
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"acs5_{year}_{table}_alabama.dat"
    path.write_bytes(payload)
    return path, {"acs_vintage": year, "table": table.upper(), "source_url": url,
                  "retrieved_on": date.today().isoformat(), "sha256": hashlib.sha256(payload).hexdigest(),
                  "rows": len(kept)-1, "local_path": str(path.relative_to(ROOT))}


def read(year: int, table: str) -> pd.DataFrame:
    return pd.read_csv(RAW / f"acs5_{year}_{table}_alabama.dat", sep="|", dtype={"GEO_ID": str})


def ipf(seed: np.ndarray, rows: np.ndarray, columns: np.ndarray, iterations: int = 200) -> np.ndarray:
    seed = np.maximum(seed.astype(float), 1e-9)
    if rows.sum() <= 0:
        return np.zeros_like(seed)
    columns = np.maximum(columns.astype(float), 0)
    columns *= rows.sum() / columns.sum() if columns.sum() > 0 else 0
    matrix = seed.copy()
    for _ in range(iterations):
        matrix *= np.divide(rows, matrix.sum(axis=1), out=np.zeros_like(rows), where=matrix.sum(axis=1)>0)[:, None]
        matrix *= np.divide(columns, matrix.sum(axis=0), out=np.zeros_like(columns), where=matrix.sum(axis=0)>0)[None, :]
    return matrix


def college(frame: pd.DataFrame, prefix: str) -> pd.Series:
    if prefix == "B15003":
        return frame[[f"{prefix}_E{i:03d}" for i in range(22, 26)]].sum(axis=1)
    return frame[f"{prefix}_E006"] + frame[f"{prefix}_E011"]


def derive(year: int) -> pd.DataFrame:
    education = read(year, "b15003")
    bg_education = education[education.GEO_ID.str.startswith("150")].copy()
    tract_education = education[education.GEO_ID.str.startswith("140")].copy()
    bg_race = read(year, "b03002")
    black = read(year, "c15002b")
    white = read(year, "c15002h")

    bg = bg_education[["GEO_ID", "B15003_E001"]].copy()
    bg["college"] = college(bg_education, "B15003")
    bg["noncollege"] = bg.B15003_E001 - bg.college
    bg = bg.merge(bg_race[["GEO_ID", "B03002_E003", "B03002_E004", "B03002_E001"]], on="GEO_ID")
    suffix = bg.GEO_ID.str.split("US").str[-1]
    bg["block_group_geoid"] = suffix
    bg["tract_geoid"] = suffix.str[:11]
    bg["white_seed"] = bg.B03002_E003
    bg["black_seed"] = bg.B03002_E004
    bg["other_seed"] = (bg.B03002_E001 - bg.white_seed - bg.black_seed).clip(lower=0)

    tract = tract_education[["GEO_ID", "B15003_E001"]].copy()
    tract["all_college"] = college(tract_education, "B15003")
    tract = tract.merge(white, on="GEO_ID").merge(black, on="GEO_ID")
    tract["white_total"] = tract.C15002H_E001
    tract["white_college"] = college(tract, "C15002H")
    tract["black_total"] = tract.C15002B_E001
    tract["black_college"] = college(tract, "C15002B")
    tract["other_total"] = (tract.B15003_E001 - tract.white_total - tract.black_total).clip(lower=0)
    tract["other_college"] = (tract.all_college - tract.white_college - tract.black_college).clip(lower=0)
    tract["tract_geoid"] = tract.GEO_ID.str.split("US").str[-1]
    controls = tract.set_index("tract_geoid")

    rows = []
    for tract_geoid, group in bg.groupby("tract_geoid", sort=False):
        if tract_geoid not in controls.index:
            continue
        control = controls.loc[tract_geoid]
        seed = group[["white_seed", "black_seed", "other_seed"]].to_numpy(float)
        for education_level in ["noncollege", "college"]:
            row_targets = group[education_level].clip(lower=0).to_numpy(float)
            if education_level == "college":
                column_targets = np.array([control.white_college, control.black_college, control.other_college])
            else:
                column_targets = np.array([control.white_total-control.white_college,
                                           control.black_total-control.black_college,
                                           control.other_total-control.other_college])
            fitted = ipf(seed, row_targets, column_targets)
            for position, (_, bg_row) in enumerate(group.iterrows()):
                rows.append({"acs_vintage": year, "block_group_geoid": bg_row.block_group_geoid,
                             "tract_geoid": tract_geoid, "education": education_level,
                             "white_nh": fitted[position, 0], "black": fitted[position, 1],
                             "other": fitted[position, 2], "block_group_education_total": row_targets[position],
                             "method": "tract_joint_controls_bg_marginals_ipf"})
    long = pd.DataFrame(rows)
    wide = long.pivot(index=["acs_vintage","block_group_geoid","tract_geoid","method"],
                      columns="education", values=["white_nh","black","other","block_group_education_total"])
    wide.columns = [f"{a}_{b}" for a,b in wide.columns]
    wide = wide.reset_index()
    cell_columns = [f"{race}_{edu}" for race in ["white_nh","black","other"] for edu in ["noncollege","college"]]
    wide["modeled_adult25_total"] = wide[cell_columns].sum(axis=1)
    wide["constraint_error"] = wide.modeled_adult25_total - (
        wide.block_group_education_total_noncollege + wide.block_group_education_total_college)
    return wide


def main() -> None:
    manifest=[]
    for year in YEARS:
        for table,prefixes in SPECS.items():
            _, record=pull(year,table,prefixes);manifest.append(record)
    panel=pd.concat([derive(year) for year in YEARS],ignore_index=True)
    OUT.mkdir(parents=True,exist_ok=True)
    panel.to_csv(OUT / "acs_block_group_joint_race_education_modeled.csv",index=False)
    pd.DataFrame(manifest).to_csv(RAW / "source_manifest.csv",index=False)
    print(panel.groupby("acs_vintage").agg(block_groups=("block_group_geoid","size"),
          adult25=("modeled_adult25_total","sum"),max_constraint_error=("constraint_error",lambda x:x.abs().max())).to_string())


if __name__ == "__main__": main()
