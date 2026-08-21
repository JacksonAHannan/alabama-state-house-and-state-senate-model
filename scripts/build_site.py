"""Build every public page and its standalone local counterpart."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDERS = [
    "build_2026_forecast_dashboard.py",
    "build_war_story_page.py",
    "build_legislator_ideology_page.py",
    "build_ideology_performance_page.py",
]


def main() -> None:
    for builder in BUILDERS:
        print(f"Building with scripts/{builder}")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / builder)],
            cwd=ROOT,
            check=True,
        )
    print("Site build complete: docs/")


if __name__ == "__main__":
    main()
