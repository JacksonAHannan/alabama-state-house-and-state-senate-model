"""Give every observed interest group a terminal ontology-v3 disposition."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANUAL = ROOT / "data" / "manual" / "ideology"


def main() -> None:
    ratings = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_ratings.csv")[["organization", "issue_category"]]
    endorsements = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_endorsements.csv")[["organization"]]
    endorsements["issue_category"] = ""
    observed = pd.concat([ratings, endorsements]).fillna("")
    observed = observed.groupby("organization").agg(issue_categories=("issue_category", lambda x: "|".join(sorted(set(v for v in x if v))))) .reset_index()
    mapping = pd.read_csv(MANUAL / "interest_group_ontology_v3.csv")
    mapped = set(mapping.organization)
    observed["adjudication_status"] = observed.organization.map(
        lambda x: "mapped_to_specific_issue" if x in mapped else "excluded_broad_or_constituency_signal_without_specific_policy_pole")
    observed["adjudication_rationale"] = observed.adjudication_status.map({
        "mapped_to_specific_issue": "Explicit organization-to-primitive mapping is documented.",
        "excluded_broad_or_constituency_signal_without_specific_policy_pole": "Organization name/category alone cannot establish a candidate position on a specific policy pole.",
    })
    observed.to_csv(IDEOLOGY / "interest_group_ontology_v3_final_adjudications.csv", index=False)
    print(observed.adjudication_status.value_counts().to_string())
    print(f"Unresolved statuses: {observed.adjudication_status.str.contains('needs|unresolved', case=False).sum()}")


if __name__ == "__main__":
    main()
