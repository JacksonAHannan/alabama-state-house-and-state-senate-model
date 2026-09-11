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
from legiscan_eligibility import checked_standalone

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


def score_period(connection: sqlite3.Connection, start: int, end: int, chamber: str,
                 cycle: int) -> tuple[pd.DataFrame, pd.DataFrame]:
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


def score_window(connection: sqlite3.Connection, cycle: int, chamber: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = WINDOWS[cycle]
    return score_period(connection, start, end, chamber, cycle)


def match_candidate(row: pd.Series, scores: pd.DataFrame) -> tuple[pd.Series|None,str]:
    pool = scores[(scores.cycle.eq(row.year)) & (scores.chamber.eq(row.chamber))]
    name, surname = member_name_parts(row.get("resolved_name", row.canonical_name))
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
        district_hit = re.search(r"(\d+)", str(row.district_candidate or ""))
        candidate_district = float(district_hit.group(1)) if district_hit else np.nan
        if pd.notna(candidate_district) and member_district.notna().any():
            surname_hit = surname_hit[member_district.eq(candidate_district)]
        if len(surname_hit)==1:
            return surname_hit.iloc[0],"surname_party_district_window"
    if bool(row.get("expected_prior_officeholder", row.incumbent)):
        district = pd.to_numeric(pool.district,errors="coerce")
        parsed = re.search(r"(\d+)", str(row.district_candidate or ""))
        candidate_district = float(parsed.group(1)) if parsed else np.nan
        hit = pool[(district.eq(candidate_district)) & pool.party.eq(row.canonical_party)
                   & pool.surname.eq(surname)]
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
    identity_key = ["year"] + (["chamber"] if "chamber" in result else []) + ["member_source_id"]
    conflicts = result[assigned & result.duplicated(identity_key, keep=False)]
    for _, group in conflicts.groupby(identity_key, sort=False):
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
    join_chamber = "score_chamber" if "score_chamber" in rows.columns else "chamber"
    if join_chamber != "chamber":
        score_wide = score_wide.rename(columns={"chamber": join_chamber})
        count_wide = count_wide.rename(columns={"chamber": join_chamber})
        source_counts = source_counts.rename(columns={"chamber": join_chamber})
    keys = ["cycle", join_chamber, "member_source_id"]
    return (rows.merge(score_wide,on=keys,how="left")
            .merge(count_wide,on=keys,how="left")
            .merge(source_counts,on=keys,how="left"))


def main() -> None:
    with sqlite3.connect(ELECTION_DB) as con:
        candidates = pd.read_sql("""SELECT canonical_candidate_id,person_id,year,chamber,district AS district_candidate,
          party AS canonical_party,ballot_name AS canonical_name,incumbent,winner
          FROM fact_candidate_election""",con)
    candidates["incumbent"] = candidates.incumbent.fillna(0).astype(int)
    candidates["winner"] = candidates.winner.fillna(0).astype(int)
    candidates = candidates.sort_values(
        ["person_id", "year", "chamber", "district_candidate"]
    ).copy()
    prior_win = (candidates.year.where(candidates.winner.eq(1))
                 .groupby(candidates.person_id).transform(lambda x: x.shift().cummax()))
    candidates["prior_winner_i"] = prior_win.lt(candidates.year).fillna(False)
    candidates["expected_prior_officeholder"] = (
        candidates.incumbent.eq(1) | candidates.prior_winner_i
    )
    identities = pd.read_csv(OUT / "candidate_legislator_identity_crosswalk.csv", low_memory=False)
    identity_cols = ["canonical_candidate_id", "resolved_name", "name_source", "people_id",
                     "member_source_id", "member_display_name", "first_session", "last_session",
                     "legislative_sessions", "identity_status", "identity_match_method"]
    candidates = candidates.merge(identities[identity_cols], on="canonical_candidate_id",
                                  how="left", validate="one_to_one")
    scored=[]; eligible_votes=[]; career_scored=[]; career_votes=[]
    with checked_standalone(DB) as con:
        for cycle in WINDOWS:
            for chamber in ("house","senate"):
                part,votes=score_window(con,cycle,chamber)
                if not part.empty: scored.append(part)
                if not votes.empty:
                    votes["cycle"]=cycle;votes["chamber"]=chamber;eligible_votes.append(votes)
        for chamber in ("house", "senate"):
            part, votes = score_period(con, 1998, 2026, chamber, 2026)
            if not part.empty: career_scored.append(part)
            if not votes.empty:
                votes["cycle"] = 2026; votes["chamber"] = chamber; career_votes.append(votes)
    scores=pd.concat(scored,ignore_index=True) if scored else pd.DataFrame()
    score_features = [c for c in scores.columns if c not in {"cycle", "chamber", "member_source_id",
                                                              "member_display_name", "party", "district"}]
    candidates = candidates.rename(columns={"member_source_id": "identity_member_source_id"})
    score_join = scores.rename(columns={"cycle": "year", "chamber": "score_chamber",
                                        "member_display_name": "score_member_display_name",
                                        "party": "score_party", "district": "score_district"})
    result = candidates.merge(score_join, left_on=["year", "chamber", "identity_member_source_id"],
                              right_on=["year", "score_chamber", "member_source_id"],
                              how="left", validate="many_to_one")
    # A candidate can move chambers while retaining the same person identity.
    # If there is exactly one pre-election score for that person in the cycle,
    # use it and retain the score's chamber explicitly. This covers House-to-
    # Senate moves without pretending the votes occurred in the destination
    # chamber.
    cross_chamber_missing = (
        result.behavioral_ideology.isna() & result.identity_member_source_id.notna()
    )
    for idx in result.index[cross_chamber_missing]:
        options = scores[
            scores.cycle.eq(result.at[idx, "year"])
            & scores.member_source_id.eq(result.at[idx, "identity_member_source_id"])
        ]
        if len(options) != 1:
            continue
        match = options.iloc[0]
        for column, value in match.items():
            if column == "cycle":
                continue
            target = {"chamber": "score_chamber",
                      "member_display_name": "score_member_display_name",
                      "party": "score_party", "district": "score_district"}.get(column, column)
            result.loc[idx, target] = value
        result.loc[idx, "identity_match_method"] = (
            str(result.loc[idx, "identity_match_method"])
            + "+cross_chamber_pre_election_score"
        )
    # Historical journal identities predate LegiScan IDs.  Resolve those only
    # inside the relevant pre-election window using the already decoded name,
    # party, and parsed district; this does not alter the career identity.
    missing_score = (result.behavioral_ideology.isna() & result.year.isin(WINDOWS)
                     & ~result.identity_status.eq("ambiguous"))
    for idx in result.index[missing_score]:
        match, method = match_candidate(result.loc[idx], scores)
        if match is None:
            continue
        for column, value in match.items():
            if column not in {"cycle", "chamber"}:
                target = {"member_display_name": "score_member_display_name",
                          "party": "score_party", "district": "score_district"}.get(column, column)
                result.loc[idx, target] = value
        result.loc[idx, "score_chamber"] = match.chamber
        result.loc[idx, "identity_match_method"] = method
    score_columns = [c for c in score_join.columns if c != "year"]
    result = remove_duplicate_member_assignments(result, score_columns)
    result["legislative_ideology_available"] = result.behavioral_ideology.notna()
    result["coverage_status"] = np.select(
        [result.year.eq(1994), result.legislative_ideology_available,
         result.identity_member_source_id.notna() | result.member_source_id.notna()],
        ["archive_unavailable_1994", "scored_pre_election_legislative_behavior",
         "verified_identity_no_scored_pre_election_service"],
        default="no_verified_legislative_identity")
    result["window_start"] = result.year.map(lambda y: WINDOWS.get(y, (np.nan, np.nan))[0])
    result["window_end"] = result.year.map(lambda y: WINDOWS.get(y, (np.nan, np.nan))[1])
    result["cycle"] = result.year
    if eligible_votes:
        all_votes=pd.concat(eligible_votes,ignore_index=True)
        result=add_anchor_dimensions(result,all_votes)

    career_scores = pd.concat(career_scored, ignore_index=True) if career_scored else pd.DataFrame()
    if career_votes:
        career_scores = add_anchor_dimensions(career_scores, pd.concat(career_votes, ignore_index=True))
    member_roster = pd.read_csv(ROOT / "data/processed/legislative/legiscan_alabama_legislators.csv",
                                low_memory=False)
    member_roster["chamber"] = member_roster.role.map({"Rep": "house", "Sen": "senate"})
    career_identity = (member_roster[member_roster.chamber.notna()]
                       .groupby(["people_id", "chamber"], as_index=False)
                       .agg(member_display_name=("name", "last"), party=("party", "last"),
                            first_session=("session_year", "min"), last_session=("session_year", "max"),
                            legislative_sessions=("session_year", "nunique")))
    career_identity["member_source_id"] = "LEGISCAN-" + career_identity.people_id.astype(int).astype(str)
    candidate_links = (identities[identities.member_source_id.notna()]
                       .groupby(["chamber", "member_source_id"], as_index=False)
                       .agg(candidate_cycles_linked=("canonical_candidate_id", "nunique"),
                            latest_candidate_id=("canonical_candidate_id", "last"),
                            latest_resolved_name=("resolved_name", "last")))
    career = (career_identity.merge(candidate_links, on=["chamber", "member_source_id"], how="left")
              .merge(career_scores.drop(columns="cycle", errors="ignore"),
                     on=["chamber", "member_source_id"], how="left",
                     validate="one_to_one", suffixes=("_roster", "")))
    career["career_window_start"] = 1998
    career["career_window_end"] = 2026
    career["career_ideology_available"] = career.behavioral_ideology.notna()
    career.to_csv(OUT / "candidate_career_ideology_through_2026.csv", index=False)
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
    service = (member_roster[member_roster.chamber.notna()].groupby(["people_id", "chamber"], as_index=False)
               .agg(member_display_name=("name", "last"), sessions=("session_year", "nunique"),
                    first_session=("session_year", "min"), last_session=("session_year", "max")))
    service["member_source_id"] = "LEGISCAN-" + service.people_id.astype(int).astype(str)
    with checked_standalone(DB) as con:
        member_votes = pd.read_sql("""SELECT member_source_id, COUNT(*) AS raw_recorded_votes,
          COUNT(DISTINCT canonical_rollcall_id) AS raw_rollcalls
          FROM member_vote WHERE vote IN ('Yea','Nay') GROUP BY member_source_id""", con)
    mapped_ids = set(pd.read_csv(ROOT / "data/processed/legislative/frontier_rollcall_ontology_v3.csv",
                                 low_memory=False).query("decision == 'map'").canonical_rollcall_id)
    with checked_standalone(DB) as con:
        classified = pd.read_sql("""SELECT member_source_id,canonical_rollcall_id FROM member_vote
          WHERE vote IN ('Yea','Nay')""", con)
    classified = (classified[classified.canonical_rollcall_id.isin(mapped_ids)]
                  .groupby("member_source_id", as_index=False)
                  .agg(classified_votes=("canonical_rollcall_id", "size"),
                       classified_rollcalls=("canonical_rollcall_id", "nunique")))
    audit = (service[service.sessions.ge(4)].merge(member_votes, on="member_source_id", how="left")
             .merge(classified, on="member_source_id", how="left")
             .merge(career[["chamber", "member_source_id", "career_ideology_available"]],
                    on=["chamber", "member_source_id"], how="left", validate="one_to_one"))
    for column in ["raw_recorded_votes", "raw_rollcalls", "classified_votes", "classified_rollcalls"]:
        audit[column] = audit[column].fillna(0).astype(int)
    audit["candidate_identity_linked"] = audit.member_source_id.isin(set(
        identities.loc[identities.identity_status.eq("resolved"), "member_source_id"].dropna()))
    audit["coverage_flag"] = np.select(
        [audit.raw_recorded_votes.eq(0), audit.classified_votes.eq(0),
         ~audit.career_ideology_available.fillna(False)],
        ["missing_raw_votes", "missing_classified_votes", "insufficient_career_score"],
        default="covered")
    audit.to_csv(OUT / "long_service_ideology_coverage_audit.csv", index=False)
    print(coverage.to_string(index=False))
    print("Long-service audit:", audit.coverage_flag.value_counts().to_dict())


if __name__=="__main__": main()
