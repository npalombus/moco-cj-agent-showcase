"""S14 of docs/S3S-DESIGN.md (D-061): a shares analysis over one year is refused before R. Brief:
briefs/S3-R7-A-tests.md. Tests only; the planning chat makes the change.

A `shares` selection whose months fall in fewer than two calendar years is refused before R as
`TOO_LITTLE`, rule `years`, with exactly S14's line. Nothing else changes; the model may still
call `count` and `share` in the same turn. S14's tests:
- a shares analysis over one year is refused with that line and R is not started (the
  Rscript of the turn is the stand-in of tests/s3s/test_s3s_engine.py, which marks every
  analysis it is started on; no job folder is made either), for one year written three ways
  and for the year the copy is in;
- over two years it runs as today (real R);
- the line word for word, in the tool answer and in the reply;
- the model can still count the whole and the part and give the share in the same turn.

READINGS (also in kit-log/raw/S3-R7-A-notes.txt):
- S14-1 the tool answer is today's form of a TOO_LITTLE refusal (stats._little): exactly
  {"error": "TOO_LITTLE", "rule": "years", "why": <the line>}.
- S14-2 the reply of a turn that ends with nothing else made is the line alone (S10 answer 10:
  "a refused analysis ends with the line of its rule"), with reason code TOO_LITTLE.
- S14-3 "months" are S2's window (the full months used, less drop_newest_months), so a period
  of the copy's own year counts the months it keeps of that year. Every period refused here
  has a base of 100 or more and a part of 10 or more in its one year (a premise), so no other
  TOO_LITTLE rule or TOO_FINE can refuse it first; which rule would come first otherwise is
  not said and not tested.
"""
import json
from collections import OrderedDict
from datetime import date

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import MAIN, MAIN_ID, Q_SHARES, StatsEnv, analyze, answered, job_folders
from s3support import count, is_, share
from test_s3s_engine import stand_in

LINE = ("That follows a share across years, so it needs at least two years of records. For one "
        "year, I can count the whole and the part and give the share.")
SRC = T.source_json(MAIN)
PART = [is_(T.SCHOOL, True)]

ONE_YEAR = {
    "2025 as a year": {"year": 2025},
    "2025 as twelve months": {"year": 2025, "months": {"from": 1, "to": 12}},
    "2025 as dates": {"from": "2025-01-01", "to": "2025-12-31"},
    "2024 as a year": {"year": 2024},
    "the copy's year": {"year": 2026},
}
TWO_YEARS = {
    "2024 and 2025": {"years": [2024, 2025]},
    "2024 to 2025 as dates": {"from": "2024-01-01", "to": "2025-12-31"},
}


def shares_arguments(period):
    return {"kind": "shares", "source": MAIN_ID, "period": period, "filters": [],
            "options": {"part": PART}}


def by_year(period):
    """No program code: the base and the part in each calendar year of S2's window."""
    months = T.window(SRC, period)
    first = date(*months[0], 1)
    last = T.last_day(*months[-1])
    rows, _ = T.select(MAIN, first, last, [], [T.SCHOOL])
    out = OrderedDict()
    for r in rows:
        yr = T.row_time(r, SRC)[0].year
        n, k = out.get(yr, (0, 0))
        out[yr] = (n + 1, k + all(T.matches(r, flt, SRC) for flt in PART))
    return out


def r_env(tmp_path, monkeypatch):
    """StatsEnv whose Rscript is the stand-in: an analysis script it is started on leaves a
    mark in tmp_path and fails; anything else goes to the real Rscript."""
    marks = tmp_path / "r_started.txt"
    rscript = stand_in(tmp_path, f'echo "$last" >> "{marks}"; exit 1')
    monkeypatch.setenv("MOCO_RSCRIPT", str(rscript))
    env = StatsEnv(tmp_path, monkeypatch, MOCO_RSCRIPT=str(rscript))
    return env, marks


def assert_r_not_started(env, marks):
    assert not marks.exists(), f"R was started: {marks.read_text(encoding='utf-8')}"
    assert job_folders(env) == [], "a job folder was made: R was to be started"


@pytest.mark.parametrize("label", list(ONE_YEAR))
def test_premise_one_year_has_enough_records_in_it(label):
    years = by_year(ONE_YEAR[label])
    assert len(years) == 1, years
    ((n, k),) = years.values()
    assert n >= 100 and k >= 10, years


@pytest.mark.parametrize("label", list(TWO_YEARS))
def test_premise_two_years_each_have_enough_records(label):
    years = by_year(TWO_YEARS[label])
    assert list(years) == [2024, 2025], years
    assert all(n >= 100 and k >= 10 for n, k in years.values()), years


@pytest.mark.parametrize("label", list(ONE_YEAR))
def test_one_year_is_refused_before_r_with_the_line(tmp_path, monkeypatch, label):
    env, marks = r_env(tmp_path, monkeypatch)
    reply = env.ask(Q_SHARES, Step(analyze(shares_arguments(ONE_YEAR[label]))),
                    Step(finish("finding", "I could not run that.")))
    assert_r_not_started(env, marks)
    answer = env.model.answer(0)
    assert answer == {"error": "TOO_LITTLE", "rule": "years", "why": LINE}, answer
    assert (reply.reason_code, reply.text) == ("TOO_LITTLE", LINE), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.status != "ANSWERED" and list(reply.run_ids) == []


def test_the_model_can_still_count_and_share_in_the_same_turn(tmp_path, monkeypatch):
    """S14: "the model may still call count and share in the same turn": after the refusal it
    counts the whole and the part of 2025 and gives the share; R is never started."""
    env, marks = r_env(tmp_path, monkeypatch)
    reply = env.ask(Q_SHARES, Step(analyze(shares_arguments({"year": 2025}))),
                    Step(count(MAIN_ID, {"year": 2025}, []),
                         count(MAIN_ID, {"year": 2025}, PART)),
                    Step(share("r2", "r1")),
                    Step(finish("finding", "{r3.share}.")))
    assert_r_not_started(env, marks)
    assert env.model.answer(0) == {"error": "TOO_LITTLE", "rule": "years", "why": LINE}
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert [r["kind"] for r in reply.results] == ["count", "count", "share"]
    assert LINE not in reply.text
    n, k = by_year({"year": 2025})[2025]
    percent = (200 * k + n) // (2 * n)   # C7: the share rounded half up (k is at least 10)
    assert f"{percent}% of the" in reply.text, reply.text


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(TWO_YEARS))
def test_two_years_run_as_today(tmp_path, monkeypatch, label):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_SHARES, Step(analyze(shares_arguments(TWO_YEARS[label]))),
                    Step(finish("finding", "{a1.share}.")))
    answer = env.model.answer(0)
    assert answer.get("result_id") == "a1", answer
    answered(reply)
    assert LINE not in json.dumps(answer) and LINE not in reply.text
    assert len(job_folders(env)) == 1, "R ran once"
