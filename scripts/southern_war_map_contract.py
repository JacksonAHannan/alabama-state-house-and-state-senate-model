"""Prespecified 2016-2022 Southern WAR map schedule and state metadata."""
from __future__ import annotations


STATE_FIPS = {
    "AL": "01", "AR": "05", "FL": "12", "GA": "13", "KY": "21",
    "LA": "22", "MO": "29", "MS": "28", "NC": "37", "OK": "40",
    "SC": "45", "TN": "47", "TX": "48", "VA": "51",
}


def scheduled_keys_2016_2022() -> set[tuple[str, int, str]]:
    """Return the 90 regular-election state/cycle/chamber map slices."""
    keys: set[tuple[str, int, str]] = set()
    for state in ("AR", "FL", "GA", "KY", "MO", "NC", "OK", "TN", "TX"):
        for cycle in (2016, 2018, 2020, 2022):
            keys.update({(state, cycle, "lower"), (state, cycle, "upper")})
    for cycle in (2018, 2022):
        keys.update({("AL", cycle, "lower"), ("AL", cycle, "upper")})
    for state in ("LA", "MS"):
        keys.update({(state, 2019, "lower"), (state, 2019, "upper")})
    for cycle in (2016, 2018, 2020, 2022):
        keys.add(("SC", cycle, "lower"))
    for cycle in (2016, 2020):
        keys.add(("SC", cycle, "upper"))
    for cycle in (2017, 2019, 2021):
        keys.add(("VA", cycle, "lower"))
    keys.add(("VA", 2019, "upper"))
    if len(keys) != 90:
        raise AssertionError(f"Southern WAR map schedule changed unexpectedly: {len(keys)}")
    return keys
