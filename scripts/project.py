"""Canonical command surface for the Alabama legislative-model repository."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "cmo": ["rebuild_cmo_war_analogue.py", "analyze_absolute_ideology_rebuild.py", "build_war_story_page.py"],
    "site": ["build_blue_oxblood_site.py"],
    "forecast": ["build_2026_forecast_dashboard.py"],
}


def run_script(name: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / name)], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build one canonical product")
    build.add_argument("target", choices=sorted(TARGETS))
    sub.add_parser("audit", help="Run repository-hygiene checks")
    sub.add_parser("test", help="Run the complete pytest suite")
    args = parser.parse_args()

    if args.command == "build":
        for script in TARGETS[args.target]:
            run_script(script)
    elif args.command == "audit":
        run_script("audit_repository_hygiene.py")
    else:
        subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
