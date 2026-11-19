"""Charts: docs/S3S-DESIGN.md S6 (one chart per result, PNG, 1600 by 1000 pixels, attached to
the same message, S5) and the floor on charts: a monthly series with any month from 1 to 9 is
drawn by quarter; if a quarter is still hidden, TOO_FINE; a histogram bar or heat map cell
from 1 to 9 is drawn as empty (and the foot line says so).

How a chart looks is not judged. The PNG is read with the standard library
(s3ssupport.png_header, png_distinct_pixels): its signature, its size, and that it is not
blank (more than two different pixel values). "Drawn as empty" is tested without looking at
the chart: two copies that differ only in the count of the one hidden cell (Tuesday at 4
am: 4 records, then 7) must give charts that are the same pixel for pixel, so the hidden
value leaves no trace. The same for a histogram bar from 1 to 9.

Not testable here: that the foot line says so, and that a series is drawn by quarter rather
than by month (both are only on the image). A monthly series with one hidden quarter is not
tested (S6 against S1: QUESTIONS.md, 6); the refused case has more than half its quarters
hidden.
"""
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import (EDGES, MAIN, Q_TREND, StatsEnv, analyze, answered, ask_case, chart_of,
                      job_folders)

KINDS = ["trend_all", "compare_school", "ba_d6", "yn_main", "sh_school", "timing",
         "ages_gender"]


def check_png(path):
    width, height, depth, colour, interlace = T.png_header(path)
    assert Path(path).read_bytes()[:8] == T.PNG_SIGNATURE
    assert (width, height) == (1600, 1000), (width, height)
    assert T.png_distinct_pixels(path, limit=50) > 2, "the chart is blank"


@pytest.mark.needs_r
def test_the_png_reader_on_a_png_made_by_r(tmp_path):
    """No program code: R draws a 1600 x 1000 PNG with ggplot2 and an all-white one; the
    reader gets the size, decodes every row, and tells them apart."""
    script = tmp_path / "draw.R"
    script.write_text(
        'suppressPackageStartupMessages(library(ggplot2))\n'
        'p <- ggplot(data.frame(x = 1:20, y = (1:20)^2), aes(x, y)) + geom_line(colour = '
        '"#2a78d6") + theme_minimal()\n'
        'ggsave(file.path(commandArgs(TRUE)[1], "chart.png"), p, width = 16, height = 10, '
        'dpi = 100)\n'
        'png(file.path(commandArgs(TRUE)[1], "white.png"), width = 1600, height = 1000)\n'
        'plot.new(); invisible(dev.off())\n', encoding="utf-8")
    subprocess.run(["Rscript", str(script), str(tmp_path)], check=True, timeout=120,
                   capture_output=True)
    check_png(tmp_path / "chart.png")
    assert T.png_header(tmp_path / "white.png")[:2] == (1600, 1000)
    assert T.png_distinct_pixels(tmp_path / "white.png") == 1
    assert len(T.png_pixels(tmp_path / "chart.png")) == 1000


@pytest.mark.needs_r
@pytest.mark.parametrize("name", KINDS)
def test_each_kind_has_its_chart(tmp_path, monkeypatch, name):
    """S5 and S6: the chart is attached to the reply (chart_path), is R's chart.png from the
    job folder, a PNG of 1600 by 1000, not blank."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    path = chart_of(reply)
    check_png(path)
    (folder,) = job_folders(env)
    assert (folder / "chart.png").is_file()
    assert (folder / "chart.png").read_bytes() == path.read_bytes()


@pytest.mark.needs_r
def test_a_series_with_hidden_months_fine_by_quarter_is_drawn(tmp_path, monkeypatch):
    """S6: batch Q1 has months from 1 to 9 but every quarter 10 or more: answered, with a
    chart, and no hidden figure in the reply."""
    months, counts, _ = T.monthly(EDGES, T.P5, T.batch("Q1"))
    assert any(1 <= n <= 9 for n in counts)
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    reply = answered(ask_case(env, "trend_q1"))
    check_png(chart_of(reply))
    # S10 answer 15 (added by the planning chat after the automatic check): the result says
    # how the series was drawn, so "by quarter" can be tested without judging the image.
    (folder,) = job_folders(env)
    assert json.loads((folder / "result.json").read_text(encoding="utf-8")).get(
        "chart_points") == "quarter"


@pytest.mark.needs_r
def test_a_series_with_no_hidden_month_is_drawn_by_month(tmp_path, monkeypatch):
    """S10 answer 15: no month of trend_all is from 1 to 9, so its chart is by month."""
    _, counts, _ = T.monthly(T.MAIN, T.P5)
    assert not any(1 <= n <= 9 for n in counts)
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "trend_all"))
    (folder,) = job_folders(env)
    assert json.loads((folder / "result.json").read_text(encoding="utf-8")).get(
        "chart_points") == "month"


def test_a_series_still_hidden_by_quarter_is_too_fine(tmp_path, monkeypatch):
    """S6 and S1: batch Q2 has 11 of its 20 quarters from 1 to 9: TOO_FINE, before R, and no
    result."""
    months, counts, _ = T.monthly(EDGES, T.P5, T.batch("Q2"))
    quarters = [sum(counts[i:i + 3]) for i in range(0, 60, 3)]
    assert sum(1 <= q <= 9 for q in quarters) == 11 and sum(counts) >= 100
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    args = T.analyze_arguments("trend_q1")
    args["filters"] = T.batch("Q2")
    reply = env.ask(Q_TREND, Step(analyze(args)), Step(finish("finding", "{a1.trend}.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "TOO_FINE", answer
    assert job_folders(env) == []
    assert reply.status != "ANSWERED" and reply.chart_path is None


def _extra_rows(n, when, **values):
    base = {"age": "30", "gender": "Male", "district": "2", "shift": "A",
            "adjacent_to_school": "0", "weapon": "0", "data_class": "SYNTHETIC"}
    return [{"id": f"FIXTURE-S-EXTRA-{i:02d}", "event_date_time": when, **base, **values}
            for i in range(n)]


def _chart_rows(tmp_path, monkeypatch, rows, name):
    env = StatsEnv(tmp_path, monkeypatch, rows={MAIN: rows})
    reply = answered(ask_case(env, name))
    return T.png_pixels(chart_of(reply)), reply


@pytest.mark.needs_r
def test_a_hidden_heat_map_cell_leaves_no_trace(tmp_path, monkeypatch):
    """S6: the Tuesday 4 am cell (4 records, then 7) is drawn as empty: the two heat maps are
    the same pixel for pixel; both replies write it `fewer than 10`."""
    rows = T.fixture_rows(MAIN)
    assert date(2025, 3, 4).weekday() == 1  # a Tuesday
    more = rows + _extra_rows(3, "2025-03-04T04:10:00.000")
    a, reply_a = _chart_rows(tmp_path / "a", monkeypatch, rows, "timing")
    b, reply_b = _chart_rows(tmp_path / "b", monkeypatch, more, "timing")
    assert "Tuesday at 4 am (fewer than 10)" in reply_a.text
    assert "Tuesday at 4 am (fewer than 10)" in reply_b.text
    assert a == b, "the hidden cell's count changed the heat map"


@pytest.mark.needs_r
def test_a_hidden_histogram_bar_leaves_no_trace(tmp_path, monkeypatch):
    """S6: a histogram bar from 1 to 9 (the two-year step of the oldest ages) is drawn as
    empty: adding two records to it leaves the histogram the same pixel for pixel."""
    bins = T.truth("ages")["bins"]
    low, n = next((b, n) for b, n in sorted(bins.items(), reverse=True) if 1 <= n <= 7)
    rows = T.fixture_rows(MAIN)
    more = rows + _extra_rows(2, "2024-05-07T15:20:00.000", age=str(low))
    a, _ = _chart_rows(tmp_path / "a", monkeypatch, rows, "ages")
    b, _ = _chart_rows(tmp_path / "b", monkeypatch, more, "ages")
    assert a == b, f"the hidden bar of ages {low} to {low + 1} ({n}, then {n + 2}) left a trace"
