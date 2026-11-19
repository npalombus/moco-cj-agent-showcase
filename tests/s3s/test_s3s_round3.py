"""Round 3 of Part S: docs/S3S-DESIGN.md S12 (the R side), every point of S12 item 5 that is
part of this round (brief S3S-R3-A). Tests only; a separate session builds it.

Item 1 is part of this round: docs/DECISIONS.md D-058 records it APPROVED.

By S12's items:
- 1: for every trend_compare case of the truth helper, the difference, its range and its
  verdict from the two groups' own fits (to S9's tolerance); that (1 + b's yearly change) /
  (1 + a's yearly change) - 1, from the two own figures at full precision, equals the stated
  difference to one decimal; the fit ratio from the two own fits; that the result names each
  group's model (compare_school's two groups differ: Poisson and negative binomial). The
  truth helper (s3ssupport._truth_compare) computes these since this round; R cross-check:
  kit-log/raw/S3S-R3-A-r-crosscheck.txt (24 pairs, 0 differ).
- 2: the foot line of trend, trend_compare and before_after charts holds the new sentences,
  by month and by quarter, before the source; read from result.json's `chart_labels`.
- 3: `"chart_scales": "own"` for trend_compare, and the added foot sentence.
- 4: the two `read_as` forms, written out by hand, for a flag, a category label and each of
  the three made-up factors, as factor and as outcome (yes_no) and as the part (shares); the
  chart's title is `read_as`; the partial-year axis label of a shares chart.
- 4b: R is started with a short environment (a stand-in for Rscript writes the environment
  it was given into the job folder: tests/s3s/fixtures/r3_env_rscript.sh).
- 4c: a before_after over exactly 24 months with the date in the middle, and at 12 and 13
  months a side, never ends ENGINE_FAILED (a SYNTHETIC series made here for it).
- And: every estimate, range and verdict the round does not change is what it was
  (tests/s3s/fixtures/round3_before.json, saved from the truth helper before this round
  changed it; the trend_compare difference and fit ratio are left out of it).

Every expected text is written out by hand from S12, with the `<what>` fragments of S11
item 1 (as the wording round's tests write them).

READINGS (each in kit-log/raw/S3S-R3-A-notes.txt):
- `chart_labels` is in result.json for every kind (S12 item 5: "result.json ... gains"), a
  dict with the four keys; each value is read with its white space folded (R may wrap a
  line), and `axis` may be one text, a list of texts or a dict of them (S12 does not say).
- The foot line "gains, before the source" the two sentences: they come before the source's
  title in the foot. "(by quarter: `Grey: recorded each quarter, as an average per month.`)"
  replaces the grey sentence; whether the blue one then follows is not said (asked in
  briefs/QUESTIONS.md): both are accepted at that one place.
- Where `The two panels have different scales.` stands in the foot is not said: anywhere.
- Each group's model is read from result.json's `own` entries (`trend_a`, `trend_b`), the
  shape the first build already writes, each with its `model` (capitals not counting).
- `read_as` with a filter: S12 writes `<unit many>`, with no place for the filters (asked
  in briefs/QUESTIONS.md); a case with a filter accepts `arrest records` or `arrest records
  in district 3` there, and nothing else.
- A partial FIRST year on the shares axis takes the same form as the partial last year of
  S12's example: `2021 (Mar to Dec)`; whole years are the bare year.
- 4b: the stand-in is a /bin/sh script; the shell itself adds PWD, SHLVL and `_` (seen with
  `env -i`), which are allowed besides S12's list. The made-up variables are named like keys
  and hold made-up text, never a key.
- 4c: "every named term is finite" is read from result.json (step and bend: estimate and
  both ends); a refusal is TOO_LITTLE with a `why`, no job folder (R not started), and the
  reply's reason code TOO_LITTLE. A build may also widen such a period to the whole copy
  (S13 point 4) and answer: allowed, with every term finite.
"""
import calendar
import json
import math
import os
import re
import shutil
from pathlib import Path

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import (EDGES, EDGES_ID, MAIN, MAIN_ID, Q_BEFORE_AFTER, Q_COMPARE, Q_SHARES,
                      Q_YES_NO, QUESTION, TITLE, UNIT_MANY, StatsEnv, analyze, answered,
                      ask_case, job_folders, result_of)

COMPARES = ["compare_school", "compare_school_rev", "compare_gender", "compare_weapon"]


def fold(text):
    return " ".join(str(text).split())


def labels_of(env):
    """result.json's `chart_labels` (S12 item 5), each value with its white space folded."""
    result = result_of(env)
    found = result.get("chart_labels")
    assert isinstance(found, dict), (f"S12 item 5: result.json gains \"chart_labels\": "
                                     f"{{\"title\", \"subtitle\", \"foot\", \"axis\"}}; it has "
                                     f"{sorted(result)}")
    assert {"title", "subtitle", "foot", "axis"} <= set(found), sorted(found)
    for k in ("title", "subtitle", "foot"):
        assert isinstance(found[k], str) and found[k].strip(), (k, found[k])
    return {"title": fold(found["title"]), "subtitle": fold(found["subtitle"]),
            "foot": fold(found["foot"]), "axis": axis_texts(found["axis"])}


def axis_texts(value):
    if isinstance(value, str):
        return [fold(value)]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [str(value)]
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return [t for v in value for t in axis_texts(v)]
    return []


def signed(x):
    """S10 answer 1, written out: one decimal, `-` below zero, `+` above, `0.0` at zero."""
    text = f"{abs(x):.1f}"
    return text if float(text) == 0 else ("-" if x < 0 else "+") + text


# ---- item 1: trend_compare from the two own fits -----------------------------------------------

# By hand, from kit-log/raw/S3S-R3-A-truth.txt (the truth helper, cross-checked against plain R):
# the difference with one decimal (95% range), the verdict, the fit ratio to four decimals,
# and each group's model. Before this round: -15.2 (-18.5 to -11.7), +17.9 (+13.3 to +22.6),
# +0.3 (-3.3 to +3.9) and -0.7 (-4.5 to +3.2); no verdict changes.
ITEM1 = {
    "compare_school": ("-15.2", "-18.5", "-11.8", True, 1.0759, ("poisson", "negative binomial")),
    "compare_school_rev": ("+18.0", "+13.4", "+22.7", True, 1.0759,
                           ("negative binomial", "poisson")),
    "compare_gender": ("-0.2", "-3.8", "+3.5", False, 1.0835,
                       ("negative binomial", "negative binomial")),
    "compare_weapon": ("-0.5", "-4.2", "+3.4", False, 1.0828, ("poisson", "negative binomial")),
}


def test_item1_the_truth_by_hand():
    """No program code: the truth helper gives the hand-written figures; the difference is the
    two own changes' ratio (exactly, on the model's scale); its standard error is the root of
    the two squared."""
    for name, (est, lo, hi, clear, ratio, models) in ITEM1.items():
        t = T.truth(name)
        d, a, b = t["difference"], t["own"]["a"], t["own"]["b"]
        assert (signed(d["estimate"]), signed(d["low"]), signed(d["high"])) == (est, lo, hi), name
        assert d["clear"] is clear, name
        assert round(t["fit_ratio"], 4) == ratio and not t["fit_line"], name
        assert (t["models"]["a"], t["models"]["b"]) == models, name
        assert math.isclose(d["coef"], b["coef"] - a["coef"], abs_tol=1e-12), name
        assert math.isclose(d["se"], math.hypot(a["se"], b["se"]), abs_tol=1e-12), name
        ratio_of_changes = 100 * ((1 + b["estimate"] / 100) / (1 + a["estimate"] / 100) - 1)
        assert math.isclose(ratio_of_changes, d["estimate"], abs_tol=1e-9), name


def _own(result):
    own = result.get("own")
    assert isinstance(own, list) and len(own) == 2, f"result.json's own trends: {own}"
    named = {e.get("name"): e for e in own}
    assert set(named) == {"trend_a", "trend_b"}, own
    return named["trend_a"], named["trend_b"]


def _difference(result):
    (d,) = [e for e in result.get("estimates", []) if e.get("name") == "difference"]
    return d


@pytest.mark.needs_r
@pytest.mark.parametrize("name", COMPARES)
def test_item1_difference_range_verdict_ratio_and_models(tmp_path, monkeypatch, name):
    """S12 item 1: R's difference, range and verdict are those of the two own fits (S9's
    tolerance), and so is the fit ratio; the result names each group's model."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, name, text="I found that {a1.difference}."))
    result = result_of(env)
    t = T.truth(name)
    d = _difference(result)
    want = t["difference"]
    assert T.estimate_matches(d, want, T.TOL_PCT, T.TOL_PCT_END), (
        f"the difference is not b(B) - b(A) of the two own fits: R {d['estimate']:.5f} "
        f"({d['low']:.5f} to {d['high']:.5f}), the two own fits {want['estimate']:.5f} "
        f"({want['low']:.5f} to {want['high']:.5f})")
    assert d.get("clear") is want["clear"], (d.get("clear"), want["clear"])
    ratio = result.get("fit_ratio")
    assert isinstance(ratio, (int, float)) and abs(ratio - t["fit_ratio"]) <= T.TOL_RATIO, (
        f"the fit ratio is not the two own fits': R {ratio}, the two own fits "
        f"{t['fit_ratio']:.6f}")
    a, b = _own(result)
    assert (str(a.get("model")).lower(), str(b.get("model")).lower()) == ITEM1[name][5], (
        "each group's model", a.get("model"), b.get("model"))


@pytest.mark.needs_r
@pytest.mark.parametrize("name", COMPARES)
def test_item1_the_stated_difference_follows_from_the_two_table_lines(tmp_path, monkeypatch,
                                                                      name):
    """S12 item 1: (1 + b's change) / (1 + a's change) - 1, from the two own figures at full
    precision (result.json), equals the stated difference to one decimal: in result.json and
    in the reply's phrase; and the reply's two table lines show those own figures."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name, text="I found that {a1.difference}."))
    result = result_of(env)
    a, b = _own(result)
    x = 100 * ((1 + b["estimate"] / 100) / (1 + a["estimate"] / 100) - 1)
    stated = _difference(result)["estimate"]
    assert f"{x:.1f}" == f"{stated:.1f}", (
        f"the two lines shown give {x:.4f}% ({a['estimate']:.4f}% and {b['estimate']:.4f}% a "
        f"year); the stated difference is {stated:.4f}%")
    if _difference(result)["clear"]:
        words = f"was about {abs(x):.1f}% {'above' if x > 0 else 'below'} the yearly trend"
    else:
        words = f"was about {signed(x)}%, 95% range"
    assert words in reply.text, (words, reply.text)
    for e in (a, b):
        assert f": about {signed(e['estimate'])}% a year (95% range" in reply.text, (
            e, reply.text)


# ---- items 2 and 3: the foot line and the panels' scales -----------------------------------------

GREY_MONTH = "Grey: recorded each month."
GREY_QUARTER = "Grey: recorded each quarter, as an average per month."
BLUE = "Blue: the model's line and its 95% range."
SCALES = "The two panels have different scales."
S6_FOOT = f"recorded {UNIT_MANY}, not people; patterns, not causes"   # S6's own part stays


def _edges_args(kind, **options):
    base = {"kind": kind, "source": EDGES_ID, "period": T.P5, "filters": T.batch("Q1")}
    if options:
        base["options"] = options
    return base


# by quarter on the edges source: batch Q1 has months from 1 to 9 and no quarter under 10
BY_QUARTER = {
    "trend": (_edges_args("trend"), "{a1.trend}."),
    "trend_compare": (_edges_args("trend_compare", versus=T.batch("P")), "{a1.difference}."),
    "before_after": (_edges_args("before_after", date="2023-07-01"), "{a1.step}. {a1.bend}."),
}


def _before_source(foot, text, title):
    assert text in foot, f"the foot line lacks {text!r}: {foot!r}"
    assert title in foot, f"the foot line lacks the source {title!r}: {foot!r}"
    assert foot.index(text) + len(text) <= foot.index(title), (
        f"S12 item 2: {text!r} comes before the source: {foot!r}")


# by month on the main source: no month from 1 to 9 (the before_after cases of the truth
# helper are on one district each and are drawn by quarter, so this one has no filter)
BY_MONTH = {
    "trend": (T.analyze_arguments("trend_all"), "{a1.trend}."),
    "trend_compare": (T.analyze_arguments("compare_school"), "{a1.difference}."),
    "before_after": ({"kind": "before_after", "source": MAIN_ID, "period": T.P5, "filters": [],
                      "options": {"date": "2023-07-01"}}, "{a1.step}. {a1.bend}."),
}


def test_the_by_month_cases_have_no_hidden_month():
    for name in ("trend_all", "compare_school"):
        t = T.truth(name)
        counts = t["counts"] if t["kind"] == "trend" else t["counts"]["a"] + t["counts"]["b"]
        assert not any(1 <= n <= 9 for n in counts), name


@pytest.mark.needs_r
@pytest.mark.parametrize("kind", list(BY_MONTH))
def test_item2_the_foot_line_by_month(tmp_path, monkeypatch, kind):
    """S12 item 2: by month, the foot gains `Grey: recorded each month. Blue: the model's line
    and its 95% range.` before the source; S6's part stays; item 3's sentence on
    trend_compare only."""
    args, text = BY_MONTH[kind]
    env = StatsEnv(tmp_path, monkeypatch)
    answered(env.ask(QUESTION[kind], Step(analyze(args)), Step(finish("finding", text))))
    assert result_of(env).get("chart_points") == "month"
    foot = labels_of(env)["foot"]
    _before_source(foot, f"{GREY_MONTH} {BLUE}", TITLE[MAIN])
    assert S6_FOOT in foot.lower(), foot
    assert "each quarter" not in foot, foot
    assert (SCALES in foot) is (kind == "trend_compare"), foot


@pytest.mark.needs_r
@pytest.mark.parametrize("kind", list(BY_QUARTER))
def test_item2_the_foot_line_by_quarter(tmp_path, monkeypatch, kind):
    """S12 item 2: by quarter, the grey sentence is `Grey: recorded each quarter, as an
    average per month.`, before the source (with or without the blue one after it: asked)."""
    args, text = BY_QUARTER[kind]
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    answered(env.ask(QUESTION[kind], Step(analyze(args)), Step(finish("finding", text))))
    assert result_of(env).get("chart_points") == "quarter"
    foot = labels_of(env)["foot"]
    grey = f"{GREY_QUARTER} {BLUE}" if f"{GREY_QUARTER} {BLUE}" in foot else GREY_QUARTER
    _before_source(foot, grey, TITLE[EDGES])
    assert GREY_MONTH not in foot and S6_FOOT in foot.lower(), foot
    assert (SCALES in foot) is (kind == "trend_compare"), foot


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["yn_main", "sh_school", "timing", "ages_gender"])
def test_item2_other_charts_gain_no_line_sentence(tmp_path, monkeypatch, name):
    """S12 item 2 is for trend, trend_compare and before_after: the other charts' foot lines
    gain neither sentence; their result.json has chart_labels too."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, name))
    foot = labels_of(env)["foot"]
    assert "Grey:" not in foot and "Blue:" not in foot and SCALES not in foot, foot
    assert TITLE[MAIN] in foot and S6_FOOT in foot.lower(), foot


@pytest.mark.needs_r
def test_item3_trend_compare_panels_have_their_own_scales(tmp_path, monkeypatch):
    """S12 item 3: result.json records `"chart_scales": "own"` for trend_compare, by month and
    by quarter."""
    env = StatsEnv(tmp_path / "month", monkeypatch)
    answered(ask_case(env, "compare_school"))
    assert result_of(env).get("chart_scales") == "own", result_of(env).get("chart_scales")
    args, text = BY_QUARTER["trend_compare"]
    env = StatsEnv(tmp_path / "quarter", monkeypatch, names=(EDGES,))
    answered(env.ask(Q_COMPARE, Step(analyze(args)), Step(finish("finding", text))))
    assert result_of(env).get("chart_points") == "quarter"
    assert result_of(env).get("chart_scales") == "own", result_of(env).get("chart_scales")


# ---- item 4: the two read_as forms, the title, the partial-year axis label ---------------------

P5_TEXT = "from January 2021 to December 2025"
SCHOOL_YES, SCHOOL_NO = T.is_(T.SCHOOL, True), T.is_(T.SCHOOL, False)
UNDER_18 = {"field": "age", "to": 17}
WEEKEND = {"field": "weekday", "in": ["Saturday", "Sunday"]}
NIGHT = {"field": "hour", "from": 22, "to": 5}

# yes_no: (outcome, factors, controls) on P5 with no filter, and read_as by hand (S12 item 4:
# `the odds of <unit many> being <outcome what>, for those <factor what 1>, ... and <factor
# what k>, <held>, from <first month> to <last month>`)
YES_NO = {
    "flag outcome; flag and category factors": (
        T.SCHOOL, [T.WEAPON, T.FEMALE, T.SHIFT_B], ["district"],
        "the odds of arrest records being within 500 feet of a school, for those with a weapon "
        "recorded, of people recorded as female and on shift B, holding district fixed, "
        f"{P5_TEXT}"),
    "under_18 and weekend as factors": (
        T.SCHOOL, ["under_18", "weekend"], ["district"],
        "the odds of arrest records being within 500 feet of a school, for those of people "
        f"under 18 and on weekends, holding district fixed, {P5_TEXT}"),
    "under_18 as outcome; night as factor": (
        "under_18", ["night", T.WEAPON], [],
        "the odds of arrest records being of people under 18, for those between 10 pm and 5 am "
        f"and with a weapon recorded, with nothing else held fixed, {P5_TEXT}"),
    "weekend as outcome": (
        "weekend", ["under_18", T.SCHOOL], [],
        "the odds of arrest records being on weekends, for those of people under 18 and within "
        f"500 feet of a school, with nothing else held fixed, {P5_TEXT}"),
    "night as outcome; weekend as factor": (
        "night", ["weekend", T.SHIFT_B], [],
        "the odds of arrest records being between 10 pm and 5 am, for those on weekends and on "
        f"shift B, with nothing else held fixed, {P5_TEXT}"),
    "category outcome": (
        T.FEMALE, [T.WEAPON, "night"], [],
        "the odds of arrest records being of people recorded as female, for those with a weapon "
        f"recorded and between 10 pm and 5 am, with nothing else held fixed, {P5_TEXT}"),
}

# shares: the part on P5 with no filter, and read_as by hand (S12 item 4: `the yearly share of
# <unit many> that were <part what>, from <first month> to <last month>`)
SHARES = {
    "a flag": ([SCHOOL_YES], "the yearly share of arrest records that were within 500 feet of a "
                             f"school, {P5_TEXT}"),
    "a flag's no": ([SCHOOL_NO], "the yearly share of arrest records that were not within 500 "
                                 f"feet of a school, {P5_TEXT}"),
    "a category label": ([T.SHIFT_B], "the yearly share of arrest records that were on shift B, "
                                      f"{P5_TEXT}"),
    "under 18": ([UNDER_18], "the yearly share of arrest records that were of people under 18, "
                             f"{P5_TEXT}"),
    "weekends": ([WEEKEND], f"the yearly share of arrest records that were on weekends, {P5_TEXT}"),
    "night": ([NIGHT], "the yearly share of arrest records that were between 10 pm and 5 am, "
                       f"{P5_TEXT}"),
}


def _read_as(env):
    answer = env.model.answer(0)
    assert answer.get("result_id") == "a1", answer
    return answer["read_as"]


def _title_is(title, read_as):
    """S12 item 4: the chart's title is read_as (Python writes it; the chart only prints it)."""
    assert title == fold(read_as[:1].upper() + read_as[1:]), (title, read_as)


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(YES_NO))
def test_item4_read_as_of_yes_no(tmp_path, monkeypatch, label):
    outcome, factors, controls, want = YES_NO[label]
    env = StatsEnv(tmp_path, monkeypatch)
    args = {"kind": "yes_no", "source": MAIN_ID, "period": T.P5, "filters": [],
            "options": {"outcome": outcome, "factors": factors, "controls": controls}}
    slots = " ".join(f"{{a1.odds.{i}}}." for i in range(1, len(factors) + 1))
    answered(env.ask(Q_YES_NO, Step(analyze(args)), Step(finish("finding", slots))))
    read_as = _read_as(env)
    assert read_as == want, f"\n got: {read_as}\nwant: {want}"
    _title_is(labels_of(env)["title"], want)


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(SHARES))
def test_item4_read_as_of_shares(tmp_path, monkeypatch, label):
    part, want = SHARES[label]
    env = StatsEnv(tmp_path, monkeypatch)
    args = {"kind": "shares", "source": MAIN_ID, "period": T.P5, "filters": [],
            "options": {"part": part}}
    answered(env.ask(Q_SHARES, Step(analyze(args)),
                     Step(finish("finding", "{a1.share}. {a1.sharetrend}."))))
    read_as = _read_as(env)
    assert read_as == want, f"\n got: {read_as}\nwant: {want}"
    _title_is(labels_of(env)["title"], want)


@pytest.mark.needs_r
@pytest.mark.parametrize("kind", ["yes_no", "shares"])
def test_item4_read_as_with_a_filter_accepts_both_readings(tmp_path, monkeypatch, kind):
    """S12 writes `<unit many>` with no place for the filters (asked): with district 3 as a
    filter, `arrest records` or `arrest records in district 3`, and nothing else."""
    env = StatsEnv(tmp_path, monkeypatch)
    if kind == "yes_no":
        options = {"outcome": T.SCHOOL, "factors": [T.WEAPON, T.SHIFT_B], "controls": []}
        text = "{a1.odds.1}. {a1.odds.2}."
        forms = [f"the odds of {many} being within 500 feet of a school, for those with a "
                 f"weapon recorded and on shift B, with nothing else held fixed, {P5_TEXT}"
                 for many in ("arrest records", "arrest records in district 3")]
    else:
        options = {"part": [SCHOOL_YES]}
        text = "{a1.share}. {a1.sharetrend}."
        forms = [f"the yearly share of {many} that were within 500 feet of a school, {P5_TEXT}"
                 for many in ("arrest records", "arrest records in district 3")]
    args = {"kind": kind, "source": MAIN_ID, "period": T.P5, "filters": T.district(3),
            "options": options}
    answered(env.ask(Q_YES_NO if kind == "yes_no" else Q_SHARES, Step(analyze(args)),
                     Step(finish("finding", text))))
    read_as = _read_as(env)
    assert read_as in forms, f"\n got: {read_as}\nwant one of: {forms}"
    _title_is(labels_of(env)["title"], read_as)


# (period, the window's first and last month as read_as writes them, the partial year's axis
# label, the whole years' labels)
PARTIAL = {
    "a partial last year": (T.P6, "from January 2021 to August 2026", "2026 (Jan to Aug)",
                            ["2021", "2022", "2023", "2024", "2025"]),
    "a partial first year": ({"from": "2021-03-01", "to": "2025-12-31"},
                             "from March 2021 to December 2025", "2021 (Mar to Dec)",
                             ["2022", "2023", "2024", "2025"]),
}


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(PARTIAL))
def test_item4_the_partial_year_axis_label(tmp_path, monkeypatch, label):
    """S12 item 4: a partial year on the shares chart's axis is labelled `2026 (Jan to Sep)`
    (here the fixture's window ends in August); whole years are the bare year. Read from
    chart_labels' `axis`."""
    period, months, partial, whole = PARTIAL[label]
    src = T.source_json(MAIN)
    window = T.window(src, period)
    assert (T.month_text(window[0]), T.month_text(window[-1])) == tuple(months[5:].split(" to "))
    env = StatsEnv(tmp_path, monkeypatch)
    args = {"kind": "shares", "source": MAIN_ID, "period": period, "filters": [],
            "options": {"part": [SCHOOL_YES]}}
    answered(env.ask(Q_SHARES, Step(analyze(args)),
                     Step(finish("finding", "{a1.share}. {a1.sharetrend}."))))
    read_as = _read_as(env)
    assert read_as == ("the yearly share of arrest records that were within 500 feet of a "
                       f"school, {months}"), read_as
    axis = labels_of(env)["axis"]
    joined = " | ".join(axis)
    assert partial in joined, f"the axis lacks the partial year's label {partial!r}: {axis}"
    for year in whole:
        assert year in joined and f"{year} (" not in joined, (year, axis)


# ---- item 4b: R is started with a short environment ---------------------------------------------

STAND_IN = T.FIXTURES / "r3_env_rscript.sh"
ALLOWED = {"PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR"}   # S12 item 4b, and R_*
SHELL_OWN = {"PWD", "OLDPWD", "SHLVL", "_"}                     # what /bin/sh adds itself
FAKE = "MOCO_R3_FAKE_KEY"
FAKE_VALUE = "made-up-value-r3-not-a-key"


def _r_environment(tmp_path, monkeypatch):
    rscript = tmp_path / "bin" / "Rscript"
    rscript.parent.mkdir(parents=True)
    shutil.copyfile(STAND_IN, rscript)
    rscript.chmod(0o755)
    library = tmp_path / "r-library"
    monkeypatch.setenv(FAKE, FAKE_VALUE)
    monkeypatch.setenv("R3_FAKE_TOKEN", FAKE_VALUE)   # starts with R3_, not R_: not R's
    monkeypatch.setenv("R_LIBS_USER", str(library))
    monkeypatch.setenv("MOCO_RSCRIPT", str(rscript))
    env = StatsEnv(tmp_path, monkeypatch, MOCO_RSCRIPT=str(rscript))
    reply = ask_case(env, "trend_all")
    folders = job_folders(env)
    assert len(folders) == 1, folders
    path = folders[0] / "r_environment.txt"
    assert path.is_file(), "the stand-in for Rscript was not started on the job folder"
    names = {line for line in path.read_text(encoding="utf-8").splitlines()
             if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", line)}
    libs = folders[0] / "r_libs_user.txt"
    value = libs.read_text(encoding="utf-8").rstrip("\n") if libs.is_file() else None
    assert reply.status != "ANSWERED"   # the stand-in stops; nothing real was run
    return names, value, str(library)


def _ours(names):
    """Only the names this test and conftest set are written into a message (the stand-in
    records names only; the session's own variables are not listed)."""
    return sorted(n for n in names if n.startswith(("MOCO_", "R3_")))


def test_the_stand_in_for_rscript():
    """No program code: the stand-in is the SYNTHETIC fixture file, a /bin/sh script that runs
    nothing but /usr/bin/env and writes names, never values (but R_LIBS_USER's)."""
    text = STAND_IN.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n") and "SYNTHETIC" in text
    commands = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    assert any(line.startswith("/usr/bin/env |") for line in commands)
    assert any("${line%%=*}" in line for line in commands)   # the name before the first =
    assert not any("Rscript" in line or "exec" in line for line in commands), commands


def test_item4b_r_gets_no_key_and_keeps_path(tmp_path, monkeypatch):
    """S12 item 4b: a made-up variable named like a key, set in the agent's environment, does
    not reach R; PATH does; R_LIBS_USER set the same way does, with its value."""
    names, value, library = _r_environment(tmp_path, monkeypatch)
    assert FAKE not in names, f"{FAKE} reached R (with {_ours(names)})"
    assert "PATH" in names, "PATH did not reach R"
    assert "R_LIBS_USER" in names and value == library, ("R_LIBS_USER", value, library)
    assert os.environ.get(FAKE) == FAKE_VALUE   # it was in the agent's environment


def test_item4b_r_gets_nothing_but_the_short_list(tmp_path, monkeypatch):
    """S12 item 4b: R gets only PATH, HOME, LANG, LC_ALL, TZ, TMPDIR and variables whose name
    starts with R_ (the shell's own PWD, SHLVL and `_` aside): no MOCO_ variable (this test's
    MOCO_ENV_FILE and MOCO_RSCRIPT), nothing named R3_."""
    names, _, _ = _r_environment(tmp_path, monkeypatch)
    extra = sorted(n for n in names if n not in ALLOWED | SHELL_OWN and not n.startswith("R_"))
    assert not extra, (f"R was given {len(extra)} variables beyond S12 item 4b's list, among "
                       f"them {_ours(extra)}")


# ---- item 4c: a before_after at the edge of S3 ------------------------------------------------------

_SEASON = (0.92, 0.88, 0.97, 1.00, 1.05, 1.08, 1.10, 1.07, 1.02, 1.00, 0.96, 0.95)
_WOBBLE = (1.06, 0.95, 1.02, 0.97, 1.04, 0.99, 0.93, 1.05, 1.01, 0.96, 1.03, 0.98, 1.07)


def edge_rows():
    """SYNTHETIC: a made-up monthly series of arrest records for S12 item 4c, January 2021 to
    14 October 2026 (the fixture's newest day, so S2's window ends in August 2026): about 60
    a month, a slow rise, a seasonal pattern and a 13-month wobble; every month 10 or more.
    Labelled SYNTHETIC in every row; no row is a real record."""
    rows = []
    for y in range(2021, 2027):
        for m in range(1, 13):
            if (y, m) > (2026, 10):
                break
            k = (y - 2021) * 12 + m - 1
            n = round(60 * 1.004 ** k * _SEASON[m - 1] * _WOBBLE[k % 13])
            days = 14 if (y, m) == (2026, 10) else calendar.monthrange(y, m)[1]
            for j in range(n):
                rows.append({
                    "id": f"FIXTURE-R3-EDGE-{len(rows) + 1:05d}",
                    "event_date_time": f"{y:04d}-{m:02d}-{1 + j % days:02d}T{(7 * j) % 24:02d}:"
                                       f"{(13 * j) % 60:02d}:00.000",
                    "age": str(18 + j % 50), "gender": ("Male", "Female")[j % 2],
                    "district": str(1 + j % 7), "shift": ("A", "B")[j % 3 == 0],
                    "adjacent_to_school": "1" if j % 5 == 0 else "0",
                    "weapon": "1" if j % 11 == 0 else "0", "data_class": "SYNTHETIC"})
    return rows


# label: (rows, period, date, months before the date, months from it on)
EDGE_CASES = {
    "24 months, 12 a side (2024-2025, date January 2025)":
        ("made", {"from": "2024-01-01", "to": "2025-12-31"}, "2025-01-01", 12, 12),
    "24 months, 12 a side (2023-2024, date January 2024)":
        ("made", {"from": "2023-01-01", "to": "2024-12-31"}, "2024-01-01", 12, 12),
    "24 months, 12 a side (July 2023 to June 2025, date July 2024)":
        ("made", {"from": "2023-07-01", "to": "2025-06-30"}, "2024-07-01", 12, 12),
    "25 months, 12 before and 13 from the date on":
        ("made", {"from": "2024-01-01", "to": "2026-01-31"}, "2025-01-01", 12, 13),
    "25 months, 13 before and 12 from the date on":
        ("made", {"from": "2023-12-01", "to": "2025-12-31"}, "2025-01-01", 13, 12),
    "24 months, 12 a side, on the main fixture":
        ("main", {"from": "2024-01-01", "to": "2025-12-31"}, "2025-01-01", 12, 12),
}


def test_item4c_the_edge_cases_by_counting():
    """No program code: each case's window and sides are as labelled; the made-up series has
    no month from 1 to 9 (so no chart by quarter) and every row says SYNTHETIC."""
    src = T.source_json(MAIN)
    rows = edge_rows()
    assert all(r["data_class"] == "SYNTHETIC" for r in rows)
    assert max(r["event_date_time"][:10] for r in rows) == T.NEWEST.isoformat()
    by_month = {}
    for r in rows:
        ym = (int(r["event_date_time"][:4]), int(r["event_date_time"][5:7]))
        by_month[ym] = by_month.get(ym, 0) + 1
    assert min(by_month.values()) >= 10, min(by_month.values())
    for label, (_, period, when, before, after) in EDGE_CASES.items():
        months = T.window(src, period)
        ym = (int(when[:4]), int(when[5:7]))
        assert (sum(m < ym for m in months), sum(m >= ym for m in months)) == (before, after), \
            label


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(EDGE_CASES))
def test_item4c_a_before_after_at_the_edge_never_ends_engine_failed(tmp_path, monkeypatch,
                                                                    label):
    """S12 item 4c: either every term the reply names (step, bend) is finite, or the turn ends
    TOO_LITTLE (with a why) before R is started; never ENGINE_FAILED."""
    which, period, when, _, _ = EDGE_CASES[label]
    rows = {MAIN: edge_rows()} if which == "made" else None
    env = StatsEnv(tmp_path, monkeypatch, rows=rows)
    args = {"kind": "before_after", "source": MAIN_ID, "period": period, "filters": [],
            "options": {"date": when}}
    reply = env.ask(Q_BEFORE_AFTER, Step(analyze(args)),
                    Step(finish("finding", "{a1.step}. {a1.bend}.")))
    assert reply.reason_code != "ENGINE_FAILED", (
        f"S12 item 4c: {label} ended ENGINE_FAILED: {reply.text}")
    answer = env.model.answer(0)   # (an ENGINE_ error ends the turn at the call: no answer)
    if answer.get("error") == "TOO_LITTLE":
        assert isinstance(answer.get("why"), str) and answer["why"].strip(), answer
        assert job_folders(env) == [], "a refusal comes before R is started"
        assert reply.reason_code == "TOO_LITTLE", (reply.status, reply.reason_code)
        return
    assert answer.get("result_id") == "a1", (label, answer)
    entries = {e.get("name"): e for e in result_of(env).get("estimates", [])}
    for term in ("step", "bend"):
        e = entries.get(term)
        assert e is not None and all(
            isinstance(e.get(k), (int, float)) and math.isfinite(e[k])
            for k in ("estimate", "low", "high")), (term, e)
    answered(reply)


# ---- what the round does not change ---------------------------------------------------------------

def test_every_estimate_range_and_verdict_the_round_does_not_change():
    """Brief S3S-R3-A step 5: every case of the truth helper against the numbers saved from it
    before this round changed it (within 1e-4, as the wording round's own check). Left out of
    the file, and only these: the trend_compare difference and fit ratio (S12 item 1)."""
    before = json.loads((T.FIXTURES / "round3_before.json").read_text(encoding="utf-8"))
    assert set(before) == set(T.CASES)

    def same(now, then, where):
        for k in ("estimate", "low", "high"):
            assert math.isclose(now[k], then[k], rel_tol=0, abs_tol=1e-4), (where, k, now[k],
                                                                              then[k])
        assert now["clear"] is then["clear"], where

    for name, item in before.items():
        t = T.truth(name)
        assert t["kind"] == item["kind"], name
        if t["kind"] == "trend_compare":
            assert set(item) == {"kind", "own"}, (name, sorted(item))
            for k, then in item["own"].items():
                same(t["own"][k], then, (name, "own", k))
            continue
        assert [e["name"] for e in t["estimates"]] == [e["name"] for e in item["estimates"]]
        for now, then in zip(t["estimates"], item["estimates"]):
            same(now, then, (name, now["name"]))
        if t["kind"] in ("trend", "before_after"):
            assert math.isclose(t["fit_ratio"], item["fit_ratio"], rel_tol=0, abs_tol=1e-6), name
            assert t["fit_line"] is item["fit_line"], name
        for year, then in item.get("years", {}).items():
            v = t["years"][int(year)]
            for k, now in (("share", v["share"]), ("low", v["range"][0]),
                           ("high", v["range"][1])):
                assert math.isclose(now, then[k], rel_tol=0, abs_tol=1e-4), (name, year, k)
        if t["kind"] == "timing":
            assert (t["busiest_n"], t["quietest_n"]) == (item["busiest_n"], item["quietest_n"])
        if t["kind"] == "distribution":
            assert {str(k): v for k, v in t["groups"].items()} == item["groups"], name
