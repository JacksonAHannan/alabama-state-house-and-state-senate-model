from scripts.audit_repository_paths import ROOT, violations
from scripts.build_site import BUILDERS


def test_no_retired_path_references():
    assert violations() == []


def test_site_builders_exist():
    assert all((ROOT / "scripts" / builder).is_file() for builder in BUILDERS)


def test_public_site_and_project_docs_are_separate():
    assert not (ROOT / "docs" / "superpowers").exists()
    assert (ROOT / "project_docs" / "development").is_dir()
