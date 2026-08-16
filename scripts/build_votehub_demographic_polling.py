"""Validate and pool reviewed demographic crosstabs from VoteHub-linked polls."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "polling" / "votehub_crosstabs_reviewed.csv"
CATALOG = ROOT / "data" / "raw" / "polling" / "votehub_generic_ballot_catalog.json"
OUT = ROOT / "data" / "processed" / "polling"
SILVER = OUT / "votehub_crosstab_documents_with_silver_grades.csv"
REQUIRED = {"poll_id", "dimension", "group", "dem_pct", "rep_pct", "source_url", "reviewed"}
POPULATION_WEIGHT = {"lv": 1.0, "rv": 0.75, "a": 0.5}
ALLOWED_DIMENSIONS = {"race", "education", "race_education", "age", "gender", "overall"}


def validate_reviewed(frame: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Reviewed crosstab file is missing columns: {sorted(missing)}")
    result = frame.copy()
    result["poll_id"] = result.poll_id.astype(str)
    if not result.poll_id.isin(catalog.id.astype(str)).all():
        bad = sorted(result.loc[~result.poll_id.isin(catalog.id.astype(str)), "poll_id"].unique())
        raise ValueError(f"Unknown VoteHub poll IDs: {bad[:10]}")
    if not result.reviewed.astype(str).str.lower().isin({"true", "1", "yes"}).all():
        raise ValueError("Every included crosstab row must be explicitly reviewed")
    if not result.dimension.isin(ALLOWED_DIMENSIONS).all():
        raise ValueError("Unsupported demographic dimension")
    for col in ("dem_pct", "rep_pct"):
        result[col] = pd.to_numeric(result[col], errors="raise")
        if not result[col].between(0, 100).all():
            raise ValueError(f"{col} must be between 0 and 100")
    if (result.dem_pct + result.rep_pct <= 0).any() or (result.dem_pct + result.rep_pct > 100.5).any():
        raise ValueError("Democratic and Republican shares must have a plausible sum")
    keys = ["poll_id", "dimension", "group"]
    if result.duplicated(keys).any():
        raise ValueError(f"Duplicate reviewed cells on {keys}")
    meta = catalog[["id", "pollster", "end_date", "population", "sample_size", "internal", "partisan"]].copy()
    meta = meta.rename(columns={"population": "catalog_population", "sample_size": "catalog_sample_size"})
    meta["id"] = meta.id.astype(str)
    result = result.merge(meta, left_on="poll_id", right_on="id", validate="many_to_one").drop(columns="id")
    result["population"] = result.get("population_override", pd.Series(index=result.index, dtype=object)).fillna(
        result.catalog_population).astype(str).str.lower()
    result["end_date"] = pd.to_datetime(result.end_date)
    result["dem_two_party_share"] = result.dem_pct / (result.dem_pct + result.rep_pct)
    result["dem_margin_two_party"] = 200 * result.dem_two_party_share - 100
    return result


def pool(frame: pd.DataFrame, as_of: pd.Timestamp | None = None, window_days: int = 42,
         half_life_days: float = 21.0) -> pd.DataFrame:
    eligible = frame[(~frame.internal.fillna(False)) & frame.partisan.isna()].copy()
    if eligible.empty:
        return pd.DataFrame()
    as_of = pd.Timestamp(as_of) if as_of is not None else eligible.end_date.max()
    eligible = eligible[eligible.end_date.between(as_of - pd.Timedelta(days=window_days - 1), as_of)]
    # One observation per pollster and cell prevents high-frequency trackers dominating.
    eligible = eligible.sort_values("end_date").drop_duplicates(["pollster", "dimension", "group"], keep="last")
    age = (as_of - eligible.end_date).dt.days.clip(lower=0)
    recency = np.power(0.5, age / half_life_days)
    population = eligible.population.str.lower().map(POPULATION_WEIGHT).fillna(0.5)
    # Cell bases are missing for many otherwise valid published tables. Using
    # precision weights only where available would systematically overpower
    # pollsters that publish bases, so pooling uses recency/population weights.
    precision = pd.Series(1.0, index=eligible.index)
    eligible["weight"] = recency * population * precision
    eligible["cell_base_numeric"] = (pd.to_numeric(eligible["cell_base"], errors="coerce")
                                     if "cell_base" in eligible else np.nan)
    rows = []
    for (dimension, group), part in eligible.groupby(["dimension", "group"]):
        rows.append({"as_of": as_of.date().isoformat(), "dimension": dimension, "group": group,
                     "dem_margin_two_party": np.average(part.dem_margin_two_party, weights=part.weight),
                     "dem_two_party_share": np.average(part.dem_two_party_share, weights=part.weight),
                     "pollsters": part.pollster.nunique(), "polls": part.poll_id.nunique(),
                     "effective_cell_base": part.cell_base_numeric.sum(min_count=1),
                     "first_poll": part.end_date.min().date().isoformat(),
                     "last_poll": part.end_date.max().date().isoformat(),
                     "method": "latest_pollster_cell_recency_population_weighted"})
    return pd.DataFrame(rows)


def main() -> None:
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["poll_id", "dimension", "group", "dem_pct", "rep_pct", "cell_base",
                              "population_override", "source_url", "page_or_table", "extraction_method",
                              "reviewed"]).to_csv(RAW, index=False)
        print(f"Created review template: {RAW}")
        return
    catalog = pd.read_json(CATALOG)
    reviewed = validate_reviewed(pd.read_csv(RAW), catalog)
    pooled = pool(reviewed)
    if SILVER.exists():
        grades = pd.read_csv(SILVER)[["pollster", "silver_grade", "b_plus_or_better"]].drop_duplicates("pollster")
        reviewed = reviewed.merge(grades, on="pollster", how="left", validate="many_to_one")
    else:
        reviewed["b_plus_or_better"] = False
    silver_reviewed = reviewed[reviewed.b_plus_or_better.fillna(False)].copy()
    if "silver_pollster" in pd.read_csv(SILVER, nrows=1).columns:
        canonical = pd.read_csv(SILVER)[["pollster", "silver_pollster"]].drop_duplicates("pollster")
        silver_reviewed = silver_reviewed.merge(canonical, on="pollster", how="left", validate="many_to_one")
        silver_reviewed["pollster"] = silver_reviewed.silver_pollster.fillna(silver_reviewed.pollster)
    silver_pool = pool(silver_reviewed, window_days=180, half_life_days=45)
    OUT.mkdir(parents=True, exist_ok=True)
    reviewed.to_csv(OUT / "votehub_demographic_crosstabs_long.csv", index=False)
    pooled.to_csv(OUT / "votehub_demographic_polling_pooled.csv", index=False)
    silver_pool.to_csv(OUT / "votehub_silver_bplus_demographic_polling_pooled.csv", index=False)
    coverage = reviewed.groupby(["dimension", "group"]).agg(
        polls=("poll_id", "nunique"), pollsters=("pollster", "nunique"),
        first_poll=("end_date", "min"), last_poll=("end_date", "max")).reset_index()
    coverage.to_csv(OUT / "votehub_demographic_crosstab_coverage.csv", index=False)
    print(pooled.to_string(index=False))


if __name__ == "__main__":
    main()
