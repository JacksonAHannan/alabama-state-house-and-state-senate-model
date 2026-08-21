"""Audit spatial precinct allocations and identify cross-cycle fallback risk."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_geographic_crosswalks import (  # noqa: E402
    WAR,
    block_assignments,
    county_lookup,
    match_precincts,
    normalize_name,
    reference_vtds,
)


def legacy_weights(target: pd.DataFrame, cycle: int, chamber: str) -> pd.DataFrame:
    """Reproduce the retired direct-VTD method for a diagnostic comparison."""
    matches = match_precincts(target[target.cycle.eq(cycle)], reference_vtds(cycle))
    weights = block_assignments(cycle, chamber)
    valid_ids = weights[["county_fips", "vtd"]].drop_duplicates().assign(_valid=True)
    eligible = matches.merge(valid_ids, on=["county_fips", "vtd"], how="left")
    valid = eligible._valid.eq(True)
    direct = eligible[valid].merge(
        weights[["county_fips", "vtd", "district", "allocation_weight"]],
        on=["county_fips", "vtd"], how="left", validate="many_to_many"
    )
    county = weights.groupby(["county_fips", "district"], as_index=False).population.sum()
    county["allocation_weight"] = county.population / county.groupby(
        "county_fips"
    ).population.transform("sum")
    fallback = eligible[~valid].merge(
        county[["county_fips", "district", "allocation_weight"]],
        on="county_fips", how="left", validate="many_to_many"
    )
    result = pd.concat([direct, fallback], ignore_index=True)
    result["chamber"] = chamber
    return result


def weight_l1(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    keys = ["cycle", "chamber", "county_key", "precinct_key", "district"]
    merged = left[keys + ["allocation_weight"]].merge(
        right[keys + ["allocation_weight"]], on=keys, how="outer",
        suffixes=("_new", "_legacy")
    ).fillna({"allocation_weight_new": 0, "allocation_weight_legacy": 0})
    merged["absolute_change"] = (
        merged.allocation_weight_new - merged.allocation_weight_legacy
    ).abs()
    precinct_keys = keys[:-1]
    return (merged.groupby(precinct_keys, as_index=False)
            .absolute_change.sum().rename(columns={"absolute_change": "weight_l1_change"}))


def main() -> None:
    current = pd.read_csv(WAR / "geographic_precinct_district_weights.csv")
    activity = pd.read_csv(WAR / "precinct_district_allocation_weights.csv")
    target = activity[["cycle", "county_key", "precinct_key"]].drop_duplicates()
    lookup = county_lookup()
    county_norm = target.county_key.map(normalize_name).replace({"STCLAIR": "SAINT CLAIR"})
    target["county_fips"] = county_norm.map(lookup)

    rows = []
    for cycle in (2014, 2018, 2022):
        for chamber in ("house", "senate"):
            new = current[(current.cycle.eq(cycle)) & (current.chamber.eq(chamber))]
            legacy = legacy_weights(target, cycle, chamber)
            legacy["cycle"] = cycle
            changes = weight_l1(new, legacy)
            precinct = new.drop_duplicates(["cycle", "chamber", "county_key", "precinct_key"])
            fallback = precinct.allocation_method.str.contains("fallback", regex=False)
            county_batch = precinct.allocation_method.eq("county_level_ballot")
            rows.append({
                "cycle": cycle,
                "chamber": chamber,
                "precincts": len(precinct),
                "direct_or_spatial_precincts": int((~fallback & ~county_batch).sum()),
                "fallback_precincts": int(fallback.sum()),
                "fallback_share": float(fallback.mean()),
                "county_level_ballots": int(county_batch.sum()),
                "mean_weight_l1_change_vs_legacy": float(changes.weight_l1_change.mean()),
                "p95_weight_l1_change_vs_legacy": float(changes.weight_l1_change.quantile(.95)),
                "max_weight_l1_change_vs_legacy": float(changes.weight_l1_change.max()),
                "precincts_l1_change_gt_0_10": int(changes.weight_l1_change.gt(.10).sum()),
            })
    audit = pd.DataFrame(rows)
    audit.to_csv(WAR / "geographic_crosswalk_cycle_audit.csv", index=False)

    all_cycle_parts = []
    historical_path = ROOT / "data" / "processed" / "precinct_history" / "historical_precinct_geometry_audit_summary.csv"
    if historical_path.exists():
        historical = pd.read_csv(historical_path)
        pivot = historical.pivot_table(
            index=["cycle", "chamber"], columns="geometry_confidence",
            values="precinct_district_slices", aggfunc="sum", fill_value=0
        ).reset_index()
        for column in ("high", "medium", "low", "unresolved"):
            if column not in pivot:
                pivot[column] = 0
        pivot["total_units"] = pivot[["high", "medium", "low", "unresolved"]].sum(axis=1)
        pivot["audit_basis"] = "historical_approximate_precinct_district_slices"
        pivot["spatial_or_high_medium"] = pivot["high"] + pivot["medium"]
        pivot["fallback_or_low_unresolved"] = pivot["low"] + pivot["unresolved"]
        pivot["fallback_or_low_unresolved_share"] = (
            pivot.fallback_or_low_unresolved / pivot.total_units.where(pivot.total_units.gt(0))
        )
        all_cycle_parts.append(pivot[[
            "cycle", "chamber", "audit_basis", "total_units",
            "spatial_or_high_medium", "fallback_or_low_unresolved",
            "fallback_or_low_unresolved_share", "high", "medium", "low", "unresolved"
        ]])

    canonical_qa_path = ROOT / "data" / "processed" / "elections" / "canonical_geography_qa.csv"
    if canonical_qa_path.exists():
        canonical = pd.read_csv(canonical_qa_path)
        canonical = canonical[canonical.cycle.eq(2010)].copy()
        canonical["is_direct_or_spatial"] = canonical.allocation_method.str.contains(
            "reported_single_district|split_precinct_block_population|spatial_no_legislative_result",
            regex=True)
        canonical["is_fallback"] = canonical.allocation_method.str.contains("fallback", regex=False)
        canonical["is_county_batch"] = canonical.allocation_method.str.contains("county_level_ballot", regex=False)
        canonical["direct_or_spatial_units"] = np.where(canonical.is_direct_or_spatial,canonical["size"],0)
        canonical["fallback_units"] = np.where(canonical.is_fallback,canonical["size"],0)
        canonical["county_batch_units"] = np.where(canonical.is_county_batch,canonical["size"],0)
        wide = canonical.groupby(["cycle","chamber"],as_index=False).agg(
            total_units=("size","sum"),
            direct_or_spatial_units=("direct_or_spatial_units","sum"),
            fallback_units=("fallback_units","sum"),
            county_level_ballot=("county_batch_units","sum"))
        wide["audit_basis"] = "canonical_precinct_nodes"
        wide["spatial_or_high_medium"] = wide.direct_or_spatial_units
        wide["fallback_or_low_unresolved"] = wide.fallback_units
        wide["fallback_or_low_unresolved_share"] = (
            wide.fallback_units / wide.total_units.where(wide.total_units.gt(0))
        )
        all_cycle_parts.append(wide[[
            "cycle", "chamber", "audit_basis", "total_units",
            "spatial_or_high_medium", "fallback_or_low_unresolved",
            "fallback_or_low_unresolved_share", "county_level_ballot"
        ]])

    modern = audit.rename(columns={
        "precincts": "total_units", "direct_or_spatial_precincts": "spatial_or_high_medium",
        "fallback_precincts": "fallback_or_low_unresolved",
        "fallback_share": "fallback_or_low_unresolved_share",
    })
    modern["audit_basis"] = "election_precinct_nodes"
    all_cycle_parts.append(modern[[
        "cycle", "chamber", "audit_basis", "total_units",
        "spatial_or_high_medium", "fallback_or_low_unresolved",
        "fallback_or_low_unresolved_share"
    ]])
    all_cycle = pd.concat(all_cycle_parts, ignore_index=True, sort=False).sort_values(
        ["cycle", "chamber"]
    )
    all_cycle.to_csv(WAR / "geographic_all_cycle_audit.csv", index=False)

    hd32 = current[(current.cycle.eq(2022)) & (current.chamber.eq("house")) &
                   (current.district.eq(32))]
    report = ROOT / "project_docs" / "audits" / "GEOGRAPHIC_CROSSWALK_AUDIT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    display = audit.copy()
    for column in display.select_dtypes(include=["float"]).columns:
        display[column] = display[column].map(lambda value: f"{value:.3f}")
    headers = list(display.columns)
    table_rows = ["| " + " | ".join(headers) + " |",
                  "| " + " | ".join(["---"] * len(headers)) + " |"]
    table_rows.extend(
        "| " + " | ".join(map(str, row)) + " |"
        for row in display.itertuples(index=False, name=None)
    )
    table = "\n".join(table_rows)
    report.write_text(
        "# Geographic crosswalk audit\n\n"
        "The modern crosswalk now treats the district reported with a precinct's "
        "legislative result as authoritative. Census-block population and official "
        "district assignments are used only for genuine split precincts. Legislative "
        "vote shares are retained only as a labeled split fallback, and county shares "
        "are reserved for non-geographic batches or splits with no usable activity. "
        "The pipeline no longer assumes that election precinct IDs are Census VTD IDs.\n\n"
        "## Modern-cycle method comparison\n\n" + table + "\n\n"
        "`weight_l1_change_vs_legacy` is the total absolute change in a precinct's "
        "district allocation vector. Zero means identical; two is the theoretical "
        "maximum. Older-cycle fallback rows remain explicitly identified and should "
        "not be interpreted as exact precinct geography.\n\n"
        f"The corrected 2022 House crosswalk assigns {hd32.precinct_key.nunique()} "
        "source precincts at least partly to HD-32.\n\n"
        "## Earlier-cycle finding\n\n"
        "The same general risk persists before 2018. The separate historical "
        "precinct audit classifies a large share of 1994-2006 precinct-district "
        "slices as low-confidence or unresolved, and the production historical "
        "CMO still labels those baselines provisional. The 2010 canonical export "
        "now improves matched nodes with the spatial-block method but retains "
        "explicit county fallback for unmatched labels. See "
        "`geographic_all_cycle_audit.csv` for the complete 1994-2022 inventory.\n",
        encoding="utf-8",
    )
    print(audit.to_string(index=False))


if __name__ == "__main__":
    main()
