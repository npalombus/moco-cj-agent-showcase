"""TOO_LITTLE: every threshold of docs/S3S-DESIGN.md S1 at its edge, and that the error and
the reply say which.

  T             fewer than 24 full months (23 refused, 24 run), or under 100 records in all
                (99 refused, 100 run)
  L             fewer than 100 yes cases or 100 no cases (99 refused, 100 run each); fewer than
                10 of the rarer outcome per estimated coefficient
  S             a year with under 100 records in the base (99 refused, 100 run)
  distribution  a group under 30 usable ages (29 refused; 30 run: test_s3s_timing_ages.py)

Each refused case is refused before R is started (no job folder). The error answer names the
threshold (its number is in it) and holds no value from the data (not the 99 or 29 it
counted); the reply's reason code is TOO_LITTLE and its text names the threshold's number
(the fixed text is not given: QUESTIONS.md, 10).

Per coefficient: whether the intercept is counted is asked (QUESTIONS.md, 3). The cases that
are refused or answered under both readings are tested; the two that depend on it are
skipped with the question's number.
"""
import json

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import (EDGES, EDGES_ID, MAIN, Q_TREND, StatsEnv, analyze, answered, ask_case,
                      job_folders)


def _args(name, filters=None, options=None, period=None):
    args = T.analyze_arguments(name)
    if filters is not None:
        args["filters"] = filters
    if options is not None:
        args["options"] = options
    if period is not None:
        args["period"] = period
    return args


L_OPTIONS = {"outcome": T.SCHOOL, "factors": [T.SHIFT_B], "controls": []}
K2 = {"outcome": T.SCHOOL, "factors": [T.WEAPON, T.SHIFT_B], "controls": ["zone"]}
K3 = {"outcome": T.SCHOOL, "factors": [T.WEAPON, T.SHIFT_B, T.FEMALE], "controls": ["zone"]}

# label: (source, analyze arguments, the threshold's number, a data value that must not show)
REFUSED = {
    "23 full months": (MAIN, _args("trend_23"), "24", None),
    "99 records": (EDGES, _args("trend_r099"), "100", "99"),
    "99 yes cases": (EDGES, _args("yn_k110", T.batch("Y099"), L_OPTIONS), "100", "99"),
    "99 no cases": (EDGES, _args("yn_k110", T.batch("N099"), L_OPTIONS), "100", "99"),
    "9.09 a coefficient either way": (EDGES, _args("yn_k110", T.batch("K100"), K3), "10", None),
    "a base year of 99": (EDGES, _args("sh_s100", T.batch("S099")), "100", "99"),
    "29 usable ages": (EDGES, _args("ages_d30", T.batch("D29")), "30", "29"),
}
ANSWERED = {
    "24 full months": (MAIN, _args("trend_24")),
    "100 records": (EDGES, _args("trend_r100")),
    "100 yes cases": (EDGES, _args("yn_k110", T.batch("Y100"), L_OPTIONS)),
    "100 no cases": (EDGES, _args("yn_k110", T.batch("N100"), L_OPTIONS)),
    "10.0 a coefficient either way": (EDGES, _args("yn_k110", T.batch("K110"), K2)),
    "a base year of 100": (EDGES, _args("sh_s100")),
}
WAITING = {  # answered without the intercept, refused with it
    "K100, 2 factors: 10.0 without the intercept, 9.09 with it":
        (EDGES, _args("yn_k110", T.batch("K100"), K2)),
    "K109, 2 factors: 10.9 without the intercept, 9.91 with it":
        (EDGES, _args("yn_k110", T.batch("K109"), K2)),
}


def _rows(name, b):
    src = T.source_json(name)
    return [r for r in T.fixture_rows(name) if r.get("batch") == b] if "batch" in str(
        src["fields"]) else []


def test_the_edges_by_counting():
    """No program code: each edge is where the fixture says."""
    assert len(T.window(T.source_json(MAIN), T.case("trend_23")["period"])) == 23
    assert len(T.window(T.source_json(MAIN), T.case("trend_24")["period"])) == 24
    assert len(_rows(EDGES, "R099")) == 99 and len(_rows(EDGES, "R100")) == 100
    for b, yes, no in (("Y099", 99, 400), ("Y100", 100, 400), ("N099", 400, 99),
                       ("N100", 400, 100), ("K100", 100, 400), ("K109", 109, 400),
                       ("K110", 110, 400)):
        flags = [r["adjacent_to_school"] for r in _rows(EDGES, b)]
        assert (flags.count("1"), flags.count("0")) == (yes, no), b
    # coefficients besides the intercept: factors, then the nine zones less the reference
    assert len(K2["factors"]) + 8 == 10 and len(K3["factors"]) + 8 == 11
    by_year = [sum(1 for r in _rows(EDGES, "S099") if r["event_date_time"].startswith(str(y)))
               for y in range(2021, 2026)]
    assert min(by_year) == 99
    women = [r for r in _rows(EDGES, "D29") if r["gender"] == "Female"
             and r.get("age", "").isdigit() and 10 <= int(r["age"]) <= 98]
    assert len(women) == 29


@pytest.mark.parametrize("label", list(REFUSED))
def test_refused_at_the_edge(tmp_path, monkeypatch, label):
    source, args, number, value = REFUSED[label]
    env = StatsEnv(tmp_path, monkeypatch, names=(source,))
    reply = env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "I found that.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "TOO_LITTLE", (label, answer)
    assert "result_id" not in answer
    text = json.dumps(answer)
    assert number in text, f"the error must say which threshold ({number}): {answer}"
    if value:
        assert value not in text.replace(number, ""), f"a value from the data: {answer}"
    assert job_folders(env) == [], "R is not started for an analysis with too little data"
    assert reply.reason_code == "TOO_LITTLE", (reply.status, reply.reason_code, reply.text)
    assert reply.status != "ANSWERED"
    assert number in reply.text, f"the reply must say which threshold ({number}): {reply.text}"
    if value:
        assert value not in reply.text.replace(number, ""), reply.text


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(ANSWERED))
def test_answered_at_the_edge(tmp_path, monkeypatch, label):
    source, args = ANSWERED[label]
    env = StatsEnv(tmp_path, monkeypatch, names=(source,))
    kind = args["kind"]
    text = {"trend": "{a1.trend}.", "yes_no": "{a1.odds.1}.", "shares": "{a1.share}."}[kind]
    reply = env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", text)))
    answer = env.model.answer(0)
    assert answer.get("result_id") == "a1", (label, answer)
    answered(reply)


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(WAITING))
def test_per_coefficient_edge_does_not_count_the_intercept(tmp_path, monkeypatch, label):
    """Question 3, answered in docs/S3S-DESIGN.md S10 (answer 3): the intercept is not
    counted, so 10.0 and 10.9 of the rarer outcome per coefficient are both answered.
    Written by the planning chat in place of the test the tests session left skipped."""
    source, args = WAITING[label]
    env = StatsEnv(tmp_path, monkeypatch, names=(source,))
    reply = env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "{a1.odds.1}.")))
    answer = env.model.answer(0)
    assert answer.get("result_id") == "a1", (label, answer)
    answered(reply)


def test_the_ids_are_the_edges_source():
    assert EDGES_ID == "FIXTURE:stats_edges"
