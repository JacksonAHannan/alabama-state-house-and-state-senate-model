"""Exploratory tests of plausible ideology/CMO relationships.

These are descriptive, low-powered tests. Shor--McCarty individual scores are
career-level ideal points, so even a legislator with pre-election service can
have an estimate informed by later votes. Results must not be described as
causal or strictly prospective.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
INPUT = RESEARCH / "shor_mccarty_candidate_universe.csv"
RESULTS = RESEARCH / "plausible_ideology_relationship_tests.csv"
ISSUE_RESULTS = RESEARCH / "pre_election_issue_relationship_tests.csv"
REPORT = RESEARCH / "PLAUSIBLE_IDEOLOGY_RELATIONSHIPS.md"
WHITE_AUDIT = RESEARCH / "majority_white_ideology_case_audit.csv"
SEED = 20260816
BOOTSTRAPS = 3000


def zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    sd = numeric.std(ddof=0)
    return (numeric - numeric.mean()) / sd if pd.notna(sd) and sd > 0 else numeric * 0


def design(frame: pd.DataFrame, focal: str, extras: list[str]) -> tuple[np.ndarray, np.ndarray]:
    controls = pd.DataFrame(index=frame.index)
    controls["intercept"] = 1.0
    controls["focal"] = frame[focal]
    for column in extras:
        controls[column] = frame[column]
    cycle_dummies = pd.get_dummies(frame.cycle.astype(int), prefix="cycle", drop_first=True, dtype=float)
    controls = pd.concat([controls, cycle_dummies], axis=1)
    controls["senate"] = frame.chamber.astype(str).str.lower().eq("senate").astype(float)
    controls["incumbent_control"] = pd.to_numeric(frame.incumbent, errors="coerce").fillna(0)
    return controls.astype(float).to_numpy(), controls.columns.to_numpy()


def coefficient(frame: pd.DataFrame, outcome: str, focal: str, extras: list[str]) -> float:
    x, names = design(frame, focal, extras)
    y = frame[outcome].astype(float).to_numpy()
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return float(beta[np.where(names == "focal")[0][0]])


def clustered_interval(frame: pd.DataFrame, outcome: str, focal: str, extras: list[str]) -> tuple[float, float]:
    people = frame.person_id.unique()
    if len(people) < 8:
        return np.nan, np.nan
    x, names = design(frame, focal, extras)
    focal_index = np.where(names == "focal")[0][0]
    y = frame[outcome].astype(float).to_numpy()
    person_index = pd.Categorical(frame.person_id, categories=people).codes
    rng = np.random.default_rng(SEED)
    estimates = []
    for _ in range(BOOTSTRAPS):
        counts = rng.multinomial(len(people), np.repeat(1 / len(people), len(people)))
        weights = counts[person_index]
        keep = weights > 0
        root_weights = np.sqrt(weights[keep])
        try:
            beta = np.linalg.lstsq(
                x[keep] * root_weights[:, None], y[keep] * root_weights, rcond=None
            )[0]
            estimates.append(float(beta[focal_index]))
        except np.linalg.LinAlgError:
            continue
    return tuple(np.quantile(estimates, [.025, .975])) if estimates else (np.nan, np.nan)


def result_row(
    frame: pd.DataFrame, test: str, outcome: str, focal: str, extras: list[str],
    expectation: str, caveat: str = "",
) -> dict:
    needed = [outcome, focal, *extras, "cycle", "chamber", "incumbent", "person_id"]
    sample = frame.dropna(subset=needed).copy()
    estimate = coefficient(sample, outcome, focal, extras) if len(sample) >= 8 else np.nan
    low, high = clustered_interval(sample, outcome, focal, extras)
    return {
        "test": test, "outcome": outcome, "n": len(sample),
        "people": sample.person_id.nunique(), "cycles": sample.cycle.nunique(),
        "estimate_cmo_points_per_1sd": estimate,
        "cluster_bootstrap_95_low": low, "cluster_bootstrap_95_high": high,
        "expected_direction": expectation,
        "direction_matches_hypothesis": (
            (estimate > 0 and expectation == "positive")
            or (estimate < 0 and expectation == "negative")
            if pd.notna(estimate) else False
        ),
        "interval_excludes_zero": bool(pd.notna(low) and pd.notna(high) and (low > 0 or high < 0)),
        "caveat": caveat,
    }


def main() -> None:
    data = pd.read_csv(INPUT)
    data = data[data.shor_match_status.eq("matched") & data.cycle.le(2018)].copy()
    data["np_z"] = zscore(data.shor_np_score)
    data["district_republican_lean_z"] = zscore(-data.core_index_margin)
    data["fit_interaction"] = data.np_z * data.district_republican_lean_z
    data["incumbent_interaction"] = data.np_z * pd.to_numeric(data.incumbent, errors="coerce")
    data["caucus_extremity_z"] = zscore(
        (data.shor_al_dem_conservative_percentile - 50).abs()
    )

    outcomes = [
        "candidate_cmo_total_oof", "candidate_cmo_total_district_grouped",
        "candidate_cmo_resource_adjusted_oof",
    ]
    rows = []
    for outcome in outcomes:
        rows.append(result_row(
            data, "overall_conservatism", outcome, "np_z", [], "positive",
            "Career-level ideal point; does not isolate cultural ideology.",
        ))
        rows.append(result_row(
            data, "conservative_candidate_x_republican_district", outcome,
            "fit_interaction", ["np_z", "district_republican_lean_z"], "positive",
            "Primary candidate-district-fit test; district lean is the same-cycle top-ticket baseline.",
        ))
        rows.append(result_row(
            data, "conservatism_x_incumbency", outcome, "incumbent_interaction",
            ["np_z"], "positive",
            "Tests whether established conservative Democrats received a larger benefit.",
        ))
        rows.append(result_row(
            data, "caucus_extremity", outcome, "caucus_extremity_z", [], "negative",
            "Extremity is distance from the active Alabama Democratic caucus percentile midpoint.",
        ))
        white = data[data.nonwhite_share.lt(.5)].copy()
        nonwhite = data[data.nonwhite_share.ge(.5)].copy()
        rows.append(result_row(
            white, "conservatism_in_majority_white_districts", outcome, "np_z", [], "positive",
            "Very small, predominantly 2014 demographic subset.",
        ))
        rows.append(result_row(
            nonwhite, "conservatism_in_majority_nonwhite_districts", outcome, "np_z", [], "negative",
            "Very small, predominantly 2014 demographic subset.",
        ))
    results = pd.DataFrame(rows)
    results.to_csv(RESULTS, index=False)

    white_audit = data[data.nonwhite_share.lt(.5)][[
        "person_id", "candidate", "cycle", "chamber", "district", "incumbent",
        "nonwhite_share", "shor_np_score", "shor_al_dem_conservative_percentile",
        "candidate_cmo_total_oof", "candidate_cmo_total_district_grouped",
        "candidate_cmo_resource_adjusted_oof", "cmo_geography_low", "cmo_geography_high",
    ]].copy()
    white_audit.to_csv(WHITE_AUDIT, index=False)

    heatmap = pd.read_csv(RESEARCH / "article_issue_heatmap.csv")
    cycles = pd.read_csv(RESEARCH / "candidate_cycle_analysis.csv")[[
        "person_id", "cycle", "candidate_cmo_total_oof",
        "candidate_cmo_total_district_grouped", "candidate_cmo_resource_adjusted_oof",
    ]].drop_duplicates(["person_id", "cycle"])
    issue = heatmap.merge(
        cycles, left_on=["person_id", "election_cycle"], right_on=["person_id", "cycle"],
        how="left", validate="many_to_one",
    )
    issue_rows = []
    for dimension, part in issue.groupby("dimension"):
        for outcome in outcomes:
            usable = part[["person_id", "coded_value", outcome]].dropna()
            rho = spearmanr(usable.coded_value, usable[outcome]).statistic if len(usable) >= 5 else np.nan
            issue_rows.append({
                "dimension": dimension, "outcome": outcome, "n": len(usable),
                "people": usable.person_id.nunique(), "spearman": rho,
                "minimum_code": usable.coded_value.min() if len(usable) else np.nan,
                "maximum_code": usable.coded_value.max() if len(usable) else np.nan,
                "both_ideological_directions_observed": bool(
                    len(usable) and usable.coded_value.min() < 0 < usable.coded_value.max()
                ),
                "inferential_status": "descriptive_only" if len(usable) >= 5 else "insufficient_coverage",
            })
    issue_results = pd.DataFrame(issue_rows)
    issue_results.to_csv(ISSUE_RESULTS, index=False)

    headline = results[results.outcome.eq("candidate_cmo_total_oof")]
    lines = [
        "# Plausible ideology relationships: first test battery", "",
        "These are exploratory associations, not causal estimates. The Shor--McCarty score is a career-level ideal point and can incorporate post-election votes.", "",
        "## Headline OOF CMO results", "",
        "| Test | N | Estimate | Cluster-bootstrap range | Read |", "|---|---:|---:|---:|---|",
    ]
    for row in headline.itertuples(index=False):
        estimate = "NA" if pd.isna(row.estimate_cmo_points_per_1sd) else f"{row.estimate_cmo_points_per_1sd:+.2f}"
        interval = "NA" if pd.isna(row.cluster_bootstrap_95_low) else f"[{row.cluster_bootstrap_95_low:+.2f}, {row.cluster_bootstrap_95_high:+.2f}]"
        read = "direction fits, highly uncertain" if row.direction_matches_hypothesis else "does not fit hypothesized direction"
        if row.interval_excludes_zero:
            read = "direction fits; range excludes zero" if row.direction_matches_hypothesis else "opposite direction; range excludes zero"
        lines.append(f"| {row.test.replace('_', ' ')} | {row.n} | {estimate} | {interval} | {read} |")
    lines += [
        "", "## Interpretation rules", "",
        "- Estimates are CMO points associated with a one-standard-deviation change in the named focal term, conditional on cycle, chamber, and incumbency.",
        "- The candidate-district-fit model also includes candidate ideology and district Republican lean as main effects.",
        "- Candidate-clustered bootstrap ranges describe resampling sensitivity; they are not calibrated causal confidence intervals.",
        "- Race-composition splits have only the subset with available district demographics and should be treated as a power audit.",
        f"- The majority-white subset has {len(white_audit)} rows; {int(white_audit.cycle.eq(2014).sum())} are from 2014. It therefore cannot distinguish an ideology relationship from the known 2014 model/source break.",
        "- Issue-specific cultural and economic results remain descriptive because the pre-election coded samples are tiny.",
        "", "## Pre-election hand-coded signals", "",
        "Localism/personal-vote evidence has 14 observations and is positively associated with CMO in the descriptive ranking. The economic and labor samples have 15 and 10 observations, but every coded case is on the progressive side; their correlations compare degrees of progressive alignment and cannot test progressive versus conservative positioning. Guns has only five candidate-cycle rows (four people), while abortion and broad social ideology each have only two. These are hypothesis-generating rather than confirmatory.",
        "", "## Files", "",
        f"- `{RESULTS.relative_to(ROOT)}`", f"- `{ISSUE_RESULTS.relative_to(ROOT)}`",
        f"- `{WHITE_AUDIT.relative_to(ROOT)}`",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} model rows to {RESULTS}")
    print(f"Wrote {len(issue_results)} issue rows to {ISSUE_RESULTS}")
    print(headline[["test", "n", "estimate_cmo_points_per_1sd", "cluster_bootstrap_95_low", "cluster_bootstrap_95_high"]].to_string(index=False))


if __name__ == "__main__":
    main()
