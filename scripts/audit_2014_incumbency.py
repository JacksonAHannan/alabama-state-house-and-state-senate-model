"""Build an evidence-level audit of 2014 legislative incumbency assignments."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
VERIFIED_ANNOTATION_INCUMBENTS = {("house", 45, "DICKIE DRAKE"),
                                  ("house", 47, "JACK WILLIAMS")}
VERIFIED_PARTY_SWITCHERS = {"MIKE MILLICAN", "STEVE HURST", "ALAN HARPER",
                            "LESLEY VANCE", "ALAN C BOOTHE"}


def norm(value: object) -> str:
    import re
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", str(value).upper())).strip()


def main() -> None:
    races = pd.read_csv(WAR / "race_results.csv")
    candidates = pd.read_csv(WAR / "race_candidate_results.csv")
    roster = pd.read_csv(WAR / "incumbency_roster.csv")
    race_inc = pd.read_csv(WAR / "race_incumbency.csv")

    candidates = candidates[candidates.cycle.eq(2014)].copy()
    roster = roster[roster.cycle.eq(2014)].copy()
    audit = candidates.merge(
        roster[["chamber", "district", "incumbent_candidate", "incumbent_party",
                "incumbency_source", "match_score"]],
        left_on=["chamber", "district", "candidate", "party"],
        right_on=["chamber", "district", "incumbent_candidate", "incumbent_party"],
        how="left", validate="one_to_one")
    audit["assigned_incumbent"] = audit.incumbent_candidate.notna()
    source = audit.incumbency_source.fillna("")
    audit["prior_winner_evidence"] = source.str.contains("prior_winner_match")
    audit["annotation_evidence"] = source.str.contains("wikipedia_incumbent_annotation")
    audit["evidence_class"] = "non_incumbent_candidate"
    audit.loc[audit.prior_winner_evidence & audit.annotation_evidence, "evidence_class"] = "corroborated"
    audit.loc[audit.prior_winner_evidence & ~audit.annotation_evidence, "evidence_class"] = "prior_winner_only"
    audit.loc[~audit.prior_winner_evidence & audit.annotation_evidence, "evidence_class"] = "annotation_only_review"
    audit["party_switch_flag"] = False

    # A prior winner matched to a current candidate under a different party is
    # still an incumbent; preserve it for explicit review rather than dropping it.
    transitions = pd.read_csv(WAR / "incumbency_transition_validation.csv")
    transitions = transitions[(transitions.cycle.eq(2014)) &
                              transitions.current_incumbent_match.notna()].copy()
    prior_party = (transitions.sort_values("match_score", ascending=False)
                   .drop_duplicates(["chamber", "current_incumbent_match"])
                   .set_index(["chamber", "current_incumbent_match"]).prior_party.to_dict())
    audit["prior_party"] = [prior_party.get((c, n)) for c, n in
                            zip(audit.chamber, audit.candidate)]
    audit["party_switch_flag"] = (audit.assigned_incumbent & audit.prior_party.notna() &
                                  audit.party.ne(audit.prior_party))

    race_flags = race_inc[race_inc.cycle.eq(2014)][
        ["chamber", "district", "incumbency_status", "incumbent_count"]]
    eligibility = races[races.cycle.eq(2014)][["chamber", "district", "war_eligible"]]
    audit = audit.merge(race_flags, on=["chamber", "district"], how="left", validate="many_to_one")
    audit = audit.merge(eligibility, on=["chamber", "district"], how="left", validate="many_to_one")
    audit["audit_priority"] = "standard"
    audit.loc[audit.evidence_class.eq("annotation_only_review"), "audit_priority"] = "manual_review"
    audit.loc[audit.party_switch_flag, "audit_priority"] = "party_switch_review"
    annotation_verified = [
        (chamber, int(district), norm(candidate)) in VERIFIED_ANNOTATION_INCUMBENTS
        for chamber, district, candidate in zip(audit.chamber, audit.district, audit.candidate)
    ]
    switch_verified = audit.candidate.map(norm).isin(VERIFIED_PARTY_SWITCHERS)
    audit.loc[annotation_verified, "audit_priority"] = "externally_verified_incumbent"
    audit.loc[audit.party_switch_flag & switch_verified,
              "audit_priority"] = "externally_verified_party_switch"
    audit.to_csv(WAR / "2014_incumbency_candidate_audit.csv", index=False)

    summary = (audit.groupby(["evidence_class", "audit_priority"], as_index=False)
               .agg(candidates=("candidate", "size"),
                    contested_candidates=("war_eligible", "sum")))
    summary.to_csv(WAR / "2014_incumbency_audit_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("\nManual-review incumbents:")
    print(audit[audit.audit_priority.ne("standard")][
        ["chamber", "district", "candidate", "party", "incumbency_source",
         "prior_party", "party_switch_flag", "audit_priority"]].to_string(index=False))


if __name__ == "__main__":
    main()
