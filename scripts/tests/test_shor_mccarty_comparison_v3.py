from compare_shor_mccarty_to_ontology_v3 import CONSERVATIVE_DIRECTION


def test_conservative_orientation_distinguishes_opposite_issue_axes():
    assert CONSERVATIVE_DIRECTION["gun_access"] == 1
    assert CONSERVATIVE_DIRECTION["abortion_access"] == -1
    assert CONSERVATIVE_DIRECTION["welfare_generosity"] == -1
    assert "resource_management" not in CONSERVATIVE_DIRECTION
