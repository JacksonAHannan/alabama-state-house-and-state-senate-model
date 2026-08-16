"""Match public Vote Smart identities to canonical candidate-election records."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pandas as pd
from rapidfuzz.fuzz import WRatio

from oe_normalize import normalize_name
from warehouse import connect


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ROSTER = IDEOLOGY / "votesmart_public_candidate_roster.csv"
OUT = IDEOLOGY / "votesmart_candidate_crosswalk.csv"
PARTY = {"Democratic": "D", "Republican": "R", "Independent": "I"}


def score_name(left: object, right: object) -> float:
    return float(WRatio(normalize_name(left), normalize_name(right)))


def build_crosswalk(canonical: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    roster = roster.copy()
    roster["party_code"] = roster.party.map(PARTY).fillna("O")
    people = roster.sort_values("election_year").drop_duplicates("votesmart_candidate_id")
    results: list[dict[str, object]] = []
    for candidate in canonical.itertuples(index=False):
        same_race = roster[
            roster.election_year.eq(candidate.year)
            & roster.chamber.eq(candidate.chamber)
            & roster.district.eq(candidate.district)
        ]
        party_pool = same_race[same_race.party_code.eq(candidate.party)]
        pool = party_pool if not party_pool.empty else same_race
        method = "same_race_party" if not party_pool.empty else "same_race"
        if pool.empty and candidate.year == 1994:
            # Vote Smart has no public 1994 Alabama election roster. Repeated
            # candidates can still be linked by an exceptionally strong unique
            # person-name match, retained with an explicit retrospective method.
            pool = people
            method = "1994_unique_person_name"
        scored = sorted(
            ((score_name(candidate.ballot_name, row.candidate), row) for row in pool.itertuples()),
            key=lambda item: item[0], reverse=True,
        )
        best_score = scored[0][0] if scored else 0.0
        margin = best_score - (scored[1][0] if len(scored) > 1 else 0.0)
        match = scored[0][1] if scored else None
        accepted = bool(
            match is not None
            and (
                (method.startswith("same_race") and best_score >= 86 and margin >= 4)
                or (method == "1994_unique_person_name" and best_score >= 96 and margin >= 8)
            )
        )
        results.append(
            {
                "canonical_candidate_id": candidate.canonical_candidate_id,
                "person_id": candidate.person_id,
                "election_year": candidate.year,
                "chamber": candidate.chamber,
                "district": candidate.district,
                "party": candidate.party,
                "canonical_candidate": candidate.ballot_name,
                "votesmart_candidate_id": int(match.votesmart_candidate_id) if accepted else None,
                "votesmart_candidate": match.candidate if match is not None else None,
                "match_method": method if accepted else "unmatched",
                "name_score": round(best_score, 3),
                "score_margin": round(margin, 3),
                "accepted": accepted,
                "review_required": bool(not accepted and best_score >= 75),
            }
        )
    result = pd.DataFrame(results)
    accepted_people = (
        result[result.accepted]
        .groupby("person_id").votesmart_candidate_id
        .agg(lambda values: sorted(set(values.dropna())))
    )
    unique_people = accepted_people[accepted_people.map(len).eq(1)]
    for index, row in result[result.election_year.eq(1994) & ~result.accepted].iterrows():
        identifiers = unique_people.get(row.person_id, [])
        if len(identifiers) != 1:
            continue
        votesmart_id = int(identifiers[0])
        profile = people[people.votesmart_candidate_id.eq(votesmart_id)].iloc[0]
        result.loc[index, [
            "votesmart_candidate_id", "votesmart_candidate", "match_method",
            "accepted", "review_required",
        ]] = [
            votesmart_id, profile.candidate, "canonical_person_id_propagation", True, False,
        ]
    return result


def main() -> None:
    roster = pd.read_csv(ROSTER)
    with closing(connect(readonly=True)) as connection:
        canonical = pd.read_sql(
            """SELECT canonical_candidate_id,person_id,year,chamber,district,party,ballot_name
               FROM fact_candidate_election WHERE year BETWEEN 1994 AND 2022""",
            connection,
        )
    result = build_crosswalk(canonical, roster)
    result.to_csv(OUT, index=False)
    summary = result.groupby("election_year").accepted.agg(["sum", "count"])
    print(summary.to_string())
    print(f"Wrote {len(result):,} rows to {OUT}")


if __name__ == "__main__":
    main()
