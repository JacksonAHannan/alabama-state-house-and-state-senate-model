"""Create a CMO-free, anonymized packet for independent ideology recoding."""

from pathlib import Path
import hashlib
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
ELECTION_DATES = {
    2010: "2010-11-02", 2014: "2014-11-04",
    2018: "2018-11-06", 2022: "2022-11-08",
}
REVIEW_DIMENSIONS = {
    "economic_ideology", "social_ideology", "guns_position",
    "abortion_position", "labor_position", "overall_ideological_valence",
}


def redact_candidate_identities(text: object, candidate_names: list[str]) -> str:
    """Remove candidate names from evidence presented to blind reviewers."""
    value = "" if pd.isna(text) else str(text)
    variants: set[str] = set()
    for name in candidate_names:
        cleaned = re.sub(r"[^A-Za-z' -]", " ", str(name)).strip()
        if not cleaned:
            continue
        variants.add(cleaned)
        tokens = [token.strip("'-") for token in re.split(r"\s+", cleaned) if token]
        # Any meaningful name component can identify the subject, especially
        # when suffixes make the final token something other than the surname.
        # Over-redaction is preferable to leaking identity in a blind packet.
        variants.update(token for token in tokens if len(token) >= 4)
    for variant in sorted(variants, key=len, reverse=True):
        value = re.sub(rf"\b{re.escape(variant)}\b", "the candidate", value,
                       flags=re.IGNORECASE)
    return re.sub(r"\bthe candidate(?:\s+the candidate)+\b", "the candidate", value,
                  flags=re.IGNORECASE)


def stable_anonymous_case_id(person_id: str, election_cycle: int) -> str:
    """Return an opaque ID that does not change when the review sample grows."""
    payload = f"{person_id}|{int(election_cycle)}|cmo-blind-v1".encode()
    return "CASE-" + hashlib.sha256(payload).hexdigest()[:10].upper()


def main() -> None:
    old_key_path = RESEARCH / "blind_code_review_key.csv"
    old_key = pd.read_csv(old_key_path) if old_key_path.exists() else pd.DataFrame()
    ledger = pd.read_csv(RESEARCH / "evidence_ledger.csv")
    candidate_names = sorted(ledger.candidate.dropna().astype(str).unique())
    ledger["evidence_date"] = pd.to_datetime(ledger.evidence_date, errors="coerce")
    ledger["election_date"] = pd.to_datetime(ledger.election_cycle.map(ELECTION_DATES))
    ledger["temporally_eligible"] = (
        ledger.evidence_date.le(ledger.election_date)
        & ~ledger.review_status.fillna("").str.contains("post_election|retrospective", case=False)
    )

    cases = ledger[["person_id", "election_cycle"]].drop_duplicates().copy()
    # Opaque but stable IDs prevent an expanded case set from silently changing
    # the identity attached to an existing blind-review decision.
    cases["anonymous_case_id"] = cases.apply(
        lambda row: stable_anonymous_case_id(row.person_id, row.election_cycle), axis=1
    )
    if cases.anonymous_case_id.duplicated().any():
        raise ValueError("Anonymous case-ID collision")

    packet = ledger.merge(cases, on=["person_id", "election_cycle"], validate="many_to_one")
    packet["review_evidence_summary"] = packet.evidence_summary.map(
        lambda value: redact_candidate_identities(value, candidate_names)
    )
    packet = packet.sort_values(["anonymous_case_id", "dimension", "evidence_date"])
    packet[[
        "anonymous_case_id", "election_cycle", "evidence_date", "dimension",
        "review_evidence_summary", "source_type", "confidence",
        "temporally_eligible",
    ]].rename(columns={"review_evidence_summary": "evidence_summary"}).assign(
        reviewer_code="", reviewer_confidence="", reviewer_note=""
    ).to_csv(RESEARCH / "blind_code_review_packet.csv", index=False)

    key = packet[[
        "anonymous_case_id", "person_id", "candidate", "election_cycle",
        "dimension", "coded_value", "review_status",
    ]]
    key.to_csv(RESEARCH / "blind_code_review_key.csv", index=False)

    audit = (ledger.groupby(["person_id", "candidate", "election_cycle"], as_index=False)
             .agg(total_items=("dimension", "size"),
                  eligible_items=("temporally_eligible", "sum"),
                  post_election_items=("temporally_eligible", lambda x: (~x).sum()),
                  dimensions=("dimension", "nunique"),
                  sources=("source_url", "nunique")))
    audit["needs_more_pre_election_evidence"] = audit.eligible_items.lt(2)
    audit.to_csv(RESEARCH / "temporal_evidence_audit.csv", index=False)

    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    priority = cohort.merge(
        audit[["person_id", "election_cycle", "eligible_items", "post_election_items",
               "dimensions", "sources"]],
        left_on=["person_id", "cycle"], right_on=["person_id", "election_cycle"],
        how="left",
    ).drop(columns="election_cycle", errors="ignore")
    for column in ["eligible_items", "post_election_items", "dimensions", "sources"]:
        priority[column] = priority[column].fillna(0).astype(int)
    priority["pre_election_evidence_gap"] = (2 - priority.eligible_items).clip(lower=0)
    priority["research_priority_score"] = (
        priority.best_cmo.rank(method="min", ascending=False)
        + priority.eligible_items.mul(20)
    )
    priority = priority.sort_values(
        ["pre_election_evidence_gap", "best_cmo"], ascending=[False, False]
    )
    priority.to_csv(RESEARCH / "research_priority_queue.csv", index=False)

    decisions_path = RESEARCH / "blind_review_decisions.csv"
    if decisions_path.exists():
        decisions = pd.read_csv(decisions_path)
        if not old_key.empty and decisions.anonymous_case_id.str.match(r"CASE-\d{3}$").any():
            identity = old_key[["anonymous_case_id", "dimension", "person_id", "election_cycle"]].drop_duplicates()
            decisions = decisions.merge(
                identity, on=["anonymous_case_id", "dimension"], how="left", validate="one_to_one"
            ).drop(columns="anonymous_case_id")
            decisions = decisions.merge(
                cases, on=["person_id", "election_cycle"], how="left", validate="many_to_one"
            ).drop(columns=["person_id", "election_cycle"])
            decisions = decisions[[
                "anonymous_case_id", "dimension", "reviewer_code",
                "reviewer_confidence", "reviewer_note",
            ]]
            decisions.to_csv(decisions_path, index=False)
        decided = set(zip(decisions.anonymous_case_id, decisions.dimension))
        reviewable = packet.loc[
            packet.temporally_eligible
            & packet.dimension.isin(REVIEW_DIMENSIONS)
            & pd.to_numeric(packet.coded_value, errors="coerce").notna()
        ].copy()
        reviewable["already_decided"] = reviewable.apply(
            lambda row: (row.anonymous_case_id, row.dimension) in decided, axis=1
        )
        pending = (reviewable.loc[~reviewable.already_decided]
                   .groupby(["anonymous_case_id", "election_cycle", "dimension"], as_index=False)
                   .agg(evidence_summary=("review_evidence_summary", " | ".join),
                        source_types=("source_type", lambda x: ";".join(sorted(set(x)))),
                        evidence_items=("dimension", "size")))
        pending = pending.assign(
            reviewer_code="", reviewer_confidence="", reviewer_note=""
        )
        pending.to_csv(RESEARCH / "blind_review_pending.csv", index=False)
        current = key.copy()
        current["current_numeric_code"] = pd.to_numeric(current.coded_value, errors="coerce")
        results = decisions.merge(
            current[["anonymous_case_id", "dimension", "person_id", "candidate",
                     "election_cycle", "current_numeric_code"]].drop_duplicates(),
            on=["anonymous_case_id", "dimension"], how="left", validate="one_to_one"
        )
        results["reviewer_code"] = pd.to_numeric(results.reviewer_code, errors="coerce")
        results["code_agrees"] = results.reviewer_code.eq(results.current_numeric_code)
        results.to_csv(RESEARCH / "blind_code_review_results.csv", index=False)
        print(
            f"Blind review agreement: {results.code_agrees.sum()}/{len(results)} "
            f"completed decisions; {len(pending)} eligible decisions pending"
        )
    print(
        f"Wrote {len(packet)} blinded evidence rows for {len(cases)} cases; "
        f"{audit.needs_more_pre_election_evidence.sum()} cases have fewer than two pre-election items"
    )


if __name__ == "__main__":
    main()
