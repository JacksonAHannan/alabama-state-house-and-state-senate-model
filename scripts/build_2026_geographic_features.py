"""Project official 2024 presidential precinct votes onto the 2026 SLD plan.

The allocation uses 2020 Census block population and the supplied 2025 TIGER
SLD boundaries. Legislative or presidential turnout is never used to construct
the crosswalk.
"""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import geopandas as gpd
from build_geographic_crosswalks import block_population

ROOT=Path(__file__).resolve().parents[1]
MAPS=ROOT/"data"/"raw"/"alabama_elections_and_geography"; WAR=ROOT/"data"/"processed"/"war"
PRES=ROOT/"data"/"processed"/"presidential"
BLOCKS=ROOT/"data"/"raw"/"census"/"tl_2020_01_tabblock20.zip"
PRECINCTS=MAPS/"al_2024_gen_prec"/"al_2024_gen_all_prec"/"al_2024_gen_all_prec.shp"
DISTRICTS={
    "house":(MAPS/"tl_2025_01_sldl"/"tl_2025_01_sldl.shp","SLDLST",105),
    "senate":(MAPS/"tl_2025_01_sldu"/"tl_2025_01_sldu.shp","SLDUST",35),
}

def main():
    precincts=gpd.read_file(PRECINCTS)[["UNIQUE_ID","COUNTYFP","County","Precinct","G24PREDHAR","G24PRERTRU","geometry"]]
    precincts=precincts.to_crs(5070)
    blocks=gpd.read_file(f"zip://{BLOCKS.resolve()}")[["GEOID20","COUNTYFP20","geometry"]].to_crs(5070)
    pop=block_population(2020).rename(columns={"blockid":"GEOID20"})
    blocks=blocks.merge(pop,on="GEOID20",validate="one_to_one")
    points=blocks.copy(); points.geometry=points.geometry.representative_point()
    precinct_join=gpd.sjoin(points,precincts[["UNIQUE_ID","COUNTYFP","geometry"]],how="left",predicate="within")
    precinct_join=precinct_join[precinct_join.COUNTYFP.isna() | precinct_join.COUNTYFP.eq(precinct_join.COUNTYFP20)]
    if precinct_join.UNIQUE_ID.isna().any():
        missing=precinct_join.UNIQUE_ID.isna()
        nearest_parts=[]
        for county,part in points.loc[missing].groupby("COUNTYFP20"):
            nearest_parts.append(gpd.sjoin_nearest(part[["GEOID20","geometry"]],
                precincts.loc[precincts.COUNTYFP.eq(county),["UNIQUE_ID","geometry"]],
                how="left",distance_col="snap_distance"))
        nearest=pd.concat(nearest_parts,ignore_index=True)
        nearest=nearest.sort_values("snap_distance").drop_duplicates("GEOID20").set_index("GEOID20")
        precinct_join.loc[missing,"UNIQUE_ID"]=precinct_join.loc[missing,"GEOID20"].map(nearest.UNIQUE_ID)
        precinct_join["precinct_snap_fallback"]=missing
    else:
        precinct_join["precinct_snap_fallback"]=False
    outputs=[]
    for chamber,(path,field,expected) in DISTRICTS.items():
        districts=gpd.read_file(path)[[field,"LSY","geometry"]].to_crs(5070)
        if len(districts)!=expected or set(districts.LSY.astype(str))!={"2024"}:
            raise ValueError(f"Unexpected {chamber} plan metadata")
        assignment=gpd.sjoin(points[["GEOID20","population","geometry"]],districts[[field,"geometry"]],how="left",predicate="within")
        if assignment[field].isna().any():
            missing=assignment[field].isna()
            nearest=gpd.sjoin_nearest(points.loc[missing,["GEOID20","geometry"]],
                                      districts[[field,"geometry"]],how="left",distance_col="snap_distance")
            nearest=nearest.sort_values("snap_distance").drop_duplicates("GEOID20").set_index("GEOID20")
            assignment.loc[missing,field]=assignment.loc[missing,"GEOID20"].map(nearest[field])
        joined=precinct_join[["GEOID20","UNIQUE_ID","population"]].merge(
            assignment[["GEOID20",field]],on="GEOID20",validate="one_to_one")
        joined["district"]=pd.to_numeric(joined[field]).astype(int); joined["block_count"]=1
        weights=(joined.groupby(["UNIQUE_ID","district"],as_index=False)
                 .agg(population=("population","sum"),block_count=("block_count","sum")))
        weights["precinct_population"]=weights.groupby("UNIQUE_ID").population.transform("sum")
        weights["precinct_blocks"]=weights.groupby("UNIQUE_ID").block_count.transform("sum")
        weights["allocation_weight"]=np.where(weights.precinct_population.gt(0),
            weights.population/weights.precinct_population,weights.block_count/weights.precinct_blocks)
        weights["cycle"]=2026; weights["chamber"]=chamber
        outputs.append(weights)
    weights=pd.concat(outputs,ignore_index=True).merge(
        precincts.drop(columns="geometry")[["UNIQUE_ID","County","Precinct"]],on="UNIQUE_ID",validate="many_to_one")
    weights=weights.rename(columns={"County":"county_key","Precinct":"precinct_key"})
    weights["allocation_method"]="2020_block_population_to_2025_tiger_sld"
    if not np.allclose(weights.groupby(["chamber","UNIQUE_ID"]).allocation_weight.sum(),1):
        raise ValueError("2026 precinct allocation weights do not sum to one")
    weights.to_csv(WAR/"2026_geographic_precinct_district_weights.csv",index=False)

    vote_cols={"G24PREDHAR":"dem_votes","G24PRERTRU":"rep_votes"}
    votes=pd.DataFrame(precincts.drop(columns="geometry")).rename(columns=vote_cols)
    allocated=weights.merge(votes[["UNIQUE_ID","dem_votes","rep_votes"]],on="UNIQUE_ID",validate="many_to_one")
    for party in ("dem","rep"):
        allocated[f"{party}_allocated"]=allocated[f"{party}_votes"]*allocated.allocation_weight
    district=(allocated.groupby(["chamber","district"],as_index=False)
              .agg(pres_2024_dem_votes=("dem_allocated","sum"),pres_2024_rep_votes=("rep_allocated","sum")))
    district["pres_2024_two_party_votes"]=district.pres_2024_dem_votes+district.pres_2024_rep_votes
    district["pres_2024_dem_margin"]=100*(district.pres_2024_dem_votes-district.pres_2024_rep_votes)/district.pres_2024_two_party_votes
    district["pres_2024_fallback_share"]=0.0; district["pres_2024_source_complete"]=True; district["cycle"]=2026
    district.to_csv(PRES/"2026_district_presidential_features.csv",index=False)
    qa=pd.DataFrame([{"chamber":c,"districts":len(g),"min_weight":weights[weights.chamber.eq(c)].allocation_weight.min(),
                      "max_weight_sum_error":float((weights[weights.chamber.eq(c)].groupby("UNIQUE_ID").allocation_weight.sum()-1).abs().max())}
                     for c,g in district.groupby("chamber")])
    qa.to_csv(WAR/"2026_geographic_crosswalk_qa.csv",index=False)
    manifest=[]
    for chamber,(path,field,expected) in DISTRICTS.items():
        for component in sorted(path.parent.glob(path.stem+".*")):
            manifest.append({"chamber":chamber,"source_file":str(component.relative_to(ROOT)),
                             "bytes":component.stat().st_size,
                             "sha256":hashlib.sha256(component.read_bytes()).hexdigest(),
                             "applicable_cycle":2026,"legislative_session_year":2024,
                             "selection_basis":"user_supplied_reinstated_original_2021_plan"})
    pd.DataFrame(manifest).to_csv(WAR/"2026_geography_source_manifest.csv",index=False)
    print(qa.to_string(index=False))
    print(district.groupby("chamber").agg(districts=("district","size"),dem_votes=("pres_2024_dem_votes","sum"),rep_votes=("pres_2024_rep_votes","sum")).to_string())

if __name__=="__main__": main()
