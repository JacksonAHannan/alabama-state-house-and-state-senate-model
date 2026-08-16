import pandas as pd

from scripts.backtest_ces_polling_transfer import fit_pooled_beta, inv_logit, logit


def test_logit_round_trip_and_clipping():
    assert abs(inv_logit(logit(0.7)) - 0.7) < 1e-12
    assert logit(0) == logit(0.01)
    assert logit(1) == logit(0.99)


def test_empty_history_uses_unit_transfer():
    assert fit_pooled_beta(pd.DataFrame()) == 1.0


def test_pooled_beta_is_shrunk_and_bounded():
    history = pd.DataFrame({
        "national_signal_logit": [0.1, 0.2],
        "actual_change_logit": [0.2, 0.4],
        "effective_n_actual": [100, 100],
    })
    beta = fit_pooled_beta(history)
    assert 1 < beta < 2
