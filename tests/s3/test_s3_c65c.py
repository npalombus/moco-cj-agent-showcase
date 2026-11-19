"""C65 points 8 and 9 (docs/S3A-DESIGN.md, 18 Nov 10:22 EST; D-082): point 8, the age chart's bars are
figures; point 9, a big conversation is decided slice by slice. Brief: briefs/S3-R31-A-tests.md.
Tests only; red until the planning chat builds points 8 and 9, except those that pin what stays
(named in their docstrings and in kit-log/raw/S3-R31-A-notes.txt). The distributions that R runs
for are in tests/s3s/test_s3s_c65c.py.

Everything here is SYNTHETIC: the fixtures of tests/s3/fixtures (arrests_like, and made-up copies of
its file with other usable ages), test_s3_c54.py's juvenile-like source, and round 30's made-up
oracle source (tests/s3/test_s3_c65b.py). No figure of a real county source is used or quoted.

What is here, in the brief's order:
3. Point 8: counting.shown_bands(..., steps=True) and shown_figures(..., steps=True); the function
   on distributions with counts (every example of point 8's Tests and this session's own cases,
   OWN_8, each saying what point 8's words decide); county turns with the model stand-in: a
   distribution refused on its own before anything is computed, one let through by the check, one
   remembered from an earlier turn and one kept through `reset`, and which statistics are given the
   steps.
4. Point 9: (a) soundness with counting.WORK_EXACT at 0 and at 20,000 against the bound out of reach,
   on 1,200 seeded sets of this file's own and on round 30's oracle; (b) the examples of points 1 to
   8 with the bound as it is; (c) size: a thread of 22 counts of 2025, alone, after a trend, and
   after a trend, a rate by age band and two distributions; (d) a first step refused early, as
   point 9 allows.

Readings (also in the notes; the open ones in briefs/QUESTIONS.md):
- R31-1. The steps: two-year steps from the even age at or below the source's first usable age (10
  and 11, 12 and 13, ...), to the source's last usable age; each is cut to the distribution's own
  ages (the band of its own age filter, or every usable age when it has none) and so also to the
  source's usable ages; a step with nothing left gives no figure. They are added to the bands
  shown_bands gives today (the distribution's own band). `steps` is a keyword that is False unless
  given.
- R31-2. A distribution by a field ("one row of bars for each of its groups") needs nothing more:
  a statistic's figures are held against every part of its records (C65 point 2), so each step is
  known for each group alone.
- R31-3. A distribution refused by the check on its own: tool answer NOT_ALLOWED, the age field,
  C21's `why` word for word without C61 point 10's sentence; the turn ends as a count C21 refuses
  on its own figures ends: UNSUPPORTED, NOT_ALLOWED, the reply the NOT_ALLOWED row and the
  can-ask sentence (test_s3_c65.OLD_SENTENCE). Nothing computed: stats.prepare, run_r, write_job
  and rates.count not called, no job folder, no saved record.
- R31-4. "Given" through a county turn in this file (no R): the check lets it through, so
  stats.prepare is reached; prepare is replaced by a stand-in that refuses with TOO_LITTLE, so no R
  runs here. With R: tests/s3s/test_s3s_c65c.py.
- R31-5. Point 9 "never says no where it says yes with the bound out of reach": out of reach is
  WORK_EXACT = 10**18. The test sets WORK_EXACT with monkeypatch on the module counting; a
  build that reads it once at import would not be tested by it (the tests then fail their premise
  that slicing happens at 0).
- R31-6. The size test: "decided" is one call of counting.one_year_under_18 with every count of the
  thread and the statistics' figures as the turn gives them (a rate with the Census's bands, a
  distribution with the steps); peak memory by tracemalloc (numpy's arrays are traced too); the
  time without tracemalloc, the best of two tries. A guard stops a decision that passes 300 MB or
  60 seconds, so a build without point 9 fails here without taking the machine's memory.
- R31-7. "The examples of points 1 to 8" are the parametrized function cases of round 29
  (FUNCTION_CASES but the one whose answer is a question, COPY_CASES), round 30 (POINT_6_CASES,
  OWN_CASES, RATE_CASES) and this file (CASES_8, OWN_8).
- R31-8. Point 9's sliced first step (d): with WORK_EXACT = 0, under 18 in 2025 and then ages 10 to
  16 from January to June: the halves are the dimension with the most entries; in the first half's
  slice "under 18" is taken as known for that half alone, so 10 to 16 of the half gives the
  17-year-olds of the half: refused one step early. With the bound out of reach it is answered.
"""
import inspect
import random
import signal
import time
import tracemalloc
from datetime import date

import pytest

from p1support import Step, finish, mod
from s3support import (A_ID, C65_CENSUS_BANDS, SCHOOL, CountyEnv, age, dates, hours, in_, months,
                       source_json, weekdays, years)
from test_s3_c54 import juvenile_source
from test_s3_c61d import assert_answered, assert_refused
from test_s3_c65 import (A10_16, ALPHA_BETA, COPY_CASES, D3, D5, F, FIRST_DAY,
                         FUNCTION_CASES, GAMMA, H1, H2, M, NEAR, NEW_SENTENCE, NEWEST_A,
                         OLD_SENTENCE, QUARTERS, QUESTION_CASE, RATE, RATE_BY_BAND, SINCE_2024,
                         TALK, U18_25, Y24, Cnt, Stat, Talk, analyze, ask_counts, assert_refused_end,
                         decide, fcopy, given, holds, nothing_run, plain, run_case, slack_env,
                         spy_runs)
from test_s3_c65b import (OWN_CASES, POINT_6_CASES, RATE_CASES, SEEDS, decide_7, o_program, o_set,
                          oracle, remember, replace_results)
from test_s3_round5 import A, U17, U18, WHY, Y25, spec

CENSUS = list(C65_CENSUS_BANDS)
EVERY = Stat("distribution", SINCE_2024, [], raw={})
OUT_OF_REACH = 10 ** 18


def dist(filters=(), period=SINCE_2024, by=None, days=None):
    """A distribution (options as check_options keeps them: {"by": field or None})."""
    return Stat("distribution", period, list(filters), options={"by": by}, days=days)


def decide_8(items, src=None, newest=NEWEST_A):
    """one_year_under_18 on the items as the turn gives them: a distribution's figures with the
    steps (point 8), a rate's with the Census's bands (point 7), any other statistic's as today."""
    counting = mod("counting")
    src = src or source_json(A)
    copy = fcopy(newest, src["id"])
    start = date.fromisoformat(src["coverage_start"])
    specs, days, shown = [], [], []
    for it in items:
        s = counting.check_spec(src, copy, {"source": src["id"], "period": it.period,
                                            "filters": list(it.filters),
                                            "group_by": list(it.group_by)})
        if isinstance(it, Stat):
            options = it.options if it.raw is None else \
                mod("stats").check_options(src, s, it.kind, it.raw)
            first, last = it.days or (start, newest)
            kw = {}
            if it.kind == "distribution":
                kw["steps"] = True
            if it.kind == "rate":
                kw["age_bands"] = CENSUS
            shown.extend(counting.shown_figures(src, s, options, first, last, **kw))
        else:
            specs.append(s)
            days.append(it.days)
    kw = {"shown": shown} if any(isinstance(it, Stat) for it in items) else {}
    if any(d is not None for d in days):
        kw["days"] = days
    return bool(counting.one_year_under_18(src, specs, copy, **kw))


def usable_source(first, last, sid="FIXTURE:r31_usable"):
    """arrests_like's file with other usable ages (made up for these tests) and another id."""
    src = source_json(A)
    src["id"] = sid
    (f,) = [f for f in src["fields"] if f["kind"] == "age"]
    f["usable"] = [first, last]
    f["bands"] = [[first, min(17, last)]] + ([[18, last]] if last >= 18 else [])
    return src


def checked(src, period, filters=(), group_by=(), newest=NEWEST_A):
    return mod("counting").check_spec(src, fcopy(newest, src["id"]),
                                      {"source": src["id"], "period": period,
                                       "filters": list(filters), "group_by": list(group_by)})


def steps_of(first, last, low, high):
    """R31-1, written out: the two-year steps of a source whose usable ages are first to last,
    cut to low to high."""
    out = []
    for b in range(first - first % 2, last + 1, 2):
        a, z = max(b, low, first), min(b + 1, high, last)
        if a <= z:
            out.append((a, z))
    return out


# ==== step 3: point 8, shown_bands and shown_figures ================================================

BANDS_8 = {  # name: (source, filters, expected bands with steps=True)
    "every age": (A, [], [(10, 98)] + steps_of(10, 98, 10, 98)),
    "under 18": (A, [U18], [(10, 17), (10, 11), (12, 13), (14, 15), (16, 17)]),
    "ages 16 to 17": (A, [age(16, 17)], [(16, 17)]),
    "ages 10 to 16 (its last step is the 16-year-olds)": (
        A, [A10_16], [(10, 16), (10, 11), (12, 13), (14, 15), (16, 16)]),
    "ages 15 to 17 (its first step is the 15-year-olds)": (
        A, [age(15, 17)], [(15, 17), (15, 15), (16, 17)]),
    "ages 17 to 30": (A, [age(17, 30)], [(17, 30), (17, 17)] + steps_of(10, 98, 18, 30)),
    "the last usable age, 98, is a step of its own": (
        A, [age(90)], [(90, 98), (90, 91), (92, 93), (94, 95), (96, 97), (98, 98)]),
    "a source whose usable ages end at 17": (
        "juvenile", [], [(10, 17), (10, 11), (12, 13), (14, 15), (16, 17)]),
    "a source whose usable ages start at 11 (steps from 10)": (
        (11, 98), [], [(11, 98), (11, 11)] + steps_of(10, 98, 12, 98)),
    "a source whose usable ages start at 13, 15 and over": (
        (13, 40), [age(15)], [(15, 40), (15, 15)] + steps_of(10, 40, 16, 40)),
}


def source_named(name):
    if name == "juvenile":
        return juvenile_source()
    if isinstance(name, tuple):
        return usable_source(*name)
    return source_json(name)


@pytest.mark.parametrize("name", list(BANDS_8))
def test_p8_shown_bands_with_the_steps(name):
    """Point 8 (R31-1): shown_bands(..., steps=True) of a distribution gives its own band and the
    two-year steps from an even age, each cut to its own ages."""
    which, filters, expected = BANDS_8[name]
    src = source_named(which)
    got = mod("counting").shown_bands(src, checked(src, Y25, filters), {"by": None}, steps=True)
    assert set(map(tuple, got)) == set(expected), (name, sorted(got))


@pytest.mark.parametrize("kw", [{}, {"steps": False}], ids=["steps left out", "steps=False"])
def test_p8_shown_bands_without_the_steps_is_as_today(kw):
    """Without `steps` (or with steps=False) a distribution of ages 10 to 16 shows its own band
    only, as today. With `steps` left out this passes today; must still pass."""
    src = source_json(A)
    got = mod("counting").shown_bands(src, checked(src, Y25, [A10_16]), {"by": None}, **kw)
    assert set(map(tuple, got)) == {(10, 16)}, got


def test_p8_shown_figures_with_the_steps():
    """shown_figures passes `steps` on: each band over the days of the period (2025), held against
    every value (no field constraint)."""
    src = source_json(A)
    got = mod("counting").shown_figures(src, checked(src, Y25, [age(15, 17)]), {"by": "gender"},
                                        FIRST_DAY, NEWEST_A, steps=True)
    runs = ((date(2025, 1, 1), date(2025, 12, 31)),)
    assert {(tuple(r), tuple(sorted(dict(k).items())), tuple(b)) for r, k, b in got} == \
        {(runs, (), b) for b in [(15, 17), (15, 15), (16, 17)]}, got


# ---- point 8 through the function --------------------------------------------------------------

# name: (items, expected[, source]). True: one single year of age under 18 follows (refused).
CASES_8 = {
    # ---- point 8's Tests ----
    "a distribution of every age, on its own": ([EVERY], False),
    "a distribution of under 18, on its own": ([dist([U18])], False),
    "a distribution of ages 16 to 17, on its own": ([dist([age(16, 17)])], False),
    "a distribution of ages 10 to 16, on its own": ([dist([A10_16])], True),
    "a distribution of ages 15 to 17, on its own": ([dist([age(15, 17)])], True),
    "a distribution of ages 17 to 30, on its own": ([dist([age(17, 30)])], True),
    "the ages of everyone, then ages 10 to 16": ([EVERY, Cnt(Y25, [A10_16])], True),
    "the ages of everyone, then under 18 instead": ([EVERY, U18_25], False),
    "then ages 17 to 18": ([EVERY, U18_25, Cnt(Y25, [age(17, 18)])], False),
    "and 19 and over after them": (
        [EVERY, U18_25, Cnt(Y25, [age(17, 18)]), Cnt(Y25, [age(19)])], True),
    "a source whose usable ages end at 17: every age": ([EVERY], False, "juvenile"),
    "a source whose usable ages end at 17: ages 10 to 16": ([dist([A10_16])], True, "juvenile"),
    # ---- what stays ----
    "the ages of everyone of 2024, then ages 10 to 16 of 2025 (other days)": (
        [dist(period=Y24), Cnt(Y25, [A10_16])], False),
    "a trend of every age, then ages 10 to 16 (no steps for a trend)": (
        [Stat("trend", SINCE_2024, raw={}), Cnt(Y25, [A10_16])], False),
}

# This session's own (step 3), each with what point 8's words decide.
OWN_8 = {
    # "one row of bars for each of its groups" (R31-2)
    "by gender: every age by gender, then female aged 10 to 16 (her bars are figures)": (
        [dist(by="gender"), Cnt(Y25, [A10_16, F])], True),
    "by gender: ages 10 to 16 by gender, on its own": ([dist([A10_16], by="gender")], True),
    "by gender: under 18 by gender, then female under 18": (
        [dist([U18], by="gender"), Cnt(Y25, [U18, F])], False),
    # "two-year steps from an even age": a source whose usable ages start at an odd age
    "a source whose usable ages start at 11: every age (its first bar is the 11-year-olds)": (
        [EVERY], True, (11, 98)),
    "a source whose usable ages start at 11: 12 and over": ([dist([age(12)])], False, (11, 98)),
    "a source whose usable ages start at 11: 11 to 13": ([dist([age(11, 13)])], True, (11, 98)),
    # "cut to its own ages": a step cut to one year of 18 or over is not under 18
    "ages 14 to 20, on its own (its last bar is the 20-year-olds)": ([dist([age(14, 20)])], False),
    # and the source's usable ages are its ages too: a last usable age that is even
    "a source whose usable ages end at 16: every age (its last bar is the 16-year-olds)": (
        [EVERY], True, (10, 16)),
    "a source whose usable ages end at 18: every age (its last bar is the 18-year-olds)": (
        [EVERY], False, (10, 18)),
    # a statistic's figures are of its own days (C65 point 2)
    "under 18 of January to June, then ages 10 to 16 of 2025": (
        [dist([U18], H1), Cnt(Y25, [A10_16])], False),
    "under 18 of January to June, then ages 10 to 16 of January to June": (
        [dist([U18], H1), Cnt(H1, [A10_16])], True),
    # the steps with counts: 12 to 17 and 10 to 16 leave 10, 11 and 16 together
    "ages 12 to 17, then ages 10 to 16": ([dist([age(12, 17)]), Cnt(Y25, [A10_16])], False),
    "ages 12 to 17, then 10 to 16, then 10 to 11 (the 16-year-olds)": (
        [dist([age(12, 17)]), Cnt(Y25, [A10_16]), Cnt(Y25, [age(10, 11)])], True),
    # a distribution of a remembered earlier copy: its own days (C62 point 5)
    "every age of an older copy (to June 2026), then under 17 from July 2026": (
        [dist(period=years(2026), days=(FIRST_DAY, date(2026, 6, 30))),
         Cnt(dates("2026-07-01", "2026-09-17"), [U17])], False),
    "every age of an older copy (to June 2026), then under 17 from January 2026": (
        [dist(period=years(2026), days=(FIRST_DAY, date(2026, 6, 30))),
         Cnt(months(2026, 1, 3), [U17])], True),
}


def run_8(case):
    items, expected, *rest = case
    return decide_8(items, src=source_named(rest[0]) if rest else None), expected


@pytest.mark.parametrize("name", list(CASES_8))
def test_p8_examples_through_the_function(name):
    """Step 3: each example of point 8's Tests (True: the last request is refused)."""
    got, expected = run_8(CASES_8[name])
    assert got is expected, name


@pytest.mark.parametrize("name", list(OWN_8))
def test_p8_own_cases_that_point_8_decides(name):
    """Step 3: this session's own cases, each decided by point 8's words (the name says how)."""
    got, expected = run_8(OWN_8[name])
    assert got is expected, name


# ---- point 8 through county turns (the model stand-in; no R) -----------------------------------

def stub_prepare(monkeypatch):
    """R31-4: stats.prepare replaced by a stand-in that records the call and refuses with
    TOO_LITTLE, so the check's answer is seen without R."""
    calls = []
    counting = mod("counting")

    def prepare(*args, **kwargs):
        calls.append(args[4] if len(args) > 4 else kwargs.get("kind"))
        raise counting.SpecError("TOO_LITTLE", rule="records",
                                 why="SYNTHETIC test stand-in: not computed in this test")
    monkeypatch.setattr(mod("stats"), "prepare", prepare)
    return calls


DIST_ALONE_REFUSED = {"ages 10 to 16": A10_16, "ages 15 to 17": age(15, 17),
                      "ages 17 to 30": age(17, 30)}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("ages", list(DIST_ALONE_REFUSED))
def test_p8_a_distribution_refused_on_its_own_before_anything_is_computed(tmp_path, monkeypatch,
                                                                           ages, talk):
    """Point 8's test: a distribution of ages 10 to 16, 15 to 17 or 17 to 30, as the first message of
    a thread: NOT_ALLOWED with C21's `why` and no word of earlier figures; nothing computed, no job
    folder, no record; the reply the NOT_ALLOWED row (R31-3). Talk off and on."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    calls = spy_runs(monkeypatch)
    reply = env.ask("how old are the people arrested?",
                    Step(analyze("distribution", SINCE_2024, [DIST_ALONE_REFUSED[ages]])),
                    Step(finish("finding", "I found that.")))
    assert_refused(env.model.answer(0), why=WHY)
    nothing_run(env, calls)
    assert_refused_end(env, reply, before=0, sentence=OLD_SENTENCE)


DIST_ALONE_GIVEN = {"every age": [], "under 18": [U18], "ages 16 to 17": [age(16, 17)],
                    "ages 14 to 20": [age(14, 20)]}


@pytest.mark.parametrize("ages", list(DIST_ALONE_GIVEN))
def test_p8_a_distribution_the_check_lets_through(tmp_path, monkeypatch, ages):
    """Point 8's test: a distribution of every age, of under 18, of ages 16 to 17 (and, own, 14 to
    20) on its own is given: the check lets it through to stats.prepare (R31-4). Passes today; must
    still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    calls = stub_prepare(monkeypatch)
    env.ask("how old are the people arrested?",
            Step(analyze("distribution", SINCE_2024, DIST_ALONE_GIVEN[ages])),
            Step(finish("finding", "I found that.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "TOO_LITTLE", answer
    assert calls == ["distribution"], calls


def test_p8_ages_10_to_16_by_gender_refused_on_its_own(tmp_path, monkeypatch):
    """Own (R31-2): a distribution of ages 10 to 16 by gender, as the first message: refused with
    C21's `why` alone, nothing computed."""
    env = CountyEnv(tmp_path, monkeypatch)
    calls = spy_runs(monkeypatch)
    reply = env.ask("how old are the boys and girls arrested aged 10 to 16?",
                    Step(analyze("distribution", SINCE_2024, [A10_16], {"by": "gender"})),
                    Step(finish("finding", "I found that.")))
    assert_refused(env.model.answer(0), why=WHY)
    nothing_run(env, calls)
    assert_refused_end(env, reply, before=0, sentence=OLD_SENTENCE)


def test_p8_a_source_whose_usable_ages_start_at_11(tmp_path, monkeypatch):
    """Own: arrests_like with usable ages 11 to 98 (made up): the distribution of every age is
    refused on its own (its first bar, 10 and 11, is the 11-year-olds alone)."""
    env = CountyEnv(tmp_path, monkeypatch, change={A: lambda s: s["fields"][1].update(
        usable=[11, 98])})
    calls = spy_runs(monkeypatch)
    reply = env.ask("how old are the people arrested?",
                    Step(analyze("distribution", SINCE_2024)),
                    Step(finish("finding", "I found that.")))
    assert_refused(env.model.answer(0), why=WHY)
    nothing_run(env, calls)
    assert_refused_end(env, reply, before=0, sentence=OLD_SENTENCE)


def stored_distribution(filters=(), by=None, period=SINCE_2024, days=("2024-01-01", "2026-09-17"),
                        source=A_ID):
    s = {"source": source, "period": period, "filters": list(filters), "group_by": []}
    out = {"id": "a1", "kind": "analysis", "stat": "distribution", "spec": s,
           "options": {"by": by}, "read_as": "SYNTHETIC ages of arrest records",
           "run_id": "R31-NO-RUN"}
    if days is not None:
        out["days"] = list(days)
    return out


THEN = [("ages 10 to 16", [A10_16], True), ("under 18 instead", [U18], False),
        ("then ages 17 to 18", [age(17, 18)], False), ("and 19 and over", [age(19)], True)]


@pytest.mark.parametrize("talk", TALK)
def test_p8_the_ages_of_everyone_remembered_then_counts(tmp_path, monkeypatch, talk):
    """Point 8's tests, with "a distribution remembered from an earlier turn": an earlier answered
    turn holds the distribution of every age (as the program remembers it); then ages 10 to 16 in
    2025: refused with C62 point 2's sentence; under 18 instead: answered; then 17 to 18: answered;
    and 19 and over after them: refused with the sentence."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    remember(env, stored_distribution())
    for name, filters, refused in THEN:
        reply, (answer,) = ask_counts(env, [spec(Y25, filters)], f"and {name} in 2025?")
        if refused:
            assert_refused(answer)
            assert reply.text == NEW_SENTENCE, (name, reply.text)
        else:
            assert_answered(reply, [answer])


@pytest.mark.parametrize("stored, refused", [
    (stored_distribution(by="gender"), True),
    (stored_distribution(days=None), True),
    (stored_distribution(days=("2024-01-01", "2024-12-31")), False),
    (stored_distribution([age(16, 17)]), False),
], ids=["by gender", "no days: this copy", "days of an older copy, to 2024", "ages 16 to 17"])
def test_p8_a_remembered_distribution_then_10_to_16(tmp_path, monkeypatch, stored, refused):
    """Point 8 and C65 point 2c: a remembered distribution, then ages 10 to 16 in 2025: refused with
    the sentence when its bars give the 17-year-olds of 2025 (by gender too; with no `days`, read
    with this copy), answered when its days end in 2024, or when it is of ages 16 to 17 (pins:
    those two pass today)."""
    env = CountyEnv(tmp_path, monkeypatch)
    remember(env, stored)
    reply, (answer,) = ask_counts(env, [spec(Y25, [A10_16])], "and 10 to 16 in 2025?")
    if refused:
        assert_refused(answer)
        assert reply.text == NEW_SENTENCE, reply.text
    else:
        assert_answered(reply, [answer])


@pytest.mark.parametrize("ages, refused", [(A10_16, True), (U18, False)],
                         ids=["ages 10 to 16", "under 18"])
def test_p8_a_distribution_kept_through_reset(tmp_path, monkeypatch, ages, refused):
    """Point 8 with C65 point 4: an answered turn holding the distribution of every age, `reset`
    (the stripped record keeps "stat": "distribution"), then a count of 2025: 10 to 16 refused with
    C62 point 2's sentence; under 18 answered."""
    env = slack_env(tmp_path, monkeypatch)
    talk = Talk(env)
    label, reply = talk.count(spec(Y24, [age(30, 40)]), "how many aged 30 to 40 in 2024?")
    assert label == "answered", (label, reply.text)
    replace_results(env, [stored_distribution()])
    label, _ = talk.send("reset")
    assert label == "reset"
    kept = plain(given(env))
    assert holds(kept, "distribution"), f"premise: the stripped record keeps it: {kept}"
    label, reply = talk.count(spec(Y25, [ages]), "and how many in 2025?")
    if refused:
        assert_refused(env.model.answer(0))
        assert reply.text == NEW_SENTENCE, reply.text
    else:
        assert label == "answered", (label, reply.text)


def spy_steps(monkeypatch):
    """Records (function, options, steps) of every call of counting.shown_figures and shown_bands,
    read by the real function's own signature (steps None when not passed); each still works."""
    calls = []
    counting = mod("counting")
    for name in ("shown_figures", "shown_bands"):
        real = getattr(counting, name)

        def spy(*args, _real=real, _name=name, **kwargs):
            bound = inspect.signature(_real).bind(*args, **kwargs).arguments
            calls.append((_name, bound.get("options"), bound.get("steps")))
            return _real(*args, **kwargs)
        monkeypatch.setattr(counting, name, spy)
    return calls


def stored_stat(stat, options, sid="a1"):
    s = {"source": A_ID, "period": Y25, "filters": [], "group_by": []}
    return {"id": sid, "kind": "analysis", "stat": stat, "spec": s, "options": dict(options),
            "read_as": f"SYNTHETIC {stat}", "run_id": "R31-NO-RUN",
            "days": ["2024-01-01", "2026-09-17"]}


def test_p8_no_other_statistic_is_given_the_steps(tmp_path, monkeypatch):
    """Point 8, "for no other statistic": a thread remembering a trend, a rate by age band and a
    distribution by gender; a count is checked against them: only the distribution's figures are
    asked for with steps=True."""
    env = CountyEnv(tmp_path, monkeypatch)
    remember(env, stored_stat("trend", {}), stored_stat("rate", RATE_BY_BAND, "a2"),
             stored_stat("distribution", {"by": "gender"}, "a3"))
    calls = spy_steps(monkeypatch)
    reply, answers = ask_counts(env, [spec(Y25, [age(30, 40)])])
    assert_answered(reply, answers)
    calls = [c for c in calls if c[0] == "shown_figures"]
    dists = [st for _, options, st in calls if options == {"by": "gender"}]
    others = [st for _, options, st in calls if options != {"by": "gender"}]
    assert dists and others, f"premise: each statistic was read: {calls}"
    assert all(st is True for st in dists), calls
    assert not any(others), calls


@pytest.mark.parametrize("kind, raw, steps", [
    ("distribution", {}, True), ("distribution", {"by": "gender"}, True), ("trend", None, False),
    ("timing", None, False)], ids=["distribution", "distribution by gender", "trend", "timing"])
def test_p8_this_messages_statistic_is_given_the_steps_only_if_a_distribution(
        tmp_path, monkeypatch, kind, raw, steps):
    """Point 8, "for a distribution of this message ... and for no other statistic": the check of a
    new statistic (ages 30 to 40) asks for its figures with steps=True for a distribution only."""
    env = CountyEnv(tmp_path, monkeypatch)
    stub_prepare(monkeypatch)
    calls = spy_steps(monkeypatch)
    env.ask("a question", Step(analyze(kind, SINCE_2024, [age(30, 40)], raw)),
            Step(finish("finding", "I found that.")))
    assert env.model.answer(0).get("error") == "TOO_LITTLE", env.model.answer(0)
    mine = [st for name, _, st in calls if name == "shown_figures"]
    assert mine, f"premise: the statistic was checked: {calls}"
    assert all(bool(st) is steps for st in mine), calls


# ==== step 4: point 9 ===============================================================================

def set_bound(monkeypatch, value):
    """R31-5: counting.WORK_EXACT, set on the module (raising: the bound must exist)."""
    monkeypatch.setattr(mod("counting"), "WORK_EXACT", value)


# ---- (a) soundness: seeded sets of this file's own on arrests_like ---------------------------------

AGES_9 = [None, U18, A10_16, age(10, 13), age(14, 17), age(16, 17), age(17), age(18), U17,
          age(15, 17), age(12, 17), age(17, 30), age(18, 24)]
DIST_AGES_9 = [U18, age(12, 17), age(16, 17), age(10, 15), age(14, 17), A10_16, age(15, 17)]
PERIODS_9 = [Y25, Y25, Y24, H1, H2, QUARTERS[0], QUARTERS[3], months(2025, 1, 1),
             years(2024, 2025)]
FIELDS_9 = [None, None, None, F, M, in_("gender", "female", "male"), D3, D5, GAMMA, ALPHA_BETA,
            in_("race", "group Alpha", "group Beta", "group Gamma"), NEAR, hours(0, 11),
            hours(12, 23), weekdays("Monday", "Tuesday", "Wednesday")]
BY_9 = [[], [], [], ["year"], ["month"], ["gender"], ["race"], ["district"], ["age_band"],
        [SCHOOL], ["gender", "race"], ["hour"], ["weekday"], ["ethnicity"]]
HEAVY_BY = (["hour"], ["weekday"], ["gender", "race"], ["month"])
STATS_9 = [("trend", {}), ("distribution", {}), ("distribution", {"by": "gender"}),
           ("shares", {"part": [D3]}), ("rate", None), ("timing", {})]


def a_stat(rng):
    """A statistic: its age filter of a few years (a distribution's steps stay few), a period."""
    kind, raw = rng.choice(STATS_9)
    if kind == "rate":
        return Stat("rate", rng.choice([Y25, Y24]), options=rng.choice([RATE_BY_BAND, RATE]))
    ages = rng.choice(DIST_AGES_9 if kind == "distribution" else AGES_9[:6] + [age(18)])
    return Stat(kind, rng.choice([Y25, Y24, H1, years(2024, 2025)]), [ages] if ages else [],
                raw=dict(raw))


def a_count(rng):
    ages = rng.choice(AGES_9)
    filters = [ages] if ages else []
    extra = rng.choice(FIELDS_9)
    if extra:
        filters.append(extra)
    return Cnt(rng.choice(PERIODS_9), filters, rng.choice(BY_9))


def a_family(rng):
    """Related counts: one period and one set of filters, cut by ages, halves, quarters, genders,
    labels or a breakdown (the ways C65's threads go round the rule), now and then a statistic."""
    period = rng.choice([Y25, Y25, Y24, years(2024, 2025)])
    base = [f for f in [rng.choice(FIELDS_9[:3] + [D3, NEAR, GAMMA])] if f]
    out = []
    for _ in range(rng.randint(1, 5)):
        move = rng.choice(["ages", "ages", "half", "quarter", "gender", "label", "by", "stat"])
        p, extra, by = period, [], []
        if move == "half":
            p = rng.choice([H1, H2])
        elif move == "quarter":
            p = rng.choice(QUARTERS)
        elif move == "gender":
            extra = [rng.choice([F, M, in_("gender", "female", "male")])]
        elif move == "label":
            extra = [rng.choice([GAMMA, ALPHA_BETA, in_("race", "group Alpha", "group Beta",
                                                        "group Gamma")])]
        elif move == "by":
            by = rng.choice(BY_9[3:])
        elif move == "stat":
            out.append(a_stat(rng))
            continue
        ages = rng.choice(AGES_9)
        filters, seen = [], set()
        for f in [ages, *base, *extra]:
            if f and f["field"] not in seen:
                seen.add(f["field"])
                filters.append(f)
        out.append(Cnt(p, filters, by))
    return out


A_SEEDS = range(1200)


def a_set(seed):
    """Two sets in three are families. A set with a statistic has no breakdown by hour, weekday,
    month or a pair beside it (a statistic stands for each part of its records, and those make
    tables that only the bound keeps small: the test compares with the bound out of reach)."""
    rng = random.Random(31_000 + seed)
    items = a_family(rng) if seed % 3 else \
        [a_stat(rng) if rng.random() < 0.2 else a_count(rng) for _ in range(rng.randint(1, 5))]
    if any(isinstance(it, Stat) for it in items):
        items = [Cnt(it.period, it.filters, []) if isinstance(it, Cnt) and
                 list(it.group_by) in HEAVY_BY else it for it in items]
    return [it for it in items if valid(it)]


def valid(it, src=None):
    """C5's checks (and check_options for a statistic) let the item through on its own."""
    counting, src = mod("counting"), src or source_json(A)
    try:
        s = counting.check_spec(src, fcopy(NEWEST_A), {"source": A_ID, "period": it.period,
                                                       "filters": list(it.filters),
                                                       "group_by": list(it.group_by)})
        if isinstance(it, Stat) and it.raw is not None:
            mod("stats").check_options(src, s, it.kind, it.raw)
    except counting.SpecError:
        return False  # refused on its own (a single year asked outright, ...)
    return True


def test_step4a_soundness_on_this_files_own_sets(monkeypatch):
    """Point 9 (a): on 1,200 seeded sets of one to five counts and statistics (two in three of them
    families) on arrests_like, with WORK_EXACT at 0 and at 20,000 the function never says no where
    it says yes with the bound out of reach. Premises: a mix of answers, and at 0 some first step
    is refused early (so slicing happens)."""
    counting = mod("counting")
    assert hasattr(counting, "WORK_EXACT"), "point 9: counting.WORK_EXACT"
    wrong, counts = [], {"sets": 0, "yes": 0, "early at 0": 0, "early at 20,000": 0}
    for seed in A_SEEDS:
        items = a_set(seed)
        if not items:
            continue
        answers = {}
        for bound in (OUT_OF_REACH, 0, 20_000):
            set_bound(monkeypatch, bound)
            answers[bound] = decide_8(items)
        counts["sets"] += 1
        counts["yes"] += answers[OUT_OF_REACH]
        counts["early at 0"] += answers[0] and not answers[OUT_OF_REACH]
        counts["early at 20,000"] += answers[20_000] and not answers[OUT_OF_REACH]
        for bound in (0, 20_000):
            if answers[OUT_OF_REACH] and not answers[bound]:
                wrong.append((seed, bound))
    assert counts["sets"] >= 1000, f"premise: {counts}"
    assert 100 <= counts["yes"] <= counts["sets"] - 100, f"premise: a mix of answers: {counts}"
    assert counts["early at 0"] > 0, f"premise: slicing at 0 refuses some first step: {counts}"
    assert not wrong, f"{len(wrong)} sets: no where the bound out of reach says yes: {wrong[:10]}"


# ---- (a) soundness on round 30's oracle --------------------------------------------------------------

_ORACLE = {}


def oracle_of(seed):
    if seed not in _ORACLE:
        specs = o_set(seed)
        _ORACLE[seed] = (specs, oracle(specs) if specs else None)
    return _ORACLE[seed]


@pytest.mark.parametrize("bound", [0, 20_000], ids=["WORK_EXACT 0", "WORK_EXACT 20,000"])
def test_step4a_soundness_on_round_30s_oracle(monkeypatch, bound):
    """Point 9 (a): on round 30's 2,000 seeded sets, with the bound at 0 and at 20,000, the function
    never says no where the oracle's reading (ii) or (iii) says yes (R30-1)."""
    set_bound(monkeypatch, bound)
    wrong, sets = [], 0
    for seed in SEEDS:
        specs, answers = oracle_of(seed)
        if not specs:
            continue
        sets += 1
        _, usable, few_gaps = answers
        if (usable or few_gaps) and not o_program(specs):
            wrong.append(seed)
    assert sets >= 1900, f"premise: {sets}"
    assert not wrong, f"{len(wrong)} sets: no where (ii) or (iii) says yes; seeds {wrong[:10]}"


# ---- (b) the examples of points 1 to 8 with the bound as it is ---------------------------------------

EXAMPLES = {}
EXAMPLES.update({f"r29 {n}": ("29", c) for n, c in FUNCTION_CASES.items()
                 if c[1] != QUESTION_CASE})
EXAMPLES.update({f"r29 copy: {n}": ("29 copy", c) for n, c in COPY_CASES.items()})
EXAMPLES.update({f"r30 point 6: {n}": ("29", c) for n, c in POINT_6_CASES.items()})
EXAMPLES.update({f"r30 own: {n}": ("29", c) for n, c in OWN_CASES.items()})
EXAMPLES.update({f"r30 rate: {n}": ("30 rate", c) for n, c in RATE_CASES.items()})
EXAMPLES.update({f"r31 {n}": ("31", c) for n, c in {**CASES_8, **OWN_8}.items()})


def run_example(how, case):
    if how == "29":
        return run_case(case)
    if how == "29 copy":
        from test_s3_c62 import NEWEST_B
        items, expected = case
        return decide(items, newest=NEWEST_B), expected
    if how == "30 rate":
        items, expected = case
        return decide_7(items), expected
    return run_8(case)


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_step4b_the_examples_with_the_bound_as_it_is(monkeypatch, name):
    """Point 9 (b): each example of points 1 to 8 (R31-7) gives its answer with WORK_EXACT as it is,
    and the same answer with the bound out of reach."""
    how, case = EXAMPLES[name]
    assert mod("counting").WORK_EXACT == 10_000_000, "point 9: the bound is 10,000,000"
    got, expected = run_example(how, case)
    set_bound(monkeypatch, OUT_OF_REACH)
    unbounded, _ = run_example(how, case)
    assert got is expected, name
    assert unbounded is got, name


# ---- (c) size ---------------------------------------------------------------------------------------

BREAKDOWNS_22 = [["gender"], ["race"], ["ethnicity"], ["district"], [SCHOOL], ["gender", "race"],
                 ["district", "ethnicity"], ["month"], ["weekday"], ["hour"], ["age_band"]]
THREAD_22 = ([Cnt(Y25, [U18], by) for by in BREAKDOWNS_22] +
             [Cnt(Y25, [age(18)], by) for by in BREAKDOWNS_22[:9]] +
             [Cnt(H1, [age(17, 30), D3, hours(0, 11)], ["race"]),
              Cnt(Y25, [age(16), D5], ["month"])])
TREND = Stat("trend", SINCE_2024, raw={})
AFTER = {"alone": [], "after a trend": [TREND],
         "after a trend, a rate by age band and two distributions": [
             TREND, Stat("rate", Y25, options=RATE_BY_BAND), EVERY,
             Stat("distribution", Y25, [U18], options={"by": "gender"})]}


class TooBig(Exception):
    pass


class Bounded:
    """Stops what runs inside it (SIGALRM, every 50 ms) once tracemalloc's peak passes `mb` or the
    time passes `seconds` (R31-6)."""

    def __init__(self, seconds, mb=None):
        self.seconds, self.mb, self.peak, self.took = seconds, mb, 0, None

    def _check(self, *_):
        if self.mb is not None and tracemalloc.get_traced_memory()[1] > self.mb * 2 ** 20:
            raise TooBig(f"over {self.mb} MB")
        if time.perf_counter() - self.started > self.seconds:
            raise TooBig(f"over {self.seconds} s")

    def __enter__(self):
        if self.mb is not None:
            tracemalloc.start()
        self.old = signal.signal(signal.SIGALRM, self._check)
        self.started = time.perf_counter()
        signal.setitimer(signal.ITIMER_REAL, 0.05, 0.05)
        return self

    def __exit__(self, *exc):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.old)
        self.took = time.perf_counter() - self.started
        if self.mb is not None:
            self.peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
        return False


def test_step4c_premise_the_thread_has_22_counts_of_2025_and_a_single_year_to_look_for():
    """The thread of (c): 22 counts of 2025 (the last two of January to June and of 2025), every
    breakdown arrests_like allows (each field alone, two pairs, month, weekday, hour, age band), and
    ages whose edges leave single years under 18 (16, 17) to look for, so no build can answer by the
    ages alone. Passes today."""
    assert len(THREAD_22) >= 20
    bys = {tuple(c.group_by) for c in THREAD_22}
    for by in BREAKDOWNS_22:
        assert tuple(by) in bys, by
    edges = {e for c in THREAD_22 for f in c.filters if f["field"] == "age"
             for e in (f.get("from", 10), f.get("to", 98) + 1)}
    assert {16, 17, 18} <= edges, edges


@pytest.mark.parametrize("after", list(AFTER))
def test_step4c_a_thread_of_22_counts_is_decided_in_under_two_seconds_and_300_mb(after):
    """Point 9 (c): the 22 counts of 2025 with every breakdown, alone, after a trend, and after a
    trend, a rate by age band and two distributions: decided in under two seconds (the best of two
    tries, without tracemalloc) and under 300 MB at its peak (tracemalloc)."""
    items = AFTER[after] + THREAD_22
    with Bounded(60, mb=300) as b:
        try:
            decide_8(items)
        except TooBig as e:
            pytest.fail(f"{after}: {e} ({b.took or 0:.1f} s)")
    assert b.peak < 300 * 2 ** 20, f"{after}: peak {b.peak / 2 ** 20:.0f} MB"
    best = None
    for _ in range(2):
        with Bounded(30) as t:
            try:
                decide_8(items)
            except TooBig as e:
                pytest.fail(f"{after}: {e}")
        best = t.took if best is None else min(best, t.took)
    assert best < 2.0, f"{after}: {best:.2f} s (peak {b.peak / 2 ** 20:.0f} MB)"


# ---- (d) a first step refused early, as point 9 allows -----------------------------------------------

def test_step4d_a_sliced_first_step_is_refused_early_as_point_9_allows(monkeypatch):
    """Point 9 (d), R31-8: with WORK_EXACT = 0, under 18 in 2025 and then ages 10 to 16 from January
    to June (a count that is only one step of a sum) is refused: the halves are sliced and in the
    first half's slice "under 18" is known for that half alone. Point 9 allows it ("that count is
    then refused one step early"). With the bound out of reach it is answered, as C65 point 1 has
    it."""
    items = [U18_25, Cnt(H1, [A10_16])]
    set_bound(monkeypatch, 0)
    assert decide(items) is True
    set_bound(monkeypatch, OUT_OF_REACH)
    assert decide(items) is False


@pytest.mark.parametrize("bound, refused", [(0, True), (OUT_OF_REACH, False)],
                         ids=["WORK_EXACT 0: refused one step early", "out of reach: answered"])
def test_step4d_the_same_through_county_turns(tmp_path, monkeypatch, bound, refused):
    """Point 9 (d) through two county turns: under 18 in 2025 (answered), then ages 10 to 16 from
    January to June: with WORK_EXACT = 0 refused with C62 point 2's sentence, nothing saved for it;
    with the bound out of reach answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    set_bound(monkeypatch, bound)
    reply, answers = ask_counts(env, [spec(Y25, [U18])], "how many under 18 in 2025?")
    assert_answered(reply, answers)
    reply, (answer,) = ask_counts(env, [spec(H1, [A10_16])], "and 10 to 16 in January to June?")
    if refused:
        assert_refused(answer)
        assert_refused_end(env, reply, before=1)
    else:
        assert_answered(reply, [answer])


def test_step4d_slices_of_another_dimension_the_genders(monkeypatch):
    """Point 9 (d), own: with WORK_EXACT = 0, under 18 in 2025 and then males aged 10 to 16: the
    gender's values are sliced and in the males' slice "under 18" is known for them alone: refused
    one step early, as point 9 allows. With the bound out of reach: answered."""
    items = [U18_25, Cnt(Y25, [A10_16, M])]
    set_bound(monkeypatch, 0)
    assert decide(items) is True
    set_bound(monkeypatch, OUT_OF_REACH)
    assert decide(items) is False


def test_step4_point_9_exact_at_every_size_adults_across_18(monkeypatch):
    """Point 9, "exact at every size": figures of adults only are left out only where no figure
    reaches across the eighteenth birthday. All ages, 18 and over, and 11 to 17 of 2025 give the
    10-year-olds (the adults' figure is needed): refused at 0, at 20,000 and as it is."""
    items = [Cnt(Y25), Cnt(Y25, [age(18)]), Cnt(Y25, [age(11, 17)])]
    for bound in (0, 20_000, 10_000_000):
        set_bound(monkeypatch, bound)
        assert decide(items) is True, bound


def test_step4_point_9_figures_of_other_slices_are_cut_away(monkeypatch):
    """Point 9, "every figure taken as known for the slice alone": with WORK_EXACT = 0, under 18 in
    2025 and 10 to 16 in each half (C65's P21) are refused, as with the bound out of reach: each
    figure is cut to the slice (a build that kept the whole year's figure in each slice would miss
    it)."""
    items = [U18_25, Cnt(H1, [A10_16]), Cnt(H2, [A10_16])]
    for bound in (0, 20_000, OUT_OF_REACH):
        set_bound(monkeypatch, bound)
        assert decide(items) is True, bound


def test_step4_point_9_a_single_figure_is_not_cut(monkeypatch):
    """Point 9 with WORK_EXACT = 0: a count of under 18 in 2025 alone, and one of 18 to 24 alone,
    are answered (a slice of one figure gives no single year): never more than the figures give."""
    for items in ([U18_25], [Cnt(Y25, [age(18, 24)], ["district"])], [Cnt(Y25, [U18], ["hour"])]):
        set_bound(monkeypatch, 0)
        assert decide(items) is False, items


def test_step4_the_bound_is_10_million():
    """Point 9: counting.WORK_EXACT is 10,000,000."""
    assert getattr(mod("counting"), "WORK_EXACT", None) == 10_000_000

