"""Attach Shor--McCarty scores to every Democratic CMO candidate-cycle row.

Only normalized-exact and explicit-alias matches are analysis-ready. Fuzzy
suggestions are exported for review but deliberately excluded from inference.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from build_cmo_ideology_legislator_matches import (
    ALIASES,
    ROOT,
    SHOR,
    active_reference,
    any_service_by,
    normalize,
    service_years_by,
)


INPUT = ROOT / "research" / "cmo_ideology" / "candidate_cycle_analysis.csv"
OUTPUT = ROOT / "research" / "cmo_ideology" / "shor_mccarty_candidate_universe.csv"
REVIEW = ROOT / "research" / "cmo_ideology" / "shor_mccarty_universe_review.csv"


def main() -> None:
    candidates = pd.read_csv(INPUT)
    source = pd.read_csv(SHOR, sep="\t", low_memory=False)
    democrats = source[(source["st"] == "AL") & (source["party"] == "D")].copy()
    democrats["normalized_name"] = democrats["name"].map(normalize)
    choices = sorted(democrats["normalized_name"].dropna().unique())

    additions: list[dict[str, object]] = []
    for row in candidates.itertuples(index=False):
        alias = ALIASES.get(row.candidate, row.candidate)
        query = normalize(alias)
        selected = democrats[democrats["normalized_name"] == query]
        method = "manual_alias" if row.candidate in ALIASES else "normalized_exact"
        suggestion_name = ""
        similarity = 100.0 if not selected.empty else np.nan
        if selected.empty:
            suggestion = process.extractOne(query, choices, scorer=fuzz.WRatio)
            if suggestion:
                suggestion_name, similarity = suggestion[0], float(suggestion[1])
            additions.append(
                {
                    "canonical_candidate_id": row.canonical_candidate_id,
                    "shor_match_status": "fuzzy_review" if similarity >= 90 else "unmatched",
                    "shor_match_method": "none",
                    "shor_similarity": similarity,
                    "shor_suggested_name": suggestion_name,
                }
            )
            continue

        scores = pd.to_numeric(selected["np_score"], errors="coerce").dropna().unique()
        status = "matched" if len(scores) == 1 else "ambiguous_multiple_scores"
        score = float(scores[0]) if len(scores) == 1 else np.nan
        reference = active_reference(source, row.chamber, int(row.cycle))
        percentile = (
            float((reference <= score).mean() * 100)
            if len(reference) and pd.notna(score)
            else np.nan
        )
        first = selected.iloc[0]
        prior_service_years = service_years_by(first, int(row.cycle))
        additions.append(
            {
                "canonical_candidate_id": row.canonical_candidate_id,
                "shor_match_status": status,
                "shor_match_method": method,
                "shor_similarity": similarity,
                "shor_suggested_name": " | ".join(sorted(selected["name"].unique())),
                "shor_u_id": " | ".join(sorted(selected["u_id"].astype(str).unique())),
                "shor_np_score": score,
                "shor_np_score_min": float(scores.min()) if len(scores) else np.nan,
                "shor_np_score_max": float(scores.max()) if len(scores) else np.nan,
                "shor_al_dem_conservative_percentile": percentile,
                "shor_reference_caucus_n": len(reference),
                "shor_served_by_election": any_service_by(first, int(row.cycle)),
                "shor_pre_election_service_years": len(prior_service_years),
                "shor_first_observed_service_year": (
                    min(prior_service_years) if prior_service_years else np.nan
                ),
            }
        )

    result = candidates.merge(
        pd.DataFrame(additions), on="canonical_candidate_id", how="left", validate="one_to_one"
    )
    result.to_csv(OUTPUT, index=False)
    review = result[result["shor_match_status"] != "matched"][
        [
            "cycle",
            "chamber",
            "district",
            "candidate",
            "candidate_cmo_total_oof",
            "shor_match_status",
            "shor_similarity",
            "shor_suggested_name",
        ]
    ].sort_values(["shor_match_status", "shor_similarity"], ascending=[True, False])
    review.to_csv(REVIEW, index=False)
    print(f"Wrote {len(result)} candidate-cycle rows to {OUTPUT}")
    print(result["shor_match_status"].value_counts(dropna=False).to_string())
    matched = result[result["shor_match_status"] == "matched"]
    print(
        "Analysis-ready matches:",
        len(matched),
        "rows /",
        matched["person_id"].nunique(),
        "people; pre-election service:",
        int(matched["shor_served_by_election"].sum()),
    )


if __name__ == "__main__":
    main()
