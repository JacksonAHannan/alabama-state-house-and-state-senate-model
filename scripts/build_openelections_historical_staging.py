#!/usr/bin/env python3
"""Normalize acquired OpenElections historical gap files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "data/processed/source_audits/openelections_historical_gap_manifest.csv"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
OUTPUT = ROOT / "data/processed/precinct_history/openelections"
STATE_NAMES = {"Arkansas": "AR", "Georgia": "GA", "Missouri": "MO", "South Carolina": "SC"}
CONTEXT_OFFICES = {"USP", "USS", "GOV"}
LEGISLATIVE_OFFICES = {"house", "senate"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def classify_office(value: object) -> tuple[str | None, str | None]:
    text = re.sub(r"\s+", " ", str(value).strip()).lower()
    district_match = re.search(r"district\s+(\d+)", text)
    embedded = district_match.group(1) if district_match else None
    if "state representative" in text or "state house" in text or "state assembly" in text:
        return "house", embedded
    if "state senate" in text or "state senator" in text:
        return "senate", embedded
    if "president" in text:
        return "USP", None
    if any(term in text for term in ("u.s. senate", "u.s. senator", "united states senator")):
        return "USS", None
    if any(term in text for term in ("u.s. house", "u.s. representative", "united states representative")):
        return "USH", embedded
    if text == "governor":
        return "GOV", None
    return None, None


def normalize_party(value: object) -> str | None:
    text = re.sub(r"[^a-z]", "", str(value).lower())
    if text in {"d", "dem", "democrat", "democratic"} or text.startswith("democrat"):
        return "D"
    if text in {"r", "rep", "republican"} or text.startswith("republican"):
        return "R"
    return None


def candidate_key(value: object) -> str:
    tokens = re.findall(r"[a-z]+", str(value).lower())
    return " ".join(sorted(token for token in tokens if token not in {"jr", "sr", "ii", "iii", "iv"}))


def resolve_parties(observations: pd.DataFrame, klarner_path: Path) -> pd.DataFrame:
    out = observations.copy()
    out["candidate_key"] = out["candidate"].map(candidate_key)
    out["party_resolution"] = out["party"].map(lambda value: "source" if value in {"D", "R"} else "unknown")
    mapping_keys = ["state", "year", "office", "candidate_key"]
    known = out.loc[out["party"].isin(["D", "R"])].groupby(mapping_keys)["party"].agg(lambda values: values.iloc[0] if values.nunique() == 1 else pd.NA).dropna()
    missing = out["party"].isna()
    cross = pd.MultiIndex.from_frame(out.loc[missing, mapping_keys]).map(known)
    out.loc[missing, "party"] = cross
    out.loc[missing & out["party"].notna(), "party_resolution"] = "cross_file_candidate"

    with ZipFile(klarner_path) as bundle:
        candidates = pd.read_csv(bundle.open("208slers_uoa_cand_contest20230810.csv"), low_memory=False)
    candidates = candidates.loc[candidates["state"].isin(STATE_NAMES) & candidates["partyt"].isin(["d", "r"])].copy()
    candidates["state"] = candidates["state"].map(STATE_NAMES)
    candidates["office"] = candidates["sen"].map({0: "house", 1: "senate"})
    candidates["district"] = pd.to_numeric(candidates["dno"], errors="coerce").astype("Int64")
    candidates["candidate_key"] = candidates["cand"].map(candidate_key)
    candidates["klarner_party"] = candidates["partyt"].str.upper()
    join_keys = ["state", "year", "office", "district", "candidate_key"]
    candidate_map = candidates[join_keys + ["klarner_party"]].drop_duplicates(join_keys)
    out = out.merge(candidate_map, on=join_keys, how="left", validate="many_to_one")
    missing = out["party"].isna() & out["klarner_party"].notna()
    out.loc[missing, "party"] = out.loc[missing, "klarner_party"]
    out.loc[missing, "party_resolution"] = "klarner_candidate_key"
    return out.drop(columns="klarner_party")


def vote_series(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    if "votes" in frame and pd.to_numeric(frame["votes"], errors="coerce").notna().any():
        return pd.to_numeric(frame["votes"], errors="coerce"), "votes"
    mode_fields = [field for field in (
        "election_day_votes", "advanced_votes", "absentee_by_mail_votes", "provisional_votes",
        "absentee_by_mail", "election_day", "advance_in_person", "advance_in_person_1",
        "advance_in_person_2", "advance_in_person_3", "provisional",
    ) if field in frame]
    if not mode_fields:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64"), "missing"
    numeric = frame[mode_fields].apply(pd.to_numeric, errors="coerce")
    return numeric.sum(axis=1, min_count=1), "+".join(mode_fields)


def normalize_file(path: Path, manifest_row: pd.Series) -> pd.DataFrame:
    source = pd.read_csv(path, low_memory=False)
    votes, vote_fields = vote_series(source)
    classified = source["office"].map(classify_office)
    out = pd.DataFrame({
        "state": manifest_row["state"], "year": int(manifest_row["election_year"]),
        "county": source["county"] if "county" in source else pd.NA,
        "ward": source["ward"] if "ward" in source else pd.NA,
        "precinct": source["precinct"] if "precinct" in source else pd.NA,
        "office_raw": source["office"],
        "office": classified.map(lambda item: item[0]),
        "district_embedded": classified.map(lambda item: item[1]),
        "district_raw": source["district"] if "district" in source else pd.NA,
        "party_raw": source["party"] if "party" in source else pd.NA,
        "party": source["party"].map(normalize_party) if "party" in source else pd.NA,
        "candidate": source["candidate"] if "candidate" in source else pd.NA,
        "votes": votes, "vote_source_fields": vote_fields,
        "source_file": manifest_row["local_path"], "source_sha256": manifest_row["sha256"],
        "source_status": manifest_row["source_status"], "source_row": range(1, len(source) + 1),
    })
    if "first name" in source and "last name" in source:
        fallback = source["first name"].fillna("").astype(str).str.strip() + " " + source["last name"].fillna("").astype(str).str.strip()
        out["candidate"] = out["candidate"].where(out["candidate"].notna() & out["candidate"].astype(str).str.strip().ne(""), fallback.str.strip())
    existing_district = out["district_raw"].astype(str).str.extract(r"(\d+)", expand=False)
    out["district"] = pd.to_numeric(existing_district.fillna(out["district_embedded"]), errors="coerce").astype("Int64")
    return out.loc[out["office"].notna() & out["votes"].notna()].reset_index(drop=True)


def klarner_reconciliation(districts: pd.DataFrame, path: Path) -> pd.DataFrame:
    with ZipFile(path) as bundle:
        source = pd.read_csv(bundle.open("202slers_uoa_contest20230810.csv"), low_memory=False)
    source = source.loc[source["state"].isin(STATE_NAMES)].copy()
    source["state"] = source["state"].map(STATE_NAMES)
    source["chamber"] = source["sen"].map({0: "house", 1: "senate"})
    source["district"] = pd.to_numeric(source["dno"], errors="coerce").astype("Int64")
    source["klarner_dem_votes"] = pd.to_numeric(source["dvote"], errors="coerce")
    source["klarner_rep_votes"] = pd.to_numeric(source["rvote"], errors="coerce")
    keys = ["state", "year", "chamber", "district"]
    source = source[keys + ["klarner_dem_votes", "klarner_rep_votes"]].dropna(subset=["district", "chamber"]).drop_duplicates(keys)
    audit = districts.merge(source, on=keys, how="left", validate="one_to_one")
    audit["dem_vote_delta"] = audit["dem_votes"] - audit["klarner_dem_votes"]
    audit["rep_vote_delta"] = audit["rep_votes"] - audit["klarner_rep_votes"]
    audit["exact_party_totals"] = audit["dem_vote_delta"].eq(0) & audit["rep_vote_delta"].eq(0)
    return audit


def build(manifest_path: Path, klarner_path: Path, output: Path) -> dict[str, int]:
    manifest_path, klarner_path, output = manifest_path.resolve(), klarner_path.resolve(), output.resolve()
    manifest = pd.read_csv(manifest_path)
    pieces = [normalize_file(ROOT / row["local_path"], row) for _, row in manifest.iterrows()]
    observations = resolve_parties(pd.concat(pieces, ignore_index=True), klarner_path)
    legislative = observations.loc[observations["office"].isin(LEGISLATIVE_OFFICES) & observations["district"].notna()].copy()
    context = observations.loc[observations["office"].isin(CONTEXT_OFFICES)].copy()
    party_legislative = legislative.loc[legislative["party"].isin(["D", "R"])]
    district_party = party_legislative.groupby(["state", "year", "office", "district", "party"], as_index=False)["votes"].sum()
    districts = district_party.pivot(index=["state", "year", "office", "district"], columns="party", values="votes").reset_index()
    districts = districts.rename(columns={"office": "chamber", "D": "dem_votes", "R": "rep_votes"})
    for field in ("dem_votes", "rep_votes"):
        if field not in districts:
            districts[field] = pd.NA
    denominator = districts["dem_votes"] + districts["rep_votes"]
    districts["dem_margin"] = 100 * (districts["dem_votes"] - districts["rep_votes"]) / denominator.where(denominator > 0)
    reconciliation = klarner_reconciliation(districts, klarner_path)
    coverage = observations.groupby(["state", "year", "office"], as_index=False).agg(
        observation_rows=("source_row", "size"), precincts=("precinct", "nunique"),
        districts=("district", "nunique"), dem_rows=("party", lambda values: int(values.eq("D").sum())),
        rep_rows=("party", lambda values: int(values.eq("R").sum())),
    )
    output.mkdir(parents=True, exist_ok=True)
    gzip = {"method": "gzip", "mtime": 0}
    observations.to_csv(output / "openelections_relevant_precinct_candidate.csv.gz", index=False, compression=gzip)
    legislative.to_csv(output / "openelections_legislative_precinct_candidate.csv.gz", index=False, compression=gzip)
    context.to_csv(output / "openelections_context_precinct_candidate.csv.gz", index=False, compression=gzip)
    districts.to_csv(output / "openelections_legislative_district_party_totals.csv", index=False)
    reconciliation.to_csv(output / "openelections_klarner_reconciliation.csv", index=False)
    coverage.to_csv(output / "openelections_contest_coverage.csv", index=False)
    resolution = observations.groupby(["state", "year", "office", "party_resolution"], as_index=False).size().rename(columns={"size": "rows"})
    resolution.to_csv(output / "openelections_party_resolution_audit.csv", index=False)
    output_files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "build_manifest.json")
    script_path = Path(__file__).resolve()
    run_manifest = {
        "schema_version": 1,
        "build_id": hashlib.sha256(f"{sha256(manifest_path)}:{sha256(klarner_path)}:{sha256(script_path)}".encode()).hexdigest()[:20],
        "code_commit": git_commit(), "pipeline": display_path(script_path),
        "inputs": [{"path": display_path(manifest_path), "sha256": sha256(manifest_path)},
                   {"path": display_path(klarner_path), "sha256": sha256(klarner_path)}],
        "configuration": {"offices": sorted(CONTEXT_OFFICES | LEGISLATIVE_OFFICES),
                          "party_resolution": ["source", "cross_file_candidate", "klarner_candidate_key", "unknown"],
                          "authority": "secondary_validation_source"},
        "row_counts": {"observations": len(observations), "legislative": len(legislative), "context": len(context),
                       "districts": len(districts), "state_cycles": observations[["state", "year"]].drop_duplicates().shape[0]},
        "outputs": [{"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in output_files],
    }
    (output / "build_manifest.json").write_text(json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")
    return {"observations": len(observations), "legislative": len(legislative), "context": len(context),
            "districts": len(districts), "state_cycles": observations[["state", "year"]].drop_duplicates().shape[0]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=SOURCE_MANIFEST)
    parser.add_argument("--klarner", type=Path, default=KLARNER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    counts = build(args.manifest, args.klarner, args.output)
    print("OpenElections historical staging:", ", ".join(f"{key}={value:,}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
