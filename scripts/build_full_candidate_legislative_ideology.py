"""Build pre-election legislative ideology features for every canonical candidate.

The output is universal in rows, not fabricated in scores: candidates without
legislative service or enough recorded votes retain an explicit unavailable
status. Behavioral scores are relative to the chamber and pre-election window.
Reviewed anchor votes provide issue dimensions where evidence exists.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "legislative" / "alabama_legislative_rollcalls_1998_2026.sqlite"
ELECTION_DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
OUT = ROOT / "data" / "processed" / "ideology"
RESEARCH = ROOT / "research" / "cmo_ideology"
WINDOWS = {1998:(1998,1998), 2002:(1999,2002), 2006:(2003,2006),
           2010:(2007,2010), 2014:(2011,2014), 2018:(2015,2018), 2022:(2019,2022)}
MIN_VOTES = 20


def norm(value: object) -> str:
    text = re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper())
    return re.sub(r"\s+", " ", text).strip()


def member_name_parts(value: object) -> tuple[str,str]:
    raw=str(value or "")
    if "," in raw:
        surname,given=raw.split(",",1)
        normalized=norm(f"{given} {surname}")
        return normalized,norm(surname)
    normalized=norm(raw)
    return normalized,(normalized.split()[-1] if normalized else "")


def score_window(connection: sqlite3.Connection, cycle: int, chamber: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = WINDOWS[cycle]
    query = """
      SELECT v.canonical_rollcall_id,v.session_year,v.member_source_id,
             v.member_display_name,v.party,v.district,v.vote,
             r.bill_type,r.yea_total,r.nay_total
      FROM member_vote v JOIN rollcall r USING(canonical_rollcall_id)
      WHERE v.session_year BETWEEN ? AND ? AND v.chamber=?
        AND v.identity_status NOT IN ('unmatched','ambiguous_active_surname')
        AND v.vote IN ('Yea','Nay') AND r.bill_type IN ('HB','SB')
    """
    votes = pd.read_sql(query, connection, params=(start,end,chamber))
    if votes.empty:
        return pd.DataFrame(), votes
    rolls = votes[["canonical_rollcall_id","yea_total","nay_total"]].drop_duplicates()
    rolls["recorded"] = rolls.yea_total.fillna(0) + rolls.nay_total.fillna(0)
    rolls["minority"] = rolls[["yea_total","nay_total"]].min(axis=1)
    eligible = rolls.minority.ge(2) & rolls.minority.div(rolls.recorded.replace(0,np.nan)).ge(.025)
    keep = set(rolls.loc[eligible,"canonical_rollcall_id"])
    votes = votes[votes.canonical_rollcall_id.isin(keep)].copy()
    votes["binary"] = votes.vote.eq("Yea").astype(int)
    matrix = votes.pivot_table(index="member_source_id",columns="canonical_rollcall_id",
                               values="binary",aggfunc="first")
    participation = matrix.notna().sum(axis=1)
    matrix = matrix.loc[participation.ge(MIN_VOTES)]
    if matrix.shape[0] < 4 or matrix.shape[1] < 2:
        return pd.DataFrame(), votes
    x = matrix.fillna(matrix.mean(axis=0)).to_numpy(float)
    x -= x.mean(axis=0,keepdims=True)
    raw = PCA(n_components=1).fit_transform(x).ravel()
    meta = (votes.sort_values("session_year").drop_duplicates("member_source_id",keep="last")
            .set_index("member_source_id").reindex(matrix.index))
    d = meta.party.eq("D"); r = meta.party.eq("R")
    if d.any() and r.any() and raw[r].mean() < raw[d].mean(): raw *= -1
    sd = raw.std(ddof=0); score = raw/sd if sd else raw
    result = meta[["member_display_name","party","district"]].copy()
    result["behavioral_ideology"] = score
    result["chamber_percentile"] = pd.Series(score,index=result.index).rank(pct=True)*100
    result["votes_used"] = participation.reindex(result.index)
    result["possible_votes"] = matrix.shape[1]
    result["participation_rate"] = result.votes_used/result.possible_votes
    result["caucus_median"] = result.groupby("party").behavioral_ideology.transform("median")
    result["distance_from_caucus_median"] = result.behavioral_ideology-result.caucus_median
    parts=result.member_display_name.map(member_name_parts)
    result["normalized_name"]=[p[0] for p in parts]
    result["surname"]=[p[1] for p in parts]
    result["cycle"] = cycle; result["chamber"] = chamber
    return result.reset_index(), votes


def match_candidate(row: pd.Series, scores: pd.DataFrame) -> tuple[pd.Series|None,str]:
    pool = scores[(scores.cycle.eq(row.year)) & (scores.chamber.eq(row.chamber))]
    name, surname = member_name_parts(row.canonical_name)
    exact = pool[pool.normalized_name.eq(name)]
    if len(exact)==1: return exact.iloc[0],"exact_name_window"
    # Historical ballots and journals sometimes preserve surname only. Require
    # party and a unique surname to avoid converting ambiguity into evidence.
    same_party = pool[pool.party.eq(row.canonical_party)]
    surname_hit = same_party[same_party.surname.eq(surname)]
    if len(surname_hit)==1: return surname_hit.iloc[0],"unique_surname_party_window"
    if bool(row.incumbent):
        district = pd.to_numeric(pool.district,errors="coerce")
        hit = pool[(district.eq(float(row.district_candidate))) & pool.party.eq(row.canonical_party)]
        if len(hit)==1: return hit.iloc[0],"incumbent_district_party_window"
    return None,"unmatched_no_verified_legislative_identity"


def add_anchor_dimensions(rows: pd.DataFrame, votes: pd.DataFrame) -> pd.DataFrame:
    """Attach all accepted directional classifications, preserving provenance."""
    path = ROOT/"data"/"processed"/"legislative"/"comprehensive_rollcall_classifications.csv"
    if path.exists():
        codes = pd.read_csv(path, low_memory=False)
        codes = codes[codes.yea_direction.notna()].copy()
        codes = codes.rename(columns={"issue_code": "human_issue_code"})
        codes = codes[["canonical_rollcall_id","human_issue_code","yea_direction","classification_source"]]
    else:
        codes = pd.read_csv(RESEARCH/"anchor_vote_human_codes.csv")
        codes = codes[codes.substantive_vote.fillna(False) & codes.summary_sufficient_for_coding.fillna(False)].copy()
        codes["canonical_rollcall_id"] = "LS-"+codes.roll_call_id.astype(str)
        codes["yea_direction"] = codes.ideological_valence.str.lower().map({"conservative":1.0,"progressive":-1.0})
        codes["classification_source"] = "human_anchor_review"
        codes = codes[["canonical_rollcall_id","human_issue_code","yea_direction","classification_source"]]
    codes = codes.drop_duplicates(["canonical_rollcall_id","human_issue_code"])
    joined = votes.merge(codes, on="canonical_rollcall_id",how="inner")
    if joined.empty: return rows
    joined["issue_position"] = joined.yea_direction*np.where(joined.vote.eq("Yea"),1,-1)
    dims = (joined.groupby(["cycle","chamber","member_source_id","human_issue_code"])
            .agg(issue_score=("issue_position","mean"),issue_votes=("issue_position","size")).reset_index())
    score_wide = dims.pivot_table(index=["cycle","chamber","member_source_id"],columns="human_issue_code",values="issue_score").add_prefix("legislative_issue_").reset_index()
    count_wide = dims.pivot_table(index=["cycle","chamber","member_source_id"],columns="human_issue_code",values="issue_votes").add_prefix("legislative_issue_votes_").reset_index()
    source_counts = (joined.groupby(["cycle","chamber","member_source_id","classification_source"])
                     .size().unstack(fill_value=0).add_prefix("legislative_source_votes_").reset_index())
    return (rows.merge(score_wide,on=["cycle","chamber","member_source_id"],how="left")
            .merge(count_wide,on=["cycle","chamber","member_source_id"],how="left")
            .merge(source_counts,on=["cycle","chamber","member_source_id"],how="left"))


def main() -> None:
    with sqlite3.connect(ELECTION_DB) as con:
        candidates = pd.read_sql("""SELECT canonical_candidate_id,person_id,year,chamber,district AS district_candidate,
          party AS canonical_party,ballot_name AS canonical_name,incumbent FROM fact_candidate_election""",con)
    scored=[]; eligible_votes=[]
    with sqlite3.connect(DB) as con:
        for cycle in WINDOWS:
            for chamber in ("house","senate"):
                part,votes=score_window(con,cycle,chamber)
                if not part.empty: scored.append(part)
                if not votes.empty:
                    votes["cycle"]=cycle;votes["chamber"]=chamber;eligible_votes.append(votes)
    scores=pd.concat(scored,ignore_index=True) if scored else pd.DataFrame()
    matched=[]
    for _,candidate in candidates.iterrows():
        base=candidate.to_dict(); match,method=match_candidate(candidate,scores) if candidate.year in WINDOWS else (None,"archive_unavailable_1994")
        if match is not None:
            base.update({k:v for k,v in match.to_dict().items() if k not in {"cycle","chamber"}})
            base["legislative_ideology_available"]=True
            base["coverage_status"]="scored_pre_election_legislative_behavior"
        else:
            base["legislative_ideology_available"]=False
            base["coverage_status"]="archive_unavailable_1994" if candidate.year==1994 else "no_verified_scored_pre_election_service"
        base["identity_match_method"]=method
        base["window_start"]=WINDOWS.get(candidate.year,(np.nan,np.nan))[0]
        base["window_end"]=WINDOWS.get(candidate.year,(np.nan,np.nan))[1]
        matched.append(base)
    result=pd.DataFrame(matched)
    result["cycle"] = result.year
    if eligible_votes:
        all_votes=pd.concat(eligible_votes,ignore_index=True)
        result=add_anchor_dimensions(result,all_votes)
    sponsorship_path=OUT/"candidate_sponsorship_issue_full_universe.csv"
    if sponsorship_path.exists():
        sponsorship=pd.read_csv(sponsorship_path)
        if not sponsorship.empty:
            sponsor_scores=(sponsorship.pivot_table(index="canonical_candidate_id",columns="issue_code",
                            values="sponsorship_issue_score",aggfunc="mean")
                            .add_prefix("sponsorship_issue_").reset_index())
            sponsor_counts=(sponsorship.pivot_table(index="canonical_candidate_id",columns="issue_code",
                            values="directional_sponsored_bills",aggfunc="sum")
                            .add_prefix("sponsorship_issue_bills_").reset_index())
            result=(result.merge(sponsor_scores,on="canonical_candidate_id",how="left",validate="one_to_one")
                    .merge(sponsor_counts,on="canonical_candidate_id",how="left",validate="one_to_one"))
    # Merge exact-election candidate-supplied PCT dimensions as parallel fields.
    pct_path=OUT/"votesmart_pct_candidate_cycle_features.csv"
    if pct_path.exists():
        pct=pd.read_csv(pct_path).drop_duplicates("canonical_candidate_id")
        pct_cols=[c for c in pct if c.endswith("_position") or c.endswith("_ideology")]
        pct=pct[["canonical_candidate_id","pct_dimensions_scored","pct_policies_scored"]+pct_cols]
        pct=pct.rename(columns={c:"votesmart_pct_"+c for c in pct_cols})
        result=result.merge(pct,on="canonical_candidate_id",how="left",validate="one_to_one")
    # Broader dimensions use only reviewed anchor-vote directions. Requiring at
    # least two issue families avoids presenting one isolated vote as a broad
    # ideology score. +1 remains conservative and -1 progressive.
    bundles={
        "legislative_social_ideology":["abortion","guns","immigration","gambling_cultural","healthcare_conscience","lgbtq_rights","criminal_justice","voting_elections"],
        "legislative_economic_ideology":["taxes_budget","labor_unions","public_employee_benefits",
            "school_choice","public_education","social_services","business_economic_development","healthcare","business_regulation"],
        "legislative_governance_ideology":["ethics_government","occupational_licensing","public_private_partnerships"],
    }
    for output,issues in bundles.items():
        columns=[f"legislative_issue_{issue}" for issue in issues if f"legislative_issue_{issue}" in result]
        result[output+"_dimensions"] = result[columns].notna().sum(axis=1)
        result[output] = result[columns].mean(axis=1,skipna=True).where(
            result[output+"_dimensions"].ge(2))
    pct_social=[c for c in ["votesmart_pct_abortion_position","votesmart_pct_guns_position",
                            "votesmart_pct_social_ideology"] if c in result]
    result["votesmart_pct_social_composite"] = result[pct_social].mean(axis=1,skipna=True).where(
        result[pct_social].notna().sum(axis=1).ge(2))
    result["best_available_social_ideology"] = result.votesmart_pct_social_composite.fillna(
        result.legislative_social_ideology)
    result["best_available_social_source"] = np.select(
        [result.votesmart_pct_social_composite.notna(),result.legislative_social_ideology.notna()],
        ["candidate_supplied_votesmart_pct","reviewed_pre_election_legislative_votes"],default="unavailable")
    result["best_available_economic_ideology"] = result.get(
        "votesmart_pct_economic_ideology",pd.Series(np.nan,index=result.index)).fillna(
            result.legislative_economic_ideology)
    result["best_available_economic_source"] = np.select(
        [result.get("votesmart_pct_economic_ideology",pd.Series(np.nan,index=result.index)).notna(),
         result.legislative_economic_ideology.notna()],
        ["candidate_supplied_votesmart_pct","reviewed_pre_election_legislative_votes"],default="unavailable")
    sponsor_cols=[c for c in result if c.startswith("sponsorship_issue_") and not c.startswith("sponsorship_issue_bills_")]
    result["sponsorship_ideology_available"] = result[sponsor_cols].notna().any(axis=1) if sponsor_cols else False
    result["any_ideology_evidence"] = (result.legislative_ideology_available | result.pct_dimensions_scored.notna()
                                       | result.sponsorship_ideology_available)
    result = result.drop(columns="cycle")
    OUT.mkdir(parents=True,exist_ok=True)
    result.to_csv(OUT/"candidate_ideology_full_universe.csv",index=False)
    coverage=(result.groupby(["year","canonical_party"],as_index=False)
              .agg(candidates=("canonical_candidate_id","size"),legislative_scores=("legislative_ideology_available","sum"),
                   pct_profiles=("pct_dimensions_scored","count"),any_ideology=("any_ideology_evidence","sum")))
    coverage["any_ideology_share"]=coverage.any_ideology/coverage.candidates
    coverage.to_csv(OUT/"candidate_ideology_full_coverage.csv",index=False)
    scores.to_csv(OUT/"legislator_pre_election_window_scores.csv",index=False)
    print(coverage.to_string(index=False))


if __name__=="__main__": main()
