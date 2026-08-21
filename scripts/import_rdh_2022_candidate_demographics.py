"""Match RDH 2022 Alabama legislative candidate demographics to nominees."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
OUT = ROOT / "data" / "processed" / "elections" / "validation" / "rdh_2022_candidate_demographic_matches.csv"
ARCHIVES = {
    "house": ROOT / "data" / "raw" / "candidates" / "legacy_2022" / "AL_SLDL_22_Candidates.zip",
    "senate": ROOT / "data" / "raw" / "rdh" / "AL_SLDU_22_Candidates.zip",
}
CATALOG = "https://redistrictingdatahub.org/state/alabama/"


def name_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\b(JR|SR|II|III|IV|COACH)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


def read_archive(chamber: str, path: Path) -> pd.DataFrame:
    with ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(member) as handle:
            frame = pd.read_csv(handle)
    frame["chamber"] = chamber
    frame["name_key"] = frame.Cand_name.map(name_key)
    # Multiple primary/runoff appearances describe the same candidate evidence.
    frame = frame.sort_values(
        ["District", "name_key", "Race_1_source", "Race_1_conf"],
        ascending=[True, True, True, True],
    ).drop_duplicates(["District", "name_key"], keep="first")
    return frame


def main() -> None:
    source = pd.concat(
        [read_archive(chamber, path) for chamber, path in ARCHIVES.items()],
        ignore_index=True,
    )
    candidates = pd.read_csv(CANDIDATES)
    candidates = candidates[candidates.year.eq(2022)].copy()
    candidates["name_key"] = candidates.canonical_name.map(name_key)
    match = candidates.merge(
        source[["chamber", "District", "name_key", "Cand_name", "Party", "Race_1",
                "Race_1_type", "Race_1_source", "Race_1_conf", "Race_1_URL", "Notes"]],
        left_on=["chamber", "district", "name_key"],
        right_on=["chamber", "District", "name_key"], how="left", validate="one_to_one",
    )
    match["race_ethnicity"] = match.Race_1.map({"BLK": "black", "WHT": "non_black"}).fillna("")
    match["black_candidate"] = match.race_ethnicity.map({"black": 1, "non_black": 0})
    supported = (
        match.race_ethnicity.ne("")
        & match.Race_1_source.isin(["CAND", "OTH"])
        & match.Race_1_URL.notna()
    )
    guessed = match.race_ethnicity.ne("") & match.Race_1_source.eq("GUES")
    match["review_status"] = "external_unknown"
    match.loc[supported, "review_status"] = "approved_external_dataset"
    match.loc[guessed, "review_status"] = "sensitivity_guess_excluded"
    match["evidence_url"] = match.Race_1_URL.fillna(CATALOG)
    match["evidence_quote"] = match.apply(
        lambda row: (
            f"RDH Race_1={row['Race_1']}; source={row['Race_1_source']}; "
            f"type={row['Race_1_type']}; confidence={row['Race_1_conf']}"
            if pd.notna(row.Race_1) else ""
        ), axis=1)
    match["evidence_date"] = "2022"
    match["reviewer"] = "Redistricting Data Hub"
    match["notes"] = match.Notes.fillna("")
    columns = [
        "canonical_candidate_id", "person_id", "year", "chamber", "district",
        "canonical_party", "canonical_name", "Cand_name", "race_ethnicity",
        "black_candidate", "Race_1_type", "Race_1_source", "Race_1_conf",
        "evidence_url", "evidence_quote", "evidence_date", "review_status",
        "reviewer", "notes",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    match[columns].to_csv(OUT, index=False)
    print(match.groupby(["chamber", "review_status"]).size().to_string())


if __name__ == "__main__":
    main()
