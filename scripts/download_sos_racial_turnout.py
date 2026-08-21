"""Download Alabama SOS direct general-election participation-by-race reports."""
from __future__ import annotations

import hashlib
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd

from warehouse import ROOT

OUT = ROOT / "data/raw/alabama_elections_and_geography/sos_racial_turnout"
SOURCES = [
    (2018, "general_participation_by_race", "https://www.sos.alabama.gov/sites/default/files/election-data/2019-01/2018GeneralTotalsByRace.xlsx"),
    (2018, "voter_registration", "https://www.sos.alabama.gov/sites/default/files/election-data/2019-01/ALVR-2018.xls"),
    (2020, "general_participation_by_race", "https://www.sos.alabama.gov/sites/default/files/election-data/2021-06/2020%20General%20Election%20Participation%20by%20Race.pdf"),
    (2020, "voter_registration", "https://www.sos.alabama.gov/sites/default/files/election-data/2021-01/ALVR-2020.xls"),
    (2024, "general_participation_by_race", "https://www.sos.alabama.gov/sites/default/files/election-data/2025-10/2024%20General%20Election%20Participation%20by%20Race.pdf"),
    (2024, "voter_registration", "https://www.sos.alabama.gov/sites/default/files/election-data/2025-01/ALVR-2024.xlsx"),
    (2026, "voter_registration", "https://www.sos.alabama.gov/sites/default/files/election-data/2026-07/ALVR-2026.xlsx"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for year, dataset, url in SOURCES:
        suffix = Path(unquote(urlparse(url).path)).suffix.lower()
        target = OUT / f"{year}_{dataset}{suffix}"
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".part")
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 turnout-research/1.0"})
            with urllib.request.urlopen(request) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            temporary.replace(target)
        rows.append({"year": year, "dataset": dataset, "provider": "Alabama Secretary of State",
                     "url": url, "local_path": target.relative_to(ROOT).as_posix(),
                     "bytes": target.stat().st_size, "sha256": sha256(target),
                     "verified_at_utc": datetime.now(timezone.utc).isoformat()})
    manifest = pd.DataFrame(rows)
    manifest.to_csv(OUT / "source_manifest.csv", index=False)
    print(manifest[["year", "bytes", "sha256"]].to_string(index=False))


if __name__ == "__main__":
    main()
