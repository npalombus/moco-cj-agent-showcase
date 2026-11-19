"""The wording round of Part S: docs/S3S-DESIGN.md S11 (round 2; brief S3S-R2-A). Every point
of S11's part 3. Tests only: the planning chat builds this round (D-050).

By S11's items:
- 1: the odds phrase exactly, clear (higher, lower) and not clear, for a flag, a category
  label and each made-up factor (under_18, weekend, night), as factor and as outcome; the
  yes_no table line.
- 2: the difference and bend phrases, clear (above, below) and not clear (hand strings
  here; their R runs are in test_s3s_compare.py and test_s3s_before_after.py, the bend's
  whole reply in test_s3s_reply.py); the trend_compare table line, which does not change.
- 2b: the hidden line on the timing case (its quietest cell is hidden), not on a case with
  nothing hidden.
- 2c: a partial last year and a partial first year in the yearly table; a whole year as it
  was.
- 2d: the fixed rendering of a yes_no answer with and without controls.
- 2f: the one line about cause on a sensitive field; the association line as it was
  without one (more cases in test_s3s_reply.py).
- 2g: the partial last year in the shares table and in `{aN.share}`.
- 2i: R1's limits with one, four and six odds slots.
- Every estimate, range and clear-or-not verdict of every case of the truth helper is as
  before the round (tests/s3s/fixtures/wording_round_before.json, saved from the truth
  helper before any builder changed).
- No other phrase or fixed line changed: the unchanged builders against hand strings here;
  the R runs of the rest of tests/s3s (trend, step, share, sharetrend, timing, ages, the
  fixed lines of S5 and S10 answer 10) are unchanged and still hold.

Each phrase is written out here by hand from S11 for one case, its numbers typed from the
truth helper's output (kit-log/raw/S3S-R2-A-truth.txt). The made-up factors' words are C6's
for the matching filter, read from the Part A phrase tests (tests/s3/test_s3_phrases.py):
`of people under 18`, `on weekends`, `between 10 pm and 5 am`.

READINGS (each in kit-log/raw/S3S-R2-A-notes.txt):
- The extra yes_no cases (a made-up factor or a category as outcome; night; four and six
  factors) are not added to s3ssupport.CASES, whose numbers this round must not change.
  Their truth is s3ssupport's own L model; `night` (S10 answer 2: the hour is 22, 23 or 0 to
  5) is added here, because no case of the truth helper used it.
- A shares question to the newest record uses S2's window (S10 answer 13): January 2021 to
  August 2026, so 2026 is a partial year (January to August).
- The hidden line ends with the source's page (C8.2) or its address (S11 2b writes
  `<address>`): asked in briefs/QUESTIONS.md, both accepted at that one place.
- 2b's "straight after the table": with no table in the reply (timing: S10 answer 14),
  straight after line 1.
- 2f's one line stands where the association line stood. S5.6 names a sensitive field as a
  "filter, factor, control or group", not as the outcome: with gender as the outcome, the
  association line and the one line are both accepted (asked in briefs/QUESTIONS.md).
- 2i's k is the number of odds slots the text fills; a refused text falls back to the fixed
  rendering with SHAPE among its failures (R1's code for too many sentences or characters).
"""
import json
import math
import re
from functools import lru_cache
from unittest.mock import patch

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import (MAIN_ID, Q_COMPARE, Q_SHARES, Q_TIMING, Q_TREND, Q_YES_NO, SEP,
                      UNIT_MANY, StatsEnv, analyze, answered, first_source, result_of)

SRC = T.source_json(T.MAIN)
ASSOC = T.association_line(UNIT_MANY)
CAUSE = T.cause_line(UNIT_MANY)
ASSOC_RE, CAUSE_RE = re.escape(ASSOC), re.escape(CAUSE)

# ---- the cases this file adds (not in s3ssupport.CASES) ----------------------------------------

NIGHT_HOURS = (22, 23, 0, 1, 2, 3, 4, 5)     # S10 answer 2
_L_VALUE = T._l_value

YES_NO = {  # name: (outcome, factors, controls), all on P5 with no filter
    "yn_out_u18": ("under_18", ["night", T.WEAPON], []),
    "yn_out_weekend": ("weekend", ["under_18", T.SCHOOL], []),
    "yn_out_night": ("night", ["weekend", T.SHIFT_B], []),
    "yn_out_female": (T.FEMALE, [T.WEAPON, "night"], []),
    "yn_four": (T.SCHOOL, [T.WEAPON, T.FEMALE, T.SHIFT_B, "under_18"], ["district"]),
    "yn_six": (T.SCHOOL, [T.WEAPON, T.FEMALE, T.SHIFT_B, "under_18", "weekend", "night"],
               ["district"]),
}
SH_PART = [T.is_(T.SCHOOL, True)]
SH_P6_MONTHS = T.window(SRC, T.P6)            # January 2021 to August 2026


def _l_value(row, item, src):
    if item == "night":
        return 1 if T.row_time(row, src)[1] in NIGHT_HOURS else 0
    return _L_VALUE(row, item, src)


def options(name):
    if name in T.CASES:
        return T.case(name)["options"]
    outcome, factors, controls = YES_NO[name]
    return {"outcome": outcome, "factors": list(factors), "controls": list(controls)}


@lru_cache(maxsize=None)
def truth(name):
    """s3ssupport's truth, or for a case of this file s3ssupport's own L model with night."""
    if name in T.CASES:
        return T.truth(name)
    with patch.object(T, "_l_value", _l_value):
        return T._truth_yes_no({"source": T.MAIN, "period": T.P5, "filters": [],
                                "options": options(name)})


@lru_cache(maxsize=None)
def sh_p6():
    """Shares of `within 500 feet of a school` on the P6 window, by s3ssupport's own S model."""
    (y0, m0), last = SH_P6_MONTHS[0], SH_P6_MONTHS[-1]
    period = {"from": f"{y0}-{m0:02d}-01", "to": T.last_day(*last).isoformat()}
    return T._truth_shares({"source": T.MAIN, "period": period, "filters": [],
                            "options": {"part": SH_PART}})


def arguments(name):
    if name in T.CASES:
        return T.analyze_arguments(name)
    return {"kind": "yes_no", "source": MAIN_ID, "period": T.P5, "filters": [],
            "options": options(name)}


SH_P6_ARGUMENTS = {"kind": "shares", "source": MAIN_ID, "period": T.P6, "filters": [],
                   "options": {"part": SH_PART}}


def ask(env, args, text, question=Q_YES_NO):
    return env.ask(question, Step(analyze(args)), Step(finish("finding", text)))


def held(name):
    return T.held_text(options(name)["controls"])


def odds_slots(name):
    return " ".join(f"{{a1.odds.{i}}}." for i in range(1, len(options(name)["factors"]) + 1))


# ---- the whole reply (S5 with S11) ---------------------------------------------------------------

def reply_re(line1, table=(), *, used, cause=ASSOC_RE, hidden=False, source=None):
    """S5's order with S11: line 1, the table (each line exactly), the hidden line (2b), the
    used line, the line about cause (2f: the association line, or the one line), the source
    line. Joined as s3sagent reads S5: one space, one line break or one blank line; table
    lines each on a line of their own."""
    out = line1 + "".join(r"\n" + line for line in table)
    if hidden:
        out += SEP + T.hidden_line_re(SRC)
    return out + SEP + used + SEP + cause + SEP + (source or first_source())


def assert_reply(text, pattern):
    assert re.fullmatch(pattern, text), (f"not the expected reply.\n--- got ---\n{text}\n"
                                         f"--- expected (regex) ---\n{pattern}")


def used(t, months=60):
    return T.used_re(t["records"], months, [k for k in t["left_once"].values() if k])


def cause_re(name):
    """2f: the one line when gender (the fixture's sensitive field) is a factor; when it is
    only the outcome, either line (S5.6 does not name the outcome: asked)."""
    o = options(name)

    def gender(x):
        return isinstance(x, dict) and x["field"] == "gender"
    if any(gender(f) for f in o["factors"]):
        return CAUSE_RE
    return f"(?:{ASSOC_RE}|{CAUSE_RE})" if gender(o["outcome"]) else ASSOC_RE


def assert_odds_estimates(env, name):
    entries = T.result_estimates(result_of(env))
    for e in truth(name)["odds"]:
        assert T.find_estimate(entries, e, "yes_no"), (name, e["factor"], e["estimate"],
                                                       entries)


# ---- the phrases by hand (S11) -------------------------------------------------------------------

ODDS = {  # (case, factor index): {aN.odds.k} by hand, S11 item 1 (yn_main's: test_s3s_yes_no.py)
    ("yn_u18", 0): "arrest records of people under 18 had higher odds of being within 500 feet "
                   "of a school (odds ratio 2.06, 95% range 1.74 to 2.44)",
    ("yn_u18", 1): "arrest records on weekends showed no clear difference in the odds of being "
                   "within 500 feet of a school (odds ratio 1.03, 95% range 0.92 to 1.15)",
    ("yn_out_u18", 0): "arrest records between 10 pm and 5 am showed no clear difference in the "
                       "odds of being of people under 18 (odds ratio 1.14, 95% range 0.95 to "
                       "1.36)",
    ("yn_out_u18", 1): "arrest records with a weapon recorded had lower odds of being of people "
                       "under 18 (odds ratio 0.81, 95% range 0.67 to 0.98)",
    ("yn_out_weekend", 0): "arrest records of people under 18 had higher odds of being on "
                           "weekends (odds ratio 1.21, 95% range 1.02 to 1.43)",
    ("yn_out_weekend", 1): "arrest records within 500 feet of a school showed no clear "
                           "difference in the odds of being on weekends (odds ratio 1.04, 95% "
                           "range 0.92 to 1.16)",
    ("yn_out_night", 0): "arrest records on weekends showed no clear difference in the odds of "
                         "being between 10 pm and 5 am (odds ratio 0.91, 95% range 0.82 to "
                         "1.02)",
    ("yn_out_night", 1): "arrest records on shift B showed no clear difference in the odds of "
                         "being between 10 pm and 5 am (odds ratio 1.02, 95% range 0.92 to "
                         "1.12)",
    ("yn_out_female", 0): "arrest records with a weapon recorded showed no clear difference in "
                          "the odds of being of people recorded as female (odds ratio 1.04, 95% "
                          "range 0.94 to 1.16)",
    ("yn_out_female", 1): "arrest records between 10 pm and 5 am showed no clear difference in "
                          "the odds of being of people recorded as female (odds ratio 0.97, 95% "
                          "range 0.87 to 1.08)",
}
ODDS_LINES = {  # the yes_no table, S11 item 1
    "yn_main": ["with a weapon recorded: odds ratio 3.16 (95% range 2.82 to 3.53)",
                "of people recorded as female: odds ratio 0.70 (95% range 0.62 to 0.79)",
                "on shift B: odds ratio 1.01 (95% range 0.90 to 1.12)"],
    "yn_out_u18": ["between 10 pm and 5 am: odds ratio 1.14 (95% range 0.95 to 1.36)",
                   "with a weapon recorded: odds ratio 0.81 (95% range 0.67 to 0.98)"],
    "yn_out_weekend": ["of people under 18: odds ratio 1.21 (95% range 1.02 to 1.43)",
                       "within 500 feet of a school: odds ratio 1.04 (95% range 0.92 to 1.16)"],
    "yn_out_night": ["on weekends: odds ratio 0.91 (95% range 0.82 to 1.02)",
                     "on shift B: odds ratio 1.02 (95% range 0.92 to 1.12)"],
}
DIFFERENCE = {  # {aN.difference}, S11 item 2: (a, b, the phrase by hand)
    "compare_school": ("within 500 feet of a school", "not within 500 feet of a school",
                       "the yearly trend not within 500 feet of a school was about 15.2% below "
                       "the yearly trend within 500 feet of a school (the ratio of the two "
                       "yearly changes; 95% range -18.5% to -11.8%)"),  # S12 item 1: round 3
    "compare_school_rev": ("not within 500 feet of a school", "within 500 feet of a school",
                           "the yearly trend within 500 feet of a school was about 18.0% above "
                           "the yearly trend not within 500 feet of a school (the ratio of the "
                           "two yearly changes; 95% range +13.4% to +22.7%)"),
    "compare_weapon": ("with a weapon recorded", "with no weapon recorded",
                       "there was no clear difference in yearly trend between with a weapon "
                       "recorded and with no weapon recorded (the ratio of the two yearly "
                       "changes was about -0.5%, 95% range -4.2% to +3.4%)"),
}
BEND = {  # {aN.bend}, S11 item 2
    "ba_d6": "after July 2023 the yearly trend was about 39.7% above the yearly trend before "
             "(the ratio of the two yearly changes; 95% range +14.0% to +71.1%)",
    "ba_d7": "after July 2023 the yearly trend was about 24.6% below the yearly trend before "
             "(the ratio of the two yearly changes; 95% range -38.9% to -7.0%)",
    "ba_d2": "there was no clear change in the yearly trend after July 2022 (the ratio of the "
             "two yearly changes was about +30.7%, 95% range -6.9% to +83.5%)",
}
COMPARE_LINES = [  # the trend_compare table of compare_school, S10 answer 9: does not change
    "within 500 feet of a school: about +24.1% a year (95% range +20.1% to +28.3%)",
    "not within 500 feet of a school: about +5.2% a year (95% range +3.1% to +7.4%)",
]
HIDDEN = ("Counts under 10 are not shown here; the county's open data has every record: "
          "https://fixture.invalid/d/stats-like.")
YEARLY = {  # S11 2c
    "trend_all_p6": ["2021: 1,439", "2022: 1,577", "2023: 1,576", "2024: 1,859", "2025: 2,040",
                     "2026 (January to August): 1,508"],
    "trend_mid": ["2021 (February to December): 1,343", "2022: 1,577", "2023: 1,576",
                  "2024: 1,859", "2025 (January to November): 1,884"],
    "trend_all": ["2021: 1,439", "2022: 1,577", "2023: 1,576", "2024: 1,859", "2025: 2,040"],
}
SHARE_P6 = ("the share within 500 feet of a school went from 16.3% in 2021 to 27.9% in January "
            "to August 2026")                                                 # S11 2g
SHARE_P6_LINES = ["2021: 16.3% (95% range 14.4% to 18.3%)",
                  "2022: 18.1% (95% range 16.3% to 20.1%)",
                  "2023: 22.1% (95% range 20.1% to 24.2%)",
                  "2024: 23.4% (95% range 21.5% to 25.4%)",
                  "2025: 27.1% (95% range 25.2% to 29.1%)",
                  "2026 (January to August): 27.9% (95% range 25.7% to 30.2%)"]
FIXED = {  # S11 2d: the fixed rendering's line 1
    "yn_main": "Arrest records with a weapon recorded had higher odds of being within 500 feet of "
               "a school (odds ratio 3.16, 95% range 2.82 to 3.53). Arrest records of people "
               "recorded as female had lower odds of being within 500 feet of a school (odds "
               "ratio 0.70, 95% range 0.62 to 0.79). Arrest records on shift B showed no clear "
               "difference in the odds of being within 500 feet of a school (odds ratio 1.01, 95% "
               "range 0.90 to 1.12), holding district fixed.",
    "yn_nocontrol": "Arrest records with a weapon recorded had higher odds of being within 500 "
                    "feet of a school (odds ratio 3.13, 95% range 2.80 to 3.50). Arrest records "
                    "of people recorded as female had lower odds of being within 500 feet of a "
                    "school (odds ratio 0.70, 95% range 0.62 to 0.79). Arrest records on shift B "
                    "showed no clear difference in the odds of being within 500 feet of a school "
                    "(odds ratio 1.01, 95% range 0.91 to 1.12), with nothing else held fixed.",
}
CAUSE_BY_HAND = ("These are patterns in recorded arrest records, not rates: what goes with what, "
                 "not what causes what.")                                     # S11 2f


def compare_line_re(label, e):
    """S10 answer 9's trend_compare line (unchanged by S11): `<compare label>: about <p>% a
    year (95% range <lo>% to <hi>%)`, signed as S10 answer 1."""
    return (re.escape(f"{label}: about ") + T.sign_re(e["estimate"]) + r"% a year \(95% range "
            + T.sign_re(e["low"], 1, T.TOL_PCT_END) + "% to "
            + T.sign_re(e["high"], 1, T.TOL_PCT_END) + r"%\)")


# ---- no program code: the hand strings are the truth -----------------------------------------------

def test_the_extra_cases_have_the_forms_they_are_used_for():
    """Higher, lower and not clear; each range's ends at least three tolerances from 1, so R
    and Python cannot fall on different sides of clear (as s3ssupport.check_designed)."""
    forms = {name: [(e["clear"], e["estimate"] > 1) for e in truth(name)["odds"]]
             for name in ("yn_u18", "yn_out_u18", "yn_out_weekend", "yn_out_night",
                          "yn_out_female")}
    assert forms == {"yn_u18": [(True, True), (False, True)],
                     "yn_out_u18": [(False, True), (True, False)],
                     "yn_out_weekend": [(True, True), (False, True)],
                     "yn_out_night": [(False, False), (False, True)],
                     "yn_out_female": [(False, True), (False, False)]}
    for name in forms:
        for e in truth(name)["odds"]:
            assert min(abs(e["low"] - 1), abs(e["high"] - 1)) > 3 * T.TOL_OR_END, (name, e)
    for name in ("yn_four", "yn_six"):
        t = truth(name)
        assert min(t["yes"], t["no"]) >= T.MIN_CASES
        assert min(t["yes"], t["no"]) >= T.PER_COEFFICIENT * t["coefficients"], name


def test_the_odds_phrases_by_hand():
    """S11 item 1: a flag, a category label and each made-up factor, as factor and as
    outcome, clear (higher, lower) and not clear."""
    for (name, i), text in ODDS.items():
        e = truth(name)["odds"][i]
        assert re.fullmatch(T.odds_re(e, UNIT_MANY, options(name)["outcome"]), text), text
    factors = {T.what_of(options(name)["factors"][i]) for name, i in ODDS}
    outcomes = {T.what_of(options(name)["outcome"]) for name, _ in ODDS}
    made_up = {"of people under 18", "on weekends", "between 10 pm and 5 am"}
    assert made_up | {"within 500 feet of a school", "on shift B"} <= factors     # flag, label
    assert made_up | {"within 500 feet of a school", "of people recorded as female"} <= outcomes
    # the old words are gone
    for text in ODDS.values():
        assert "went with" not in text and "no clear link" not in text


def test_the_yes_no_table_lines_by_hand():
    for name, lines in ODDS_LINES.items():
        for e, line in zip(truth(name)["odds"], lines, strict=True):
            assert re.fullmatch(T.odds_line_re(e), line), line


def test_the_difference_and_bend_phrases_by_hand():
    """S11 item 2: above, below, not clear; a percentage, not "points"."""
    for name, (a, b, text) in DIFFERENCE.items():
        assert re.fullmatch(T.difference_re(T.truth(name), a, b), text), name
        assert "points" not in text
    for name, text in BEND.items():
        assert re.fullmatch(T.bend_re(T.truth(name)), text), name
        assert "points" not in text
    # the sign rule of S10 answer 1 holds: no + after above or below, a + in a range
    text = DIFFERENCE["compare_school_rev"][2]
    assert not re.fullmatch(T.difference_re(T.truth("compare_school_rev"), *DIFFERENCE[
        "compare_school_rev"][:2]), text.replace("+13.4%", "13.4%"))
    assert not re.fullmatch(T.difference_re(T.truth("compare_school_rev"), *DIFFERENCE[
        "compare_school_rev"][:2]), text.replace("18.0%", "+18.0%"))


def test_the_trend_compare_table_line_is_unchanged_by_hand():
    own = T.truth("compare_school")["own"]
    for label, e, line in zip(("within 500 feet of a school", "not within 500 feet of a school"),
                              (own["a"], own["b"]), COMPARE_LINES):
        assert re.fullmatch(compare_line_re(label, e), line), line


def test_the_hidden_line_partial_years_held_and_cause_by_hand():
    assert re.fullmatch(T.hidden_line_re(SRC), HIDDEN)
    for name, lines in YEARLY.items():
        assert T.yearly_lines(T.truth(name)) == lines, name
    t = sh_p6()
    assert list(t["years"]) == [2021, 2022, 2023, 2024, 2025, 2026]
    assert re.fullmatch(T.share_re(t, "within 500 feet of a school", SH_P6_MONTHS), SHARE_P6)
    for (year, v), line in zip(t["years"].items(), SHARE_P6_LINES, strict=True):
        assert re.fullmatch(T.share_line_re(year, v, SH_P6_MONTHS), line), line
    for name, text in FIXED.items():
        t = T.truth(name)
        assert re.fullmatch(T.fixed_odds_re(t, UNIT_MANY, options(name)["outcome"], held(name)),
                            text), name
    assert T.cause_line(UNIT_MANY) == CAUSE_BY_HAND
    assert (T.r1_limits(1), T.r1_limits(4), T.r1_limits(6)) == ((4, 600), (6, 1000), (8, 1400))


def test_no_other_phrase_or_fixed_line_changed_by_hand():
    """S11: nothing else changes. The builders the round did not touch still give S4's and
    S10's words (the R runs of the other files check the program against them)."""
    assert re.fullmatch(T.trend_re(T.truth("trend_all"), UNIT_MANY, ""),
                        "arrest records rose by about 8.9% a year from January 2021 to "
                        "December 2025 (95% range +6.8% to +11.1%)")
    assert re.fullmatch(T.step_re(T.truth("ba_d6")),
                        "from July 2023 on, the monthly level was about 40.6% higher than the "
                        "earlier trend pointed to (95% range +3.8% to +90.4%)")
    assert re.fullmatch(T.step_re(T.truth("ba_d2")),
                        "there was no clear step in July 2022 (about +24.8%, 95% range -12.6% to "
                        "+78.2%)")
    assert re.fullmatch(T.share_re(T.truth("sh_school"), "within 500 feet of a school"),
                        "the share within 500 feet of a school went from 16.3% in 2021 to 27.1% "
                        "in 2025")
    assert T.sharetrend_text(T.truth("sh_school")) == "a clear rise over the years"
    assert T.timing_text(T.truth("timing")) == ("the busiest hour was Friday at 11 pm (122) and "
                                                "the quietest Tuesday at 4 am (fewer than 10)")
    assert T.ages_text(T.truth("ages")["groups"][None]) == ("the median age was 30 (the middle "
                                                            "half were 24 to 38)")
    assert T.held_text(["district"]) == "holding district fixed"
    assert ASSOC == ("These are patterns in recorded arrest records: what goes with what, not "
                     "what causes what.")
    assert T.BEFORE_AFTER_LINE == ("Other things changed over the same months. This shows "
                                   "timing, not cause.")
    assert re.fullmatch(T.fit_line_re(0.85), "The last six months were about 15.0% below the "
                                             "trend line, so a straight line describes the "
                                             "recent period poorly.")
    assert re.fullmatch(T.used_re(8491, 60), "(8,491 records over 60 months.)")
    assert re.fullmatch(T.share_line_re(2021, T.truth("sh_school")["years"][2021]),
                        "2021: 16.3% (95% range 14.4% to 18.3%)")


def test_every_estimate_range_and_verdict_is_as_before_the_round():
    """S11 part 3: for every case of the truth helper, against the numbers saved from it
    before any builder changed (within 1e-4, far below the one or two decimals shown, so that
    another machine's last digits do not matter)."""
    before = json.loads((T.FIXTURES / "wording_round_before.json").read_text(encoding="utf-8"))
    assert set(before) == set(T.CASES)

    def same(now, then, where):
        for k in ("estimate", "low", "high"):
            assert math.isclose(now[k], then[k], rel_tol=0, abs_tol=1e-4), (where, k, now[k],
                                                                              then[k])
        assert now["clear"] is then["clear"], where

    for name, item in before.items():
        t = T.truth(name)
        assert t["kind"] == item["kind"], name
        assert [e["name"] for e in t["estimates"]] == [e["name"] for e in item["estimates"]]
        for now, then in zip(t["estimates"], item["estimates"]):
            if t["kind"] != "trend_compare":  # S12 item 1 (D-058) changed it in round 3
                same(now, then, (name, now["name"]))
        for k, then in item.get("own", {}).items():
            same(t["own"][k], then, (name, "own", k))
        for year, then in item.get("years", {}).items():
            v = t["years"][int(year)]
            for k, now in (("share", v["share"]), ("low", v["range"][0]),
                           ("high", v["range"][1])):
                assert math.isclose(now, then[k], rel_tol=0, abs_tol=1e-4), (name, year, k)


# ---- with R: the program -------------------------------------------------------------------------

@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["yn_main", "yn_plain", "yn_u18", "yn_out_u18", "yn_out_weekend",
                                  "yn_out_night", "yn_out_female"])
def test_a_yes_no_reply_in_full(tmp_path, monkeypatch, name):
    """S11 item 1 (each odds phrase and its table line), with 2f (the one line about cause
    when gender is a factor or the outcome, else the association line as it was)."""
    env = StatsEnv(tmp_path, monkeypatch)
    text = f"{odds_slots(name)} {{a1.held}}."
    reply = answered(ask(env, arguments(name), text))
    assert reply.reply_style == "agent", reply.draft_failures
    assert_odds_estimates(env, name)
    t, outcome = truth(name), options(name)["outcome"]
    line1 = " ".join(T.cap_re(T.odds_re(e, UNIT_MANY, outcome)) + r"\." for e in t["odds"]) + \
        " " + re.escape(T.cap(held(name)) + ".")
    table = [T.odds_line_re(e) for e in t["odds"]]
    assert_reply(reply.text, reply_re(line1, table, used=used(t), cause=cause_re(name)))
    assert "went with" not in reply.text and "no clear link" not in reply.text


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["yn_main", "yn_nocontrol"])
def test_the_fixed_rendering_joins_held_to_the_last_odds_sentence(tmp_path, monkeypatch, name):
    """S11 2d, with and without controls (MOCO_REPLY_STYLE=fixed)."""
    env = StatsEnv(tmp_path, monkeypatch, MOCO_REPLY_STYLE="fixed")
    reply = answered(ask(env, arguments(name), f"{odds_slots(name)} {{a1.held}}."))
    assert reply.reply_style == "fixed"
    t = truth(name)
    line1 = T.fixed_odds_re(t, UNIT_MANY, options(name)["outcome"], held(name))
    assert_reply(reply.text, reply_re(line1, [T.odds_line_re(e) for e in t["odds"]],
                                      used=used(t), cause=CAUSE_RE))
    assert f"{T.cap(held(name))}." not in reply.text


@pytest.mark.needs_r
def test_the_hidden_line_on_the_timing_case(tmp_path, monkeypatch):
    """S11 2b: the timing phrase holds `fewer than 10` (the quietest cell, 4 records), so the
    reply carries C8.2's line, straight after line 1 (no table) and before the used line."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask(env, T.analyze_arguments("timing"), "I found that {a1.timing}.",
                         Q_TIMING))
    # Changed by briefs/S3-R21-A-tests.md (C59 of docs/S3A-DESIGN.md: the days first; was
    # "I found that " + T.timing_text(...) + "."). The fixture's days: Friday 1,488, Tuesday
    # 1,063 (tests/s3/test_s3_c59.py checks the sums).
    line1 = re.escape("I found that the busiest day of the week was Friday (1,488) and the "
                      "quietest Tuesday (1,063); " + T.timing_text(T.truth("timing")) + ".")
    assert_reply(reply.text, reply_re(line1, hidden=True, used=used(T.truth("timing"))))
    assert reply.text.count("Counts under 10 are not shown here") == 1


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["trend_all_p6", "trend_mid"])
def test_partial_years_in_the_yearly_table_and_no_hidden_line(tmp_path, monkeypatch, name):
    """S11 2c: trend_all_p6 ends in August 2026 (a partial last year, whole years before it);
    trend_mid runs February 2021 to November 2025 (a partial first and last year). Nothing is
    hidden, so no hidden line (2b); the trend phrase and the other lines are as they were."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask(env, T.analyze_arguments(name), "I found that {a1.trend}.", Q_TREND))
    t = T.truth(name)
    line1 = r"I found that " + T.trend_re(t, UNIT_MANY, "") + r"\."
    table = [re.escape(line) for line in T.yearly_lines(t)]
    assert_reply(reply.text, reply_re(line1, table, used=used(t, len(t["months"]))))
    assert "Counts under" not in reply.text


@pytest.mark.needs_r
def test_the_partial_last_year_of_a_share(tmp_path, monkeypatch):
    """S11 2g: the shares table line of the partial year and `{aN.share}`'s end; whole years as
    they were; the sharetrend phrase as it was."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask(env, SH_P6_ARGUMENTS, "{a1.share}. {a1.sharetrend}.", Q_SHARES))
    assert reply.reply_style == "agent", reply.draft_failures
    t = sh_p6()
    entries = T.result_estimates(result_of(env))
    assert T.find_estimate(entries, t["sharetrend"], "shares"), entries
    line1 = (T.cap_re(T.share_re(t, "within 500 feet of a school", SH_P6_MONTHS)) + r"\. "
             + re.escape(T.cap(T.sharetrend_text(t)) + "."))
    table = [T.share_line_re(y, v, SH_P6_MONTHS) for y, v in t["years"].items()]
    assert_reply(reply.text, reply_re(line1, table, used=used(t, len(SH_P6_MONTHS))))


@pytest.mark.needs_r
def test_a_trend_compare_reply_in_full(tmp_path, monkeypatch):
    """S11 item 2's difference phrase with S10 answer 9's table line, which does not change:
    each group's own yearly change."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask(env, T.analyze_arguments("compare_school"),
                         "I found that {a1.difference}.", Q_COMPARE))
    t = T.truth("compare_school")
    a, b, _ = DIFFERENCE["compare_school"]
    line1 = r"I found that " + T.difference_re(t, a, b) + r"\."
    table = [compare_line_re(a, t["own"]["a"]), compare_line_re(b, t["own"]["b"])]
    assert_reply(reply.text, reply_re(line1, table, used=used(t, len(t["months"]))))


# ---- 2i: R1's limits for a reply with odds slots ---------------------------------------------------

def _shape(reply, passes):
    if passes:
        assert reply.reply_style == "agent", (reply.reply_style, reply.draft_failures)
    else:
        assert reply.reply_style == "fallback", reply.reply_style
        assert "SHAPE" in reply.draft_failures, reply.draft_failures


FOUR = "{a1.odds.1}. {a1.odds.2}. {a1.odds.3}. {a1.odds.4}. {a1.held}."
SIX = "{a1.odds.1}. {a1.odds.2}. {a1.odds.3}. {a1.odds.4}. {a1.odds.5}. {a1.odds.6}. {a1.held}."
ONE = "{a1.odds.1}. {a1.held}."


@pytest.mark.needs_r
@pytest.mark.parametrize("name,text,passes", [
    ("yn_four", FOUR, True),                                # 5 sentences: refused before
    ("yn_four", FOUR + " Thanks.", True),                   # 6 = 4 + 2
    ("yn_four", FOUR + " Here it is. Thanks.", False),      # 7
    ("yn_six", SIX, True),                                  # 7
    ("yn_six", SIX + " Thanks.", True),                     # 8 = 6 + 2
    ("yn_six", SIX + " Here it is. Thanks.", False),        # 9
    ("yn_main", ONE + " Here it is. Thanks.", True),        # one odds slot: 4 sentences
    ("yn_main", ONE + " Here it is. That is it. Thanks.", False),   # 5
])
def test_r1_sentences_with_odds_slots(tmp_path, monkeypatch, name, text, passes):
    """S11 2i: the larger of 4 and k + 2 sentences, k the odds slots filled."""
    env = StatsEnv(tmp_path, monkeypatch)
    _shape(ask(env, arguments(name), text), passes)


def odds_text(e, outcome):
    """One odds phrase as the program fills it (only its length is used: the words are
    odds_re's, the numbers two decimals each)."""
    side = (f"had {'higher' if e['estimate'] > 1 else 'lower'} odds of being" if e["clear"]
            else "showed no clear difference in the odds of being")
    return (f"{UNIT_MANY} {T.what_of(e['factor'])} {side} {T.what_of(outcome)} (odds ratio "
            f"{e['estimate']:.2f}, 95% range {e['low']:.2f} to {e['high']:.2f})")


def filled_length(name, text):
    t, outcome = truth(name), options(name)["outcome"]
    for i, e in enumerate(t["odds"], 1):
        phrase = odds_text(e, outcome)
        assert re.fullmatch(T.odds_re(e, UNIT_MANY, outcome), phrase)
        text = text.replace(f"{{a1.odds.{i}}}", phrase)
    return len(text.replace("{a1.held}", held(name)))


def padded(name, head, limit, over):
    """`head` and one more sentence `Here it is and the data ... .`: the longest that is at
    most `limit` characters once filled, or (over) one ` and the data` more than that."""
    def text(n):
        return head + " Here it is" + " and the data" * n + "."
    n = 0
    while filled_length(name, text(n + 1)) <= limit:
        n += 1
    out = text(n + 1 if over else n)
    assert (filled_length(name, out) > limit) is over
    return out


@pytest.mark.needs_r
@pytest.mark.parametrize("name,head,k,over", [
    ("yn_main", ONE, 1, False), ("yn_main", ONE, 1, True),      # 600 characters
    ("yn_four", FOUR, 4, False), ("yn_four", FOUR, 4, True),    # 1,000 characters
])
def test_r1_characters_with_odds_slots(tmp_path, monkeypatch, name, head, k, over):
    """S11 2i: the larger of 600 and 200 k + 200 characters once filled; within k + 2
    sentences in every text here."""
    sentences, limit = T.r1_limits(k)
    text = padded(name, head, limit, over)
    assert len(re.findall(r"[.!?](?:\s|$)", text)) <= sentences
    env = StatsEnv(tmp_path, monkeypatch)
    _shape(ask(env, arguments(name), text), not over)
