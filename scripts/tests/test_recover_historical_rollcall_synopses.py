from scripts.recover_historical_rollcall_synopses import page_window


def test_page_window_invalid_page_is_empty():
    assert page_window(object(), None) == ""
