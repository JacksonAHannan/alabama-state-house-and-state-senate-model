"""Assemble model-ready WAR features from validated component tables."""

from pathlib import Path
import pandas as pd


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    war = root / "data" / "processed" / "war"
    pres = root / "data" / "processed" / "presidential"
    model = pd.read_csv(war / "district_cycle_model_with_incumbency.csv")
    model["district"] = model.district.astype(int)
    pres_frames = []
    for cycle in (2014, 2018, 2022):
        features = pd.read_csv(pres / f"{cycle}_district_presidential_features.csv")
        features = features.drop(columns=["office"], errors="ignore")
        features["district"] = features.district.astype(int)
        pres_frames.append(features)
    presidential = pd.concat(pres_frames, ignore_index=True, sort=False)
    assembled = model.merge(presidential, on=["cycle", "chamber", "district"], how="left",
                            validate="one_to_one")
    demographics = pd.read_csv(root / "data" / "processed" / "demographics" /
                               "acs_direct_sld_demographics.csv")
    demographics["district"] = demographics.district.astype(int)
    demographics["white_college_method"] = "acs_c15002h_white_nh_bachelors_plus_direct"
    assembled = assembled.merge(demographics, on=["cycle", "chamber", "district"], how="left",
                                validate="one_to_one")
    finance = pd.read_csv(war / "race_finance_features.csv")
    finance["district"] = finance.district.astype(int)
    assembled = assembled.merge(finance, on=["cycle", "chamber", "district"], how="left",
                                validate="one_to_one")
    assembled.to_csv(war / "war_model_features.csv", index=False)
    print(f"Rows: {len(assembled)}")
    print(f"2014 presidential coverage: "
          f"{assembled.loc[assembled.cycle.eq(2014), 'pres_2012_dem_margin'].notna().sum()}/140")
    print(f"2018 presidential coverage: "
          f"{assembled.loc[assembled.cycle.eq(2018), 'pres_2016_dem_margin'].notna().sum()}/140")
    print(f"2022 presidential coverage: "
          f"{assembled.loc[assembled.cycle.eq(2022), 'pres_2020_dem_margin'].notna().sum()}/140")
    print(f"Demographic coverage: {assembled.nonwhite_share.notna().sum()}/420")
    print(f"Complete finance coverage: {assembled.finance_complete.fillna(False).sum()}/420")
    print(f"Unique keys: {not assembled.duplicated(['cycle','chamber','district']).any()}")


if __name__ == "__main__":
    main()
