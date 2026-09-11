#!/usr/bin/env python3
"""Prepare exact-vintage 2012 precinct votes and allocate them to 2018-2020 plans."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zipfile
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import from_wkb

from build_southern_2016_vest_plan_allocation import (
    BLOCK_MANIFEST, geometry_fallback, load_vap, resolve_point_matches,
)
from build_southern_historical_plan_allocations import (
    assign_blocks_to_plan, detailed_plan_geometry, insert_district_rows, plan_geometry,
)
from load_southern_context_warehouse import register_source, stable_id
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_southern_2012_plan_allocation_schema.sql")
GEOMETRY_MANIFEST = ROOT / "data/processed/source_audits/southern_2012_precinct_geography_manifest.csv"
DETAILED_MANIFEST = ROOT / "data/processed/source_audits/southern_2020_detailed_plan_supplement_manifest.csv"
VA_RESULTS = ROOT / "data/raw/southern_sos_elections/VA/2012/2012_president_contest_44930.csv"
OUT = ROOT / "data/processed/presidential/southern_2012_plan_allocations"


def norm(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value).replace("&", " AND ")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", value).strip()


def zip_member(path: Path, state: str) -> str:
    with zipfile.ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".shp") and not n.startswith("__MACOSX")]
    if state == "VA":
        members = [n for n in members if n.endswith("/va_precincts_2012_nov_general.shp")]
    if len(members) != 1:
        raise ValueError(f"Expected one 2012 precinct shapefile for {state}, found {members}")
    return members[0]


def read_geometry(row: dict) -> tuple[gpd.GeoDataFrame, str]:
    path = (ROOT / row["local_path"]).resolve()
    member = zip_member(path, row["state_code"])
    frame = gpd.read_file(f"zip://{path.as_posix()}!{member}")
    if frame.crs is None or frame.geometry.isna().any() or frame.geometry.is_empty.any():
        raise ValueError(f"Invalid 2012 precinct geometry for {row['state_code']}")
    # The Virginia archive has four otherwise-valid polygons with a missing Z
    # ordinate. All downstream overlays are planar, so normalize every source
    # to 2-D before topology repair rather than allowing GEOS to see NaN Zs.
    frame.geometry = frame.geometry.force_2d().make_valid()
    if (~frame.geometry.is_valid).any() or frame.geometry.is_empty.any():
        raise ValueError(f"Unrepairable 2012 precinct geometry for {row['state_code']}")
    return frame.to_crs(4326), member


def result_rows(connection, state: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """SELECT result_observation_id,source_file_id,county_name_original,
                  precinct_name_original,dem_votes,rep_votes,other_votes,total_votes
           FROM fact_southern_presidential_geography_result
           WHERE state_code=? AND cycle=2012 ORDER BY county_key,precinct_key""",
        connection, params=(state,),
    )
    if frame.empty:
        raise ValueError(f"No validated 2012 presidential rows for {state}")
    return frame


def dissolve(frame: gpd.GeoDataFrame, key: str, fields: list[str]) -> gpd.GeoDataFrame:
    if frame[key].isna().any():
        raise ValueError(f"Null precinct key {key}")
    attributes = frame.groupby(key, as_index=False)[fields].first()
    geometry = frame[[key, "geometry"]].dissolve(by=key, as_index=False)
    return gpd.GeoDataFrame(attributes.merge(geometry, on=key, validate="one_to_one"), geometry="geometry", crs=frame.crs)


def allocate_pool(prepared: pd.DataFrame, indexes: list[int], pool: dict) -> None:
    if not indexes:
        raise ValueError(f"No eligible precinct geometry for redistribution: {pool}")
    redistributed = pd.Series(0.0, index=indexes)
    for column in ("dem_votes", "rep_votes", "other_votes"):
        amount = float(pool[column])
        base = prepared.loc[indexes, column].clip(lower=0)
        shares = base / base.sum() if base.sum() > 0 else pd.Series(1 / len(indexes), index=indexes)
        allocated = shares * amount
        prepared.loc[indexes, column] += allocated
        if column in {"dem_votes", "rep_votes"}:
            redistributed += allocated
    prepared.loc[indexes, "redistributed_two_party_votes"] += redistributed


def finalize(frame: gpd.GeoDataFrame, state: str, result_source: str, geometry_source: str,
             source_rows: int, source_two_party: float, mode_votes: float,
             unmatched_votes: float) -> tuple[gpd.GeoDataFrame, dict]:
    frame["total_votes"] = frame.dem_votes + frame.rep_votes + frame.other_votes
    frame["prepared_precinct_id"] = [stable_id("PRES2012GEO", geometry_source, key) for key in frame.precinct_key]
    frame["result_observation_id"] = frame.prepared_precinct_id
    frame["result_source_file_id"] = result_source
    prepared_two_party = float((frame.dem_votes + frame.rep_votes).sum())
    if abs(prepared_two_party - source_two_party) > 0.011:
        raise ValueError(f"{state} prepared vote reconciliation failed: {prepared_two_party} != {source_two_party}")
    return frame, {
        "state_code": state, "result_source_file_id": result_source,
        "geometry_source_file_id": geometry_source, "source_result_rows": source_rows,
        "prepared_precincts": len(frame), "source_two_party_votes": source_two_party,
        "direct_two_party_votes": source_two_party - mode_votes - unmatched_votes,
        "redistributed_mode_two_party_votes": mode_votes,
        "redistributed_unmatched_two_party_votes": unmatched_votes,
    }


def prepare_fl(frame: gpd.GeoDataFrame, geometry_source: str) -> tuple[gpd.GeoDataFrame, dict]:
    vote_cols = [c for c in frame.columns if c.startswith("G12PRE")]
    for key, group in frame.groupby("PCT_STD"):
        for col in vote_cols:
            positive = group.loc[group[col].gt(0), col].unique()
            if len(positive) > 1:
                raise ValueError(f"Conflicting repeated Florida votes for {key}/{col}")
    fields = ["COUNTY", "PRECINCT"] + vote_cols
    first = frame.groupby("PCT_STD", as_index=False)[fields].first()
    for col in vote_cols:
        first[col] = frame.groupby("PCT_STD")[col].max().values
    geom = frame[["PCT_STD", "geometry"]].dissolve(by="PCT_STD", as_index=False)
    out = gpd.GeoDataFrame(first.merge(geom, on="PCT_STD"), geometry="geometry", crs=frame.crs)
    out["county_key"] = out.COUNTY.map(norm)
    out["precinct_key"] = out.PCT_STD.map(norm)
    out["dem_votes"] = out.G12PREDOBA.astype(float)
    out["rep_votes"] = out.G12PRERROM.astype(float)
    out["other_votes"] = out[[c for c in vote_cols if c not in {"G12PREDOBA", "G12PRERROM"}]].sum(axis=1).astype(float)
    out["direct_two_party_votes"] = out.dem_votes + out.rep_votes
    out["redistributed_two_party_votes"] = 0.0
    out["source_result_ids_json"] = out.PCT_STD.map(lambda x: json.dumps([f"VEST-2012-FL:{x}"]))
    out["preparation_method"] = "vest_2012_native_precinct_result_geometry"
    total = float((out.dem_votes + out.rep_votes).sum())
    return finalize(out, "FL", geometry_source, geometry_source, len(out), total, 0.0, 0.0)


def prepare_ga(connection, frame: gpd.GeoDataFrame, geometry_source: str) -> tuple[gpd.GeoDataFrame, dict]:
    out = dissolve(frame.assign(CTYSOSID=frame.CTYSOSID.map(str)), "CTYSOSID", ["COUNTY_NAM", "PRECINCT_I", "PRECINCT_N"])
    out["county_key"] = out.COUNTY_NAM.map(norm); out["precinct_key"] = out.CTYSOSID.map(norm)
    for col in ["dem_votes", "rep_votes", "other_votes", "direct_two_party_votes", "redistributed_two_party_votes"]: out[col] = 0.0
    out["source_result_ids_json"] = "[]"; out["preparation_method"] = "exact_county_code_or_name_then_county_party_proportional"
    lookup: dict[tuple[str, str], set[int]] = {}
    for i, row in out.iterrows():
        for value in {row.PRECINCT_I, row.PRECINCT_N, re.sub(r"^[0-9]+[A-Z]* ", "", norm(row.PRECINCT_N))}:
            lookup.setdefault((row.county_key, norm(value)), set()).add(i)
    rows = result_rows(connection, "GA"); pools = []
    for row in rows.itertuples(index=False):
        keys = {(norm(row.county_name_original), norm(row.precinct_name_original)),
                (norm(row.county_name_original), re.sub(r"^[0-9]+[A-Z]* ", "", norm(row.precinct_name_original)))}
        indexes = set().union(*(lookup.get(key, set()) for key in keys))
        values = {c: float(getattr(row, c)) for c in ["dem_votes", "rep_votes", "other_votes"]}
        if len(indexes) == 1:
            i = indexes.pop()
            for col, value in values.items(): out.loc[i, col] += value
            out.loc[i, "direct_two_party_votes"] += values["dem_votes"] + values["rep_votes"]
            out.loc[i, "source_result_ids_json"] = json.dumps([row.result_observation_id])
        else:
            pools.append({"county": norm(row.county_name_original), **values})
    unmatched = sum(p["dem_votes"] + p["rep_votes"] for p in pools)
    for county, group in pd.DataFrame(pools).groupby("county") if pools else []:
        allocate_pool(out, out.index[out.county_key.eq(county)].tolist(), group[["dem_votes", "rep_votes", "other_votes"]].sum().to_dict())
    source = str(rows.source_file_id.iloc[0]); total = float((rows.dem_votes + rows.rep_votes).sum())
    return finalize(out, "GA", source, geometry_source, len(rows), total, 0.0, unmatched)


def prepare_nc(connection, frame: gpd.GeoDataFrame, geometry_source: str) -> tuple[gpd.GeoDataFrame, dict]:
    frame = frame.copy()
    frame["GEOKEY"] = frame.COUNTY_NAM.map(norm) + "|" + frame.PREC_ID.map(norm)
    out = dissolve(frame, "GEOKEY", ["PREC_ID", "ENR_DESC", "COUNTY_NAM", "COUNTY_ID"])
    out["county_key"] = out.COUNTY_NAM.map(norm); out["precinct_key"] = out.GEOKEY.map(norm)
    for col in ["dem_votes", "rep_votes", "other_votes", "direct_two_party_votes", "redistributed_two_party_votes"]: out[col] = 0.0
    out["source_result_ids_json"] = "[]"; out["preparation_method"] = "exact_ncsbe_precinct_id_then_county_party_proportional_for_modes_and_unmatched"
    lookup = {(row.county_key, norm(row.PREC_ID)): i for i, row in out.iterrows()}
    rows = result_rows(connection, "NC"); pools: dict[str, list[dict]] = {"mode": [], "unmatched": []}
    mode_terms = ("ONE STOP", "ABSENTEE", "PROVISIONAL", "CURBSIDE", "TRANSFER", "ACCUMULATED")
    for row in rows.itertuples(index=False):
        county = norm(row.county_name_original); precinct = norm(str(row.precinct_name_original).split("_")[0])
        values = {c: float(getattr(row, c)) for c in ["dem_votes", "rep_votes", "other_votes"]}
        if (county, precinct) in lookup:
            i = lookup[(county, precinct)]
            for col, value in values.items(): out.loc[i, col] += value
            out.loc[i, "direct_two_party_votes"] += values["dem_votes"] + values["rep_votes"]
            out.loc[i, "source_result_ids_json"] = json.dumps([row.result_observation_id])
        else:
            kind = "mode" if any(term in norm(row.precinct_name_original) for term in mode_terms) else "unmatched"
            pools[kind].append({"county": county, **values})
    for kind, items in pools.items():
        for county, group in pd.DataFrame(items).groupby("county") if items else []:
            allocate_pool(out, out.index[out.county_key.eq(county)].tolist(), group[["dem_votes", "rep_votes", "other_votes"]].sum().to_dict())
    mode = sum(p["dem_votes"] + p["rep_votes"] for p in pools["mode"])
    unmatched = sum(p["dem_votes"] + p["rep_votes"] for p in pools["unmatched"])
    source = str(rows.source_file_id.iloc[0]); total = float((rows.dem_votes + rows.rep_votes).sum())
    return finalize(out, "NC", source, geometry_source, len(rows), total, mode, unmatched)


def prepare_va(connection, frame: gpd.GeoDataFrame, geometry_source: str) -> tuple[gpd.GeoDataFrame, dict]:
    frame["precinctID"] = frame.precinctID.map(lambda x: str(int(x)))
    out = dissolve(frame, "precinctID", ["precinctCo", "precinct", "localityCo", "locality", "congDist"])
    out["county_key"] = out.locality.map(norm); out["precinct_key"] = out.precinctID.map(norm)
    for col in ["dem_votes", "rep_votes", "other_votes", "direct_two_party_votes", "redistributed_two_party_votes"]: out[col] = 0.0
    out["source_result_ids_json"] = "[]"; out["preparation_method"] = "exact_locality_precinct_code_then_locality_cd_party_proportional_for_modes"
    lookup = {(row.county_key, norm(row.precinctCo)): i for i, row in out.iterrows()}
    raw = pd.read_csv(VA_RESULTS, header=[0, 1]); locality = None; direct = 0; source_rows = 0
    locality_totals: dict[str, dict[str, float]] = {}
    # Use the provider's locality totals as the authority for non-geographic
    # absentee/provisional votes. The export contains two duplicated Richmond
    # rows before the first locality and one misplaced duplicate under Prince
    # William, so summing every displayed precinct row would double count.
    for _, row in raw.iterrows():
        kind, label = str(row.iloc[0]), str(row.iloc[1])
        values = {"dem_votes": float(row.iloc[2] or 0), "rep_votes": float(row.iloc[3] or 0),
                  "other_votes": float(pd.to_numeric(row.iloc[4:8], errors="coerce").fillna(0).sum())}
        if kind == "Locality":
            locality = norm(label); locality_totals[locality] = values; continue
        if kind != "Precinct" or locality is None: continue
        source_rows += 1
        code = norm(label.split(" - ", 1)[0])
        if code.startswith("AB") or code.startswith("PROVISIONAL") or (locality, code) not in lookup:
            continue
        i = lookup[(locality, code)]
        for col, value in values.items(): out.loc[i, col] += value
        out.loc[i, "direct_two_party_votes"] += values["dem_votes"] + values["rep_votes"]
        direct += values["dem_votes"] + values["rep_votes"]
    for county, totals in locality_totals.items():
        indexes = out.index[out.county_key.eq(county)].tolist()
        pool = {col: totals[col] - float(out.loc[indexes, col].sum()) for col in ("dem_votes", "rep_votes", "other_votes")}
        if min(pool.values()) < -0.011:
            raise ValueError(f"Virginia locality detail exceeds official total for {county}: {pool}")
        pool = {key: max(0.0, value) for key, value in pool.items()}
        allocate_pool(out, indexes, pool)
    source = connection.execute("SELECT source_file_id FROM source_southern_context_file WHERE manifest_source_file_id='VAELECTIONS-2012-VA-PRESIDENT-PRECINCT'").fetchone()[0]
    source_total = float(sum(v["dem_votes"] + v["rep_votes"] for v in locality_totals.values()))
    mode = source_total - direct
    return finalize(out, "VA", source, geometry_source, source_rows, source_total, mode, 0.0)


PREPARERS = {"FL": prepare_fl, "GA": prepare_ga, "NC": prepare_nc, "VA": prepare_va}


def cells(connection, states: set[str]) -> pd.DataFrame:
    marks = ",".join("?" for _ in states)
    return pd.read_sql_query(
        f"""SELECT s.assignment_source_file_id,s.geography_layer_id,
                   s.state_code,s.plan_cycle,s.chamber,l.geography_vintage
            FROM source_southern_spatial_plan_assignment s
            JOIN dim_southern_geography_layer l ON l.geography_layer_id=s.geography_layer_id
            WHERE s.state_code IN ({marks}) AND s.plan_cycle BETWEEN 2018 AND 2020
            ORDER BY s.state_code,s.plan_cycle,s.chamber""", connection, params=sorted(states),
    )


def build(database: Path | None = None) -> dict:
    manifest = pd.read_csv(GEOMETRY_MANIFEST, dtype=str).fillna("")
    manifest = manifest[manifest.state_code.isin(PREPARERS)].copy()
    block_manifest = pd.read_csv(BLOCK_MANIFEST, dtype=str).fillna("").set_index("state_code")
    detailed = pd.read_csv(DETAILED_MANIFEST, dtype=str).fillna("").set_index("source_file_id")
    vap = load_vap(set(manifest.state_code))
    with closing(connect(database)) as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        targets = cells(connection, set(manifest.state_code))
        run_id = begin_run(connection, "southern_2012_plan_allocations", {
            "contract_version": 1, "states": sorted(manifest.state_code),
            "mode_vote_method": "party-specific proportional allocation within county/locality and congressional district where reported",
            "spatial_weight": "2020 modified VAP with explicit geometry-area fallback",
        }); connection.commit(); connection.execute("BEGIN IMMEDIATE")
        old = "SELECT prepared_precinct_id FROM mart_southern_2012_precinct_vote_geometry"
        connection.execute("DELETE FROM qa_southern_2012_plan_allocation")
        connection.execute("DELETE FROM bridge_southern_2012_precinct_plan_weight")
        connection.execute("DELETE FROM mart_southern_2012_precinct_vote_geometry")
        connection.execute("DELETE FROM mart_southern_presidential_district_result WHERE election_cycle=2012 AND assignment_source_file_id IN (SELECT assignment_source_file_id FROM source_southern_spatial_plan_assignment)")
        connection.execute("DELETE FROM qa_southern_presidential_district_allocation WHERE election_cycle=2012 AND assignment_source_file_id IN (SELECT assignment_source_file_id FROM source_southern_spatial_plan_assignment)")
        connection.execute("DELETE FROM source_southern_precinct_geometry_file")
        audits = []; district_rows = 0
        for source in manifest.to_dict("records"):
            state = source["state_code"]; source_id = register_source(connection, source, normalized=True)
            raw_geometry, member = read_geometry(source)
            connection.execute("INSERT INTO source_southern_precinct_geometry_file VALUES (?,?,?,?,?,?)",
                               (source_id, state, 2012, source["geography_vintage"], member, "passed"))
            if state == "FL": prepared, base = prepare_fl(raw_geometry, source_id)
            else: prepared, base = PREPARERS[state](connection, raw_geometry, source_id)
            records = []
            for row in prepared.itertuples(index=False):
                records.append((row.prepared_precinct_id,run_id,base["result_source_file_id"],source_id,state,
                    row.county_key,row.precinct_key,row.source_result_ids_json,float(row.dem_votes),float(row.rep_votes),
                    float(row.other_votes),float(row.total_votes),float(row.direct_two_party_votes),
                    float(row.redistributed_two_party_votes),row.preparation_method,bytes(row.geometry.wkb),"EPSG:4326"))
            connection.executemany("INSERT INTO mart_southern_2012_precinct_vote_geometry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",records)
            block_path = ROOT / block_manifest.loc[state].local_path
            blocks = gpd.read_file(f"zip://{block_path.resolve().as_posix()}", columns=["GEOID20","geometry"])
            blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
            blocks = blocks.merge(vap.pop(state),on="GEOID20",validate="one_to_one").to_crs(5070)
            spatial = prepared[["prepared_precinct_id","dem_votes","rep_votes","other_votes","total_votes","geometry"]].rename(columns={"prepared_precinct_id":"result_observation_id"}).to_crs(5070)
            precinct_matches, precinct_audit = resolve_point_matches(blocks, spatial)
            for cell in targets[targets.state_code.eq(state)].itertuples(index=False):
                if cell.assignment_source_file_id in detailed.index:
                    districts = detailed_plan_geometry(detailed.loc[cell.assignment_source_file_id].to_dict())
                else:
                    districts = plan_geometry(connection, cell.geography_layer_id)
                plan_matches, plan_audit = assign_blocks_to_plan(blocks, districts)
                matched = precinct_matches.merge(plan_matches,on="block_index",validate="one_to_one").merge(blocks[["GEOID20","VAP_MOD"]],left_on="block_index",right_index=True,validate="one_to_one")
                primary = matched[matched.VAP_MOD.gt(0)].groupby(["result_observation_id","district"],as_index=False).agg(basis=("VAP_MOD","sum"),contributing_blocks=("GEOID20","nunique"),VAP_MOD=("VAP_MOD","sum"))
                positive = set(spatial.loc[spatial.total_votes.gt(0),"result_observation_id"]); primary_ids=set(primary.result_observation_id)
                fallback_ids=positive-primary_ids; fallback_blocks=blocks.copy(); fallback_blocks[f"{cell.chamber}_district"]=fallback_blocks.index.to_series().map(plan_matches.set_index("block_index").district)
                fallback=geometry_fallback(fallback_blocks,spatial,fallback_ids,f"{cell.chamber}_district");primary["weight_basis"]="2020_vap";fallback["weight_basis"]="geometry_intersection_area"
                weights=pd.concat([primary,fallback],ignore_index=True);weights["allocation_weight"]=weights.basis/weights.groupby("result_observation_id").basis.transform("sum")
                missing=positive-set(weights.result_observation_id); max_error=float((weights.groupby("result_observation_id").allocation_weight.sum()-1).abs().max())
                fallback_votes=float(spatial.loc[spatial.result_observation_id.isin(fallback_ids),["dem_votes","rep_votes"]].sum().sum())
                status="passed" if not missing and max_error<=1e-10 and fallback_votes/base["source_two_party_votes"]<=0.001 and (precinct_audit["unmatched_positive_vap"]+plan_audit["unmatched_plan_positive_vap"])/plan_audit["total_positive_vap"]<=0.001 else "review"
                for col,val in {"build_run_id":run_id,"assignment_source_file_id":cell.assignment_source_file_id,"state_code":state,"election_cycle":2012,"plan_cycle":int(cell.plan_cycle),"chamber":cell.chamber}.items():weights[col]=val
                connection.executemany("INSERT INTO bridge_southern_2012_precinct_plan_weight VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",[(r.build_run_id,r.result_observation_id,r.assignment_source_file_id,r.state_code,r.election_cycle,r.plan_cycle,r.chamber,str(r.district),float(r.allocation_weight),r.weight_basis,int(r.contributing_blocks),float(r.VAP_MOD)) for r in weights.itertuples(index=False)])
                allocated=weights.merge(spatial.drop(columns="geometry"),on="result_observation_id",validate="many_to_one")
                audit={**base,"assignment_source_file_id":cell.assignment_source_file_id,"election_cycle":2012,"plan_cycle":int(cell.plan_cycle),"chamber":cell.chamber,"assigned_result_rows":len(positive)-len(missing),"validation_status":status}
                district_rows += insert_district_rows(connection,allocated,audit,run_id,"2012_exact_vintage_precinct_2020_vap_weighted_to_election_plan")
                allocated_two=float(((allocated.dem_votes+allocated.rep_votes)*allocated.allocation_weight).sum())
                connection.execute("INSERT INTO qa_southern_2012_plan_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,base["result_source_file_id"],source_id,cell.assignment_source_file_id,state,int(cell.plan_cycle),cell.chamber,base["source_result_rows"],len(prepared),base["direct_two_party_votes"],base["redistributed_mode_two_party_votes"],base["redistributed_unmatched_two_party_votes"],base["source_two_party_votes"],allocated_two,base["source_two_party_votes"]-allocated_two,max_error,status,f"fallback_geometry_votes={fallback_votes}; unmatched_positive_vap={precinct_audit['unmatched_positive_vap']+plan_audit['unmatched_plan_positive_vap']}") )
                connection.execute("INSERT INTO qa_southern_presidential_district_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(base["result_source_file_id"],cell.assignment_source_file_id,run_id,state,2012,int(cell.plan_cycle),cell.chamber,len(prepared),len(positive)-len(missing),float(prepared.dem_votes.sum()),float((allocated.dem_votes*allocated.allocation_weight).sum()),float(prepared.rep_votes.sum()),float((allocated.rep_votes*allocated.allocation_weight).sum()),base["source_two_party_votes"]-allocated_two,allocated_two/base["source_two_party_votes"],"exact" if status=="passed" else "review"))
                audits.append({**audit,"allocated_two_party_votes":allocated_two,"fallback_geometry_votes":fallback_votes,"missing_positive_precincts":len(missing),"max_precinct_weight_error":max_error})
        reviews=[a for a in audits if a["validation_status"]!="passed"]
        validation={"states":len(manifest),"plan_cells":len(audits),"district_result_rows":district_rows,"prepared_precincts":connection.execute("SELECT COUNT(*) FROM mart_southern_2012_precinct_vote_geometry").fetchone()[0],"weight_rows":connection.execute("SELECT COUNT(*) FROM bridge_southern_2012_precinct_plan_weight").fetchone()[0],"review_cells":reviews}
        for args in [("source_southern_precinct_geometry_file","source","scripts/build_southern_2012_plan_allocations.py","source_file_id","one source per state","replace","2012 exact-vintage precinct geometry"),("mart_southern_2012_precinct_vote_geometry","mart","scripts/build_southern_2012_plan_allocations.py","prepared_precinct_id","one geometry per prepared precinct","replace","2012 votes attached to exact-vintage geometry"),("bridge_southern_2012_precinct_plan_weight","canonical","scripts/build_southern_2012_plan_allocations.py","prepared precinct + assignment + district","explicit m:n allocation bridge","replace","2012 precinct-to-plan VAP weights"),("qa_southern_2012_plan_allocation","qa","scripts/build_southern_2012_plan_allocations.py","result source + assignment + chamber","vote and geography reconciliation","replace","2012 allocation validation")]: register_table(connection,*args)
        if connection.execute("PRAGMA foreign_key_check").fetchall(): raise ValueError("Foreign-key failure")
        if reviews: raise ValueError(f"2012 allocation reviews: {reviews}")
        finish_run(connection,run_id,validation);connection.commit()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"manifest.json").write_text(json.dumps({"contract_version":1,"build_run_id":run_id,"pipeline":"scripts/build_southern_2012_plan_allocations.py","validation":validation},indent=2)+"\n",encoding="utf-8")
    with closing(connect(database,readonly=True)) as connection:
        pd.read_sql_query("SELECT * FROM qa_southern_2012_plan_allocation ORDER BY state_code,plan_cycle,chamber",connection).to_csv(OUT/"allocation_validation.csv",index=False)
    return validation


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--database",type=Path);args=parser.parse_args();print(json.dumps(build(args.database),indent=2))


if __name__ == "__main__": main()
