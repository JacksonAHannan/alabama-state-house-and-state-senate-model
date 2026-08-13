"""Build WAR-ready Alabama legislative race and district-baseline tables.

2014 and 2018 use normalized OpenElections copies of official precinct returns.
2022 uses RDH precinct and legislative-district split layers. Geometry is not
required: legislative contest activity supplies weights for split precincts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import is_pseudocandidate, load_oe, norm_party  # noqa: E402


CORE_BASELINE_OFFICES = {"Governor", "Attorney General"}
EXECUTIVE_OFFICES = {
    "Governor",
    "Lieutenant Governor",
    "Attorney General",
    "Secretary of State",
    "State Auditor",
    "State Treasurer",
    "Commissioner of Agriculture and Industries",
}
MAP_VINTAGE = {2014: "2012_enacted", 2018: "2017_remedial", 2022: "2021_enacted"}


def load_jefferson_2014_legislative(root: Path) -> pd.DataFrame:
    """Repair OpenElections' omitted Jefferson legislative contests."""
    path = (
        root
        / "Results and Shapefiles"
        / "2014General-precinctLevel"
        / "Jefferson 2014 General Precinct.xls"
    )
    wide = pd.read_excel(path)
    title_col, party_col, candidate_col = wide.columns[:3]
    legislative = wide[
        wide[title_col].astype(str).str.contains("STATE REPRESENTATIVE|STATE SENATOR", case=False, regex=True)
    ].copy()
    records: list[pd.DataFrame] = []
    for _, row in legislative.iterrows():
        title = str(row[title_col])
        match = re.search(r"DISTRICT\s+(\d+)", title, flags=re.I)
        if not match:
            continue
        office = "State House" if "REPRESENTATIVE" in title.upper() else "State Senate"
        part = pd.DataFrame(
            {
                "county": "Jefferson",
                "precinct": [str(c) for c in wide.columns[4:]],
                "office": office,
                "district": int(match.group(1)),
                "party": row[party_col],
                "candidate": row[candidate_col],
                "votes": [row[c] for c in wide.columns[4:]],
            }
        )
        records.append(part)
    data = pd.concat(records, ignore_index=True)
    data["votes"] = pd.to_numeric(data["votes"], errors="coerce").fillna(0.0)
    data["district"] = pd.to_numeric(data["district"], errors="coerce")
    data["party_norm"] = data["party"].map(norm_party)
    data["county_key"] = data["county"].astype(str).str.upper().str.strip()
    data["precinct_key"] = data["precinct"].astype(str).str.upper().str.strip()
    return data


def oe_cycle(data: pd.DataFrame, cycle: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates: list[pd.DataFrame] = []
    weights: list[pd.DataFrame] = []
    for office, chamber in [("State House", "house"), ("State Senate", "senate")]:
        legislative = data[(data["office"] == office) & data["district"].notna()].copy()
        activity = (
            legislative.groupby(["county_key", "precinct_key", "district"], as_index=False)["votes"]
            .sum()
            .rename(columns={"votes": "district_activity"})
        )
        activity["precinct_activity"] = activity.groupby(
            ["county_key", "precinct_key"]
        )["district_activity"].transform("sum")
        activity["allocation_weight"] = np.where(
            activity["precinct_activity"] > 0,
            activity["district_activity"] / activity["precinct_activity"],
            np.nan,
        )
        activity["chamber"] = chamber
        weights.append(activity)

        named = legislative[
            legislative["party_norm"].isin(["D", "R"])
            & ~legislative["candidate"].map(is_pseudocandidate)
        ]
        result = (
            named.groupby(["district", "candidate", "party_norm"], as_index=False)["votes"]
            .sum()
            .rename(columns={"party_norm": "party"})
        )
        result["cycle"] = cycle
        result["chamber"] = chamber
        result["candidate_code"] = result["candidate"]
        candidates.append(result)

    statewide = data[
        data["office"].isin(EXECUTIVE_OFFICES) & data["party_norm"].isin(["D", "R"])
    ][["county_key", "precinct_key", "office", "party_norm", "candidate", "votes"]]
    baseline_parts: list[pd.DataFrame] = []
    for weight in weights:
        merged = statewide.merge(
            weight[["county_key", "precinct_key", "district", "allocation_weight", "chamber"]],
            on=["county_key", "precinct_key"],
            how="inner",
        )
        merged["allocated_votes"] = merged["votes"] * merged["allocation_weight"]
        merged["cycle"] = cycle
        baseline_parts.append(merged)
    return pd.concat(candidates, ignore_index=True), pd.concat(baseline_parts, ignore_index=True), pd.concat(weights, ignore_index=True)


def candidate_columns(columns: list[str], prefix: str) -> list[str]:
    return [c for c in columns if c.startswith(prefix) and "OWRI" not in c]


def rdh_2022_cycle(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source = root / "Results and Shapefiles" / "al_gen_22_prec"
    statewide = gpd.read_file(source / "al_gen_22_st_prec.shp", ignore_geometry=True)
    candidates: list[pd.DataFrame] = []
    allocations: list[pd.DataFrame] = []
    weights_out: list[pd.DataFrame] = []

    for chamber, filename, district_col, prefix, width in [
        ("house", "al_gen_22_sldl_prec.shp", "SLDL_DIST", "GSL", 3),
        ("senate", "al_gen_22_sldu_prec.shp", "SLDU_DIST", "GSU", 2),
    ]:
        split = gpd.read_file(source / filename, ignore_geometry=True)
        split["district"] = pd.to_numeric(split[district_col], errors="coerce")
        split["county_key"] = split["County"].astype(str).str.upper().str.strip()
        split["precinct_key"] = split["Precinct"].astype(str).str.upper().str.strip()
        legislative_cols = candidate_columns(list(split.columns), prefix)
        split["district_activity"] = split[legislative_cols].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0).sum(axis=1)
        split["precinct_activity"] = split.groupby(
            ["county_key", "precinct_key"]
        )["district_activity"].transform("sum")
        split["allocation_weight"] = np.where(
            split["precinct_activity"] > 0,
            split["district_activity"] / split["precinct_activity"],
            np.nan,
        )
        weights = split[
            ["county_key", "precinct_key", "district", "district_activity", "precinct_activity", "allocation_weight"]
        ].copy()
        weights["chamber"] = chamber
        weights_out.append(weights)

        for district in sorted(split["district"].dropna().astype(int).unique()):
            district_prefix = f"{prefix}{district:0{width}d}"
            for column in [c for c in legislative_cols if c.startswith(district_prefix)]:
                party_position = len(district_prefix)
                party = column[party_position] if len(column) > party_position else "O"
                if party not in {"D", "R"}:
                    continue
                votes = pd.to_numeric(split[column], errors="coerce").fillna(0).sum()
                candidates.append(
                    pd.DataFrame(
                        [{
                            "district": district,
                            "candidate": column,
                            "party": party,
                            "votes": float(votes),
                            "cycle": 2022,
                            "chamber": chamber,
                            "candidate_code": column,
                        }]
                    )
                )

        st = statewide.copy()
        st["county_key"] = st["County"].astype(str).str.upper().str.strip()
        st["precinct_key"] = st["Precinct"].astype(str).str.upper().str.strip()
        statewide_fields: list[dict[str, object]] = []
        office_names = {
            "GOV": "Governor",
            "LTG": "Lieutenant Governor",
            "ATG": "Attorney General",
            "SOS": "Secretary of State",
            "AUD": "State Auditor",
            "TRE": "State Treasurer",
            "AGR": "Commissioner of Agriculture and Industries",
        }
        for column in st.columns:
            match = re.match(r"G22([A-Z0-9]{3})([DR])", column)
            if match and match.group(1) in office_names:
                statewide_fields.append(
                    {
                        "column": column,
                        "office": office_names[match.group(1)],
                        "party_norm": match.group(2),
                    }
                )
        long_parts = []
        for field in statewide_fields:
            part = st[["county_key", "precinct_key", field["column"]]].copy()
            part = part.rename(columns={field["column"]: "votes"})
            part["votes"] = pd.to_numeric(part["votes"], errors="coerce").fillna(0)
            part["office"] = field["office"]
            part["party_norm"] = field["party_norm"]
            part["candidate"] = field["column"]
            long_parts.append(part)
        statewide_long = pd.concat(long_parts, ignore_index=True)
        merged = statewide_long.merge(
            weights[["county_key", "precinct_key", "district", "allocation_weight"]],
            on=["county_key", "precinct_key"],
            how="inner",
        )
        merged["allocated_votes"] = merged["votes"] * merged["allocation_weight"]
        merged["cycle"] = 2022
        merged["chamber"] = chamber
        allocations.append(merged)

    return pd.concat(candidates, ignore_index=True), pd.concat(allocations, ignore_index=True), pd.concat(weights_out, ignore_index=True)


def race_tables(candidate_results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Some 2014 county files shorten a multicounty candidate to a surname and
    # incorrectly label that fragment's party. Reattach an unambiguous surname
    # fragment to the full-name record before aggregating party totals.
    repaired_groups = []
    for _, group in candidate_results.groupby(["cycle", "chamber", "district"], sort=False):
        group = group.copy()
        names = group.candidate.astype(str).str.upper().str.replace(r"[^A-Z ]", " ", regex=True).str.split()
        full = group[names.map(len).ge(2)].copy()
        def last_name(value: object) -> str:
            tokens = re.sub(r"[^A-Z ]", " ", str(value).upper()).split()
            while tokens and tokens[-1] in {"JR", "SR", "II", "III", "IV"}:
                tokens.pop()
            return tokens[-1] if tokens else ""
        full["_last"] = full.candidate.map(last_name)
        last_party = full.groupby("_last").party.agg(lambda x: x.iloc[0] if x.nunique() == 1 else None).to_dict()
        last_name = full.sort_values(full.candidate.astype(str).str.len().name if False else "votes",
                                     ascending=False).drop_duplicates("_last").set_index("_last").candidate.to_dict()
        for idx, tokens in names.items():
            if len(tokens) == 1 and tokens[0] in last_party and last_party[tokens[0]] is not None:
                group.loc[idx, "party"] = last_party[tokens[0]]
                group.loc[idx, "candidate"] = last_name[tokens[0]]
                group.loc[idx, "candidate_code"] = last_name[tokens[0]]
        repaired_groups.append(group)
    candidate_results = pd.concat(repaired_groups, ignore_index=True)
    candidate_results = (
        candidate_results.groupby(
            ["cycle", "chamber", "district", "candidate", "candidate_code", "party"], as_index=False
        )["votes"].sum()
    )
    # A multicounty contest may use a full name in one county and only a
    # surname in another. There is one general-election nominee per party, so
    # preserve the most vote-bearing label and sum all county vote fragments.
    keys = ["cycle", "chamber", "district", "party"]
    candidate_results["_name_length"] = candidate_results.candidate.astype(str).str.len()
    representative = (candidate_results.sort_values(["_name_length", "votes"], ascending=False)
                      .drop_duplicates(keys)[keys + ["candidate", "candidate_code"]])
    totals = candidate_results.groupby(keys, as_index=False).votes.sum()
    candidate_results = totals.merge(representative, on=keys, validate="one_to_one")[
        ["cycle", "chamber", "district", "candidate", "candidate_code", "party", "votes"]]
    party = (
        candidate_results.groupby(["cycle", "chamber", "district", "party"], as_index=False)["votes"]
        .sum()
        .pivot(index=["cycle", "chamber", "district"], columns="party", values="votes")
        .fillna(0)
        .reset_index()
    )
    for column in ["D", "R"]:
        if column not in party:
            party[column] = 0.0
    party = party.rename(columns={"D": "dem_votes", "R": "rep_votes"})
    party["two_party_votes"] = party["dem_votes"] + party["rep_votes"]
    party["legislative_dem_margin"] = np.where(
        party["two_party_votes"] > 0,
        100 * (party["dem_votes"] - party["rep_votes"]) / party["two_party_votes"],
        np.nan,
    )
    party["war_eligible"] = (party["dem_votes"] > 0) & (party["rep_votes"] > 0)
    party["winner_party"] = np.select(
        [party["dem_votes"] > party["rep_votes"], party["rep_votes"] > party["dem_votes"]],
        ["D", "R"],
        default="TIE",
    )
    party["map_vintage"] = party["cycle"].map(MAP_VINTAGE)
    return candidate_results, party


def baseline_tables(allocations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    office_party = (
        allocations.groupby(["cycle", "chamber", "district", "office", "party_norm"], as_index=False)["allocated_votes"]
        .sum()
        .pivot(index=["cycle", "chamber", "district", "office"], columns="party_norm", values="allocated_votes")
        .fillna(0)
        .reset_index()
    )
    for column in ["D", "R"]:
        if column not in office_party:
            office_party[column] = 0.0
    office_party = office_party.rename(columns={"D": "dem_votes", "R": "rep_votes"})
    office_party["two_party_votes"] = office_party["dem_votes"] + office_party["rep_votes"]
    office_party["office_dem_margin"] = np.where(
        (office_party["dem_votes"] > 0) & (office_party["rep_votes"] > 0),
        100 * (office_party["dem_votes"] - office_party["rep_votes"]) / office_party["two_party_votes"],
        np.nan,
    )
    office_party["contested_dr"] = office_party["office_dem_margin"].notna()
    office_party["core_office"] = office_party["office"].isin(CORE_BASELINE_OFFICES)

    contested = office_party[office_party["contested_dr"]]
    expanded = contested.groupby(["cycle", "chamber", "district"]).agg(
        statewide_index_margin=("office_dem_margin", "mean"),
        statewide_index_offices=("office", "nunique"),
    )
    core = contested[contested["core_office"]].groupby(["cycle", "chamber", "district"]).agg(
        core_index_margin=("office_dem_margin", "mean"),
        core_index_offices=("office", "nunique"),
    )
    baseline = expanded.join(core, how="outer").reset_index()
    baseline["core_index_complete"] = baseline["core_index_offices"] == len(CORE_BASELINE_OFFICES)
    baseline.loc[~baseline["core_index_complete"], "core_index_margin"] = np.nan
    baseline["baseline_quality"] = np.select(
        [
            baseline["core_index_complete"] & (baseline["statewide_index_offices"] >= 3),
            baseline["core_index_complete"],
        ],
        ["complete_core_expanded", "complete_core_limited_expanded"],
        default="incomplete_core",
    )
    baseline["map_vintage"] = baseline["cycle"].map(MAP_VINTAGE)
    return office_party, baseline


def allocation_qa(allocations: pd.DataFrame) -> pd.DataFrame:
    keys = ["cycle", "chamber", "county_key", "precinct_key", "office", "party_norm", "candidate"]
    source = (
        allocations.drop_duplicates(keys)[keys + ["votes"]]
        .groupby(["cycle", "chamber", "office"], as_index=False)["votes"]
        .sum()
        .rename(columns={"votes": "source_votes_with_join"})
    )
    allocated = (
        allocations.groupby(["cycle", "chamber", "office"], as_index=False)["allocated_votes"]
        .sum()
    )
    qa = source.merge(allocated, on=["cycle", "chamber", "office"], how="outer")
    qa["allocation_reconciliation_ratio"] = qa["allocated_votes"] / qa["source_votes_with_join"].where(
        qa["source_votes_with_join"] != 0
    )
    return qa


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "raw" / "openelections"
    candidate_parts = []
    allocation_parts = []
    weight_parts = []
    for cycle, filename in [
        (2014, "20141104__al__general__precinct.csv"),
        (2018, "20181106__al__general__precinct.csv"),
    ]:
        source_data = load_oe(raw / filename)
        if cycle == 2014:
            # OpenElections contains a partial/duplicated set of Jefferson
            # legislative rows (often shortened candidate names) while the
            # official county workbook contains the complete contest records.
            # Replace, rather than append to, those rows to prevent double count.
            jefferson_legislative = (
                source_data["county_key"].eq("JEFFERSON")
                & source_data["office"].isin(["State House", "State Senate"])
            )
            source_data = source_data.loc[~jefferson_legislative].copy()
            source_data = pd.concat(
                [source_data, load_jefferson_2014_legislative(root)], ignore_index=True
            )
        candidates, allocations, weights = oe_cycle(source_data, cycle)
        candidate_parts.append(candidates)
        allocation_parts.append(allocations)
        weights["cycle"] = cycle
        weight_parts.append(weights)
    candidates, allocations, weights = rdh_2022_cycle(root)
    candidate_parts.append(candidates)
    allocation_parts.append(allocations)
    weights["cycle"] = 2022
    weight_parts.append(weights)

    candidate_results, races = race_tables(pd.concat(candidate_parts, ignore_index=True))
    all_allocations = pd.concat(allocation_parts, ignore_index=True)
    office_baselines, baselines = baseline_tables(all_allocations)
    district_cycle = races.merge(
        baselines,
        on=["cycle", "chamber", "district", "map_vintage"],
        how="left",
        validate="one_to_one",
    )
    district_cycle["raw_overperformance"] = (
        district_cycle["legislative_dem_margin"] - district_cycle["statewide_index_margin"]
    )
    district_cycle["core_raw_overperformance"] = (
        district_cycle["legislative_dem_margin"] - district_cycle["core_index_margin"]
    )

    output = root / "data" / "processed" / "war"
    output.mkdir(parents=True, exist_ok=True)
    candidate_results.to_csv(output / "race_candidate_results.csv", index=False)
    races.to_csv(output / "race_results.csv", index=False)
    office_baselines.to_csv(output / "district_baseline_office.csv", index=False)
    baselines.to_csv(output / "district_baselines.csv", index=False)
    allocation_qa(all_allocations).to_csv(output / "baseline_allocation_qa.csv", index=False)
    district_cycle.to_csv(output / "district_cycle_model.csv", index=False)
    pd.concat(weight_parts, ignore_index=True).to_csv(
        output / "precinct_district_allocation_weights.csv", index=False
    )


if __name__ == "__main__":
    main()
