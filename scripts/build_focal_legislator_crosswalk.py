"""Suggest stable LegiScan people IDs for the focal CMO candidate roster."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

try:
    from scripts.import_legiscan_alabama_rollcalls import normalize_name
except ModuleNotFoundError:
    from import_legiscan_alabama_rollcalls import normalize_name


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
REVIEWED_ALIASES = {"Billy Beasley": 3386, "Marc Keahey": 3485}


def district_number(value: object) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def main() -> None:
    focal = pd.read_csv(RESEARCH / "candidate_state_issue_matrix.csv")
    canonical = pd.read_csv(ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv")
    people = pd.read_csv(ROOT / "data" / "processed" / "legislative" / "legiscan_alabama_legislators.csv")
    canonical = canonical[["person_id", "year", "winner", "incumbent"]].drop_duplicates()
    focal = focal.merge(canonical, left_on=["person_id", "election_cycle"], right_on=["person_id", "year"], how="left")
    people["normalized_name"] = people.name.map(normalize_name)
    people["district_number"] = people.district.map(district_number)
    people["record_chamber"] = people.district.astype(str).str[:2].map({"HD": "house", "SD": "senate"})
    records = []
    for _, candidate in focal.iterrows():
        normalized = normalize_name(candidate.display_candidate)
        pool = people.copy()
        exact_ids = pool[pool.normalized_name.eq(normalized)].people_id.unique()
        match_id = None
        method = "unmatched"
        if candidate.display_candidate in REVIEWED_ALIASES:
            match_id, method = REVIEWED_ALIASES[candidate.display_candidate], "reviewed_name_alias"
        elif len(exact_ids) == 1:
            match_id, method = int(exact_ids[0]), "exact_name"
        else:
            tokens = normalized.split()
            first_last = pool[
                pool.normalized_name.str.split().str[0].eq(tokens[0])
                & pool.normalized_name.str.split().str[-1].eq(tokens[-1])
            ].people_id.unique()
            if len(first_last) == 1:
                match_id, method = int(first_last[0]), "unique_first_last_name"
        if match_id is None and bool(candidate.winner):
            service_start = candidate.election_cycle if bool(candidate.incumbent) else candidate.election_cycle + 1
            first_service = pool[
                pool.record_chamber.eq(candidate.chamber)
                & pool.session_year.between(service_start, candidate.election_cycle + 2)
                & pool.district_number.eq(int(candidate.district))
            ]
            ids = first_service.people_id.unique()
            if len(ids) == 1:
                match_id, method = int(ids[0]), "winner_unique_district_first_service"
        matched = people[people.people_id.eq(match_id)] if match_id is not None else people.iloc[0:0]
        records.append({
            "person_id": candidate.person_id, "candidate": candidate.display_candidate,
            "election_cycle": candidate.election_cycle, "candidate_chamber": candidate.chamber,
            "candidate_district": candidate.district, "winner": candidate.winner,
            "legiscan_people_id": match_id, "legiscan_name": matched.name.mode().iat[0] if not matched.empty else "",
            "match_method": method, "review_status": "reviewed" if method in {"exact_name", "unique_first_last_name", "reviewed_name_alias"} else "needs_human_review",
            "review_note": "",
        })
    output = pd.DataFrame(records)
    output.to_csv(RESEARCH / "focal_legislator_identity_crosswalk.csv", index=False)
    print(output.match_method.value_counts().to_string())


if __name__ == "__main__":
    main()
