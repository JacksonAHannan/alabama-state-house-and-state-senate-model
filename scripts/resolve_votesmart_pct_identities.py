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
CANONICAL = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
RESOLVED = IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv"
AUDIT = IDEOLOGY / "votesmart_pct_identity_resolution.csv"
MANUAL_OVERRIDES = ROOT / "data" / "manual" / "ideology" / "candidate_votesmart_identity_overrides.csv"
MANUAL_REJECTIONS = ROOT / "data" / "manual" / "ideology" / "candidate_votesmart_identity_rejections.csv"
PARTY = {"Democratic": "D", "Republican": "R", "Independent": "I",
         "Libertarian": "L", "U.S. Taxpayers": "UST"}


def score(left: object, right: object) -> float:
    return float(WRatio(normalize_name(left), normalize_name(right)))


def main() -> None:
    pct = pd.read_csv(PCT)
    roster = pd.read_csv(ROSTER)
    crosswalk = pd.read_csv(CROSSWALK)
    canonical = pd.read_csv(CANONICAL).rename(columns={
        "year": "election_year", "canonical_party": "party",
        "canonical_name": "canonical_candidate"})
    race_key = ["election_year", "chamber", "district", "party"]
    signal_columns = [column for column in crosswalk.columns
                      if column not in {"canonical_candidate_id", "person_id",
                                        "canonical_candidate", *race_key}]
    crosswalk = canonical[["canonical_candidate_id", "person_id", "canonical_candidate",
                           *race_key]].merge(
        crosswalk[race_key + signal_columns], on=race_key, how="left",
        validate="one_to_one")
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

    if MANUAL_OVERRIDES.exists():
        overrides = pd.read_csv(MANUAL_OVERRIDES, dtype=str).fillna("")
        if overrides.canonical_candidate_id.duplicated().any():
            raise ValueError("Manual Vote Smart overrides must be canonical-candidate unique")
        # Vote Smart IDs are person identifiers and therefore legitimately
        # recur when the same candidate runs in multiple cycles.  What must be
        # unique is an ID within an election cycle; otherwise two canonical
        # candidates in the same election could be assigned to one profile.
        override_years = pd.to_numeric(
            overrides.canonical_candidate_id.str.extract(r"^AL-(\d{4})-")[0],
            errors="coerce",
        )
        if override_years.isna().any():
            raise ValueError("Manual Vote Smart override IDs must encode an election year")
        if pd.DataFrame({
            "election_year": override_years,
            "votesmart_candidate_id": overrides.votesmart_candidate_id,
        }).duplicated().any():
            raise ValueError("Manual Vote Smart overrides must be Vote Smart-ID unique within cycle")
        for override in overrides.itertuples(index=False):
            mask = resolved.canonical_candidate_id.eq(override.canonical_candidate_id)
            if mask.sum() != 1:
                raise ValueError(
                    f"Manual Vote Smart override target must exist exactly once: {override.canonical_candidate_id}"
                )
            resolved.loc[mask, ["votesmart_candidate_id", "votesmart_candidate", "match_method",
                                "name_score", "score_margin", "accepted", "review_required"]] = [
                int(override.votesmart_candidate_id), override.votesmart_candidate,
                "manual_verified_identity_override", 100.0, 100.0, True, False,
            ]

    if MANUAL_REJECTIONS.exists():
        rejections = pd.read_csv(MANUAL_REJECTIONS, dtype=str).fillna("")
        if rejections.canonical_candidate_id.duplicated().any():
            raise ValueError("Manual Vote Smart rejections must be canonical-candidate unique")
        for rejection in rejections.itertuples(index=False):
            mask = resolved.canonical_candidate_id.eq(rejection.canonical_candidate_id)
            if mask.sum() != 1:
                raise ValueError(
                    f"Manual Vote Smart rejection target must exist exactly once: {rejection.canonical_candidate_id}"
                )
            current_id = pd.to_numeric(
                resolved.loc[mask, "votesmart_candidate_id"], errors="coerce"
            ).iloc[0]
            rejected_id = pd.to_numeric(rejection.rejected_votesmart_candidate_id, errors="coerce")
            if pd.notna(current_id) and pd.notna(rejected_id) and int(current_id) != int(rejected_id):
                raise ValueError(
                    f"Vote Smart rejection ID changed for {rejection.canonical_candidate_id}: "
                    f"expected {int(rejected_id)}, found {int(current_id)}"
                )
            resolved.loc[mask, ["votesmart_candidate_id", "votesmart_candidate", "match_method",
                                "name_score", "score_margin", "accepted", "review_required"]] = [
                pd.NA, "", "manual_rejected_identity", 0.0, 0.0, False, True,
            ]

    audit = pd.DataFrame(audit_rows).sort_values(
        ["election_year", "resolution_status", "candidate"]
    )
    resolved.to_csv(RESOLVED, index=False)
    audit.to_csv(AUDIT, index=False)
    print(audit.groupby(["election_year", "resolution_status"]).size().to_string())
    print(f"New reviewed aliases: {audit.resolution_status.eq('matched_reviewed_alias').sum()}")


if __name__ == "__main__":
    main()
