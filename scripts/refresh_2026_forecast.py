"""Refresh polling, both 2026 forecast views, simulations, and site exports."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    command = [sys.executable, *args]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--from-date",
        default=(date.today() - timedelta(days=60)).isoformat(),
        help="Earliest VoteHub poll field date (default: 60 days ago).",
    )
    parser.add_argument(
        "--skip-document-downloads",
        action="store_true",
        help="Refresh VoteHub metadata without downloading linked documents.",
    )
    args = parser.parse_args()

    inventory = [
        "scripts/build_votehub_crosstab_source_inventory.py",
        "--from-date",
        args.from_date,
    ]
    if not args.skip_document_downloads:
        inventory.extend(["--download", "--workers", "8"])
    run(*inventory)
    run("scripts/build_silver_pollster_quality_gate.py")
    run("scripts/refresh_yougov_generic_ballot.py")
    run("scripts/build_silver_bplus_polling_environment.py")
    run("scripts/build_2026_catalist_yougov_transfer.py")
    run("scripts/build_2026_poll_adjusted_baseline.py")
    run("scripts/fit_2026_prospective_model.py")
    run("scripts/run_next_forecast_tournaments.py")
    run("scripts/build_2026_forecast_dashboard.py")


if __name__ == "__main__":
    main()
