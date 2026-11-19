"""The `analyze` tool: docs/S3S-DESIGN.md S1 (offered in county mode only; each `kind` with
its `options`; BAD_OPTIONS; at most two calls a turn; the model answered with `result_id`,
`read_as` and `slots` and no value), C5 and C9 of docs/S3A-DESIGN.md (`source`, `period` and
`filters` checked as Part A checks them; filling from memory). TOO_LITTLE is in
test_s3s_too_little.py, TOO_FINE in test_s3s_charts.py, ENGINE_MISSING and ENGINE_FAILED in
test_s3s_engine.py.

Readings: the option shapes of s3ssupport's module text; the slots of s3sagent's. A spec
refused with BAD_OPTIONS is refused before R is started: no job folder is made. Which error
a third `analyze` call gets is not said: any error, and no third result.
"""
import json
import re

import pytest

import p1support as p1
import s3ssupport as T
from p1support import Step, finish
from s3sagent import (EDGES_ID, MAIN, MAIN_ID, QUESTION, Q_TREND, StatsEnv, analyze,
                      analyze_case, answered, assert_estimates, job_folders, slots)
from s3support import KEPT_ANY, count, guard_free

KIND_CASES = ["trend_all", "compare_school", "ba_d6", "yn_main", "sh_school", "timing",
              "ages_gender"]
TOOL_PARTS = {"kind", "source", "period", "filters", "options"}


def test_every_question_passes_the_guard():
    """A premise: stage 1's guard neither refuses nor restricts the tests' questions."""
    for question in QUESTION.values():
        guard_free(question)


def test_analyze_is_offered_in_county_mode(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    env.ask(Q_TREND, Step(finish("finding", "I found that.")))
    offered = {t["function"]["name"]: t for t in env.model.calls[0]["tools"]}
    assert "analyze" in offered, sorted(offered)
    properties = offered["analyze"]["function"]["parameters"]["properties"]
    assert TOOL_PARTS <= set(properties), sorted(properties)
    assert {"count", "share", "compare", "describe_data", "ask_user", "show_details",
            "decline", "finish"} <= set(offered)


def test_analyze_is_not_offered_in_synthetic_mode(tmp_path):
    """S0 with C0: county mode only; stage 2's synthetic turn is unchanged."""
    env = p1.Env(tmp_path)
    env.ask("How many arrests were recorded each month in 2025?",
            p1.Step(p1.count(2025, "all")), p1.Step(p1.finish("finding", p1.ONE_COUNT_TEXT)))
    assert "analyze" not in env.model.tools_offered(0)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", KIND_CASES)
def test_each_kind_is_answered_with_an_id_a_reading_and_slots(tmp_path, monkeypatch, name):
    """S1: a good call makes a1; Python answers {"result_id", "read_as", "slots"} and nothing
    else, with no value from the data (no decimal, no count) in it."""
    env = StatsEnv(tmp_path, monkeypatch)
    env.ask(QUESTION[T.case(name)["kind"]], Step(analyze_case(name)),
            Step(finish("finding", " ".join(f"{s}." for s in slots(name)))))
    answer = env.model.answer(0)
    assert set(answer) == {"result_id", "read_as", "slots"}, answer
    assert answer["result_id"] == "a1" and answer["slots"] == slots(name), answer
    assert isinstance(answer["read_as"], str) and answer["read_as"].strip()
    text = json.dumps(answer)
    assert not re.search(r"\d+\.\d+", text), text
    for n in (T.truth(name)["records"],):
        assert f"{n:,}" not in text and str(n) not in text, (n, text)


def _bad(change=None, **arguments):
    def make(name):
        args = T.analyze_arguments(name)
        args.update(arguments)
        if change:
            change(args)
        return args
    return make


def _drop(key):
    return lambda args: args.pop(key, None)


def _set_options(**options):
    def change(args):
        args["options"] = options
    return change


def _no_options(args):
    args.pop("options", None)


BAD_OPTIONS = {
    "trend with a date": ("trend_all", _set_options(date="2023-07-01")),
    "trend with an unknown option": ("trend_all", _set_options(colour="blue")),
    "trend_compare with no versus": ("compare_school", _no_options),
    "versus differing in two fields": ("compare_school", _set_options(
        versus=[T.is_(T.SCHOOL, False), T.is_(T.WEAPON, True)])),
    "versus differing in no field": ("compare_school", _set_options(
        versus=[T.is_(T.SCHOOL, True)])),
    "before_after with no date": ("ba_d6", _no_options),
    "a date not on the 1st": ("ba_d6", _set_options(date="2023-07-15")),
    "a date in words": ("ba_d6", _set_options(date="July 2023")),
    "yes_no with no outcome": ("yn_main", _set_options(factors=[T.WEAPON], controls=[])),
    "yes_no with no factor": ("yn_main", _set_options(outcome=T.SCHOOL, factors=[],
                                                      controls=[])),
    "seven factors": ("yn_main", _set_options(
        outcome=T.SCHOOL, controls=[],
        factors=[T.WEAPON, T.FEMALE, T.SHIFT_B, "under_18", "weekend", "night",
                 T.is_("district", "district 2")])),
    "four controls": ("yn_main", _set_options(outcome=T.SCHOOL, factors=[T.WEAPON],
                                              controls=["district", "shift", "gender",
                                                        "year"])),
    "a flag as a control": ("yn_main", _set_options(outcome=T.SCHOOL, factors=[T.FEMALE],
                                                    controls=[T.WEAPON])),
    "a category outcome with no label": ("yn_main", _set_options(
        outcome={"field": "gender"}, factors=[T.WEAPON], controls=[])),
    "an age as the outcome": ("yn_main", _set_options(outcome="age", factors=[T.WEAPON],
                                                      controls=[])),
    "shares with no part": ("sh_school", _no_options),
    "shares with an empty part": ("sh_school", _set_options(part=[])),
    "distribution by age": ("ages", _set_options(by="age")),
    "timing with an option": ("timing", _set_options(by="gender")),
}


@pytest.mark.parametrize("label", list(BAD_OPTIONS))
def test_bad_options(tmp_path, monkeypatch, label):
    """S1's BAD_OPTIONS: options missing, unknown, or not allowed for the kind. The turn goes
    on, no result is made and R is not started."""
    name, change = BAD_OPTIONS[label]
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments(name)
    change(args)
    env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "I found that.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "BAD_OPTIONS", (label, answer)
    assert "result_id" not in answer
    assert len(env.model.calls) == 2, "the turn goes on after a tool error"
    assert job_folders(env) == []


def _no_age(src):
    src["fields"] = [f for f in src["fields"] if f["kind"] != "age"]


@pytest.mark.parametrize("name,options", [
    ("yn_main", {"outcome": "under_18", "factors": [T.WEAPON], "controls": []}),
    ("ages", {}),
])
def test_options_not_allowed_for_the_source(tmp_path, monkeypatch, name, options):
    """S1: "not allowed ... for the source": `under_18` and `distribution` on a source with no
    age field are BAD_OPTIONS."""
    env = StatsEnv(tmp_path, monkeypatch, change={MAIN: _no_age})
    args = T.analyze_arguments(name)
    if options:
        args["options"] = options
    env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "I found that.")))
    assert env.model.answer(0).get("error") == "BAD_OPTIONS", env.model.answer(0)


@pytest.mark.parametrize("label,change,code", [
    ("an unknown field", lambda a: a.update(filters=[T.is_("colour", "red")]), "BAD_FIELD"),
    ("a key field", lambda a: a.update(filters=[T.is_("id", "x")]), "BAD_FIELD"),
    ("an unknown label", lambda a: a.update(filters=[T.is_("district", "district 9")]),
     "BAD_VALUE"),
    ("a range the wrong way round", lambda a: a.update(period={"from": "2025-12-31",
                                                               "to": "2021-01-01"}),
     "BAD_VALUE"),
    ("a period outside the copy", lambda a: a.update(period={"years": [2012, 2013]}),
     "OUT_OF_COVERAGE"),
    ("an age filter under 18 narrower than two years",
     lambda a: a.update(filters=[{"field": "age", "from": 16, "to": 16}]), "NOT_ALLOWED"),
])
def test_source_period_and_filters_are_checked_as_part_a(tmp_path, monkeypatch, label, change,
                                                        code):
    """S1: `source`, `period` and `filters` are exactly C5's, with the same errors."""
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("trend_all")
    change(args)
    env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "I found that.")))
    assert env.model.answer(0).get("error") == code, (label, env.model.answer(0))


def test_an_unknown_source_is_refused(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("trend_all")
    args["source"] = EDGES_ID  # not in this agent's sources folder
    env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "I found that.")))
    answer = env.model.answer(0)
    assert "error" in answer and "result_id" not in answer, answer


@pytest.mark.needs_r
def test_at_most_two_analyze_calls_a_turn(tmp_path, monkeypatch):
    """S1: a third `analyze` call in the turn is refused (an error, no a3)."""
    env = StatsEnv(tmp_path, monkeypatch)
    env.ask(Q_TREND, Step(analyze_case("timing")), Step(analyze_case("ages")),
            Step(analyze_case("trend_all")), Step(finish("finding", "{a1.timing}.")))
    first, second, third = (env.model.answer(i) for i in range(3))
    assert (first.get("result_id"), second.get("result_id")) == ("a1", "a2")
    assert "error" in third and "result_id" not in third, third
    assert len(job_folders(env)) == 2


@pytest.mark.needs_r
def test_period_and_filters_are_filled_from_memory(tmp_path, monkeypatch):
    """S1 with C9: an `analyze` call that leaves out the period and the filters takes them
    from the last answer (here a count of district 1 over 2021 to 2025); the kept note says
    so; the result is the trend of district 1."""
    env = StatsEnv(tmp_path, monkeypatch)
    first = env.ask("How many arrests were there in district 1 from 2021 to 2025?",
                    Step(count(MAIN_ID, T.P5, T.district(1))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED", (first.status, first.reason_code, first.text)
    reply = answered(env.ask("And is that going up?",
                             Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert KEPT_ANY.search(reply.text), reply.text
    assert "district 1" in KEPT_ANY.search(reply.text)[0]
    assert reply.carried.get("period") and reply.carried.get("filters"), reply.carried
    assert_estimates(env, "trend_d1")


@pytest.mark.needs_r
def test_a_period_left_out_with_nothing_kept_uses_the_whole_copy(tmp_path, monkeypatch):
    """S13 point 1 (round 4; before S13 this test expected Python to ask): with no period
    stated, pending or kept, `analyze` runs over the whole copy (S2's window: January 2021 to
    August 2026, the estimate of trend_all_p6); Python does not ask and does not say the
    period was kept. More in test_s3s_round4.py."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(env.ask(Q_TREND, Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "{a1.trend}."))))
    assert env.model.answer(0)["result_id"] == "a1", env.model.answer(0)
    assert not KEPT_ANY.search(reply.text), reply.text
    assert len(job_folders(env)) == 1
    assert_estimates(env, "trend_all_p6")
