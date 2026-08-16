"""Build cycle-specific candidate spending features from Alabama FCPA extracts."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import re
import unicodedata

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from build_incumbency_features import read_candidate_code_names

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "data" / "raw" / "finance" / "alabama"
WAR = ROOT / "data" / "processed" / "war"
# Historical windows end on Election Day. The 2026 value is an explicitly
# frozen data-as-of cutoff, preventing post-cutoff information from leaking
# into a prospective model.
ELECTION_DAY = {2014: "2014-11-04", 2018: "2018-11-06", 2022: "2022-11-08", 2026: "2026-08-14"}
WINDOW_START = {2014: "2013-01-01", 2018: "2017-01-01", 2022: "2021-01-01", 2026: "2025-01-01"}
FIRST_NAME_EQUIVALENTS = {
    "BILL": "WILLIAM", "BOB": "ROBERT", "CHRIS": "CHRISTOPHER",
    "CINDY": "CYNTHIA", "ED": "EDWARD", "JIM": "JAMES",
    "MIKE": "MICHAEL", "PAM": "PAMELA", "RON": "RONALD",
    "SAM": "SAMUEL", "TOM": "THOMAS", "WES": "WESLEY",
}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    text = re.sub(r"[^A-Z ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def surname(value: object) -> str:
    tokens = norm(value).split()
    return tokens[-1] if tokens else ""


def canonical_person(value: object) -> str:
    """Normalize common legal-name variants without making surname-only guesses."""
    tokens = norm(value).split()
    if not tokens:
        return ""
    # FCPA sometimes stores initials as JB while election files use J.B.
    if len(tokens) >= 3 and len(tokens[0]) == len(tokens[1]) == 1:
        tokens = [tokens[0] + tokens[1], *tokens[2:]]
    tokens[0] = FIRST_NAME_EQUIVALENTS.get(tokens[0], tokens[0])
    return " ".join(tokens)


def load_cycle(cycle: int) -> pd.DataFrame:
    with ZipFile(FIN / f"{cycle}_ExpendituresExtract.zip") as archive:
        csv_members = sorted(name for name in archive.namelist() if name.lower().endswith(".csv"))
        if len(csv_members) != 1:
            raise ValueError(f"Expected one CSV in {cycle} finance archive; found {csv_members}")
        filename = csv_members[0]
        data = pd.read_csv(BytesIO(archive.read(filename)), low_memory=False)
    data["ExpenditureDate"] = pd.to_datetime(data.ExpenditureDate, errors="coerce")
    data["FiledDate"] = pd.to_datetime(data.FiledDate, errors="coerce")
    data["ExpenditureAmount"] = pd.to_numeric(data.ExpenditureAmount, errors="coerce").fillna(0)
    # Retain the latest filing for a transaction ID. Merely dropping rows marked
    # amended can preserve the superseded value and discard its correction.
    data = data.sort_values(["ExpenditureID", "FiledDate"], na_position="first").drop_duplicates(
        "ExpenditureID", keep="last")
    keep = (data.CommitteeType.eq("Principal Campaign Committee") &
            data.CandidateName.notna() & data.CandidateName.astype(str).str.strip().ne("") &
            data.ExpenditureDate.le(pd.Timestamp(ELECTION_DAY[cycle])) &
            data.ExpenditureDate.ge(pd.Timestamp(WINDOW_START[cycle])) &
            data.ExpenditureID.notna())
    data = data[keep].copy()
    data["finance_name"] = data.CandidateName.astype(str).str.strip()
    data["finance_name_norm"] = data.finance_name.map(norm)
    out = (data.groupby(["finance_name_norm"], as_index=False)
           .agg(finance_name=("finance_name", "first"),
                candidate_expenditures=("ExpenditureAmount", "sum"),
                expenditure_transactions=("ExpenditureID", "nunique"),
                committee_count=("CommitteeId", "nunique")))
    out["cycle"] = cycle
    out["window_start"] = WINDOW_START[cycle]
    out["window_end"] = ELECTION_DAY[cycle]
    return out


def main() -> None:
    finance = pd.concat([load_cycle(c) for c in ELECTION_DAY], ignore_index=True)
    finance["finance_canonical"] = finance.finance_name_norm.map(canonical_person)
    candidates = pd.read_csv(WAR / "race_candidate_results.csv")
    final_2026 = WAR / "2026_final_candidate_roster.csv"
    certified_2026 = WAR / "2026_certified_candidate_roster.csv"
    roster_2026 = final_2026 if final_2026.exists() else certified_2026 if certified_2026.exists() else WAR / "2026_candidate_roster_provisional.csv"
    if roster_2026.exists():
        provisional = pd.read_csv(roster_2026)
        provisional["candidate_code"] = pd.NA
        provisional["votes"] = pd.NA
        candidates = pd.concat([candidates, provisional[candidates.columns]], ignore_index=True)
    code_names = read_candidate_code_names()
    candidates.loc[candidates.cycle.eq(2022), "candidate"] = (
        candidates.loc[candidates.cycle.eq(2022), "candidate_code"].map(code_names)
        .fillna(candidates.loc[candidates.cycle.eq(2022), "candidate"]))
    candidates["candidate_norm"] = candidates.candidate.map(norm)
    matches = []
    for row in candidates.itertuples(index=False):
        pool = finance[finance.cycle.eq(row.cycle)]
        choices = pool.finance_name_norm.tolist()
        found = process.extract(row.candidate_norm, choices, scorer=fuzz.token_set_ratio, limit=2)
        selected = None; method = "unmatched"; score = margin = 0.0
        if row.candidate_norm in choices:
            selected, method, score, margin = row.candidate_norm, "exact", 100.0, 100.0
        elif found:
            score = float(found[0][1]); second = float(found[1][1]) if len(found) > 1 else 0.0
            margin = score - second
            # Statewide name-only matching is intentionally conservative because
            # the extract has no office/district metadata.
            if score >= 97 and margin >= 10:
                selected, method = found[0][0], "fuzzy"
        if selected is None:
            canonical = canonical_person(row.candidate_norm)
            same_canonical = pool.loc[
                pool.finance_canonical.eq(canonical), "finance_name_norm"].unique().tolist()
            if len(same_canonical) == 1:
                selected, method = same_canonical[0], "canonical_name"
        if selected is None:
            same_surname = [choice for choice in choices
                            if surname(choice) == surname(row.candidate_norm)]
            if len(same_surname) == 1:
                # Record the evidence but do not automatically assign money to
                # a candidate from surname alone.
                method = "surname_review"
        matches.append({"cycle": row.cycle, "chamber": row.chamber,
                        "district": int(row.district), "party": row.party,
                        "candidate": row.candidate, "candidate_norm": row.candidate_norm,
                        "finance_name_norm": selected, "finance_match_method": method,
                        "finance_match_score": score, "finance_score_margin": margin})
    matches = pd.DataFrame(matches)
    matched = matches.merge(finance, on=["cycle", "finance_name_norm"], how="left",
                            validate="many_to_one")
    matched["candidate_expenditures"] = matched.candidate_expenditures.fillna(0)
    race = (matched.groupby(["cycle", "chamber", "district", "party"], as_index=False)
            .candidate_expenditures.sum()
            .pivot(index=["cycle", "chamber", "district"], columns="party",
                   values="candidate_expenditures").fillna(0).reset_index())
    for party in ("D", "R"):
        if party not in race:
            race[party] = 0.0
    race = race.rename(columns={"D": "dem_candidate_spending", "R": "rep_candidate_spending"})
    constant = 500.0
    race["log_spending_ratio_d_to_r"] = np.log(
        (race.dem_candidate_spending + constant) / (race.rep_candidate_spending + constant))
    race["spending_constant"] = constant
    match_flags = (matched.assign(finance_matched=matched.finance_match_method.ne("unmatched"))
                   .pivot_table(index=["cycle", "chamber", "district"], columns="party",
                                values="finance_matched", aggfunc="max", fill_value=False)
                   .reset_index())
    for party in ("D", "R"):
        if party not in match_flags:
            match_flags[party] = False
    match_flags = match_flags.rename(columns={"D": "dem_finance_matched", "R": "rep_finance_matched"})
    race = race.merge(match_flags, on=["cycle", "chamber", "district"], how="left",
                      validate="one_to_one")
    race["finance_complete"] = race.dem_finance_matched & race.rep_finance_matched
    race.loc[~race.finance_complete, "log_spending_ratio_d_to_r"] = np.nan
    coverage = (matched.assign(matched=lambda x: x.finance_match_method.ne("unmatched"))
                .groupby(["cycle", "party"], as_index=False)
                .agg(candidates=("candidate", "size"), matched=("matched", "sum"),
                     spending=("candidate_expenditures", "sum")))
    coverage["match_rate"] = coverage.matched / coverage.candidates

    finance.to_csv(WAR / "finance_candidate_cycle_totals.csv", index=False)
    matched.to_csv(WAR / "candidate_finance_matches.csv", index=False)
    # Every non-exact match requires evidence review; previously this file only
    # exposed unmatched candidates and hid the riskier accepted guesses.
    matched[~matched.finance_match_method.eq("exact")].to_csv(
        WAR / "candidate_finance_review.csv", index=False)
    race.to_csv(WAR / "race_finance_features.csv", index=False)
    coverage.to_csv(WAR / "candidate_finance_coverage.csv", index=False)
    print(coverage.to_string(index=False))
    print(f"Unmatched candidates: {(matched.finance_match_method == 'unmatched').sum()}")


if __name__ == "__main__":
    main()
