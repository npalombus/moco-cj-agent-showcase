"""`yes_no`: docs/S3S-DESIGN.md S1 (`outcome`, 1 to 6 `factors`, 0 to 3 `controls`), S3 (model
L: logistic regression; category controls as indicators against the most common label), S4
(`{aN.odds.<k>}` one per factor label in table order, `{aN.held}`), S9 (odds ratios within
0.001, ends within 0.005).

Option shapes (READING, s3ssupport): a flag is its field name, a category with one label is
`{"field": "gender", "is": "female"}`, `under_18` and `weekend` are strings. The odds phrase
is S11 item 1's (the wording round): `<unit many> <factor what> had higher|lower odds of
being <outcome what>`, both sides written as C6 writes a filter (s3ssupport.L_WHAT); the
made-up factors and the table line are in test_s3s_wording.py. `<controls>` in `{aN.held}`
is read as the controls' dimension words (district -> `district`). Phrases by hand, numbers
of the R cross-check.
"""
import re

import pytest

import s3ssupport as T
from s3sagent import (UNIT_MANY, StatsEnv, answered, ask_case, assert_estimates,
                      assert_line1, tool_answer)

OUTCOME = T.SCHOOL      # the outcome option of every case here; its <what> is the flag's text
ODDS = [
    "arrest records with a weapon recorded had higher odds of being within 500 feet of a "
    "school (odds ratio 3.16, 95% range 2.82 to 3.53)",
    "arrest records of people recorded as female had lower odds of being within 500 feet of "
    "a school (odds ratio 0.70, 95% range 0.62 to 0.79)",
    "arrest records on shift B showed no clear difference in the odds of being within 500 "
    "feet of a school (odds ratio 1.01, 95% range 0.90 to 1.12)",
]
ODDS_NO_CONTROL = [
    "arrest records with a weapon recorded had higher odds of being within 500 feet of a "
    "school (odds ratio 3.13, 95% range 2.80 to 3.50)",
    "arrest records of people recorded as female had lower odds of being within 500 feet of "
    "a school (odds ratio 0.70, 95% range 0.62 to 0.79)",
    "arrest records on shift B showed no clear difference in the odds of being within 500 "
    "feet of a school (odds ratio 1.01, 95% range 0.91 to 1.12)",
]


def test_the_hand_written_phrases_match_the_truth():
    """No program code: higher, lower, not clear, in the order of `factors`."""
    for name, texts in (("yn_main", ODDS), ("yn_nocontrol", ODDS_NO_CONTROL)):
        t = T.truth(name)
        assert t["outcome_label"] == T.what_of(OUTCOME) == "within 500 feet of a school"
        assert [(e["clear"], e["estimate"] > 1) for e in t["odds"]] == \
            [(True, True), (True, False), (False, True)]
        for est, text in zip(t["odds"], texts):
            assert re.fullmatch(T.odds_re(est, UNIT_MANY, OUTCOME), text), (name, text)
    assert T.held_text(["district"]) == "holding district fixed"
    assert T.held_text([]) == "with nothing else held fixed"
    assert T.truth("yn_main")["references"] == {"district": "district 1"}


def _line1(texts, held):
    return " ".join(re.escape(T.cap(x)) + r"\." for x in texts) + " " + re.escape(T.cap(held))


@pytest.mark.needs_r
@pytest.mark.parametrize("name,held", [("yn_main", "holding district fixed"),
                                       ("yn_nocontrol", "with nothing else held fixed")])
def test_odds_and_held(tmp_path, monkeypatch, name, held):
    """S4: one `{a1.odds.k}` per factor, in the order given, then `{a1.held}` in the
    sentence after the last; the fixed words exactly, the numbers within S9 of the truth."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    assert reply.reply_style == "agent", reply.draft_failures
    assert tool_answer(env)["slots"] == ["{a1.odds.1}", "{a1.odds.2}", "{a1.odds.3}",
                                         "{a1.held}"]
    assert_estimates(env, name)
    t = T.truth(name)
    pattern = " ".join(T.cap_re(T.odds_re(e, UNIT_MANY, OUTCOME)) + r"\." for e in t["odds"]) + \
        " " + re.escape(T.cap(held))
    assert_line1(reply.text, pattern)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["yn_u18", "yn_k110"])
def test_estimates_of_other_factors(tmp_path, monkeypatch, name):
    """S9 for `under_18` and `weekend` against district, and for a small source with a
    nine-label control (zone, against its most common label, zone 1)."""
    env = StatsEnv(tmp_path, monkeypatch, names=(T.case(name)["source"],))
    answered(ask_case(env, name))
    assert_estimates(env, name)


def test_the_l_premises():
    """No program code: under 18 goes with the outcome (built in), weekend does not, and
    records with no usable value in a used field are left out."""
    u18, weekend = T.truth("yn_u18")["odds"]
    assert u18["clear"] and u18["estimate"] > 1.5 and not weekend["clear"]
    left = T.truth("yn_main")["left_out"]
    assert left["gender"] > 0 and left["district"] > 0
