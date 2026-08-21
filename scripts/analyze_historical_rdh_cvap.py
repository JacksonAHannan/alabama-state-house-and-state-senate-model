"""Build cycle-matched RDH CVAP features and test forecast accuracy."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_geographic_crosswalks import block_population, read_member
from run_forecast_experiment_tournament import ALL, prepare_data, prepare_prospective_data

RAW = ROOT / "data" / "raw" / "rdh"
CENSUS = ROOT / "data" / "raw" / "census"
DEM = ROOT / "data" / "processed" / "demographics"
VALID = ROOT / "data" / "processed" / "elections" / "validation"


def csv_from_zip(name: str) -> pd.DataFrame:
    with zipfile.ZipFile(RAW / name) as bundle:
        member = next(item for item in bundle.namelist() if item.lower().endswith(".csv"))
        with bundle.open(member) as stream:
            return pd.read_csv(stream, low_memory=False)


def block_district(cycle: int, chamber: str) -> pd.DataFrame:
    entity = "SLDL" if chamber == "house" else "SLDU"
    baf = CENSUS / "BlockAssign2010_ST01_AL.zip"
    if cycle == 2010:
        sld = read_member(baf, f"_{entity}.txt", ",")
    else:
        post = CENSUS / ("sldl_post2010.zip" if chamber == "house" else "sldu_post2010.zip")
        sld = read_member(post, f"01_AL_{entity}.txt", ",")
    sld = sld.rename(columns={"BLOCKID": "blockid", "DISTRICT": "district"})
    pop = block_population(2010)
    out = sld[["blockid", "district"]].merge(pop, on="blockid", validate="one_to_one")
    out["district"] = pd.to_numeric(out.district).astype(int)
    out["block_group"] = out.blockid.str[:12]
    out["block_count"] = 1
    out["bg_population"] = out.groupby("block_group").population.transform("sum")
    out["bg_blocks"] = out.groupby("block_group").block_count.transform("sum")
    out["weight"] = np.where(out.bg_population.gt(0), out.population / out.bg_population,
                              out.block_count / out.bg_blocks)
    return out.groupby(["district", "block_group"], as_index=False).weight.sum()


def allocated_cvap(cycle: int, archive: str) -> pd.DataFrame:
    x = csv_from_zip(archive)
    x["block_group"] = x.GEOID.astype(str).str.zfill(12)
    suffix = str(cycle)[-2:]
    values = {"total": f"CVAP_TOT{suffix}", "white": f"CVAP_WHT{suffix}",
              "black": f"CVAP_BLK{suffix}", "hispanic": f"CVAP_HSP{suffix}"}
    outputs = []
    for chamber in ["house", "senate"]:
        links = block_district(cycle, chamber)
        joined = links.merge(x[["block_group", *values.values()]], on="block_group", how="left", validate="many_to_one")
        for column in values.values():
            joined[column] *= joined.weight
        out = joined.groupby("district", as_index=False)[list(values.values())].sum()
        out = out.rename(columns={value: key for key, value in values.items()})
        out["chamber"] = chamber
        outputs.append(out)
    result = pd.concat(outputs, ignore_index=True)
    result["cycle"] = cycle
    result["cvap_method"] = "native_2010_block_group_population_allocation"
    return result


def direct_cvap(cycle: int) -> pd.DataFrame:
    suffix = str(cycle)[-2:]
    outputs = []
    names = {
        2018: {"house": "al_cvap_2018_sldl (1).zip", "senate": "al_cvap_2018_sldu (1).zip"},
        2022: {"house": "al_cvap_2022_sldl.zip", "senate": "al_cvap_2022_sldu.zip"},
    }
    for chamber, archive in names[cycle].items():
        x = csv_from_zip(archive)
        district_field = "SLDL" if chamber == "house" else "SLDU"
        x["district"] = pd.to_numeric(x[district_field]).astype(int)
        black = f"CVAP_BLK{suffix}" if f"CVAP_BLK{suffix}" in x else f"CVAP_BLA{suffix}"
        out = x[["district", f"CVAP_TOT{suffix}", f"CVAP_WHT{suffix}", black,
                 f"CVAP_HSP{suffix}", "CVAPTOTMOE"]].copy()
        out.columns = ["district", "total", "white", "black", "hispanic", "total_moe"]
        out["chamber"] = chamber
        outputs.append(out)
    result = pd.concat(outputs, ignore_index=True)
    result["cycle"] = cycle
    result["cvap_method"] = "direct_RDH_Census_SLD_tabulation"
    return result


def features() -> pd.DataFrame:
    parts = [allocated_cvap(2010, "al_cvap_2010_bg (1).zip"),
             allocated_cvap(2014, "al_cvap_2014_bg (1).zip"),
             direct_cvap(2018), direct_cvap(2022)]
    x = pd.concat(parts, ignore_index=True)
    x["cvap_nonwhite_share"] = 1 - x.white / x.total
    x["cvap_black_share"] = x.black / x.total
    x["cvap_hispanic_share"] = x.hispanic / x.total
    x["cvap_other_nonwhite_share"] = x.cvap_nonwhite_share - x.cvap_black_share - x.cvap_hispanic_share
    x["cvap_moe_ratio"] = x.get("total_moe", pd.Series(index=x.index, dtype=float)) / x.total
    return x


def validate(x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    h = prepare_data()
    data = h.merge(x, on=["cycle", "chamber", "district"], how="left", validate="one_to_one")
    data["ramp_swing"] = data.national_environment_weight * data.national_environment_swing
    data["total_x_swing"] = data.nonwhite_share * data.ramp_swing
    data["cvap_x_swing"] = data.cvap_nonwhite_share * data.ramp_swing
    data["cvap_black_x_swing"] = data.cvap_black_share * data.ramp_swing
    data["cvap_hispanic_x_swing"] = data.cvap_hispanic_share * data.ramp_swing
    data["cvap_other_x_swing"] = data.cvap_other_nonwhite_share * data.ramp_swing
    data["cvap_available"] = data.cvap_nonwhite_share.notna().astype(int)
    data["hybrid_nonwhite_share"] = data.cvap_nonwhite_share.fillna(data.nonwhite_share)
    data["hybrid_x_swing"] = data.hybrid_nonwhite_share * data.ramp_swing
    data["senate_i"] = data.chamber.eq("senate").astype(int)
    data["outcome"] = data.legislative_dem_margin - data.national_environment_ramp_baseline
    data = data.dropna(subset=["legislative_dem_margin", "national_environment_ramp_baseline", "outcome"]).copy()
    specs = {
        "ramp": ([], 20, 0),
        "ramp_total_nonwhite": (["nonwhite_share", "total_x_swing"], 20, 1),
        "ramp_total_nonwhite_80_20": (["nonwhite_share", "total_x_swing"], 20, .2),
        "ramp_cvap_nonwhite": (["cvap_nonwhite_share", "cvap_x_swing"], 20, 1),
        "ramp_cvap_nonwhite_80_20": (["cvap_nonwhite_share", "cvap_x_swing"], 20, .2),
        "ramp_cvap_nonwhite_heavy_shrink": (["cvap_nonwhite_share", "cvap_x_swing"], 100, .2),
        "ramp_total_interaction_only": (["total_x_swing"], 20, 1),
        "ramp_cvap_interaction_only": (["cvap_x_swing"], 20, 1),
        "ramp_cvap_interaction_80_20": (["cvap_x_swing"], 20, .2),
        "ramp_total_demographics": (["nonwhite_share", "white_college_share", "total_x_swing"], 20, 1),
        "ramp_total_demographics_80_20": (["nonwhite_share", "white_college_share", "total_x_swing"], 20, .2),
        "ramp_cvap_demographics": (["cvap_nonwhite_share", "white_college_share", "cvap_x_swing"], 20, 1),
        "ramp_cvap_demographics_80_20": (["cvap_nonwhite_share", "white_college_share", "cvap_x_swing"], 20, .2),
        "ramp_cvap_components": (["cvap_black_share", "cvap_hispanic_share", "cvap_other_nonwhite_share",
                                  "cvap_black_x_swing", "cvap_hispanic_x_swing", "cvap_other_x_swing"], 20, 1),
        "ramp_cvap_components_80_20": (["cvap_black_share", "cvap_hispanic_share", "cvap_other_nonwhite_share",
                                        "cvap_black_x_swing", "cvap_hispanic_x_swing", "cvap_other_x_swing"], 20, .2),
        "public_all_total_80_20": (ALL + ["senate_i"], 20, .2),
        "public_all_cvap_80_20": ([{"nonwhite_share": "cvap_nonwhite_share",
                                     "ramp_x_nonwhite": "cvap_x_swing"}.get(c, c) for c in ALL] + ["senate_i"], 20, .2),
        "public_all_hybrid_cvap_80_20": ([{"nonwhite_share": "hybrid_nonwhite_share",
                                            "ramp_x_nonwhite": "hybrid_x_swing"}.get(c, c) for c in ALL]
                                          + ["cvap_available", "senate_i"], 20, .2),
    }
    rows = []
    prediction_rows = []
    for test_cycle in [2014, 2018, 2022]:
        train, test = data[data.cycle < test_cycle], data[data.cycle == test_cycle]
        for name, (columns, alpha, scale) in specs.items():
            # Copy: in-place scenario additions must never mutate the shared
            # baseline column used by subsequent specifications.
            pred = test.national_environment_ramp_baseline.to_numpy(copy=True)
            if columns:
                model = Pipeline([("impute", SimpleImputer(strategy="median")),
                                  ("scale", StandardScaler()), ("ridge", Ridge(alpha=alpha))])
                weights = train.cycle.map(lambda c: 1 / train.cycle.value_counts().loc[c])
                model.fit(train[columns], train.outcome, ridge__sample_weight=weights)
                pred += scale * model.predict(test[columns])
            rows.append({"test_cycle": test_cycle, "specification": name, "races": len(test),
                         "mae": mean_absolute_error(test.legislative_dem_margin, pred)})
            for race, prediction in zip(test.itertuples(), pred):
                prediction_rows.append({"test_cycle": test_cycle, "specification": name,
                                        "chamber": race.chamber, "district": race.district,
                                        "actual": race.legislative_dem_margin, "prediction": prediction,
                                        "absolute_error": abs(race.legislative_dem_margin - prediction)})
    detail = pd.DataFrame(rows)
    summary = (detail.groupby("specification", as_index=False)
               .agg(mean_mae=("mae", "mean"), post2016_mean_mae=("mae", lambda z: z.iloc[-2:].mean()),
                    latest_mae=("mae", "last"))).sort_values("mean_mae")
    return data, detail.merge(summary, on="specification"), pd.DataFrame(prediction_rows)


def prospective_comparison(train: pd.DataFrame) -> pd.DataFrame:
    test = prepare_prospective_data()
    cvap = pd.read_csv(DEM / "rdh_2024_sld_cvap.csv")
    test = test.merge(cvap[["chamber", "district", "cvap_nonwhite_share"]],
                      on=["chamber", "district"], validate="one_to_one")
    test["senate_i"] = test.chamber.eq("senate").astype(int)
    test["cvap_available"] = 1
    test["hybrid_nonwhite_share"] = test.cvap_nonwhite_share
    test["hybrid_x_swing"] = test.hybrid_nonwhite_share * test.ramp_swing
    total_cols = ALL + ["senate_i"]
    hybrid_cols = ([{"nonwhite_share": "hybrid_nonwhite_share", "ramp_x_nonwhite": "hybrid_x_swing"}.get(c, c)
                    for c in ALL] + ["cvap_available", "senate_i"])
    rows = test[["chamber", "district", "ramp_baseline"]].copy()
    target = train.legislative_dem_margin - train.national_environment_ramp_baseline
    weights = train.cycle.map(lambda c: 1 / train.cycle.value_counts().loc[c])
    for name, columns in [("total_population", total_cols), ("hybrid_cvap", hybrid_cols)]:
        model = Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler()), ("ridge", Ridge(alpha=20))])
        model.fit(train[columns], target, ridge__sample_weight=weights)
        rows[f"{name}_margin"] = test.ramp_baseline + .2 * model.predict(test[columns])
    rows["hybrid_minus_total"] = rows.hybrid_cvap_margin - rows.total_population_margin
    rows["winner_changed"] = ((rows.hybrid_cvap_margin >= 0) != (rows.total_population_margin >= 0))
    return rows


def main() -> None:
    x = features()
    data, validation, predictions = validate(x)
    prospective = prospective_comparison(data)
    x.to_csv(DEM / "rdh_historical_sld_cvap_2010_2022.csv", index=False)
    data.to_csv(VALID / "rdh_historical_cvap_model_detail.csv", index=False)
    validation.to_csv(VALID / "rdh_historical_cvap_forward_validation.csv", index=False)
    predictions.to_csv(VALID / "rdh_historical_cvap_forward_predictions.csv", index=False)
    prospective.to_csv(VALID / "rdh_2026_hybrid_cvap_forecast_comparison.csv", index=False)
    print(validation[["test_cycle", "specification", "mae"]].pivot(
        index="test_cycle", columns="specification", values="mae").to_string())
    print("\nSummary")
    print(validation[["specification", "mean_mae", "post2016_mean_mae", "latest_mae"]]
          .drop_duplicates().sort_values("mean_mae").to_string(index=False))


if __name__ == "__main__":
    main()
