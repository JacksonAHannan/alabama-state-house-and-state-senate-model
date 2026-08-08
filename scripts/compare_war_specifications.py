"""Compare nested WAR specifications under random- and cycle-holdout CV."""

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]


def prepared() -> pd.DataFrame:
    x = pd.read_csv(ROOT / "data" / "processed" / "war" / "war_model_features.csv")
    x = x[x.war_eligible].copy().reset_index(drop=True)
    x["incumbency_advantage_d"] = x.dem_incumbent.astype(int) - x.rep_incumbent.astype(int)
    x["dem_incumbent_i"] = x.dem_incumbent.astype(int)
    x["rep_incumbent_i"] = x.rep_incumbent.astype(int)
    x["prior_pres_dem_margin"] = np.select(
        [x.cycle.eq(2014), x.cycle.eq(2018), x.cycle.eq(2022)],
        [x.pres_2012_dem_margin, x.pres_2016_dem_margin, x.pres_2020_dem_margin])
    x["prior_pres_swing"] = np.select(
        [x.cycle.eq(2018), x.cycle.eq(2022)],
        [x.pres_swing_2012_2016, x.pres_swing_2016_2020], default=np.nan)
    x["pres_trend_available"] = x.cycle.ne(2014).astype(int)
    x["finance_complete"] = x.finance_complete.fillna(False).astype(int)
    return x


def evaluate(name: str, data: pd.DataFrame, numeric: list[str], categorical: list[str]) -> dict:
    prep = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                           ("scale", StandardScaler())]), numeric),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), categorical)])
    pipe = Pipeline([("prep", prep), ("model", Ridge())])
    estimator = GridSearchCV(pipe, {"model__alpha": [0.1, 0.3, 1, 3, 10, 30]},
                             scoring="neg_mean_absolute_error",
                             cv=KFold(5, shuffle=True, random_state=20260806))
    features = numeric + categorical
    y = data.raw_overperformance
    random_pred = cross_val_predict(estimator, data[features], y,
                                    cv=KFold(10, shuffle=True, random_state=20260805))
    group_pred = cross_val_predict(estimator, data[features], y,
                                   cv=GroupKFold(data.cycle.nunique()), groups=data.cycle)
    return {"specification": name, "races": len(data),
            "random_mae": mean_absolute_error(y, random_pred),
            "random_rmse": mean_squared_error(y, random_pred) ** 0.5,
            "random_r2": r2_score(y, random_pred),
            "cycle_holdout_mae": mean_absolute_error(y, group_pred),
            "cycle_holdout_rmse": mean_squared_error(y, group_pred) ** 0.5,
            "cycle_holdout_r2": r2_score(y, group_pred)}


def main() -> None:
    x = prepared()
    base = ["dem_incumbent_i", "rep_incumbent_i", "prior_pres_dem_margin"]
    rows = [
        evaluate("core", x, base, ["cycle", "chamber"]),
        evaluate("core_demographics", x, base + ["nonwhite_share", "white_college_share"],
                 ["cycle", "chamber"]),
        evaluate("core_demographics_spending", x, base + ["nonwhite_share", "white_college_share",
                 "log_spending_ratio_d_to_r", "finance_complete"], ["cycle", "chamber"]),
        evaluate("full_with_presidential_trend", x, base + ["nonwhite_share", "white_college_share",
                 "log_spending_ratio_d_to_r", "finance_complete", "prior_pres_swing",
                 "pres_trend_available"], ["cycle", "chamber"]),
    ]
    contemporary = x[x.cycle.isin([2018, 2022])].copy()
    rows.append(evaluate("contemporary_2018_2022_full", contemporary,
                         base + ["nonwhite_share", "white_college_share",
                                 "log_spending_ratio_d_to_r", "finance_complete",
                                 "prior_pres_swing"], ["chamber"]))
    result = pd.DataFrame(rows)
    result.to_csv(ROOT / "data" / "processed" / "war" / "war_specification_comparison.csv",
                  index=False)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
