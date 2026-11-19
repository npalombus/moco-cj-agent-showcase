"""S2: the window and what R is given (docs/S3S-DESIGN.md).

- Count models use full months only, from the later of coverage_start and the period's
  start, to the last full month in the copy minus drop_newest_months (1). The fixture's
  newest record is 14 October 2026, so its last full month is September 2026 and the models
  end in August 2026. The answer's period phrase names the months used.
- The job folder holds job.json (kind, options, labels, the window) and the input table: for
  T and S counts by month (and group); for L one line per record holding only 0/1 and
  category columns; for timing a weekday-by-hour table; for distribution ages with the group
  column.

Readings: s3ssupport's window (a period starting after the 1st begins at the next month; a
period ending before a month's last day ends at the month before) and s3sagent's (the job
folder holds job.json; the input table is its one CSV). Whether L, S, timing and
distribution use the full-month window is asked (QUESTIONS.md, 13); the cases here use whole
years, where both readings agree.
"""
import re
from datetime import date

import pytest

import s3ssupport as T
from s3sagent import (StatsEnv, UNIT_MANY, answered, ask_case, assert_estimates, assert_line1,
                      input_table, job_folder, read_json)

WINDOWS = {  # case: (first month, last month, months)
    "trend_all": ("January 2021", "December 2025", 60),
    "trend_all_p6": ("January 2021", "August 2026", 68),
    "trend_coverage": ("January 2021", "December 2025", 60),
    "trend_mid": ("February 2021", "November 2025", 58),
    "trend_sep": ("January 2024", "August 2026", 32),
}


def test_the_windows_by_counting():
    """No program code: S2's window for each case."""
    for name, (first, last, n) in WINDOWS.items():
        months = T.window(T.source_json(T.MAIN), T.case(name)["period"])
        assert (T.month_text(months[0]), T.month_text(months[-1]), len(months)) == \
            (first, last, n), name
    assert T.last_full_month() == (2026, 9)
    assert T.last_full_month(date(2026, 9, 30)) == (2026, 9)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", list(WINDOWS))
def test_the_period_phrase_names_the_months_used(tmp_path, monkeypatch, name):
    """S2: full months only; coverage_start; the dropped newest month; the phrase names the
    months used, and the estimate is the one of exactly those months."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name, text="I found that {a1.trend}."))
    first, last, _ = WINDOWS[name]
    assert f"from {first} to {last}" in reply.text.split("\n", 1)[0], reply.text
    assert_line1(reply.text, T.trend_re(T.truth(name), UNIT_MANY, ""), before="I found that ")
    assert_estimates(env, name)


def _ints(column):
    return [int(v) for v in column]


def _columns(header, rows):
    return {h: [r[i] for r in rows] for i, h in enumerate(header)}


def _no_record_traces(folder):
    for path in folder.iterdir():
        if path.suffix in (".json", ".csv", ".tsv", ".txt"):
            text = path.read_text(encoding="utf-8")
            assert "FIXTURE-" not in text, path
            assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text), (path, "a record time")


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["trend_all", "compare_school", "ba_d6", "sh_school"])
def test_counts_by_month_for_t_and_s(tmp_path, monkeypatch, name):
    """S2: for T and S the input table is the counts by month (and group); job.json names
    the kind. READING: a count column holds the window's counts in month order (for two
    groups: stacked, or one column per group); for S the counts of the base add up to the
    records (the part's are a column of their own or a group)."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, name))
    folder = job_folder(env)
    job = read_json(folder / "job.json")
    assert T.case(name)["kind"] in str(job.values()), job
    header, rows = input_table(folder)
    numeric = {h: _ints(v) for h, v in _columns(header, rows).items()
               if v and all(re.fullmatch(r"\d+", x) for x in v)}
    t = T.truth(name)
    if t["kind"] == "trend_compare":
        a, b = t["counts"]["a"], t["counts"]["b"]
        values = list(numeric.values())
        assert a + b in values or b + a in values or (a in values and b in values), header
        assert len(rows) in (len(a), 2 * len(a))
    elif t["kind"] == "shares":
        assert len(rows) in (60, 120), (len(rows), header)
        totals = sorted(sum(v) for v in numeric.values())
        parts = sum(v["part"] for v in t["years"].values())
        assert t["records"] in totals or (parts in totals and t["records"] - parts in totals), \
            (header, totals)
    else:
        assert t["counts"] in list(numeric.values()), (header, rows[:3])
        assert len(rows) == len(t["months"])
    _no_record_traces(folder)


@pytest.mark.needs_r
def test_the_record_table_for_l_holds_only_0_1_and_category_columns(tmp_path, monkeypatch):
    """S2: for L one line per record holding only 0/1 and category columns for the outcome,
    factors and controls: no id, no time, nothing else."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "yn_main"))
    folder = job_folder(env)
    header, rows = input_table(folder)
    t = T.truth("yn_main")
    assert len(rows) == t["records"], (len(rows), t["records"])
    assert len(header) == 1 + 3 + 1, header  # outcome, three factors, one control
    labels = set(T.source_json(T.MAIN)["fields"][3]["values"].values())  # district labels
    for h, values in _columns(header, rows).items():
        found = set(values)
        assert found <= {"0", "1"} or found <= labels, (h, sorted(found)[:5])
    _no_record_traces(folder)


@pytest.mark.needs_r
def test_timing_is_a_weekday_by_hour_table(tmp_path, monkeypatch):
    """S2: a weekday-by-hour table: either a 7 x 24 grid or one line per cell; its counts add
    up to the records and hold the busiest cell's count."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "timing"))
    folder = job_folder(env)
    header, rows = input_table(folder)
    t = T.truth("timing")
    numeric = {h: _ints(v) for h, v in _columns(header, rows).items()
               if v and all(re.fullmatch(r"\d+", x) for x in v)}
    long_form = len(rows) == 168 and any(sum(v) == t["records"] for v in numeric.values())
    grid = len(rows) in (7, 24) and sum(sum(v) for h, v in numeric.items()
                                        if not re.fullmatch(r"(?i)weekday|day|hour|wd|h", h)) \
        == t["records"]
    assert long_form or grid, (header, len(rows))
    assert any(t["busiest_n"] in v for v in numeric.values())
    _no_record_traces(folder)


@pytest.mark.needs_r
def test_distribution_is_ages_with_the_group_column(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "ages_gender"))
    folder = job_folder(env)
    header, rows = input_table(folder)
    t = T.truth("ages_gender")
    assert len(rows) == sum(len(a) for a in t["ages"].values()), (len(rows), header)
    cols = _columns(header, rows)
    ages = [h for h, v in cols.items() if all(re.fullmatch(r"\d+", x) for x in v)]
    groups = [h for h, v in cols.items() if set(v) <= {"female", "male"}]
    assert len(ages) == 1 and len(groups) == 1, header
    assert sorted(map(int, cols[ages[0]])) == sorted(a for v in t["ages"].values() for a in v)
    _no_record_traces(folder)
