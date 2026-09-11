from audit_repository_hygiene import failures


def test_publication_boundary_has_no_legacy_exports():
    assert failures() == []
