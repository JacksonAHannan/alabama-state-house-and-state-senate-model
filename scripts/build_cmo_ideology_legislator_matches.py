"""Match the CMO research cohort to Shor--McCarty legislator ideal points."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process


ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "research" / "cmo_ideology" / "candidate_cohort.csv"
SHOR = ROOT / "data" / "raw" / "ideology" / "shor_mccarty_individual_legislators_1993_2018.tsv"
OUTPUT = ROOT / "research" / "cmo_ideology" / "shor_mccarty_matches.csv"
REVIEW = ROOT / "research" / "cmo_ideology" / "shor_mccarty_match_review.csv"

# Dataset names are sometimes abbreviated, formalized, or recorded under a
# middle name. These aliases are auditable; they do not silently alter source data.
ALIASES = {
    "John (Jody) Letson": "Letson",
    "BARBARA BIGSBY BOYD": "Boyd, Barbara",
    "Jeff McLaughlin": "McLaughlin, Jeffrey",
    "Johnny Mack Morrow": "Morrow, Johnny",
    "MARC KEAHEY": "Keahey, George",
    "BILLY BEASLEY": "Beasley, William",
    "VIVIAN DAVIS FIGURES": "Figures, Vivian",
    "Barbara A. Drummond": "Drummond, Barbara",
    "Henry A. White": "White, Henry",
    "Johnny MacK Morrow": "Morrow, Johnny",
    "TAMMY L. IRONS": "Irons, Tammy",
    "JERRY L. FIELDING": "Fielding, Jerry",
    "JAMES C. FIELDS, JR.": "Fields, James Jr.",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r'"[^"\n]+"|\([^\n)]+\)', " ", text)
    text = re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", text, flags=re.I)
    tokens = re.findall(r"[a-z]+", text.lower())
    return " ".join(sorted(tokens))


def active_reference(source: pd.DataFrame, chamber: str, cycle: int) -> pd.Series:
    column = f"{chamber}{min(cycle, 2018)}"
    mask = (
        (source["st"] == "AL")
        & (source["party"] == "D")
        & (pd.to_numeric(source[column], errors="coerce") == 1)
    )
    return pd.to_numeric(source.loc[mask, "np_score"], errors="coerce").dropna()


def service_timing(row: pd.Series, chamber: str, cycle: int) -> tuple[bool, bool]:
    years = range(1993, 2019)
    served = [
        year
        for year in years
        if pd.to_numeric(row.get(f"{chamber}{year}"), errors="coerce") == 1
    ]
    return any(year <= cycle for year in served), any(year > cycle for year in served)


def any_service_by(row: pd.Series, cycle: int) -> bool:
    return any(
        pd.to_numeric(row.get(f"{chamber}{year}"), errors="coerce") == 1
        for chamber in ("house", "senate")
        for year in range(1993, min(cycle, 2018) + 1)
    )

def service_years_by(row: pd.Series, cycle: int) -> list[int]:
    return [
        year
        for year in range(1993, min(cycle, 2018) + 1)
        if any(
            pd.to_numeric(row.get(f"{chamber}{year}"), errors="coerce") == 1
            for chamber in ("house", "senate")
        )
    ]


def main() -> None:
    cohort = pd.read_csv(COHORT)
    source = pd.read_csv(SHOR, sep="\t", low_memory=False)
    alabama = source[source["st"] == "AL"].copy()
    alabama["normalized_name"] = alabama["name"].map(normalize)
    choices = sorted(alabama["normalized_name"].dropna().unique())

    rows: list[dict[str, object]] = []
    for candidate in cohort.itertuples(index=False):
        alias = ALIASES.get(candidate.candidate, candidate.candidate)
        query = normalize(alias)
        exact = alabama[alabama["normalized_name"] == query]
        match_method = "manual_alias" if candidate.candidate in ALIASES else "normalized_exact"
        similarity = 100.0 if not exact.empty else np.nan
        if exact.empty:
            suggestion = process.extractOne(query, choices, scorer=fuzz.WRatio)
            if suggestion and suggestion[1] >= 92:
                exact = alabama[alabama["normalized_name"] == suggestion[0]]
                similarity = float(suggestion[1])
                match_method = "high_confidence_fuzzy"
            else:
                rows.append(
                    {
                        "person_id": candidate.person_id,
                        "candidate": candidate.candidate,
                        "cycle": candidate.cycle,
                        "chamber": candidate.chamber,
                        "district": candidate.district,
                        "best_cmo": candidate.best_cmo,
                        "match_status": "unmatched",
                        "match_method": "none",
                        "similarity": suggestion[1] if suggestion else np.nan,
                        "suggested_source_name": suggestion[0] if suggestion else "",
                    }
                )
                continue

        # Prefer the party under which the candidate ran in the cohort. Switchers
        # can have separate party-specific ideal points under one source u_id.
        party_rows = exact[exact["party"] == "D"]
        selected = party_rows if not party_rows.empty else exact
        scores = pd.to_numeric(selected["np_score"], errors="coerce").dropna().unique()
        reference = active_reference(source, candidate.chamber, int(candidate.cycle))
        source_score = float(np.mean(scores)) if len(scores) else np.nan
        source_is_democratic = set(selected["party"].dropna()) == {"D"}
        percentile = (
            float((reference <= source_score).mean() * 100)
            if len(reference) and pd.notna(source_score) and source_is_democratic
            else np.nan
        )
        first = selected.iloc[0]
        served_by, served_after = service_timing(first, candidate.chamber, int(candidate.cycle))
        status = (
            "party_mismatch"
            if not source_is_democratic
            else "matched"
            if len(scores) == 1
            else "ambiguous_multiple_scores"
        )
        rows.append(
            {
                "person_id": candidate.person_id,
                "candidate": candidate.candidate,
                "cycle": candidate.cycle,
                "chamber": candidate.chamber,
                "district": candidate.district,
                "best_cmo": candidate.best_cmo,
                "match_status": status,
                "match_method": match_method,
                "similarity": similarity,
                "suggested_source_name": " | ".join(sorted(selected["name"].unique())),
                "source_party": " | ".join(sorted(selected["party"].unique())),
                "source_u_id": " | ".join(sorted(selected["u_id"].astype(str).unique())),
                "np_score": source_score,
                "np_score_min": float(scores.min()) if len(scores) else np.nan,
                "np_score_max": float(scores.max()) if len(scores) else np.nan,
                "al_dem_caucus_conservative_percentile": percentile,
                "reference_caucus_n": len(reference),
                "served_in_chamber_by_election": served_by,
                "served_in_chamber_after_election": served_after,
                "served_in_either_chamber_by_election": any_service_by(
                    first, int(candidate.cycle)
                ),
                "temporal_use": (
                    "pre_election_service_available"
                    if served_by
                    else "pre_election_other_chamber_service_available"
                    if any_service_by(first, int(candidate.cycle))
                    else "post_election_or_other_chamber_only"
                    if served_after
                    else "no_same_chamber_service_flag"
                ),
                "review_note": (
                    "Multiple source rows yield different ideal points; do not use mean inferentially."
                    if status == "ambiguous_multiple_scores"
                    else "Source score is from a different party period; exclude from Democratic-caucus inference."
                    if status == "party_mismatch"
                    else ""
                ),
            }
        )

    output = pd.DataFrame(rows).sort_values("best_cmo", ascending=False)
    output.to_csv(OUTPUT, index=False)
    review = output[
        (output["match_status"] != "matched")
        | (output["match_method"] == "high_confidence_fuzzy")
        | (output.get("source_party", pd.Series(index=output.index, dtype=str)) != "D")
    ]
    review.to_csv(REVIEW, index=False)
    print(f"Wrote {len(output)} cohort rows to {OUTPUT}")
    print(output["match_status"].value_counts(dropna=False).to_string())
    print(f"Review queue: {len(review)} rows")


if __name__ == "__main__":
    main()
