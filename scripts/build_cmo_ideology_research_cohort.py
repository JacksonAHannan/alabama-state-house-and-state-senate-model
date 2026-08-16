"""Build the reproducible candidate cohort for the CMO ideology research loop."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv"
OUT = ROOT / "research" / "cmo_ideology" / "candidate_cohort.csv"


def main():
    data = pd.read_csv(SOURCE)
    dem = data.loc[data["party"].eq("D")].copy()
    dem["candidate"] = dem["candidate"].str.strip()
    geography_path = ROOT / "research" / "cmo_ideology" / "cmo_geography_sensitivity.csv"
    if geography_path.exists():
        geography = pd.read_csv(geography_path)[[
            "canonical_candidate_id", "cmo_geography_low", "cmo_geography_high",
            "cmo_geography_mean", "cmo_geography_range",
        ]]
        dem = dem.merge(geography, on="canonical_candidate_id", how="left", validate="one_to_one")
    else:
        for column in ["cmo_geography_low", "cmo_geography_high", "cmo_geography_mean",
                       "cmo_geography_range"]:
            dem[column] = pd.NA
    score = "candidate_cmo_total_oof"
    robustness = [score, "candidate_cmo_total_cycle_holdout", "candidate_cmo_total_district_grouped"]
    dem["robust_cmo_median"] = dem[robustness].median(axis=1)
    dem["cmo_method_range"] = dem[robustness].max(axis=1) - dem[robustness].min(axis=1)
    dem["robust_positive"] = dem[robustness].min(axis=1).gt(0)
    dem = dem.sort_values(score, ascending=False)

    # Candidate-level selection avoids allowing repeat candidates to consume the
    # entire research queue. Their other cycles remain visible in cycles_observed.
    cohort = dem.groupby("person_id", as_index=False).first()
    histories = dem.groupby("person_id").agg(
        cycles_observed=("cycle", lambda x: ";".join(map(str, sorted(set(x))))),
        scored_cycles=("cycle", "size"),
        best_cmo=(score, "max"),
        median_cmo=(score, "median"),
        minimum_cmo=(score, "min"),
    )
    cohort = cohort.drop(columns=[score]).join(histories, on="person_id")
    cohort = cohort.sort_values("best_cmo", ascending=False).head(30)

    cohort["validation_priority"] = "standard"
    cohort.loc[~cohort["robust_positive"], "validation_priority"] = "sensitivity_review"
    geography_review = cohort.cmo_geography_range.ge(5) | cohort.cmo_geography_low.le(0)
    cohort.loc[geography_review, "validation_priority"] = "geography_review"
    cohort.loc[cohort["best_cmo"].abs().ge(50), "validation_priority"] = "critical"
    cohort["party_identity_status"] = "unverified"
    cohort["party_identity_note"] = ""
    known = {
        "ALPERSON-HOLMES": ("invalid", "2014 HD-31 Mike Holmes was an unopposed Republican; not a Democratic overperformer."),
        "ALPERSON-BAKER": ("invalid", "2014 HD-66 Alan Baker was a Republican; not a Democratic overperformer."),
        "ALPERSON-JERRY-L-FIELDING": ("verified_switcher", "Elected as a Democrat in 2010; switched to Republican in 2012."),
        "ALPERSON-ALAN-HARPER": ("verified_switcher", "Elected as a Democrat; switched to Republican in 2012."),
    }
    for person_id, (status, note) in known.items():
        hit = cohort["person_id"].eq(person_id)
        cohort.loc[hit, ["party_identity_status", "party_identity_note"]] = [status, note]

    # Promote official, cycle-specific identity checks from the evidence ledger
    # instead of requiring every verified candidate to be hard-coded here.
    ledger_path = OUT.parent / "evidence_ledger.csv"
    if ledger_path.exists():
        ledger = pd.read_csv(ledger_path)
        verified = ledger.loc[
            ledger["dimension"].eq("party_identity")
            & ledger["coded_value"].eq("verified_democrat")
            & ledger["source_type"].eq("official_election_record"),
            ["person_id", "election_cycle", "evidence_summary"],
        ].drop_duplicates(["person_id", "election_cycle"])
        for row in verified.itertuples(index=False):
            hit = cohort["person_id"].eq(row.person_id) & cohort["cycle"].eq(row.election_cycle)
            # Explicit invalid/switcher audits remain more informative.
            hit &= cohort["party_identity_status"].eq("unverified")
            cohort.loc[hit, ["party_identity_status", "party_identity_note"]] = [
                "verified_democrat", row.evidence_summary,
            ]

    cohort["research_status"] = "queued"
    cohort.loc[cohort["party_identity_status"].eq("invalid"), "research_status"] = "exclude_data_error"
    for col in [
        "economic_ideology", "social_ideology", "guns_position", "abortion_position",
        "labor_position", "party_independence", "localism_personal_vote",
        "overall_ideological_valence", "confidence", "evidence_summary", "primary_source_urls",
        "secondary_source_urls", "research_notes",
    ]:
        cohort[col] = ""

    keep = [
        "person_id", "candidate", "cycle", "chamber", "district", "incumbent", "winner",
        "cycles_observed", "scored_cycles", "best_cmo", "median_cmo", "minimum_cmo",
        "candidate_cmo_total_cycle_holdout", "candidate_cmo_total_district_grouped",
        "candidate_cmo_resource_adjusted_oof", "robust_cmo_median", "cmo_method_range",
        "robust_positive", "cmo_geography_low", "cmo_geography_high",
        "cmo_geography_mean", "cmo_geography_range",
        "validation_priority", "party_identity_status", "party_identity_note", "research_status",
        "economic_ideology", "social_ideology", "guns_position", "abortion_position",
        "labor_position", "party_independence", "localism_personal_vote",
        "overall_ideological_valence", "confidence", "evidence_summary", "primary_source_urls",
        "secondary_source_urls", "research_notes",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cohort[keep].to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(cohort)} candidate profiles)")


if __name__ == "__main__":
    main()
