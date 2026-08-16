"""Build the remaining defensible historical context features for 1994."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import re
import sqlite3

import geopandas as gpd
import numpy as np
import pandas as pd

from build_candidate_finance_features import canonical_person
from build_presidential_district_features import _prepare_weights, allocate_to_districts
from sos_precinct import _workbook_sheets
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_source_file, register_table

CYCLE=1994; PRESIDENTIAL_YEAR=1992
ELECT=ROOT/"data"/"processed"/"elections"; PRES=ROOT/"data"/"processed"/"presidential"
DEM=ROOT/"data"/"processed"/"demographics"; WAR=ROOT/"data"/"processed"/"war"
SF3=ROOT/"data"/"raw"/"census"/"1990_sf3_alabama"/"all"
TRACTS=ROOT/"data"/"raw"/"census"/"1990_sf3_alabama"/"tracts"/"tr01_d90.shp"
PRES_RAW=ROOT/"data"/"raw"/"alabama_elections_and_geography"/"92g-prec_0"/"92g-prec"
SHOR=ROOT/"data"/"raw"/"ideology"/"shor_mccarty_individual_legislators_1993_2018.tsv"
SCHEMA=Path(__file__).with_name("warehouse_1994_context_schema.sql")
KNOWN_1992_PRESIDENTIAL_GAPS={"MONTGOMERY","TALLADEGA","WILCOX"}
COUNTY_1994_ALIASES={"COVINGTN":"COVINGTON","JEFFERSN":"JEFFERSON","LADRDALE":"LAUDERDALE",
 "LIMSTONE":"LIMESTONE","MONTGMRY":"MONTGOMERY","TALADEGA":"TALLADEGA",
 "TALPOOSA":"TALLAPOOSA","TSCLOOSA":"TUSCALOOSA","WASHNTON":"WASHINGTON"}
PLANS={
 "house":(ROOT/"data"/"raw"/"alabama_elections_and_geography"/"al_lower_1992_2000"/"al_lower_1992_2000.shp","DISTRICT"),
 "senate":(ROOT/"data"/"raw"/"alabama_elections_and_geography"/"al_upper_1992_2000"/"al_upper_1992_2000.shp","SLDUST00"),
}


def read_dbf(path: Path) -> pd.DataFrame:
    return pd.DataFrame(gpd.read_file(path,ignore_geometry=True))


def tract_demographics() -> gpd.GeoDataFrame:
    geography=read_dbf(SF3/"stf300al.dbf")
    seg1=read_dbf(SF3/"stf301al.dbf")
    seg10=read_dbf(SF3/"stf310al.dbf")
    keys=["LOGRECNU","CNTY","TRACTBNA"]
    geo=geography[geography.SUMLEV.eq("140")][keys+["POP100"]]
    race=seg1[seg1.SUMLEV.eq("140")][keys+["P0010001","P0080001"]]
    p57=[f"P057{i:04d}" for i in range(1,8)]
    p58=[f"P058{i:04d}" for i in range(1,8)]
    edu=seg10[seg10.SUMLEV.eq("140")][keys+p57+p58]
    data=geo.merge(race,on=keys,validate="one_to_one").merge(edu,on=keys,validate="one_to_one")
    for column in ["P0010001","P0080001",*p57,*p58]: data[column]=pd.to_numeric(data[column],errors="coerce")
    data["total_population"]=data.P0010001
    data["white_population"]=data.P0080001
    data["age25_population"]=data[p57].sum(axis=1,min_count=1)
    data["college_population"]=data[["P0570006","P0570007"]].sum(axis=1,min_count=1)
    data["white_age25_population"]=data[p58].sum(axis=1,min_count=1)
    data["white_college_population"]=data[["P0580006","P0580007"]].sum(axis=1,min_count=1)
    data["tract_key"]=data.CNTY.astype(str).str.zfill(3)+"|"+data.TRACTBNA.astype(str).str.zfill(6)
    shapes=gpd.read_file(TRACTS)
    # The legacy Census cartographic archive predates .prj sidecars. Its
    # documented coordinates are geographic NAD83, matching the legislative
    # plan archive; declare rather than transform the source coordinates.
    if shapes.crs is None: shapes=shapes.set_crs(4269)
    shapes["tract_key"]=shapes.CO.astype(str).str.zfill(3)+"|"+(shapes.TRACTBASE.fillna("").astype(str)+shapes.TRACTSUF.fillna("").astype(str)).str.zfill(6)
    shapes=shapes.dissolve("tract_key",as_index=False)
    columns=["tract_key","total_population","white_population","age25_population",
             "white_age25_population","college_population","white_college_population"]
    return shapes.merge(data[columns],on="tract_key",how="inner",validate="one_to_one")


def district_demographics() -> pd.DataFrame:
    tracts=tract_demographics().to_crs(5070)
    statewide_source=float(tracts.total_population.sum()); frames=[]
    for chamber,(path,district_col) in PLANS.items():
        districts=gpd.read_file(path)[[district_col,"geometry"]].rename(columns={district_col:"district"})
        districts["district"]=pd.to_numeric(districts.district,errors="raise").astype(int)
        districts=districts.to_crs(5070)
        intersection=gpd.overlay(tracts,districts,how="intersection",keep_geom_type=False)
        tract_area=tracts.set_index("tract_key").geometry.area
        intersection["area_share"]=intersection.geometry.area/intersection.tract_key.map(tract_area)
        count_cols=["total_population","white_population","age25_population","white_age25_population",
                    "college_population","white_college_population"]
        for column in count_cols: intersection[column]=intersection[column]*intersection.area_share
        result=intersection.groupby("district",as_index=False)[count_cols].sum()
        result["nonwhite_share"]=1-result.white_population/result.total_population.where(result.total_population.gt(0))
        result["college_share"]=result.college_population/result.age25_population.where(result.age25_population.gt(0))
        result["white_college_share"]=result.white_college_population/result.white_age25_population.where(result.white_age25_population.gt(0))
        result["source_population_coverage"]=result.total_population.sum()/statewide_source
        result["allocation_method"]="1990_sf3_tract_area_interpolation_provisional"
        result["census_vintage"]=1990;result["chamber"]=chamber;result["cycle"]=CYCLE
        frames.append(result)
    return pd.concat(frames,ignore_index=True)


def county_from_workbook(sheets: dict[str,list[list[object]]],fallback: str) -> str:
    for rows in sheets.values():
        for row in rows[:8]:
            for value in row[:5]:
                match=re.search(r"(.+?)\s+County(?:\s+1992)?$",str(value).strip(),re.I)
                if match:return match.group(1).strip()
    return fallback


def presidential_precincts() -> pd.DataFrame:
    records=[]
    for path in sorted(PRES_RAW.glob("*.*")):
        if path.name.lower()=="readme.txt":continue
        sheets=_workbook_sheets(path.read_bytes());county=county_from_workbook(sheets,path.stem)
        for rows in sheets.values():
            if not rows:continue
            width=max(map(len,rows));padded=[row+[""]*(width-len(row)) for row in rows]
            header_index=None;clinton=bush=None
            for i,row in enumerate(padded[:15]):
                labels=[str(value).strip().upper() for value in row]
                if "CLINTON" in labels and "BUSH" in labels:
                    header_index=i;clinton=labels.index("CLINTON");bush=labels.index("BUSH");break
            if header_index is None:continue
            carried_name=""
            for row in padded[header_index+1:]:
                dem=pd.to_numeric(row[clinton],errors="coerce");rep=pd.to_numeric(row[bush],errors="coerce")
                if pd.isna(dem) and pd.isna(rep):continue
                name=str(row[2]).strip() if len(row)>2 else ""
                # Several workbooks merge a precinct-name cell vertically over
                # multiple numbered ballot boxes. Spreadsheet readers expose
                # the later rows as blank, so carry the printed name downward.
                if name:carried_name=name
                else:name=carried_name
                if not name or re.search(r"TOTAL",name,re.I):continue
                records.append({"cycle":PRESIDENTIAL_YEAR,"county_key":county.upper(),"precinct_key":name.upper(),
                    "dem_candidate":"Bill Clinton","rep_candidate":"George H. W. Bush",
                    "dem_votes":float(0 if pd.isna(dem) else dem),"rep_votes":float(0 if pd.isna(rep) else rep),
                    "source_file":path.name})
    result=pd.DataFrame(records)
    result=(result.groupby(["cycle","county_key","precinct_key","dem_candidate","rep_candidate","source_file"],as_index=False)
            [["dem_votes","rep_votes"]].sum())
    observed=set(result.county_key)
    # Wilcox is absent per the archive README; Montgomery and Talladega files
    # contain blank presidential columns. Preserve all three as source gaps.
    all_counties=set(county_from_workbook(_workbook_sheets(path.read_bytes()),path.stem).upper()
                     for path in PRES_RAW.glob("*.*") if path.name.lower()!="readme.txt")|{"WILCOX"}
    if all_counties-observed!=KNOWN_1992_PRESIDENTIAL_GAPS:
        raise ValueError(f"Unexpected 1992 presidential county gaps: {sorted(all_counties-observed)}")
    return result


def presidential_features(precincts: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    raw_weights=pd.read_csv(ELECT/"1994_precinct_district_ballot_weights.csv")
    raw_weights["county_key"]=raw_weights.county_key.replace(COUNTY_1994_ALIASES)
    # Several 1994 counties append the senate ballot split (for example
    # ``SD3-2``) to the polling-place label. It identifies the district slice,
    # not a different polling place, and the district column already preserves
    # that information.
    raw_weights["precinct_key"]=raw_weights.precinct_key.astype(str).str.replace(
        r"\s+SD\s*\d+(?:-\d+)?$","",regex=True,case=False)
    weights=_prepare_weights(raw_weights,CYCLE)
    district,matches=allocate_to_districts(precincts,weights,PRESIDENTIAL_YEAR)
    universe=pd.concat([pd.DataFrame({"chamber":"house","district":range(1,106)}),
                        pd.DataFrame({"chamber":"senate","district":range(1,36)})],ignore_index=True)
    district=universe.merge(district,on=["chamber","district"],how="left",validate="one_to_one")
    district= district.rename(columns={
      "pres_1992_dem_votes":"dem_votes","pres_1992_rep_votes":"rep_votes",
      "pres_1992_two_party_votes":"two_party_votes","pres_1992_dem_margin":"dem_margin",
      "pres_1992_fallback_share":"fallback_share","pres_1992_source_complete":"source_complete"})
    district["cycle"]=CYCLE;district["source_year"]=PRESIDENTIAL_YEAR
    district["source_complete"]=district["source_complete"].fillna(False)
    district.loc[district.dem_margin.isna(),"source_complete"]=False
    district["allocation_method"]="precinct_match_then_legislative_activity_fallback"
    return district,matches


def candidates() -> pd.DataFrame:
    with sqlite3.connect(ELECT/"alabama_elections.sqlite") as connection:
        return pd.read_sql_query("""SELECT canonical_candidate_id,year AS cycle,chamber,district,
          canonical_party AS party,canonical_name AS candidate FROM canonical_candidates
          WHERE year=1994 AND canonical_party IN ('D','R')""",connection)


def incumbency(candidate: pd.DataFrame) -> pd.DataFrame:
    prior=pd.read_csv(ELECT/"historical_candidate_results.csv")
    prior=prior[prior.year.eq(1990)&prior.winner.eq(1)].copy()
    candidate=candidate.copy();candidate["surname"]=candidate.candidate.map(canonical_person).str.split().str[-1]
    prior["surname"]=prior.normalized_name.str.split().str[-1]
    shor=pd.read_csv(SHOR,sep="\t");shor=shor[shor.st.eq("AL")].copy()
    shor["surname"]=shor.name.astype(str).str.split(",").str[0].map(canonical_person).str.split().str[-1]
    rows=[]
    for row in candidate.itertuples(index=False):
        pool=prior[(prior.chamber.eq(row.chamber))&(prior.surname.eq(row.surname))]
        current_same=candidate[(candidate.chamber.eq(row.chamber))&(candidate.surname.eq(row.surname))]
        accepted=len(pool)==1 and len(current_same)==1
        hit=pool.iloc[0] if accepted else None
        current_party=row.party;party_method="1994_ballot_order"
        # A lone 1994 candidate was mechanically assigned the first ballot
        # position by the source parser. For an unopposed winner, validate the
        # actual current party against Shor-McCarty's 1996 serving roster.
        race_size=len(candidate[(candidate.chamber.eq(row.chamber))&(candidate.district.eq(row.district))])
        chamber_flag="house1996" if row.chamber=="house" else "senate1996"
        shor_pool=shor[shor[chamber_flag].notna()&shor.surname.eq(row.surname)]
        if race_size==1 and len(shor_pool)==1:
            current_party=shor_pool.iloc[0].party;party_method="shor_mccarty_1996_serving_roster"
        rows.append({"canonical_candidate_id":row.canonical_candidate_id,"cycle":CYCLE,"chamber":row.chamber,
          "district":row.district,"party":current_party,"candidate":row.candidate,"incumbent":int(accepted),
          "prior_candidate_name":hit.candidate_name if accepted else None,"prior_party":hit.party if accepted else None,
          "match_method":(("unique_chamber_surname_to_1990_winner" if accepted else "no_unique_prior_winner_match")+"+"+party_method),
          "match_confidence":"medium" if accepted else "low","review_status":"supported" if accepted else "unknown"})
    return pd.DataFrame(rows)


def finance_coverage(candidate: pd.DataFrame) -> pd.DataFrame:
    result=candidate.copy();result["total_resources_raised"]=np.nan
    result["observation_status"]="not_observed_unknown_not_zero";result["source_name"]=None
    result["coverage_note"]="DIME Alabama state-legislative recipient coverage begins in 1998; no 1994 observation is treated as zero"
    return result


def combined_context(demographics: pd.DataFrame,president: pd.DataFrame,inc: pd.DataFrame,finance: pd.DataFrame) -> pd.DataFrame:
    context=demographics[["cycle","chamber","district","nonwhite_share","college_share","white_college_share","allocation_method"]].rename(columns={"allocation_method":"demographics_method"})
    race_inc=(inc.groupby(["cycle","chamber","district","party"]).incumbent.max().unstack(fill_value=0).reset_index())
    for party in ("D","R"):
        if party not in race_inc:race_inc[party]=0
    race_inc=race_inc.rename(columns={"D":"dem_incumbent","R":"rep_incumbent"})
    race_fin=(finance.groupby(["cycle","chamber","district"]).total_resources_raised
              .agg(lambda values: int(values.notna().sum()==2)).reset_index(name="finance_complete"))
    race_fin["log_resource_ratio_d_to_r"]=np.nan
    pres=president[["cycle","chamber","district","dem_margin","fallback_share","source_complete"]].rename(columns={
      "dem_margin":"pres_1992_dem_margin","fallback_share":"pres_1992_fallback_share",
      "source_complete":"pres_1992_source_complete"})
    return (context.merge(race_inc,on=["cycle","chamber","district"],how="left",validate="one_to_one")
            .merge(race_fin,on=["cycle","chamber","district"],how="left",validate="one_to_one")
            .merge(pres,on=["cycle","chamber","district"],how="left",validate="one_to_one"))


def main() -> None:
    demographics=district_demographics();precincts=presidential_precincts()
    president,matches=presidential_features(precincts);candidate=candidates()
    inc=incumbency(candidate);finance=finance_coverage(candidate)
    context=combined_context(demographics,president,inc,finance)
    DEM.mkdir(parents=True,exist_ok=True);PRES.mkdir(parents=True,exist_ok=True)
    demographics.to_csv(DEM/"1994_district_demographics.csv",index=False)
    precincts.to_csv(PRES/"1992_president_precinct.csv",index=False)
    matches.to_csv(PRES/"1992_to_1994_precinct_match.csv",index=False)
    president.to_csv(PRES/"1994_district_presidential_features.csv",index=False)
    inc.to_csv(ELECT/"1994_candidate_incumbency.csv",index=False)
    finance.to_csv(WAR/"1994_candidate_finance_coverage.csv",index=False)
    context.to_csv(ELECT/"1994_cmo_context_features.csv",index=False)

    table_frames={"mart_historical_district_demographic_feature":demographics,
      "source_historical_presidential_precinct":precincts,
      "mart_historical_district_presidential_feature":president,
      "mart_historical_candidate_incumbency":inc,
      "mart_historical_candidate_finance_coverage":finance,
      "mart_historical_cmo_context_feature":context}
    with closing(connect()) as connection:
        initialize(connection);connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run=begin_run(connection,"historical_1994_context",{"cycle":CYCLE,"census_vintage":1990,"presidential_source_year":1992})
        for provider,path,scope in [("us_census",SF3/"stf300al.dbf","1990_sf3_geography"),
          ("us_census",SF3/"stf301al.dbf","1990_sf3_population_race"),("us_census",SF3/"stf310al.dbf","1990_sf3_education"),
          ("us_census",TRACTS,"1990_census_tract_geometry"),("alabama_sos_lublin_archive",PRES_RAW/"AUTAUGA.XLS","1992_presidential_precinct_directory_sample"),
          ("shor_mccarty",SHOR,"incumbency_validation_context")]:
            register_source_file(connection,provider=provider,path=path,extraction_status="normalized",authoritative_scope=scope)
        for table,frame in table_frames.items():
            connection.execute(f"DELETE FROM {table} WHERE cycle=?",(CYCLE if table!='source_historical_presidential_precinct' else PRESIDENTIAL_YEAR,))
            write=frame.copy()
            for col in ["source_complete","incumbent","finance_complete","dem_incumbent","rep_incumbent","pres_1992_source_complete"]:
                if col in write:write[col]=write[col].fillna(False).astype(int)
            write.to_sql(table,connection,if_exists="append",index=False)
            register_table(connection,table,"source" if table.startswith("source_") else "mart",
              "scripts/build_1994_context_features.py","cycle/chamber/district",
              "1990 Census SF3; 1992 official precinct returns; 1990 prior winners; DIME coverage contract",
              "replace",f"Auditable 1994 context: {table}")
        finish_run(connection,run,{"demographic_districts":len(demographics),"presidential_districts":len(president),
          "supported_incumbents":int(inc.incumbent.sum()),"finance_observed":int(finance.total_resources_raised.notna().sum()),
          "presidential_direct_match_share":float(matches.match_method.isin(['exact','fuzzy']).mean())})
        connection.commit()
    print(context.groupby("chamber").agg(districts=("district","size"),incumbents=("dem_incumbent","sum"),
      pres_complete=("pres_1992_source_complete","sum"),finance_complete=("finance_complete","sum")).to_string())
    print("Presidential precinct matching:",matches.match_method.value_counts().to_dict())


if __name__=="__main__":main()
