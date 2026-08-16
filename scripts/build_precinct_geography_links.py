"""Link official election precincts to VEST/RDH VTD geography."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rapidfuzz import process
from rapidfuzz.fuzz import WRatio

from build_precinct_identity import precinct_code, vote_similarity
from build_geographic_crosswalks import precinct_norm
from oe_normalize import is_county_level_ballot, normalize_name

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"
DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"

OFFICES = {"PRE":"President", "GOV":"Governor", "LTG":"Lieutenant Governor",
           "ATG":"Attorney General", "SOS":"Secretary of State", "AUD":"State Auditor",
           "TRE":"State Treasurer", "AGR":"Commissioner of Agriculture and Industries"}


def _fingerprints(frame: pd.DataFrame, node_col: str, vote_columns: list[str]) -> pd.DataFrame:
    parts = []
    for code, office in OFFICES.items():
        cols = [c for c in vote_columns if len(c) >= 6 and c[3:6] == code and "OWRI" not in c]
        if cols:
            parts.append(pd.DataFrame({"geo_node_id": frame[node_col], "office": office,
                                      "votes": frame[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["geo_node_id","office","votes"])


def load_geography() -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes, fingerprints = [], []
    county_ref = gpd.read_file(MAPS / "al_gen_22_prec" / "al_gen_22_st_prec.shp", ignore_geometry=True)
    fips_name = county_ref[["COUNTYFP","County"]].drop_duplicates().set_index("COUNTYFP").County.to_dict()
    next_id = 1
    # 2014 uses 2010 Census VTD identifiers paired with the official 2012 SLD
    # block-equivalency plan. Do not substitute VEST-2016 identifiers here.
    frame = gpd.read_file(f"zip://{(MAPS/'tl_2012_01_vtd10.zip').resolve()}", ignore_geometry=True)
    for census_cycle in (2010,2014):
        part = pd.DataFrame({"geo_node_id":np.arange(next_id,next_id+len(frame)), "cycle":census_cycle,
                             "geography_source":"census_vtd10", "county_fips":frame.COUNTYFP10.astype(str).str.zfill(3),
                             "vtd":frame.VTDST10.astype(str).str.zfill(6), "geography_name":frame.NAME10})
        part["county_key"]=part.county_fips.map(fips_name).str.upper().str.strip()
        part["name_norm"]=part.geography_name.map(precinct_norm); part["precinct_code"]=part.geography_name.map(precinct_code)
        nodes.append(part); next_id += len(frame)
    for cycle, year in [(2018,18)]:
        frame = gpd.read_file(f"zip://{(MAPS/f'al_vest_{year}.zip').resolve()}", ignore_geometry=True)
        part = pd.DataFrame({"geo_node_id": np.arange(next_id,next_id+len(frame)), "cycle":cycle,
                             "geography_source":f"vest_{year}", "county_fips":frame.COUNTYFP20.astype(str).str.zfill(3),
                             "vtd":frame[f"VTDST{year}"].astype(str).str.zfill(6), "geography_name":frame[f"NAME{year}"]})
        part["county_key"] = part.county_fips.map(fips_name).str.upper().str.strip()
        part["name_norm"] = part.geography_name.map(precinct_norm); part["precinct_code"] = part.geography_name.map(precinct_code)
        nodes.append(part); fingerprints.append(_fingerprints(frame.assign(_node=part.geo_node_id),"_node",list(frame.columns)))
        next_id += len(frame)
    frame = county_ref
    part = pd.DataFrame({"geo_node_id":np.arange(next_id,next_id+len(frame)), "cycle":2022,
                         "geography_source":"rdh_2022", "county_fips":frame.COUNTYFP.astype(str).str.zfill(3),
                         "geography_record_id":frame.UNIQUE_ID.astype(str), "geography_name":frame.Precinct})
    part["county_key"] = frame.County.str.upper().str.strip()
    part["name_norm"] = part.geography_name.map(precinct_norm); part["precinct_code"] = part.geography_name.map(precinct_code)
    prior = pd.read_csv(ROOT/"data"/"processed"/"war"/"geographic_precinct_vtd_matches.csv",dtype={"vtd":str})
    prior = prior[prior.cycle.eq(2022) & prior.vtd.notna()].drop_duplicates(["county_key","precinct_key"])
    vtd_map = prior.set_index(["county_key","precinct_key"]).vtd.to_dict()
    part["vtd"] = [vtd_map.get((county, name)) for county, name in zip(part.county_key, part.geography_name)]
    nodes.append(part); fingerprints.append(_fingerprints(frame.assign(_node=part.geo_node_id),"_node",list(frame.columns)))
    return pd.concat(nodes,ignore_index=True), pd.concat(fingerprints,ignore_index=True)


def match(nodes: pd.DataFrame, source_fp: pd.DataFrame, geo: pd.DataFrame, geo_fp: pd.DataFrame):
    source_groups={n:dict(zip(g.office,g.votes)) for n,g in source_fp.groupby("node_id")}
    geo_groups={n:dict(zip(g.office,g.votes)) for n,g in geo_fp.groupby("geo_node_id")}
    pools={(cy,co):g for (cy,co),g in geo.groupby(["cycle","county_key"])}
    candidates=[]
    for row in nodes[nodes.source.eq("alabama_sos") & nodes.year.isin([2010,2014,2018,2022]) & nodes.county_level_ballot.eq(0)].itertuples():
        pool=pools.get((row.year,row.county_key))
        if pool is None: continue
        choices=pool.set_index("geo_node_id").name_norm.to_dict()
        ids={x[2] for x in process.extract(row.name_norm,choices,scorer=WRatio,limit=5)}
        if row.precinct_code:
            ids |= set(pool.loc[pool.precinct_code.eq(row.precinct_code),"geo_node_id"])
        for gid in ids:
            target=pool.loc[pool.geo_node_id.eq(gid)].iloc[0]
            name=float(WRatio(row.name_norm,target.name_norm)); code=int(bool(row.precinct_code and row.precinct_code==target.precinct_code))
            vote,shared=vote_similarity(source_groups.get(row.node_id,{}),geo_groups.get(gid,{})) if row.year in {2018,2022} else (0.0,0)
            if shared:
                vw=min(shared/3,1)*.4; cw=.25 if row.precinct_code and target.precinct_code else 0; score=(1-vw-cw)*name+vw*vote+cw*100*code
            else:
                cw=.35 if row.precinct_code and target.precinct_code else 0; score=(1-cw)*name+cw*100*code
            candidates.append({"source_node_id":row.node_id,"geo_node_id":gid,"name_score":name,"code_exact":code,
                               "vote_score":vote,"shared_offices":shared,"composite_score":score})
    out=pd.DataFrame(candidates).sort_values(["source_node_id","composite_score"],ascending=[True,False])
    out["candidate_rank"]=out.groupby("source_node_id").cumcount()+1
    second=out.groupby("source_node_id").composite_score.transform(lambda x:x.iloc[1] if len(x)>1 else 0)
    out["score_margin"]=out.composite_score-second
    best=out[out.candidate_rank.eq(1)].copy()
    best["match_method"]=np.select(
        [best.name_score.eq(100)&((best.shared_offices.eq(0))|(best.vote_score.ge(90))),
         best.code_exact.eq(1)&best.name_score.ge(75),
         best.composite_score.ge(90)&best.score_margin.ge(5)&best.shared_offices.ge(2)],
        ["exact_name","code_name","composite_vote"],default="review")
    best["accepted"]=best.match_method.ne("review").astype(int)
    return out,best


def main():
    with sqlite3.connect(DB) as connection:
        nodes=pd.read_sql("select * from precinct_nodes",connection); fp=pd.read_sql("select * from precinct_vote_fingerprints",connection)
        geo,geo_fp=load_geography(); candidates,links=match(nodes,fp,geo,geo_fp)
        geo.to_sql("geographic_precinct_nodes",connection,index=False,if_exists="replace")
        geo_fp.to_sql("geographic_vote_fingerprints",connection,index=False,if_exists="replace")
        candidates.to_sql("precinct_geography_match_candidates",connection,index=False,if_exists="replace")
        links.to_sql("precinct_geography_links",connection,index=False,if_exists="replace")
        source_links=pd.read_sql("select * from precinct_source_links where accepted=1",connection)
        old=pd.read_sql("select * from precinct_vtd_link_evidence",connection)
        oe_nodes=nodes[nodes.source.eq("openelections")][["node_id","year","county_key","precinct_key"]]
        transferred=(source_links.merge(oe_nodes,left_on="right_node_id",right_on="node_id")
                     .merge(old,left_on=["year","county_key","precinct_key"],
                            right_on=["cycle","county_key","precinct_key"]))
        transferred=transferred[transferred.match_method_y.isin(["exact","fuzzy"]) & transferred.vtd.notna()]
        transferred=pd.DataFrame({"source_node_id":transferred.left_node_id,"vtd":transferred.vtd,
                                  "evidence":"source_transfer"})
        direct=(links[links.accepted.eq(1)].merge(geo[["geo_node_id","vtd"]],on="geo_node_id")
                [["source_node_id","vtd"]].assign(evidence="direct_geography"))
        evidence=pd.concat([direct,transferred],ignore_index=True).drop_duplicates()
        counts=evidence.groupby("source_node_id").vtd.nunique()
        canonical=evidence[evidence.source_node_id.map(counts).eq(1)].copy()
        canonical=(canonical.groupby(["source_node_id","vtd"],as_index=False)
                   .agg(evidence=("evidence",lambda x:"consensus" if x.nunique()>1 else x.iloc[0])))
        conflicts=evidence[evidence.source_node_id.map(counts).gt(1)].copy()
        evidence.to_sql("canonical_geography_evidence",connection,index=False,if_exists="replace")
        canonical.to_sql("canonical_precinct_geography_links",connection,index=False,if_exists="replace")
        conflicts.to_sql("precinct_geography_conflicts",connection,index=False,if_exists="replace")
    review=links.merge(nodes[["node_id","year","county_key","precinct_key"]],left_on="source_node_id",right_on="node_id")
    review=review.merge(geo[["geo_node_id","vtd","geography_name","geography_source"]],on="geo_node_id")
    review.to_csv(ROOT/"data"/"processed"/"elections"/"precinct_geography_review.csv",index=False)
    print(review.groupby(["year","match_method","accepted"]).size().to_string())
    print(f"Canonical geography links: {len(canonical):,}; conflicting evidence: "
          f"{conflicts.source_node_id.nunique():,} precincts")

if __name__=="__main__": main()
