"""C65's two more points (docs/S3A-DESIGN.md, 18 Nov 09:29 EST; D-082): point 6, the check's figures are
what a count really shows (check 14's DEFECT 2), and point 7, a rate's age bands are the Census's
(check 14's DEFECT 1). Brief: briefs/S3-R30-A-tests.md. Tests only; red until the planning chat
builds points 6 and 7, except those that pin what stays (named in their docstrings and in
kit-log/raw/S3-R30-A-notes.txt). The rates that R runs for are in tests/s3s/test_s3s_c65b.py.

Everything here is SYNTHETIC: the fixtures of tests/s3/fixtures (arrests_like, coded_like and
test_s3_c54.py's juvenile-like copy of arrests_like), and a small made-up source of this file's own
for the oracle (step 4). No figure of a real county source is used or quoted.

What is here, in the brief's order:
3. counting.one_year_under_18 and counting.age_figures on the fixture sources: every example of point
   6's Tests, check 14's DEFECT 2 through two county turns, and this session's own cases (OWN_CASES,
   each saying what point 6 a to d decide).
4. An oracle of this session's own, written from counting.tally's behaviour and point 6's words, not
   from age_figures: a made-up source, one record for every combination, `tally` run on each record
   alone to learn which records each shown number counts, and exact arithmetic (whole numbers,
   fraction-free elimination). Compared with the program's function on 2,000 seeded sets.
5. Point 7: counting.shown_bands and shown_figures with and without `age_bands`; the function on a
   rate by age band with counts; county turns with a rate remembered from an earlier turn and one
   kept through `reset` (stored as the program stores it, so no R runs); no other statistic is
   passed the Census bands.

Readings (also in the notes; the open ones in briefs/QUESTIONS.md):
- R30-1. Point 6's three answers, as the oracle works them out: (i) with every record; (ii) with the
  records of no usable age left out; (iii) as (ii) and with the records that have no value in more
  than one of the fields the counts name left out too. The function must answer "(ii) or (iii)",
  and so never "no" where (i) is "yes". "One single year of age under 18" is a sum of the shown
  numbers, each taken any number of times with either sign, that is not zero and counts only
  records of one usable age under 18 (C65 answer 3, the wide reading).
- R30-2. "Every left-out line" is every entry of tally's `left_out`, the age field's included (C52
  point 2 gives the age field no figure; under (ii) and (iii) its line counts nothing, so it changes
  no answer there).
- R30-3. age_figures keeps today's shape: a list of (((source, runs), ((field, constraint), ...)),
  (first age, last age)). A constraint is read with counting._kept_values (the function's own
  reader), so how the build writes "one of these values, or none recorded" is its own.
- R30-4. C65's Tests, point 6: "with the first turn a year earlier both are answered". Read
  literally (18 and over by gender and race in 2024, then 17 and over, female, every label of
  race, 2024 and 2025, by year) the 2024 figure of the second less the female groups of the first
  is the 17-year-olds of 2024 (female, with a race): point 6 a to c and C21's rule refuse it. The
  tests pin it refused, and pin "both answered" for the pair a year earlier as a whole (2024, then
  2025 and 2026), which shares no day (briefs/QUESTIONS.md, S3-R30-A question 1).
- R30-5. `age_bands` is passed as a list of (first, last) pairs, last None for "and over"
  (s3support.C65_CENSUS_BANDS, written by hand from C65 point 7). A rate's figures: its own band
  (every usable age; a rate takes no filter) and each Census band cut to the source's usable ages.
- R30-6. A rate is a statistic of `"stat": "rate"` in a remembered turn and in a stripped record
  of `reset`; the remembered rate's options are as the program keeps them ({"by", "reference"}).
"""
import inspect
import json
import random
import sqlite3
import time
from datetime import date
from itertools import product
from types import SimpleNamespace

import pytest

from p1support import THREAD_1, mod, thread_block
from s3support import A_ID, C65_CENSUS_BANDS, CountyEnv, age, hours, in_, source_json, years
from test_s3_c54 import J, SIDS, juvenile_source, two_sources
from test_s3_c61d import assert_answered, assert_refused
from test_s3_c65 import (A10_16, ALPHA_BETA, D3, D4, D5, F, GAMMA, H1, H2, NEAR, NEW_SENTENCE,
                         NEWEST_A, NOT_NEAR, RATE, RATE_BY_BAND, RATE_BY_GENDER, TALK, U18_25, Y24,
                         Cnt, Stat, Talk, ask_counts, assert_refused_end, decide, fcopy, given,
                         holds, plain, slack_env)
from test_s3_round5 import A, U17, U18, Y25, spec

RACES = ("group Alpha", "group Beta", "group Gamma")
EVERY_RACE = in_("race", *RACES)
EVERY_GENDER = in_("gender", "female", "male")
CENSUS = list(C65_CENSUS_BANDS)


# ==== step 3: point 6, the function ===============================================================

def defect_2(first_period=Y25, second_period=years(2024, 2025), first_ages=age(18),
             second_ages=age(17), race=EVERY_RACE):
    """Check 14's DEFECT 2: 18 and over by gender and race; then 17 and over, female, the race
    filter `race`, by year (two years)."""
    return [Cnt(first_period, [first_ages], ["gender", "race"]),
            Cnt(second_period, [second_ages, F, race], ["year"])]


# name: (items, expected). True: one single year of age under 18 follows (the last is refused).
POINT_6_CASES = {
    # ---- C65's Tests, point 6 ----
    "check 14's DEFECT 2: the second is refused": (defect_2(), True),
    "check 14's DEFECT 2: the first alone is answered": (defect_2()[:1], False),
    "check 14's DEFECT 2 a year earlier as a whole (2024, then 2025 and 2026): both answered "
    "(R30-4)": (defect_2(Y24, years(2025, 2026)), False),
    "check 14's DEFECT 2 with only the first turn a year earlier (2024): refused by a to c "
    "(R30-4)": (defect_2(Y24), True),
    "C52 point 1's pair as round 16: under 18, then under 17 with every label of race": (
        [U18_25, Cnt(Y25, [U17, EVERY_RACE])], True),
    "C52 point 1's pair as round 16: the labels in another order and case": (
        [U18_25, Cnt(Y25, [U17, in_("race", "GROUP GAMMA", "group alpha", "Group Beta")])], True),
    "C52 point 4's pair as round 16: two labels of race by race, then the third": (
        [Cnt(Y25, [U18, ALPHA_BETA], ["race"]), Cnt(Y25, [U17, GAMMA])], True),
    "C52 point 1 for hours, as before: under 17 at every hour after under 18": (
        [U18_25, Cnt(Y25, [U17, hours(0, 23)])], True),
    "round 29's case that turns round (6d): three fields, the last in another district": (
        [Cnt(Y25, [U18, F, D3]), Cnt(Y25, [A10_16, F, D3, ALPHA_BETA]),
         Cnt(Y25, [A10_16, F, D4, GAMMA])], True),
}

# This session's own (step 3), each with what point 6 a to d decide.
OWN_CASES = {
    # a: an every-label filter is the filter it is (the records with a label), with a breakdown
    "a: every label of race with a breakdown by year, against district and race groups": (
        [Cnt(Y25, [age(18)], ["race", "district"]),
         Cnt(years(2024, 2025), [age(17), D3, EVERY_RACE], ["year"])], True),
    "a: every label of gender with a breakdown by year, against gender and race groups": (
        [Cnt(Y25, [age(18)], ["gender", "race"]),
         Cnt(years(2024, 2025), [age(17), EVERY_GENDER, GAMMA], ["year"])], True),
    "a: one label in place of every label (as C21, a group of the same kind)": (
        defect_2(race=GAMMA), True),
    "a: every label but one (two groups of the first make it)": (defect_2(race=ALPHA_BETA), True),
    "a: every label by year, the first count of 18 and over of 2024 and 2025 by year too": (
        [Cnt(years(2024, 2025), [age(18)], ["year", "race"]),
         Cnt(years(2024, 2025), [age(17), EVERY_RACE], ["year"])], True),
    # a with the no-value figure: those labels and the count's no-value figure make every record
    "a: with the no-value figure that completes the sum (one year, no breakdown by year)": (
        [Cnt(Y25, [age(18)], ["gender", "race"]), Cnt(Y25, [age(17), F, EVERY_RACE])], True),
    "a: without it: an every-label count of two years by year, and a count of every record": (
        [Cnt(years(2024, 2025), [age(17), EVERY_RACE], ["year"]), Cnt(Y25, [age(18)])], False),
    # b: no total for a breakdown by a category it does not filter (the total is its groups)
    "b: the total of a breakdown by race against a count of every record": (
        [Cnt(Y25, [U18], ["race"]), Cnt(Y25, [U17])], True),
    "b: the groups of race and of gender, of two counts, make the same records": (
        [Cnt(Y25, [U18], ["race"]), Cnt(Y25, [U17], ["gender"])], True),
    "b: a breakdown by race of 2024 against a count of 2025 (other days)": (
        [Cnt(Y24, [U18], ["race"]), Cnt(Y25, [U17])], False),
    # c: a left-out figure: no value for its field, the other filters "these values or none"
    "c: left-out figures whose other filter is a category (both group Gamma)": (
        [Cnt(Y25, [U18, D3, GAMMA]), Cnt(Y25, [U17, D5, GAMMA])], True),
    "c: left-out figures whose other filter is a category (Gamma, then Alpha or Beta)": (
        [Cnt(Y25, [U18, D3, GAMMA]), Cnt(Y25, [U17, D5, ALPHA_BETA])], False),
    "c: left-out figures whose other filter is an hour range (the same hours)": (
        [Cnt(Y25, [U18, D3, hours(0, 11)]), Cnt(Y25, [U17, D5, hours(0, 11)])], True),
    "c: left-out figures whose other filter is an hour range (other hours)": (
        [Cnt(Y25, [U18, D3, hours(0, 11)]), Cnt(Y25, [U17, D5, hours(12, 23)])], False),
    "c: the hours of a day make the day, in the left-out figures": (
        [Cnt(Y25, [U18, D3]), Cnt(Y25, [U17, D5, hours(0, 11)]),
         Cnt(Y25, [U17, D5, hours(12, 23)])], True),
    "c: left-out figures whose other filter is the flag (both ways: does not fit)": (
        [Cnt(Y25, [U18, D3, NEAR]), Cnt(Y25, [U17, D5, NOT_NEAR])], False),
    "c: a left-out figure of two years against one of one year": (
        [Cnt(years(2024, 2025), [U18, D3], ["year"]), Cnt(Y25, [U17, D5])], False),
    # d: a count with no age filter is the count of the usable ages
    "d: all ages, then 11 and over in two halves (the 10-year-olds)": (
        [Cnt(Y25), Cnt(H1, [age(11)]), Cnt(H2, [age(11)])], True),
    # d: records with no value in more than one named field are taken not to exist
    "d: two fields: a breakdown by gender and race, then a count of every record": (
        [Cnt(Y25, [U18], ["gender", "race"]), Cnt(Y25, [U17])], True),
    "d: three fields: district 3 by gender and race, then district 3 alone": (
        [Cnt(Y25, [U18, D3], ["gender", "race"]), Cnt(Y25, [U17, D3])], True),
    "d: three fields of another year (does not fit)": (
        [Cnt(Y25, [U18, D3], ["gender", "race"]), Cnt(Y24, [U17, D3])], False),
    "d: two fields, the second count of 18 and over (the year is 18)": (
        [Cnt(Y25, [age(None, 18)], ["gender", "race"]), Cnt(Y25, [age(None, 17)])], False),
}


@pytest.mark.parametrize("name", list(POINT_6_CASES))
def test_step3_point_6_examples(name):
    """Step 3: each example of C65 point 6's Tests (True: one single year of age under 18 follows,
    and the request that completes it is refused)."""
    items, expected = POINT_6_CASES[name]
    assert decide(items) is expected, name


@pytest.mark.parametrize("name", list(OWN_CASES))
def test_step3_own_cases_that_point_6_decides(name):
    """Step 3: this session's own cases, each decided by point 6 a to d (the case's name says
    which)."""
    items, expected = OWN_CASES[name]
    assert decide(items) is expected, name


def checked(src, period, filters=(), group_by=(), newest=NEWEST_A):
    return mod("counting").check_spec(src, fcopy(newest, src["id"]),
                                      {"source": src["id"], "period": period,
                                       "filters": list(filters), "group_by": list(group_by)})


def kinds(src, s):
    """age_figures' figures as (runs, {field: constraint}, band) (R30-3)."""
    out = []
    for ((_, runs), kept), band in mod("counting").age_figures(src, s):
        out.append((runs, dict(kept), tuple(band)))
    return out


def values(name, constraint):
    return mod("counting")._kept_values(name, constraint)


def labels_read(*labels, none=False):
    out = {json.dumps(label, sort_keys=True) for label in labels}
    return frozenset(out | ({mod("counting").NO_VALUE} if none else set()))


def test_step3_6a_an_every_label_filter_keeps_the_records_with_a_label():
    """Point 6a: age_figures gives a category filter that names every label as the filter it is:
    the total keeps the three labels, not the records with no value; the no-value figure is the
    count's left-out figure."""
    src = source_json(A)
    figs = kinds(src, checked(src, Y25, [U17, EVERY_RACE]))
    totals = [k for _, k, band in figs if k.get("race") != mod("counting").NO_VALUE]
    assert totals and all("race" in k for k in totals), figs
    for k in totals:
        assert values("race", k["race"]) == labels_read(*RACES), k
    assert any(k.get("race") == mod("counting").NO_VALUE for _, k, _ in figs), figs


def test_step3_6b_no_total_for_a_breakdown_by_a_category_it_does_not_filter():
    """Point 6b: a count broken down by race (no race filter) has no figure for its total: every
    figure names race (a label or no value). A count by year keeps its total (pins what stays)."""
    src = source_json(A)
    figs = kinds(src, checked(src, Y25, [U18], ["race"]))
    assert figs and all("race" in k for _, k, _ in figs), figs
    by_year = kinds(src, checked(src, years(2024, 2025), [U18], ["year"]))
    assert any(k == {} and len(runs) == 1 for runs, k, _ in by_year), by_year


def test_step3_6b_a_breakdown_by_the_flag_it_does_not_filter():
    src = source_json(A)
    figs = kinds(src, checked(src, Y25, [U18], ["adjacent_to_school"]))
    assert figs and all("adjacent_to_school" in k for _, k, _ in figs), figs


def test_step3_6c_the_left_out_figure_reads_other_filters_as_these_values_or_none():
    """Point 6c: the left-out figure of district of "under 18, district 3, Alpha or Beta, near a
    school, hours 0 to 11": no value for district; race Alpha or Beta or none; the flag yes or
    none; the hours as they are; the count's ages."""
    src = source_json(A)
    figs = kinds(src, checked(src, Y25, [U18, D3, ALPHA_BETA, NEAR, hours(0, 11)]))
    (left,) = [(k, band) for _, k, band in figs if k.get("district") == mod("counting").NO_VALUE]
    k, band = left
    assert values("race", k["race"]) == labels_read(*RACES[:2], none=True), k
    assert values("adjacent_to_school", k["adjacent_to_school"]) == \
        frozenset([True, mod("counting").NO_VALUE]), k
    assert values("hour", k["hour"]) == frozenset(range(12)), k
    assert band == (10, 17), band


def test_step3_6c_the_total_reads_its_filters_exactly():
    """Point 6c's other side: the total of the same count keeps district 3, Alpha or Beta and near
    a school, with no "none" (pins what stays)."""
    src = source_json(A)
    figs = kinds(src, checked(src, Y25, [U18, D3, ALPHA_BETA, NEAR]))
    (total,) = [k for _, k, _ in figs if mod("counting").NO_VALUE not in k.values()]
    assert values("race", total["race"]) == labels_read(*RACES[:2]), total
    assert values("adjacent_to_school", total["adjacent_to_school"]) == frozenset([True]), total


# ---- check 14's DEFECT 2 through two county turns ----------------------------------------------

DEFECT_2_FIRST = "how many arrests in 2025 of people 18 and over, by gender and race?"
DEFECT_2_SECOND = ("how many arrests of people 17 and over, recorded as female, race group Alpha, "
                   "Beta or Gamma, in 2024 and 2025, by year?")


def defect_2_specs(first=Y25, second=years(2024, 2025)):
    return (spec(first, [age(18)], ["gender", "race"]),
            spec(second, [age(17), F, EVERY_RACE], ["year"]))


@pytest.mark.parametrize("talk", TALK)
def test_step3_defect_2_through_two_county_turns(tmp_path, monkeypatch, talk):
    """Check 14's DEFECT 2 as the check ran it, on arrests_like: the first message answered, the
    second refused (NOT_ALLOWED, C21's `why` with C61's sentence, C62 point 2's sentence, nothing
    counted or saved for it)."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    first, second = defect_2_specs()
    reply, answers = ask_counts(env, [first], DEFECT_2_FIRST)
    assert_answered(reply, answers)
    reply, (answer,) = ask_counts(env, [second], DEFECT_2_SECOND)
    assert_refused(answer)
    assert_refused_end(env, reply, before=1)


def test_step3_defect_2_a_year_earlier_as_a_whole_both_answered(tmp_path, monkeypatch):
    """R30-4: the pair a year earlier as a whole (2024; then 2025 and 2026 by year): no day shared,
    both answered. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    for s, question in zip(defect_2_specs(Y24, years(2025, 2026)),
                           (DEFECT_2_FIRST, DEFECT_2_SECOND)):
        reply, answers = ask_counts(env, [s], question)
        assert_answered(reply, answers)


# ==== step 4: an oracle of this session's own =====================================================
# A made-up SYNTHETIC source: usable ages 15 to 19 (bands 15-16, 17-18, 19), two categories of two
# labels (colour, shape), one flag (lit), one day in 2024 and one in 2025. One record for every
# combination: each age 15 to 19, an age outside the usable ages ("12"), no age; each label and no
# value for each category and the flag; each day. Which records each shown number counts is learnt
# by running counting.tally on each record alone; the decision is the oracle's own arithmetic.

O_ID = "FIXTURE:r30_world"
O_DAYS = (date(2024, 6, 14), date(2025, 6, 13))
O_NEWEST = date(2025, 12, 31)
O_AGES = ("15", "16", "17", "18", "19", "12", None)
O_COPY = SimpleNamespace(newest_day=O_NEWEST, sha256="0" * 64)


def o_source():
    return {"id": O_ID, "data_class": "COUNTY_OPEN_DATA",
            "title": "SYNTHETIC oracle world of round 30 (made up for tests)",
            "unit": {"one": "record", "many": "records"}, "is_not": ["people"],
            "time_field": "event_date_time", "coverage_start": "2024-01-01", "floor": 10,
            "fields": [{"name": "id", "kind": "key"},
                       {"name": "age", "kind": "age", "usable": [15, 19],
                        "bands": [[15, 16], [17, 18], [19, 19]]},
                       {"name": "colour", "kind": "category", "dimension": "colour",
                        "wording": "in {labels}", "values": {"R": "red", "G": "green"}},
                       {"name": "shape", "kind": "category", "dimension": "shape",
                        "wording": "in {labels}", "values": {"S": "square", "C": "circle"}},
                       {"name": "lit", "kind": "flag", "dimension": "light", "yes_raw": "1",
                        "no_raw": "0", "yes": "lit", "no": "not lit"}]}


O_SRC = o_source()
O_FIELDS = ("colour", "shape", "lit")
O_RECORDS = [{"id": f"FIXTURE-R30-{i:04d}", "age": a, "colour": c, "shape": s, "lit": lit,
              "event_date_time": f"{d.isoformat()}T10:00:00.000"}
             for i, (a, c, s, lit, d) in enumerate(product(O_AGES, ("R", "G", None),
                                                           ("S", "C", None), ("1", "0", None),
                                                           O_DAYS))]


def o_year(record):
    """The record's usable age (15 to 19), or None (no usable age)."""
    a = record["age"]
    return int(a) if isinstance(a, str) and a.isdigit() and 15 <= int(a) <= 19 else None


def o_gaps(record, names):
    return sum(1 for n in names if record[n] is None)


_SHOWN = {}


def o_shown(s):
    """Which records each number a count shows counts: the total, every group (or cell), every
    left-out line (R30-2), learnt from counting.tally on each record alone. A list of frozensets
    of record indexes."""
    key = json.dumps(s, sort_keys=True)
    if key not in _SHOWN:
        tally = mod("counting").tally
        numbers = None
        for i, record in enumerate(O_RECORDS):
            t = tally(O_SRC, [record], s, O_NEWEST)
            row = [t["total"]] + [g[-1] for g in (t["groups"] or t["grid"] or [])] + \
                [t["left_out"][n] for n in sorted(t["left_out"])]
            if numbers is None:
                numbers = [set() for _ in row]
            assert len(row) == len(numbers) and set(row) <= {0, 1}, (s, row)
            for k, n in enumerate(row):
                if n:
                    numbers[k].add(i)
        _SHOWN[key] = [frozenset(n) for n in numbers]
    return _SHOWN[key]


def o_rank(rows):
    """The rank of whole-number rows, exactly (fraction-free elimination; each new row divided
    by what its entries share)."""
    rows = [list(r) for r in rows if any(r)]
    rank, width = 0, len(rows[0]) if rows else 0
    for col in range(width):
        pick = next((r for r in range(rank, len(rows)) if rows[r][col]), None)
        if pick is None:
            continue
        rows[rank], rows[pick] = rows[pick], rows[rank]
        top = rows[rank]
        for r in range(rank + 1, len(rows)):
            f = rows[r][col]
            if f:
                new = [top[col] * x - f * y for x, y in zip(rows[r], top)]
                g = 0
                for x in new:
                    g = _gcd(g, x)
                rows[r] = [x // g for x in new] if g > 1 else new
        rank += 1
        if rank == len(rows):
            break
    return rank


def _gcd(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def o_one_year(numbers, keep):
    """True when some sum of the shown numbers (each any number of times, either sign), over the
    records `keep` allows, is not zero and counts only records of one usable age under 18."""
    columns = {}
    for i, record in enumerate(O_RECORDS):
        if keep(record):
            columns.setdefault((tuple(i in n for n in numbers), o_year(record)), None)
    cols = list(columns)
    rows = [[int(member[k]) for member, _ in cols] for k in range(len(numbers))]
    whole = o_rank(rows)
    for y in (15, 16, 17):
        others = [[x for x, (_, yy) in zip(row, cols) if yy != y] for row in rows]
        if whole > o_rank(others):
            return True
    return False


def oracle(specs):
    """(i, ii, iii) of R30-1 for a set of checked specs."""
    numbers = [n for s in specs for n in o_shown(s)]
    named = {n for s in specs for n in [f["field"] for f in s["filters"]] + s["group_by"]
             if n in O_FIELDS}
    every = o_one_year(numbers, lambda r: True)
    usable = o_one_year(numbers, lambda r: o_year(r) is not None)
    few_gaps = o_one_year(numbers, lambda r: o_year(r) is not None and o_gaps(r, named) <= 1)
    return every, usable, few_gaps


O_PERIODS = ({"year": 2024}, {"year": 2025}, {"years": [2024, 2025]})
O_AGE_PICKS = (None, (None, 17), (15, 16), (16, 17), (15, 17), (17, 18), (16, 18), (17, 19),
               (18, 19), (16, None), (17, None), (18, None), (None, 16), (15, 19), (None, 18))
O_BY = ([], [], ["year"], ["colour"], ["shape"], ["lit"], ["age_band"], ["colour", "shape"],
        ["year", "colour"], ["year", "shape"], ["colour", "lit"], ["shape", "age_band"])
LABELS = {"colour": ("red", "green"), "shape": ("square", "circle")}


def o_age(pick):
    if pick is None:
        return []
    out = {"field": "age"}
    if pick[0] is not None:
        out["from"] = pick[0]
    if pick[1] is not None:
        out["to"] = pick[1]
    return [out]


def o_cat(name, how):
    if how == "every":
        return [{"field": name, "in": list(LABELS[name])}]
    if how in LABELS[name]:
        return [{"field": name, "is": how}]
    return []


def o_raw(period, ages, colour=None, shape=None, lit=None, group_by=()):
    filters = o_age(ages) + o_cat("colour", colour) + o_cat("shape", shape)
    if lit is not None:
        filters.append({"field": "lit", "is": lit})
    return {"source": O_ID, "period": period, "filters": filters, "group_by": list(group_by)}


def o_check(raw):
    counting = mod("counting")
    try:
        return counting.check_spec(O_SRC, O_COPY, raw)
    except counting.SpecError:
        return None  # refused on its own (a single year asked outright, ...): never counted


def o_pick_cat(rng, name):
    return rng.choice([None, None, "every", "every", *LABELS[name]])


def o_random(rng):
    return o_raw(rng.choice(O_PERIODS), rng.choice(O_AGE_PICKS), o_pick_cat(rng, "colour"),
                 o_pick_cat(rng, "shape"), rng.choice([None, None, True, False]),
                 rng.choice(O_BY))


def o_family(rng):
    """The same people cut by neighbouring ages, an every-label filter or one label, by year or
    by a field."""
    period = rng.choice(O_PERIODS)
    colour, shape = o_pick_cat(rng, "colour"), o_pick_cat(rng, "shape")
    lit = rng.choice([None, None, True])
    low = rng.choice([None, 15, 16, 17])
    out = []
    for _ in range(rng.randint(1, 4)):
        p, c, s, by = period, colour, shape, []
        ages = rng.choice([(low, None), (low, 17), (low, 16), (17, None), (18, None), (low, 18),
                           (16, None)])
        move = rng.choice(["ages", "every", "one", "year", "field", "two years"])
        if move == "every":
            c = "every" if c != "every" else rng.choice(LABELS["colour"])
        elif move == "one":
            s = rng.choice(LABELS["shape"]) if s in (None, "every") else "every"
        elif move == "year":
            p, by = {"years": [2024, 2025]}, ["year"]
        elif move == "field":
            by = [rng.choice(["colour", "shape", "lit", "age_band"])]
        elif move == "two years":
            p = rng.choice(O_PERIODS)
        out.append(o_raw(p, ages, c, s, lit, by))
    return out


SEEDS = range(2000)


def o_set(seed):
    rng = random.Random(30_000 + seed)
    raws = o_family(rng) if seed % 2 == 0 else [o_random(rng) for _ in range(rng.randint(1, 4))]
    return [s for s in (o_check(r) for r in raws) if s is not None]


def o_program(specs):
    return bool(mod("counting").one_year_under_18(O_SRC, specs, O_COPY))


def test_step4_the_oracle_against_the_program():
    """Step 4: on 2,000 seeded sets of one to four counts (half of them families), the program's
    function answers "(ii) or (iii)" of R30-1, and never "no" where (i) is "yes". A failure prints
    the smallest disagreeing set, with the oracle's three answers."""
    wrong, counts = [], {"sets": 0, "every": 0, "usable": 0, "few gaps": 0, "families": 0}
    for seed in SEEDS:
        specs = o_set(seed)
        if not specs:
            continue
        every, usable, few_gaps = oracle(specs)
        counts["sets"] += 1
        counts["families"] += seed % 2 == 0
        counts["every"] += every
        counts["usable"] += usable
        counts["few gaps"] += few_gaps
        got = o_program(specs)
        if got is not (usable or few_gaps) or (every and not got):
            wrong.append((len(json.dumps(specs)), seed, got, (every, usable, few_gaps), specs))
    assert counts["sets"] >= 1900 and counts["families"] >= 900, f"premise: {counts}"
    assert 0.15 * counts["sets"] < counts["usable"] < 0.85 * counts["sets"], \
        f"premise: a mix of answers: {counts}"
    assert counts["few gaps"] > counts["usable"], f"premise: (iii) adds yeses: {counts}"
    wrong.sort(key=lambda w: w[0])
    assert not wrong, (f"{len(wrong)} of {counts['sets']} sets disagree; the smallest: seed "
                       f"{wrong[0][1]}, program {wrong[0][2]}, oracle (i, ii, iii) {wrong[0][3]}: "
                       f"{json.dumps(wrong[0][4])}")


def o_spec(period, ages, colour=None, shape=None, lit=None, group_by=()):
    s = o_check(o_raw(period, ages, colour, shape, lit, group_by))
    assert s is not None, "premise: the count is not refused on its own"
    return s


O_DEFECT_2 = [o_spec({"year": 2025}, (18, None), group_by=["colour", "shape"]),
              o_spec({"years": [2024, 2025]}, (17, None), "red", "every", group_by=["year"])]


def test_step4_the_oracle_says_yes_with_every_record_for_defect_2():
    """Step 4: check 14's DEFECT 2 rebuilt in the made-up source (18 and over in 2025 by colour
    and shape; then 17 and over, red, every shape, 2024 and 2025, by year): the oracle says yes
    with every record, (i), and so with (ii). Passes today (the oracle uses no program code to
    decide)."""
    every, usable, _ = oracle(O_DEFECT_2)
    assert every and usable
    assert oracle(O_DEFECT_2[:1]) == (False, False, False)


def test_step4_the_program_on_defect_2_rebuilt():
    """The program's function on the same two counts: refused (it is today: no)."""
    assert o_program(O_DEFECT_2) is True


ORACLE_SELF = {  # the oracle on small cases its own words decide: (specs, (i, ii, iii))
    "under 18, then under 17 (the 17-year-olds)": (
        [((2025,), (None, 17)), ((2025,), (None, 16))], (True, True, True)),
    "every age, then 16 and over: the age's own left-out line gives the 15-year-olds": (
        [((2025,), None), ((2025,), (16, None))], (True, True, True)),
    "every age of 2025, then 16 and over of two years by year: only without no usable age": (
        [((2025,), None), ((2024, 2025), (16, None), None, None, None, ["year"])],
        (False, True, True)),
    "a breakdown by colour and shape, then every record: only (iii)": (
        [((2025,), (None, 17), None, None, None, ["colour", "shape"]), ((2025,), (None, 16))],
        (False, False, True)),
    "two years by year, then under 17 of one year: the 17-year-olds of 2025": (
        [((2024, 2025), (None, 17), None, None, None, ["year"]), ((2025,), (None, 16))],
        (True, True, True)),
    "two years by year, then 16 and over of one year: no single year": (
        [((2024, 2025), (None, 16), None, None, None, ["year"]), ((2025,), (16, None))],
        (False, False, False)),
}


@pytest.mark.parametrize("name", list(ORACLE_SELF))
def test_step4_the_oracle_on_its_own_small_cases(name):
    """The oracle itself on cases written out by hand. Passes today."""
    raw, expected = ORACLE_SELF[name]
    specs = []
    for period, ages, *rest in raw:
        p = {"year": period[0]} if len(period) == 1 else {"years": list(period)}
        specs.append(o_spec(p, ages, *rest))
    assert oracle(specs) == expected, name


def test_step4_the_oracle_is_quick_enough():
    """The comparison above runs in a few minutes at most: one set of four counts takes under a
    second here (a premise of the suite's time)."""
    specs = [s for s in (o_check(r) for r in o_family(random.Random(7))) if s is not None]
    started = time.perf_counter()
    oracle(specs)
    assert time.perf_counter() - started < 1.0


# ==== step 5: point 7, a rate's age bands are the Census's =========================================

def rate_spec(src, period=Y25, filters=()):
    return checked(src, period, filters)


def test_step5_shown_bands_of_a_rate_by_age_band_with_the_census_bands():
    """Point 7: shown_bands with `age_bands` for a rate by age band: every usable age (its own
    band) and the Census's bands cut to arrests_like's usable ages (10 to 98): 65 and over is 65
    to 98; the source's own last band (55 to 98) is not among them."""
    src = source_json(A)
    got = mod("counting").shown_bands(src, rate_spec(src), RATE_BY_BAND, age_bands=CENSUS)
    assert set(map(tuple, got)) == {(10, 98), (10, 17), (18, 24), (25, 34), (35, 44), (45, 54),
                                    (55, 64), (65, 98)}, got


def test_step5_shown_bands_without_age_bands_is_as_today():
    """Point 7: with no `age_bands`, a breakdown by age band gives the source's own bands (passes
    today; must still pass)."""
    src = source_json(A)
    got = mod("counting").shown_bands(src, rate_spec(src), RATE_BY_BAND)
    assert set(map(tuple, got)) == {(10, 98), (10, 17), (18, 24), (25, 34), (35, 44), (45, 54),
                                    (55, 98)}, got


def test_step5_shown_bands_of_a_rate_by_gender_ignores_the_census_bands():
    """A rate by gender has one band, every usable age, with or without `age_bands`."""
    src = source_json(A)
    for kw in ({}, {"age_bands": CENSUS}):
        got = mod("counting").shown_bands(src, rate_spec(src), RATE_BY_GENDER, **kw)
        assert set(map(tuple, got)) == {(10, 98)}, (kw, got)


def test_step5_shown_bands_of_a_source_whose_usable_ages_end_at_17():
    """Point 7's test: the juvenile-like source (usable ages 10 to 17): the Census's bands cut to
    those ages leave 10 to 17 alone (18 to 24 and the others, 65 and over too, have no age left)."""
    src = juvenile_source()
    assert src["fields"][[f["kind"] for f in src["fields"]].index("age")]["usable"] == [10, 17], \
        "premise"
    got = mod("counting").shown_bands(src, rate_spec(src), RATE_BY_BAND, age_bands=CENSUS)
    assert set(map(tuple, got)) == {(10, 17)}, got


def test_step5_shown_bands_cut_to_coded_likes_usable_ages():
    """coded_like (usable ages 12 to 90): 10 to 17 becomes 12 to 17, 65 and over 65 to 90."""
    src = source_json("coded_like")
    got = mod("counting").shown_bands(src, rate_spec(src), RATE_BY_BAND, age_bands=CENSUS)
    assert set(map(tuple, got)) == {(12, 90), (12, 17), (18, 24), (25, 34), (35, 44), (45, 54),
                                    (55, 64), (65, 90)}, got


def test_step5_shown_bands_cut_to_the_rates_own_ages():
    """Point 7, "each cut ... to the rate's own ages": with an age filter of 18 to 70 on the spec
    (a rate takes none in the program; the function cuts), the bands are 18 to 24 ... 55 to 64 and
    65 to 70; 10 to 17 has no age left."""
    src = source_json(A)
    got = mod("counting").shown_bands(src, rate_spec(src, filters=[age(18, 70)]), RATE_BY_BAND,
                                      age_bands=CENSUS)
    assert set(map(tuple, got)) == {(18, 70), (18, 24), (25, 34), (35, 44), (45, 54), (55, 64),
                                    (65, 70)}, got


def test_step5_shown_figures_with_and_without_age_bands():
    """shown_figures passes `age_bands` on: each band over the days of the period (2025), held
    against every value (no field constraint); without it, the source's bands."""
    src = source_json(A)
    s = rate_spec(src)
    start, newest = date(2024, 1, 1), NEWEST_A
    counting = mod("counting")
    with_census = counting.shown_figures(src, s, RATE_BY_BAND, start, newest, age_bands=CENSUS)
    without = counting.shown_figures(src, s, RATE_BY_BAND, start, newest)
    runs = ((date(2025, 1, 1), date(2025, 12, 31)),)
    assert {(tuple(r), tuple(sorted(dict(k).items())), tuple(b)) for r, k, b in with_census} == \
        {(runs, (), b) for b in [(10, 98), (10, 17), (18, 24), (25, 34), (35, 44), (45, 54),
                                 (55, 64), (65, 98)]}, with_census
    assert {tuple(b) for _, _, b in without} == {(10, 98), (10, 17), (18, 24), (25, 34), (35, 44),
                                                 (45, 54), (55, 98)}, without


def decide_7(items, src=None, newest=NEWEST_A):
    """As test_s3_c65.decide, with a rate's figures given the Census bands (point 7)."""
    counting = mod("counting")
    src = src or source_json(A)
    copy = fcopy(newest, src["id"])
    start = date.fromisoformat(src["coverage_start"])
    specs, shown = [], []
    for it in items:
        s = counting.check_spec(src, copy, {"source": src["id"], "period": it.period,
                                            "filters": list(it.filters),
                                            "group_by": list(it.group_by)})
        if isinstance(it, Stat):
            shown.extend(counting.shown_figures(src, s, it.options, start, newest,
                                                age_bands=CENSUS if it.kind == "rate" else None))
        else:
            specs.append(s)
    return bool(counting.one_year_under_18(src, specs, copy, shown=shown))


RATE_25 = Stat("rate", Y25, options=RATE_BY_BAND)
RATE_CASES = {
    "a rate by age band, then 17 to 64 of its year": ([RATE_25, Cnt(Y25, [age(17, 64)])], True),
    "17 to 64, then the rate (the other order)": ([Cnt(Y25, [age(17, 64)]), RATE_25], True),
    "a rate by age band, then 18 to 64": ([RATE_25, Cnt(Y25, [age(18, 64)])], False),
    "a rate by gender, then 17 to 64": (
        [Stat("rate", Y25, options=RATE_BY_GENDER), Cnt(Y25, [age(17, 64)])], False),
    "a rate with no breakdown, then 17 to 64": (
        [Stat("rate", Y25, options=RATE), Cnt(Y25, [age(17, 64)])], False),
    "a rate by age band, then 17 and over (65 and over is a band)": (
        [RATE_25, Cnt(Y25, [age(17)])], True),
    "a rate by age band, then 16 to 24 (10 to 17 and 18 to 24)": (
        [RATE_25, Cnt(Y25, [age(16, 24)])], False),
    "a rate by age band, then 10 to 16 (10 to 17 less it)": ([RATE_25, Cnt(Y25, [A10_16])], True),
    "a rate by age band of 2024, then 17 to 64 in 2025": (
        [Stat("rate", Y24, options=RATE_BY_BAND), Cnt(Y25, [age(17, 64)])], False),
    "a rate by age band, then 17 to 64 from January to June (it stands for each part of its days)":
        ([RATE_25, Cnt(H1, [age(17, 64)])], True),
    "a rate by age band, then 17 to 64 in each half": (
        [RATE_25, Cnt(H1, [age(17, 64)]), Cnt(H2, [age(17, 64)])], True),
}


@pytest.mark.parametrize("name", list(RATE_CASES))
def test_step5_one_year_under_18_with_a_rate_by_age_band(name):
    """Point 7 through the function: a rate by age band with the Census's bands and counts."""
    items, expected = RATE_CASES[name]
    assert decide_7(items) is expected, name


def test_step5_the_source_bands_would_miss_it():
    """The premise of DEFECT 1: with the source's own bands (no `age_bands`), the rate by age band
    and 17 to 64 give no single year to the function (passes today)."""
    assert decide([RATE_25, Cnt(Y25, [age(17, 64)])]) is False


# ---- a rate remembered from an earlier turn (stored as the program stores it) --------------------

def stored_rate(options=RATE_BY_BAND, period=Y25, days=("2024-01-01", "2026-09-17")):
    s = {"source": A_ID, "period": period, "filters": [], "group_by": []}
    return {"id": "a1", "kind": "analysis", "stat": "rate", "spec": s, "options": dict(options),
            "read_as": "SYNTHETIC arrest rate per 10,000 residents", "run_id": "R30-NO-RUN",
            "days": list(days)}


def stored_trend_by(options, period=Y25):
    s = {"source": A_ID, "period": period, "filters": [], "group_by": []}
    return {"id": "a1", "kind": "analysis", "stat": "trend", "spec": s, "options": dict(options),
            "read_as": "SYNTHETIC trend of arrest records", "run_id": "R30-NO-RUN",
            "days": ["2024-01-01", "2026-09-17"]}


def replace_results(env, results, thread_key=THREAD_1):
    """The thread's newest turn holds `results` in place of its own (a real answered turn first)."""
    db = sqlite3.connect(env.tmp_path / "agent.db")
    try:
        row_id, text = db.execute("SELECT id, record FROM agent_turns WHERE thread_key = ? "
                                  "ORDER BY id DESC LIMIT 1", (thread_key,)).fetchone()
        record = json.loads(text)
        record["results"] = list(results)
        db.execute("UPDATE agent_turns SET record = ? WHERE id = ?", (json.dumps(record), row_id))
        db.commit()
    finally:
        db.close()


def remember(env, *results):
    reply, answers = ask_counts(env, [spec(Y24, [age(30, 40)])], "a message")
    assert_answered(reply, answers)
    replace_results(env, results)


@pytest.mark.parametrize("ages, options, refused", [
    (age(17, 64), RATE_BY_BAND, True),
    (age(17), RATE_BY_BAND, True),
    (age(18, 64), RATE_BY_BAND, False),
    (age(17, 64), RATE_BY_GENDER, False),
], ids=["by age band, then 17 to 64", "by age band, then 17 and over", "by age band, then 18 to 64",
        "by gender, then 17 to 64"])
def test_step5_a_rate_remembered_from_an_earlier_turn(tmp_path, monkeypatch, ages, options,
                                                      refused):
    """Point 7: an earlier answered turn holds a rate of 2025 (as the program remembers it, with
    its days); a count of 2025 is refused with C62 point 2's sentence when the Census's bands give
    one year with it, and answered when they do not. (A rate by age band stored on arrests_like,
    whose own last band is 55 to 98; no Census copy is read: the check needs none.)"""
    env = CountyEnv(tmp_path, monkeypatch)
    remember(env, stored_rate(options))
    reply, (answer,) = ask_counts(env, [spec(Y25, [ages])], "and how many in 2025?")
    if refused:
        assert_refused(answer)
        assert reply.text == NEW_SENTENCE, reply.text
    else:
        assert_answered(reply, [answer])


def test_step5_a_remembered_rate_of_another_source_is_not_read(tmp_path, monkeypatch):
    """A rate by age band remembered for the juvenile-like source, then 17 to 64 of arrests_like:
    answered (another source's figures are never read in)."""
    env = two_sources(tmp_path, monkeypatch)
    rate = stored_rate()
    rate["spec"]["source"] = SIDS[J]
    rate["days"] = ["2024-01-01", "2026-09-17"]
    remember(env, rate)
    reply, answers = ask_counts(env, [spec(Y25, [age(17, 64)])])
    assert_answered(reply, answers)


@pytest.mark.parametrize("ages, refused", [(age(17, 64), True), (age(18, 64), False)],
                         ids=["17 to 64", "18 to 64"])
def test_step5_a_rate_kept_through_reset(tmp_path, monkeypatch, ages, refused):
    """Point 7 with C65 point 4: an answered turn holding a rate by age band of 2025, then `reset`
    (the stripped record keeps "stat": "rate"), then a count of 2025: 17 to 64 refused with C62
    point 2's sentence, 18 to 64 answered."""
    env = slack_env(tmp_path, monkeypatch)
    talk = Talk(env)
    label, reply = talk.count(spec(Y24, [age(30, 40)]), "how many aged 30 to 40 in 2024?")
    assert label == "answered", (label, reply.text)
    replace_results(env, [stored_rate()])
    label, _ = talk.send("reset")
    assert label == "reset"
    kept = plain(given(env))
    assert holds(kept, "rate"), f"premise: the stripped record keeps the rate: {kept}"
    label, reply = talk.count(spec(Y25, [ages]), "and how many in 2025?")
    if refused:
        assert_refused(env.model.answer(0))
        assert reply.text == NEW_SENTENCE, reply.text
    else:
        assert label == "answered", (label, reply.text)


def spy_bands(monkeypatch):
    """Records the `age_bands` of every call of counting.shown_figures and shown_bands (each still
    does its work), read by the real function's own signature: (function, options, age_bands)."""
    calls = []
    counting = mod("counting")
    for name in ("shown_figures", "shown_bands"):
        real = getattr(counting, name)

        def spy(*args, _real=real, _name=name, **kwargs):
            bound = inspect.signature(_real).bind(*args, **kwargs).arguments
            calls.append((_name, bound.get("options"), bound.get("age_bands")))
            return _real(*args, **kwargs)
        monkeypatch.setattr(counting, name, spy)
    return calls


def test_step5_no_other_statistic_is_passed_the_census_bands(tmp_path, monkeypatch):
    """Point 7, "for no other statistic": a thread remembering a trend and a distribution and a
    rate by age band; a count is checked against them. The rate's figures are asked for with the
    Census's bands (as a list of pairs, R30-5), the others' with none."""
    env = CountyEnv(tmp_path, monkeypatch)
    remember(env, stored_trend_by({}), stored_trend_by({"by": "gender"}) | {"stat": "distribution",
                                                                            "id": "a2"},
             stored_rate() | {"id": "a3"})
    calls = spy_bands(monkeypatch)
    reply, answers = ask_counts(env, [spec(Y25, [age(30, 40)])])
    assert_answered(reply, answers)
    rate = [bands for _, options, bands in calls if options == RATE_BY_BAND]
    others = [bands for _, options, bands in calls if options != RATE_BY_BAND]
    assert rate and others, f"premise: each statistic was read: {calls}"
    assert all(b is not None and [tuple(x) for x in b] == CENSUS for b in rate), rate
    assert all(b is None for b in others), others


def test_step5_a_rate_by_age_band_with_the_census_bands_through_two_sources(tmp_path, monkeypatch):
    """A remembered rate by age band of the juvenile-like source (usable 10 to 17), then a count of
    that source aged 10 to 16 in 2025: refused (the Census's 10 to 17, cut to the source, less 10 to
    16). Passes today too (the source's own band 10 to 17 gives the same)."""
    env = two_sources(tmp_path, monkeypatch)
    rate = stored_rate()
    rate["spec"]["source"] = SIDS[J]
    remember(env, rate)
    reply, (answer,) = ask_counts(env, [spec(Y25, [A10_16], name=J)])
    assert_refused(answer)


def test_step5_the_thread_block_and_details_are_unchanged_by_a_remembered_rate(tmp_path,
                                                                               monkeypatch):
    """Point 7 changes only what the check holds against: the next turn's thread block still
    names the remembered rate as today (premise that the remembered record is read as a rate)."""
    env = CountyEnv(tmp_path, monkeypatch)
    remember(env, stored_rate())
    ask_counts(env, [spec(Y24, [age(30, 40)])])
    block = thread_block(env.model.calls[0]["messages"]) or ""
    assert "SYNTHETIC arrest rate per 10,000 residents" in block, block
