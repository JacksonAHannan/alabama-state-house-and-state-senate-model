"""Create prospective demographics for the reinstated original 2021 SLD plan."""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DEM=ROOT/"data"/"processed"/"demographics"

def main():
    historical=pd.read_csv(DEM/"acs_direct_sld_demographics.csv")
    result=historical[historical.cycle.eq(2022)].copy()
    if len(result)!=140:
        raise ValueError(f"Expected 140 rows on the original plan; found {len(result)}")
    result["cycle"]=2026
    result["feature_method"]="reuse_2022_acs_sld_estimate_original_2021_plan"
    result["geography_validation"]="2025_TIGER_vs_2022_BEF_block_assignment"
    result.to_csv(DEM/"2026_sld_demographics.csv",index=False)
    print(result.groupby("chamber").agg(rows=("district","size"),acs_vintage=("acs_vintage","first"),
        null_nonwhite=("nonwhite_share",lambda x:x.isna().sum()),null_white_college=("white_college_share",lambda x:x.isna().sum())).to_string())

if __name__=="__main__": main()
