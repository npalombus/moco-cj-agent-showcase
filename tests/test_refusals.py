"""Point 8: the ten agreed refused questions U1-U10 (design sections 8 and 10)."""
import pytest

from support import REFUSED, ROUTER_RULES, ask, check_refused, record


@pytest.mark.parametrize("uid", REFUSED)
def test_refused_question(uid, runs_dir):
    """UNSUPPORTED with the listed code, empty computed_values, no chart, a saved manifest."""
    question, code = REFUSED[uid]
    check_refused(ask(question, runs_dir), runs_dir, question=question, router=ROUTER_RULES,
                  status="UNSUPPORTED", code=code)


def test_u6_does_not_repeat_the_figure_it_was_told_to_state(runs_dir):
    question, _ = REFUSED["U6"]
    d = record(ask(question, runs_dir))
    assert d["status"] == "UNSUPPORTED"
    assert "50" not in d["user_facing_summary"]
