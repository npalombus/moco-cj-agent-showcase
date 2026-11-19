"""R9, point 6: no rate, margin, residents figure or count in any tool answer, log line or stored
turn (docs/S3S2-DESIGN.md R9, with Part S's S0 and S9 and Part A's C9: the model never sees a
value, and a stored turn holds specs and slot texts, never a value).

For a rate turn of each breakdown: every message the model is given after the system prompt
(tool answers included) and the stored turns hold no decimal number, no residents figure or
its margin (with or without commas), and no record count of a group or of the whole. Every
log line (all loggers, DEBUG, from the moment the agent is set up, fetch-census included)
holds (R10 point 9; the automatic check's change 5) no rate, margin or ratio at any precision
(s2support.written: rounded or cut to any number of decimals, up to full precision; a value
under 1 is looked for from two decimals on, since a bare `0.4` could be anything), no
residents figure or its margin written as a whole number or with decimals, and no count. For
the case with a group under 10 records (re_2021: 7), the 7 is a figure nowhere, the reply and
`details` included (dates taken out first). Every test starts R.

Brief S3S2-A3 (the second automatic check, kit-log/raw/S3S2-A-autocheck-2.txt, WHAT TO
CHANGE 1 to 3):
- The counts the used line stands on are looked for too (R10 points 4 and 5, R11 point 1: "The
  count appears nowhere else"): the records left out, each not-shown group's records and
  their sum, and the period's whole count (shown + left out + not shown). Those of three
  digits or more as strings (`_values`); those under 100 by the two-run way of the 7: the case
  again with one more record of that kind, and no figure in the tool answers, the messages to
  the model, the stored turns or the log moves with it (`_moved`).
- re_2022 and age_2025 (groups not shown with 60, and 72 and 30 records) are among the CASES.
- In the log, a margin under 1 written with one decimal is caught where it stands next to
  "margin", "moe" or "se" (`_NEXT_TO_MARGIN`); so is its standard error (margin / 1.645).
"""
import json
import logging
import re

import pytest

import s2support as T
from s2agent import S2Env, ask_rate, details_of
from s3sagent import _DECIMAL
from s3support import figures

CASES = ["re_2025", "re_2024_25", "gender_2025", "age_5y", "all_2025", "re_2022", "age_2025"]


def _counts(t):
    """The counts the used line stands on, besides each group's: the records left out, each
    not-shown group's records, their sum, and the period's whole count."""
    small = [t["groups"][g]["n"] for g in t["not_shown"]]
    return [t["left_out"], *small, sum(small), t["records"] + t["left_out"] + sum(small)]


def _values(t):
    """Every number the case's answer may show a person, as it could be written."""
    out = set()
    for v in t["groups"].values():
        for n in (v["n"], v["residents"]):
            out |= {f"{n:,}", str(n)}
        if v["residents_margin"] is not None:
            m = v["residents_margin"]
            out |= {f"{round(m):,}", str(round(m)), f"{m:,.1f}", f"{m:.1f}"}
    for n in (t["records"], *_counts(t)):
        out |= {f"{n:,}", str(n)}
    return {x for x in out if len(x.replace(",", "")) >= 3}   # (two digits stand for too much)


def _check(text, t, where):
    assert not re.search(r"\d+\.\d+", text), f"a decimal number in the {where}: {text[:600]}"
    for value in _values(t):
        assert not re.search(rf"(?<![\w.,]){re.escape(value)}(?![\w,]|\.\d)", text), (
            f"{value} (a count, residents figure or margin) is in the {where}")
    assert "FIXTURE-" not in text, where


# A number standing next to "margin", "moe" or "se" (`margin 0.4`, `moe=0.4`, `se: 0.24`,
# `margin of error ±0.4`, `residents_margin=...`).
_NEXT_TO_MARGIN = re.compile(r"(?i)(?<![a-z])(?:margins?|moes?|ses?)(?![a-z])[^\d\n]{0,12}"
                             r"(\d+\.\d+)")


def _margins_under_1(t):
    """Every rate's and ratio's margin, and its standard error (margin / 1.645), under 1."""
    ms = [v["margin"] for v in t["groups"].values() if v["margin"] is not None]
    ms += [v["margin"] for v in t["ratios"].values()]
    return [x for m in ms for x in (m, m / T.Z90) if x < 1]


def _check_log(logs, t):
    def at_any_precision(value):
        return T.written(logs, value, min_decimals=1 if abs(value) >= 1 else 2)
    near = " ".join(_NEXT_TO_MARGIN.findall(logs))
    for m in _margins_under_1(t):   # one decimal, where a word says it is a margin
        assert not T.written(near, m), ("a margin under 1 in the log, next to margin/moe/se", m)
    for g, v in t["groups"].items():
        assert not at_any_precision(v["rate"]), ("a rate in the log", g, v["rate"])
        if v["margin"] is not None:
            assert not at_any_precision(v["margin"]), ("a rate's margin in the log", g)
        assert not T.written(logs, v["residents"], whole=True), ("residents in the log", g)
        if v["residents_margin"] is not None:
            assert not T.written(logs, v["residents_margin"], whole=True), (
                "a residents margin in the log", g, v["residents_margin"])
    for g, v in t["ratios"].items():
        assert not at_any_precision(v["ratio"]), ("a ratio in the log", g, v["ratio"])
        assert not at_any_precision(v["margin"]), ("a ratio's margin in the log", g)
    for value in _values(t):
        assert not re.search(rf"(?<![\w.,]){re.escape(value)}(?![\w,]|\.\d)", logs), (
            f"{value} is in a log line")


def test_the_log_check_by_hand():
    """No program code: the log line the automatic check wrote is caught, and so is each value
    at one decimal, two, or full precision; a margin under 1 at one decimal next to "margin",
    "moe" or "se", and the period's whole count (4,416) too (brief S3S2-A3); dates and ids are
    not taken for values."""
    t = T.truth("re_2024_25")
    caught = ["rate.R result: Hispanic rate=27.525252525252526 margin=0.3981431437063937 "
              "residents=396000.0 residents_margin=5728.001396647875",
              "rate 27.5", "rate=27.53", "margin 0.40", "residents 396000", "residents 396,000",
              "residents_margin 5728", "ratio=1.8327", "group n=1090",
              "margin 0.4", "Hispanic moe=0.3", "se: 0.2", "margin of error ±0.6",
              "total n=4416"]
    for line in caught:
        with pytest.raises(AssertionError):
            _check_log(line, t)
    _check_log("rate job a1 started 2026-11-13T09:22:10 run 3f2a9c, 4 groups, R 4.4.1, "
               "exit 0", t)


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
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],))
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    for i, call in enumerate(env.model.calls):
        _check(json.dumps(call["messages"][1:], ensure_ascii=False), t,
               f"messages of model call {i}")
    for answer in env.answers():
        _check(json.dumps(answer, ensure_ascii=False), t, "tool answer")
    logs = "\n".join(r.getMessage() for r in caplog.records).replace(str(tmp_path), " ")
    _check_log(logs, t)
    # Changed by briefs/S3-R23-A-tests.md (C61): `sent` is taken out first (_without_sent).
    _check(json.dumps(_without_sent(env.stored_turns(), reply), ensure_ascii=False, default=str),
           t, "stored turn")


EXTRA_ASIAN = {"id": "FIXTURE-R-EXTRA-1", "event_date_time": "2021-06-01T12:00:00.000",
               "age": "30", "gender": "Male", "race": "Asian", "ethnicity": "NON-HISPANIC",
               "district": "1", "adjacent_to_school": "0", "data_class": "SYNTHETIC"}


@pytest.mark.needs_r
def test_a_group_under_ten_is_a_figure_nowhere(tmp_path, monkeypatch, caplog):
    """re_2021: the Asian group has 7 records and is not shown (R10 point 4); 7 stands as a
    figure in no reply, tool answer, `details` or stored turn (dates taken out first, so the
    7th of a month is no figure). For the log, as Part S
    checks a hidden cell (tests/s3s/test_s3s_no_values.py): the case twice, with 7 and then 8
    Asian records; a log that holds the hidden count holds 7 in the first run only and 8 in
    the second only."""
    seen = {}
    for key, extra in (("a", []), ("b", [EXTRA_ASIAN])):
        caplog.clear()
        caplog.set_level(logging.DEBUG)
        rows = {T.RATES: T.fixture_rows(T.RATES) + [dict(r) for r in extra]}
        env = S2Env(tmp_path / key, monkeypatch, rows=rows)
        reply = ask_rate(env, "re_2021")
        hidden = 7 + len(extra)
        texts = {"reply": reply.text,
                 "tool answers": json.dumps(env.answers(), ensure_ascii=False)}
        texts["details"] = details_of(env).text   # a second turn: after the tool answers
        texts["stored turns"] = json.dumps(env.stored_turns(), ensure_ascii=False, default=str)
        for where, text in texts.items():  # figures() takes dates out first
            assert hidden not in figures(_DECIMAL.sub(" ", T.undated(text))), (where, text[:800])
        log = "\n".join(r.getMessage() for r in caplog.records).replace(str(tmp_path), " ")
        seen[key] = set(figures(_DECIMAL.sub(" ", log)))
    assert (7 in seen["a"]) == (7 in seen["b"]), "the hidden count (7) is in the log"
    assert (8 in seen["a"]) == (8 in seen["b"]), "the hidden count (8) is in the log"


# ---- a count under 100: the two-run way (brief S3S2-A3, the second check's change 1) ----------

def _small_kinds(t):
    """[(kind, counts)]: each kind of record whose count is from 1 to 99 (None: the records
    left out; else a group not shown), with the counts under 100 that move when that kind
    gains one record (a not-shown group's own and the not-shown groups' sum). The whole count
    moves too; it has three digits or more and is in `_values`."""
    small = sum(t["groups"][g]["n"] for g in t["not_shown"])
    out = [(None, [t["left_out"]])] if 0 < t["left_out"] < 100 else []
    for g in t["not_shown"]:
        out.append((g, sorted({k for k in (t["groups"][g]["n"], small) if k < 100})))
    return out


def _one_more(t, kind, i):
    """A copy, with a new id, of the first fixture record of that kind in the case's years."""
    src = T.source_json(t["source"])
    row = next(r for r in T.fixture_rows(t["source"])
               if int(r[src["time_field"]][:4]) in t["years"]
               and T.group_of(r, t["by"], src) == kind)
    return dict(row, id=f"FIXTURE-EXTRA-{i}")


def _seen(env, caplog, tmp_path, reply):
    """{place: the figures it holds} (dates and decimals taken out first, as for the 7). Changed
    by briefs/S3-R23-A-tests.md (C61): the stored turns without `sent` (_without_sent)."""
    texts = {"tool answers": json.dumps(env.answers(), ensure_ascii=False),
             "messages to the model": json.dumps([c["messages"][1:] for c in env.model.calls],
                                                 ensure_ascii=False),
             "stored turns": json.dumps(_without_sent(env.stored_turns(), reply),
                                        ensure_ascii=False, default=str),
             "log": "\n".join(r.getMessage() for r in caplog.records).replace(str(tmp_path), " ")}
    return {where: figures(_DECIMAL.sub(" ", T.undated(text))) for where, text in texts.items()}


def _moved(a, b, counts):
    """[(place, figure)] for each count k (and k + 1) that stands as a figure in one run and
    not in the other (a: the case as it is; b: with one more record of that kind)."""
    return [(where, x) for where in a for k in counts for x in (k, k + 1)
            if (x in a[where]) != (x in b[where])]


SMALL_CASES = [name for name in CASES if _small_kinds(T.truth(name))]


@pytest.mark.needs_r
@pytest.mark.parametrize("name", SMALL_CASES)
def test_a_count_under_100_moves_no_figure_the_model_the_log_or_memory_sees(
        tmp_path, monkeypatch, caplog, name):
    """The records left out (re_2025 30, re_2024_25 60, gender_2025 18, re_2022 30, age_2025
    40) and a not-shown group's records (re_2022 Asian, not Hispanic 60; age_2025 aged 55 to 64
    72 and aged 65 and over 30) are under 100, so they cannot be looked for as strings. As the 7
    is (test_a_group_under_ten_is_a_figure_nowhere): the case as it is, then again with one more
    record of each such kind; in the tool answers, the messages to the model, the stored turns
    and the log, no figure moves with the count (k in one run and not the other, or k + 1).
    The reply's used line is not looked at here: it writes these counts (R11 point 1), and
    test_s2_phrases_lines.py holds the reply and `details` to them."""
    t = T.truth(name)
    runs = [("as it is", [], [])] + [
        (f"one more record ({kind or 'left out'})", counts, [_one_more(t, kind, i)])
        for i, (kind, counts) in enumerate(_small_kinds(t), 1)]
    seen = {}
    for i, (key, _, extra) in enumerate(runs):
        caplog.clear()
        caplog.set_level(logging.DEBUG)
        rows = {t["source"]: T.fixture_rows(t["source"]) + extra}
        env = S2Env(tmp_path / f"run{i}", monkeypatch, names=(t["source"],), rows=rows)
        reply = ask_rate(env, name)
        assert reply.status == "ANSWERED", (key, reply.status, reply.reason_code, reply.text)
        seen[key] = _seen(env, caplog, tmp_path, reply)
    for key, counts, _ in runs[1:]:
        moved = _moved(seen["as it is"], seen[key], counts)
        assert not moved, f"{key}: a count under 100 ({counts}) moves a figure in {moved}"
