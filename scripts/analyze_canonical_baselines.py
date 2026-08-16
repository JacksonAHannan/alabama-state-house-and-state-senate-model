"""Audit, stress-test, and compare canonical district partisan baselines."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from build_geographic_crosswalks import block_assignments
from oe_normalize import normalize_name

ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"
OUT=ROOT/"data"/"processed"/"elections"; CYCLES=(2010,2014,2018,2022)
EXECUTIVE={"Governor","Lieutenant Governor","Attorney General","Secretary of State","State Auditor","State Treasurer","Commissioner of Agriculture and Industries"}
CORE={"Governor","Attorney General"}
PARTY_2010={"RON SPARKS":"D","ROBERT BENTLEY":"R","JAMES H ANDERSON":"D","LUTHER STRANGE":"R"}

def clean_vtd(value):
    if pd.isna(value): return None
    text=str(value).strip(); text=text[:-2] if text.endswith('.0') else text
    return text.zfill(6)

def source_votes(connection):
    votes=pd.read_sql("""select year,source,county_key,precinct_key,office,candidate_key,party_norm,votes
      from vote_observations where office in ('Governor','Lieutenant Governor','Attorney General','Secretary of State','State Auditor','State Treasurer','Commissioner of Agriculture and Industries')""",connection)
    votes.loc[votes.year.eq(2010),"party_norm"]=votes.loc[votes.year.eq(2010),"candidate_key"].map(PARTY_2010).fillna("O")
    return votes[votes.party_norm.isin(["D","R"])]

def reconciliation(votes):
    county=(votes.groupby(["year","source","county_key","office","party_norm"],as_index=False).votes.sum()
            .pivot(index=["year","county_key","office","party_norm"],columns="source",values="votes").reset_index())
    for source in ("alabama_sos","openelections"):
        if source not in county: county[source]=np.nan
    county["difference_sos_minus_oe"]=county.alabama_sos-county.openelections
    county["absolute_difference"]=county.difference_sos_minus_oe.abs()
    county["comparison_status"]=np.select(
        [county.alabama_sos.isna(),county.openelections.isna(),county.absolute_difference.le(.5)],
        ["sos_missing","secondary_missing","exact"],default="different")
    county["authoritative_vote_source"]="alabama_sos_official_precinct"
    county["certified_canvass_status"]="separate_canvass_comparison_pending"
    return county

def statewide_reconciliation(votes):
    statewide=(votes.groupby(["year","source","office","party_norm"],as_index=False).votes.sum()
               .pivot(index=["year","office","party_norm"],columns="source",values="votes").reset_index())
    for source in ("alabama_sos","openelections"):
        if source not in statewide: statewide[source]=np.nan
    statewide["difference_sos_minus_oe"]=statewide.alabama_sos-statewide.openelections
    statewide["absolute_difference"]=statewide.difference_sos_minus_oe.abs()
    statewide["comparison_status"]=np.select(
        [statewide.alabama_sos.isna(),statewide.openelections.isna(),statewide.absolute_difference.le(.5)],
        ["sos_missing","secondary_missing","exact"],default="different")
    statewide["authoritative_vote_source"]="alabama_sos_official_precinct"
    statewide["certified_canvass_status"]="separate_canvass_comparison_pending"
    return statewide

def county_map():
    frame=gpd.read_file(ROOT/"data"/"raw"/"alabama_elections_and_geography"/"al_gen_22_prec"/"al_gen_22_st_prec.shp",ignore_geometry=True)
    frame=frame[["County","COUNTYFP"]].drop_duplicates(); frame["county_norm"]=frame.County.map(normalize_name)
    return dict(zip(frame.county_norm,frame.COUNTYFP.astype(str).str.zfill(3)))

def link_variants(connection,nodes):
    canonical=pd.read_sql("select * from canonical_precinct_geography_links",connection)
    evidence=pd.read_sql("select * from canonical_geography_evidence",connection)
    canonical.vtd=canonical.vtd.map(clean_vtd); evidence.vtd=evidence.vtd.map(clean_vtd)
    # Re-evaluate agreement after normalization so values such as 123 and 000123
    # do not create spurious conflicts.
    evidence=evidence[evidence.vtd.notna()].copy()
    counts=evidence.groupby("source_node_id").vtd.nunique()
    conflicts=set(counts[counts.gt(1)].index)
    base=dict(zip(canonical.source_node_id,canonical.vtd))
    unambiguous=evidence[evidence.source_node_id.isin(counts[counts.eq(1)].index)].drop_duplicates("source_node_id")
    base.update(dict(zip(unambiguous.source_node_id,unambiguous.vtd)))
    variants={"strict_consensus":base.copy(),"conflict_county_fallback":base.copy()}
    for node in conflicts: variants["conflict_county_fallback"].pop(node,None)
    for preference,name in [("direct_geography","prefer_direct"),("source_transfer","prefer_source_transfer")]:
        mapping=base.copy()
        preferred=evidence[evidence.evidence.eq(preference)].drop_duplicates("source_node_id")
        mapping.update(dict(zip(preferred.source_node_id,preferred.vtd)))
        variants[name]=mapping
    return variants,conflicts,evidence

def build_weights(nodes,links,cycle,chamber,cmap):
    current=nodes[nodes.year.eq(cycle)].copy(); current["vtd"]=current.node_id.map(links)
    current["county_norm"]=current.county_key.map(normalize_name).replace({"STCLAIR":"SAINT CLAIR"})
    current["county_fips"]=current.county_norm.map(cmap)
    blocks=block_assignments(cycle,chamber); blocks.vtd=blocks.vtd.map(clean_vtd)
    direct=current[current.vtd.notna()].merge(blocks[["county_fips","vtd","district","allocation_weight"]],on=["county_fips","vtd"],how="inner")
    direct["allocation_method"]="vtd_population"; used=set(direct.node_id)
    fallback=current[~current.node_id.isin(used)]
    county=blocks.groupby(["county_fips","district"],as_index=False).population.sum(); county["allocation_weight"]=county.population/county.groupby("county_fips").population.transform("sum")
    fallback=fallback.merge(county[["county_fips","district","allocation_weight"]],on="county_fips",how="left"); fallback["allocation_method"]="county_population_fallback"
    return pd.concat([direct,fallback],ignore_index=True)[["node_id","district","allocation_weight","allocation_method"]]

def baselines_for_variant(votes,nodes,links,name,cmap):
    official=votes[votes.source.eq("alabama_sos")].merge(nodes[["node_id","year","county_key","precinct_key"]],on=["year","county_key","precinct_key"],validate="many_to_one")
    rows=[]
    for cycle in CYCLES:
        for chamber in ("house","senate"):
            weights=build_weights(nodes,links,cycle,chamber,cmap)
            allocated=official[official.year.eq(cycle)].merge(weights,on="node_id"); allocated["allocated_votes"]=allocated.votes*allocated.allocation_weight
            part=(allocated.groupby(["office","district","party_norm"],as_index=False).allocated_votes.sum()
                  .pivot(index=["office","district"],columns="party_norm",values="allocated_votes").fillna(0).reset_index())
            for p in ("D","R"):
                if p not in part: part[p]=0
            part["two_party_votes"]=part.D+part.R
            contested=part.D.gt(0)&part.R.gt(0)
            part["office_margin"]=np.where(contested,100*(part.D-part.R)/part.two_party_votes.where(part.two_party_votes.gt(0)),np.nan)
            part.loc[~contested,["D","R"]]=np.nan
            part["cycle"]=cycle; part["chamber"]=chamber; part["scenario"]=name; rows.append(part)
    return pd.concat(rows,ignore_index=True)

def baselines_for_saved_weights(votes,nodes,weights,name="production_canonical_weights"):
    """Evaluate the exact allocation weights consumed by the production CMO."""
    official=(votes[votes.source.eq("alabama_sos")]
              .merge(nodes[["node_id","year","county_key","precinct_key"]],
                     on=["year","county_key","precinct_key"],validate="many_to_one"))
    rows=[]
    for cycle in CYCLES:
        for chamber in ("house","senate"):
            current=weights[(weights.cycle.eq(cycle))&(weights.chamber.eq(chamber))]
            allocated=official[official.year.eq(cycle)].merge(
                current[["node_id","district","allocation_weight"]],on="node_id")
            allocated["allocated_votes"]=allocated.votes*allocated.allocation_weight
            part=(allocated.groupby(["office","district","party_norm"],as_index=False).allocated_votes.sum()
                  .pivot(index=["office","district"],columns="party_norm",values="allocated_votes")
                  .fillna(0).reset_index())
            for party in ("D","R"):
                if party not in part: part[party]=0
            part["two_party_votes"]=part.D+part.R
            contested=part.D.gt(0)&part.R.gt(0)
            part["office_margin"]=np.where(
                contested,100*(part.D-part.R)/part.two_party_votes.where(part.two_party_votes.gt(0)),np.nan)
            part.loc[~contested,["D","R"]]=np.nan
            part["cycle"]=cycle; part["chamber"]=chamber; part["scenario"]=name
            rows.append(part)
    return pd.concat(rows,ignore_index=True)

def definitions(office):
    keys=["scenario","cycle","chamber","district"]
    outputs=[]
    def add(frame,name,method):
        value=method(frame); value["baseline_definition"]=name; outputs.append(value)
    for name,selected in [("governor_only",{"Governor"}),("attorney_general_only",{"Attorney General"}),
                          ("core_equal",CORE),("expanded_equal",EXECUTIVE)]:
        frame=office[office.office.isin(selected)]
        add(frame,name,lambda x:x.groupby(keys,as_index=False).office_margin.mean().rename(columns={"office_margin":"baseline_margin"}))
    for name,selected in [("core_turnout_weighted",CORE),("expanded_turnout_weighted",EXECUTIVE)]:
        frame=office[office.office.isin(selected)].groupby(keys,as_index=False)[["D","R"]].sum()
        frame["baseline_margin"]=100*(frame.D-frame.R)/(frame.D+frame.R).where((frame.D+frame.R).gt(0)); frame["baseline_definition"]=name
        outputs.append(frame[keys+["baseline_definition","baseline_margin"]])
    result=pd.concat(outputs,ignore_index=True)
    # A latent office factor is available where at least three offices exist.
    latent=[]
    for group_key,group in office.groupby(["scenario","cycle","chamber"]):
        matrix=group.pivot(index="district",columns="office",values="office_margin").dropna(axis=1)
        if matrix.shape[1]<3: continue
        z=StandardScaler().fit_transform(matrix); score=PCA(1).fit_transform(z).ravel()
        core=result[(result.scenario.eq(group_key[0]))&(result.cycle.eq(group_key[1]))&(result.chamber.eq(group_key[2]))&(result.baseline_definition.eq("core_equal"))].set_index("district").baseline_margin
        common=core.reindex(matrix.index); score=score*(1 if np.corrcoef(score,common)[0,1]>=0 else -1)
        scaled=(score-score.mean())/(score.std() or 1)*(common.std() or 1)+common.mean()
        latent.extend([{"scenario":group_key[0],"cycle":group_key[1],"chamber":group_key[2],"district":d,"baseline_definition":"latent_office_factor","baseline_margin":v} for d,v in zip(matrix.index,scaled)])
    if latent: result=pd.concat([result,pd.DataFrame(latent)],ignore_index=True)
    return result

def main():
    with sqlite3.connect(DB) as connection:
        votes=source_votes(connection); nodes=pd.read_sql("select * from precinct_nodes where source='alabama_sos'",connection)
        variants,conflicts,evidence=link_variants(connection,nodes)
    recon=reconciliation(votes); recon.to_csv(OUT/"baseline_source_reconciliation.csv",index=False)
    statewide_reconciliation(votes).to_csv(OUT/"baseline_statewide_source_reconciliation.csv",index=False)
    cmap=county_map()
    scenario_frames=[baselines_for_variant(votes,nodes,mapping,name,cmap) for name,mapping in variants.items()]
    saved_weights=pd.read_csv(OUT/"canonical_precinct_district_weights.csv")
    scenario_frames.append(baselines_for_saved_weights(votes,nodes,saved_weights))
    office=pd.concat(scenario_frames,ignore_index=True)
    office.to_csv(OUT/"canonical_district_baseline_office_scenarios.csv",index=False)
    defined=definitions(office); defined.to_csv(OUT/"canonical_district_baseline_definitions.csv",index=False)
    core=defined[defined.baseline_definition.eq("core_equal")]
    uncertainty=(core.groupby(["cycle","chamber","district"]).baseline_margin.agg(["min","max","mean","std"]).reset_index())
    uncertainty.columns=["cycle","chamber","district","baseline_low","baseline_high","baseline_mean","baseline_scenario_sd"]
    uncertainty["baseline_range"]=uncertainty.baseline_high-uncertainty.baseline_low
    uncertainty.to_csv(OUT/"canonical_baseline_uncertainty.csv",index=False)
    node_votes=(votes[(votes.source.eq("alabama_sos"))&votes.office.isin(CORE)].merge(nodes[["node_id","year","county_key","precinct_key"]],on=["year","county_key","precinct_key"])
                .groupby("node_id",as_index=False).votes.sum().rename(columns={"votes":"core_votes"}))
    impact=evidence[evidence.source_node_id.isin(conflicts)].merge(node_votes,left_on="source_node_id",right_on="node_id",how="left")
    impact=(impact.groupby("source_node_id",as_index=False).agg(alternative_vtds=("vtd","nunique"),core_votes=("core_votes","max"),evidence_paths=("evidence","nunique")))
    impact["priority_proxy"]=impact.core_votes.fillna(0)*impact.alternative_vtds
    impact=impact.merge(nodes[["node_id","year","county_key","precinct_key"]],left_on="source_node_id",right_on="node_id").sort_values("priority_proxy",ascending=False)
    impact.to_csv(OUT/"precinct_geography_conflict_impact.csv",index=False)
    reference=defined[defined.baseline_definition.eq("core_equal")][["scenario","cycle","chamber","district","baseline_margin"]].rename(columns={"baseline_margin":"core_margin"})
    comparison=defined.merge(reference,on=["scenario","cycle","chamber","district"]); comparison["difference_from_core"]=comparison.baseline_margin-comparison.core_margin
    diagnostics=(comparison.groupby(["scenario","cycle","chamber","baseline_definition"],as_index=False)
                 .agg(mean_abs_difference=("difference_from_core",lambda x:x.abs().mean()),max_abs_difference=("difference_from_core",lambda x:x.abs().max()),correlation=("baseline_margin",lambda x:x.corr(comparison.loc[x.index,"core_margin"]))))
    diagnostics.to_csv(OUT/"baseline_definition_diagnostics.csv",index=False)
    print(recon.groupby(["year","comparison_status"]).size().to_string())
    print("\nBaseline uncertainty:\n",uncertainty.groupby("cycle").baseline_range.describe()[["mean","50%","max"]].to_string())
    print(f"\nGeography conflicts prioritized: {len(impact)}")

if __name__=="__main__":main()
