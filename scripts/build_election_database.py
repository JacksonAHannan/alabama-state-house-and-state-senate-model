"""Build a provenance-aware SQLite database of Alabama election observations.

Official SOS records remain immutable observations. OpenElections records are
stored alongside them for candidate/party enrichment and reconciliation; they
never silently overwrite an SOS vote value.
"""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from oe_normalize import load_oe, normalize_name
from sos_precinct import YEAR_SOURCES, load_sos_year
from warehouse import (atomic_database, begin_run, connect, finish_run, initialize,
                       register_source_file, register_table)

OE_FILES = {
    2012: "20121106__al__general__precinct.csv", 2014: "20141104__al__general__precinct.csv",
    2016: "20161108__al__general__precinct.csv", 2018: "20181106__al__general__precinct.csv",
    2020: "20201103__al__general__precinct.csv",
}

def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()

def _observations(data: pd.DataFrame, source: str, authority: int) -> pd.DataFrame:
    out = data.copy()
    out["source"] = source; out["authority_rank"] = authority
    out["candidate_key"] = out.candidate.map(normalize_name)
    cols = ["year", "county", "county_key", "precinct", "precinct_key", "office", "district",
            "candidate", "candidate_key", "party", "party_norm", "votes", "source", "authority_rank"]
    return out.reindex(columns=cols)

def build(root: Path, years: list[int]) -> Path:
    output = root / "data" / "processed" / "elections"; output.mkdir(parents=True, exist_ok=True)
    database = output / "alabama_elections.sqlite"
    manifests, observations, availability = [], [], []
    for year in years:
        sos = load_sos_year(root, year)
        observations.append(_observations(sos, "alabama_sos", 1))
        present = set(sos.county_key.unique())
        for county in sorted(present):
            availability.append({"year": year, "source": "alabama_sos", "county_key": county,
                                 "status": "available"})
        source_name = YEAR_SOURCES[year]
        archive = root / "data" / "raw" / "alabama_elections_and_geography" / (
            source_name if source_name.lower().endswith((".xls", ".xlsx", ".zip")) else f"{source_name}.zip")
        manifests.append({"source_id": f"sos_{year}", "year": year, "source": "alabama_sos",
                          "path": str(archive.relative_to(root)), "sha256": _hash(archive),
                          "authoritative_votes": 1})
        if year in OE_FILES:
            path = root / "data" / "raw" / "openelections" / OE_FILES[year]
            oe = load_oe(path); oe["year"] = year
            observations.append(_observations(oe, "openelections", 2))
            manifests.append({"source_id": f"oe_{year}", "year": year, "source": "openelections",
                              "path": str(path.relative_to(root)), "sha256": _hash(path),
                              "authoritative_votes": 0})
    frame = pd.concat(observations, ignore_index=True)
    with atomic_database(database) as building:
      with closing(connect(building)) as connection:
        initialize(connection)
        run_id = begin_run(connection, "election_source_layer", {"years": years})
        pd.DataFrame(manifests).to_sql("source_manifest", connection, index=False, if_exists="replace")
        pd.DataFrame(availability).to_sql("source_availability", connection, index=False, if_exists="replace")
        frame.to_sql("vote_observations", connection, index=False, if_exists="replace", chunksize=20000)
        connection.executescript("""
        CREATE UNIQUE INDEX source_manifest_pk ON source_manifest(source_id);
        CREATE UNIQUE INDEX source_availability_pk ON source_availability(year,source,county_key);
        CREATE INDEX vote_lookup ON vote_observations(year, county_key, precinct_key, office, district);
        CREATE INDEX candidate_lookup ON vote_observations(year, candidate_key);
        CREATE VIEW canonical_vote_observations AS
        SELECT * FROM vote_observations v
        WHERE authority_rank = (SELECT MIN(v2.authority_rank) FROM vote_observations v2
          WHERE v2.year=v.year AND v2.county_key=v.county_key);
        """)
        for manifest in manifests:
            register_source_file(
                connection, provider=manifest["source"], path=root / manifest["path"],
                extraction_status="normalized", authoritative_scope=(
                    "official_vote_counts" if manifest["authoritative_votes"] else "identity_enrichment"),
                project_root=root)
        register_table(connection, "vote_observations", "source", "scripts/build_election_database.py",
                       "source + year + county + precinct + office + district + candidate",
                       "Preserve all sources; canonical view selects lowest authority_rank by county/year",
                       "replace", "Normalized provider-specific election vote observations")
        register_table(connection, "canonical_vote_observations", "canonical", "scripts/build_election_database.py",
                       None, "Alabama SOS before OpenElections", "view",
                       "Current authoritative election vote observations")
        finish_run(connection, run_id, {"vote_observations": len(frame),
                   "sources": len(manifests), "counties": len(availability)})
        connection.commit()
    return database

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument("--years", nargs="+", type=int, default=sorted(YEAR_SOURCES))
    args=parser.parse_args(); root=Path(__file__).resolve().parents[1]
    print(build(root,args.years))
