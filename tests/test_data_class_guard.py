"""Point 10: the data class guard (design section 8, DATA_CLASS_MISMATCH).

The brief's two cases (no data_class column; a row saying VERIFIED_OFFICIAL) plus copies
added by the tests session, listed in support.NOT_SYNTHETIC_COPIES: the changed row sits
first, last or in the middle, has another wrong value, is empty, or every row is wrong.
"""
import pytest

from support import (NOT_SYNTHETIC_COPIES, ROUTER_DIRECT, ROUTER_RULES, SKILL, SUPPORTED, ask,
                     call, check_refused, expected_values, snapshot_of, standalone)


def check_no_count_leaked(d):
    """A refusal "contains no computed number": not the total the rows would have given."""
    would_be_total = str(expected_values(2025, "18_25")["total"])
    assert not standalone(would_be_total, d["user_facing_summary"]), d["user_facing_summary"]


@pytest.mark.parametrize("make_bad_copy", NOT_SYNTHETIC_COPIES.values(), ids=NOT_SYNTHETIC_COPIES)
def test_execute_call_refuses_data_that_is_not_synthetic(make_bad_copy, tmp_path, runs_dir):
    bad = make_bad_copy(tmp_path)
    d = check_refused(call(SKILL, {"year": 2025, "age_group": "18_25"}, runs_dir, data_path=bad),
                      runs_dir, question="", router=ROUTER_DIRECT, status="ERROR",
                      code="DATA_CLASS_MISMATCH", data_path=bad)
    assert d["snapshot_id"] == snapshot_of(bad)  # the file could be read
    check_no_count_leaked(d)


@pytest.mark.parametrize("make_bad_copy", NOT_SYNTHETIC_COPIES.values(), ids=NOT_SYNTHETIC_COPIES)
def test_answer_question_refuses_data_that_is_not_synthetic(make_bad_copy, tmp_path, runs_dir):
    bad = make_bad_copy(tmp_path)
    question, _, _ = SUPPORTED["S1"]
    d = check_refused(ask(question, runs_dir, data_path=bad), runs_dir, question=question,
                      router=ROUTER_RULES, status="ERROR", code="DATA_CLASS_MISMATCH",
                      data_path=bad)
    assert d["snapshot_id"] == snapshot_of(bad)
    check_no_count_leaked(d)
