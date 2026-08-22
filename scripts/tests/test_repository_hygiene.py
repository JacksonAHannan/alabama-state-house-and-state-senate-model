from audit_repository_hygiene import failures
from project import TARGETS


def test_publication_boundary_has_no_legacy_exports():
    assert failures() == []


def test_canonical_targets_are_explicit_and_current():
    assert set(TARGETS) == {"cmo", "forecast", "site"}
    assert TARGETS["cmo"][0] == "rebuild_cmo_war_analogue.py"
    assert "rebuild_cmo_direct_estimand.py" not in TARGETS["cmo"]
    assert "rebuild_cmo_methodology_v2.py" not in TARGETS["cmo"]
