"""Build district-allocation weights for canonical SOS precinct identities."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from build_geographic_crosswalks import block_assignments
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
    links["vtd"]=links.vtd.map(clean_vtd)
    target=nodes.merge(links,left_on="node_id",right_on="source_node_id",how="left")
    county=gpd.read_file(ROOT/"data"/"raw"/"alabama_elections_and_geography"/"al_gen_22_prec"/"al_gen_22_st_prec.shp",ignore_geometry=True)
    county_map=county[["County","COUNTYFP"]].drop_duplicates(); county_map["county_norm"]=county_map.County.map(normalize_name)
    target["county_norm"]=target.county_key.map(normalize_name)
    target["county_norm"]=target.county_norm.replace({"STCLAIR":"SAINT CLAIR"})
    target=target.merge(county_map[["county_norm","COUNTYFP"]],on="county_norm",how="left").rename(columns={"COUNTYFP":"county_fips"})
    outputs=[]
    for cycle in (2010,2014,2018,2022):
        for chamber in ("house","senate"):
            blocks=block_assignments(cycle,chamber); blocks["vtd"]=blocks.vtd.map(clean_vtd)
            current=target[target.year.eq(cycle)].copy()
            direct=current[current.vtd.notna()].merge(blocks[["county_fips","vtd","district","allocation_weight"]],on=["county_fips","vtd"],how="inner")
            direct["allocation_method"]="canonical_vtd_population"
            used=set(direct.node_id); fallback=current[~current.node_id.isin(used)].copy()
            county_weights=blocks.groupby(["county_fips","district"],as_index=False).population.sum()
            county_weights["allocation_weight"]=county_weights.population/county_weights.groupby("county_fips").population.transform("sum")
            fallback=fallback.merge(county_weights[["county_fips","district","allocation_weight"]],on="county_fips",how="left")
            fallback["allocation_method"]=np.where(fallback.county_level_ballot.eq(1),"county_level_ballot","county_population_fallback")
            combined=pd.concat([direct,fallback],ignore_index=True); combined["cycle"]=cycle; combined["chamber"]=chamber
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
