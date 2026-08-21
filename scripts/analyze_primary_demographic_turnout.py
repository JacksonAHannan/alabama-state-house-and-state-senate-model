"""Test whether Alabama primary turnout predicts demographic general turnout.

The SOS precinct exports do not contain usable precinct registration counts, so
the confirmatory analysis aggregates their ballot-count rows to counties and
uses 2020 Census voting-age population (VAP) as a common denominator.  Outcomes
are normalized to each election's statewide turnout rate before forward tests;
this asks whether primaries predict *where* turnout will be high, not the
unobservable 2026 statewide level.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from build_alabama_race_ei import block_race

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/alabama_elections_and_geography"
PRIMARY = RAW / "historical_primaries"
OUT = ROOT / "data/processed/elections/validation"

PRIMARY_ARCHIVES = {
    2018: PRIMARY / "2018_primary_precinct_results.zip",
    2020: PRIMARY / "2020_primary_precinct_results.zip",
    2022: PRIMARY / "2022_primary_precinct_results.zip",
    2024: PRIMARY / "2024_primary_precinct_results.zip",
    2026: PRIMARY / "2026_primary_election_results.zip",
}
GENERAL_FOLDERS = {
    2018: RAW / "2018-Official-General-Precinct-Results",
    2022: RAW / "2022 General Precinct Level Results",
    2024: RAW / "2024-General Precinct Level Results",
}


def county_key(value: object) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper().replace("COUNTY", ""))


def county_lookup() -> pd.DataFrame:
    """Use the supplied 2022 VEST precinct geography as the county authority."""
    import geopandas as gpd

    shp = next((RAW / "al_gen_22_prec").glob("*.shp"))
    frame = gpd.read_file(shp, ignore_geometry=True)[["COUNTYFP", "County"]].drop_duplicates()
    frame["county_key"] = frame.County.map(county_key)
    frame["county_fips"] = frame.COUNTYFP.astype(str).str.zfill(3)
    if len(frame) != 67 or frame.county_key.duplicated().any():
        raise ValueError("Expected 67 unique Alabama counties")
    return frame[["county_key", "county_fips", "County"]]


def filename_county(name: str) -> str:
    stem = Path(name).stem
    for marker in ("PRIMARY_ELECTION-", "Primary-", "General-"):
        if marker.lower() in stem.lower():
            stem = re.split(re.escape(marker), stem, flags=re.I)[-1]
    return county_key(stem)


def ballot_rows(payload: bytes) -> dict[str, float]:
    data = pd.read_excel(io.BytesIO(payload), sheet_name=0, header=None).fillna("")
    if data.shape[1] < 4:
        return {}
    labels = data.iloc[:, 0].astype(str).str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
    result: dict[str, float] = {}
    definitions = {
        "ballots": r"^BALLOTS CAST - TOTAL$",
        "dem_ballots": r"^BALLOTS CAST - DEMOCRAT(?: \(DEM\))?$",
        "rep_ballots": r"^BALLOTS CAST - REPUBLICAN(?: \(REP\))?$",
    }
    for key, pattern in definitions.items():
        matches = data.loc[labels.str.match(pattern), data.columns[3:]]
        if len(matches):
            result[key] = float(pd.to_numeric(matches.iloc[0], errors="coerce").fillna(0).sum())
    return result


def primary_totals(year: int) -> pd.DataFrame:
    rows = []
    with ZipFile(PRIMARY_ARCHIVES[year]) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".xls"):
                continue
            values = ballot_rows(archive.read(name))
            if values.get("ballots", 0) > 0:
                rows.append({"cycle": year, "county_key": filename_county(name), **values})
    result = pd.DataFrame(rows)
    if result.county_key.duplicated().any():
        raise ValueError(f"Duplicate primary county in {year}")
    return result


def general_totals(year: int) -> pd.DataFrame:
    rows = []
    for path in GENERAL_FOLDERS[year].glob("*.xls"):
        values = ballot_rows(path.read_bytes())
        if values.get("ballots", 0) > 0:
            rows.append({"cycle": year, "county_key": filename_county(path.name),
                         "general_ballots": values["ballots"]})
    result = pd.DataFrame(rows)
    if result.county_key.duplicated().any():
        raise ValueError(f"Duplicate general county in {year}")
    return result


def demographics() -> pd.DataFrame:
    race = block_race(2020)
    race["county_fips"] = race.blockid.str[2:5]
    county = race.groupby("county_fips", as_index=False)[
        ["population", "white_nh", "black_nh", "other"]].sum()
    county["black_vap_share"] = county.black_nh / county.population
    county["white_vap_share"] = county.white_nh / county.population
    return county.merge(county_lookup(), on="county_fips", validate="one_to_one")


def panel() -> pd.DataFrame:
    demos = demographics()
    rows = []
    for year in (2018, 2022, 2024):
        joined = primary_totals(year).merge(general_totals(year),
                                             on=["cycle", "county_key"], validate="one_to_one")
        joined = joined.merge(demos, on="county_key", validate="one_to_one")
        rows.append(joined)
    data = pd.concat(rows, ignore_index=True)
    data["primary_turnout_rate"] = data.ballots / data.population
    data["general_turnout_rate"] = data.general_ballots / data.population
    data["dem_primary_share"] = data.dem_ballots / (data.dem_ballots + data.rep_ballots)
    for col in ("primary_turnout_rate", "general_turnout_rate"):
        statewide = data.groupby("cycle").apply(
            lambda x: x[("ballots" if col.startswith("primary") else "general_ballots")].sum()
            / x.population.sum(), include_groups=False)
        data[f"relative_{col}"] = data[col] / data.cycle.map(statewide)
    data["black_x_primary"] = data.black_vap_share * data.relative_primary_turnout_rate
    data["black_x_dem_primary"] = data.black_vap_share * data.dem_primary_share
    return data


SPECS = {
    "demographics_only": ["black_vap_share", "white_vap_share"],
    "primary_level": ["black_vap_share", "white_vap_share", "relative_primary_turnout_rate"],
    "primary_demographic": ["black_vap_share", "white_vap_share", "relative_primary_turnout_rate",
                            "dem_primary_share", "black_x_primary", "black_x_dem_primary"],
}


def model():
    return make_pipeline(SimpleImputer(), StandardScaler(), Ridge(alpha=10.0))


def validate(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    details, summaries = [], []
    for name, features in SPECS.items():
        for cycle in sorted(data.cycle.unique()):
            train, test = data[data.cycle.ne(cycle)], data[data.cycle.eq(cycle)]
            fitted = model().fit(train[features], train.relative_general_turnout_rate)
            prediction = fitted.predict(test[features])
            for row, estimate in zip(test.itertuples(index=False), prediction):
                details.append({"specification": name, "test_cycle": cycle,
                                "county": row.County, "actual_relative_general_turnout": row.relative_general_turnout_rate,
                                "predicted_relative_general_turnout": estimate,
                                "absolute_error": abs(row.relative_general_turnout_rate-estimate)})
    detail = pd.DataFrame(details)
    for name, part in detail.groupby("specification"):
        summaries.append({"specification": name, "forward_mae": part.absolute_error.mean(),
                          "worst_cycle_mae": part.groupby("test_cycle").absolute_error.mean().max(),
                          "counties": len(part), "cycles": part.test_cycle.nunique()})
    summary = pd.DataFrame(summaries).sort_values("forward_mae")
    errors = detail.pivot(index=["test_cycle", "county"], columns="specification",
                          values="absolute_error")
    baseline = errors.demographics_only
    rng = np.random.default_rng(20260817)
    for index, row in summary.iterrows():
        name = row.specification
        delta = baseline - errors[name]
        observed = float(delta.mean())
        cluster_delta = delta.groupby(level="county").mean().to_numpy()
        sampled = rng.choice(cluster_delta, size=(4000, len(cluster_delta)), replace=True)
        draws = sampled.mean(axis=1)
        summary.loc[index, "mae_improvement_vs_demographics_only"] = observed
        summary.loc[index, "cluster_bootstrap_ci_low"] = np.quantile(draws, .025)
        summary.loc[index, "cluster_bootstrap_ci_high"] = np.quantile(draws, .975)
        summary.loc[index, "cluster_bootstrap_probability_improvement"] = np.mean(np.array(draws) > 0)
    return detail, summary


def score_2026(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    demos = demographics()
    current = primary_totals(2026).merge(demos, on="county_key", validate="one_to_one")
    current["primary_turnout_rate"] = current.ballots / current.population
    statewide = current.ballots.sum() / current.population.sum()
    current["relative_primary_turnout_rate"] = current.primary_turnout_rate / statewide
    current["dem_primary_share"] = current.dem_ballots / (current.dem_ballots + current.rep_ballots)
    current["black_x_primary"] = current.black_vap_share * current.relative_primary_turnout_rate
    current["black_x_dem_primary"] = current.black_vap_share * current.dem_primary_share
    for name, features in SPECS.items():
        fitted = model().fit(data[features], data.relative_general_turnout_rate)
        current[f"predicted_relative_general_turnout__{name}"] = fitted.predict(current[features])
    current["primary_demographic_increment"] = (
        current.predicted_relative_general_turnout__primary_demographic
        - current.predicted_relative_general_turnout__demographics_only)
    high = current.black_vap_share.ge(current.black_vap_share.quantile(.75))
    summary = pd.DataFrame([
        {"metric": "statewide_primary_turnout_rate", "value": statewide},
        {"metric": "black_share_correlation_with_relative_primary_turnout", "value": current.black_vap_share.corr(current.relative_primary_turnout_rate)},
        {"metric": "high_black_county_mean_relative_primary_turnout", "value": current.loc[high, "relative_primary_turnout_rate"].mean()},
        {"metric": "other_county_mean_relative_primary_turnout", "value": current.loc[~high, "relative_primary_turnout_rate"].mean()},
        {"metric": "high_black_primary_demographic_increment", "value": current.loc[high, "primary_demographic_increment"].mean()},
        {"metric": "other_primary_demographic_increment", "value": current.loc[~high, "primary_demographic_increment"].mean()},
    ])
    return current, summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = panel()
    detail, summary = validate(data)
    current, current_summary = score_2026(data)
    data.to_csv(OUT / "primary_demographic_turnout_panel.csv", index=False)
    detail.to_csv(OUT / "primary_turnout_forward_validation.csv", index=False)
    summary.to_csv(OUT / "primary_turnout_model_summary.csv", index=False)
    current.to_csv(OUT / "2026_primary_demographic_turnout_signal.csv", index=False)
    current_summary.to_csv(OUT / "2026_primary_demographic_turnout_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("\n2026 signal")
    print(current_summary.to_string(index=False))


if __name__ == "__main__":
    main()
