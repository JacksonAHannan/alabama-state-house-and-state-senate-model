"""Run the reproducible legislative-position pipeline in dependency order."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ["recover_historical_rollcall_synopses.py",
         "build_comprehensive_rollcall_classifications.py",
         "build_comprehensive_legislative_actions.py",
         "build_full_candidate_legislative_ideology.py"]


def main() -> None:
    for step in STEPS:
        print(f"\n==> {step}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / step)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "pytest",
                    "scripts/tests/test_comprehensive_rollcall_classifications.py",
                    "scripts/tests/test_recover_historical_rollcall_synopses.py",
                    "scripts/tests/test_comprehensive_legislative_actions.py",
                    "scripts/tests/test_full_candidate_legislative_ideology.py", "-q"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
