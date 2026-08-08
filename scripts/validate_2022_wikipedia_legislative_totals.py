"""Compare 2022 RDH/SOS-derived totals with archived Wikipedia district tables."""

from pathlib import Path

import pandas as pd

from build_incumbency_features import best_match, norm_name, read_candidate_code_names


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def main() -> None:
    modeled = pd.read_csv(WAR / "race_candidate_results.csv")
    modeled = modeled[modeled.cycle.eq(2022)].copy()
    codes = read_candidate_code_names()
    modeled["candidate_display"] = modeled.candidate_code.map(codes).fillna(modeled.candidate)

    wiki = pd.read_csv(WAR / "wikipedia_legislative_candidates.csv")
    wiki = wiki[wiki.cycle.eq(2022)].copy()
    records = []
    for row in modeled.itertuples(index=False):
        pool = wiki[(wiki.chamber.eq(row.chamber)) & (wiki.district.eq(row.district)) &
                    (wiki.party.eq(row.party))]
        found, score = best_match(row.candidate_display, pool.candidate.tolist())
        hit = pool[pool.candidate.eq(found)] if found else pool.iloc[0:0]
        records.append({
            "cycle": 2022, "chamber": row.chamber, "district": int(row.district),
            "party": row.party, "candidate_modeled": row.candidate_display,
            "candidate_wikipedia": found, "name_match_score": score,
            "votes_modeled": row.votes,
            "votes_wikipedia": hit.votes_wikipedia.iloc[0] if len(hit) == 1 else pd.NA,
            "name_match_status": "matched" if found else "review",
        })
    comparison = pd.DataFrame(records)
    comparison["vote_difference"] = comparison.votes_modeled - comparison.votes_wikipedia
    comparison["exact_vote_match"] = comparison.vote_difference.eq(0)
    comparison["absolute_vote_difference"] = comparison.vote_difference.abs()
    comparison.to_csv(WAR / "2022_wikipedia_vote_validation.csv", index=False)
    joined = comparison.votes_wikipedia.notna()
    summary = pd.DataFrame([{
        "modeled_candidates": len(comparison),
        "name_matched_candidates": int(joined.sum()),
        "name_review_candidates": int((~joined).sum()),
        "exact_vote_matches": int(comparison.exact_vote_match.sum()),
        "vote_mismatches": int((joined & ~comparison.exact_vote_match).sum()),
        "total_absolute_vote_difference": float(comparison.absolute_vote_difference.sum()),
        "maximum_absolute_vote_difference": float(comparison.absolute_vote_difference.max()),
        "modeled_vote_total": float(comparison.votes_modeled.sum()),
        "wikipedia_vote_total_for_matches": float(comparison.loc[joined, "votes_wikipedia"].sum()),
    }])
    summary.to_csv(WAR / "2022_wikipedia_vote_validation_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("\nRows requiring review or with vote differences:")
    print(comparison[(~joined) | (~comparison.exact_vote_match)].to_string(index=False))


if __name__ == "__main__":
    main()
