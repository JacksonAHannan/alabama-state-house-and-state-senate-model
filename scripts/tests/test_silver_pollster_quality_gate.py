import pandas as pd

from build_silver_pollster_quality_gate import attach_grades


def test_quality_gate_is_exact_and_does_not_inherit_combination_grade():
    ratings = pd.DataFrame([
        {"Pollster": "Echelon Insights", "Grade": "A-@@3", "Predictive Plus-Minus": -0.2,
         "Number of polls": 10},
        {"Pollster": "Marist College", "Grade": "A-@@3", "Predictive Plus-Minus": -0.1,
         "Number of polls": 20},
    ])
    queue = pd.DataFrame({"pollster": ["Echelon Insights", "Echelon Insights/GBAO", "Marist University"]})
    out = attach_grades(queue, ratings).set_index("pollster")
    assert bool(out.loc["Echelon Insights", "b_plus_or_better"])
    assert not bool(out.loc["Echelon Insights/GBAO", "b_plus_or_better"])
    assert bool(out.loc["Marist University", "b_plus_or_better"])
