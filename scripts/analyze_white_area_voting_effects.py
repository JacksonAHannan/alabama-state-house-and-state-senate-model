"""Test Madison County contextual effects in white voting composition, 2018-2024.

This is an aggregate precinct analysis, not an individual-level estimate of
white vote choice.  It asks whether precincts in the Huntsville/Madison metro
run more Democratic than otherwise similar Alabama precincts, especially as
their white-college share increases, and whether that residual grows over time.
"""
from __future__ import annotations

from pathlib import Path
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import norm

from build_precinct_joint_demographics import allocate, block_precinct_links

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "war"
DOC = ROOT / "project_docs" / "model" / "WHITE_AREA_VOTING_EFFECTS.md"
CELLS = ["white_nh_noncollege", "white_nh_college", "black_noncollege",
         "black_college", "other_noncollege", "other_college"]


def _read_2024() -> gpd.GeoDataFrame:
    archive = (RAW / "rdh" / "al_2024_gen_prec.zip").resolve()
    shp = str(archive).replace("\\", "/")
    return gpd.read_file(f"/vsizip/{shp}/al_2024_gen_all_prec/al_2024_gen_all_prec.shp")


def precinct_sources() -> dict[int, tuple[gpd.GeoDataFrame, str, str, str]]:
    p18 = gpd.read_file(f"zip://{(RAW/'alabama_elections_and_geography'/'al_vest_18.zip').resolve()}")
    p20 = gpd.read_file(f"zip://{(RAW/'alabama_elections_and_geography'/'al_vest_20.zip').resolve()}")
    p22 = gpd.read_file(RAW/'alabama_elections_and_geography'/'al_gen_22_prec.zip',
                        layer="al_gen_22_no_splits_prec")
    p24 = _read_2024()
    return {
        2018: (p18, "COUNTYFP20", "G18GOVDMAD", "G18GOVRIVE"),
        2020: (p20, "COUNTYFP20", "G20PREDBID", "G20PRERTRU"),
        2022: (p22, "COUNTYFP", "G22GOVDFLO", "G22GOVRIVE"),
        2024: (p24, "COUNTYFP", "G24PREDHAR", "G24PRERTRU"),
    }


def links_for_frame(frame: gpd.GeoDataFrame) -> pd.DataFrame:
    precincts = frame[["precinct_id", "geometry"]].to_crs(5070)
    blocks = gpd.read_file(f"zip://{(RAW/'census'/'tl_2020_01_tabblock20.zip').resolve()}")
    blocks = blocks[["GEOID20", "geometry"]].rename(columns={"GEOID20": "blockid"}).to_crs(5070)
    points = blocks.set_geometry(blocks.geometry.representative_point())
    joined = gpd.sjoin(points, precincts, how="inner", predicate="within")
    return joined.sort_index().drop_duplicates("blockid")[["blockid", "precinct_id"]]


def build_panel() -> pd.DataFrame:
    cells = pd.read_csv(ROOT/"data"/"processed"/"demographics"/
                        "acs_block_group_joint_race_education_modeled.csv",
                        dtype={"block_group_geoid": str})
    rows = []
    for cycle, (geo, county_col, dem_col, rep_col) in precinct_sources().items():
        geo = geo.reset_index(names="precinct_id")
        vintage = 2022 if cycle <= 2022 else 2024
        links = block_precinct_links(cycle) if cycle in (2018, 2020) else links_for_frame(geo)
        demo = allocate(cells, links, cycle, vintage)
        vote = geo[["precinct_id", county_col, dem_col, rep_col]].rename(
            columns={county_col: "county_fips", dem_col: "dem_votes", rep_col: "rep_votes"})
        x = vote.merge(demo[["precinct_id", *CELLS, "adult25_total"]], on="precinct_id", validate="one_to_one")
        x["cycle"] = cycle
        rows.append(x)
    panel = pd.concat(rows, ignore_index=True)
    panel["county_fips"] = panel.county_fips.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(3)
    panel["two_party_votes"] = panel.dem_votes + panel.rep_votes
    panel = panel[(panel.two_party_votes >= 25) & (panel.adult25_total > 0)].copy()
    panel["dem_share"] = panel.dem_votes / panel.two_party_votes
    for col in CELLS:
        panel[col + "_share"] = panel[col] / panel.adult25_total
    panel["madison_county"] = (panel.county_fips == "089").astype(int)
    panel["time"] = (panel.cycle - 2018) / 2
    panel["madison_x_white_college"] = panel.madison_county * panel.white_nh_college_share
    panel["madison_x_white_noncollege"] = panel.madison_county * panel.white_nh_noncollege_share
    return panel


def _design(panel: pd.DataFrame, extra: list[str]) -> tuple[np.ndarray, list[str]]:
    names = ["intercept", "cycle_2020", "cycle_2022", "cycle_2024",
             "white_nh_noncollege_share", "white_nh_college_share",
             "black_noncollege_share", "black_college_share", "other_college_share", *extra]
    columns = [np.ones(len(panel)), *(panel.cycle.eq(c).astype(float) for c in (2020, 2022, 2024)),
               *(panel[c].to_numpy(float) for c in names[4:9])]
    for name in extra:
        if name == "madison_county:time": columns.append((panel.madison_county * panel.time).to_numpy(float))
        elif name == "madison_x_white_college:time": columns.append((panel.madison_x_white_college * panel.time).to_numpy(float))
        else: columns.append(panel[name].to_numpy(float))
    return np.column_stack(columns), names


def _wls_hc1(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    sw = np.sqrt(w / np.mean(w)); xw = x * sw[:, None]; yw = y * sw
    bread = np.linalg.pinv(xw.T @ xw); beta = bread @ xw.T @ yw
    residual = yw - xw @ beta
    meat = xw.T @ (xw * residual[:, None] ** 2)
    covariance = bread @ meat @ bread * len(y) / (len(y) - x.shape[1])
    ssr = np.sum(residual**2); sst = np.sum((yw - np.average(yw))**2)
    return beta, np.sqrt(np.maximum(np.diag(covariance), 0)), 1 - ssr/sst


def fit_models(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Other noncollege is the omitted composition category. Cycle fixed effects
    # absorb statewide election environments; covariance is HC1 robust.
    specs = {
        "area_level": ["madison_county"],
        "education_concentration": ["madison_county", "madison_x_white_college", "madison_x_white_noncollege"],
        "growing_area_effect": ["madison_county", "madison_county:time", "madison_x_white_college",
                                "madison_x_white_college:time", "madison_x_white_noncollege"],
    }
    estimates = []
    for name, extra in specs.items():
        x, names = _design(panel, extra)
        beta, se, r2 = _wls_hc1(x, panel.dem_share.to_numpy(), panel.two_party_votes.to_numpy())
        for i, term in enumerate(names):
            if "madison" in term:
                z = beta[i] / se[i]
                estimates.append({"model": name, "term": term, "estimate": beta[i],
                                  "std_error": se[i], "p_value": 2*norm.sf(abs(z)),
                                  "ci_low": beta[i]-1.96*se[i], "ci_high": beta[i]+1.96*se[i],
                                  "n_precincts": len(panel), "r_squared": r2})
    # Transparent cycle-specific adjusted Madison residuals from a statewide
    # model that excludes the area indicator.
    x, _ = _design(panel, [])
    beta, _, _ = _wls_hc1(x, panel.dem_share.to_numpy(), panel.two_party_votes.to_numpy())
    panel = panel.copy(); panel["residual"] = panel.dem_share - x @ beta
    cycle_rows = []
    for cycle, group in panel.groupby("cycle"):
        for area, subset in group.groupby("madison_county"):
            cycle_rows.append({"cycle": cycle, "area": "Madison County" if area else "Rest of Alabama",
                               "precincts": len(subset), "votes": subset.two_party_votes.sum(),
                               "weighted_residual": np.average(subset.residual, weights=subset.two_party_votes),
                               "white_college_share": np.average(subset.white_nh_college_share,
                                                                  weights=subset.adult25_total)})
    return pd.DataFrame(estimates), pd.DataFrame(cycle_rows)


def write_report(panel: pd.DataFrame, estimates: pd.DataFrame, trends: pd.DataFrame) -> None:
    grow = estimates[estimates.model.eq("growing_area_effect")].set_index("term")
    trend = grow.loc["madison_county:time"] if "madison_county:time" in grow.index else None
    edu = grow.loc["madison_x_white_college"] if "madison_x_white_college" in grow.index else None
    edu_trend = grow.loc["madison_x_white_college:time"] if "madison_x_white_college:time" in grow.index else None
    def line(label, row):
        return f"- {label}: {100*row.estimate:+.2f} points (95% CI {100*row.ci_low:+.2f} to {100*row.ci_high:+.2f}; p={row.p_value:.3f})."
    text = ["# Madison–Huntsville white-voting area-effect test", "",
            "## Scope", "",
            "This precinct-level contextual analysis covers the 2018 governor, 2020 president, 2022 governor, and 2024 president elections. Madison County is the reproducible proxy for the Huntsville–Madison metro. It does **not** identify individual white voters, and municipal boundaries are not yet separated from the rest of the county.", "",
            "## Results", ""]
    if edu is not None: text.append(line("Madison × white-college composition", edu))
    if trend is not None: text.append(line("Madison area effect per two-year step", trend))
    if edu_trend is not None: text.append(line("Additional growth in the white-college interaction per step", edu_trend))
    header = "| cycle | area | precincts | votes | weighted residual | white-college share |"
    rule = "|---:|---|---:|---:|---:|---:|"
    table = [header, rule] + [f"| {int(r.cycle)} | {r.area} | {int(r.precincts)} | {int(r.votes)} | {r.weighted_residual:.4f} | {r.white_college_share:.4f} |" for r in trends.itertuples()]
    text += ["", "Adjusted residual by election:", "", *table, "", "## Interpretation", "",
             "A positive Madison coefficient means precincts in the county vote more Democratic than statewide demographic composition and election-year effects predict. A positive Madison × white-college term is consistent with the difference being concentrated in educated-white precinct composition. Because this is aggregate ecological evidence, it should be treated as a forecast feature hypothesis, not a causal or individual-level finding.", "",
             "The time test has only four elections and mixes gubernatorial with presidential electorates. Promotion requires forward-validation showing that the area terms improve held-out prediction, plus a municipal/suburban geography refinement using Census place and urban-area boundaries."]
    DOC.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    warnings.filterwarnings("ignore", message=".*invalid winding order.*")
    panel = build_panel()
    estimates, trends = fit_models(panel)
    OUT.mkdir(parents=True, exist_ok=True)
    panel.drop(columns=[]).to_csv(OUT/"white_area_voting_precinct_panel.csv", index=False)
    estimates.to_csv(OUT/"white_area_voting_model_estimates.csv", index=False)
    trends.to_csv(OUT/"white_area_voting_cycle_trends.csv", index=False)
    write_report(panel, estimates, trends)
    print(estimates.to_string(index=False))
    print("\n", trends.to_string(index=False))


if __name__ == "__main__":
    main()
