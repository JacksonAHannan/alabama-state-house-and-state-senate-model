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

from ideology_ontology_v3 import primitive_axis_direction

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
    # Historical ballots sometimes preserve surname only.  Never use a surname
    # fallback for a ballot record that contains a fuller name, and require the
    # recorded district when both sources expose one.  A merely unique surname
    # in the legislative pool is not enough (it previously attached, e.g., one
    # Thomas's record to another Thomas in a different district).
    same_party = pool[pool.party.eq(row.canonical_party)]
    surname_hit = same_party[same_party.surname.eq(surname)]
    candidate_is_surname_only = len(name.split()) == 1
    if candidate_is_surname_only and len(surname_hit):
        member_district = pd.to_numeric(surname_hit.district, errors="coerce")
        candidate_district = pd.to_numeric(pd.Series([row.district_candidate]), errors="coerce").iloc[0]
        if pd.notna(candidate_district) and member_district.notna().any():
            surname_hit = surname_hit[member_district.eq(candidate_district)]
        if len(surname_hit)==1:
            return surname_hit.iloc[0],"surname_party_district_window"
    if bool(row.incumbent):
        district = pd.to_numeric(pool.district,errors="coerce")
        hit = pool[(district.eq(float(row.district_candidate))) & pool.party.eq(row.canonical_party)]
        if len(hit)==1: return hit.iloc[0],"incumbent_district_party_window"
    return None,"unmatched_no_verified_legislative_identity"


def remove_duplicate_member_assignments(result: pd.DataFrame, score_columns: list[str]) -> pd.DataFrame:
    """Quarantine non-unique candidate-to-member assignments within a cycle.

    Candidate matching is deliberately conservative: one voting identity may
    not supply evidence to two candidate rows in the same election cycle.
    District agreement can select a single winner; otherwise every conflicting
    assignment is removed for manual resolution.
    """
    assigned = result.member_source_id.fillna("").ne("")
    conflicts = result[assigned & result.duplicated(["year", "member_source_id"], keep=False)]
    for _, group in conflicts.groupby(["year", "member_source_id"], sort=False):
        candidate_district = pd.to_numeric(group.district_candidate, errors="coerce")
        member_district = pd.to_numeric(group.district, errors="coerce")
        district_match = candidate_district.eq(member_district) & candidate_district.notna()
        keep = group.index[district_match] if district_match.sum() == 1 else []
        drop = group.index.difference(keep)
        result.loc[drop, score_columns] = np.nan
        result.loc[drop, "legislative_ideology_available"] = False
        result.loc[drop, "coverage_status"] = "ambiguous_legislative_identity_quarantined"
        result.loc[drop, "identity_match_method"] = "duplicate_member_assignment_rejected"
    return result


def add_anchor_dimensions(rows: pd.DataFrame, votes: pd.DataFrame) -> pd.DataFrame:
    """Attach only frontier-authorized ontology-v3 roll-call dimensions."""
    path = ROOT/"data"/"processed"/"legislative"/"frontier_rollcall_ontology_v3.csv"
    if not path.exists():
        return rows
    codes = pd.read_csv(path, low_memory=False).fillna("")
    codes = codes[codes.decision.eq("map")].copy()
    codes["human_issue_code"] = codes.primitive_axis
    codes["yea_direction"] = [primitive_axis_direction(a, p)
                               for a, p in zip(codes.primitive_axis, codes.policy_pole)]
    codes["classification_source"] = "frontier_manual_review:" + codes.translation_rule
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
    score_columns=[c for c in scores.columns if c not in {"cycle","chamber"}]
    result=remove_duplicate_member_assignments(result, score_columns)
    result["cycle"] = result.year
    if eligible_votes:
        all_votes=pd.concat(eligible_votes,ignore_index=True)
        result=add_anchor_dimensions(result,all_votes)
    # Sponsorship, amendment, and committee evidence are intentionally deferred.
    # Do not merge a stale optional sponsorship file into this direct-vote mart.
    # Merge exact-election candidate-supplied PCT dimensions as parallel fields.
    pct_path=OUT/"votesmart_pct_candidate_cycle_features.csv"
    if pct_path.exists():
        pct=pd.read_csv(pct_path).drop_duplicates("canonical_candidate_id")
        pct_cols=[c for c in pct if c.endswith("_position") or c.endswith("_ideology")]
        pct=pct[["canonical_candidate_id","pct_dimensions_scored","pct_policies_scored"]+pct_cols]
        pct=pct.rename(columns={c:"votesmart_pct_"+c for c in pct_cols})
        result=result.merge(pct,on="canonical_candidate_id",how="left",validate="one_to_one")
    # Convert issue-specific ontology coordinates into explicitly documented
    # conservative (+) / progressive (-) broad summaries. Guns and punitive
    # order are not folded into the social-morality bundle.
    bundle_signs={
        "legislative_social_ideology":{
            "abortion_access":-1, "christian_sexual_morality":1,
            "civil_social_liberty":-1, "racial_civil_rights":-1,
            "anti_discrimination":-1, "affirmative_action":-1,
        },
        "legislative_economic_ideology":{
            "tax_burden":-1, "tax_distribution":-1, "labor_rights":-1,
            "labor_capital_alignment":-1, "public_employee_compensation":-1,
            "market_governance":-1, "public_spending":-1,
            "education_public_funding":-1, "education_market_choice":1,
            "welfare_generosity":-1, "healthcare_access":-1,
        },
        "legislative_governance_ideology":{
            "voting_access":-1, "election_integrity_controls":1,
            "campaign_finance_disclosure":-1, "government_ethics_transparency":-1,
        },
    }
    for output,signs in bundle_signs.items():
        oriented=[]
        for issue,sign in signs.items():
            column=f"legislative_issue_{issue}"
            if column in result:
                oriented.append(result[column]*sign)
        frame=pd.concat(oriented,axis=1) if oriented else pd.DataFrame(index=result.index)
        result[output+"_dimensions"] = frame.notna().sum(axis=1)
        result[output] = frame.mean(axis=1,skipna=True).where(result[output+"_dimensions"].ge(2))
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
    result["sponsorship_ideology_available"] = False
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
