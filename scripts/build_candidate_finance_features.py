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
FIN = ROOT / "Candidate Financial Information"
WAR = ROOT / "data" / "processed" / "war"
ELECTION_DAY = {2014: "2014-11-04", 2018: "2018-11-06", 2022: "2022-11-08"}
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
        filename = archive.namelist()[0]
        data = pd.read_csv(BytesIO(archive.read(filename)), low_memory=False)
    data["ExpenditureDate"] = pd.to_datetime(data.ExpenditureDate, errors="coerce")
    data["ExpenditureAmount"] = pd.to_numeric(data.ExpenditureAmount, errors="coerce").fillna(0)
    keep = (data.CommitteeType.eq("Principal Campaign Committee") &
            data.CandidateName.notna() & data.CandidateName.astype(str).str.strip().ne("") &
            data.ExpenditureDate.le(pd.Timestamp(ELECTION_DAY[cycle])) &
            data.ExpenditureDate.ge(pd.Timestamp(f"{cycle}-01-01")) &
            ~data.Amended.astype(str).str.upper().eq("Y"))
    data = data[keep].copy()
    data["finance_name"] = data.CandidateName.astype(str).str.strip()
    data["finance_name_norm"] = data.finance_name.map(norm)
    out = (data.groupby(["finance_name_norm"], as_index=False)
           .agg(finance_name=("finance_name", "first"),
                candidate_expenditures=("ExpenditureAmount", "sum"),
                expenditure_transactions=("ExpenditureID", "nunique"),
                committee_count=("CommitteeId", "nunique")))
    out["cycle"] = cycle
    return out


def main() -> None:
    finance = pd.concat([load_cycle(c) for c in ELECTION_DAY], ignore_index=True)
    finance["finance_canonical"] = finance.finance_name_norm.map(canonical_person)
    candidates = pd.read_csv(WAR / "race_candidate_results.csv")
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
            if score >= 92 and margin >= 5:
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
                selected, method = same_surname[0], "unique_surname"
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
    matched[matched.finance_match_method.eq("unmatched")].to_csv(
        WAR / "candidate_finance_review.csv", index=False)
    race.to_csv(WAR / "race_finance_features.csv", index=False)
    coverage.to_csv(WAR / "candidate_finance_coverage.csv", index=False)
    print(coverage.to_string(index=False))
    print(f"Unmatched candidates: {(matched.finance_match_method == 'unmatched').sum()}")


if __name__ == "__main__":
    main()
