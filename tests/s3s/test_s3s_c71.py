"""S3S C71 (D-089): a yes-or-no analysis whose factors say the same thing as each other is
refused before R runs.

Found on 19 November 2026 on the live code: asked "what are arrests most associated with
being at night?", the model gave both "male" and "female" as factors; every record is one or
the other, so R could not tell them apart and stopped (ENGINE_FAILED). Written by the planning
chat (no separate tests session, by D-089)."""
import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import EDGES, Q_TREND, StatsEnv, analyze, job_folders

from moco_agent import stats

MALE = T.is_("gender", "male")
SHIFT_A = T.is_("shift", "shift A")
ZONE_1, ZONE_2 = T.is_("zone", "zone 1"), T.is_("zone", "zone 2")


def _args(factors, controls=()):
    args = T.analyze_arguments("yn_k110")
    args["filters"] = T.batch("K110")
    args["options"] = {"outcome": T.SCHOOL, "factors": factors, "controls": list(controls)}
    return args


def test_the_fixture_has_only_two_genders_and_two_shifts():
    """No program code: in batch K110 every record is male or female, and shift A or B."""
    rows = [r for r in T.fixture_rows(EDGES) if r.get("batch") == "K110"]
    assert {r["gender"] for r in rows} == {"Male", "Female"}
    assert {r["shift"] for r in rows} == {"A", "B"}
    assert len({r["zone"] for r in rows}) > 2


@pytest.mark.parametrize("factors", [[T.FEMALE, MALE], [SHIFT_A, T.SHIFT_B],
                                     [T.WEAPON, T.FEMALE, MALE]],
                         ids=["both genders", "both shifts", "both genders beside another"])
def test_factors_that_say_the_same_thing_are_refused_before_r(tmp_path, monkeypatch, factors):
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    env.ask(Q_TREND, Step(analyze(_args(factors))), Step(finish("finding", "I found that.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "BAD_OPTIONS", answer
    assert "result_id" not in answer
    assert "say the same thing" in str(answer), answer
    assert job_folders(env) == [], "R is not started for factors it cannot tell apart"


@pytest.mark.needs_r
def test_two_values_of_a_wider_field_still_run(tmp_path, monkeypatch):
    """Two zones out of six do not cover every record, so they can be told apart: no refusal."""
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    reply = env.ask(Q_TREND, Step(analyze(_args([ZONE_1, ZONE_2]))),
                    Step(finish("finding", "{a1.odds.1}.")))
    assert env.model.answer(0).get("result_id") == "a1", env.model.answer(0)
    # (answered() is not used: its figure check reads the labels "zone 1" and "zone 2" as counts)
    assert reply.status == "ANSWERED", (reply.status, reply.text)
    assert "odds ratio" in reply.text


def test_rank_by_hand():
    # lines are [outcome, factor 1, ..., control 1, ...]
    both = [[0, 1, 0], [1, 0, 1], [0, 1, 0], [1, 0, 1]]  # factor 2 = 1 - factor 1
    assert stats._rank(both, 2, []) == 2  # the intercept and one factor; full would be 3
    apart = [[0, 1, 0], [1, 0, 1], [0, 0, 0], [1, 1, 1]]
    assert stats._rank(apart, 2, []) == 3
    # a factor that is the same as a control level: zone b is exactly factor 1
    alias = [[0, 1, "b"], [1, 0, "a"], [0, 0, "a"], [1, 1, "b"]]
    assert stats._rank(alias, 1, [["a", "b"]]) == 2  # full would be 3
    mixed = [[0, 1, "b"], [1, 0, "a"], [0, 0, "b"], [1, 1, "a"]]
    assert stats._rank(mixed, 1, [["a", "b"]]) == 3
