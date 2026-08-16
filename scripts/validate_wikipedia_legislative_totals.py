"""Validate official-derived legislative totals against saved Wikipedia tables.

Wikipedia is an independent secondary check, not a certified canvass. Pages may
contain primary and general-election tables, so validation succeeds when a
candidate-name match has exactly one vote total equal to the official result;
ambiguous or conflicting rows are retained for review.
"""
from pathlib import Path
import sqlite3
import pandas as pd
from build_incumbency_features import best_match, norm_name

ROOT=Path(__file__).resolve().parents[1]; WAR=ROOT/"data"/"processed"/"war"
DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"

def main():
    with sqlite3.connect(DB) as connection:
        official=pd.read_sql("""select year as cycle,chamber,district,
            canonical_party as party,canonical_name as candidate_display,
            canonical_votes as votes from canonical_candidates
            where canonical_party in ('D','R') and year in (2010,2014,2018,2022)""",connection)
    wiki=pd.read_csv(WAR/"wikipedia_legislative_candidates.csv")
    records=[]
    for row in official.itertuples(index=False):
        pool=wiki[(wiki.cycle.eq(row.cycle))&(wiki.chamber.eq(row.chamber))&
                  (wiki.district.eq(row.district))&(wiki.party.eq(row.party))].copy()
        pool["same_name"]=pool.candidate.map(norm_name).eq(norm_name(row.candidate_display))
        named=pool[pool.same_name]
        found=None; score=0.0
        if named.empty:
            found,score=best_match(row.candidate_display,pool.candidate.tolist())
            named=pool[pool.candidate.eq(found)] if found else pool.iloc[0:0]
        else:
            found=named.candidate.iloc[0]; score=1.0
        totals=sorted(set(pd.to_numeric(named.votes_wikipedia,errors="coerce").dropna().astype(int)))
        exact=int(row.votes) in totals
        if exact: status="exact"
        elif not totals: status="name_review"
        elif len(totals)>1: status="ambiguous_tables_review"
        else: status="vote_difference"
        records.append({"cycle":int(row.cycle),"chamber":row.chamber,"district":int(row.district),
            "party":row.party,"candidate_official":row.candidate_display,"candidate_wikipedia":found,
            "name_match_score":score,"votes_official":int(row.votes),
            "wikipedia_vote_options":" | ".join(map(str,totals)),"wikipedia_option_count":len(totals),
            "exact_vote_match":exact,"validation_status":status,
            "validation_source":"saved_wikipedia_secondary_not_certified"})
    out=pd.DataFrame(records)
    out.to_csv(WAR/"wikipedia_vote_validation.csv",index=False)
    out[~out.validation_status.eq("exact")].to_csv(WAR/"wikipedia_vote_validation_review.csv",index=False)
    summary=(out.groupby(["cycle","chamber","validation_status"]).size().rename("candidates").reset_index())
    summary.to_csv(WAR/"wikipedia_vote_validation_summary.csv",index=False)
    print(summary.to_string(index=False))
    print(f"\nExact secondary-source matches: {out.exact_vote_match.sum()}/{len(out)}")

if __name__=="__main__": main()
