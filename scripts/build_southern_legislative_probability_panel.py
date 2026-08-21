"""Build a 2018-2024 Southern state-legislative probability calibration panel.

Raw sources remain zipped. The primary panel contains contested, single-member
Democratic-versus-Republican general elections with an independently measured
presidential baseline. Odd-year races are retained in the coverage audit but
not silently mixed into the even-year national-environment calibration.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "historical_statewide_elections"
OUT = ROOT / "data" / "processed" / "forecast_calibration"
STATES = {"AR", "GA", "LA", "MS", "TN", "TX"}
STATE_NAMES = {
    "Arkansas": "AR", "Georgia": "GA", "Louisiana": "LA",
    "Mississippi": "MS", "Tennessee": "TN", "Texas": "TX",
}

# Realized national two-party margins. These isolate district-level forecast
# error; national polling error is estimated and simulated separately.
NATIONAL_MARGIN = {2016: 2.23, 2020: 4.54, 2024: -1.47}


def klarner_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = RAW / "dataverse_files.zip"
    with ZipFile(path) as zf:
        source = pd.read_csv(zf.open("202slers_uoa_contest20230810.csv"), low_memory=False)
    source = source[source.state.isin(STATE_NAMES)].copy()
    source["state"] = source.state.map(STATE_NAMES)
    source = source[source.year.between(2018, 2022)]
    audit = (source.groupby(["state", "year", "sen"], as_index=False)
             .agg(source_contests=("dno", "size"), dontuse=("dontuse", "sum"),
                  uncontested=("uncont", "sum"), big_third=("bigthird", "sum")))
    usable = source[
        source.dontuse.eq(0) & source.bigthird.eq(0) & source.dseats.eq(1)
        & source.eseats.eq(1) & source.dvote.notna() & source.rvote.notna()
        & source.dvote.gt(0) & source.rvote.gt(0)
    ].copy()
    usable["chamber"] = np.where(usable.sen.eq(1), "upper", "lower")
    usable["district"] = pd.to_numeric(usable.dno, errors="coerce")
    usable["dem_votes"] = usable.dvote
    usable["rep_votes"] = usable.rvote
    usable["dem_margin"] = 100 * (usable.dem_votes - usable.rep_votes) / (usable.dem_votes + usable.rep_votes)
    usable["dem_win"] = usable.dwin.gt(0).astype(int)
    usable["incumbency_balance"] = usable.dinc.fillna(0) - usable.rinc.fillna(0)
    usable["result_source"] = "Klarner SLER contest file"
    return usable[["state", "year", "chamber", "district", "dem_votes", "rep_votes",
                   "dem_margin", "dem_win", "incumbency_balance", "result_source"]], audit


def results_2024() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = RAW / "dataverse_files (1).zip"
    usecols = ["precinct", "office", "party_simplified", "mode", "votes", "district",
               "year", "state_po", "stage", "special", "writein"]
    with ZipFile(path) as zf:
        raw = pd.read_csv(zf.open("STATE_precinct_general.csv"), usecols=usecols, low_memory=False)
    raw = raw[
        raw.state_po.isin(STATES) & raw.office.isin(["STATE HOUSE", "STATE SENATE"])
        & raw.year.eq(2024) & raw.stage.eq("GEN") & ~raw.special.fillna(False)
        & raw.party_simplified.isin(["DEMOCRAT", "REPUBLICAN"])
    ].copy()
    raw["votes"] = pd.to_numeric(raw.votes, errors="coerce")
    raw = raw.dropna(subset=["votes", "district"])
    # Prefer a TOTAL row for a precinct/candidate when supplied; otherwise sum
    # its mutually exclusive voting modes.
    key = ["state_po", "office", "district", "precinct", "party_simplified"]
    has_total = raw.groupby(key).mode.transform(lambda x: x.eq("TOTAL").any())
    raw = raw[~has_total | raw["mode"].eq("TOTAL")]
    votes = (raw.groupby(["state_po", "office", "district", "party_simplified"], as_index=False).votes.sum()
             .pivot(index=["state_po", "office", "district"], columns="party_simplified", values="votes")
             .reset_index())
    audit = (votes.groupby(["state_po", "office"], as_index=False)
             .agg(source_contests=("district", "size")))
    audit["year"] = 2024
    votes = votes.dropna(subset=["DEMOCRAT", "REPUBLICAN"])
    votes = votes[votes.DEMOCRAT.gt(0) & votes.REPUBLICAN.gt(0)].copy()
    votes["state"] = votes.state_po
    votes["year"] = 2024
    votes["chamber"] = np.where(votes.office.eq("STATE SENATE"), "upper", "lower")
    votes["district"] = pd.to_numeric(votes.district, errors="coerce")
    votes["dem_votes"], votes["rep_votes"] = votes.DEMOCRAT, votes.REPUBLICAN
    votes["dem_margin"] = 100 * (votes.dem_votes - votes.rep_votes) / (votes.dem_votes + votes.rep_votes)
    votes["dem_win"] = votes.dem_votes.gt(votes.rep_votes).astype(int)
    votes["incumbency_balance"] = np.nan
    votes["result_source"] = "MEDSL 2024 precinct general returns"
    return votes[["state", "year", "chamber", "district", "dem_votes", "rep_votes",
                  "dem_margin", "dem_win", "incumbency_balance", "result_source"]], audit


def post2020_presidential_baselines() -> pd.DataFrame:
    block_path = RAW / "national_block_2020_pres_results.zip"
    with ZipFile(block_path) as zf:
        blocks = pd.read_csv(
            zf.open("national_block_2020_pres_results/national_block_2020_pres_results.csv"),
            usecols=["GEOID20", "STATEAB", "G20PREDBID", "G20PRERTRU"],
            dtype={"GEOID20": str, "STATEAB": str}, low_memory=False,
        )
    blocks = blocks[blocks.STATEAB.isin(STATES)].copy()
    blocks["GEOID20"] = blocks.GEOID20.str.zfill(15)
    outputs = []
    for year in (2022, 2024):
        boundary_path = RAW / f"national_{year}_elections_st_leg_boundaries.zip"
        member = f"national_{year}_elections_st_leg_boundaries_baf.csv"
        with ZipFile(boundary_path) as zf:
            baf = pd.read_csv(zf.open(member), usecols=["GEOID20", "STATE", "SLDU", "SLDL"],
                              dtype={"GEOID20": str, "STATE": str}, low_memory=False)
        baf = baf[baf.STATE.isin(STATES)].copy()
        baf["GEOID20"] = baf.GEOID20.str.zfill(15)
        joined = baf.merge(blocks, on="GEOID20", how="left", validate="one_to_one")
        for chamber, field in (("upper", "SLDU"), ("lower", "SLDL")):
            agg = (joined.groupby(["STATE", field], as_index=False)[["G20PREDBID", "G20PRERTRU"]].sum())
            agg["state"], agg["year"], agg["chamber"] = agg.STATE, year, chamber
            agg["district"] = pd.to_numeric(agg[field], errors="coerce")
            agg["prior_pres_margin"] = 100 * (agg.G20PREDBID - agg.G20PRERTRU) / (agg.G20PREDBID + agg.G20PRERTRU)
            agg["presidential_source"] = f"2020 block results aggregated to {year} BAF"
            outputs.append(agg[["state", "year", "chamber", "district", "prior_pres_margin", "presidential_source"]])
    return pd.concat(outputs, ignore_index=True)


def pre2020_presidential_baselines() -> pd.DataFrame:
    path = RAW / "Daily Kos Elections Statewide Results by LD (public).xlsx"
    book = pd.ExcelFile(path)
    outputs = []
    for state in sorted(STATES):
        for chamber, suffix in (("upper", "Upper"), ("lower", "Lower")):
            matches = [s for s in book.sheet_names if s.strip() == f"{state}_{suffix}"]
            if not matches:
                continue
            frame = pd.read_excel(path, sheet_name=matches[0], header=1)
            district_col = "SD" if chamber == "upper" else "HD"
            if district_col not in frame or "Clinton%" not in frame.columns:
                continue
            clinton_pos = list(frame.columns).index("Clinton%")
            if clinton_pos + 1 >= len(frame.columns):
                continue
            # Several workbook sheets inherit a duplicate-column suffix rather
            # than the intended Trump% label. The adjacent numeric share is the
            # Republican presidential percentage in the workbook's fixed schema.
            republican_share_col = frame.columns[clinton_pos + 1]
            out = pd.DataFrame({
                "state": state, "chamber": chamber,
                "district": pd.to_numeric(frame[district_col], errors="coerce"),
                "prior_pres_margin": 100 * (pd.to_numeric(frame["Clinton%"], errors="coerce")
                                               - pd.to_numeric(frame[republican_share_col], errors="coerce")),
            }).dropna()
            out["presidential_source"] = "Daily Kos 2016 presidential results by 2010-plan district"
            for year in (2018, 2019, 2020):
                copy = out.copy(); copy["year"] = year; outputs.append(copy)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    old, old_audit = klarner_results()
    new, new_audit = results_2024()
    results = pd.concat([old, new], ignore_index=True)
    baselines = pd.concat([pre2020_presidential_baselines(), post2020_presidential_baselines()], ignore_index=True)
    baselines = (baselines.groupby(["state", "year", "chamber", "district"], as_index=False)
                 .agg(prior_pres_margin=("prior_pres_margin", "mean"),
                      presidential_source=("presidential_source", "first")))
    panel = results.merge(baselines, on=["state", "year", "chamber", "district"], how="left", validate="many_to_one")
    panel["national_swing"] = panel.year.map({
        2018: 6.280563,
        2020: NATIONAL_MARGIN[2020] - NATIONAL_MARGIN[2016],
        2022: -7.177168,
        2024: NATIONAL_MARGIN[2024] - NATIONAL_MARGIN[2020],
    })
    # Midterms use the realized national U.S. House swing; presidential years
    # use the realized presidential swing. National polling error is modeled as
    # a separate uncertainty layer rather than being hidden in district error.
    panel["environment_baseline_margin"] = panel.prior_pres_margin + panel.national_swing
    demographics_path = OUT / "southern_sld_acs_demographics.csv"
    if demographics_path.exists():
        demographics = pd.read_csv(demographics_path)
        panel = panel.merge(
            demographics, on=["state", "year", "chamber", "district"], how="left", validate="many_to_one"
        )
    else:
        panel["nonwhite_share"] = np.nan
        panel["college_share"] = np.nan
        panel["white_college_share"] = np.nan
        panel["acs_vintage"] = np.nan
        panel["demographics_source"] = np.nan
    panel["swing_x_nonwhite"] = panel.national_swing * panel.nonwhite_share
    panel["swing_x_white_college"] = panel.national_swing * panel.white_college_share
    panel["baseline_error"] = panel.dem_margin - panel.environment_baseline_margin
    panel["primary_calibration_eligible"] = (
        panel.year.isin([2018, 2020, 2022, 2024]) & panel.prior_pres_margin.notna()
    )
    panel.to_csv(OUT / "southern_legislative_probability_panel.csv", index=False)
    pd.concat([
        old_audit.rename(columns={"sen": "chamber_code"}),
        new_audit.rename(columns={"state_po": "state", "office": "chamber"}),
    ], ignore_index=True, sort=False).to_csv(OUT / "southern_legislative_source_coverage.csv", index=False)
    coverage = (panel.groupby(["state", "year", "chamber"], as_index=False)
                .agg(contested_races=("district", "size"), baselines=("prior_pres_margin", "count"),
                     eligible=("primary_calibration_eligible", "sum")))
    coverage.to_csv(OUT / "southern_legislative_panel_coverage.csv", index=False)
    print(coverage.to_string(index=False))
    print("\nEligible races:", int(panel.primary_calibration_eligible.sum()))


if __name__ == "__main__":
    main()
