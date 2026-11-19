"""R9, point 8: with no `rate` call, nothing a user or a test can see changes (docs/S3S2-DESIGN.md
R9). These tests describe today and pass today; after the build they must still pass.

Each compares two agents that differ in one thing the build brings, asked the same question:
- a source file marked "rates": true against the same file unmarked (R2's mark);
- Census copies made by fetch-census against none (once fetch-census exists, and then it must
  have made a copy of every year; until then both agents have none, which is today).
Compared: the reply, Python's answers to the model, the tools offered, and for counts the
stored turn. The source is Part S's main fixture (stats_like). The Part S trend starts R.
"""
import json

import pytest

import s2support as T
from p1support import Step, call, decline, finish
from s2agent import (MAIN, MAIN_ID, FakeCensus, S2Env, census_folder, holds,
                     run_fetch_census, total_text)
from s3support import count, year

Q_COUNT = "How many arrests were there in 2025?"
TREND = {"kind": "trend", "source": MAIN_ID,
         "period": {"from": "2021-01-01", "to": "2025-12-31"}, "filters": []}


def _turns(env):
    """The same questions in every agent: a count, a count by gender, about the data, a
    declined question, and the stored turns afterwards."""
    out = {}
    reply = env.ask(Q_COUNT, Step(count(MAIN_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    out["count"] = (reply.status, reply.reason_code, reply.text, env.answers(),
                    sorted(env.model.tools_offered(0)))
    reply = env.ask("Break 2025 down by gender.",
                    Step(count(MAIN_ID, year(2025), [], ["gender"])),
                    Step(finish("finding", "I counted {r1.count}.")))
    out["by gender"] = (reply.status, reply.text, env.answers())
    reply = env.ask("What data do you have?", Step(call("describe_data", {})),
                    Step(finish("about_data", "{f1}.")))
    out["about"] = (reply.status, reply.text, env.answers())
    reply = env.ask("Who will win the game?", Step(decline("UNRECOGNIZED_QUESTION")))
    out["declined"] = (reply.status, reply.reason_code, reply.text)
    out["tools"] = json.dumps(env.model.calls[0]["tools"], sort_keys=True)
    out["stored"] = [{k: _no_run_ids(t.get(k)) for k in ("status", "reason_code", "results",
                                                          "spec", "slots")}
                     for t in env.stored_turns()]
    return out


def _no_run_ids(value):
    """A stored turn without its run ids (new for every run)."""
    if isinstance(value, dict):
        return {k: _no_run_ids(v) for k, v in value.items() if k != "run_id"}
    if isinstance(value, list):
        return [_no_run_ids(v) for v in value]
    return value


def _with_census(env, monkeypatch):
    """Census copies when fetch-census exists (none today). Once it is a command, it must have
    made a copy for every year, so the comparison is not empty (R10 point 9; the automatic
    check's change 7)."""
    run = run_fetch_census(monkeypatch, env.state_dir, FakeCensus())
    if run.code == 2 and "invalid choice" in run.text:
        return False
    for year in T.YEARS:
        assert holds(census_folder(env.state_dir, year), total_text(year)), (
            f"fetch-census made no copy of {year}, so nothing is compared:\n{run.text}")
    return True


def test_the_rates_mark_changes_nothing_without_a_rate_call(tmp_path, monkeypatch):
    plain = _turns(S2Env(tmp_path / "plain", monkeypatch, names=(MAIN,), mark=(), census=False))
    marked = _turns(S2Env(tmp_path / "marked", monkeypatch, names=(MAIN,), census=False))
    assert marked.keys() == plain.keys()
    for key in plain:
        assert marked[key] == plain[key], key


def test_census_copies_change_nothing_without_a_rate_call(tmp_path, monkeypatch):
    none = _turns(S2Env(tmp_path / "none", monkeypatch, names=(MAIN,), census=False))
    env = S2Env(tmp_path / "census", monkeypatch, names=(MAIN,), census=False)
    _with_census(env, monkeypatch)
    some = _turns(env)
    for key in none:
        assert some[key] == none[key], key


@pytest.mark.needs_r
def test_a_part_s_analysis_is_the_same(tmp_path, monkeypatch):
    """A Part S trend on the marked source with Census copies (once they can be made) reads
    exactly as on the unmarked source without them."""
    replies = {}
    for key, mark in (("plain", ()), ("marked", None)):
        env = S2Env(tmp_path / key, monkeypatch, names=(MAIN,), mark=mark, census=False)
        if mark is None:
            _with_census(env, monkeypatch)
        reply = env.ask("Are arrests going up over the years?", Step(call("analyze", TREND)),
                        Step(finish("finding", "I found that {a1.trend}.")))
        assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
        replies[key] = (reply.text, env.answers(), reply.reply_style)
    assert replies["marked"] == replies["plain"]


def test_the_stand_ins_do_not_change_the_fixture():
    """No program code: the marked source differs from Part S's file only by the mark."""
    plain = T.source_json(MAIN)
    marked = T.source_json(MAIN)
    T.marked(marked)
    assert "rates" not in plain and {k: v for k, v in marked.items() if k != "rates"} == plain
    assert marked["rates"] is True
