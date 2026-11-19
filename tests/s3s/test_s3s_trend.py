"""`trend`: docs/S3S-DESIGN.md S1 (the kind), S3 (model T), S4 (`{aN.trend}`), S9 (R's
estimate equals the tests' own recomputation; the phrase exactly, clear and not clear, both
directions).

The expected phrases below are written out by hand from S4, with the numbers R gave in the
tests session's cross-check (kit-log/raw/S3S-A-r-crosscheck.txt). The first test checks
them against s3ssupport's phrase builders with no program code; the others run the agent
with R and check the reply's line 1 and R's result.json against the truth.

Readings: s3ssupport's module text (time in years, the window) and s3sagent's (slots, the
job folder). S4's sign rule is asked (QUESTIONS.md, 1): the builders accept `+` before a
positive value and the signed value after "rose/fell by about"; the hand-written strings use
the plain form.
"""
import re

import pytest

import s3ssupport as T
from s3sagent import (UNIT_MANY, StatsEnv, answered, ask_case, assert_estimates, assert_line1)

# case: (<what> of C6, the phrase written by hand from S4)
PHRASES = {
    "trend_all": ("", "arrest records rose by about 8.9% a year from January 2021 to December "
                      "2025 (95% range 6.8% to 11.1%)"),
    "trend_d1": ("in district 1", "arrest records in district 1 rose by about 18.8% a year "
                                  "from January 2021 to December 2025 (95% range 13.8% to "
                                  "24.0%)"),
    "trend_d2": ("in district 2", "arrest records in district 2 showed no clear change from "
                                  "January 2021 to December 2025 (about -1.6% a year, 95% "
                                  "range -6.7% to 3.7%)"),
    "trend_d3": ("in district 3", "arrest records in district 3 fell by about 8.8% a year from "
                                  "January 2021 to December 2025 (95% range -13.0% to -4.5%)"),
}


def test_the_hand_written_phrases_are_the_truths_in_each_form():
    """No program code: each case has the form its fixture was built for (a clear rise, a
    clear fall, no clear change), and the phrase written by hand matches the builder."""
    forms = {name: (T.truth(name)["trend"]["clear"], T.truth(name)["trend"]["estimate"] > 0)
             for name in PHRASES}
    assert forms == {"trend_all": (True, True), "trend_d1": (True, True),
                     "trend_d2": (False, False), "trend_d3": (True, False)}
    for name, (what, text) in PHRASES.items():
        assert re.fullmatch(T.trend_re(T.truth(name), UNIT_MANY, what), text), name
    # the sign rule is the one open point: a "+" before a positive value is accepted too
    assert re.fullmatch(T.trend_re(T.truth("trend_all"), UNIT_MANY, ""),
                        PHRASES["trend_all"][1].replace("6.8%", "+6.8%"))
    # and nothing else is: a different number, a missing range, another month
    for wrong in ("rose by about 9.9%", "(95% range 6.8% to 11.1%)", "December 2025"):
        bad = PHRASES["trend_all"][1].replace(wrong, {"rose by about 9.9%": "rose by about 9.9%",
                                                      "(95% range 6.8% to 11.1%)": "",
                                                      "December 2025": "November 2025"}[wrong])
        if wrong == "rose by about 9.9%":
            bad = PHRASES["trend_all"][1].replace("8.9%", "9.9%")
        assert not re.fullmatch(T.trend_re(T.truth("trend_all"), UNIT_MANY, ""), bad), wrong


def test_the_months_are_the_window():
    """S2 with S4: the phrase names the window's first and last month (no program code)."""
    t = T.truth("trend_all")
    assert (T.month_text(t["months"][0]), T.month_text(t["months"][-1])) == \
        ("January 2021", "December 2025")
    assert len(t["months"]) == 60 and t["records"] == sum(t["counts"])


@pytest.mark.needs_r
@pytest.mark.parametrize("name", list(PHRASES))
def test_trend_estimate_and_phrase(tmp_path, monkeypatch, name):
    """S9: R's estimate and interval (result.json) equal the truth within 0.01 and 0.10 of a
    percentage point; S4: line 1 is the model's sentence with `{a1.trend}` filled exactly."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name, text="I found that {a1.trend}."))
    assert (reply.reply_kind, reply.reply_style) == ("finding", "agent"), reply.draft_failures
    assert_estimates(env, name)
    assert_line1(reply.text, T.trend_re(T.truth(name), UNIT_MANY, PHRASES[name][0]),
                 before="I found that ")


@pytest.mark.needs_r
def test_the_model_used_is_the_negative_binomial(tmp_path, monkeypatch):
    """S3: with spread above zero the negative binomial is used, and the result says so (the
    Poisson fallback is in test_s3s_fallback_fit.py)."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "trend_d1"))
    from s3sagent import result_text
    text = result_text(env)
    assert "negative binomial" in text or "glm.nb" in text or "negbin" in text, text[:400]
    assert "poisson" not in text.replace("quasipoisson", ""), text[:400]
