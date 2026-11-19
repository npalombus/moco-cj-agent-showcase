"""No estimate, row or hidden figure anywhere but the reply: docs/S3S-DESIGN.md S0 ("The model
... never sees an estimate"), S1 (the model is answered with no value), S9 ("no estimate, row
or hidden figure in any tool answer, log line or stored turn"), with C1 and C9 of
docs/S3A-DESIGN.md (a stored turn holds specs and slot texts, never a value).

For a turn of each kind: every message the model is given (tool answers included), every log
line (all loggers, DEBUG), and the stored turn (memory) hold no decimal number at all, no
estimate or interval end as R or the reply writes it, no record count of the analysis, no
fixture id or record time, and no hidden figure (the timing case's quietest cell is 4).
"""
import json
import logging
import re

import pytest

import s3ssupport as T
from s3sagent import MAIN, StatsEnv, _DECIMAL, answered, ask_case, assert_no_hidden_stat_figure
from s3support import figures

CASES = ["trend_all", "compare_school", "ba_d6", "yn_main", "sh_school", "timing", "ages"]


def _forms(value):
    out = set()
    for d in (1, 2, 3):
        out.add(f"{value:.{d}f}")
        out.add(f"{abs(value):.{d}f}")
    return {x for x in out if x not in ("0.0", "0.00", "0.000", "1.0", "1.00", "1.000")}


def _row_traces(rows):
    times = {r["event_date_time"][:16] for r in rows}
    return times


def _check(text, name, where, times):
    t = T.truth(name)
    assert "FIXTURE-" not in text, where
    assert not re.search(r"\d+\.\d+", text), f"a decimal number in the {where}: {text[:500]}"
    for est in t["estimates"]:
        for v in (est["estimate"], est["low"], est["high"]):
            for form in _forms(v):
                assert form not in text, (where, form)
    assert f"{t['records']:,}" not in text and not re.search(rf"\b{t['records']}\b", text), where
    assert not any(stamp in text for stamp in times), f"a record's time in the {where}"


def _without_sent(turns, reply):
    """The stored turns without `sent`. Added by briefs/S3-R23-A-tests.md: by C61 points 4 and 6 of
    docs/S3A-DESIGN.md the memory's `sent` is the reply as it was sent (cut to 600 characters),
    figures and all, and it is the only part of the stored turn that may hold one: it must be the
    reply (or its start, then ` ...`), and the rest of the turn is checked as strictly as before."""
    out = []
    for turn in turns:
        turn = dict(turn)
        sent = turn.pop("sent", None)
        if sent is not None:
            head = sent[:-4] if sent.endswith(" ...") else sent
            assert reply.text.startswith(head) and (head == sent or len(head) <= 600), sent
        out.append(turn)
    return out


@pytest.mark.needs_r
@pytest.mark.parametrize("name", CASES)
def test_no_value_reaches_the_model_the_log_or_memory(tmp_path, monkeypatch, caplog, name):
    caplog.set_level(logging.DEBUG)
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    times = _row_traces(T.fixture_rows(T.MAIN))
    for i, call in enumerate(env.model.calls):
        given = json.dumps(call["messages"][1:], ensure_ascii=False)  # the system prompt aside
        _check(given, name, f"messages of model call {i}", times)
    logs = "\n".join(r.getMessage() for r in caplog.records)
    for est in T.truth(name)["estimates"]:
        for v in (est["estimate"], est["low"], est["high"]):
            for form in _forms(v):
                assert form not in logs, ("log", form)
    assert "FIXTURE-" not in logs and not any(s in logs for s in times)
    # Changed by briefs/S3-R23-A-tests.md (C61): `sent` is taken out first (_without_sent).
    stored = json.dumps(_without_sent(env.stored_turns(), reply), ensure_ascii=False, default=str)
    _check(stored, name, "stored turn", times)
    assert_no_hidden_stat_figure(reply.text)
    if name == "timing":  # the quietest cell holds 4 records: never a figure outside the reply
        for turn in env.stored_turns():
            text = json.dumps(turn.get("results"), ensure_ascii=False)
            assert 4 not in figures(text), text
        for call in env.model.calls:
            for m in call["messages"][1:]:
                if m.get("role") == "tool":
                    assert 4 not in figures(m["content"]), m["content"]
        # S9, "no ... hidden figure in any ... log line" (added by the planning chat after
        # the automatic check): which cell is busiest or quietest is a result, so no log
        # line names a weekday, and so none can hold the hidden cell or its count.
        for record in caplog.records:
            line = record.getMessage()
            assert not re.search(r"\b(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b", line), line


def _extra_rows(n, when):
    """n more made-up records at `when` (the rows test_s3s_charts.py adds to a cell)."""
    base = {"age": "30", "gender": "Male", "district": "2", "shift": "A",
            "adjacent_to_school": "0", "weapon": "0", "data_class": "SYNTHETIC"}
    return [{"id": f"FIXTURE-S-EXTRA-{i:02d}", "event_date_time": when, **base}
            for i in range(n)]


@pytest.mark.needs_r
def test_the_log_does_not_depend_on_a_hidden_cell(tmp_path, monkeypatch, caplog):
    """S9, "no ... hidden figure in any ... log line". Written by the planning chat exactly as
    the second automatic check specified (kit-log/raw/S3S-A-autocheck-2.txt): the timing case
    twice, once with the fixture rows (the Tuesday 4 am cell holds 4 records) and once with
    3 more records in that cell (7). A build that logs the hidden count has the figure 4 in
    the first run's log only and 7 in the second's only; a correct build's log is the same
    in this respect, whatever else it holds (an R version, a path)."""
    caplog.set_level(logging.DEBUG)
    rows = T.fixture_rows(MAIN)
    more = rows + _extra_rows(3, "2025-03-04T04:10:00.000")
    seen = {}
    for key, data in (("a", rows), ("b", more)):
        caplog.clear()
        env = StatsEnv(tmp_path / key, monkeypatch, rows={MAIN: data})
        reply = answered(ask_case(env, "timing"))
        assert "Tuesday at 4 am (fewer than 10)" in reply.text, reply.text
        log = "\n".join(r.getMessage() for r in caplog.records).replace(str(tmp_path), " ")
        seen[key] = set(figures(_DECIMAL.sub(" ", log)))
    assert (4 in seen["a"]) == (4 in seen["b"]), "the hidden cell's count (4) is in the log"
    assert (7 in seen["a"]) == (7 in seen["b"]), "the hidden cell's count (7) is in the log"

