from __future__ import annotations

import pandas as pd

from scripts.analyze_historical_shor_mccarty_cmo import cluster_ols, normalize, surname


def test_name_normalization_handles_order_quotes_and_suffixes() -> None:
    assert normalize('JOHN "JODY" LETSON, JR.') == "jody john letson"
    assert normalize("Letson, John (Jody)") == "john letson"
    assert surname('JOHN "JODY" LETSON, JR.') == "letson"
    assert surname("Letson, John") == "letson"


def test_cluster_ols_recovers_positive_relationship() -> None:
    frame = pd.DataFrame({
        "person_id": [f"p{i}" for i in range(20)],
        "cycle": [1998] * 10 + [2002] * 10,
        "chamber": ["house", "senate"] * 10,
        "shor_np_z": list(range(20)),
        "outcome": [3 * i + (i % 2) for i in range(20)],
    })
    result = cluster_ols(frame, "outcome", ["cycle", "chamber"])
    assert result["status"] == "estimated"
    assert result["coefficient_per_sd"] > 2.5


def test_published_panel_keeps_1994_out_of_headline_tier() -> None:
    panel = pd.read_csv("research/cmo_ideology/historical_shor_mccarty_analysis_panel.csv")
    assert panel.loc[panel.cycle.eq(1994), "temporal_status"].eq("1994_later_observed_sensitivity").all()
    estimates = pd.read_csv("research/cmo_ideology/historical_shor_mccarty_estimates.csv")
    headline = estimates[estimates["sample"].eq("headline_1998_2018")]
    assert headline.n.max() <= panel.cycle.between(1998, 2018).sum()

