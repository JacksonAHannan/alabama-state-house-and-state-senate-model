"""Build provisional 2026 incumbency from 2022 winners and saved-page annotations."""
from pathlib import Path
import sqlite3
import pandas as pd
from build_incumbency_features import best_match

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"processed"/"war"
DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"

def main():
    final=OUT/"2026_final_candidate_roster.csv"; certified=OUT/"2026_certified_candidate_roster.csv"
    roster=pd.read_csv(final if final.exists() else certified if certified.exists() else OUT/"2026_candidate_roster_provisional.csv")
    if "incumbent_wikipedia" not in roster:
        provisional=pd.read_csv(OUT/"2026_candidate_roster_provisional.csv")
        annotations=(provisional.groupby(["chamber","district","party"],as_index=False)
                     .incumbent_wikipedia.max())
        roster=roster.merge(annotations,on=["chamber","district","party"],how="left")
        roster["incumbent_wikipedia"]=roster.incumbent_wikipedia.fillna(False)
    with sqlite3.connect(DB) as connection:
        winners=pd.read_sql("""select chamber,canonical_name,canonical_party from canonical_candidates
            where year=2022 and winner=1""",connection)
    rows=[]
    for candidate in roster.itertuples(index=False):
        pool=winners[winners.chamber.eq(candidate.chamber)]
        found,score=best_match(candidate.candidate,pool.canonical_name.tolist())
        prior=bool(found)
        annotated=bool(candidate.incumbent_wikipedia)
        rows.append({"cycle":2026,"chamber":candidate.chamber,"district":candidate.district,
                     "party":candidate.party,"candidate":candidate.candidate,"incumbent":prior or annotated,
                     "prior_winner_match":found,"prior_winner_match_score":score,
                     "incumbent_wikipedia":annotated,
                     "incumbency_source":"2022_winner_match+wikipedia_annotation" if prior and annotated else
                       "2022_winner_match" if prior else "wikipedia_annotation" if annotated else "not_incumbent"})
    candidates=pd.DataFrame(rows); candidates.to_csv(OUT/"2026_candidate_incumbency.csv",index=False)
    candidates[(candidates.incumbent)&(
        candidates.prior_winner_match_score.lt(.95)|
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
