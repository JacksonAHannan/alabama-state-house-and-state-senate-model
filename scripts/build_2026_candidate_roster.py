"""Extract a provisional 2026 general-election nominee roster from saved pages."""
from pathlib import Path
import re
import pandas as pd
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"processed"/"war"
PAGES={
    "house":ROOT/"data"/"raw"/"alabama_elections_and_geography"/"2026 Alabama House of Representatives election - Wikipedia.html",
    "senate":ROOT/"data"/"raw"/"alabama_elections_and_geography"/"2026 Alabama Senate election - Wikipedia.html",
}
PARTIES={"Democratic primary":"D","Republican primary":"R"}

def clean(text):
    text=re.sub(r"\[[^]]*\]","",text)
    text=re.sub(r"\s+"," ",text).strip()
    return text.split(",")[0].strip()

def parse(path,chamber):
    soup=BeautifulSoup(path.read_text(encoding="utf-8"),"html.parser")
    records=[]; district=None; party=None
    for tag in soup.find_all(re.compile(r"^h[2-5]$")):
        title=tag.get_text(" ",strip=True).replace("[ edit ]","").strip()
        match=re.fullmatch(r"District\s+(\d+)",title,re.I)
        if match: district=int(match.group(1)); party=None; continue
        if title in PARTIES: party=PARTIES[title]; continue
        if title != "Nominee" or district is None or party is None: continue
        container=tag.find_parent("section") or tag.parent
        for item in container.find_all("li"):
            raw=item.get_text(" ",strip=True); candidate=clean(raw)
            if candidate and not re.search(r"withdrew|declined|disqualified",candidate,re.I):
                records.append({"cycle":2026,"chamber":chamber,"district":district,
                                "party":party,"candidate":candidate,
                                "incumbent_wikipedia":bool(re.search(r"incumbent (?:representative|senator)",raw,re.I)),
                                "roster_status":"provisional_wikipedia_nominee",
                                "source_file":path.name})
    columns=["cycle","chamber","district","party","candidate","incumbent_wikipedia","roster_status","source_file"]
    return pd.DataFrame(records,columns=columns).drop_duplicates(["chamber","district","party","candidate"])

def main():
    roster=pd.concat([parse(path,chamber) for chamber,path in PAGES.items()],ignore_index=True)
    roster.to_csv(OUT/"2026_candidate_roster_provisional.csv",index=False)
    final_path=OUT/"2026_final_candidate_roster.csv"; certified_path=OUT/"2026_certified_candidate_roster.csv"
    authoritative=pd.read_csv(final_path if final_path.exists() else certified_path) if (final_path.exists() or certified_path.exists()) else roster
    universe=pd.MultiIndex.from_tuples(
        [("house",d) for d in range(1,106)]+[("senate",d) for d in range(1,36)],
        names=["chamber","district"]).to_frame(index=False)
    counts=authoritative.pivot_table(index=["chamber","district"],columns="party",values="candidate",aggfunc="nunique",fill_value=0).reset_index()
    for party in ("D","R"):
        if party not in counts: counts[party]=0
    manifest=universe.merge(counts,on=["chamber","district"],how="left").fillna({"D":0,"R":0})
    manifest=manifest.rename(columns={"D":"dem_nominees","R":"rep_nominees"})
    manifest["candidate_roster_ready"]=manifest.dem_nominees.eq(1)&manifest.rep_nominees.eq(1)
    geo_path=OUT/"2026_geographic_crosswalk_qa.csv"
    geo_ready=set()
    if geo_path.exists():
        geo=pd.read_csv(geo_path)
        geo_ready=set(geo.loc[geo.districts.eq(geo.chamber.map({"house":105,"senate":35})),"chamber"])
    manifest["district_geometry_ready"]=manifest.chamber.isin(geo_ready)
    pres_path=ROOT/"data"/"processed"/"presidential"/"2026_district_presidential_features.csv"
    pres_ready=set()
    if pres_path.exists():
        pres=pd.read_csv(pres_path)
        valid=pres.pres_2024_dem_margin.notna()&pres.pres_2024_source_complete.astype(bool)
        pres_ready=set(map(tuple,pres.loc[valid,["chamber","district"]].to_records(index=False)))
    manifest["pres_2024_projection_ready"]=[(c,d) in pres_ready for c,d in zip(manifest.chamber,manifest.district)]
    acs_path=ROOT/"data"/"processed"/"demographics"/"2026_sld_demographics.csv"
    acs_ready=set()
    if acs_path.exists():
        acs=pd.read_csv(acs_path); valid=acs.nonwhite_share.notna()&acs.white_college_share.notna()
        acs_ready=set(map(tuple,acs.loc[valid,["chamber","district"]].to_records(index=False)))
    manifest["acs_features_ready"]=[(c,d) in acs_ready for c,d in zip(manifest.chamber,manifest.district)]
    incumbent_path=OUT/"2026_race_incumbency.csv"
    incumbent_ready=set()
    if incumbent_path.exists():
        incumbency=pd.read_csv(incumbent_path)
        incumbent_ready=set(map(tuple,incumbency.loc[incumbency.incumbency_ready,["chamber","district"]].to_records(index=False)))
    manifest["incumbency_ready"]=[(c,d) in incumbent_ready for c,d in zip(manifest.chamber,manifest.district)]
    finance_path=OUT/"race_finance_features.csv"
    if finance_path.exists():
        finance=pd.read_csv(finance_path)
        finance=finance[finance.cycle.eq(2026)][["chamber","district","finance_complete"]]
        manifest=manifest.merge(finance,on=["chamber","district"],how="left")
        manifest["finance_cutoff_ready"]=manifest.finance_complete.fillna(False).astype(bool)
        manifest=manifest.drop(columns="finance_complete")
    else:
        manifest["finance_cutoff_ready"]=False
    # Wikipedia nominee extraction is provisional until checked against an
    # official general-election ballot or filing roster.
    certified_keys=set(map(tuple,authoritative[["chamber","district"]].drop_duplicates().to_records(index=False))) if (final_path.exists() or certified_path.exists()) else set()
    manifest["official_ballot_ready"]=[(c,d) in certified_keys for c,d in zip(manifest.chamber,manifest.district)]
    manifest["model_validation_ready"]=False
    manifest["forecast_ready"]=manifest[[c for c in manifest if c.endswith("_ready")]].all(axis=1)
    manifest.to_csv(OUT/"2026_feature_readiness.csv",index=False)
    print(f"Provisional nominees parsed: {len(roster)}")
    print(manifest.candidate_roster_ready.value_counts().to_string())

if __name__=="__main__": main()
