"""C58 of docs/S3A-DESIGN.md: C7, a compared month that the copy cuts short (live Soak 2, C17 run
3). Brief: briefs/S3-R21-A-tests.md (the part added 17 Nov 15:23 EST). Tests only; the planning
chat builds C58. Every test goes through `compare` (agent.county_compare) in a county turn on
the SYNTHETIC fixtures, with copies whose newest day the test sets; the answers are written out
by hand from C58 point 1. Red until the build, except the tests that pin what stays (point 2):
their docstrings say "Passes today".

The fixture copies: arrests_like's newest record is on 17 September 2026 (mid-month), so the
unfinished month is September and the month before it August; coded_like's is on 20 August
2026. `ending_on(day)` makes a copy of arrests_like whose newest record is on `day`: the
fixture's rows up to that day and one more SYNTHETIC row on it.

Readings (also in kit-log/raw/S3-R21-A-notes.txt):
- R21-C58-1. "The tool answers {...}": the answer is that object, key for key, nothing more;
  without `months` in the second answer.
- R21-C58-2. As with C7's answer today, an answer of C58 makes no result: the model counts
  again (two new results) and compares those, so the compare of the recounts is r5.
"""
import copy
from datetime import date

import pytest

from p1support import Step, finish, mod
from s3support import (A_ID, C_ID, Q_COMPARE, CountyEnv, compare, count, fixture_rows, is_,
                       months, year)

WHY_AGAIN = "count both years again with these months"
WHY_NONE = "no month of that period is finished in this copy"


def ending_on(day):
    """SYNTHETIC rows of arrests_like whose newest record is on `day` (ISO date)."""
    rows = [r for r in fixture_rows("arrests_like") if r["event_date_time"][:10] <= day]
    extra = copy.deepcopy(rows[-1])
    extra.update(id="FIXTURE-C58-END", event_date_time=f"{day}T10:00:00.000")
    return rows + [extra]


def compare_answer(env, sid, *periods, filters=None):
    """One turn: a count of each period, then compare of them all; the compare's answer."""
    ids = [f"r{n}" for n in range(1, len(periods) + 1)]
    counts = [count(sid, p, filters[i]) if filters else count(sid, p)
              for i, p in enumerate(periods)]
    reply = env.ask(Q_COMPARE, Step(*counts), Step(compare(*ids)),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert all(f"r{n}" in [r["id"] for r in reply.results] for n in range(1, len(ids) + 1)), \
        "premise: every count was made"
    return env.model.answer(1)


def compared(answer, n):
    assert "error" not in answer, answer
    assert answer.get("result_id") == f"r{n}", answer


# ---- C58's tests ---------------------------------------------------------------------------------

def test_the_soak_2_case_on_a_copy_that_ends_mid_month(tmp_path, monkeypatch):
    """C58 point 1: January to September of 2025 and of 2026, the copy ending on 17 September
    2026: PARTIAL_YEAR with months to August. Then the recount with those months is compared
    (R21-C58-2)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(count(A_ID, months(2025, 1, 9)), count(A_ID, months(2026, 1, 9))),
                    Step(compare("r1", "r2")),
                    Step(count(A_ID, months(2025, 1, 8)), count(A_ID, months(2026, 1, 8))),
                    Step(compare("r3", "r4")),
                    Step(finish("finding", "Here is the comparison: {r5.compare}.")))
    assert env.model.answer(1) == {"error": "PARTIAL_YEAR", "year": 2026,
                                   "months": {"from": 1, "to": 8}, "why": WHY_AGAIN}
    compared(env.model.answer(3), 5)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def test_the_same_with_a_copy_that_ends_on_the_months_last_day(tmp_path, monkeypatch):
    """C58 point 2: a copy that reaches the last day of that month is compared as today.
    Passes today."""
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": ending_on("2026-08-31")})
    newest = mod("sources").latest(A_ID, state_dir=env.state_dir).newest_day
    assert newest == date(2026, 8, 31), "premise: the copy ends on the month's last day"
    compared(compare_answer(env, A_ID, months(2025, 1, 8), months(2026, 1, 8)), 3)


@pytest.mark.parametrize("periods", [
    (months(2025, 1, 8), months(2026, 1, 8)),
    (months(2025, 3, 7), months(2026, 3, 7)),
    (months(2024, 1, 9), months(2025, 1, 9)),
], ids=["to August 2026", "March to July 2026", "September, years before the copy's"])
def test_months_that_do_not_hold_the_copys_newest_month_are_compared(tmp_path, monkeypatch,
                                                                     periods):
    """C58 point 2: months that end before the copy's newest month, or the same months of
    years before the copy's newest year, are compared as today. Passes today."""
    env = CountyEnv(tmp_path, monkeypatch)
    compared(compare_answer(env, A_ID, *periods), 3)


def test_three_years_with_the_same_months(tmp_path, monkeypatch):
    """C58 point 1, "in at least two different years": three years."""
    env = CountyEnv(tmp_path, monkeypatch)
    answer = compare_answer(env, A_ID, months(2024, 1, 9), months(2025, 1, 9), months(2026, 1, 9))
    assert answer == {"error": "PARTIAL_YEAR", "year": 2026, "months": {"from": 1, "to": 8},
                      "why": WHY_AGAIN}


def test_a_equal_to_b_in_the_unfinished_month(tmp_path, monkeypatch):
    """C58 point 1, B - 1 below A: no `months`, the second `why`."""
    env = CountyEnv(tmp_path, monkeypatch)
    answer = compare_answer(env, A_ID, months(2025, 9, 9), months(2026, 9, 9))
    assert answer == {"error": "PARTIAL_YEAR", "year": 2026, "why": WHY_NONE}


@pytest.mark.parametrize("order", ["2025, 2026", "2026, 2025"])
def test_whole_years_as_before_c58(tmp_path, monkeypatch, order):
    """C58 point 2: whole years are C7's, as today (M = 8 for this copy). Passes today."""
    env = CountyEnv(tmp_path, monkeypatch)
    pair = (year(2025), year(2026)) if order == "2025, 2026" else (year(2026), year(2025))
    assert compare_answer(env, A_ID, *pair) == {"error": "PARTIAL_YEAR", "year": 2026,
                                                "months": {"from": 1, "to": 8},
                                                "why": WHY_AGAIN}


# ---- three more, this session's own ----------------------------------------------------------

def test_own_periods_whose_months_differ_are_compared(tmp_path, monkeypatch):
    """C58 point 2, "periods whose months differ": January to September of 2025 against
    February to September of 2026 are compared as today. Passes today."""
    env = CountyEnv(tmp_path, monkeypatch)
    compared(compare_answer(env, A_ID, months(2025, 1, 9), months(2026, 2, 9)), 3)


def test_own_one_year_twice_is_compared(tmp_path, monkeypatch):
    """C58 point 1 asks for "at least two different years": two counts of January to September
    2026 (two districts) are compared as today. Passes today."""
    env = CountyEnv(tmp_path, monkeypatch)
    answer = compare_answer(env, A_ID, months(2026, 1, 9), months(2026, 1, 9),
                            filters=[[is_("district", "district 1")],
                                     [is_("district", "district 2")]])
    compared(answer, 3)


def test_own_it_is_the_copy_of_the_counts_source(tmp_path, monkeypatch):
    """C58 point 1, "the copy's newest day" is the compared source's: coded_like's copy ends on
    20 August 2026, so January to August of 2025 and 2026 answer PARTIAL_YEAR to July."""
    env = CountyEnv(tmp_path, monkeypatch, names=("coded_like",))
    answer = compare_answer(env, C_ID, months(2025, 1, 8), months(2026, 1, 8))
    assert answer == {"error": "PARTIAL_YEAR", "year": 2026, "months": {"from": 1, "to": 7},
                      "why": WHY_AGAIN}
