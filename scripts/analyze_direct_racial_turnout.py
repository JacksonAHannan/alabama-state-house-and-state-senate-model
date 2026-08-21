"""Test primary signals against direct SOS Black and White general turnout."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from pypdf import PdfReader
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from analyze_primary_demographic_turnout import county_key, primary_totals

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/alabama_elections_and_geography/sos_racial_turnout"
OUT = ROOT / "data/processed/elections/validation"
REGISTRATION_SHEETS = {2018: "2018 General Election", 2020: "2020 General", 2024: "October", 2026: "MAY"}


def registration(year: int) -> pd.DataFrame:
    path = next(RAW.glob(f"{year}_voter_registration.*"))
    data = pd.read_excel(path, sheet_name=REGISTRATION_SHEETS[year], header=None).fillna(0)
    rows = data.iloc[2:].copy()
    result = pd.DataFrame({
        "county_key": rows.iloc[:, 0].map(county_key),
        "registered_total": pd.to_numeric(rows.iloc[:, 1], errors="coerce"),
        "registered_black": pd.to_numeric(rows.iloc[:, 4], errors="coerce") + pd.to_numeric(rows.iloc[:, 14], errors="coerce"),
        "registered_white": pd.to_numeric(rows.iloc[:, 8], errors="coerce") + pd.to_numeric(rows.iloc[:, 18], errors="coerce"),
    })
    result = result[result.county_key.ne("TOTAL") & result.registered_total.notna()].copy()
    result["cycle"] = year
    if len(result) != 67:
        raise ValueError(f"Expected 67 registration counties for {year}, found {len(result)}")
    return result


def participation_xlsx(path: Path, year: int) -> pd.DataFrame:
    data = pd.read_excel(path, sheet_name=0, header=None).fillna(0).iloc[2:].copy()
    result = pd.DataFrame({"county_key": data.iloc[:, 0].map(county_key),
                           "general_ballots": pd.to_numeric(data.iloc[:, 1], errors="coerce"),
                           "black_ballots": pd.to_numeric(data.iloc[:, 4], errors="coerce"),
                           "white_ballots": pd.to_numeric(data.iloc[:, 10], errors="coerce")})
    result = result[~result.county_key.str.startswith("TOTAL") & result.general_ballots.notna()].copy()
    result["cycle"] = year
    return result


def participation_pdf(path: Path, year: int) -> pd.DataFrame:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    rows = []
    # Every county data row has the county token followed by ten integer fields.
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z_ ]+?)\s+([\d,]+(?:\s+[\d,]+){8,9})\s*$", line.strip())
        if not match:
            continue
        values = [int(item.replace(",", "")) for item in match.group(2).split()]
        if year == 2024 and len(values) == 9:
            values.insert(4, 0)  # PDF suppresses Randolph's zero federal-registration cell.
        # 2024 prints White before Not Identified; 2020 prints it last.
        white_index = 8 if year == 2024 else 9
        rows.append({"cycle": year, "county_key": county_key(match.group(1)),
                     "general_ballots": values[0], "black_ballots": values[3],
                     "white_ballots": values[white_index]})
    result = pd.DataFrame(rows).drop_duplicates("county_key")
    result = result[~result.county_key.str.startswith("TOTAL")].copy()
    if len(result) != 67:
        missing = sorted(set(registration(year).county_key) - set(result.county_key))
        raise ValueError(f"Parsed {len(result)} participation counties for {year}; missing {missing}")
    return result


def participation(year: int) -> pd.DataFrame:
    path = next(RAW.glob(f"{year}_general_participation_by_race.*"))
    return participation_xlsx(path, year) if path.suffix.lower() == ".xlsx" else participation_pdf(path, year)


def build_panel() -> pd.DataFrame:
    frames = []
    for year in (2018, 2020, 2024):
        data = participation(year).merge(registration(year), on=["cycle", "county_key"], validate="one_to_one")
        data = data.merge(primary_totals(year), on=["cycle", "county_key"], validate="one_to_one")
        frames.append(data)
    panel = pd.concat(frames, ignore_index=True)
    return add_features(panel)


def add_features(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data["registered_black_share"] = data.registered_black / data.registered_total
    data["primary_turnout_rate"] = data.ballots / data.registered_total
    data["dem_primary_rate"] = data.dem_ballots / data.registered_total
    data["rep_primary_rate"] = data.rep_ballots / data.registered_total
    data["dem_primary_share"] = data.dem_ballots / (data.dem_ballots + data.rep_ballots)
    if "black_ballots" in data:
        data["black_general_turnout"] = data.black_ballots / data.registered_black
        data["white_general_turnout"] = data.white_ballots / data.registered_white
        for group in ("black", "white"):
            statewide = data.groupby("cycle").apply(
                lambda x: x[f"{group}_ballots"].sum() / x[f"registered_{group}"].sum(), include_groups=False)
            data[f"relative_{group}_general_turnout"] = data[f"{group}_general_turnout"] / data.cycle.map(statewide)
    return data


SPECS = {
    "registration_only": ["registered_black_share"],
    "total_primary": ["registered_black_share", "primary_turnout_rate"],
    "party_primary": ["registered_black_share", "primary_turnout_rate", "dem_primary_rate",
                      "rep_primary_rate", "dem_primary_share"],
}


def model():
    return make_pipeline(SimpleImputer(), StandardScaler(), Ridge(alpha=10.0))


def validate(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for group in ("black", "white"):
        target = f"relative_{group}_general_turnout"
        for specification, features in SPECS.items():
            for cycle in sorted(panel.cycle.unique()):
                train, test = panel[panel.cycle.ne(cycle)], panel[panel.cycle.eq(cycle)]
                estimate = model().fit(train[features], train[target]).predict(test[features])
                for row, predicted in zip(test.itertuples(index=False), estimate):
                    actual = getattr(row, target)
                    rows.append({"group": group, "specification": specification, "test_cycle": cycle,
                                 "county_key": row.county_key, "actual": actual, "predicted": predicted,
                                 "absolute_error": abs(actual-predicted)})
    detail = pd.DataFrame(rows)
    summary = detail.groupby(["group", "specification"], as_index=False).agg(
        forward_mae=("absolute_error", "mean"),
        worst_cycle_mae=("absolute_error", lambda x: detail.loc[x.index].groupby("test_cycle").absolute_error.mean().max()))
    baseline = summary[summary.specification.eq("registration_only")].set_index("group").forward_mae
    summary["mae_improvement_vs_registration_only"] = summary.apply(
        lambda x: baseline[x.group] - x.forward_mae, axis=1)
    return detail, summary.sort_values(["group", "forward_mae"])


def score_2026(panel: pd.DataFrame) -> pd.DataFrame:
    current = registration(2026).merge(primary_totals(2026), on=["cycle", "county_key"], validate="one_to_one")
    current = add_features(current)
    for group in ("black", "white"):
        target = f"relative_{group}_general_turnout"
        for specification, features in SPECS.items():
            current[f"predicted_{target}__{specification}"] = model().fit(
                panel[features], panel[target]).predict(current[features])
        current[f"primary_increment_{group}"] = (
            current[f"predicted_{target}__party_primary"]
            - current[f"predicted_{target}__registration_only"])
    return current


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = build_panel()
    detail, summary = validate(panel)
    current = score_2026(panel)
    panel.to_csv(OUT / "sos_direct_racial_turnout_panel.csv", index=False)
    detail.to_csv(OUT / "sos_direct_racial_turnout_forward_validation.csv", index=False)
    summary.to_csv(OUT / "sos_direct_racial_turnout_model_summary.csv", index=False)
    current.to_csv(OUT / "2026_sos_direct_racial_turnout_signal.csv", index=False)
    print(summary.to_string(index=False))
    print("\n2026 primary increments")
    print(current[["primary_increment_black", "primary_increment_white"]].describe().to_string())


if __name__ == "__main__":
    main()
