"""Build 2026 incumbency from resolved 2022 winners and later annotations."""
from pathlib import Path
import pandas as pd
from build_incumbency_features import best_match

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"processed"/"war"
CANONICAL=ROOT/"data"/"processed"/"elections"/"canonical_cmo_candidates.csv"
IDENTITIES=ROOT/"data"/"processed"/"ideology"/"candidate_legislator_identity_crosswalk.csv"
VOTE_NAMES=OUT/"2022_wikipedia_vote_validation.csv"
MANUAL=ROOT/"data"/"manual"/"candidates"/"2026_incumbency_overrides.csv"


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}

def main():
    final=OUT/"2026_final_candidate_roster.csv"; certified=OUT/"2026_certified_candidate_roster.csv"
    roster=pd.read_csv(final if final.exists() else certified if certified.exists() else OUT/"2026_candidate_roster_provisional.csv")
    if "incumbent_wikipedia" not in roster:
        provisional=pd.read_csv(OUT/"2026_candidate_roster_provisional.csv")
        annotations=(provisional.groupby(["chamber","district","party"],as_index=False)
                     .incumbent_wikipedia.max())
        roster=roster.merge(annotations,on=["chamber","district","party"],how="left")
        roster["incumbent_wikipedia"]=roster.incumbent_wikipedia.map(truthy)
    canonical=pd.read_csv(CANONICAL)
    identities=pd.read_csv(IDENTITIES,usecols=["canonical_candidate_id","resolved_name","name_source"])
    vote_names=pd.read_csv(VOTE_NAMES)
    vote_names=(vote_names[vote_names.name_match_status.eq("matched")]
                [["chamber","district","party","votes_modeled","candidate_wikipedia"]]
                .rename(columns={"party":"canonical_party","votes_modeled":"canonical_votes"}))
    winners=(canonical[canonical.year.eq(2022)&canonical.winner.fillna(False).astype(bool)]
             .merge(identities,on="canonical_candidate_id",how="left",validate="one_to_one")
             .merge(vote_names,on=["chamber","district","canonical_party","canonical_votes"],
                    how="left",validate="one_to_one"))
    resolved_usable=winners.resolved_name.fillna("").ne("")&~winners.resolved_name.fillna("").str.match(r"^GS[UH]\d+")
    winners["winner_name"]=winners.resolved_name.where(resolved_usable,winners.candidate_wikipedia)
    winners["winner_name"]=winners.winner_name.fillna(winners.canonical_name)
    rows=[]
    for candidate in roster.itertuples(index=False):
        pool=winners[winners.chamber.eq(candidate.chamber)&winners.district.eq(int(candidate.district))&
                     winners.canonical_party.eq(candidate.party)]
        found,score=best_match(candidate.candidate,pool.winner_name.tolist())
        match_scope="same_district_party"
        if not found:
            fallback=winners[winners.chamber.eq(candidate.chamber)&winners.canonical_party.eq(candidate.party)]
            found,score=best_match(candidate.candidate,fallback.winner_name.tolist())
            pool=fallback
            match_scope="same_chamber_party_fallback" if found else "unmatched"
        prior=bool(found)
        matched=pool[pool.winner_name.eq(found)].iloc[0] if prior else None
        annotated=truthy(candidate.incumbent_wikipedia)
        rows.append({"cycle":2026,"chamber":candidate.chamber,"district":candidate.district,
                     "party":candidate.party,"candidate":candidate.candidate,"incumbent":prior or annotated,
                     "prior_winner_match":found,"prior_winner_match_score":score,
                     "prior_winner_candidate_id":matched.canonical_candidate_id if prior else None,
                     "prior_winner_district":int(matched.district) if prior else None,
                     "prior_winner_name_source":matched.name_source if prior else None,
                     "prior_winner_match_scope":match_scope,
                     "incumbent_wikipedia":annotated,
                     "incumbency_source":"2022_winner_match+wikipedia_annotation" if prior and annotated else
                       "2022_winner_match" if prior else "wikipedia_annotation" if annotated else "not_incumbent"})
    candidates=pd.DataFrame(rows)
    if MANUAL.exists():
        overrides=pd.read_csv(MANUAL)
        for override in overrides.itertuples(index=False):
            key=(candidates.chamber.eq(override.chamber)&candidates.district.eq(int(override.district))&
                 candidates.party.eq(override.party)&candidates.candidate.eq(override.candidate))
            if key.sum()!=1:
                raise ValueError(f"Incumbency override matched {key.sum()} rows: {override.candidate}")
            candidates.loc[key,"incumbent"]=truthy(override.incumbent)
            candidates.loc[key,"incumbency_source"]=f"manual_override:{override.resolution}"
    candidates.to_csv(OUT/"2026_candidate_incumbency.csv",index=False)
    candidates[(candidates.incumbent)&(
        candidates.prior_winner_match_score.lt(.95)|
        candidates.prior_winner_match_scope.ne("same_district_party")|
        candidates.incumbent_wikipedia.ne(candidates.prior_winner_match.notna()))].to_csv(
            OUT/"2026_incumbency_review.csv",index=False)
    races=(candidates.groupby(["cycle","chamber","district"],as_index=False)
           .agg(incumbent_count=("incumbent","sum"),candidate_count=("candidate","size")))
    races["incumbency_status"]=races.incumbent_count.map({0:"open",1:"incumbent_running"}).fillna("multiple_incumbents")
    races["incumbency_ready"]=races.candidate_count.gt(0)&races.incumbent_count.le(1)
    races.to_csv(OUT/"2026_race_incumbency.csv",index=False)
    print(races.groupby("incumbency_status").size().to_string())
    print(f"Ready: {races.incumbency_ready.sum()}/{len(races)}")

if __name__=="__main__": main()
