"""Vendor OpenElections Alabama precinct CSVs from the sibling data repo.

This replaces the previous silent manual copy of these files into
data/raw/openelections/: running this script is the explicit, logged sync
step, and it fails loudly if the sibling checkout or a source file is
missing rather than silently leaving a stale copy in place.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

CYCLES: list[tuple[int, str]] = [
    (2012, "2012/20121106__al__general__precinct.csv"),
    (2014, "2014/20141104__al__general__precinct.csv"),
    (2016, "2016/20161108__al__general__precinct.csv"),
    (2018, "2018/20181106__al__general__precinct.csv"),
    (2020, "2020/20201103__al__general__precinct.csv"),
]


def sync(source_repo: Path, dest_dir: Path) -> list[dict[str, object]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, object]] = []
    for cycle, relpath in CYCLES:
        source_path = source_repo / relpath
        if not source_path.exists():
            raise FileNotFoundError(f"missing OpenElections source file for {cycle}: {source_path}")
        dest_path = dest_dir / Path(relpath).name
        shutil.copyfile(source_path, dest_path)
        digest = hashlib.sha256(dest_path.read_bytes()).hexdigest()
        try:
            commit = subprocess.check_output(
                ["git", "-C", str(source_repo), "rev-parse", "HEAD"], text=True).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            commit = "unknown"
        report.append({"cycle": cycle, "source": str(source_path), "dest": str(dest_path),
                       "bytes": dest_path.stat().st_size, "sha256": digest,
                       "source_commit": commit,
                       "retrieved_utc": datetime.now(timezone.utc).isoformat()})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-repo", type=Path, default=None,
                         help="Path to the openelections-data-al checkout "
                              "(default: ../openelections-data-al next to this repo)")
    args = parser.parse_args()
    root = args.root
    source_repo = args.source_repo or (root.parent / "openelections-data-al")
    if not source_repo.exists():
        raise FileNotFoundError(f"openelections-data-al checkout not found at {source_repo}")
    report = sync(source_repo, root / "data" / "raw" / "openelections")
    import pandas as pd
    pd.DataFrame(report).to_csv(root / "data" / "raw" / "openelections" /
                                "source_manifest.csv", index=False)
    for row in report:
        print(f"{row['cycle']}: {row['dest']} ({row['bytes']:,} bytes)")


if __name__ == "__main__":
    main()
