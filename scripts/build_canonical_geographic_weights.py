"""Build district-allocation weights for canonical SOS precinct identities."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from build_geographic_crosswalks import (
    block_district_assignments,
    hierarchical_precinct_weights,
    match_precincts,
    reference_precinct_geometries,
    spatial_precinct_weights,
)
from oe_normalize import normalize_name

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"
OUT=ROOT/"data"/"processed"/"elections"

def clean_vtd(value):
    if pd.isna(value): return None
    text=str(value).strip()
    if text.endswith('.0'): text=text[:-2]
    return text.zfill(6)

def main():
    with sqlite3.connect(DB) as c:
        nodes=pd.read_sql("select node_id,year,county_key,precinct_key,county_level_ballot from precinct_nodes where source='alabama_sos' and year in (2010,2014,2018,2022)",c)
        links=pd.read_sql("select * from canonical_precinct_geography_links",c)
        legislative=pd.read_sql("""select year,county_key,precinct_key,office,district,votes
          from vote_observations where source='alabama_sos'
          and office in ('State House','State Senate') and district is not null
          and year in (2010,2014,2018,2022)""",c)
    links["vtd"]=links.vtd.map(clean_vtd)
    target=nodes.merge(links,left_on="node_id",right_on="source_node_id",how="left")
    county=gpd.read_file(ROOT/"data"/"raw"/"alabama_elections_and_geography"/"al_gen_22_prec"/"al_gen_22_st_prec.shp",ignore_geometry=True)
    county_map=county[["County","COUNTYFP"]].drop_duplicates(); county_map["county_norm"]=county_map.County.map(normalize_name)
    target["county_norm"]=target.county_key.map(normalize_name)
    target["county_norm"]=target.county_norm.replace({"STCLAIR":"SAINT CLAIR"})
    target=target.merge(county_map[["county_norm","COUNTYFP"]],on="county_norm",how="left").rename(columns={"COUNTYFP":"county_fips"})
    target["county_fips"]=target.county_fips.astype(str).str.zfill(3)
    target["cycle"]=target.year
    outputs=[]
    legislative["chamber"]=legislative.office.map({"State House":"house","State Senate":"senate"})
    activity=(legislative.groupby(
        ["year","chamber","county_key","precinct_key","district"],as_index=False
    ).votes.sum().rename(columns={"year":"cycle","votes":"district_activity"}))
    activity["precinct_activity"]=activity.groupby(
        ["cycle","chamber","county_key","precinct_key"]
    ).district_activity.transform("sum")
    activity["allocation_weight"]=activity.district_activity/activity.precinct_activity.where(
        activity.precinct_activity.gt(0))
    for cycle in (2010,2014,2018,2022):
        geometry=reference_precinct_geometries(cycle)
        refs=geometry[["county_fips","geometry_id","geometry_name","match_norm"]]
        current=target[target.year.eq(cycle)].copy()
        matches=match_precincts(current[["cycle","county_key","precinct_key","county_fips"]],refs,"geometry_id")
        alias_path=ROOT/"data"/"manual"/"precinct_history"/"canonical_2022_precinct_geometry_aliases.csv"
        if cycle==2022 and alias_path.exists():
            aliases=pd.read_csv(alias_path,dtype={"county_fips":str})
            aliases["county_fips"]=aliases.county_fips.str.zfill(3)
            aliases=aliases[aliases.review_status.eq("approved")].merge(
                refs[["county_fips","geometry_id","geometry_name"]],
                on=["county_fips","geometry_name"],how="left",validate="many_to_one")
            alias_ids=aliases.set_index(["county_key","precinct_key"]).geometry_id.to_dict()
            for index,row in matches.iterrows():
                override=alias_ids.get((row.county_key,row.precinct_key))
                if pd.notna(override):
                    matches.at[index,"geometry_id"]=override
                    matches.at[index,"match_method"]="manual_alias"
        matches["vtd"]=matches.geometry_id
        current=current.merge(
            matches[["county_key","precinct_key","geometry_id","match_method"]],
            on=["county_key","precinct_key"],how="left",validate="many_to_one")
        for chamber in ("house","senate"):
            blocks=spatial_precinct_weights(cycle,chamber)
            official=block_district_assignments(cycle,chamber)
            cycle_activity=activity[(activity.cycle.eq(cycle))&(activity.chamber.eq(chamber))]
            hierarchy=hierarchical_precinct_weights(cycle_activity,matches,blocks,official)
            direct=current.merge(
                hierarchy[["cycle","county_key","precinct_key","district","allocation_weight","allocation_method"]],
                on=["cycle","county_key","precinct_key"],how="inner",validate="many_to_many")
            direct["allocation_method"]="canonical_"+direct.allocation_method
            used=set(direct.node_id); fallback=current[~current.node_id.isin(used)].copy()
            spatial_missing=fallback[fallback.geometry_id.notna() & ~fallback.county_level_ballot.eq(1)].merge(
                blocks[["county_fips","geometry_id","district","allocation_weight"]],
                on=["county_fips","geometry_id"],how="inner",validate="many_to_many")
            spatial_missing["allocation_method"]="canonical_spatial_no_legislative_result"
            used_spatial=set(spatial_missing.node_id)
            fallback=fallback[~fallback.node_id.isin(used_spatial)].copy()
            county_weights=official.groupby(["county_fips","district"],as_index=False).population.sum()
            county_weights["allocation_weight"]=county_weights.population/county_weights.groupby("county_fips").population.transform("sum")
            fallback=fallback.merge(county_weights[["county_fips","district","allocation_weight"]],on="county_fips",how="left")
            is_batch = (fallback.county_level_ballot.eq(1) |
                        fallback.precinct_key.astype(str).str.upper().str.contains("ABSENT|PROV", regex=True))
            fallback["allocation_method"]=np.where(is_batch,"county_level_ballot","county_population_fallback")
            combined=pd.concat([direct,spatial_missing,fallback],ignore_index=True); combined["cycle"]=cycle; combined["chamber"]=chamber
            combined["vtd"]=combined.geometry_id.fillna(combined.vtd)
            outputs.append(combined[["cycle","chamber","node_id","county_key","precinct_key","vtd","district","allocation_weight","allocation_method"]])
    result=pd.concat(outputs,ignore_index=True)
    sums=result.groupby(["cycle","chamber","node_id"]).allocation_weight.sum()
    if not np.allclose(sums,1,atol=1e-9):
        bad=sums[~np.isclose(sums,1,atol=1e-9)]
        raise AssertionError(f"weight error {(sums-1).abs().max()}; examples {bad.head().to_dict()}")
    result.to_csv(OUT/"canonical_precinct_district_weights.csv",index=False)
    qa=(result.drop_duplicates(["cycle","chamber","node_id","allocation_method"])
        .groupby(["cycle","chamber","allocation_method"],as_index=False).size())
    qa.to_csv(OUT/"canonical_geography_qa.csv",index=False); print(qa.to_string(index=False))

if __name__=="__main__": main()
