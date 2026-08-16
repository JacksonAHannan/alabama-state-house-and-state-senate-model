"""Build and validate Alabama legislative incumbency features from Wikipedia.

Wikipedia is used as a reproducible roster source. Election votes remain sourced
from the official/OpenElections pipeline. Matching is performed within each
cycle/chamber/district and prior-winner validation is chamber-wide so that a
redistricted incumbent need not retain the same district number.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "data" / "raw" / "wikipedia"
WAR = ROOT / "data" / "processed" / "war"
MODEL_CYCLES = (2014, 2018, 2022)
PARTIES = {"Democratic": "D", "Republican": "R", "Independent": "I",
           "Libertarian": "L"}
# Corrections to known bad incumbent annotations in archived election tables.
# HD29 incumbent Becky Nordgren defeated incumbent Jack Page in 2010; Michael
# J. Gladden was the 2014 challenger, not a second incumbent.
FALSE_INCUMBENT_ANNOTATIONS = {(2014, "house", 29, "MICHAEL GLADDEN")}

SAVED_PAGE_OVERRIDES = {
    (2010, "house"): ROOT / "data" / "raw" / "alabama_elections_and_geography" / "2010 Alabama House of Representatives election - Wikipedia.html",
    (2014, "senate"): ROOT / "data" / "raw" / "alabama_elections_and_geography" / "2014 Alabama Senate election - Wikipedia.html",
}


def wikipedia_path(cycle: int, chamber: str) -> Path:
    override = SAVED_PAGE_OVERRIDES.get((cycle, chamber))
    return override if override and override.exists() else WIKI / f"{cycle}_{chamber}.html"


def clean_candidate(value: str) -> str:
    value = re.sub(r"\[[^]]*]", "", value)
    value = re.sub(r"\(\s*incumbent\s*\)", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def norm_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r'\b(JR|SR|II|III|IV)\b', ' ', value.upper())
    value = re.sub(r'[^A-Z ]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def parse_votes(value: str) -> int | None:
    value = value.replace(",", "").strip()
    return int(value) if re.fullmatch(r"\d+", value) else None


def parse_wikipedia_page(path: Path, cycle: int, chamber: str) -> pd.DataFrame:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    records = []
    fallback_district = 0
    for table in soup.find_all("table"):
        heading = table.find_previous(["h2", "h3", "h4"])
        title = heading.get_text(" ", strip=True) if heading else ""
        match = re.fullmatch(r"District\s+(\d+)", title, flags=re.I)
        district = int(match.group(1)) if match else None
        table_records = []
        for row in table.find_all("tr"):
            # Winning candidates are commonly stored in <th> rather than <td>.
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            party_idx = next((i for i, text in enumerate(cells) if text in PARTIES), None)
            if party_idx is None or party_idx + 2 >= len(cells):
                continue
            raw_candidate = cells[party_idx + 1]
            votes = parse_votes(cells[party_idx + 2])
            if votes is None or re.search(r"write[- ]?in", raw_candidate, re.I):
                continue
            table_records.append({
                "cycle": cycle, "chamber": chamber, "district": district,
                "party": PARTIES[cells[party_idx]],
                "candidate": clean_candidate(raw_candidate),
                "candidate_norm": norm_name(clean_candidate(raw_candidate)),
                "votes_wikipedia": votes,
                "incumbent_wikipedia": bool(re.search(r"incumbent", raw_candidate, re.I)),
                "source_file": path.name,
            })
        if table_records:
            if district is None:
                # Some Senate pages put all district tables under one Results
                # heading. Their documented order is District 1..35.
                fallback_district += 1
                district = fallback_district
                for record in table_records:
                    record["district"] = district
            records.extend(table_records)
    out = pd.DataFrame(records)
    if out.empty:
        raise ValueError(f"No district results parsed from {path}")
    out["winner_wikipedia"] = out.groupby(["cycle", "chamber", "district"])[
        "votes_wikipedia"
    ].transform("max").eq(out["votes_wikipedia"])
    return out


def read_candidate_code_names() -> dict[str, str]:
    readme = ROOT / "data" / "raw" / "alabama_elections_and_geography" / "al_gen_22_prec" / "README.txt"
    mapping = {}
    pattern = re.compile(r"^(G(?:SL\d{3}|SU\d{2})[A-Z][A-Z]{3})\s+.*?-:-(.*?)-:-")
    for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line.strip())
        if match and not re.search(r"write[- ]?in", match.group(2), re.I):
            mapping[match.group(1)] = match.group(2).strip()
    return mapping


def best_match(name: str, options: list[str]) -> tuple[str | None, float]:
    if not options:
        return None, 0.0
    target = norm_name(name)
    exact = [item for item in options if norm_name(item) == target]
    if len(exact) == 1:
        return exact[0], 1.0
    scored = sorted(((SequenceMatcher(None, target, norm_name(x)).ratio(), x)
                     for x in options), reverse=True)
    if scored[0][0] >= 0.86 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.08):
        return scored[0][1], scored[0][0]
    return None, scored[0][0]


def main() -> None:
    frames = []
    for cycle in (2010, 2014, 2018, 2022):
        for chamber in ("house", "senate"):
            frames.append(parse_wikipedia_page(wikipedia_path(cycle, chamber), cycle, chamber))
    wiki = pd.concat(frames, ignore_index=True)
    wiki = (wiki.groupby(["cycle", "chamber", "district", "party", "candidate",
                          "candidate_norm", "source_file"], as_index=False)
            .agg(votes_wikipedia=("votes_wikipedia", "max"),
                 incumbent_wikipedia=("incumbent_wikipedia", "max"),
                 winner_wikipedia=("winner_wikipedia", "max")))

    official = pd.read_csv(WAR / "race_candidate_results.csv")
    official["district"] = official["district"].astype(int)
    code_names = read_candidate_code_names()
    official["candidate_name"] = official["candidate"].astype(str)
    mask22 = official["cycle"].eq(2022)
    official.loc[mask22, "candidate_name"] = official.loc[mask22, "candidate_code"].map(code_names)
    official["candidate_name"] = official["candidate_name"].fillna(official["candidate"].astype(str))

    matches = []
    # Only explicit incumbent annotations need candidate-level matching. This
    # avoids treating candidates from primary-election tables as general-election
    # candidates on pages that publish both.
    for row in wiki[wiki.cycle.isin(MODEL_CYCLES) & wiki.incumbent_wikipedia].itertuples(index=False):
        pool = official[(official.cycle == row.cycle) & (official.chamber == row.chamber) &
                        (official.district == row.district) & (official.party == row.party)]
        matched, score = best_match(row.candidate, pool.candidate_name.tolist())
        matches.append({
            "cycle": row.cycle, "chamber": row.chamber, "district": row.district,
            "party": row.party, "wikipedia_candidate": row.candidate,
            "official_candidate": matched, "match_score": score,
            "incumbent": row.incumbent_wikipedia, "winner_wikipedia": row.winner_wikipedia,
            "match_status": "matched" if matched else "review",
        })
    matched = pd.DataFrame(matches).drop_duplicates(
        ["cycle", "chamber", "district", "party", "wikipedia_candidate"])

    prior = wiki[wiki.winner_wikipedia].copy()
    validations = []
    for cycle in MODEL_CYCLES:
        prior_cycle = cycle - 4
        for chamber in ("house", "senate"):
            old = prior[(prior.cycle == prior_cycle) & (prior.chamber == chamber)]
            current_inc = wiki[(wiki.cycle == cycle) & (wiki.chamber == chamber) &
                               wiki.incumbent_wikipedia].drop_duplicates("candidate_norm")
            candidates = current_inc.candidate.tolist()
            for row in old.itertuples(index=False):
                found, score = best_match(row.candidate, candidates)
                validations.append({
                    "cycle": cycle, "chamber": chamber,
                    "prior_district": row.district, "prior_winner": row.candidate,
                    "prior_party": row.party, "current_incumbent_match": found,
                    "match_score": score,
                    "transition_status": "continuing_incumbent" if found else "not_on_incumbent_roster",
                })
    validation = pd.DataFrame(validations)

    # Build an operational incumbent roster from (a) prior winners who appear
    # anywhere in the current chamber's candidate list and (b) current-page
    # incumbent annotations that successfully match the official candidate.
    roster_records = []
    for cycle in MODEL_CYCLES:
        for chamber in ("house", "senate"):
            pool = official[(official.cycle == cycle) & (official.chamber == chamber)]
            for row in prior[(prior.cycle == cycle - 4) & (prior.chamber == chamber)].itertuples(index=False):
                found, score = best_match(row.candidate, pool.candidate_name.tolist())
                if found:
                    hit = pool[pool.candidate_name.eq(found)].iloc[0]
                    roster_records.append({
                        "cycle": cycle, "chamber": chamber, "district": int(hit.district),
                        "incumbent_candidate": found, "incumbent_party": hit.party,
                        "incumbency_source": "prior_winner_match", "match_score": score,
                    })
    valid_annotations = matched[matched.match_status.eq("matched")].copy()
    false_annotation = pd.Series(False, index=valid_annotations.index)
    normalized_annotation_name = valid_annotations.wikipedia_candidate.map(norm_name)
    for bad_cycle, bad_chamber, bad_district, bad_name in FALSE_INCUMBENT_ANNOTATIONS:
        false_annotation |= (
            valid_annotations.cycle.eq(bad_cycle)
            & valid_annotations.chamber.eq(bad_chamber)
            & valid_annotations.district.eq(bad_district)
            & normalized_annotation_name.eq(bad_name)
        )
    valid_annotations = valid_annotations[~false_annotation]
    for row in valid_annotations.itertuples(index=False):
        roster_records.append({
            "cycle": row.cycle, "chamber": row.chamber, "district": int(row.district),
            "incumbent_candidate": row.official_candidate, "incumbent_party": row.party,
            "incumbency_source": "wikipedia_incumbent_annotation", "match_score": row.match_score,
        })
    roster = pd.DataFrame(roster_records)
    if not roster.empty:
        # Collapse candidate duplicates while retaining every independent source.
        roster = (roster.groupby(["cycle", "chamber", "district", "incumbent_candidate",
                                  "incumbent_party"], as_index=False)
                  .agg(incumbency_source=("incumbency_source", lambda x: "+".join(sorted(set(x)))),
                       match_score=("match_score", "max")))

    model = pd.read_csv(WAR / "district_cycle_model.csv")
    model["district"] = model["district"].astype(int)
    race_inc = model[["cycle", "chamber", "district"]].drop_duplicates()
    incumbents = roster
    summary = (incumbents.groupby(["cycle", "chamber", "district"], as_index=False)
               .agg(incumbent_count=("incumbent_candidate", "size"),
                    incumbent_candidate=("incumbent_candidate", lambda x: " | ".join(x)),
                    incumbent_party=("incumbent_party", lambda x: " | ".join(x)),
                    incumbency_source=("incumbency_source", lambda x: " | ".join(x)),
                    match_score=("match_score", "min")))
    summary["dem_incumbent"] = summary.incumbent_party.str.split(" | ", regex=False).map(lambda x: "D" in x)
    summary["rep_incumbent"] = summary.incumbent_party.str.split(" | ", regex=False).map(lambda x: "R" in x)
    race_inc = race_inc.merge(summary, how="left", on=["cycle", "chamber", "district"])
    race_inc["incumbent_count"] = race_inc["incumbent_count"].fillna(0).astype(int)
    for column in ("dem_incumbent", "rep_incumbent"):
        race_inc[column] = race_inc[column].eq(True)
    race_inc["open_seat"] = race_inc.incumbent_count.eq(0)
    race_inc["incumbency_status"] = race_inc.incumbent_count.map(
        {0: "open", 1: "incumbent_running"}).fillna("multiple_incumbents")

    enriched = model.merge(race_inc, how="left", on=["cycle", "chamber", "district"], validate="one_to_one")

    WAR.mkdir(parents=True, exist_ok=True)
    wiki.to_csv(WAR / "wikipedia_legislative_candidates.csv", index=False)
    matched.to_csv(WAR / "incumbency_candidate_matches.csv", index=False)
    validation.to_csv(WAR / "incumbency_transition_validation.csv", index=False)
    race_inc.to_csv(WAR / "race_incumbency.csv", index=False)
    roster.to_csv(WAR / "incumbency_roster.csv", index=False)
    enriched.to_csv(WAR / "district_cycle_model_with_incumbency.csv", index=False)

    review = pd.concat([
        matched[matched.match_status.eq("review")].assign(review_type="candidate_match"),
        validation.iloc[0:0].assign(review_type="prior_winner_transition"),
    ], ignore_index=True, sort=False)
    review.to_csv(WAR / "incumbency_review.csv", index=False)

    print(f"Wikipedia candidate rows: {len(wiki):,}")
    print(f"Model races enriched: {len(enriched):,}")
    print("Incumbency by cycle/status:")
    print(race_inc.groupby(["cycle", "incumbency_status"]).size().to_string())
    print(f"Candidate matches needing review: {(matched.match_status == 'review').sum():,}")
    print(f"Prior winners not on the next explicit-incumbent roster: "
          f"{(validation.transition_status != 'continuing_incumbent').sum():,}")


if __name__ == "__main__":
    main()
