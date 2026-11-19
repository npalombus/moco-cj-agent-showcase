"""`before_after`: docs/S3S-DESIGN.md S1 (`"date": "YYYY-MM-01"`), S3 (T with an indicator
for the months from the date on and the time since the date, 0 before it; at least 12 full
months on each side), S4 (`{aN.step}`, `{aN.bend}`), S5.3 (its fixed line is in
test_s3s_reply.py), S9.

Phrases written by hand from S4 (step) and S11 item 2 (bend, the wording round: "the ratio of
the two yearly changes", a percentage, clear and not clear) with the numbers of the R
cross-check. Which error a date too near an end gets is asked (QUESTIONS.md, 12): either
BAD_OPTIONS or TOO_LITTLE is accepted.
"""
import re

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import (Q_BEFORE_AFTER, StatsEnv, analyze, answered, ask_case, assert_estimates,
                      assert_line1, phrase_in)

STEP = {
    "ba_d6": "from July 2023 on, the monthly level was about 40.6% higher than the earlier "
             "trend pointed to (95% range 3.8% to 90.4%)",
    "ba_d7": "from July 2023 on, the monthly level was about 52.3% lower than the earlier trend "
             "pointed to (95% range -64.8% to -35.5%)",
    "ba_d2": "there was no clear step in July 2022 (about 24.8%, 95% range -12.6% to 78.2%)",
}
BEND = {
    "ba_d6": "after July 2023 the yearly trend was about 39.7% above the yearly trend before "
             "(the ratio of the two yearly changes; 95% range +14.0% to +71.1%)",
    "ba_d7": "after July 2023 the yearly trend was about 24.6% below the yearly trend before "
             "(the ratio of the two yearly changes; 95% range -38.9% to -7.0%)",
    "ba_d2": "there was no clear change in the yearly trend after July 2022 (the ratio of the "
             "two yearly changes was about +30.7%, 95% range -6.9% to +83.5%)",
}


def test_the_hand_written_phrases_match_the_truth():
    """No program code: step higher and lower and not clear; bend higher and lower and not
    clear."""
    assert [(T.truth(n)["step"]["clear"], T.truth(n)["step"]["estimate"] > 0)
            for n in STEP] == [(True, True), (True, False), (False, True)]
    assert [(T.truth(n)["bend"]["clear"], T.truth(n)["bend"]["estimate"] > 0)
            for n in STEP] == [(True, True), (True, False), (False, True)]
    for name, text in STEP.items():
        assert re.fullmatch(T.step_re(T.truth(name)), text), name
    for name, text in BEND.items():
        assert re.fullmatch(T.bend_re(T.truth(name)), text), name
    t = T.truth("ba_d6")
    assert (t["months_before"], t["months_after"]) == (30, 30)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", list(STEP))
def test_step_and_bend(tmp_path, monkeypatch, name):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name, text="{a1.step}. {a1.bend}."))
    assert reply.reply_style == "agent", reply.draft_failures
    assert_estimates(env, name)
    t = T.truth(name)
    assert_line1(reply.text, T.cap_re(T.step_re(t)) + r"\. " + T.cap_re(T.bend_re(t)))


def _date_call(date):
    args = T.analyze_arguments("ba_d2")
    args["options"] = {"date": date}
    return analyze(args)


@pytest.mark.needs_r
@pytest.mark.parametrize("date", ["2022-01-01", "2025-01-01"])
def test_a_date_leaving_exactly_12_months_on_a_side_is_run(tmp_path, monkeypatch, date):
    """S3: at least 12 full months on each side. The window is January 2021 to December
    2025: 1 January 2022 leaves 12 before it, 1 January 2025 leaves 12 from it on."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BEFORE_AFTER, Step(_date_call(date)),
                    Step(finish("finding", "{a1.step}. {a1.bend}.")))
    answered(reply)
    assert env.model.answer(0)["result_id"] == "a1"


@pytest.mark.parametrize("date,widened", [
    ("2021-12-01", False), pytest.param("2025-02-01", True, marks=pytest.mark.needs_r)])
def test_11_months_on_a_side_is_refused_at_the_copys_start_else_run_on_the_whole_copy(
        tmp_path, monkeypatch, date, widened):
    """S3 at its edge, with S13 point 4 (round 4; before S13 both dates were refused). The
    period is January 2021 to December 2025. 1 December 2021 leaves 11 full months before
    it, and the whole copy starts in January 2021 too: refused before R is started
    (BAD_OPTIONS or TOO_LITTLE: asked), no result. 1 February 2025 leaves 11 from it on: run
    on the whole copy instead (January 2021 to August 2026, 19 months from it on), whose
    months the answer names."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BEFORE_AFTER, Step(_date_call(date)),
                    Step(finish("finding", "{a1.step}.")))
    answer = env.model.answer(0)
    if not widened:
        assert answer.get("error") in ("BAD_OPTIONS", "TOO_LITTLE"), answer
        assert "result_id" not in answer
        return
    answered(reply)
    assert answer.get("result_id") == "a1", answer
    assert "January 2021" in answer["read_as"] and "August 2026" in answer["read_as"], answer


def test_the_months_on_each_side_by_counting():
    """No program code: the edges above, by counting the window's months."""
    months = T.window(T.source_json(T.MAIN), T.P5)
    for date, before, after in (("2022-01-01", 12, 48), ("2025-01-01", 48, 12),
                                ("2021-12-01", 11, 49), ("2025-02-01", 49, 11)):
        y, m = int(date[:4]), int(date[5:7])
        assert (sum(ym < (y, m) for ym in months), sum(ym >= (y, m) for ym in months)) == \
            (before, after), date


def test_phrase_in_is_strict():
    """The helper used above finds a regex anywhere, nothing looser."""
    phrase_in("abc", "b")
    with pytest.raises(AssertionError):
        phrase_in("abc", "d")
