"""Compare contextual white-voting effects across major Alabama regions."""
from __future__ import annotations

from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_white_area_voting_effects import _design, _wls_hc1, precinct_sources  # noqa: E402

WAR = ROOT / "data" / "processed" / "war"
DOC = ROOT / "project_docs" / "model" / "REGIONAL_WHITE_VOTING_EFFECTS.md"
PLACE = ROOT / "data" / "raw" / "census" / "tl_2024_01_place.zip"
REGIONS = [
    "Huntsville city", "Madison city", "Madison County remainder",
    "Birmingham city", "Birmingham educated suburbs", "Shelby County remainder",
    "Auburn city", "Tuscaloosa city", "Mobile city", "Black Belt",
]
BLACK_BELT_FIPS = {"011", "023", "047", "063", "065", "085", "087", "091", "105", "107", "119", "131"}


def label_regions() -> pd.DataFrame:
    places = gpd.read_file(f"zip://{PLACE.resolve()}")[["NAME", "geometry"]].to_crs(5070)
    rows = []
    for cycle, (geo, county_col, _, _) in precinct_sources().items():
        geo = geo.reset_index(names="precinct_id").to_crs(5070)
        points = geo[["precinct_id", county_col, "geometry"]].copy()
        points.geometry = points.geometry.representative_point()
        joined = gpd.sjoin(points, places, how="left", predicate="within").drop_duplicates("precinct_id")
        county = joined[county_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(3)
        place = joined.NAME.fillna("")
        region = np.full(len(joined), "Other Alabama", dtype=object)
        region[place.eq("Huntsville")] = "Huntsville city"
        region[place.eq("Madison")] = "Madison city"
        region[(county == "089") & (region == "Other Alabama")] = "Madison County remainder"
        region[place.eq("Birmingham")] = "Birmingham city"
        region[place.isin(["Homewood", "Hoover", "Mountain Brook", "Vestavia Hills"])] = "Birmingham educated suburbs"
        region[(county == "117") & (region == "Other Alabama")] = "Shelby County remainder"
        region[place.eq("Auburn")] = "Auburn city"
        region[place.eq("Tuscaloosa")] = "Tuscaloosa city"
        region[place.eq("Mobile")] = "Mobile city"
        region[county.isin(BLACK_BELT_FIPS)] = "Black Belt"
        rows.append(pd.DataFrame({"cycle": cycle, "precinct_id": joined.precinct_id,
                                  "county_fips": county, "place_name": place, "region": region}))
    return pd.concat(rows, ignore_index=True)


def bh_adjust(p: pd.Series) -> pd.Series:
    order = np.argsort(p.to_numpy()); ranked = p.to_numpy()[order]
    adjusted = np.minimum.accumulate((ranked * len(p) / np.arange(1, len(p)+1))[::-1])[::-1]
    result = np.empty(len(p)); result[order] = np.clip(adjusted, 0, 1)
    return pd.Series(result, index=p.index)


def estimates(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for region in REGIONS:
        x = panel.copy(); x["area"] = x.region.eq(region).astype(int)
        x["area_x_college"] = x.area * x.white_nh_college_share
        x["area_x_noncollege"] = x.area * x.white_nh_noncollege_share
        x["area_x_time"] = x.area * x.time
        x["area_x_college_time"] = x.area_x_college * x.time
        base, names = _design(x, [])
        extra_names = ["area", "area_x_college", "area_x_noncollege", "area_x_time", "area_x_college_time"]
        design = np.column_stack([base, *(x[c].to_numpy(float) for c in extra_names)])
        beta, se, r2 = _wls_hc1(design, x.dem_share.to_numpy(), x.two_party_votes.to_numpy())
        all_names = names + extra_names
        for term in extra_names:
            i = all_names.index(term); z = beta[i]/se[i]
            rows.append({"region": region, "term": term, "estimate": beta[i], "std_error": se[i],
                         "p_value": 2*norm.sf(abs(z)), "ci_low": beta[i]-1.96*se[i],
                         "ci_high": beta[i]+1.96*se[i], "r_squared": r2,
                         "precincts": int(x.loc[x.area.eq(1), ["cycle", "precinct_id"]].drop_duplicates().shape[0])})
    result = pd.DataFrame(rows)
    result["p_value_bh"] = result.groupby("term", group_keys=False).p_value.transform(bh_adjust)
    return result


def cycle_trends(panel: pd.DataFrame) -> pd.DataFrame:
    base, _ = _design(panel, [])
    beta, _, _ = _wls_hc1(base, panel.dem_share.to_numpy(), panel.two_party_votes.to_numpy())
    x = panel.copy(); x["residual"] = x.dem_share - base @ beta
    rows=[]
    for (cycle, region), g in x[x.region.ne("Other Alabama")].groupby(["cycle", "region"]):
        rows.append({"cycle": cycle, "region": region, "precincts": len(g),
                     "two_party_votes": g.two_party_votes.sum(),
                     "adjusted_dem_residual": np.average(g.residual, weights=g.two_party_votes),
                     "white_college_share": np.average(g.white_nh_college_share, weights=g.adult25_total)})
    return pd.DataFrame(rows)


def black_belt_subgroups(panel: pd.DataFrame) -> pd.DataFrame:
    base, _ = _design(panel, [])
    beta, _, _ = _wls_hc1(base, panel.dem_share.to_numpy(), panel.two_party_votes.to_numpy())
    x=panel[panel.region.eq("Black Belt")].copy(); x["residual"]=x.dem_share-(base@beta)[panel.region.eq("Black Belt")]
    white=x.white_nh_college_share+x.white_nh_noncollege_share
    black=x.black_college_share+x.black_noncollege_share
    x["subgroup"]=np.select([black.ge(.50),white.ge(.50)],
                             ["majority-Black precinct","majority-white precinct"],default="racially mixed precinct")
    rows=[]
    for (cycle,subgroup),g in x.groupby(["cycle","subgroup"]):
        rows.append({"cycle":cycle,"subgroup":subgroup,"precincts":len(g),"two_party_votes":g.two_party_votes.sum(),
                     "adjusted_dem_residual":np.average(g.residual,weights=g.two_party_votes),
                     "white_college_share":np.average(g.white_nh_college_share,weights=g.adult25_total),
                     "black_share":np.average(g.black_college_share+g.black_noncollege_share,weights=g.adult25_total)})
    return pd.DataFrame(rows)


def forward_test(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = panel.copy()
    x["statewide_dem_share"] = x.groupby("cycle").apply(
        lambda g: np.average(g.dem_share, weights=g.two_party_votes), include_groups=False
    ).reindex(x.cycle).to_numpy()
    x["relative_dem_share"] = x.dem_share - x.statewide_dem_share
    region_cols=[]
    for region in REGIONS:
        key = "reg_" + str(REGIONS.index(region))
        x[key] = x.region.eq(region).astype(float)
        x[key+"_college"] = x[key] * x.white_nh_college_share
        region_cols += [key, key+"_college"]
    detail=[]
    for test_cycle in [2020, 2022, 2024]:
        train=x[x.cycle < test_cycle]; test=x[x.cycle == test_cycle]
        base_cols=["white_nh_noncollege_share", "white_nh_college_share", "black_noncollege_share",
                   "black_college_share", "other_college_share"]
        for model, cols in [("demographics_only", base_cols), ("demographics_plus_regions", base_cols+region_cols)]:
            xt=np.column_stack([np.ones(len(train)), train[cols]]); xv=np.column_stack([np.ones(len(test)), test[cols]])
            # Modest ridge stabilizes sparse regional interactions; intercept is unpenalized.
            penalty=np.eye(xt.shape[1])*5; penalty[0,0]=0
            sw=np.sqrt(train.two_party_votes.to_numpy()/train.two_party_votes.mean())
            coef=np.linalg.solve((xt*sw[:,None]).T@(xt*sw[:,None])+penalty, (xt*sw[:,None]).T@(train.relative_dem_share.to_numpy()*sw))
            pred=xv@coef; err=np.abs(test.relative_dem_share.to_numpy()-pred)
            for row, prediction, error in zip(test.itertuples(), pred, err):
                detail.append({"test_cycle":test_cycle,"model":model,"precinct_id":row.precinct_id,
                               "region":row.region,"actual_relative_dem_share":row.relative_dem_share,
                               "prediction":prediction,"absolute_error":error,"two_party_votes":row.two_party_votes})
    detail=pd.DataFrame(detail)
    summary=[]
    for (cycle,model),g in detail.groupby(["test_cycle","model"]):
        summary.append({"test_cycle":cycle,"model":model,"scope":"statewide",
                        "mae":np.average(g.absolute_error,weights=g.two_party_votes),"votes":g.two_party_votes.sum()})
        regional=g[g.region.ne("Other Alabama")]
        summary.append({"test_cycle":cycle,"model":model,"scope":"named_regions",
                        "mae":np.average(regional.absolute_error,weights=regional.two_party_votes),"votes":regional.two_party_votes.sum()})
    return detail, pd.DataFrame(summary)


def report(est: pd.DataFrame, high_white_trends: pd.DataFrame, trends: pd.DataFrame,
           black_belt: pd.DataFrame, forward: pd.DataFrame) -> None:
    average=trends.groupby("region",as_index=False).apply(
        lambda g: pd.Series({"estimate":np.average(g.adjusted_dem_residual,weights=g.two_party_votes)}),
        include_groups=False).reset_index(drop=True).sort_values("estimate",ascending=False)
    college=est[est.term.eq("area_x_college")].sort_values("estimate",ascending=False)
    hw_average=high_white_trends.groupby("region",as_index=False).apply(
        lambda g: pd.Series({"estimate":np.average(g.adjusted_dem_residual,weights=g.two_party_votes)}),
        include_groups=False).reset_index(drop=True).sort_values("estimate",ascending=False)
    def table(frame, value="estimate"):
        has_p="p_value_bh" in frame
        return (["| Region | Estimate |"+(" Adjusted p |" if has_p else ""), "|---|---:|"+("---:|" if has_p else "")] + [
            f"| {r.region} | {100*getattr(r,value):+.2f} |"+(f" {r.p_value_bh:.3f} |" if has_p else "") for r in frame.itertuples()])
    pivot=forward.pivot(index=["test_cycle","scope"],columns="model",values="mae").reset_index()
    pivot["gain"] = pivot.demographics_only-pivot.demographics_plus_regions
    ftable=["| Cycle | Scope | Base MAE | Regional MAE | Gain |","|---:|---|---:|---:|---:|"]+[
        f"| {int(r.test_cycle)} | {r.scope} | {r.demographics_only:.4f} | {r.demographics_plus_regions:.4f} | {r.gain:+.4f} |" for r in pivot.itertuples()]
    bbtable=["| Cycle | Precinct type | Precincts | Adjusted residual |","|---:|---|---:|---:|"]+[
        f"| {int(r.cycle)} | {r.subgroup} | {int(r.precincts)} | {100*r.adjusted_dem_residual:+.2f} |" for r in black_belt.itertuples()]
    text=["# Regional white-voting contextual effects","",
          "This aggregate precinct analysis compares incorporated-city and residual-county areas using 2024 Census TIGER/Line place boundaries. It covers the 2018 and 2022 governor elections and the 2020 and 2024 presidential elections. Coefficients are contextual effects, not individual white-voter estimates.","",
          "## Average adjusted regional residuals","",*table(average),"","## White-college composition interactions","",*table(college),"",
          "The interaction coefficients are slopes rather than average regional effects and can be unstable where a region has a narrow education range.","",
          "## High-white-precinct sensitivity","","These are average adjusted residuals only where non-Hispanic white adults are at least 70% of the modeled adult population, reducing reliance on ecological assumptions about Black voting.","",*table(hw_average),"",
          "## Black Belt composition check","","The Black Belt uses the traditional 12-county definition: Bullock, Choctaw, Dallas, Greene, Hale, Lowndes, Macon, Marengo, Perry, Pickens, Sumter, and Wilcox. Precinct subgroups are based on modeled adult race composition.","",*bbtable,"",
          "## Expanding-cycle prediction test","",*ftable,"",
          "Positive gain means regional features reduced held-out MAE. Statewide election means are removed in each cycle, so the test evaluates relative geographic prediction rather than leaking the statewide environment.","",
          "## Limitations","","Precincts are assigned by representative point; split-place precincts are not fractionally allocated. HC1 uncertainty treats precincts as observations and can overstate certainty for a region represented by one place. Results are multiple-test corrected within each coefficient family. Mixed gubernatorial and presidential cycles limit the time-trend interpretation."]
    DOC.write_text("\n".join(text)+"\n",encoding="utf-8")


def main() -> None:
    panel=pd.read_csv(WAR/"white_area_voting_precinct_panel.csv")
    panel["county_fips"] = panel.county_fips.astype(str).str.zfill(3)
    labels=label_regions(); panel=panel.merge(labels,on=["cycle","precinct_id","county_fips"],validate="one_to_one")
    est=estimates(panel)
    white_share=panel.white_nh_college_share+panel.white_nh_noncollege_share
    high_white_panel=panel[white_share.ge(.70)].copy()
    high_white=estimates(high_white_panel)
    high_white_trends=cycle_trends(high_white_panel)
    trends=cycle_trends(panel); black_belt=black_belt_subgroups(panel); detail,summary=forward_test(panel)
    panel.to_csv(WAR/"regional_white_voting_precinct_panel.csv",index=False)
    est.to_csv(WAR/"regional_white_voting_model_estimates.csv",index=False)
    high_white.to_csv(WAR/"regional_white_voting_high_white_estimates.csv",index=False)
    high_white_trends.to_csv(WAR/"regional_white_voting_high_white_cycle_trends.csv",index=False)
    trends.to_csv(WAR/"regional_white_voting_cycle_trends.csv",index=False)
    black_belt.to_csv(WAR/"regional_white_voting_black_belt_subgroups.csv",index=False)
    detail.to_csv(WAR/"regional_white_voting_forward_predictions.csv",index=False)
    summary.to_csv(WAR/"regional_white_voting_forward_summary.csv",index=False)
    report(est,high_white_trends,trends,black_belt,summary)
    print(est[est.term.isin(["area","area_x_college","area_x_time"])].to_string(index=False))
    print("\n",summary.to_string(index=False))


if __name__ == "__main__": main()
