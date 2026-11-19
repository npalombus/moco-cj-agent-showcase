"""C65 of docs/S3A-DESIGN.md (D-082): two ways round the under-18 rule, closed. Brief:
briefs/S3-R29-A-tests.md. Tests only; red until the planning chat builds C65, except those that pin
what stays (named in their docstrings and in kit-log/raw/S3-R29-A-notes.txt). The statistics that
R has to run for are in tests/s3s/test_s3s_c65.py.

Everything here is SYNTHETIC: the fixtures of tests/s3/fixtures (arrests_like, coded_like, and
test_s3_c54.py's juvenile-like copy of arrests_like), and two small made-up worlds of this file's
own for the oracle (step 4). No figure of a real county source is used or quoted.

What is here, in the brief's order:
3. counting.one_year_under_18(source, specs, copy=None, days=None, shown=()) and
   counting.shown_figures(source, spec, options, start, newest): every example of C65's Tests,
   points 1 and 2, and this session's own cases (FUNCTION_CASES; each says what its words decide).
4. An oracle of this session's own, written from C65's words: the whole table of a small world's
   cells (ages 15 to 19, six days, one field of two values and "no value"), each figure the set of
   its cells, and exact arithmetic (fractions). It is compared with the program's function on 520
   seeded sets of counts (arm A) and 520 seeded sets of counts and statistics (arm B).
5. County turns with the model stand-in: threads P21 (and P20's statistic, refused before R),
   talk off and on; a refusal of a statistic before anything is computed; a remembered statistic
   with and without `days`; a refresh of the copy between messages; another source never read in;
   SYNTHETIC mode untouched.
5b. Points 4 and 5 through slack_app.process_event and the store: `reset` keeps the stripped
   records and nothing else, the model and the other readers see an empty thread, two resets, the
   retention days, the reply's words; a top-level direct message read past its memory minutes; a
   thread longer than 500 turns.
7. Speed.

Readings (also in the notes; the open ones in briefs/QUESTIONS.md):
- R29-1. `shown` is one flat list: the figures of each statistic as shown_figures gives them, one
  statistic's after another. A test passes `shown` only when it has a statistic and `days` only
  when it gives one, so the cases with counts alone call the function as today.
- R29-2. A statistic's days are its period cut to the days of the copy it reads (start, newest),
  as a count's are (C21 answer 3, C62 point 5; the signature takes `start` and `newest`). S2's
  window of full months is narrower. Every test uses periods for which both give the same answer
  (whole years well inside the copy, or a whole month inside the window), so both are accepted.
- R29-3. shown_figures gets the options as the program keeps them for the result: check_options'
  tidied options, and a rate's {"by", "reference"}.
- R29-4. "Some sum of the figures leaves records of one single year under 18 and nothing else":
  the figures' sums, each taken any number of times and with any sign (C21's "added and subtracted,
  each taken any number of times"), hold a total that is not zero and lies in one single year of
  age under 18. The oracle also works out the narrower reading, "a count of records" (a sum that
  is the number of the records of some part of that year, every record once). Where the two differ
  (n(day 1) + 2 n(day 2) + n(day 3) of the 17-year-olds, say), both answers are accepted and the
  case is a question (briefs/QUESTIONS.md).
- R29-5. A statistic "stands for a figure of EACH part of the records of its days, whatever its
  other filters": every cell of its days (every day, hour and value of every field, with no value
  too), for each of its bands; its filters other than age do not narrow it. What a weekday filter
  does to a statistic's days, and whether under_18's bands are cut to the statistic's own ages, are
  not tested (no test needs them).
- R29-6. C65's Tests say "under 18 of one district and ages 10 to 16 of another" are both
  answered, but C52 point 4 refuses that pair (their left-out figures, records with no district,
  differ by the 17-year-olds; the round 16 tests pin it) and C65 says "What C21 refused it still
  refuses". The test accepts both (briefs/QUESTIONS.md); the pairs that surely cannot be combined
  (two years; one district then no district filter) are pinned.
- R29-7. A statistic refused by the check: tool answer NOT_ALLOWED, `field` the age field, `why`
  C21's word for word, with C61 point 10's sentence when the thread's earlier figures are the cause;
  nothing computed: stats.prepare, stats.run_r, stats.write_job and rates.count are not called, no
  job folder and no saved record (manifest.json).
- R29-8. A rate with an age filter is refused either by the check (NOT_ALLOWED) or by R10 point 7's
  refusal of any filter (BAD_OPTIONS), whichever comes first; both are accepted, nothing run.
- R29-9. `Store.given_before_reset(thread_key, limit)` returns the stripped records in a form the
  contract leaves open; the tests search it (and every table of the store) for what must and must
  not be there.
- R29-11. C52 point 1 (a category filter that names every label "is no filter, for the kind")
  makes age_figures' figures of such a count hold the records with no value too, its groups
  included; the records the count keeps do not. C65's figures are "as counting.age_figures gives
  them", and also "of its values of each field it names". The oracle works out both; where they
  differ (only ever the program refusing a little more) both are accepted (briefs/QUESTIONS.md).
- Changed by briefs/S3-R30-A-tests.md (C65 point 6d): one FUNCTION_CASES case turns round, "own:
  three fields, the last in another district (does not fit)", now True (refused); it was False.
  The cases that accept both readings of C52 point 1 (R29-11) stay as they are;
  tests/s3/test_s3_c65b.py pins point 6's reading.
- Changed by briefs/S3-R31-A-tests.md (C65 point 8): the two cases
  test_p2_each_kind_after_under_18_is_refused_before_anything_is_computed[distribution-off] and
  [distribution-on] (a distribution of ages 10 to 16 is refused on its own: C21's `why` alone, the
  NOT_ALLOWED row; the test's first point kept with a distribution of under 18 after a count of 10 to
  16). The FUNCTION_CASES with a distribution do not change: they ask shown_figures without
  `steps`, as before; tests/s3/test_s3_c65c.py has the steps.
- R29-10. C64 is not built: where C64 point 3a's line would come, the reply is accepted with or
  without it (at most once).
"""
import json
import random
import sqlite3
import time
from datetime import date, timedelta
from fractions import Fraction
from itertools import product

import pytest

from p1support import (AGENT_USER, FAKE_SECRETS, RESET_LINE, ROOT_TS, TEAM, THREAD_1, THREAD_2,
                       USER, USER2, Env, FakeModel, FakeSlack, Step, call, describe,
                       direct_message, finish, manifests, mention, mod, process, show_details,
                       thread_block)
from s3support import (A_ID, C64_LINE_A, C65_RESET_LINE, NEWEST, NOW_S3, SCHOOL, WEEKDAYS,
                       CountyEnv, age, clear, count, dates, hours, in_,
                       in_period, is_, months, source_json, synthetic_three_turns, weekdays, year,
                       years)
from test_s3_c41 import CAN_ASK
from test_s3_c54 import J, SIDS, call_of, two_sources
from test_s3_c61d import P05_FIRST, WHY_THREAD, assert_answered, assert_refused, turn
from test_s3_c62 import NEWEST_B, refresh
from test_s3_synthetic_untouched import assert_same_as_today
from test_s3_round5 import A, AGE_FIELD, NOT_ALLOWED_ROW, U17, U18, WHY, Y25, line1, phrase, spec

NEW_SENTENCE = (f"With the figures already given in this conversation, that count would give one "
                f"single year of age under 18, so I don't give it. {CAN_ASK[1]}")   # C62 point 2
OLD_SENTENCE = f"{NOT_ALLOWED_ROW} {CAN_ASK[1]}"
SLACK = dict(FAKE_SECRETS, SLACK_ALLOWED_TEAM_ID=TEAM, SLACK_ALLOWED_USER_IDS=f"{USER},{USER2}")
TALK = ["off", "on"]

Y24, Y26 = year(2024), year(2026)
H1, H2 = months(2025, 1, 6), months(2025, 7, 12)
QUARTERS = [months(2025, 1, 3), months(2025, 4, 6), months(2025, 7, 9), months(2025, 10, 12)]
A10_16 = age(10, 16)
F, M = is_("gender", "female"), is_("gender", "male")
D3, D4, D5 = (is_("district", f"district {n}") for n in (3, 4, 5))
ALPHA_BETA, GAMMA = in_("race", "group Alpha", "group Beta"), is_("race", "group Gamma")
NEAR, NOT_NEAR = is_(SCHOOL, True), is_(SCHOOL, False)
MON_FRI = weekdays("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
SINCE_2024 = dates("2024-01-01", "2026-09-17")      # arrests_like's whole copy
FIRST_DAY = date(2024, 1, 1)                         # arrests_like's coverage_start
NEWEST_A = NEWEST["arrests_like"]                    # 17 September 2026
QUESTION_CASE = "either"                             # a case whose answer is a question


# ==== step 3: the function ======================================================================

def fcopy(newest, sid=A_ID):
    """A copy of the source, for the function alone (no rows are read): its newest day."""
    return mod("sources").Copy(source_id=sid, folder="", fetched_at="2026-11-12T15:00:00Z", rows=0,
                               newest=f"{newest.isoformat()}T08:30:00.000", fields=(),
                               sha256="0" * 64)


class Cnt:
    """A count: its period, filters and breakdowns as the model sends them; `days`, the (first,
    last) day of the copy it was counted from (C62 point 5), when not this copy."""

    def __init__(self, period, filters=(), group_by=(), days=None):
        self.period, self.filters, self.group_by, self.days = period, filters, group_by, days


class Stat:
    """A statistic: `kind`, its period and filters, and its options: `raw` as the model sends them
    (tidied by stats.check_options) or `options` as the program keeps them. `days`: the (first,
    last) day of its copy when not this copy."""

    def __init__(self, kind, period, filters=(), raw=None, options=None, days=None):
        self.kind, self.period, self.filters = kind, period, filters
        self.raw, self.options, self.days = raw, options, days
        self.group_by = ()


def decide(items, src=None, newest=NEWEST_A):
    """one_year_under_18 on the items, each checked and tidied by C5 (counting.check_spec) as the
    turn does; the statistics' figures from shown_figures (R29-1, R29-3)."""
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
            shown.extend(counting.shown_figures(src, s, options, first, last))
        else:
            specs.append(s)
            days.append(it.days)
    kw = {}
    if any(d is not None for d in days):
        kw["days"] = days
    if any(isinstance(it, Stat) for it in items):
        kw["shown"] = shown
    return bool(counting.one_year_under_18(src, specs, copy, **kw))


def band_source(bands):
    """arrests_like's file with other age bands (a band that ends at 18)."""
    src = source_json(A)
    (f,) = [f for f in src["fields"] if f["kind"] == "age"]
    f["bands"] = [list(b) for b in bands]
    return src


def trend_10_16(period=SINCE_2024, more=(), days=None):
    return Stat("trend", period, [A10_16, *more], raw={}, days=days)


U18_25 = Cnt(Y25, [U18])
KIND_CASES = {  # each kind of statistic with an age filter of 10 to 16 (and what it needs)
    "trend": ([A10_16], {}),
    "trend_compare": ([A10_16, F], {"versus": [A10_16, M]}),
    "before_after": ([A10_16], {"date": "2025-01-01"}),
    "yes_no": ([A10_16], {"outcome": SCHOOL, "factors": [{"field": "gender", "is": "female"}]}),
    "shares": ([A10_16], {"part": [D3]}),
    "timing": ([A10_16], {}),
    "distribution": ([A10_16], {}),
}
RATE = {"by": None, "reference": None}
RATE_BY_BAND = {"by": "age_band", "reference": None}
RATE_BY_GENDER = {"by": "gender", "reference": None}
AGE_10_16_OPTION = [{"field": "age", "from": 10, "to": 16}]
DAYS_A = (FIRST_DAY, NEWEST_A)

# name: (items, expected). True: one single year of age under 18 follows (refused).
FUNCTION_CASES = {
    # ---- C65's Tests, point 1 ----
    "P21 halves: under 18, then 10 to 16 from January to June (one step)":
        ([U18_25, Cnt(H1, [A10_16])], False),
    "P21 halves: and then July to December (completes it)":
        ([U18_25, Cnt(H1, [A10_16]), Cnt(H2, [A10_16])], True),
    "P21 halves the other way: the two halves alone":
        ([Cnt(H1, [A10_16]), Cnt(H2, [A10_16])], False),
    "P21 halves the other way: the two halves, then under 18":
        ([Cnt(H1, [A10_16]), Cnt(H2, [A10_16]), U18_25], True),
    "P21 genders: under 18, then male 10 to 16 (one step)":
        ([U18_25, Cnt(Y25, [A10_16, M])], False),
    "P21 genders: and then female 10 to 16 (with the no-value figure)":
        ([U18_25, Cnt(Y25, [A10_16, M]), Cnt(Y25, [A10_16, F])], True),
    "P20: the trend of 10 to 16 alone": ([trend_10_16()], False),
    "P20: under 18 in 2025 and the trend of 10 to 16": ([trend_10_16(), U18_25], True),
    "P20: the trend after the count": ([U18_25, trend_10_16()], True),
    "C21 as today: under 17 after under 18": ([U18_25, Cnt(Y25, [U17])], True),
    "C21 as today: 11 and over after all ages": ([Cnt(Y25), Cnt(Y25, [age(11)])], True),
    "C21 as today: 14 to 15 after 10 to 16 and 10 to 13":
        ([Cnt(Y25, [A10_16]), Cnt(Y25, [age(10, 13)]), Cnt(Y25, [age(14, 15)])], True),
    "C21 as today: 17 to 20 by age band, on its own":
        ([Cnt(Y25, [age(17, 20)], ["age_band"])], True),
    "C21 as today: female 10 to 17 after 10 to 16 by gender":
        ([Cnt(Y25, [A10_16], ["gender"]), Cnt(Y25, [age(10, 17), F])], True),
    "C52 as today: under 17 at every hour after under 18":
        ([U18_25, Cnt(Y25, [U17, hours(0, 23)])], True),
    "C52 as today: under 18 in district 3, then under 17 in district 5":
        ([Cnt(Y25, [U18, D3]), Cnt(Y25, [U17, D5])], True),
    "C54 as today: one day, then the same day on its weekday":
        ([Cnt(dates("2025-04-11", "2025-04-11"), [U18]),
          Cnt(dates("2025-04-11", "2025-04-11"), [U17, weekdays("Friday")])], True),
    "C21 allowed as today: under 18 and 18 to 24": ([U18_25, Cnt(Y25, [age(18, 24)])], False),
    "C21 allowed as today: under 18 and under 16": ([U18_25, Cnt(Y25, [age(None, 15)])], False),
    "C21 allowed as today: 18 to 21 and 19 to 21":
        ([Cnt(Y25, [age(18, 21)]), Cnt(Y25, [age(19, 21)])], False),
    "cannot be combined: under 18 in 2024, 10 to 16 in 2025":
        ([Cnt(Y24, [U18]), Cnt(Y25, [A10_16])], False),
    "cannot be combined: under 18 in district 3, 10 to 16 with no district filter":
        ([Cnt(Y25, [U18, D3]), Cnt(Y25, [A10_16])], False),
    "C65's example: under 18 in district 3, 10 to 16 in district 5 (R29-6)":
        ([Cnt(Y25, [U18, D3]), Cnt(Y25, [A10_16, D5])], QUESTION_CASE),
    "four quarters: three of them": ([U18_25] + [Cnt(q, [A10_16]) for q in QUARTERS[:3]], False),
    "four quarters: all four": ([U18_25] + [Cnt(q, [A10_16]) for q in QUARTERS], True),
    "the hours in two ranges: the first": ([U18_25, Cnt(Y25, [A10_16, hours(0, 11)])], False),
    "the hours in two ranges: both":
        ([U18_25, Cnt(Y25, [A10_16, hours(0, 11)]), Cnt(Y25, [A10_16, hours(12, 23)])], True),
    "the hours in two ranges, one round midnight":
        ([U18_25, Cnt(Y25, [A10_16, hours(22, 5)]), Cnt(Y25, [A10_16, hours(6, 21)])], True),
    # ---- C65's Tests, point 2 ----
    **{f"{kind}: 10 to 16 after under 18, days it shares": (
        [U18_25, Stat(kind, SINCE_2024, filters, raw=raw)], True)
       for kind, (filters, raw) in KIND_CASES.items()},
    **{f"{kind}: 10 to 16 after under 18, days it does not share": (
        [U18_25, Stat(kind, Y24, filters, raw=raw)], False)
       for kind, (filters, raw) in KIND_CASES.items()},
    "rate: by age band after 10 to 16": (
        [Cnt(Y25, [A10_16]), Stat("rate", Y25, options=RATE_BY_BAND)], True),
    "rate: by age band of 2024 after 10 to 16 in 2025": (
        [Cnt(Y25, [A10_16]), Stat("rate", Y24, options=RATE_BY_BAND)], False),
    "rate: with no breakdown after under 18": ([U18_25, Stat("rate", Y25, options=RATE)], False),
    "rate: by gender after under 18": ([U18_25, Stat("rate", Y25, options=RATE_BY_GENDER)], False),
    "a statistic with no age filter after under 18": ([U18_25, Stat("trend", SINCE_2024, raw={})],
                                                      False),
    "under 18, then 17 and over, after a trend of every age": (
        [Stat("trend", SINCE_2024, raw={}), U18_25, Cnt(Y25, [age(17)])], True),
    "under 18 and 17 and over with no statistic": ([U18_25, Cnt(Y25, [age(17)])], False),
    "a part of 10 to 16 of a whole under 18, on its own": (
        [Stat("shares", Y25, [U18], options={"part": AGE_10_16_OPTION})], True),
    # ---- this session's own (step 3) ----
    "own: a weekday filter with a breakdown by month, the sum fits": (
        [Cnt(QUARTERS[0], [U18, MON_FRI]), Cnt(months(2025, 1, 1), [A10_16, MON_FRI]),
         Cnt(months(2025, 2, 3), [A10_16, MON_FRI], ["month"])], True),
    "own: the same, the breakdown by month on every day (does not fit)": (
        [Cnt(QUARTERS[0], [U18, MON_FRI]), Cnt(months(2025, 1, 1), [A10_16, MON_FRI]),
         Cnt(months(2025, 2, 3), [A10_16], ["month"])], False),
    "own: three fields at once": (
        [Cnt(Y25, [U18, F, D3]), Cnt(Y25, [A10_16, F, D3, ALPHA_BETA]),
         Cnt(Y25, [A10_16, F, D3, GAMMA])], True),
    "own: four fields at once": (
        [Cnt(Y25, [U18, F, D3, NOT_NEAR]), Cnt(Y25, [A10_16, F, D3, ALPHA_BETA, NOT_NEAR]),
         Cnt(Y25, [A10_16, F, D3, GAMMA, NOT_NEAR])], True),
    # Changed by briefs/S3-R30-A-tests.md (C65 point 6d, named in C65's Tests): now refused. The
    # three counts' no-district figures give the 17-year-olds (female or no gender, no district)
    # once a record with neither a district nor a race is taken not to exist. It was False.
    "own: three fields, the last in another district (does not fit)": (
        [Cnt(Y25, [U18, F, D3]), Cnt(Y25, [A10_16, F, D3, ALPHA_BETA]),
         Cnt(Y25, [A10_16, F, D4, GAMMA])], True),
    "own: the labelled records alone, no value-figure needed": (
        [Cnt(Y25, [U18, in_("gender", "female", "male")]), Cnt(Y25, [A10_16, M]),
         Cnt(Y25, [A10_16, F])], True),
    "own: the second gender of another year (does not fit)": (
        [U18_25, Cnt(Y25, [A10_16, M]), Cnt(Y24, [A10_16, F])], False),
    "own: the youngest year, 10": ([Cnt(Y25), Cnt(H1, [age(11)]), Cnt(H2, [age(11)])], True),
    "own: 11 and over in two halves alone": ([Cnt(H1, [age(11)]), Cnt(H2, [age(11)])], False),
    "own: 16 to 18 less 16 to 17 by halves gives 18 (allowed)": (
        [Cnt(Y25, [age(16, 18)]), Cnt(H1, [age(16, 17)]), Cnt(H2, [age(16, 17)])], False),
    "own: 17 to 20 less 18 to 20 by halves gives 17": (
        [Cnt(Y25, [age(17, 20)]), Cnt(H1, [age(18, 20)]), Cnt(H2, [age(18, 20)])], True),
    "own: a band that ends at 18, less 17 to 18 by halves, gives 16": (
        [Cnt(Y25, [], ["age_band"]), Cnt(H1, [age(17, 18)]), Cnt(H2, [age(17, 18)])], True,
        band_source([[10, 15], [16, 18], [19, 98]])),
    "own: a band that ends at 18, less 16 to 17 by halves, gives 18 (allowed)": (
        [Cnt(Y25, [], ["age_band"]), Cnt(H1, [age(16, 17)]), Cnt(H2, [age(16, 17)])], False,
        band_source([[10, 15], [16, 18], [19, 98]])),
    "own: December left out (does not fit)": (
        [U18_25, Cnt(H1, [A10_16]), Cnt(months(2025, 7, 11), [A10_16])], False),
    "own: July in both parts (does not fit)": (
        [U18_25, Cnt(months(2025, 1, 7), [A10_16]), Cnt(H2, [A10_16])], False),
    "own: 1 July in neither part (does not fit)": (
        [U18_25, Cnt(dates("2025-01-01", "2025-06-30"), [A10_16]),
         Cnt(dates("2025-07-02", "2025-12-31"), [A10_16])], False),
    "own: the weekdays in two parts": (
        [U18_25, Cnt(Y25, [A10_16, weekdays("Monday", "Tuesday", "Wednesday")]),
         Cnt(Y25, [A10_16, weekdays("Thursday", "Friday", "Saturday", "Sunday")])], True),
    "own: two weekdays against a breakdown by weekday": (
        [Cnt(Y25, [U18, weekdays("Monday", "Tuesday")]), Cnt(Y25, [A10_16], ["weekday"])], True),
    "own: both ways of the school flag": (
        [U18_25, Cnt(Y25, [A10_16, NEAR]), Cnt(Y25, [A10_16, NOT_NEAR])], True),
    "own: two hours against a breakdown by hour": (
        [Cnt(Y25, [U18, hours(8, 9)]), Cnt(Y25, [A10_16], ["hour"])], True),
    "own: two years against two counts of a year": (
        [Cnt(years(2024, 2025), [U18]), Cnt(Y24, [A10_16]), Cnt(Y25, [A10_16])], True),
    "own: two months against a breakdown by month": (
        [Cnt(months(2025, 1, 2), [U18]), Cnt(Y25, [A10_16], ["month"])], True),
    "own: four counts, the last completes it": (
        [U18_25, Cnt(Y25, [age(10, 13)]), Cnt(H1, [age(14, 16)]), Cnt(H2, [age(14, 16)])], True),
    "own: four counts less the last": (
        [U18_25, Cnt(Y25, [age(10, 13)]), Cnt(H1, [age(14, 16)])], False),
    "own: a statistic and a count of part of its days": (
        [trend_10_16(), Cnt(H1, [U18])], True),
    "own: a statistic of 10 to 16 and an adult count": (
        [trend_10_16(), Cnt(Y25, [age(18, 24)])], False),
    "own: a statistic of district 3 and a count of district 5 (its filters do not narrow it)": (
        [trend_10_16(more=[D3]), Cnt(Y25, [U18, D5])], True),
    "own: the age filter of a share's part": (
        [Stat("shares", SINCE_2024, [], raw={"part": [age(10, 13)]}), Cnt(Y25, [age(10, 14)])],
        True),
    "own: the two age groups of a trend_compare": (
        [Stat("trend_compare", SINCE_2024, [age(10, 15)], raw={"versus": [age(16, 17)]}),
         Cnt(Y25, [A10_16])], True),
    "own: yes_no with under_18, and 10 to 16": (
        [Stat("yes_no", SINCE_2024, [], raw={"outcome": "under_18",
                                             "factors": [{"field": "gender", "is": "female"}]}),
         Cnt(Y25, [A10_16])], True),
    "own: yes_no with under_18 alone": (
        [Stat("yes_no", SINCE_2024, [], raw={"outcome": "under_18",
                                             "factors": [{"field": "gender", "is": "female"}]})],
        False),
    "own: yes_no with under_18, and 18 and over": (
        [Stat("yes_no", SINCE_2024, [], raw={"outcome": "under_18",
                                             "factors": [{"field": "gender", "is": "female"}]}),
         Cnt(Y25, [age(18)])], False),
    "own: the distribution by gender of 10 to 16, and under 18": (
        [Stat("distribution", SINCE_2024, [A10_16], raw={"by": "gender"}), U18_25], True),
    "own: a rate with no breakdown, and 10 to 16": (
        [Stat("rate", Y25, options=RATE), Cnt(Y25, [A10_16])], False),
    "own: a statistic of an older copy, a count of later days": (
        [trend_10_16(Y26, days=(FIRST_DAY, date(2026, 6, 30))),
         Cnt(dates("2026-07-01", "2026-09-17"), [U18])], False),
    "own: a statistic of an older copy, a count of its days": (
        [trend_10_16(Y26, days=(FIRST_DAY, date(2026, 6, 30))), Cnt(months(2026, 1, 3), [U18])],
        True),
}

# C62 point 5 with C65: the days of each figure's own copy (copy B ends on 28 September 2026).
COPY_CASES = {
    "under 18 on copy A, then 10 to 16 in 2026 on copy B (one step)":
        ([Cnt(Y26, [U18], days=DAYS_A), Cnt(Y26, [A10_16])], False),
    "and then 10 to 16 from 18 September 2026 (completes copy A's days)":
        ([Cnt(Y26, [U18], days=DAYS_A), Cnt(Y26, [A10_16]),
          Cnt(dates("2026-09-18", "2026-12-31"), [A10_16])], True),
    "both read with copy B (no days): as C21 has it":
        ([Cnt(Y26, [U18]), Cnt(Y26, [A10_16])], True),
}


def run_case(case):
    items, expected, *rest = case
    return decide(items, src=rest[0] if rest else None), expected


@pytest.mark.parametrize("name", list(FUNCTION_CASES))
def test_step3_one_year_under_18(name):
    """Step 3: each case's answer, as C65's words decide it (True: one single year of age under 18
    follows, and the request that completes it is refused)."""
    got, expected = run_case(FUNCTION_CASES[name])
    if expected == QUESTION_CASE:
        return
    assert got is expected, name


@pytest.mark.parametrize("name", list(COPY_CASES))
def test_step3_each_figure_with_its_own_copys_days(name):
    """Point 1, "each with the days of its own copy" (C62 point 5): with copy B (to 28 September
    2026), an earlier count of copy A (to 17 September) is read with its own days; the sum of two
    copy-B counts completes it."""
    items, expected = COPY_CASES[name]
    assert decide(items, newest=NEWEST_B) is expected, name


def test_step3_shown_figures_of_a_source_with_no_age_field():
    """Point 2 with C21's "a source with no age field": a statistic of such a source has nothing
    under 18, and the check says no. Made from arrests_like with its age field taken out."""
    src = source_json(A)
    src["fields"] = [f for f in src["fields"] if f["kind"] != "age"]
    assert decide([Stat("trend", SINCE_2024, raw={}), Cnt(Y25)], src=src) is False


# ==== step 4: the oracle ==========================================================================
# Two small worlds, SYNTHETIC: a source with ages 15 to 19 (bands 15-16, 17-18, 19), one category
# field `group` (group A, group B, and records with no value) and six days. Arm A: counts on six
# days, Monday 3 to Saturday 8 March 2025 (weekday filters and breakdowns). Arm B: counts and
# statistics; the six "days" are six parts of March 2025 (1-5, 6-10, ..., 26-31) inside a copy
# that ends on 30 April 2025, so a statistic of March reads the same days by R29-2's two readings.
# The oracle reads a checked spec itself (C21, C52, C54, C65) and decides with fractions on the
# whole table of cells (day, value, age); it uses no program code to decide.

W_ID = "FIXTURE:r29_world"
W_LABELS = ("group A", "group B")
W_VALUES = W_LABELS + (None,)
W_BANDS = ((15, 16), (17, 18), (19, 19))
A_DAYS = [date(2025, 3, 3) + timedelta(days=i) for i in range(6)]
B_PARTS = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 31)]
MARCH = {"year": 2025, "months": {"from": 3, "to": 3}}
AGE_PICKS = [None, (None, 17), (15, 16), (16, 17), (17, 18), (16, 18), (15, 18), (17, 19), (18, 19),
             (18, None), (19, None), (None, 16), (16, None), (15, 19)]


def world_source(start):
    return {"id": W_ID, "data_class": "COUNTY_OPEN_DATA",
            "title": "SYNTHETIC oracle world (made up for tests)",
            "unit": {"one": "record", "many": "records"}, "is_not": ["people"],
            "time_field": "event_date_time", "coverage_start": start.isoformat(), "floor": 10,
            "fields": [{"name": "id", "kind": "key"},
                       {"name": "age", "kind": "age", "usable": [15, 19],
                        "bands": [list(b) for b in W_BANDS]},
                       {"name": "group", "kind": "category", "dimension": "group",
                        "wording": "in {labels}", "values": {"A": "group A", "B": "group B"}}]}


def o_ages(filters):
    lo, hi = 15, 19
    for f in filters:
        if f["field"] == "age":
            lo, hi = max(lo, f.get("from", lo)), min(hi, f.get("to", hi))
    return tuple(range(lo, hi + 1))


def o_box(days, values, ages):
    return frozenset((d, v, a) for d in days for v in values for a in ages)


def o_count(spec, keys, weekday_of, c52=False):
    """C21's figures of a count with C52 and C54: the total; each group (a group of the field is
    the count of that value, a weekday group the count of those days, an age band group the band
    cut to the count's ages); the records with no value of the field when the count names it.
    With `c52`, C52 point 1 as age_figures has it: a filter that names every label is no filter
    for the figures (they hold the records with no value too); without, the records it keeps."""
    days = list(keys)
    labels = None
    for f in spec["filters"]:
        if f["field"] == "weekday":
            days = [d for d in days if weekday_of(d) in f["in"]]
        elif f["field"] == "group":
            labels = tuple(f["in"])
    values = labels if labels is not None else W_VALUES
    if c52 and labels is not None and set(labels) == set(W_LABELS):
        values = W_VALUES
    ages = o_ages(spec["filters"])
    figures = [o_box(days, values, ages)]
    parts = []
    for by in spec["group_by"]:
        if by == "group":
            parts.append([(None, (v,), None) for v in (labels or W_LABELS)])
        elif by == "weekday":
            parts.append([([d for d in days if weekday_of(d) == w], None, None) for w in WEEKDAYS])
        elif by == "age_band":
            parts.append([(None, None, tuple(a for a in ages if lo <= a <= hi))
                          for lo, hi in W_BANDS])
        else:  # month: every day of these worlds is in March 2025
            parts.append([(days, None, None)])
    for combo in (product(*parts) if parts else []):
        d, v, a = days, values, ages
        for pd, pv, pa in combo:
            d = d if pd is None else [x for x in d if x in pd]
            v = v if pv is None else tuple(x for x in v if x in pv)
            a = a if pa is None else tuple(x for x in a if x in pa)
        figures.append(o_box(d, v, a))
    if labels is not None or "group" in spec["group_by"]:
        figures.append(o_box(days, (None,), ages))
    return [f for f in figures if f]


def o_stat(spec, options, keys):
    """C65 point 2: a figure of each cell of its days (every value, with no value too, whatever its
    other filters) for each of its bands: its own age filter's (every usable age with none), any
    age filter of its options, and under 18 and 18 and over when it uses under_18."""
    bands = {o_ages(spec["filters"])}
    for key in ("versus", "part"):
        for f in options.get(key) or []:
            if f["field"] == "age":
                bands.add(o_ages([f]))
    items = [options.get("outcome")] + list(options.get("factors") or [])
    if any(isinstance(i, dict) and i.get("name") == "under_18" for i in items):
        bands |= {(15, 16, 17), (18, 19)}
    return [o_box([d], [v], band) for band in bands for d in keys for v in W_VALUES]


def o_reduce(row, basis):
    while row:
        p = min(row)
        if p not in basis:
            inv = row[p]
            basis[p] = {k: v / inv for k, v in row.items()}
            return
        factor, other = row[p], basis[p]
        for k, v in other.items():
            value = row.get(k, 0) - factor * v
            if value:
                row[k] = value
            else:
                row.pop(k, None)


def o_has_count_of_records(rows):
    """The narrower reading of R29-4: some sum of these rows (all in one year's cells, in echelon
    form) is 0 or 1 in every cell and not all 0. None when there are too many to try."""
    rows = [dict(r) for r in rows]
    for i in sorted(range(len(rows)), key=lambda i: -min(rows[i])):
        p = min(rows[i])
        for j in range(len(rows)):
            if j != i and rows[j].get(p):
                factor = rows[j][p]
                for k, v in rows[i].items():
                    value = rows[j].get(k, 0) - factor * v
                    if value:
                        rows[j][k] = value
                    else:
                        rows[j].pop(k, None)
    if len(rows) > 16:
        return None
    for mask in range(1, 1 << len(rows)):
        total = {}
        for i, r in enumerate(rows):
            if mask >> i & 1:
                for k, v in r.items():
                    total[k] = total.get(k, 0) + v
        if any(total.values()) and all(v in (0, 1) for v in total.values()):
            return True
    return False


def oracle(figures):
    """(wide, narrow): whether some sum of the figures lies in one single year of age under 18
    and is not zero (R29-4); and whether some such sum is the count of some of that year's
    records (None: not worked out)."""
    cells = sorted({c for f in figures for c in f}, key=repr)
    wide, narrow = False, False
    for y in (15, 16, 17):
        order = [c for c in cells if c[2] != y] + [c for c in cells if c[2] == y]
        first_y = sum(1 for c in cells if c[2] != y)
        index = {c: i for i, c in enumerate(order)}
        basis = {}
        for f in figures:
            o_reduce({index[c]: Fraction(1) for c in f}, basis)
        inside = [basis[p] for p in sorted(basis) if p >= first_y]
        if inside:
            wide = True
            if narrow is False:
                found = o_has_count_of_records(inside)
                narrow = None if found is None else found
    return wide, narrow


def a_count(rng):
    i = rng.randrange(6)
    j = rng.randrange(i, 6)
    roll = rng.random()
    period = ({"year": 2025} if roll < 0.15 else MARCH if roll < 0.25 else
              {"from": A_DAYS[i].isoformat(), "to": A_DAYS[j].isoformat()})
    filters = []
    pick = rng.choice(AGE_PICKS)
    if pick:
        filters.append({"field": "age", **({"from": pick[0]} if pick[0] else {}),
                        **({"to": pick[1]} if pick[1] else {})})
    labels = rng.choice([None, None, ["group A"], ["group B"], ["group A", "group B"]])
    if labels:
        filters.append({"field": "group", "in": labels})
    if rng.random() < 0.3:
        filters.append({"field": "weekday", "in": rng.sample(WEEKDAYS[:6], rng.randint(1, 5))})
    group_by = rng.sample(["group", "weekday", "age_band"], rng.choice([0, 0, 1, 1, 2]))
    return {"source": W_ID, "period": period, "filters": filters, "group_by": group_by}


def b_count(rng):
    i = rng.randrange(6)
    j = rng.randrange(i, 6)
    raw = {"source": W_ID, "period": {"from": date(2025, 3, B_PARTS[i][0]).isoformat(),
                                      "to": date(2025, 3, B_PARTS[j][1]).isoformat()},
           "filters": [], "group_by": rng.sample(["group", "age_band"], rng.choice([0, 0, 1, 2]))}
    pick = rng.choice(AGE_PICKS)
    if pick:
        raw["filters"].append({"field": "age", **({"from": pick[0]} if pick[0] else {}),
                               **({"to": pick[1]} if pick[1] else {})})
    labels = rng.choice([None, None, ["group A"], ["group B"], ["group A", "group B"]])
    if labels:
        raw["filters"].append({"field": "group", "in": labels})
    return raw


def b_stat(rng):
    """A statistic of March 2025: (kind, filters, raw options)."""
    def age_filter():
        pick = rng.choice(AGE_PICKS)
        return [] if not pick else [{"field": "age", **({"from": pick[0]} if pick[0] else {}),
                                     **({"to": pick[1]} if pick[1] else {})}]
    group = [] if rng.random() < 0.6 else [{"field": "group", "in": [rng.choice(W_LABELS)]}]
    kind = rng.choice(["trend", "timing", "distribution", "shares", "trend_compare", "yes_no"])
    if kind in ("trend", "timing"):
        return kind, age_filter() + group, {}
    if kind == "distribution":
        return kind, age_filter() + group, {"by": rng.choice([None, "group"])}
    if kind == "shares":
        part = age_filter() or [{"field": "group", "in": ["group A"]}]
        return kind, ([] if part[0]["field"] == "group" else group), {"part": part}
    if kind == "trend_compare":
        if rng.random() < 0.5:
            lo = rng.choice([15, 16, 17, 18])
            return kind, [{"field": "age", "from": 15, "to": lo}], \
                {"versus": [{"field": "age", "from": lo + 1, "to": 19}]}
        shared = age_filter()
        return kind, shared + [{"field": "group", "in": ["group A"]}], \
            {"versus": shared + [{"field": "group", "in": ["group B"]}]}
    items = ["under_18", {"field": "group", "is": "group A"}]
    rng.shuffle(items)
    return kind, [], {"outcome": items[0], "factors": [items[1]]}


def arm_a(seed):
    """One set of two to six counts of arm A: (program's answer, oracle's (wide, narrow), case)."""
    rng = random.Random(seed)
    counting = mod("counting")
    src, copy = world_source(A_DAYS[0]), fcopy(A_DAYS[-1], W_ID)
    specs, days, figures, figures_c52, case = [], [], [], [], []
    n = rng.randint(2, 6)
    while len(specs) < n:
        raw = a_count(rng)
        try:
            s = counting.check_spec(src, copy, raw)
        except counting.SpecError:
            continue
        own = (A_DAYS[0], A_DAYS[rng.randrange(2, 6)]) if rng.random() < 0.2 else None
        first, last = own or (A_DAYS[0], A_DAYS[-1])
        keys = [d for d in A_DAYS if first <= d <= last and in_period(d, s["period"])]
        figures += o_count(s, keys, lambda d: WEEKDAYS[d.weekday()])
        figures_c52 += o_count(s, keys, lambda d: WEEKDAYS[d.weekday()], c52=True)
        specs.append(s)
        days.append(own)
        case.append({"spec": s, "days": own and [d.isoformat() for d in own]})
    kw = {"days": days} if any(days) else {}
    got = bool(counting.one_year_under_18(src, specs, copy, **kw))
    return got, (oracle(figures), oracle(figures_c52)), case


def arm_b(seed):
    """One set of two to six counts and statistics of arm B."""
    rng = random.Random(10_000 + seed)
    counting, stats = mod("counting"), mod("stats")
    start, newest = date(2025, 3, 1), date(2025, 4, 30)
    src, copy = world_source(start), fcopy(newest, W_ID)
    specs, shown, figures, figures_c52, case = [], [], [], [], []
    n = rng.randint(2, 6)
    while len(case) < n:
        if rng.random() < 0.4:
            kind, filters, raw = b_stat(rng)
            try:
                s = counting.check_spec(src, copy, {"source": W_ID, "period": MARCH,
                                                    "filters": filters, "group_by": []})
                options = stats.check_options(src, s, kind, raw)
            except counting.SpecError:
                continue
            shown.extend(counting.shown_figures(src, s, options, start, newest))
            figures += o_stat(s, options, range(6))
            figures_c52 += o_stat(s, options, range(6))
            case.append({"statistic": kind, "spec": s, "options": options})
            continue
        try:
            s = counting.check_spec(src, copy, b_count(rng))
        except counting.SpecError:
            continue
        lo, hi = date.fromisoformat(s["period"]["from"]), date.fromisoformat(s["period"]["to"])
        keys = [k for k, (a, b) in enumerate(B_PARTS) if lo.day <= a and b <= hi.day]
        figures += o_count(s, keys, lambda k: None)
        figures_c52 += o_count(s, keys, lambda k: None, c52=True)
        specs.append(s)
        case.append({"spec": s})
    kw = {"shown": shown} if any("statistic" in c for c in case) else {}
    got = bool(counting.one_year_under_18(src, specs, copy, **kw))
    return got, (oracle(figures), oracle(figures_c52)), case


SEEDS = range(520)


def accepted(answers):
    """The answers a reading allows: (wide, narrow) of R29-4, narrow None when not worked out."""
    wide, narrow = answers
    return {wide} if narrow is None else {wide, narrow}


def compare_arm(arm):
    """Every seed: the program's answer against the oracle's. The oracle gives one answer per
    reading: R29-4's two (wide, narrow) and R29-11's two (the records an every-label filter keeps,
    or C52 point 1's no filter). Where they all agree the program must give that answer; where
    they differ, any of them is accepted and the set is counted as open."""
    wrong, open_cases, yes = [], [], 0
    for seed in SEEDS:
        got, (exact, c52), case = arm(seed)
        yes += exact[0]
        allowed = accepted(exact) | accepted(c52)
        if len(allowed) > 1:
            open_cases.append((seed, exact, c52))
        if got not in allowed:
            wrong.append((len(json.dumps(case, default=str)), seed, got, exact, case))
    return sorted(wrong, key=lambda w: w[0]), open_cases, yes


@pytest.mark.parametrize("arm", [arm_a, arm_b], ids=["arm A, counts", "arm B, with statistics"])
def test_step4_the_oracle_against_the_program(arm):
    """Step 4: 520 seeded sets of two to six figures; the program's function gives the oracle's
    answer for every one. A failure names the smallest disagreeing case."""
    wrong, open_cases, yes = compare_arm(arm)
    assert 0.2 * len(SEEDS) < yes < 0.8 * len(SEEDS), f"premise: a mix of answers ({yes} yes)"
    assert not wrong, (f"{len(wrong)} of {len(SEEDS)} sets disagree with the oracle; the smallest: "
                       f"seed {wrong[0][1]}, program {wrong[0][2]}, oracle {wrong[0][3]}: "
                       f"{json.dumps(wrong[0][4], default=str)}")


def w_spec(period, filters=(), group_by=()):
    src, copy = world_source(A_DAYS[0]), fcopy(A_DAYS[-1], W_ID)
    return mod("counting").check_spec(src, copy, {"source": W_ID, "period": period,
                                                  "filters": list(filters),
                                                  "group_by": list(group_by)})


def o_of(specs):
    figures = []
    for s in specs:
        keys = [d for d in A_DAYS if in_period(d, s["period"])]
        figures += o_count(s, keys, lambda d: WEEKDAYS[d.weekday()])
    return oracle(figures)


W_U18 = {"field": "age", "to": 17}
W_15_16 = {"field": "age", "from": 15, "to": 16}
ORACLE_SELF = {  # the oracle on C65's own examples, in the small world: (specs, (wide, narrow))
    "under 18, then 15 to 16 of the first three days": (
        [(MARCH, [W_U18]), (dates("2025-03-03", "2025-03-05"), [W_15_16])], (False, False)),
    "and of the last three": (
        [(MARCH, [W_U18]), (dates("2025-03-03", "2025-03-05"), [W_15_16]),
         (dates("2025-03-06", "2025-03-08"), [W_15_16])], (True, True)),
    "group A, then group B, with the no-value figure": (
        [(MARCH, [W_U18]), (MARCH, [W_15_16, {"field": "group", "in": ["group A"]}]),
         (MARCH, [W_15_16, {"field": "group", "in": ["group B"]}])], (True, True)),
    "the two readings differ: days 1-2 and 2-3 of 15 to 17, days 1-3 and day 2 of 15 to 16": (
        [(dates("2025-03-03", "2025-03-04"), [W_U18]), (dates("2025-03-04", "2025-03-05"), [W_U18]),
         (dates("2025-03-03", "2025-03-05"), [W_15_16]), (dates("2025-03-04", "2025-03-04"),
                                                          [W_15_16])], (True, False)),
}


@pytest.mark.parametrize("name", list(ORACLE_SELF))
def test_step4_the_oracle_on_c65s_examples(name):
    """The oracle itself, on C65's examples written in the small world, and on the smallest case
    where R29-4's two readings differ. Uses no program code to decide; passes today."""
    specs, expected = ORACLE_SELF[name]
    assert o_of([w_spec(p, f) for p, f in specs]) == expected, name


# ==== step 5: county turns =======================================================================

def ask_counts(env, specs, question="a message", **kw):
    return turn(env, specs, question, **kw)


def assert_refused_end(env, reply, before, sentence=NEW_SENTENCE):
    """A turn whose only request was refused by the check: UNSUPPORTED, NOT_ALLOWED, C62 point 2's
    sentence (or the old row when the cause is the message's own figures), nothing saved."""
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.text == sentence, reply.text
    assert reply.run_ids == [] and reply.results == [], reply.results
    assert len(manifests(env.runs_dir)) == before, "a record was saved for the refused request"


P21_HALVES = [(spec(Y25, [U18]), "how many arrests of people under 18 were there in 2025?"),
              (spec(H1, [A10_16]), "how many arrests of people aged 10 to 16 from January to "
                                   "June 2025?"),
              (spec(H2, [A10_16]), "and from July to December 2025?")]
P21_GENDERS = [(spec(Y25, [U18]), "how many arrests of people under 18 were there in 2025?"),
               (spec(Y25, [A10_16, M]), "how many arrests of males aged 10 to 16 in 2025?"),
               (spec(Y25, [A10_16, F]), "and of females aged 10 to 16 in 2025?")]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("thread", ["halves", "genders"])
def test_p21_each_way_ends_with_its_last_step_refused(tmp_path, monkeypatch, thread, talk):
    """C65's test, point 1, thread P21: under 18 in 2025 (answered), then 10 to 16 of one half (of
    one gender) (answered: one step of a sum), then of the other: NOT_ALLOWED with C21's `why` and
    C61's sentence, the reply C62 point 2's sentence, nothing counted. Talk off and on."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    steps = P21_HALVES if thread == "halves" else P21_GENDERS
    for s, question in steps[:2]:
        reply, answers = ask_counts(env, [s], question)
        assert_answered(reply, answers)
        assert line1(reply) == f"I counted {phrase(s)}.", reply.text
    s, question = steps[2]
    reply, (answer,) = ask_counts(env, [s], question)
    assert_refused(answer)
    assert_refused_end(env, reply, before=2)


@pytest.mark.parametrize("talk", TALK)
def test_p21_the_halves_the_other_way_round(tmp_path, monkeypatch, talk):
    """C65 point 1, "in both orders": the two halves of 10 to 16 (both answered), then under 18 in
    2025: refused with the sentence."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    for s, question in P21_HALVES[1:]:
        reply, answers = ask_counts(env, [s], question)
        assert_answered(reply, answers)
    reply, (answer,) = ask_counts(env, [P21_HALVES[0][0]], P21_HALVES[0][1])
    assert_refused(answer)
    assert_refused_end(env, reply, before=2)


@pytest.mark.parametrize("talk", TALK)
def test_p21_the_last_step_with_another_count_made(tmp_path, monkeypatch, talk):
    """C65's Tests, "C64 point 3a's line when another count of the message was made": the second
    half and 30 to 40 in 2024 in one message: the half refused with the sentence in its `why`, 2024
    counted, the turn ANSWERED; C64's line at most once (R29-10)."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    for s, question in P21_HALVES[:2]:
        reply, answers = ask_counts(env, [s], question)
        assert_answered(reply, answers)
    reply = env.ask("and from July to December 2025, and all of 2024?",
                    Step(call_of(spec(H2, [A10_16])), call_of(spec(Y24, [age(30, 40)]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_refused(env.model.answer(0, 0))
    assert env.model.answer(0, 1).get("result_id") == "r1", env.model.answer(0, 1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y24, [age(30, 40)]))}.", reply.text
    assert reply.text.count(C64_LINE_A) <= 1, reply.text


@pytest.mark.parametrize("last", ["by month", "by district"])
def test_p21_the_later_steps_are_refused_as_today(tmp_path, monkeypatch, last):
    """P21's last two messages, after under 18 in 2025: 10 to 16 in 2025 by month, by district.
    Their totals are of the kind of under 18 in 2025, so C21 refuses them today. Passes today;
    must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = ask_counts(env, [spec(Y25, [U18])], P21_HALVES[0][1])
    assert_answered(reply, answers)
    by = "month" if last == "by month" else "district"
    reply, (answer,) = ask_counts(env, [spec(Y25, [A10_16], [by])], f"arrests of 10 to 16, {last}")
    assert_refused(answer)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text


@pytest.mark.parametrize("pair", ["two years", "a district, then no district filter"])
def test_counts_that_cannot_be_combined_are_both_answered(tmp_path, monkeypatch, pair):
    """C65's test, point 1: counts that cannot be combined are both answered: under 18 in 2024 and
    10 to 16 in 2025; under 18 in district 3 and 10 to 16 with no district filter (R29-6; the
    second message clears the district that C9 would keep)."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, second = ((spec(Y24, [U18]), spec(Y25, [A10_16])) if pair == "two years" else
                     (spec(Y25, [U18, D3]), spec(Y25, [A10_16, clear("district")])))
    for s in (first, second):
        reply, answers = ask_counts(env, [s])
        assert_answered(reply, answers)


def test_c65s_district_example_either_reading(tmp_path, monkeypatch):
    """R29-6: under 18 in district 3, then 10 to 16 in district 5: answered (C65's Tests) or
    refused with C21's `why` and C61's sentence (C52 point 4). Both accepted."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = ask_counts(env, [spec(Y25, [U18, D3])])
    assert_answered(reply, answers)
    reply, (answer,) = ask_counts(env, [spec(Y25, [A10_16, D5])])
    if "error" in answer:
        assert_refused(answer)
    else:
        assert_answered(reply, [answer])


def test_four_quarters_and_two_ranges_of_hours(tmp_path, monkeypatch):
    """C65's tests, point 1: under 18 in 2025, then 10 to 16 in each quarter: the first three
    answered, the fourth refused; in another thread, hours 0 to 11 answered, 12 to 23 refused."""
    env = CountyEnv(tmp_path, monkeypatch)
    for thread, parts in ((THREAD_1, [spec(q, [A10_16]) for q in QUARTERS]),
                          (THREAD_2, [spec(Y25, [A10_16, hours(0, 11)]),
                                      spec(Y25, [A10_16, hours(12, 23)])])):
        reply, answers = ask_counts(env, [spec(Y25, [U18])], thread_key=thread)
        assert_answered(reply, answers)
        for s in parts[:-1]:
            reply, answers = ask_counts(env, [s], thread_key=thread)
            assert_answered(reply, answers)
        reply, (answer,) = ask_counts(env, [parts[-1]], thread_key=thread)
        assert_refused(answer)
        assert reply.text == NEW_SENTENCE, reply.text


def test_a_copy_that_changes_between_the_messages(tmp_path, monkeypatch):
    """C65's test, point 1, "a copy that changes between the messages (the days of each figure's
    own copy)": under 18 in 2026 on copy A (to 17 September); copy B comes (to 28 September); 10 to
    16 in 2026 is answered (another set of days); 10 to 16 from 18 September 2026 is refused: with
    the count before it, it gives 10 to 16 of copy A's days, and so the 17-year-olds."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = ask_counts(env, [spec(Y26, [U18])], "how many under 18 in 2026?")
    assert_answered(reply, answers)
    refresh(env)
    reply, answers = ask_counts(env, [spec(Y26, [A10_16])], "and 10 to 16 in 2026?")
    assert_answered(reply, answers)
    reply, (answer,) = ask_counts(env, [spec(dates("2026-09-18", "2026-12-31"), [A10_16])],
                                  "and 10 to 16 from 18 September 2026?")
    assert_refused(answer)
    assert reply.text == NEW_SENTENCE, reply.text


@pytest.mark.parametrize("order", ["arrests first", "juvenile records first"])
def test_another_sources_figures_are_never_read_in(tmp_path, monkeypatch, order):
    """C65's test, point 1, and C54 point 4: test_s3_c54.py's juvenile-like source (its age field
    also `age`, usable 10 to 17). Under 18 of one source, then 10 to 16 from January to June and
    from July to December of the other: all answered."""
    env = two_sources(tmp_path, monkeypatch)
    first, other = (A, J) if order == "arrests first" else (J, A)
    for s in (spec(Y25, [U18], name=first), spec(H1, [A10_16], name=other),
              spec(H2, [A10_16], name=other)):
        reply, answers = ask_counts(env, [s])
        assert_answered(reply, answers)
        assert reply.results[0]["spec"]["source"] == SIDS[s["name"]]


# ---- statistics refused before anything is computed (no R needed) ----------------------------

def analyze(kind, period, filters=(), options=None, source=A_ID):
    arguments = {"kind": kind, "source": source, "period": period, "filters": list(filters)}
    if options is not None:
        arguments["options"] = options
    return call("analyze", arguments)


def spy_runs(monkeypatch):
    """Records every call that computes a statistic or a rate (each still does its work)."""
    calls = []
    for module, name in (("stats", "prepare"), ("stats", "run_r"), ("stats", "write_job"),
                         ("rates", "count")):
        real = getattr(mod(module), name)

        def spy(*args, _real=real, _name=f"{module}.{name}", **kwargs):
            calls.append(_name)
            return _real(*args, **kwargs)
        monkeypatch.setattr(mod(module), name, spy)
    return calls


def nothing_run(env, calls):
    assert calls == [], f"computed for a refused statistic: {calls}"
    assert not list(env.runs_dir.rglob("job.json")), "a job folder was made"


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("kind", list(KIND_CASES))
def test_p2_each_kind_after_under_18_is_refused_before_anything_is_computed(tmp_path, monkeypatch,
                                                                            kind, talk):
    """C65's test, point 2: for each kind of statistic, an age filter of 10 to 16 after an answered
    count of under 18 in 2025 (days it shares: 2024 to the copy's end): NOT_ALLOWED, the age field,
    C21's `why` with C61's sentence (R29-7); nothing computed, no job folder, no record; the turn
    ends with C62 point 2's sentence.
    Changed by briefs/S3-R31-A-tests.md (C65 point 8), [distribution-off] and [distribution-on]
    only: a distribution of ages 10 to 16 is now refused on its own (its last bar is the
    16-year-olds alone), so its `why` is C21's alone and the reply the NOT_ALLOWED row
    (OLD_SENTENCE), nothing computed; before, C61's sentence and C62 point 2's sentence. The
    test's first point is kept with a distribution point 8 allows: in a second thread, ages 10 to
    16 in 2025 (answered), then the distribution of under 18: refused with C61's sentence and C62
    point 2's sentence, nothing computed."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply, answers = ask_counts(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(reply, answers)
    calls = spy_runs(monkeypatch)
    filters, options = KIND_CASES[kind]
    reply = env.ask("and the same for ages 10 to 16?", Step(analyze(kind, SINCE_2024, filters,
                                                                    options)),
                    Step(finish("finding", "I found that.")))
    if kind == "distribution":  # C65 point 8 (briefs/S3-R31-A-tests.md)
        assert_refused(env.model.answer(0), why=WHY)
        nothing_run(env, calls)
        assert_refused_end(env, reply, before=1, sentence=OLD_SENTENCE)
        reply, answers = ask_counts(env, [spec(Y25, [A10_16])], "how many aged 10 to 16 in 2025?",
                                    thread_key=THREAD_2)
        assert_answered(reply, answers)
        reply = env.ask("and how old are the people under 18?",
                        Step(analyze(kind, SINCE_2024, [U18], options)),
                        Step(finish("finding", "I found that.")), thread_key=THREAD_2)
        assert_refused(env.model.answer(0))
        nothing_run(env, calls)
        assert_refused_end(env, reply, before=2)
        return
    assert_refused(env.model.answer(0))
    nothing_run(env, calls)
    assert_refused_end(env, reply, before=1)


@pytest.mark.parametrize("talk", TALK)
def test_p20_the_trend_after_under_18_is_refused_before_anything_is_computed(tmp_path, monkeypatch,
                                                                             talk):
    """C65's test, point 1 (P20, "the trend after the count"): under 18 in 2025, then "are arrests
    of people aged 10 to 16 going up or down since 2021?": the trend of 10 to 16 over the whole
    copy is refused, R not started."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply, answers = ask_counts(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(reply, answers)
    calls = spy_runs(monkeypatch)
    reply = env.ask("are arrests of people aged 10 to 16 going up or down since 2021?",
                    Step(analyze("trend", SINCE_2024, [A10_16])), Step(finish("finding", "ok.")))
    assert_refused(env.model.answer(0))
    nothing_run(env, calls)
    assert_refused_end(env, reply, before=1)


def test_p2_a_statistic_with_the_count_of_the_same_message(tmp_path, monkeypatch):
    """Point 2a, "with those of the message": under 18 in 2025 and the trend of 10 to 16 in one
    message: the count answered, the trend refused with C21's `why` alone (the cause is this
    message's own figures), nothing computed; the turn ends ANSWERED with the count."""
    env = CountyEnv(tmp_path, monkeypatch)
    calls = spy_runs(monkeypatch)
    reply = env.ask("under 18 in 2025, and is 10 to 16 going up?",
                    Step(call_of(spec(Y25, [U18])), analyze("trend", SINCE_2024, [A10_16])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0, 0).get("result_id") == "r1", env.model.answer(0, 0)
    assert_refused(env.model.answer(0, 1), why=WHY)
    nothing_run(env, calls)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, [U18]))}.", reply.text


def test_p2_a_part_of_10_to_16_of_a_whole_under_18_on_its_own(tmp_path, monkeypatch):
    """C65's test, point 2: shares of the records under 18 in 2025 whose part is 10 to 16, as the
    first message of a thread: refused (NOT_ALLOWED by the check, or BAD_OPTIONS by S13.5, which
    refuses a part that filters a field the filters limit: both accepted), nothing computed."""
    env = CountyEnv(tmp_path, monkeypatch)
    calls = spy_runs(monkeypatch)
    reply = env.ask("among arrests of people under 18 in 2025, what share were aged 10 to 16?",
                    Step(analyze("shares", Y25, [U18], {"part": [A10_16]})),
                    Step(finish("finding", "ok.")))
    answer = env.model.answer(0)
    assert answer.get("error") in ("NOT_ALLOWED", "BAD_OPTIONS"), answer
    if answer["error"] == "NOT_ALLOWED":
        assert answer.get("why") == WHY, answer
    nothing_run(env, calls)
    assert reply.status == "UNSUPPORTED" and reply.run_ids == [], (reply.status, reply.text)


def test_p2_a_rate_with_an_age_filter_after_under_18(tmp_path, monkeypatch):
    """R29-8: a rate of 10 to 16 in 2025 after under 18 in 2025 (arrests_like is marked for rates in
    this test): NOT_ALLOWED or BAD_OPTIONS, nothing computed, no Census copy needed to say so."""
    env = CountyEnv(tmp_path, monkeypatch, change={A: lambda s: s.update(rates=True)})
    reply, answers = ask_counts(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(reply, answers)
    calls = spy_runs(monkeypatch)
    reply = env.ask("what is the arrest rate per 10,000 residents for people aged 10 to 16 in 2025?",
                    Step(analyze("rate", Y25, [A10_16])), Step(finish("finding", "ok.")))
    answer = env.model.answer(0)
    assert answer.get("error") in ("NOT_ALLOWED", "BAD_OPTIONS"), answer
    nothing_run(env, calls)
    assert reply.status == "UNSUPPORTED" and reply.run_ids == [], (reply.status, reply.text)


# ---- a remembered statistic (stored as the program stores it) ------------------------------------

def remember_statistic(env, statistic, thread_key=THREAD_1):
    """Makes the thread's last turn hold `statistic` as its one result (an analysis as remember()
    keeps it: id, kind, stat, spec, options, read_as, run_id, and `days` when given). The turn is a
    real answered count turn first; only its results are replaced."""
    reply, answers = ask_counts(env, [spec(Y24, [age(30, 40)])], "a message",
                                thread_key=thread_key)
    assert_answered(reply, answers)
    db = sqlite3.connect(env.tmp_path / "agent.db")
    try:
        row_id, text = db.execute("SELECT id, record FROM agent_turns WHERE thread_key = ? "
                                  "ORDER BY id DESC LIMIT 1", (thread_key,)).fetchone()
        record = json.loads(text)
        record["results"] = [statistic]
        db.execute("UPDATE agent_turns SET record = ? WHERE id = ?", (json.dumps(record), row_id))
        db.commit()
    finally:
        db.close()


def stored_trend(days=None, period=SINCE_2024, source=A_ID):
    s = {"source": source, "period": period, "filters": [A10_16], "group_by": []}
    out = {"id": "a1", "kind": "analysis", "stat": "trend", "spec": s, "options": {},
           "read_as": "SYNTHETIC trend of arrest records aged 10 to 16", "run_id": "R29-NO-RUN"}
    if days is not None:
        out["days"] = days
    return out


@pytest.mark.parametrize("days, refused", [
    (None, True),
    (["2024-01-01", "2024-12-31"], False),
    (["2024-01-01", "2026-09-17"], True),
], ids=["no days: this copy", "days of an older copy, to 2024", "days of this copy"])
def test_p2c_a_remembered_statistic_is_read_with_its_days(tmp_path, monkeypatch, days, refused):
    """Point 2c and 2b: an answered earlier turn holds the trend of 10 to 16 over 2024 to the copy's
    end. With no `days` it is read with this message's copy: under 18 in 2025 is refused with the
    sentence. With the days of a copy that ended in 2024 it does not reach 2025: answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    remember_statistic(env, stored_trend(days))
    reply, answers = ask_counts(env, [spec(Y25, [U18])], P05_FIRST)
    if refused:
        assert_refused(answers[0])
        assert reply.text == NEW_SENTENCE, reply.text
    else:
        assert_answered(reply, answers)


@pytest.mark.parametrize("order", ["arrests' statistic", "juvenile records' statistic"])
def test_p2_another_sources_statistic_is_never_read_in(tmp_path, monkeypatch, order):
    """C65's test, point 1 ("another source's figures are never read in") for a statistic: a
    remembered trend of 10 to 16 of one source, then under 18 in 2025 of the other: answered. The
    same source's count is refused (the premise that the statistic is read at all)."""
    env = two_sources(tmp_path, monkeypatch)
    own, other = (A, J) if order == "arrests' statistic" else (J, A)
    remember_statistic(env, stored_trend(source=SIDS[own], period=Y25))
    reply, answers = ask_counts(env, [spec(Y25, [U18], name=other)])
    assert_answered(reply, answers)
    reply, answers = ask_counts(env, [spec(Y25, [U18], name=own)])
    assert_refused(answers[0])


def test_p2_a_statistic_of_a_turn_that_did_not_end_answered_is_not_read(tmp_path, monkeypatch):
    """Point 1, "the thread's ANSWERED turns": the same remembered trend in a turn that ended
    NEEDS_INPUT is not read: under 18 in 2025 is answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    remember_statistic(env, stored_trend())
    db = sqlite3.connect(env.tmp_path / "agent.db")
    try:
        db.execute("UPDATE agent_turns SET status = 'NEEDS_INPUT'")
        db.commit()
    finally:
        db.close()
    reply, answers = ask_counts(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(reply, answers)


# ---- SYNTHETIC mode ------------------------------------------------------------------------------

def test_synthetic_mode_three_turns_are_exactly_as_today(tmp_path):
    """C65 is county mode only: the three recorded SYNTHETIC turns give exactly what they gave
    before stage 3 (tests/s3/fixtures/synthetic_today.json). Passes today; must still pass."""
    assert_same_as_today(synthetic_three_turns(tmp_path))


# ==== step 5b: points 4 and 5, through Slack and the store =========================================

class Talk:
    """process_event with the real agent of a CountyEnv (its model stand-in set per message)."""

    def __init__(self, env):
        self.env, self.slack, self.n, self.replies = env, FakeSlack(), 0, []

    def send(self, text, *steps, dm=False, now=None, user=USER, thread=True):
        self.n += 1
        if steps:
            self.env.model = FakeModel(*steps, clock=self.env.clock)
        ts = f"1762791{self.n:03d}.000{self.n:03d}"
        now = now or NOW_S3 + timedelta(minutes=self.n)
        if dm:
            event = direct_message(text, ts=ts, user=user)
        elif self.n == 1:
            event = mention(f"<@{AGENT_USER}> {text}", ts=ROOT_TS, user=user)
        else:
            event = mention(f"<@{AGENT_USER}> {text}", ts=ts, thread_ts=ROOT_TS, user=user)

        def agent(question, thread_key, user_id, memory_minutes=None):
            reply = self.env.ask(question, model=self.env.model, thread_key=thread_key,
                                 user_id=user_id, memory_minutes=memory_minutes, now=now)
            self.replies.append(reply)
            return reply
        label = process(event, settings=self.env.settings, store=self.env.store, agent=agent,
                        slack=self.slack, event_id=f"EvR29{self.n:06d}", now=now)
        return label, (self.replies[-1] if label not in ("reset", "duplicate") else None)

    def count(self, s, text, **kw):
        return self.send(text, Step(call_of(s)), Step(finish("finding", "I counted {r1.count}.")),
                         **kw)


def slack_env(tmp_path, monkeypatch, **values):
    return CountyEnv(tmp_path, monkeypatch, **SLACK, **values)


def given(env, thread_key=THREAD_1):
    return env.store.given_before_reset(thread_key, 5000)


def plain(value):
    return json.loads(json.dumps(value, default=str))


def holds(value, target):
    """`target` is somewhere in `value`, as it is or as a JSON text (R29-9)."""
    if value == target:
        return True
    if isinstance(value, str) and value[:1] in "[{":
        try:
            return holds(json.loads(value), target)
        except ValueError:
            return False
    if isinstance(value, dict):
        return any(holds(v, target) for v in value.values())
    if isinstance(value, list):
        return any(holds(v, target) for v in value)
    return False


def store_cells(env):
    """Every value of every row of every table of the store, as text: (table, text)."""
    db = sqlite3.connect(env.tmp_path / "agent.db")
    try:
        tables = [t for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return [(t, str(cell)) for t in tables for row in db.execute(f"SELECT * FROM {t}")
                for cell in row]
    finally:
        db.close()


Q_U18 = "how many arrests of people under 18 were there in 2025?"
Q_10_16 = "and how many aged 10 to 16 in 2025?"


@pytest.mark.parametrize("talk", TALK)
def test_p4_under_18_reset_then_10_to_16_is_refused(tmp_path, monkeypatch, talk):
    """C65's test, point 4: under 18, `reset`, ages 10 to 16, in one Slack thread: `reset` posts
    point 4's reply and calls no model; 10 to 16 is refused with C62 point 2's sentence."""
    env = slack_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    talk_ = Talk(env)
    label, first = talk_.count(spec(Y25, [U18]), Q_U18)
    assert label == "answered", (label, first and first.text)
    label, _ = talk_.send("reset")
    assert label == "reset"
    assert talk_.slack.log[-1] == ("post", "CTEST0001", ROOT_TS, C65_RESET_LINE), talk_.slack.log[-1]
    label, reply = talk_.count(spec(Y25, [A10_16]), Q_10_16)
    assert_refused(env.model.answer(0))
    assert (label, reply.text) == ("refused", NEW_SENTENCE), (label, reply.text)
    assert talk_.slack.log[-1][3] == NEW_SENTENCE


def test_p4_the_stripped_records_hold_only_what_point_4_names(tmp_path, monkeypatch):
    """C65's test, point 4: after `reset` the stripped records (Store.given_before_reset) hold, for
    each answered turn with a count, the count's spec and days; no question, no `sent`, no user id,
    no run id, no read_as, no turn id; and no table of the store holds the questions or the replies
    any more. A turn with no count (a talk turn) and a refused turn leave nothing."""
    env = slack_env(tmp_path, monkeypatch)
    talk_ = Talk(env)
    _, first = talk_.count(spec(Y25, [U18, D3]), "how many under 18 in district 3 in 2025?")
    _, second = talk_.count(spec(H1, [A10_16]), "and 10 to 16 from January to June?", user=USER2)
    _, refused = talk_.count(spec(Y25, [U17, D3]), "and under 17 in district 3?")
    assert refused.status == "UNSUPPORTED", refused.text
    turns = env.store.recent_turns(THREAD_1, 100)
    specs = [r["spec"] for t in turns if t["status"] == "ANSWERED" for r in t["results"]]
    sent = [t.get("sent") for t in turns]
    run_ids = first.run_ids + second.run_ids
    read_as = [r["read_as"] for t in turns for r in t.get("results") or []]
    questions = [t["question"] for t in turns]
    talk_.send("reset")
    kept = plain(given(env))
    for s in specs:
        assert holds(kept, s), f"the spec {s} is not kept"
    assert holds(kept, [FIRST_DAY.isoformat(), NEWEST_A.isoformat()]), "no days kept"
    text = json.dumps(kept)
    for word in [*questions, *sent, *run_ids, *read_as, USER, USER2, first.turn_id,
                 second.turn_id]:
        assert word and word not in text, f"kept after reset: {word!r}"
    assert "ANSWERED" in text, "the status of each kept turn"
    for table, cell in store_cells(env):
        for word in [*questions, *sent]:
            assert word not in cell, f"{table} still holds {word!r}"
        if table != "user_requests":  # who asked when, for the per-person limit (A13 step 7)
            assert USER not in cell and USER2 not in cell, f"{table} holds a user id"


def test_p4_after_reset_the_thread_is_empty_for_everything_but_the_check(tmp_path, monkeypatch):
    """C65's test, point 4: after `reset` the model's thread block is empty, `details` finds no
    answer, no filter is kept (a count with no period asks for it, as in a new thread), and the
    notices are shown in full again (the about reply is that of a new thread)."""
    env = slack_env(tmp_path, monkeypatch)
    talk_ = Talk(env)
    talk_.send("what data do you have?", Step(describe()),
               Step(finish("about_data", "Here is what I know. {f1}.")))
    first_about = talk_.replies[-1].text
    talk_.count(spec(Y25, [U18, D3]), "how many under 18 in district 3 in 2025?")
    talk_.send("reset")
    label, reply = talk_.send("details", Step(show_details()))
    assert thread_block(env.model.calls[0]["messages"]) is None, "the model was shown the thread"
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NO_PREVIOUS_ANSWER"), reply.text
    no_period = count(A_ID, filters=[A10_16])
    label, reply = talk_.send("and 10 to 16?", Step(no_period), Step(finish("finding", "ok.")))
    twin = env.ask("and 10 to 16?", Step(no_period), Step(finish("finding", "ok.")),
                   thread_key=THREAD_2)
    assert (reply.status, reply.text) == (twin.status, twin.text) and reply.status == "NEEDS_INPUT"
    label, reply = talk_.send("what data do you have?", Step(describe()),
                              Step(finish("about_data", "Here is what I know. {f1}.")))
    assert reply.text == first_about, reply.text


def test_p4_two_resets(tmp_path, monkeypatch):
    """C65's test, point 4, "two resets": under 18; reset; 10 to 16 from January to June (one step:
    answered); reset; 10 to 16 from July to December: refused. The stripped records hold both
    earlier counts."""
    env = slack_env(tmp_path, monkeypatch)
    talk_ = Talk(env)
    talk_.count(spec(Y25, [U18]), Q_U18)
    talk_.send("reset")
    label, reply = talk_.count(spec(H1, [A10_16]), P21_HALVES[1][1])
    assert label == "answered", (label, reply.text)
    talk_.send("reset")
    kept = plain(given(env))
    for s in (spec(Y25, [U18]), spec(H1, [A10_16])):
        stored = {"source": A_ID, "period": s["period"], "filters": s["filters"], "group_by": []}
        assert holds(kept, stored), f"not kept: {stored}"
    label, reply = talk_.count(spec(H2, [A10_16]), P21_HALVES[2][1])
    assert_refused(env.model.answer(0))
    assert reply.text == NEW_SENTENCE, reply.text


@pytest.mark.parametrize("days_later, refused", [(29, True), (31, False)])
def test_p4_the_stripped_records_go_with_the_retention_days(tmp_path, monkeypatch, days_later,
                                                            refused):
    """C65's test, point 4: the stripped records are deleted, as turns are, when older than the
    retention days (30): purge_older_than 29 days after the turn keeps them, 31 days after removes
    them; 10 to 16 in 2025 then is refused or answered."""
    env = slack_env(tmp_path, monkeypatch)
    talk_ = Talk(env)
    talk_.count(spec(Y25, [U18]), Q_U18, now=NOW_S3)
    talk_.send("reset", now=NOW_S3 + timedelta(minutes=1))
    later = NOW_S3 + timedelta(days=days_later)
    env.store.purge_older_than(30, later)
    assert bool(holds(plain(given(env)), spec(Y25, [U18])["filters"])) is refused
    label, reply = talk_.count(spec(Y25, [A10_16]), Q_10_16, now=later)
    assert (reply.status == "UNSUPPORTED") is refused, (reply.status, reply.text)


def test_p4_reset_in_synthetic_mode_is_as_today(tmp_path):
    """C65's test, point 4, "SYNTHETIC mode as today": `reset` posts today's line, the thread has
    no turns, and nothing is kept for it. Passes today (with no given_before_reset, nothing is
    kept); must still pass."""
    env = Env(tmp_path, **SLACK)
    reply = env.ask("How many arrests in 2025 for people under 18?",
                    Step(call("count_arrests", {"year": 2025, "age_group": "under_18"})),
                    Step(finish("finding", "I counted {r1.count}.")), thread_key=THREAD_1)
    assert reply.status == "ANSWERED", (reply.status, reply.text)
    slack = FakeSlack()
    label = process(mention(f"<@{AGENT_USER}> reset", ts="1762790600.000600", thread_ts=ROOT_TS),
                    settings=env.settings, store=env.store, agent=None, slack=slack)
    assert label == "reset" and slack.log == [("post", "CTEST0001", ROOT_TS, RESET_LINE)]
    assert not env.store.thread_has_turns(THREAD_1)
    keeper = getattr(env.store, "given_before_reset", None)
    assert not (keeper and keeper(THREAD_1, 5000)), "something was kept in SYNTHETIC mode"


@pytest.mark.parametrize("talk", TALK)
def test_p5_a_direct_message_61_minutes_later(tmp_path, monkeypatch, talk):
    """C65's test, point 5: a top-level direct message, under 18 in 2025, then 10 to 16 in 2025 61
    minutes later (MOCO_DM_MEMORY_MINUTES 60): the model is not shown the first message; the check
    refuses the second with C62 point 2's sentence."""
    env = slack_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    talk_ = Talk(env)
    label, first = talk_.count(spec(Y25, [U18]), Q_U18, dm=True, now=NOW_S3)
    assert label == "answered", (label, first.text)
    label, reply = talk_.count(spec(Y25, [A10_16]), Q_10_16, dm=True,
                               now=NOW_S3 + timedelta(minutes=61))
    shown_text = json.dumps(env.model.calls[0]["messages"])
    assert Q_U18 not in shown_text, "the model was shown the message before the memory minutes"
    assert_refused(env.model.answer(0))
    assert (label, reply.text) == ("refused", NEW_SENTENCE), (label, reply.text)


def test_p5_the_check_reads_past_500_turns(tmp_path, monkeypatch):
    """Point 5, "up to the newest 5,000": under 18 in 2025, then 600 answered turns with nothing
    counted (written to the store as the program writes a turn), then 10 to 16 in 2025: refused.
    (Today's program reads the newest 500.)"""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = ask_counts(env, [spec(Y25, [U18])], Q_U18, now=NOW_S3)
    assert_answered(reply, answers)
    db = sqlite3.connect(env.tmp_path / "agent.db")
    (record,) = [json.loads(t) for (t,) in db.execute("SELECT record FROM agent_turns")]
    db.close()
    record.update(results=[], sent="Happy to help.", reply_kind="talk")
    for n in range(600):
        env.store.add_turn(thread_key=THREAD_1, user_id=USER, question=f"thanks {n}",
                           status="ANSWERED", reason_code=None,
                           created_at=NOW_S3 + timedelta(minutes=1, seconds=n), record=record)
    reply, answers = ask_counts(env, [spec(Y25, [A10_16])], Q_10_16,
                                now=NOW_S3 + timedelta(hours=1))
    assert_refused(answers[0])
    assert reply.text == NEW_SENTENCE, reply.text


# ==== step 7: speed ===============================================================================

def thirty_specs():
    """Ten turns of three counts each (no breakdown, no field filter: one figure each), ages under
    18 and over, overlapping months of 2025: thirty figures that give no single year."""
    counting, src = mod("counting"), source_json(A)
    copy = fcopy(NEWEST_A)
    out = []
    for t in range(10):
        for k, ages in enumerate([(10, 12), (13, 15), (16, 20)]):
            last = min(12, t + 1 + k)
            out.append(counting.check_spec(src, copy, {
                "source": A_ID, "period": months(2025, t + 1, last),
                "filters": [age(*ages)], "group_by": []}))
    return src, copy, out


def test_speed_thirty_figures_of_ten_turns_under_two_seconds():
    """C65's speed test: the thirty figures of ten turns, with the days of their copies, are decided
    in under two seconds (the best of three tries). Passes today; must still pass."""
    src, copy, specs = thirty_specs()
    days = [(FIRST_DAY, NEWEST_A)] * 27 + [None] * 3
    best = None
    for _ in range(3):
        started = time.perf_counter()
        result = mod("counting").one_year_under_18(src, specs, copy, days)
        took = time.perf_counter() - started
        best = took if best is None else min(best, took)
    assert not result, "premise: the thirty figures give no single year"
    assert best < 2.0, f"{best:.2f} s"


def test_speed_the_same_through_eleven_turns(tmp_path, monkeypatch):
    """The same thirty counts as ten messages of three, then an eleventh message's count: the
    eleventh turn takes under two seconds."""
    env = CountyEnv(tmp_path, monkeypatch)
    for t in range(10):
        specs = [spec(months(2025, t + 1, min(12, t + 1 + k)), [age(*ages)])
                 for k, ages in enumerate([(10, 12), (13, 15), (16, 20)])]
        reply, answers = ask_counts(env, specs)
        assert_answered(reply, answers)
    started = time.perf_counter()
    reply, answers = ask_counts(env, [spec(Y25, [age(18, 30)])])
    took = time.perf_counter() - started
    assert_answered(reply, answers)
    assert took < 2.0, f"{took:.2f} s"


NO_AGE = [spec(Y25, [], ["district"]), spec(Y24, [D3], ["gender"]), spec(H1, [F]),
          spec(Y25, [NEAR], ["month"]), spec(years(2024, 2025), [], ["race"]),
          spec(Y26, [MON_FRI], ["hour"])]


def test_speed_a_count_with_no_age_filter_anywhere_is_not_slowed(tmp_path, monkeypatch):
    """C65's speed test, the other side: in a thread of ten messages with no age filter anywhere
    (counts with breakdowns and filters of other fields), a count with no age filter takes at most
    a tenth of a second more than the same count in a new thread (the best of three tries each)."""
    env = CountyEnv(tmp_path, monkeypatch)
    for t in range(10):
        reply, answers = ask_counts(env, [NO_AGE[t % len(NO_AGE)], NO_AGE[(t + 1) % len(NO_AGE)]])
        assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    timings = {}
    for thread in (THREAD_1, THREAD_2):
        best = None
        for n in range(3):
            started = time.perf_counter()
            reply, answers = ask_counts(env, [spec(Y25, [D4])], thread_key=thread)
            took = time.perf_counter() - started
            assert reply.status == "ANSWERED", reply.text
            best = took if best is None else min(best, took)
        timings[thread] = best
    assert timings[THREAD_1] - timings[THREAD_2] <= 0.1, timings
