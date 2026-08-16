"""Validate the principal quantitative claims and chart artifacts used in the CMO article draft."""

import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"


def near(value: float, target: float, tolerance: float = 0.15) -> bool:
    return abs(float(value) - target) <= tolerance


def main() -> None:
    repeat = pd.read_csv(RESEARCH / "article_repeat_candidate_trajectories.csv")
    geography = pd.read_csv(RESEARCH / "cmo_geography_sensitivity.csv")
    sensitivity = pd.read_csv(RESEARCH / "article_ideology_sensitivity.csv")
    pairs = pd.read_csv(RESEARCH / "matched_pair_evidence.csv")
    pair_decomposition = pd.read_csv(RESEARCH / "article_matched_pair_decomposition.csv")
    evidence = pd.read_csv(RESEARCH / "evidence_ledger.csv")
    candidate_cycles = pd.read_csv(RESEARCH / "candidate_cycle_analysis.csv")
    pending_review = pd.read_csv(RESEARCH / "blind_review_pending.csv")
    blind_results = pd.read_csv(RESEARCH / "blind_code_review_results.csv")
    blind_adjudication = pd.read_csv(RESEARCH / "blind_review_adjudication.csv")
    claim_audit = pd.read_csv(RESEARCH / "article_claim_audit.csv")
    provenance = pd.read_csv(RESEARCH / "source_provenance_audit.csv")
    article = (RESEARCH / "ARTICLE_DRAFT_01.md").read_text(encoding="utf-8")

    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, observed: object, expected: str) -> None:
        checks.append({
            "check": name, "passed": bool(passed),
            "observed": observed, "expected": expected,
        })

    for candidate, cycle, target in [
        ("LARRY MEANS", 2010, -5.72), ("Larry Means", 2014, 29.13),
        ("JOHN 'Jody' LETSON", 2010, -7.59), ("John (Jody) Letson", 2014, 37.15),
    ]:
        row = repeat.loc[repeat.candidate.eq(candidate) & repeat.cycle.eq(cycle)].iloc[0]
        value = row.candidate_cmo_total_oof
        add(f"{candidate} {cycle} CMO", near(value, target), value, f"about {target}")

    for candidate, cycle, total_target, adjusted_target in [
        ("Linda Meigs", 2018, 15.12, 9.66),
        ("Kim Caudle Lewis", 2022, 15.05, 15.78),
    ]:
        row = candidate_cycles.loc[
            candidate_cycles.candidate.str.strip().eq(candidate) & candidate_cycles.cycle.eq(cycle)
        ].iloc[0]
        passed = near(row.candidate_cmo_total_oof, total_target) and near(
            row.candidate_cmo_resource_adjusted_oof, adjusted_target
        )
        add(
            f"{candidate} total/resource-adjusted CMO", passed,
            f"{row.candidate_cmo_total_oof:.2f}/{row.candidate_cmo_resource_adjusted_oof:.2f}",
            f"about {total_target}/{adjusted_target}",
        )

    fields = candidate_cycles.loc[
        candidate_cycles.candidate.str.strip().eq("JAMES C. FIELDS, JR.")
        & candidate_cycles.cycle.eq(2010)
    ].iloc[0]
    add(
        "James Fields 2010 CMO and raw gap",
        near(fields.candidate_cmo_total_oof, 15.60)
        and near(fields.raw_overperformance_x, 34.18),
        f"{fields.candidate_cmo_total_oof:.2f}/{fields.raw_overperformance_x:.2f}",
        "about 15.60/34.18",
    )

    for candidate, cycle, total_target, fundraising_target in [
        ("Rex Cheatham", 2014, 16.74, 17.73),
        ("NAPOLEON BRACY, JR.", 2010, 20.70, 12.88),
        ("GREG VARNER", 2010, 15.46, 8.43),
    ]:
        row = candidate_cycles.loc[
            candidate_cycles.candidate.str.strip().eq(candidate)
            & candidate_cycles.cycle.eq(cycle)
        ].iloc[0]
        passed = near(row.candidate_cmo_total_oof, total_target) and near(
            row.candidate_cmo_fundraising_adjusted_oof, fundraising_target
        )
        add(
            f"{candidate} total/fundraising-adjusted CMO", passed,
            f"{row.candidate_cmo_total_oof:.2f}/{row.candidate_cmo_fundraising_adjusted_oof:.2f}",
            f"about {total_target}/{fundraising_target}",
        )

    fielding = candidate_cycles.loc[
        candidate_cycles.candidate.str.strip().eq("JERRY L. FIELDING")
        & candidate_cycles.cycle.eq(2010)
    ].iloc[0]
    add(
        "Jerry Fielding 2010 CMO", near(fielding.candidate_cmo_total_oof, 18.22),
        fielding.candidate_cmo_total_oof, "about 18.22",
    )

    for candidate, low, high in [
        ("Anthony Daniels", 48.37, 55.66),
        ("Barbara A. Drummond", 12.90, 29.89),
    ]:
        row = geography.loc[geography.candidate.eq(candidate)].iloc[0]
        passed = near(row.cmo_geography_low, low) and near(row.cmo_geography_high, high)
        add(
            f"{candidate} geography range", passed,
            f"{row.cmo_geography_low:.2f} to {row.cmo_geography_high:.2f}",
            f"about {low} to {high}",
        )

    overall = sensitivity.loc[
        sensitivity["sample"].eq("all_matched_through_2018")
        & sensitivity.specification.eq("oof_total")
    ].iloc[0]
    add("overall ideology sample n", overall.n == 52, overall.n, "52")
    add(
        "overall ideology Spearman", near(overall.spearman_cmo_vs_np_score, -0.031, .002),
        overall.spearman_cmo_vs_np_score, "about -0.03",
    )
    add(
        "overall clustered interval",
        near(overall.cluster_bootstrap_95_low, -0.320, .01)
        and near(overall.cluster_bootstrap_95_high, 0.251, .01),
        f"[{overall.cluster_bootstrap_95_low:.3f}, {overall.cluster_bootstrap_95_high:.3f}]",
        "about [-0.32, 0.25]",
    )

    pair_counts = pairs.pair_interpretation.value_counts()
    add(
        "scored matched-pair direction counts",
        pair_counts.get("higher_cmo_candidate_more_conservative", 0) == 1
        and pair_counts.get("higher_cmo_candidate_more_progressive", 0) == 2
        and pair_counts.get("large_cmo_difference_without_large_ideology_difference", 0) == 2,
        pair_counts.to_dict(), "1 more conservative, 2 more progressive, 2 similar",
    )
    drummond_pair = pair_decomposition.loc[
        pair_decomposition.focal_candidate.eq("Barbara A. Drummond")
        & pair_decomposition.comparison_candidate.eq("Louise Alexander")
    ].iloc[0]
    add(
        "Drummond-Alexander geography gap sensitivity",
        0 < drummond_pair.geography_gap_low < 1
        and not bool(drummond_pair.geography_gap_exceeds_5pt),
        f"{drummond_pair.geography_gap_low:.2f} to {drummond_pair.geography_gap_high:.2f}",
        "positive lower bound below one point and not robustly above five points",
    )

    ids_per_case = evidence.groupby(["candidate", "election_cycle"]).person_id.nunique()
    add("no split evidence identities", ids_per_case.max() == 1, ids_per_case.max(), "1")
    add("blind ideology decisions pending", len(pending_review) == 0, len(pending_review), "0")
    add(
        "blind pending queue hides identities",
        not {"person_id", "candidate"}.intersection(pending_review.columns),
        sorted(pending_review.columns), "no candidate or person_id column",
    )
    add(
        "independent blind decisions complete",
        len(blind_results) == 46,
        len(blind_results), "46 candidate-dimension decisions",
    )
    add(
        "blind disagreements adjudicated",
        (blind_adjudication.original_code != blind_adjudication.reviewer_code).sum()
        == len(blind_adjudication) == 6,
        f"{(blind_adjudication.original_code != blind_adjudication.reviewer_code).sum()} raw disagreements/"
        f"{len(blind_adjudication)} adjudications",
        "6 raw disagreements and 6 adjudications",
    )
    adjudicated_current = blind_adjudication.merge(
        blind_results[["anonymous_case_id", "dimension", "current_numeric_code"]],
        on=["anonymous_case_id", "dimension"], how="left", validate="one_to_one",
    )
    add(
        "current codes implement blind adjudication",
        adjudicated_current.current_numeric_code.eq(
            adjudicated_current.adjudicated_code
        ).all(),
        int(adjudicated_current.current_numeric_code.eq(
            adjudicated_current.adjudicated_code
        ).sum()),
        "6 of 6 adjudicated codes",
    )
    direction_reversals = blind_adjudication.loc[
        (blind_adjudication.original_code * blind_adjudication.reviewer_code < 0)
    ]
    add(
        "blind disagreements do not reverse direction",
        direction_reversals.empty,
        len(direction_reversals), "0 directional reversals",
    )
    betterton_provenance = provenance.loc[
        provenance.candidate.str.contains("Betterton")
        & provenance.source_kind.eq("candidate_issue_page")
    ].iloc[0]
    add(
        "Betterton platform provenance",
        betterton_provenance.result == "temporally_eligible"
        and betterton_provenance.observed_modified_date <= betterton_provenance.cutoff_date,
        f"{betterton_provenance.observed_publication_date}/{betterton_provenance.observed_modified_date}",
        "published and last modified before 2014-11-04",
    )
    daniels_search = provenance.loc[
        provenance.candidate.eq("Anthony Daniels")
        & provenance.source_kind.eq("campaign_issue_platform")
    ]
    add(
        "Daniels negative archive search logged",
        len(daniels_search) == 1 and daniels_search.iloc[0].result == "not_recovered",
        daniels_search.result.tolist(), "one not_recovered provenance row",
    )
    required_claims = {f"C{i:02d}" for i in range(1, 28)}
    audited_claims = set(claim_audit.claim_id)
    add(
        "article claim-audit inventory",
        required_claims.issubset(audited_claims), sorted(audited_claims),
        "C01 through C27 present",
    )

    chart_dir = RESEARCH / "charts"
    manifest = pd.read_csv(chart_dir / "chart_manifest.csv")
    expected_charts = {
        f"{stem}.{suffix}"
        for stem in [
            "01_ideology_vs_cmo", "02_repeat_candidate_trajectories",
            "03_matched_pair_gaps", "04_issue_bundle_heatmap",
        ]
        for suffix in ["png", "svg"]
    }
    listed = set(manifest.file)
    add("chart manifest inventory", listed == expected_charts, sorted(listed), "eight expected PNG/SVG files")

    artifact_results = []
    for row in manifest.itertuples():
        path = chart_dir / row.file
        exists = path.is_file()
        actual_size = path.stat().st_size if exists else 0
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest() if exists else "missing"
        artifact_results.append(exists and actual_size == row.bytes and actual_hash == row.sha256)
    add("chart artifact hashes", all(artifact_results), sum(artifact_results), f"{len(manifest)} matching artifacts")

    png_refs = {f"charts/{name}" for name in expected_charts if name.endswith(".png")}
    missing_refs = sorted(ref for ref in png_refs if ref not in article)
    add("article embeds all four charts", not missing_refs, missing_refs, "no missing PNG references")

    output = pd.DataFrame(checks)
    output.to_csv(RESEARCH / "article_reproducibility_checks.csv", index=False)
    failures = output.loc[~output.passed]
    if not failures.empty:
        raise AssertionError(f"Article validation failed:\n{failures.to_string(index=False)}")
    print(f"Article reproducibility checks passed: {len(output)}/{len(output)}")


if __name__ == "__main__":
    main()
