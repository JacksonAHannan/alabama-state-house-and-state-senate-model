"""Build a conservative adjacent-cycle alias graph for Alabama precincts."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

from audit_historical_precinct_geography import (DB, OUT, county_match_key,
                                                   donor_vtds, normalize_split_base)
from oe_normalize import normalize_for_match

YEARS = (1994, 1998, 2002, 2004, 2006, 2008, 2010)
PAIRS = tuple(zip(YEARS[:-1], YEARS[1:]))
AUDIT = OUT / "historical_precinct_geometry_audit.csv"


def nodes_and_turnout() -> pd.DataFrame:
    with sqlite3.connect(DB) as connection:
        nodes = pd.read_sql_query("""SELECT node_id,year,county_key,precinct_key,precinct_code,
          county_level_ballot FROM precinct_nodes WHERE source='alabama_sos'
          AND year IN (1994,1998,2002,2004,2006,2008,2010)""", connection)
        turnout = pd.read_sql_query("""WITH contests AS (
          SELECT year,county_key,precinct_key,office,COALESCE(district,-1) district,SUM(votes) votes
          FROM vote_observations WHERE source='alabama_sos'
          AND year IN (1994,1998,2002,2004,2006,2008,2010)
          GROUP BY year,county_key,precinct_key,office,COALESCE(district,-1))
          SELECT year,county_key,precinct_key,MAX(votes) turnout FROM contests
          GROUP BY year,county_key,precinct_key""", connection)
    nodes = nodes.merge(turnout, on=["year", "county_key", "precinct_key"], how="left", validate="one_to_one")
    nodes = nodes[nodes.county_level_ballot.eq(0)].copy()
    nodes["county_match_key"] = nodes.county_key.map(county_match_key)
    nodes["name_norm"] = nodes.precinct_key.map(normalize_for_match)
    nodes["split_base"] = nodes.precinct_key.map(normalize_split_base)
    nodes["code_norm"] = nodes.precinct_code.fillna("").astype(str).str.replace(r"[^0-9A-Z]", "", regex=True).str.lstrip("0")
    nodes["turnout_share"] = nodes.turnout / nodes.groupby(["year", "county_match_key"]).turnout.transform("sum")
    nodes["graph_node"] = nodes.apply(lambda row: f"{row.year}|{row.county_match_key}|{row.precinct_key}", axis=1)
    return nodes


def pair_edges(left: pd.DataFrame, right: pd.DataFrame) -> list[dict]:
    evidence = {}
    for i, old in enumerate(left.itertuples(index=False)):
        for j, new in enumerate(right.itertuples(index=False)):
            name_score = float(fuzz.WRatio(old.name_norm, new.name_norm))
            code_exact = bool(old.code_norm and old.code_norm == new.code_norm)
            base_exact = bool(old.split_base and old.split_base == new.split_base)
            if not (name_score >= 65 or code_exact or base_exact):
                continue
            if old.turnout_share > 0 and new.turnout_share > 0:
                turnout_score = 100 * math.exp(-abs(math.log(old.turnout_share / new.turnout_share)))
            else:
                turnout_score = 0.0
            composite = 0.72 * name_score + 0.18 * turnout_score + 10 * code_exact + 8 * base_exact
            evidence[(i, j)] = (name_score, turnout_score, code_exact, base_exact, composite)
    by_old = {i: sorted((values[4], j) for (old_i, j), values in evidence.items() if old_i == i)
              for i in range(len(left))}
    by_new = {j: sorted((values[4], i) for (i, new_j), values in evidence.items() if new_j == j)
              for j in range(len(right))}
    rows = []
    for (i, j), values in evidence.items():
        name_score, turnout_score, code_exact, base_exact, composite = values
        structural = ((name_score == 100) or (code_exact and name_score >= 40) or
                      (base_exact and name_score >= 60))
        old_rank = by_old[i]; new_rank = by_new[j]
        old_best = old_rank[-1][0]; old_second = old_rank[-2][0] if len(old_rank) > 1 else 0
        new_best = new_rank[-1][0]; new_second = new_rank[-2][0] if len(new_rank) > 1 else 0
        unique_fuzzy = (name_score >= 88 and composite == old_best == new_best and
                        old_best - old_second >= 8 and new_best - new_second >= 8)
        accepted = structural or unique_fuzzy
        if not accepted:
            continue
        old, new = left.iloc[i], right.iloc[j]
        confidence = "high" if name_score == 100 or (code_exact and name_score >= 80) else "medium"
        rows.append({"old_node": old.graph_node, "new_node": new.graph_node,
                     "old_year": old.year, "new_year": new.year,
                     "county_key": old.county_match_key, "old_precinct": old.precinct_key,
                     "new_precinct": new.precinct_key, "name_score": name_score,
                     "turnout_score": turnout_score, "code_exact": int(code_exact),
                     "split_base_exact": int(base_exact), "composite_score": composite,
                     "confidence": confidence, "relationship": (
                         "split_or_merge_candidate" if structural and (len(old_rank) > 1 or len(new_rank) > 1)
                         else "one_to_one_candidate"),
                     "verification_status": "adjacent_cycle_alias_candidate"})
    return rows


def build_edges(nodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for old_year, new_year in PAIRS:
        counties = sorted(set(nodes[nodes.year.eq(old_year)].county_match_key) &
                          set(nodes[nodes.year.eq(new_year)].county_match_key))
        for county in counties:
            left = nodes[(nodes.year.eq(old_year)) & nodes.county_match_key.eq(county)].reset_index(drop=True)
            right = nodes[(nodes.year.eq(new_year)) & nodes.county_match_key.eq(county)].reset_index(drop=True)
            rows.extend(pair_edges(left, right))
    return pd.DataFrame(rows)


def donor_seeds(nodes: pd.DataFrame) -> pd.DataFrame:
    audit = pd.read_csv(AUDIT)
    exact_methods = {"exact_name", "exact_name_district_constraint",
                     "exact_vtd_code_district_constraint", "split_base_district_constraint"}
    strong_fuzzy = (audit.name_match_method.str.contains("fuzzy", na=False) &
                    audit.name_match_score.ge(95) & audit.name_match_margin.ge(10))
    seeds = audit[audit.donor_vtd_id.notna() &
                  (audit.name_match_method.isin(exact_methods) | strong_fuzzy)].copy()
    seeds["county_match_key"] = seeds.county_key.map(county_match_key)
    seeds["graph_node"] = seeds.apply(lambda row: f"{row.cycle}|{row.county_match_key}|{row.precinct_key}", axis=1)
    rows = seeds[["graph_node", "donor_vtd_id", "donor_name", "donor_vintage"]].to_dict("records")
    donors = donor_vtds(); d2010 = donors[donors.donor_vintage.eq(2010)].copy()
    d2010["county_match_key"] = d2010.county_key.map(county_match_key)
    for node in nodes[nodes.year.eq(2010)].itertuples(index=False):
        pool = d2010[d2010.county_match_key.eq(node.county_match_key)]
        exact_code = pool[pool.donor_code_norm.eq(node.code_norm)] if node.code_norm else pool.iloc[0:0]
        exact_name = pool[pool.donor_name_norm.eq(node.name_norm)]
        hit = exact_code.iloc[0] if len(exact_code) == 1 else exact_name.iloc[0] if len(exact_name) == 1 else None
        if hit is not None:
            rows.append({"graph_node": node.graph_node, "donor_vtd_id": hit.donor_vtd_id,
                         "donor_name": hit.donor_name, "donor_vintage": 2010})
    return pd.DataFrame(rows).drop_duplicates()


def resolve(edges: pd.DataFrame, seeds: pd.DataFrame, nodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    graph = {}
    for old_node, new_node in edges[["old_node", "new_node"]].itertuples(index=False, name=None):
        graph.setdefault(old_node, set()).add(new_node); graph.setdefault(new_node, set()).add(old_node)
    seed_map = seeds.groupby("graph_node").agg({"donor_vtd_id": lambda v: sorted(set(v)),
                                                "donor_name": "first", "donor_vintage": "first"}).to_dict("index")
    resolutions, ambiguous = [], []
    node_lookup = nodes.set_index("graph_node")
    unseen = set(graph)
    while unseen:
        start = unseen.pop(); component = {start}; stack = [start]
        while stack:
            neighbors = graph.get(stack.pop(), set()) & unseen
            unseen -= neighbors; component |= neighbors; stack.extend(neighbors)
        donor_ids = sorted({donor for node in component if node in seed_map for donor in seed_map[node]["donor_vtd_id"]})
        if len(donor_ids) != 1:
            if donor_ids:
                ambiguous.append({"component_size": len(component), "donor_count": len(donor_ids),
                                  "donor_vtd_ids": "|".join(donor_ids), "nodes": "|".join(sorted(component))})
            continue
        donor_id = donor_ids[0]
        source_seed = next(seed_map[node] for node in component if node in seed_map and donor_id in seed_map[node]["donor_vtd_id"])
        seed_nodes = {node for node in component if node in seed_map and donor_id in seed_map[node]["donor_vtd_id"]}
        distances = {node: 0 for node in seed_nodes}; frontier = list(seed_nodes)
        while frontier:
            current = frontier.pop(0)
            for neighbor in graph.get(current, set()):
                if neighbor in component and neighbor not in distances:
                    distances[neighbor] = distances[current] + 1; frontier.append(neighbor)
        for node in component:
            if node not in node_lookup.index:
                continue
            record = node_lookup.loc[node]
            resolutions.append({"graph_node": node, "cycle": int(record.year),
                "county_key": record.county_key, "precinct_key": record.precinct_key,
                "donor_vtd_id": donor_id, "donor_name": source_seed["donor_name"],
                "donor_vintage": int(source_seed["donor_vintage"]),
                "path_length_to_seed": distances[node],
                "match_method": "adjacent_cycle_alias_graph", "confidence": "medium",
                "verification_status": "inferred_from_adjacent_cycle_aliases"})
    return pd.DataFrame(resolutions), pd.DataFrame(ambiguous)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nodes = nodes_and_turnout(); edges = build_edges(nodes); seeds = donor_seeds(nodes)
    resolutions, ambiguous = resolve(edges, seeds, nodes)
    edges.to_csv(OUT / "adjacent_cycle_precinct_alias_edges.csv", index=False)
    resolutions.to_csv(OUT / "adjacent_cycle_precinct_alias_resolutions.csv", index=False)
    ambiguous.to_csv(OUT / "adjacent_cycle_precinct_alias_ambiguous_components.csv", index=False)
    print({"nodes": len(nodes), "edges": len(edges), "seeds": len(seeds),
           "resolutions": len(resolutions), "ambiguous_components": len(ambiguous)})


if __name__ == "__main__":
    main()
