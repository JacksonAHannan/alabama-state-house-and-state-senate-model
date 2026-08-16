"""Link precinct records across election sources using auditable evidence.

Links are county/year constrained. Names and leading precinct codes provide
identity evidence; vectors of office-level vote totals provide an independent
fingerprint. The script writes candidates and accepted links separately so an
ambiguous suggestion never silently becomes canonical geography.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import process
from rapidfuzz.fuzz import WRatio

from oe_normalize import is_county_level_ballot, normalize_for_match

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
WAR = ROOT / "data" / "processed" / "war"


def precinct_code(value: object) -> str:
    match = re.match(r"\s*(\d{1,6})(?:\s*[-_:]|\s+)", str(value))
    return str(int(match.group(1))) if match else ""


def build_nodes(votes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = ["year", "source", "county_key", "precinct_key"]
    nodes = votes[keys].drop_duplicates().copy()
    nodes["name_norm"] = nodes.precinct_key.map(normalize_for_match)
    nodes["precinct_code"] = nodes.precinct_key.map(precinct_code)
    nodes["county_level_ballot"] = nodes.precinct_key.map(is_county_level_ballot).astype(int)
    nodes["node_id"] = np.arange(1, len(nodes) + 1)
    totals = (votes.groupby(keys + ["office"], as_index=False).votes.sum()
              .merge(nodes[keys + ["node_id"]], on=keys, validate="many_to_one"))
    return nodes, totals[["node_id", "office", "votes"]]


def vote_similarity(left, right) -> tuple[float, int]:
    if isinstance(left, pd.DataFrame): left = dict(zip(left.office, left.votes))
    if isinstance(right, pd.DataFrame): right = dict(zip(right.office, right.votes))
    shared = set(left) & set(right)
    if not shared: return 0.0, 0
    values = []
    for office in shared:
        a, b = left[office], right[office]; denom = max(a, b, 1)
        values.append(max(0, 1-abs(a-b)/denom))
    return float(100*np.median(values)), len(shared)


def score_pair(left: pd.Series, right: pd.Series, left_votes: pd.DataFrame,
               right_votes: pd.DataFrame) -> dict[str, object]:
    name_score = float(WRatio(left.name_norm, right.name_norm))
    code_exact = bool(left.precinct_code and left.precinct_code == right.precinct_code)
    vote_score, shared = vote_similarity(left_votes, right_votes)
    # Vote evidence receives full weight only with multiple shared contests.
    vote_weight = min(shared / 3, 1) * .40
    code_weight = .25 if left.precinct_code and right.precinct_code else 0
    name_weight = 1 - vote_weight - code_weight
    composite = name_weight * name_score + vote_weight * vote_score + code_weight * (100 if code_exact else 0)
    return {"left_node_id": int(left.node_id), "right_node_id": int(right.node_id),
            "name_score": name_score, "code_exact": int(code_exact),
            "vote_score": vote_score, "shared_offices": shared, "composite_score": composite}


def match_sources(nodes: pd.DataFrame, totals: pd.DataFrame, left_source: str,
                  right_source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = []
    vote_groups = {node: dict(zip(group.office, group.votes)) for node, group in totals.groupby("node_id")}
    left = nodes[nodes.source.eq(left_source) & nodes.county_level_ballot.eq(0)]
    right = nodes[nodes.source.eq(right_source) & nodes.county_level_ballot.eq(0)]
    pools = {}
    for key, group in right.groupby(["year", "county_key"]):
        name_choices = group.set_index("node_id").name_norm.to_dict()
        code_map = {code: set(g.node_id) for code, g in group[group.precinct_code.ne("")].groupby("precinct_code")}
        signature_map = {}
        for node in group.node_id:
            fingerprint = vote_groups.get(node, {})
            signature = tuple(sorted((office, round(votes, 6)) for office, votes in fingerprint.items()))
            signature_map.setdefault(signature, set()).add(node)
        pools[key] = (group.set_index("node_id"), name_choices, code_map, signature_map)
    for _, lrow in left.iterrows():
        bundle = pools.get((lrow.year, lrow.county_key))
        if bundle is None: continue
        pool, name_choices, code_map, signature_map = bundle
        candidate_ids = {item[2] for item in process.extract(lrow.name_norm, name_choices,
                                                              scorer=WRatio, limit=5)}
        candidate_ids |= code_map.get(lrow.precinct_code, set())
        fingerprint = vote_groups.get(lrow.node_id, {})
        signature = tuple(sorted((office, round(votes, 6)) for office, votes in fingerprint.items()))
        candidate_ids |= signature_map.get(signature, set())
        for node_id in candidate_ids:
            rrow = pool.loc[node_id]
            name = float(WRatio(lrow.name_norm, rrow.name_norm))
            code = bool(lrow.precinct_code and lrow.precinct_code == rrow.precinct_code)
            lv, rv = vote_groups.get(lrow.node_id, {}), vote_groups.get(node_id, {})
            vote, shared = vote_similarity(lv, rv)
            if name < 55 and not code and not (shared >= 2 and vote >= 98): continue
            rrow = rrow.copy(); rrow["node_id"] = node_id
            candidates.append(score_pair(lrow, rrow, lv, rv))
    frame = pd.DataFrame(candidates)
    if frame.empty: return frame, frame
    frame = frame.sort_values(["left_node_id", "composite_score"], ascending=[True, False])
    frame["candidate_rank"] = frame.groupby("left_node_id").cumcount()+1
    frame["score_margin"] = frame.composite_score - frame.groupby("left_node_id").composite_score.transform(
        lambda x: x.iloc[1] if len(x)>1 else 0)
    best = frame[frame.candidate_rank.eq(1)].copy()
    best["match_method"] = np.select(
        [best.code_exact.eq(1) & best.name_score.ge(75), best.name_score.eq(100) & best.vote_score.ge(95),
         best.composite_score.ge(88) & best.score_margin.ge(5) & best.shared_offices.ge(2)],
        ["code_name", "exact_name_vote", "composite"], default="review")
    best["accepted"] = best.match_method.ne("review").astype(int)
    return frame, best


def main() -> None:
    with sqlite3.connect(DB) as connection:
        votes = pd.read_sql("SELECT year,source,county_key,precinct_key,office,votes FROM vote_observations", connection)
        nodes, totals = build_nodes(votes)
        candidates, links = match_sources(nodes, totals, "alabama_sos", "openelections")
        accepted = links[links.accepted.eq(1)]
        right_uses = accepted.groupby("right_node_id").size()
        links["relationship"] = np.where(
            links.accepted.eq(0), "unresolved",
            np.where(links.right_node_id.map(right_uses).fillna(0).gt(1), "many_sos_to_one_oe", "one_to_one"))
        nodes.to_sql("precinct_nodes", connection, index=False, if_exists="replace")
        totals.to_sql("precinct_vote_fingerprints", connection, index=False, if_exists="replace")
        candidates.to_sql("precinct_match_candidates", connection, index=False, if_exists="replace")
        links.to_sql("precinct_source_links", connection, index=False, if_exists="replace")
        current = WAR / "geographic_precinct_vtd_matches.csv"
        if current.exists():
            pd.read_csv(current).to_sql("precinct_vtd_link_evidence", connection, index=False, if_exists="replace")
    review = links.merge(nodes.add_prefix("left_")[["left_node_id", "left_year", "left_county_key",
                         "left_precinct_key", "left_name_norm", "left_precinct_code"]],
                         on="left_node_id", how="left")
    right_names = nodes.add_prefix("right_")[["right_node_id", "right_precinct_key",
                                               "right_name_norm", "right_precinct_code"]]
    review = review.merge(right_names, on="right_node_id", how="left")
    review.sort_values(["left_year", "left_county_key", "accepted", "composite_score"],
                       ascending=[True, True, True, False]).to_csv(
        ROOT / "data" / "processed" / "elections" / "precinct_link_review.csv", index=False)
    print(links.groupby(["match_method", "accepted"]).size().to_string())
    print(f"Accepted {links.accepted.sum():,} of {len(links):,} SOS precinct links; "
          f"{(links.match_method=='review').sum():,} queued for review")

if __name__ == "__main__": main()
