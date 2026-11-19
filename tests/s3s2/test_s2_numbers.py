"""R9, point 2: the rate and its margin, the ratio and its margin, each against the tests' own
arithmetic written out from R5's formulas (tests/s3s2/s2support.py), to the decimals shown;
several years together; a figure the Census publishes with no margin (docs/S3S2-DESIGN.md
R5, D-057: "exactly how the census states it").

- rate per 10,000: one decimal, `(margin of error ±<m>)`, the margin to one decimal
  (READING: R5 gives one decimal for the rate "with its margin").
- ratio: two decimals, its margin to two decimals (READING, the same way).
- the reference: the group with the most residents, or the one the call names.
- several years: records added up over residents added up; the margin by the formula for a
  sum.
- no margin: the total of B01001 has the Census's "no margin" code; R10 point 2: the rate of
  `none` is written with `(the Census gives no margin of error for this figure)`.

Read from the fixed rendering (MOCO_REPLY_STYLE=fixed), whose line 1 is every phrase of the
result as its own sentence. Every program test starts R.
"""
import re

import pytest

import s2support as T
from s2agent import S2Env, ask_rate, line1_of


def test_the_numbers_by_hand():
    """No program code: the round cases, written out by hand (kit-log/raw/
    S3S2-A-truth-by-hand.txt has the sums)."""
    t = T.truth("re_2025")
    shown = {g: (T.one(v["rate"]), T.one(v["margin"])) for g, v in t["groups"].items()}
    assert shown == {"Hispanic (any race)": ("30.0", "0.6"),
                     "Black, not Hispanic": ("50.0", "1.0"),
                     "White, not Hispanic": ("10.0", "0.1"),
                     "Asian, not Hispanic": ("10.0", "0.2")}
    assert t["reference"] == "White, not Hispanic"
    ratios = {g: (T.two(v["ratio"]), T.two(v["margin"]), v["clear"])
              for g, v in t["ratios"].items()}
    assert ratios == {"Hispanic (any race)": ("3.00", "0.06", True),
                      "Black, not Hispanic": ("5.00", "0.10", True),
                      "Asian, not Hispanic": ("1.00", "0.02", False)}
    t = T.truth("re_2024_25")
    assert {g: (T.one(v["rate"]), T.one(v["margin"])) for g, v in t["groups"].items()} == {
        "Hispanic (any race)": ("27.5", "0.4"), "Black, not Hispanic": ("45.0", "0.6"),
        "White, not Hispanic": ("15.0", "0.1"), "Asian, not Hispanic": ("15.0", "0.2")}
    asian = t["ratios"]["Asian, not Hispanic"]
    assert (T.two(asian["ratio"]), T.two(asian["margin"]), asian["clear"]) == ("1.00", "0.02",
                                                                              False)
    ten17 = T.truth("age_2025")["groups"]["10 to 17"]
    assert (ten17["n"], ten17["residents"], ten17["residents_margin"]) == (188, 110000, 2500.0)
    assert (T.one(ten17["rate"]), T.one(ten17["margin"])) == ("17.1", "0.4")
    t = T.truth("re_2025_hisp")
    assert t["reference"] == "Hispanic (any race)"
    assert T.two(t["ratios"]["Black, not Hispanic"]["ratio"]) == "1.67"
    assert T.two(t["ratios"]["White, not Hispanic"]["ratio"]) == "0.33"
    none = T.truth("all_2025")["groups"]["all residents"]
    assert (T.one(none["rate"]), none["margin"], none["residents"]) == ("19.3", None, 1057000)


def test_the_ratio_formula_is_the_bureaus():
    """No program code: the margin of a ratio by the Bureau's formula with standard errors,
    SE(A/B) = (1/B) sqrt(SE(A)^2 + (A/B)^2 SE(B)^2), SE = margin / 1.645, against the margin
    form used to write it out by hand."""
    x, margin, clear = T.ratio(30.0, 0.6, 10.0, 0.06)
    se = (1 / 10.0) * ((0.6 / 1.645) ** 2 + 3.0 ** 2 * (0.06 / 1.645) ** 2) ** 0.5
    assert abs(margin - 1.645 * se) < 1e-12 and abs(margin - 0.062642) < 1e-6
    assert x == 3.0 and clear
    assert T.ratio(10.0, 0.2, 10.0, 0.06)[2] is False


def test_the_phrases_by_hand():
    """No program code: R10 point 2's phrases with the round numbers, written out by hand."""
    t = T.truth("re_2025")
    assert T.rate_phrase(t, "Hispanic (any race)") == (
        "there were about 30.0 arrest records per 10,000 residents counted as Hispanic (any "
        "race) in 2025 (margin of error ±0.6)")
    assert T.ratio_phrase(t, "Hispanic (any race)") == (
        "the rate for Hispanic (any race) was about 3.00 times the rate for White, not Hispanic "
        "(margin of error ±0.06)")
    assert T.ratio_phrase(t, "Asian, not Hispanic") == (
        "the rates for Asian, not Hispanic and White, not Hispanic were not clearly different "
        "(ratio 1.00, margin of error ±0.02)")
    assert T.rate_phrase(T.truth("all_2025"), "all residents") == (
        "there were about 19.3 arrest records per 10,000 residents in 2025 (the Census gives no "
        "margin of error for this figure)")


CASES = ["re_2025", "re_2024_25", "re_5y", "re_2023", "re_2025_hisp", "gender_2025",
         "gender_5y", "gender_2025_male", "age_5y", "all_2025", "all_5y"]


@pytest.mark.needs_r
@pytest.mark.parametrize("name", CASES)
def test_rates_ratios_and_margins(tmp_path, monkeypatch, name):
    """Each group's rate and margin and each ratio and margin, to the decimals shown; the
    reference as R5 says; nothing else stated as a rate."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],), MOCO_REPLY_STYLE="fixed")
    asked = len(env.census_runs[0].census.requests)
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    line1 = line1_of(reply.text)
    for slot, phrase in T.phrases(t).items():
        assert T.cap(phrase) + "." in line1, f"{slot}: expected\n  {T.cap(phrase)}.\nin line 1:\n{line1}"
    assert line1 == T.line1(t), (line1, T.line1(t))
    if t["by"] is None:
        assert "±" not in line1, f"R5: no margin for a figure the Census gives none: {line1}"
    assert len(env.census_runs[0].census.requests) == asked, \
        "a rate is worked out from the saved Census copies; the turn asked the Census again"
