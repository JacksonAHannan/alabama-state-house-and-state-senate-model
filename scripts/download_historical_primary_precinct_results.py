"""Download same-year historical Alabama primary precinct aliases."""
from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse
from datetime import datetime, timezone

import pandas as pd

from warehouse import ROOT

SOURCES = [
    (1998, "primary", "https://www.sos.alabama.gov/sites/default/files/election-data/2023-06/98p-prec.zip"),
    (2002, "primary", "https://www.sos.alabama.gov/sites/default/files/voter-pdfs/2002/2002priprec.exe"),
    (2002, "primary_runoff", "https://www2.alabamavotes.gov/downloads/election/2002/2ndprimary/2002prrprec.exe"),
    (2018, "primary_precinct_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2018-07/2018-Official-Primary-Precinct-Results_1.zip"),
    (2020, "primary_precinct_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2020-06/2020%20Primary%20Precinct%20Results.zip"),
    (2022, "primary_precinct_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2022-06/2022%20Primary%20Precinct%20Results.zip"),
    (2024, "primary_precinct_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2024-04/2024%20Primary%20Precinct%20Results.ZIP"),
    (2026, "primary_election_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2026-07/2026_Primary_Election.zip"),
    (2026, "primary_democratic_precinct_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2026-06/2026%20AL%20Democratic%20Party%20Primary%20Precinct%20Results.zip"),
    (2026, "primary_republican_precinct_results", "https://www.sos.alabama.gov/sites/default/files/election-data/2026-06/2026%20AL%20Republican%20Party%20Primary%20Precinct%20Results.zip"),
    (2026, "primary_total_ballots_cast", "https://www.sos.alabama.gov/sites/default/files/election-data/2026-08/2026PrimaryElectionTotalBallotsCast.pdf"),
]
OUT = ROOT / "data/raw/alabama_elections_and_geography/historical_primaries"


def sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for year, election, url in SOURCES:
        source_suffix = Path(unquote(urlparse(url).path)).suffix.lower()
        target = OUT / f"{year}_{election}{source_suffix}"
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".part")
            print(f"Downloading {year} {election}")
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 precinct-research/1.0"})
            with urllib.request.urlopen(request) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            temporary.replace(target)
        rows.append({"year": year, "election": election, "provider": "Alabama Secretary of State",
                     "url": url, "local_path": target.relative_to(ROOT).as_posix(),
                     "bytes": target.stat().st_size, "sha256": sha256(target),
                     "verified_at_utc": datetime.now(timezone.utc).isoformat()})
    pd.DataFrame(rows).to_csv(OUT / "source_manifest.csv", index=False)
    print(pd.DataFrame(rows)[["year", "election", "bytes", "sha256"]].to_string(index=False))


if __name__ == "__main__":
    main()
