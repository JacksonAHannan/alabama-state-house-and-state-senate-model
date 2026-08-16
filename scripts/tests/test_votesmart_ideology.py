from unittest.mock import Mock

import pytest

from download_votesmart_ideology import (
    VoteSmartClient,
    VoteSmartError,
    candidate_ids,
    parse_years,
    response_rows,
)


def test_parse_years_deduplicates_and_sorts():
    assert parse_years("2022,1994,1998,1994") == (1994, 1998, 2022)


def test_response_rows_supports_current_data_wrapper():
    rows = [{"candidateId": 10}, {"candidateId": "11"}]
    assert response_rows({"data": rows, "meta": {"lastPage": 1}}) == rows
    assert candidate_ids({"data": rows}) == [10, 11]


def test_client_paginates_using_api_metadata():
    session = Mock()
    first = Mock(status_code=200)
    first.json.return_value = {"data": [{"candidateId": 1}], "meta": {"lastPage": 2}}
    second = Mock(status_code=200)
    second.json.return_value = {"data": [{"candidateId": 2}], "meta": {"lastPage": 2}}
    session.get.side_effect = [first, second]
    session.headers = {}

    snapshot = VoteSmartClient("secret", session=session).get_all("/endpoint", {})

    assert len(snapshot["pages"]) == 2
    assert session.get.call_args_list[0].kwargs["params"]["page"] == 1
    assert session.get.call_args_list[1].kwargs["params"]["page"] == 2
    assert "secret" not in repr(snapshot)


def test_client_explains_unauthorized_response():
    session = Mock()
    response = Mock(status_code=401)
    session.get.return_value = response
    session.headers = {}
    with pytest.raises(VoteSmartError, match="rejected the bearer token"):
        VoteSmartClient("bad-token", session=session).get("/endpoint", {})
