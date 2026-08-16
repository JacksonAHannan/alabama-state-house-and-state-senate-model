"""Apply user-reviewed roster decisions to the OCR-certified 2026 roster."""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"processed"/"war"

def main():
    roster=pd.read_csv(OUT/"2026_certified_candidate_roster.csv")
    overrides=pd.read_csv(OUT/"2026_roster_manual_overrides.csv")
    applied=[]
    for row in overrides.itertuples(index=False):
        key=(roster.chamber.eq(row.chamber)&roster.district.eq(row.district)&roster.party.eq(row.party))
        roster=roster[~key].copy()
        record={column:pd.NA for column in roster.columns}
        record.update({"cycle":2026,"chamber":row.chamber,"district":int(row.district),"party":row.party,
                       "candidate":row.authoritative_name,"roster_status":"manual_reviewed_authoritative",
                       "parse_method":"manual_override","source_file":"2026_roster_manual_overrides.csv"})
        roster=pd.concat([roster,pd.DataFrame([record])],ignore_index=True)
        applied.append({"cycle":2026,"chamber":row.chamber,"district":row.district,"party":row.party,
                        "authoritative_name":row.authoritative_name,"resolution":row.resolution,"applied":True})
    if roster.duplicated(["chamber","district","party"]).any():
        raise ValueError("Manual roster contains duplicate chamber/district/party rows")
    roster=roster.sort_values(["chamber","district","party"])
    roster.to_csv(OUT/"2026_final_candidate_roster.csv",index=False)
    pd.DataFrame(applied).to_csv(OUT/"2026_roster_override_application.csv",index=False)
    print(roster.groupby(["party","chamber"]).size().to_string())
    print(f"Final candidates: {len(roster)}; contested D/R races: "
          f"{roster.groupby(['chamber','district']).party.agg(lambda x:set(x)>=set(['D','R'])).sum()}")

if __name__=="__main__": main()
