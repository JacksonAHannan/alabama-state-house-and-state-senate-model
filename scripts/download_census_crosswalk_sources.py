"""Download and hash official Census inputs for geographic allocation."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "census"
SOURCES = {
    "BlockAssign2010_ST01_AL.zip": "https://www2.census.gov/geo/docs/maps-data/data/baf/BlockAssign_ST01_AL.zip",
    "BlockAssign_ST01_AL.zip": "https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST01_AL.zip",
    "al2010.pl.zip": "https://www2.census.gov/census_2010/01-Redistricting_File--PL_94-171/Alabama/al2010.pl.zip",
    "al2020.pl.zip": "https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Alabama/al2020.pl.zip",
    "sldl_2022.zip": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2023/2022-state-legislative-bef/sldl_2022.zip",
    "sldu_2022.zip": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2023/2022-state-legislative-bef/sldu_2022.zip",
    "sldu_post2010.zip": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2012/2012-state-legislative-bef/sldu_post2010.zip",
    "sldl_post2010.zip": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2012/2012-state-legislative-bef/sldl_post2010.zip",
}


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for filename, url in SOURCES.items():
        path = DEST / filename
        if not path.exists():
            response = requests.get(url, timeout=180)
            response.raise_for_status()
            path.write_bytes(response.content)
        rows.append({"filename": filename, "url": url, "bytes": path.stat().st_size,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "checked_utc": datetime.now(timezone.utc).isoformat()})
    pd.DataFrame(rows).to_csv(DEST / "source_manifest.csv", index=False)


if __name__ == "__main__":
    main()
