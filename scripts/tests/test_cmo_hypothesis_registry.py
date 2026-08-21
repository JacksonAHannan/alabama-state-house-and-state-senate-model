from scripts.validate_cmo_hypothesis_registry import validate


def test_cmo_hypothesis_registry_is_valid():
    assert validate() == []
