"""Resolve Vote Smart PCT respondents against the canonical D/R candidate universe.

The output distinguishes true identity failures from candidates intentionally
outside the two-party CMO universe. Only unique same-year/race/party aliases are
accepted; no global-name or later-year propagation is used for a cycle response.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rapidfuzz.fuzz import WRatio

from oe_normalize import normalize_name


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
PCT = IDEOLOGY / "votesmart_all_1998_2022_pct_options.csv"
ROSTER = IDEOLOGY / "votesmart_public_candidate_roster.csv"
CROSSWALK = IDEOLOGY / "votesmart_candidate_crosswalk.csv"
RESOLVED = IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv"
AUDIT = IDEOLOGY / "votesmart_pct_identity_resolution.csv"
PARTY = {"Democratic": "D", "Republican": "R", "Independent": "I",
         "Libertarian": "L", "U.S. Taxpayers": "UST"}


def score(left: object, right: object) -> float:
    return float(WRatio(normalize_name(left), normalize_name(right)))


def main() -> None:
    pct = pd.read_csv(PCT)
    roster = pd.read_csv(ROSTER)
    crosswalk = pd.read_csv(CROSSWALK)
    forms = pct[["election_year", "votesmart_candidate_id", "candidate", "source_url"]].drop_duplicates()
    forms = forms[forms.election_year.isin(range(1998, 2023, 4))].copy()
    roster_key = roster.sort_values("election_year").drop_duplicates(
        ["election_year", "votesmart_candidate_id"]
    )[["election_year", "votesmart_candidate_id", "chamber", "district", "party", "outcome"]]
    forms = forms.merge(roster_key, on=["election_year", "votesmart_candidate_id"], how="left",
                        validate="one_to_one")
    forms["party_code"] = forms.party.map(PARTY).fillna("O")

    resolved = crosswalk.copy()
    accepted = resolved[resolved.accepted].copy()
    accepted["votesmart_candidate_id"] = pd.to_numeric(accepted.votesmart_candidate_id, errors="coerce")
    existing = set(zip(accepted.election_year, accepted.votesmart_candidate_id))
    audit_rows = []
    for form in forms.itertuples(index=False):
        key = (form.election_year, form.votesmart_candidate_id)
        if key in existing:
            target = accepted[(accepted.election_year.eq(form.election_year)) &
                              (accepted.votesmart_candidate_id.eq(form.votesmart_candidate_id))].iloc[0]
            audit_rows.append({**form._asdict(), "resolution_status": "matched_existing",
                               "canonical_candidate_id": target.canonical_candidate_id,
                               "canonical_candidate": target.canonical_candidate,
                               "name_score": target.name_score, "resolution_reason": "accepted_crosswalk"})
            continue
        if form.party_code not in {"D", "R"}:
            audit_rows.append({**form._asdict(), "resolution_status": "outside_two_party_cmo",
                               "canonical_candidate_id": "", "canonical_candidate": "",
                               "name_score": 0.0, "resolution_reason": f"party={form.party}"})
            continue
        pool = resolved[(resolved.election_year.eq(form.election_year)) &
                        (resolved.chamber.eq(form.chamber)) &
                        (resolved.district.eq(form.district)) &
                        (resolved.party.eq(form.party_code))]
        if len(pool) != 1:
            audit_rows.append({**form._asdict(), "resolution_status": "canonical_slot_missing",
                               "canonical_candidate_id": "", "canonical_candidate": "",
                               "name_score": 0.0, "resolution_reason": f"same_race_party_candidates={len(pool)}"})
            continue
        target = pool.iloc[0]
        name_score = score(form.candidate, target.canonical_candidate)
        if name_score >= 85:
            idx = target.name
            resolved.loc[idx, ["votesmart_candidate_id", "votesmart_candidate", "match_method",
                               "name_score", "score_margin", "accepted", "review_required"]] = [
                int(form.votesmart_candidate_id), form.candidate,
                "same_race_party_reviewed_alias", name_score, name_score, True, False,
            ]
            existing.add(key)
            audit_rows.append({**form._asdict(), "resolution_status": "matched_reviewed_alias",
                               "canonical_candidate_id": target.canonical_candidate_id,
                               "canonical_candidate": target.canonical_candidate,
                               "name_score": name_score,
                               "resolution_reason": "unique same-year chamber district party; nickname/middle-name variation"})
        else:
            audit_rows.append({**form._asdict(), "resolution_status": "conflicting_same_race_name",
                               "canonical_candidate_id": target.canonical_candidate_id,
                               "canonical_candidate": target.canonical_candidate,
                               "name_score": name_score,
                               "resolution_reason": "same race/party exists but identity is not supported by name"})

    audit = pd.DataFrame(audit_rows).sort_values(
        ["election_year", "resolution_status", "candidate"]
    )
    resolved.to_csv(RESOLVED, index=False)
    audit.to_csv(AUDIT, index=False)
    print(audit.groupby(["election_year", "resolution_status"]).size().to_string())
    print(f"New reviewed aliases: {audit.resolution_status.eq('matched_reviewed_alias').sum()}")


if __name__ == "__main__":
    main()
