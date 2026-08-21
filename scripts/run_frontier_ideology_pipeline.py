"""Rebuild the direct-vote frontier ideology layer and analyses end to end."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    "build_frontier_archive_bill_ledger.py",
    "recover_historical_rollcall_synopses.py",
    "build_comprehensive_rollcall_classifications.py",  # identity/motion substrate only
    "build_historical_frontier_rollcall_ontology.py",
    "build_frontier_rollcall_ontology.py",
    "build_full_candidate_legislative_ideology.py",
    "build_legislative_position_evidence_v3.py",
    "build_candidate_position_evidence_v3.py",
    "build_candidate_issue_valence_v3.py",
    "adjudicate_candidate_issue_conflicts_v3.py",
    "integrate_candidate_ideology_v3.py",
    "run_issue_stance_tournament.py",
    "analyze_issue_stance_durable_overperformance.py",
    "run_headline_ideology_tournament.py",
    "analyze_ideological_bundle_performance.py",
    "analyze_democratic_ideological_clusters.py",
    "analyze_ideology_thesis.py",
    "build_ideology_performance_page.py",
    "build_legislator_ideology_page.py",
    "validate_frontier_ideology_integration.py",
]
TESTS = [
    "scripts/tests/test_frontier_archive_bill_ledger.py",
    "scripts/tests/test_historical_frontier_rollcall_ontology.py",
    "scripts/tests/test_frontier_rollcall_ontology.py",
    "scripts/tests/test_legislative_position_evidence_v3.py",
    "scripts/tests/test_candidate_position_ontology_v3.py",
    "scripts/tests/test_candidate_issue_valence_v3.py",
    "scripts/tests/test_integrate_candidate_ideology_v3.py",
    "scripts/tests/test_candidate_ideology_storage_invariants.py",
    "scripts/tests/test_issue_stance_tournament.py",
    "scripts/tests/test_issue_stance_durable_overperformance.py",
    "scripts/tests/test_ideology_performance_page.py",
    "scripts/tests/test_ideological_bundle_performance.py",
]


def main() -> None:
    for step in STEPS:
        print(f"\n==> {step}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / step)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "pytest", *TESTS, "-q"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
