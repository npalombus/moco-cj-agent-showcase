"""Stage 3 Part A, C54 of docs/S3A-DESIGN.md: C21 (under 18, inside one turn) with the days a count
keeps, and one source at a time. Brief: briefs/S3-R18-A-tests.md. Tests only; the planning chat
builds C54. The findings it answers are DEFECT 1 and DEFECT 2 of kit-log/raw/CHAT-BUILDS-check-8.txt
(its step 5 probes W1 to W4, W6, W7 and X1 to X3 are here by name). All data is SYNTHETIC: the
fixtures of tests/s3, rows made for one test in that test's own copy (ids FIXTURE-R18-...), and a
second source made for this file in a test's own sources folder (juvenile_like); no real figure
is quoted.

C54 point 1: a figure's days are the days of its period, cut to the copy's days, that the count's
`weekday` filter allows (all of them with no such filter); the weekday filter is no longer part of
the kind, the days are. A count whose weekday filter allows no day of its period has no figure.
Point 2: a weekday group is of the kind of a count of that weekday's days among the count's days;
a weekday with no day among them gives no figure; groups by year or month are cut from the
count's days after the weekday filter. Point 3: C52 point 1 stays for hours and categories.
Point 4: the check takes the turn's counts of the new request's source only, each read with that
source's own ages.

What each test shows:
- refused: `counting.one_year_under_18` on the checked specs is True (and False on the counts
  before the last); through `count` in a county turn with the model stand-in, the last request is
  answered NOT_ALLOWED with the age field and C21's `why` word for word, the counts before it are
  answered, nothing is counted or saved for it, and the turn is ANSWERED;
- the refused count uses up none of the turn's eight counts, for every refused example;
- the check's probes W1 to W4 and W6, with rows that make the figures differ: plain counting of
  the test's own rows shows that the two replies' figures differ by the 17-year-olds of those days
  (so one year would follow); W7, the compare of W1's counts, cannot be made;
- allowed: `one_year_under_18` is False, every count is answered, the totals are plain counting's;
- point 4 through county turns with two SYNTHETIC sources whose age fields share a name and differ
  in usable ages (X1 to X3, both orders, and the same source after another source's count).

READINGS (also in kit-log/raw/S3-R18-A-notes.txt):
- R18-1. "The days of its period, cut to the copy's days": the copy's first day is the source
  file's coverage_start and its last is the newest record's day (C21 answer 3, as built today).
  A period that runs past either end is cut first, and the weekday filter then picks from what is
  left (the refused examples "a period that the copy cuts" and "a period that starts before the
  copy").
- R18-2. "Has no figure": not a refusal. The count is answered as today (0 records), and gives C21
  no figure at all, its left-out figures included (they are of the count's kind, so of its days).
- R18-3. Point 4 is shown through county turns only. Whether the build leaves the other source's
  counts out in agent.py (before `one_year_under_18` is called) or inside `one_year_under_18` is
  not said, so no test here calls `one_year_under_18` with specs of two sources.
- R18-4. The figures of the W probes are of the test's own rows; whether a reply shows them (10 or
  more) or hides them makes no difference to C21. Each W test still makes them 10 or more where
  the check did, so the difference could be read off the two replies.
"""
import json
from datetime import date, timedelta

import pytest

from p1support import Step, finish, mod
from s3support import (COPY_NOW, CountyEnv, FakeService, age, compare, count, dates,
                       figures, fixture_rows, hours, in_, is_, made_rows, months, source_json, truth,
                       weekdays, year)
from test_s3_round5 import (A, AGE_FIELD, IDS, U16, U17, U18, Y25, assert_counted,
                            assert_not_allowed, assert_result, checked, counts_text, spec)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MON_FRI, WEEKEND = weekdays(*DAYS[:5]), weekdays("Saturday", "Sunday")
D3, D4, D5 = (is_("district", f"district {n}") for n in (3, 4, 5))
Q_COUNT = "How many arrests were there?"
Q_COMPARE = "Compare those two counts."


def day(text):
    return dates(text, text)


APR11, APR30 = day("2025-04-11"), day("2025-04-30")          # a Friday; a Wednesday
AUG4, AUG9 = day("2025-08-04"), day("2025-08-09")            # a Monday; a Saturday
AUG4_8, AUG4_10 = dates("2025-08-04", "2025-08-08"), dates("2025-08-04", "2025-08-10")
MAR1_2, MAR1_7 = dates("2025-03-01", "2025-03-02"), dates("2025-03-01", "2025-03-07")
MARCH = months(2025, 3, 3)

# ---- the second source (point 4), made in a test's own sources folder ----------------------------

J = "juvenile_like"
J_ID = "FIXTURE:juvenile_like"
SIDS = {**IDS, J: J_ID}
AGE_FIELD = {**AGE_FIELD, J: "age"}


def juvenile_source():
    """arrests_like's file with another id, title, address and unit; its age field has the same
    name, `age`, with usable ages 10 to 17 (as the check's juvenile-like source)."""
    src = source_json(A)
    src.update(id=J_ID, title="SYNTHETIC fixture juvenile records (made up for tests)",
               address="https://fixture.invalid/resource/juvenile-like.json",
               page="https://fixture.invalid/d/juvenile-like",
               row_meaning="one made-up juvenile record",
               unit={"one": "juvenile record", "many": "juvenile records"})
    (f,) = [f for f in src["fields"] if f["kind"] == "age"]
    f["usable"], f["bands"] = [10, 17], [[10, 13], [14, 17]]
    return src


def add_juvenile(env):
    """The juvenile-like file in the env's own sources folder, and its copy (arrests_like's rows,
    through the fake transport)."""
    src = juvenile_source()
    (env.sources_dir / f"{J}.json").write_text(json.dumps(src, indent=2), encoding="utf-8")
    mod("sources").fetch(J_ID, state_dir=env.state_dir, now=COPY_NOW,
                         transport=FakeService(fixture_rows(A), address=src["address"]))
    return env


# ---- rows made for one test (the test's own copy of the fixture; the shared files unchanged) ----

def at(text, hour=14):
    return f"{text}T{hour:02d}:00:00.000"


def _r18_rows(*groups):
    """SYNTHETIC rows over arrests_like's base row (s3support.made_rows), without the anchor row
    it adds, so the fixture's own newest record stays the copy's newest."""
    made = made_rows(A, *groups, prefix="FIXTURE-R18-")
    return [r for r in made if not r["id"].endswith("ANCHOR")]


def _on(text, n, years_old, **values):
    return n, {"age": str(years_old), "event_date_time": at(text), **values}


def _span(first, last):
    d, out = date.fromisoformat(first), []
    while d <= date.fromisoformat(last):
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


EXTRA = {
    # W1 as the check made it: 12 aged 17 and 11 aged 15 on 11 April 2025
    "11 April": _r18_rows(_on("2025-04-11", 12, 17), _on("2025-04-11", 11, 15)),
    "30 April": _r18_rows(_on("2025-04-30", 10, 17), _on("2025-04-30", 10, 15)),
    # each of 4 to 8 August 2025: 11 aged 15 and 3 aged 17; and 10 aged 15 on 9 and 10 August
    "4 to 8 August": _r18_rows(*[g for d in _span("2025-08-04", "2025-08-08")
                                 for g in (_on(d, 11, 15), _on(d, 3, 17))],
                               _on("2025-08-09", 10, 15), _on("2025-08-10", 10, 15)),
    # each of 4 to 8 August 2025: 11 women and 11 men aged 15, 2 women aged 17
    "4 to 8 August by gender": _r18_rows(*[g for d in _span("2025-08-04", "2025-08-08")
                                           for g in (_on(d, 11, 15, gender="Female"),
                                                     _on(d, 11, 15, gender="Male"),
                                                     _on(d, 2, 17, gender="Female"))]),
    # W6: no district recorded, 12 aged 17 on 5 August and 12 aged 15 on 6 August 2025
    "no district, 4 to 8 August": _r18_rows(_on("2025-08-05", 12, 17, district=None),
                                            _on("2025-08-06", 12, 15, district=None)),
    # W3: 10 aged 15 and 2 aged 17 on each of 1 and 2 March 2025; 10 aged 15 on 4 March
    "1 and 2 March": _r18_rows(_on("2025-03-01", 10, 15), _on("2025-03-01", 2, 17),
                               _on("2025-03-02", 10, 15), _on("2025-03-02", 2, 17),
                               _on("2025-03-04", 10, 15)),
    # 10 aged 15 on each day of 28 July to 3 August 2025; 2 aged 17 on 1 August
    "28 July to 3 August": _r18_rows(*[_on(d, 10, 15) for d in _span("2025-07-28", "2025-08-03")],
                                     _on("2025-08-01", 2, 17)),
    # Mondays: 10 aged 15 on 3 March, 3 aged 17 on 10 March, 10 aged 15 on 7 April 2025; and 10
    # aged 15 on 4 March (a Tuesday)
    "Mondays of March and April": _r18_rows(_on("2025-03-03", 10, 15), _on("2025-03-10", 3, 17),
                                            _on("2025-04-07", 10, 15), _on("2025-03-04", 10, 15)),
    # before the copy's newest record (17 September 2026): 10 aged 15 and 2 aged 17 on the 15th
    "15 September 2026": _r18_rows(_on("2026-09-15", 10, 15), _on("2026-09-15", 2, 17)),
}


def rows_of(extra):
    return fixture_rows(A) + EXTRA[extra] if extra else None


def env_with(tmp_path, monkeypatch, extra=None):
    return CountyEnv(tmp_path, monkeypatch, rows={A: rows_of(extra)} if extra else None)


def call_of(s):
    return count(SIDS[s["name"]], s["period"], s["filters"], s["group_by"])


def one_turn(env, specs, answered=None, question=Q_COUNT):
    """One turn: every count in one step, then a finish naming the first `answered` results.
    Returns (reply, Python's answer to each count, in order)."""
    n = len(specs) if answered is None else answered
    reply = env.ask(question, Step(*[call_of(s) for s in specs]),
                    Step(finish("finding", counts_text(n))))
    return reply, [env.model.answer(0, i) for i in range(len(specs))]


def one_year(env, specs):
    """`counting.one_year_under_18` on the specs as C5 checks and tidies them, with the copy
    (as the turn hands them to C21). One source only (R18-3)."""
    (name,) = {s["name"] for s in specs}
    sid = SIDS[name]
    source = mod("sources").load_sources()[sid]
    copy = mod("sources").latest(sid, state_dir=env.state_dir)
    done = [mod("counting").check_spec(source, copy, {"period": s["period"],
                                                      "filters": s["filters"],
                                                      "group_by": s["group_by"]})
            for s in specs]
    return mod("counting").one_year_under_18(source, done, copy)


def plain(s, extra=None, src=None):
    """Plain counting (s3support.truth) of a spec on the test's own rows."""
    return truth(A, s["period"], s["filters"], s["group_by"], rows=rows_of(extra), src=src)


def seventeens(extra, first, last, no_district=False):
    """Plain counting: the records aged 17 from `first` to `last` (and, with no_district, with no
    district recorded) on the test's own rows."""
    rows = rows_of(extra) or fixture_rows(A)
    return sum(1 for r in rows if r.get("age") == "17"
               and first <= r["event_date_time"][:10] <= last
               and (not no_district or "district" not in r))


# ---- refused ------------------------------------------------------------------------------------
# Each case: (the counts of one turn, in order; the rows made for it, or None). Every count but
# the last is answered; the last is refused. arrests_like unless said.

W1 = [spec(APR11, [U18]), spec(APR11, [U17, weekdays("Friday")])]
W2 = [spec(AUG4_8, [U18]), spec(AUG4_10, [U17, MON_FRI])]
W3 = [spec(MAR1_2, [U18]), spec(MAR1_7, [U17, WEEKEND])]
W4 = [spec(AUG4_8, [U18], ["weekday"]), spec(AUG4, [U17])]
W6 = [spec(AUG4_8, [U18, D3]), spec(AUG4_10, [U17, D5, MON_FRI])]

REFUSED = {
    # C54's own examples, which are the check's W1 to W4 and W6
    "C54, W1: under 18 on 11 April 2025, then under 17 on 11 April 2025 on Fridays":
        (W1, "11 April"),
    "C54, W2: under 18 from 4 to 8 August 2025, then under 17 from 4 to 10 August on Monday to "
    "Friday": (W2, "4 to 8 August"),
    "C54, W3: under 18 on 1 and 2 March 2025, then under 17 from 1 to 7 March on Saturdays and "
    "Sundays": (W3, "1 and 2 March"),
    "C54, W4: under 18 from 4 to 8 August 2025 by weekday, then under 17 on 4 August":
        (W4, "4 to 8 August"),
    # W6: under 18 in district 3 from 4 to 8 August, then under 17 in district 5 from 4 to 10
    # August on Monday to Friday (the left-out figures)
    "C54, W6: left-out figures: district 3 on 4 to 8 August, then district 5 on 4 to 10 August "
    "on Mon-Fri": (W6, "no district, 4 to 8 August"),
    # this file's own
    "another single day: 30 April 2025 (a Wednesday), then that day on Monday to Friday":
        ([spec(APR30, [U18]), spec(APR30, [U17, MON_FRI])], "30 April"),
    "the narrower count first: under 17 on 11 April 2025 on Fridays, then under 18 that day":
        ([spec(APR11, [U17, weekdays("Friday")]), spec(APR11, [U18])], "11 April"),
    "a weekday filter on the first count only: 4 to 8 August on Monday to Friday, then without":
        ([spec(AUG4_8, [U18, MON_FRI]), spec(AUG4_8, [U17])], "4 to 8 August"),
    # March 2025 on Mondays, then 3 to 31 March 2025 on Mondays
    "a month's Mondays as a filter, then as dates and a filter":
        ([spec(MARCH, [U18, weekdays("Monday")]),
          spec(dates("2025-03-03", "2025-03-31"), [U17, weekdays("Monday")])],
         "Mondays of March and April"),
    "one Monday as a date, then as a filter: 3 March 2025, then 1 to 9 March on Mondays":
        ([spec(day("2025-03-03"), [U18]),
          spec(dates("2025-03-01", "2025-03-09"), [U17, weekdays("Monday")])],
         "Mondays of March and April"),
    "a weekend written two ways: 1 and 2 March 2025, then 28 February to 2 March on Saturdays "
    "and Sundays":
        ([spec(MAR1_2, [U18]), spec(dates("2025-02-28", "2025-03-02"), [U17, WEEKEND])],
         "1 and 2 March"),
    # 4 to 6 August 2025 on Monday to Thursday, then on Monday, Tuesday, Wednesday and Sunday
    "two weekday filters that allow the same days of a short period":
        ([spec(dates("2025-08-04", "2025-08-06"), [U18, weekdays(*DAYS[:4])]),
          spec(dates("2025-08-04", "2025-08-06"),
               [U17, weekdays("Monday", "Tuesday", "Wednesday", "Sunday")])], "4 to 8 August"),
    # by weekday from 4 to 8 August 2025, then from 4 to 10 August on Mondays
    "a weekday group against a weekday filter on a longer period":
        ([spec(AUG4_8, [U18], ["weekday"]), spec(AUG4_10, [U17, weekdays("Monday")])],
         "4 to 8 August"),
    # 28 July to 3 August 2025 by weekday and month (the cell Friday, August 2025 holds one
    # day), then 1 August
    "a weekday breakdown by month against a count of one day's date":
        ([spec(dates("2025-07-28", "2025-08-03"), [U18], ["weekday", "month"]),
          spec(day("2025-08-01"), [U17])], "28 July to 3 August"),
    # March and April 2025 on Mondays by month, then 3 to 31 March 2025 on Mondays
    "month groups cut from the days after the weekday filter":
        ([spec(months(2025, 3, 4), [U18, weekdays("Monday")], ["month"]),
          spec(dates("2025-03-03", "2025-03-31"), [U17, weekdays("Monday")])],
         "Mondays of March and April"),
    # 4 to 8 August 2025 by weekday and gender, then 4 August recorded as female
    "weekday cells with a second breakdown (gender)":
        ([spec(AUG4_8, [U18], ["weekday", "gender"]),
          spec(AUG4, [U17, is_("gender", "female")])], "4 to 8 August by gender"),
    # 14 to 17 September 2026, then 14 to 20 September 2026 (cut to the 17th) on Monday to
    # Thursday
    "a period that the copy cuts, with a weekday filter":
        ([spec(dates("2026-09-14", "2026-09-17"), [U18]),
          spec(dates("2026-09-14", "2026-09-20"), [U17, weekdays(*DAYS[:4])])],
         "15 September 2026"),
    # 1 January 2024, then 25 December 2023 to 1 January 2024 on Mondays (two Mondays; the
    # copy starts on 1 January 2024)
    "a period that starts before the copy, with a weekday filter":
        ([spec(day("2024-01-01"), [U18]),
          spec(dates("2023-12-25", "2024-01-01"), [U17, weekdays("Monday")])], None),
    "hours together with weekdays: 11 April 2025, then that day on Fridays at hours 0 to 23":
        ([spec(APR11, [U18]), spec(APR11, [U17, weekdays("Friday"), hours(0, 23)])],
         "11 April"),
    "hours together with weekdays: 11 April 2025 at hours 5 to 4, then that day on Monday to "
    "Friday": ([spec(APR11, [U18, hours(5, 4)]), spec(APR11, [U17, MON_FRI])], "11 April"),
    "left-out figures on one day: district 3 on 11 April 2025, then district 4 that day on "
    "Fridays": ([spec(APR11, [U18, D3]), spec(APR11, [U17, D4, weekdays("Friday")])], None),
    "three counts, the days written two ways: 10 to 13 and 14 to 15, then 10 to 16 (16)":
        ([spec(AUG4_8, [age(10, 13)]), spec(AUG4_10, [age(14, 15), MON_FRI]),
          spec(AUG4_8, [age(10, 16)])], "4 to 8 August"),
}


@pytest.mark.parametrize("case", list(REFUSED))
def test_c54_refused(tmp_path, monkeypatch, case):
    specs, extra = REFUSED[case]
    env = env_with(tmp_path, monkeypatch, extra)
    assert not one_year(env, specs[:-1]), "premise: the counts before the last are allowed"
    assert one_year(env, specs), "counting.one_year_under_18 must be True"
    reply, answers = one_turn(env, specs, answered=len(specs) - 1)
    for i, answer in enumerate(answers[:-1], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[-1], AGE_FIELD[specs[-1]["name"]])
    assert_counted(env, reply, len(specs) - 1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    checked(reply)


FILLERS = ([spec(Y25, [age(18), is_("district", f"district {n}")]) for n in range(1, 7)]
           + [spec(year(2024), [age(18)]), spec(year(2026), [age(18)]), spec(Y25, [age(18)])])


@pytest.mark.parametrize("case", list(REFUSED))
def test_c54_the_refused_count_uses_up_none_of_the_turns_counts(tmp_path, monkeypatch, case):
    """As round 16's R16-4: after the refusal, counts are answered up to eight; the next is
    TOO_MANY. The counts added are of ages 18 and over in whole years, so none is refused."""
    specs, extra = REFUSED[case]
    made = specs[:-1]
    fillers = FILLERS[:8 - len(made) + 1]
    env = env_with(tmp_path, monkeypatch, extra)
    reply, answers = one_turn(env, made + [specs[-1]] + fillers, answered=1)
    for i, answer in enumerate(answers[:len(made)], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[len(made)], AGE_FIELD[specs[-1]["name"]])
    for i, answer in enumerate(answers[len(made) + 1:-1], len(made) + 1):
        assert_result(answer, f"r{i}")
    assert answers[-1].get("error") == "TOO_MANY", answers[-1]
    assert_counted(env, reply, 8)


def test_c54_w1_in_two_steps(tmp_path, monkeypatch):
    """The check is over the turn's counts so far, whatever step they came in."""
    env = env_with(tmp_path, monkeypatch, "11 April")
    reply = env.ask(Q_COUNT, Step(call_of(W1[0])), Step(call_of(W1[1])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_result(env.model.answer(0), "r1")
    assert_not_allowed(env.model.answer(1))
    assert_counted(env, reply, 1)


def test_c54_w7_the_compare_cannot_be_made(tmp_path, monkeypatch):
    """W7: W1's two counts, then compare: the second count is refused, so it has no result and
    the compare is not made; no difference (13, the 17-year-olds of that day) is written."""
    env = env_with(tmp_path, monkeypatch, "11 April")
    first, second = W1
    difference = plain(first, "11 April")["total"] - plain(second, "11 April")["total"]
    assert difference == 13, "premise: 13 aged 17 on 11 April 2025 on the test's own rows"
    reply = env.ask(Q_COMPARE, Step(call_of(first), call_of(second)), Step(compare("r1", "r2")),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_result(env.model.answer(0, 0), "r1")
    assert_not_allowed(env.model.answer(0, 1))
    assert env.model.answer(1).get("error") == "BAD_COMPARE", env.model.answer(1)
    assert "difference" not in reply.text and difference not in figures(reply.text), reply.text
    assert [r["kind"] for r in reply.results] == ["count"]


# ---- the W probes by plain counting: one year would follow -------------------------------------

def _total(i):
    return lambda case_specs, extra: plain(case_specs[i], extra)["total"]


W_FIGURES = {
    # id: (specs, rows, the first figure, the second figure, (first day, last day), no district,
    #      the figures as the check had them, or None)
    "W1": (W1, "11 April", _total(0), _total(1), ("2025-04-11", "2025-04-11"), False, (24, 11)),
    "W2": (W2, "4 to 8 August", _total(0), _total(1), ("2025-08-04", "2025-08-08"), False, None),
    "W3": (W3, "1 and 2 March", _total(0), _total(1), ("2025-03-01", "2025-03-02"), False, None),
    "W4": (W4, "4 to 8 August",
           lambda s, x: plain(s[0], x)["groups"]["Monday"], _total(1),
           ("2025-08-04", "2025-08-04"), False, None),
    "W6": (W6, "no district, 4 to 8 August",
           lambda s, x: plain(s[0], x)["left_out"]["district"],
           lambda s, x: plain(s[1], x)["left_out"]["district"],
           ("2025-08-04", "2025-08-08"), True, (24, 12)),
}


@pytest.mark.parametrize("probe", list(W_FIGURES))
def test_c54_w_probes_the_figures_differ_by_the_17_year_olds_of_those_days(probe):
    """Plain counting (no program code): the first count's figure less the second's is the
    records aged 17 of the days the two keep (with no district recorded, for W6's left-out
    figures), and there are some; both figures would be shown (10 or more)."""
    specs, extra, first_of, second_of, (first, last), no_district, check = W_FIGURES[probe]
    one, two = first_of(specs, extra), second_of(specs, extra)
    aged_17 = seventeens(extra, first, last, no_district)
    assert aged_17 > 0 and one - two == aged_17, (one, two, aged_17)
    assert min(one, two) >= 10, (one, two)
    if check:
        assert (one, two) == check


# ---- allowed --------------------------------------------------------------------------------------

ALLOWED = {
    # C54's own examples
    "C54: under 18 on the Saturdays and Sundays of 2025, then under 17 on its Mondays to Fridays": ([spec(Y25, [U18, WEEKEND]), spec(Y25, [U17, MON_FRI])], None),
    "C54: under 18 in March 2025, then under 17 on the Mondays of March 2025 (some of its days)":
        ([spec(MARCH, [U18]), spec(MARCH, [U17, weekdays("Monday")])],
         "Mondays of March and April"),
    # this file's own
    "days that differ by one day: 4 to 8 August, then 4 to 10 August on Monday to Saturday":
        ([spec(AUG4_8, [U18]), spec(AUG4_10, [U17, weekdays(*DAYS[:6])])], "4 to 8 August"),
    "days that differ by one day: 11 April, then 10 to 13 April on Thursdays and Fridays":
        ([spec(APR11, [U18]), spec(dates("2025-04-10", "2025-04-13"),
                                   [U17, weekdays("Thursday", "Friday")])], "11 April"),
    "a weekday filter that allows a strict part of the days: 4 to 8 August, then on Monday to "
    "Thursday": ([spec(AUG4_8, [U18]), spec(AUG4_8, [U17, weekdays(*DAYS[:4])])],
                 "4 to 8 August"),
    "a weekday filter that allows no day of the period: 11 April (a Friday), then on Mondays":
        ([spec(APR11, [U18]), spec(APR11, [U17, weekdays("Monday")])], "11 April"),
    # district 3 on 11 April 2025, then district 5 that day on Saturdays and Sundays
    "no day of the period, so no left-out figure either":
        ([spec(APR11, [U18, D3]), spec(APR11, [U17, D5, WEEKEND])], None),
    "a weekday breakdown, then a day it has no group for: by weekday from 4 to 8 August, then 9 "
    "August": ([spec(AUG4_8, [U18], ["weekday"]), spec(AUG9, [U17])], "4 to 8 August"),
    # by weekday from 4 to 8 August 2025, then the Mondays of August 2025 (other days)
    "a weekday group against that weekday on a longer period": ([spec(AUG4_8, [U18], ["weekday"]),
                               spec(months(2025, 8, 8), [U17, weekdays("Monday")])],
                              "4 to 8 August"),
    "the same days, two years apart: 11 April, then under 16 that day on Fridays":
        ([spec(APR11, [U18]), spec(APR11, [U16, weekdays("Friday")])], "11 April"),
}


@pytest.mark.parametrize("case", list(ALLOWED))
def test_c54_allowed(tmp_path, monkeypatch, case):
    specs, extra = ALLOWED[case]
    env = env_with(tmp_path, monkeypatch, extra)
    assert not one_year(env, specs), "counting.one_year_under_18 must be False"
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert [r["total"] for r in reply.results if r["kind"] == "count"] == \
        [plain(s, extra)["total"] for s in specs]
    checked(reply)


# ---- point 4: one source at a time ------------------------------------------------------------------

JUV = juvenile_source()
A_17_24 = spec(Y25, [age(17, 24)])
A_17_UP = spec(Y25, [age(17)])
J_ALL = spec(Y25, [], name=J)
J_14_17 = spec(Y25, [age(14, 17)], name=J)

TWO_SOURCES = {
    "X1: arrests aged 17 to 24 in 2025, then the juvenile records of 2025": [A_17_24, J_ALL],
    "X2: arrests aged 17 and over, then juvenile records aged 14 to 17": [A_17_UP, J_14_17],
    "X3, the other order: the juvenile records of 2025, then arrests aged 17 to 24":
        [J_ALL, A_17_24],
    "X2, the other order: juvenile records aged 14 to 17, then arrests aged 17 and over":
        [J_14_17, A_17_UP],
    # juvenile records of 2025, arrests aged 17 to 24, then juvenile records aged 10 to 15
    "the same source after another source's count: juvenile, arrests, then juvenile 10 to 15":
        [J_ALL, A_17_24, spec(Y25, [age(10, 15)], name=J)],
    # arrests under 18 in 2025, the juvenile records of 2025, then arrests under 16
    "the same source after another source's count: arrests, juvenile, then arrests under 16": [spec(Y25, [U18]), J_ALL, spec(Y25, [U16])],
}


def two_sources(tmp_path, monkeypatch):
    env = add_juvenile(CountyEnv(tmp_path, monkeypatch))
    assert list(mod("sources").county_sources()) == [IDS[A], J_ID], "premise: two sources"
    return env


def plain_of(s):
    return truth(A, s["period"], s["filters"], src=JUV if s["name"] == J else None)["total"]


@pytest.mark.parametrize("case", list(TWO_SOURCES))
def test_c54_point_4_two_sources_are_two_kinds(tmp_path, monkeypatch, case):
    """Point 4: each count is answered; the totals are plain counting's, each of its own source
    (the juvenile ones with usable ages 10 to 17)."""
    specs = TWO_SOURCES[case]
    env = two_sources(tmp_path, monkeypatch)
    for name in (A, J):
        same = [s for s in specs if s["name"] == name]
        assert not one_year(env, same), "premise: no single year from one source's counts"
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert [r["total"] for r in reply.results if r["kind"] == "count"] == \
        [plain_of(s) for s in specs]
    assert [r["spec"]["source"] for r in reply.results] == [SIDS[s["name"]] for s in specs]


TWO_SOURCES_REFUSED = {
    "juvenile records, arrests aged 17 to 24, then juvenile records aged 10 to 16 (17)":
        [J_ALL, A_17_24, spec(Y25, [age(10, 16)], name=J)],
    "arrests under 18, juvenile records, then arrests under 17 (17)":
        [spec(Y25, [U18]), J_ALL, spec(Y25, [U17])],
}


@pytest.mark.parametrize("case", list(TWO_SOURCES_REFUSED))
def test_c54_point_4_the_new_requests_source_is_still_checked(tmp_path, monkeypatch, case):
    """Point 4 takes the counts of the new request's source, so another source's count between
    them changes nothing: the last is refused as C21 refuses it."""
    specs = TWO_SOURCES_REFUSED[case]
    env = two_sources(tmp_path, monkeypatch)
    last = specs[-1]["name"]
    assert one_year(env, [s for s in specs if s["name"] == last])
    reply, answers = one_turn(env, specs, answered=len(specs) - 1)
    for i, answer in enumerate(answers[:-1], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[-1], AGE_FIELD[last])
    assert_counted(env, reply, len(specs) - 1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ---- premises -------------------------------------------------------------------------------------

def test_premises_of_this_file():
    """Plain counting and the calendar (no program code): the days are the weekdays the cases
    name; the breakdowns made above are not too fine on the rows they use; the rows made here
    are SYNTHETIC and new ids, and none is after the copy's newest record."""
    named = {"2025-04-11": "Friday", "2025-04-30": "Wednesday", "2025-08-04": "Monday",
             "2025-08-08": "Friday", "2025-08-09": "Saturday", "2025-03-01": "Saturday",
             "2025-03-03": "Monday", "2025-02-28": "Friday", "2025-07-28": "Monday",
             "2025-08-01": "Friday", "2026-09-14": "Monday", "2026-09-17": "Thursday",
             "2024-01-01": "Monday", "2023-12-25": "Monday"}
    for text, name in named.items():
        assert DAYS[date.fromisoformat(text).weekday()] == name, text
    for s, extra in ((spec(AUG4_8, [U18], ["weekday"]), "4 to 8 August"),
                     (spec(AUG4_8, [U18], ["weekday", "gender"]), "4 to 8 August by gender"),
                     (spec(dates("2025-07-28", "2025-08-03"), [U18], ["weekday", "month"]),
                      "28 July to 3 August"),
                     (spec(months(2025, 3, 4), [U18, weekdays("Monday")], ["month"]),
                      "Mondays of March and April")):
        found = plain(s, extra)
        values = list((found["groups"] or found["grid"]).values())
        assert not [n for n in values if 1 <= n <= 9], (s, values)
    ids = {r["id"] for r in fixture_rows(A)}
    newest = max(r["event_date_time"] for r in fixture_rows(A))
    for rows in EXTRA.values():
        assert all(r["data_class"] == "SYNTHETIC" and r["id"] not in ids
                   and r["event_date_time"] < newest for r in rows)
    (f,) = [f for f in JUV["fields"] if f["kind"] == "age"]
    assert (f["name"], f["usable"]) == ("age", [10, 17])
