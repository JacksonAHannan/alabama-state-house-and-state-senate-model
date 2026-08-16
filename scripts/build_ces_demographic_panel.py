"""Build weighted CES national and Alabama demographic election panels.

The cumulative CES guide recommends ``weight`` for within-year estimates.
``weight_post`` is only available in 2012, 2016, 2018, 2020, and 2022, so it
is retained as a sensitivity estimate rather than mixed into the primary
time series. House vote estimates include only Democratic and Republican
post-election respondents.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ces" / "dataverse_files" / "cumulative_2006-2025.dta"
OUT = ROOT / "data" / "processed" / "polling"
ELECTION_YEARS = tuple(range(2006, 2025, 2))


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return np.nan
    return float(np.average(values[valid], weights=weights[valid]))


def effective_n(weights: pd.Series) -> float:
    weights = weights[weights.notna() & (weights > 0)].astype(float)
    if weights.empty:
        return 0.0
    return float(weights.sum() ** 2 / weights.pow(2).sum())


def recode_demographics(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["age_group"] = pd.cut(
        frame.age,
        bins=[17, 29, 44, 64, np.inf],
        labels=["under_30", "30_44", "45_64", "65_plus"],
    ).astype("object")
    frame["education_group"] = frame.educ.map({
        "No HS": "hs_or_less", "High School Graduate": "hs_or_less",
        "Some College": "some_college", "2-Year": "some_college",
        "4-Year": "college_grad", "Post-Grad": "postgrad",
    })
    frame["gender_group"] = frame.gender.str.lower()
    frame["race_group"] = frame.race_h.map({
        "White": "white", "Black": "black", "Hispanic": "hispanic",
        "Asian": "other", "Native American": "other", "Mixed": "other",
        "Other": "other", "Middle Eastern": "other",
    })
    return frame


def aggregate_panel(frame: pd.DataFrame, weight_col: str, weight_method: str) -> pd.DataFrame:
    rows: list[dict] = []
    dimensions = {
        "overall": pd.Series("all", index=frame.index),
        "age": frame.age_group,
        "education": frame.education_group,
        "gender": frame.gender_group,
        "race": frame.race_group,
    }
    for year in ELECTION_YEARS:
        year_frame = frame[frame.year == year]
        for geography, geo_frame in (
            ("alabama", year_frame[year_frame.state == "Alabama"]),
            ("rest_us", year_frame[year_frame.state != "Alabama"]),
            ("us", year_frame),
        ):
            voters = geo_frame[geo_frame.voted_rep_party.isin(["Democratic", "Republican"])].copy()
            voters["dem_vote"] = (voters.voted_rep_party == "Democratic").astype(float)
            for dimension, categories in dimensions.items():
                local_categories = categories.reindex(voters.index)
                for group in sorted(local_categories.dropna().unique()):
                    selected = voters[local_categories == group]
                    weights = selected[weight_col]
                    dem_share = weighted_mean(selected.dem_vote, weights)
                    rows.append({
                        "year": year,
                        "geography": geography,
                        "dimension": dimension,
                        "group": group,
                        "weight_method": weight_method,
                        "unweighted_n": len(selected),
                        "effective_n": effective_n(weights),
                        "weight_sum": weights.dropna().sum(),
                        "dem_two_party_share": dem_share,
                        "dem_two_party_margin": 200 * dem_share - 100 if pd.notna(dem_share) else np.nan,
                    })
    return pd.DataFrame(rows)


def build_panel(frame: pd.DataFrame) -> pd.DataFrame:
    frame = recode_demographics(frame)
    primary = aggregate_panel(frame, "weight", "year_specific_weight")
    sensitivity_source = frame[frame.weight_post.notna()].copy()
    sensitivity = aggregate_panel(sensitivity_source, "weight_post", "post_election_weight")
    sensitivity = sensitivity[sensitivity.unweighted_n > 0]
    return pd.concat([primary, sensitivity], ignore_index=True).sort_values(
        ["weight_method", "year", "geography", "dimension", "group"]
    ).reset_index(drop=True)


def main() -> None:
    columns = [
        "year", "state", "weight", "weight_post", "tookpost",
        "voted_turnout_self", "voted_rep_party", "race_h", "gender", "age", "educ",
    ]
    frame = pd.read_stata(RAW, columns=columns, convert_categoricals=True)
    frame = frame[frame.year.isin(ELECTION_YEARS)]
    panel = build_panel(frame)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "ces_house_vote_demographics.csv"
    panel.to_csv(path, index=False)

    coverage = panel[
        (panel.weight_method == "year_specific_weight")
        & (panel.geography == "alabama")
        & (panel.dimension == "overall")
    ][["year", "unweighted_n", "effective_n", "dem_two_party_margin"]]
    coverage.to_csv(OUT / "ces_alabama_house_vote_coverage.csv", index=False)
    print(coverage.to_string(index=False))
    print(f"Wrote {len(panel):,} panel rows to {path}")


if __name__ == "__main__":
    main()
