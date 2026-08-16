"""Build descriptive Alabama legislator voting measures from LegiScan roll calls.

These are chamber/biennium-relative behavioral scores, not universal ideology.
Only recorded, contested Yea/Nay votes on HB/SB measures enter the ideal point.
"""

from __future__ import annotations

from pathlib import Path
import re
from contextlib import closing

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from warehouse import connect

try:
    from scripts.import_legiscan_alabama_rollcalls import normalize_name
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from import_legiscan_alabama_rollcalls import normalize_name


ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data" / "processed" / "legislative"
OUT = IN
MINORITY_MIN = 2
MINORITY_SHARE_MIN = 0.025
MIN_MEMBER_VOTES = 20


def election_cycle(year: pd.Series) -> pd.Series:
    year = pd.to_numeric(year, errors="coerce").astype("Int64")
    return year.where(year.mod(2).eq(0), year + 1)


def bill_type(number: object) -> str:
    match = re.match(r"\s*([A-Za-z]+)", str(number or ""))
    return match.group(1).upper() if match else ""


def prepare_votes() -> tuple[pd.DataFrame, pd.DataFrame]:
    with closing(connect(readonly=True)) as connection:
        votes = pd.read_sql("SELECT * FROM source_legiscan_member_vote", connection)
        rolls = pd.read_sql("SELECT * FROM source_legiscan_roll_call", connection)
        bills = pd.read_sql("SELECT * FROM source_legiscan_bill", connection)
        people = pd.read_sql("SELECT * FROM source_legiscan_legislator_session", connection)
        qa = pd.read_sql("""SELECT r.roll_call_id,
          CASE WHEN r.total=count(v.people_id) THEN 1 ELSE 0 END AS reported_total_matches
          FROM source_legiscan_roll_call r LEFT JOIN source_legiscan_member_vote v
          USING(roll_call_id) GROUP BY r.roll_call_id,r.total""", connection)

    bills["bill_type"] = bills.bill_number.map(bill_type)
    roll_meta = rolls.merge(
        bills[["bill_id", "bill_number", "bill_type", "title", "description"]],
        on="bill_id", how="left", validate="many_to_one",
    )
    roll_meta["cycle"] = election_cycle(roll_meta.session_year)
    roll_meta["recorded_yea_nay"] = (
        pd.to_numeric(roll_meta.yea, errors="coerce").fillna(0)
        + pd.to_numeric(roll_meta.nay, errors="coerce").fillna(0)
    )
    roll_meta["minority_count"] = roll_meta[["yea", "nay"]].min(axis=1)
    roll_meta["minority_share"] = roll_meta.minority_count / roll_meta.recorded_yea_nay.replace(0, np.nan)
    roll_meta["eligible_ideal_point"] = (
        roll_meta.bill_type.isin(["HB", "SB"])
        & roll_meta.minority_count.ge(MINORITY_MIN)
        & roll_meta.minority_share.ge(MINORITY_SHARE_MIN)
    )
    roll_meta = roll_meta.merge(
        qa[["roll_call_id", "reported_total_matches"]],
        on="roll_call_id", how="left", validate="one_to_one",
    )
    # Quarantine aggregate/individual tally conflicts pending ALISON review.
    roll_meta["eligible_ideal_point"] &= roll_meta.reported_total_matches.fillna(False)

    people["cycle"] = election_cycle(people.session_year)
    people = people.sort_values("session_year").drop_duplicates(
        ["session_year", "people_id"], keep="last"
    )
    votes = votes.merge(
        people[["session_year", "people_id", "name", "normalized_name", "party", "role", "district"]],
        on=["session_year", "people_id"], how="left", validate="many_to_one",
    )
    votes = votes.merge(
        roll_meta[["roll_call_id", "cycle", "bill_type", "eligible_ideal_point"]],
        on="roll_call_id", how="left", validate="many_to_one",
    )
    votes = votes[votes.vote.isin(["Yea", "Nay"])].copy()
    votes["vote_binary"] = votes.vote.eq("Yea").astype(int)
    return votes, roll_meta


def score_group(group: pd.DataFrame) -> pd.DataFrame:
    matrix = group.pivot(index="people_id", columns="roll_call_id", values="vote_binary")
    participation = matrix.notna().sum(axis=1)
    matrix = matrix.loc[participation.ge(MIN_MEMBER_VOTES)]
    if matrix.shape[0] < 4 or matrix.shape[1] < 2:
        return pd.DataFrame()
    filled = matrix.fillna(matrix.mean(axis=0))
    x = filled.to_numpy(dtype=float)
    x -= x.mean(axis=0, keepdims=True)
    raw = PCA(n_components=1).fit_transform(x).ravel()
    meta = group.drop_duplicates("people_id").set_index("people_id").reindex(matrix.index)
    republican = meta.party.eq("R")
    democrat = meta.party.eq("D")
    if republican.any() and democrat.any() and raw[republican].mean() < raw[democrat].mean():
        raw *= -1
    sd = raw.std(ddof=0)
    score = raw / sd if sd else raw
    result = meta[["name", "normalized_name", "party", "role", "district"]].copy()
    result["ideal_point"] = score
    result["chamber_percentile"] = pd.Series(score, index=result.index).rank(pct=True) * 100
    result["votes_used"] = participation.reindex(result.index)
    result["possible_votes"] = matrix.shape[1]
    result["participation_rate"] = result.votes_used / result.possible_votes
    result["caucus_median"] = result.groupby("party").ideal_point.transform("median")
    result["distance_from_caucus_median"] = result.ideal_point - result.caucus_median
    chamber_median = float(np.median(score))
    result["ideological_extremity"] = (result.ideal_point - chamber_median).abs()
    return result.reset_index()


def add_party_metrics(eligible: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    party_roll = eligible[eligible.party.isin(["D", "R"])].groupby(
        ["cycle", "chamber", "roll_call_id", "party"]
    ).vote_binary.mean().rename("party_yea_share").reset_index()
    party_roll["party_majority_vote"] = party_roll.party_yea_share.ge(.5).astype(int)
    piv = party_roll.pivot(index=["cycle", "chamber", "roll_call_id"], columns="party", values="party_majority_vote")
    contested_between = piv.get("D", pd.Series(index=piv.index, dtype=float)).ne(
        piv.get("R", pd.Series(index=piv.index, dtype=float))
    ).rename("parties_disagree").reset_index()
    eligible = eligible.merge(party_roll, on=["cycle", "chamber", "roll_call_id", "party"], how="left")
    eligible = eligible.merge(contested_between, on=["cycle", "chamber", "roll_call_id"], how="left")
    eligible["party_loyal"] = eligible.vote_binary.eq(eligible.party_majority_vote)
    eligible["cross_party_vote"] = (~eligible.party_loyal).where(eligible.parties_disagree)
    metrics = eligible.groupby(["cycle", "chamber", "people_id"]).agg(
        party_loyalty_rate=("party_loyal", "mean"),
        cross_party_voting_rate=("cross_party_vote", "mean"),
        parties_disagree_votes=("parties_disagree", "sum"),
    ).reset_index()
    return scores.merge(metrics, on=["cycle", "chamber", "people_id"], how="left")


def build_candidate_features(scores: pd.DataFrame) -> pd.DataFrame:
    with closing(connect(readonly=True)) as connection:
        candidates = pd.read_sql("""SELECT canonical_candidate_id,person_id,year,chamber,district,
          party AS canonical_party,ballot_name AS canonical_name,incumbent
          FROM fact_candidate_election""", connection)
    candidates = candidates.rename(columns={"district": "district_candidate"})
    candidates["normalized_name"] = candidates.canonical_name.map(normalize_name)
    scores = scores.rename(columns={"district": "district_legislator"}).copy()
    scores["surname"] = scores.normalized_name.str.split().str[-1]
    scores["district_number"] = pd.to_numeric(
        scores.district_legislator.astype(str).str.extract(r"(\d+)")[0], errors="coerce"
    )
    rows = []
    for _, candidate in candidates.iterrows():
        pool = scores[
            scores.cycle.eq(candidate.year) & scores.chamber.eq(candidate.chamber)
        ]
        exact = pool[pool.normalized_name.eq(candidate.normalized_name)]
        match_method = "unmatched"
        match = exact if len(exact) == 1 else pool.iloc[0:0]
        if len(match) == 1:
            match_method = "exact_name_chamber_cycle"
        elif bool(candidate.incumbent):
            district_match = pool[pool.district_number.eq(float(candidate.district_candidate))]
            if len(district_match) == 1:
                match = district_match
                match_method = "incumbent_unique_district_chamber_cycle"
        combined = candidate.to_dict()
        if len(match) == 1:
            for key, value in match.iloc[0].items():
                if key not in {"cycle", "chamber", "normalized_name"}:
                    combined[key] = value
        combined["identity_match_method"] = match_method
        combined["legislative_score_available"] = int(len(match) == 1)
        rows.append(combined)
    joined = pd.DataFrame(rows)
    if "district_legislator" not in joined:
        joined["district_legislator"] = np.nan
    columns = [
        "canonical_candidate_id", "person_id", "year", "chamber", "district_candidate",
        "canonical_name", "canonical_party", "incumbent", "people_id", "party",
        "district_legislator", "ideal_point", "chamber_percentile",
        "distance_from_caucus_median", "ideological_extremity", "votes_used",
        "possible_votes", "participation_rate", "party_loyalty_rate",
        "cross_party_voting_rate", "parties_disagree_votes",
        "legislative_score_available", "identity_match_method",
    ]
    return joined[columns]


def main() -> None:
    votes, roll_meta = prepare_votes()
    eligible = votes[votes.eligible_ideal_point].copy()
    scored = []
    for (cycle, chamber), group in eligible.groupby(["cycle", "chamber"]):
        result = score_group(group)
        if not result.empty:
            result.insert(0, "chamber", chamber)
            result.insert(0, "cycle", int(cycle))
            scored.append(result)
    scores = pd.concat(scored, ignore_index=True)
    scores = add_party_metrics(eligible, scores)
    candidate_features = build_candidate_features(scores)
    roll_meta.to_csv(OUT / "legiscan_rollcall_analysis_eligibility.csv", index=False)
    scores.to_csv(OUT / "alabama_legislator_ideology_by_cycle.csv", index=False)
    candidate_features.to_csv(OUT / "candidate_pre_election_legislative_features.csv", index=False)
    print(
        f"Eligible roll calls: {roll_meta.eligible_ideal_point.sum():,} / {len(roll_meta):,}; "
        f"legislator-cycle scores: {len(scores):,}; candidate matches: "
        f"{candidate_features.legislative_score_available.sum():,} / {len(candidate_features):,}"
    )


if __name__ == "__main__":
    main()
