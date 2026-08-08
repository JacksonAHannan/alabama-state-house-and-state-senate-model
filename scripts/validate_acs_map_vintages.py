"""Validate ACS legislative-district coverage against expected Alabama plans."""

from pathlib import Path
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    acs = pd.read_csv(ROOT / "data" / "processed" / "demographics" /
                      "acs_direct_sld_demographics.csv")
    rows = []
    for cycle in (2014, 2018, 2022):
        for chamber, expected in (("house", 105), ("senate", 35)):
            part = acs[(acs.cycle == cycle) & (acs.chamber == chamber)]
            rows.append({
                "cycle": cycle, "chamber": chamber, "expected_districts": expected,
                "observed_districts": part.district.nunique(),
                "district_number_complete": set(part.district.astype(int)) == set(range(1, expected + 1)),
                "state_population_sum": part.B03002_001E.sum(),
                "district_population_cv": part.B03002_001E.std() / part.B03002_001E.mean(),
            })
    qa = pd.DataFrame(rows)
    plan_checks = []
    for chamber, filename in (("house", "al_sldl_2021_to_2023.zip"),
                              ("senate", "al_sldu_2021_to_2023.zip")):
        plan = gpd.read_file(f"zip://{(ROOT / 'Results and Shapefiles' / filename).as_posix()}",
                             ignore_geometry=True)
        plan["district"] = pd.to_numeric(plan.DISTRICT)
        part = acs[(acs.cycle == 2022) & (acs.chamber == chamber)]
        joined = part.merge(plan[["district", "POPULATION"]], on="district", validate="one_to_one")
        ratio = joined.B03002_001E / joined.POPULATION
        plan_checks.append({
            "cycle": 2022, "chamber": chamber,
            "acs_plan_population_correlation": joined.B03002_001E.corr(joined.POPULATION),
            "acs_plan_population_ratio_median": ratio.median(),
            "acs_plan_population_ratio_min": ratio.min(),
            "acs_plan_population_ratio_max": ratio.max(),
        })
    out = ROOT / "data" / "processed" / "demographics"
    qa.to_csv(out / "acs_map_vintage_qa.csv", index=False)
    pd.DataFrame(plan_checks).to_csv(out / "acs_2022_plan_population_qa.csv", index=False)
    print(qa.to_string(index=False))
    print(pd.DataFrame(plan_checks).to_string(index=False))


if __name__ == "__main__":
    main()
