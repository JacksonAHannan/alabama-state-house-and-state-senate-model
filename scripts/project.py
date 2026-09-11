"""Partial convenience CLI; see project_docs/CANONICAL_PIPELINES.md for validated routes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "site": ["build_blue_oxblood_site.py"],
    "forecast": ["build_2026_forecast_dashboard.py"],
}


def run_script(name: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / name)], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Run an existing publication renderer (not source or model validation)")
    build.add_argument("target", choices=sorted(TARGETS))
    build.add_argument("--publish", action="store_true", help="Explicitly allow writes under docs/; required release approval remains separate")
    sub.add_parser("audit", help="Run repository-hygiene checks")
    sub.add_parser("test", help="Run the complete pytest suite")
    args = parser.parse_args()

    if args.command == "build":
        if not args.publish:
            parser.error("build targets write publication files; --publish requires separately reviewed release approval. See project_docs/CANONICAL_PIPELINES.md for scoped artifact commands.")
        for script in TARGETS[args.target]:
            run_script(script)
    elif args.command == "audit":
        run_script("audit_repository_hygiene.py")
    else:
        subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
