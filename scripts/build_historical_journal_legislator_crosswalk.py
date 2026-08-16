"""Conservatively match 1998-2009 journal surnames to Shor-McCarty legislators."""
from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from oe_normalize import normalize_name


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
SHOR = ROOT / "data" / "raw" / "ideology" / "shor_mccarty_individual_legislators_1993_2018.tsv"


def surname(value: str) -> str:
    return normalize_name(str(value).split(",", 1)[0])


def journal_surname(value: str) -> str:
    value = str(value).replace("\u00ad", "").replace("¬", "")
    value = re.sub(r"^Senator\s+", "", value, flags=re.I)
    value = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", value)
    value = re.sub(r"\s*\([A-Za-z]+\)\s*$", "", value)
    return normalize_name(value)


def journal_hint(value: str) -> str | None:
    match = re.search(r"\(([A-Za-z]+)\)\s*$", str(value))
    return match.group(1).upper() if match else None


def active_roster(shor: pd.DataFrame, chamber: str, year: int) -> pd.DataFrame:
    flag = f"{chamber}{year}"
    district = f"{'h' if chamber == 'house' else 's'}district{year}"
    active = shor[(shor.st == "AL") & shor[flag].eq(1)].copy()
    active["surname_norm"] = active.name.map(surname)
    active["first_name"] = active.name.str.split(",", n=1).str[1].fillna("").str.strip()
    active["first_initial"] = active.first_name.str[:1].str.upper()
    active["district"] = active[district]
    return active


def build_crosswalk(votes: pd.DataFrame, shor: pd.DataFrame, chamber: str) -> pd.DataFrame:
    names = votes[["session_year", "member_name", "member_name_norm"]].drop_duplicates().copy()
    rows: list[dict] = []
    for row in names.itertuples(index=False):
        roster = active_roster(shor, chamber, int(row.session_year))
        candidates = roster[roster.surname_norm.eq(journal_surname(row.member_name))]
        hint = journal_hint(row.member_name)
        status = "unmatched"
        selected = None
        if len(candidates) == 1:
            status = "unique_active_surname"
            selected = candidates.iloc[0]
        elif len(candidates) > 1 and hint:
            hinted = candidates[candidates.first_initial.eq(hint[:1])]
            if len(hinted) == 1:
                status = "surname_plus_initial"
                selected = hinted.iloc[0]
            else:
                status = "ambiguous_active_surname"
        elif len(candidates) > 1:
            status = "ambiguous_active_surname"
        rows.append({
            "session_year": int(row.session_year), "chamber": chamber,
            "member_name": row.member_name, "member_name_norm": row.member_name_norm,
            "journal_surname_norm": journal_surname(row.member_name), "name_hint": hint,
            "match_status": status, "candidate_count": len(candidates),
            "shor_u_id": selected.u_id if selected is not None else None,
            "shor_name": selected["name"] if selected is not None else None,
            "party": selected.party if selected is not None else None,
            "district": selected.district if selected is not None else None,
            "np_score": selected.np_score if selected is not None else None,
        })
    return pd.DataFrame(rows)


def main() -> None:
    shor = pd.read_csv(SHOR, sep="\t")
    crosswalks: list[pd.DataFrame] = []
    matched_votes: list[pd.DataFrame] = []
    for chamber in ("house", "senate"):
        votes = pd.read_csv(DATA / f"historical_{chamber}_journal_member_votes.csv")
        crosswalk = build_crosswalk(votes[votes.count_valid], shor, chamber)
        crosswalks.append(crosswalk)
        matched = votes.merge(
            crosswalk[["session_year", "member_name", "member_name_norm", "shor_u_id", "shor_name", "party", "district", "np_score", "match_status"]],
            on=["session_year", "member_name", "member_name_norm"], how="left", validate="many_to_one",
        )
        matched_votes.append(matched)
    all_crosswalk = pd.concat(crosswalks, ignore_index=True)
    all_votes = pd.concat(matched_votes, ignore_index=True)
    all_crosswalk.to_csv(DATA / "historical_journal_legislator_crosswalk.csv", index=False)
    all_votes.to_csv(DATA / "historical_journal_member_votes_identified.csv", index=False)
    qa = (all_crosswalk.groupby(["session_year", "chamber", "match_status"], as_index=False)
          .agg(distinct_journal_names=("member_name_norm", "nunique")))
    qa.to_csv(DATA / "historical_journal_legislator_crosswalk_qa.csv", index=False)
    print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
