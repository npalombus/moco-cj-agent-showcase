"""Stage 3 round 10 (brief briefs/S3-R10-A-tests.md): tests for "C40, amendment 2" of
docs/S3A-DESIGN.md and "S14, the order" of docs/S3S-DESIGN.md, the answers to
kit-log/raw/CHAT-BUILDS-check-4.txt; and C28's place (briefs/QUESTIONS.md, S3-R9-A question 4).
Tests only; the planning chat makes the change. All data is SYNTHETIC fixtures; no real figure
is quoted. County turns run with the model stand-in (FakeModel); each chart is read from its
`chart.json` (C40 point 6).

- (a) Two or more plain counts get a chart only when every one is of the same source: two plain
  counts of two sources (also DEFECT 2's turn, the second filtered by a sensitive field, and
  three counts, two of one source): no chart, no chart.png or chart.json, the reply as today;
  two plain counts of one source, with both sources offered: the chart as today.
- (b) Two plain counts of one source, the first not sensitive and the second by gender (sex for
  coded_like): the chart's foot ends with the reply's own sensitive line, the very same string.
- (c) Rule 9's sentence word for word, once, at the end of rule 9 in both county prompts, and
  not in the SYNTHETIC prompts.
- (d) A breakdown with a 0 group: a shown bar of value 0, labelled plainly (no "fewer than"),
  `hidden` false.
- S14's order: one year whose base is under `min_base_year` (also with a part under the floor)
  gets S14's line, and R is not started.
- C28's place: a count under 18 broken down by district, with records of no district, has
  C28's line before the left-out line.

READINGS (also in kit-log/raw/S3-R10-A-notes.txt):
- A2-1. "The reply is as today" (a): today's text, written out by hand: line 1 (the model's
  text filled), the sensitive line when a count has it, and the first answer's source line,
  which names each source in the order of the counts, on one line, then the question.
- A2-2. "Of the same source": the count's `source` (the source id). Both fixtures are offered
  in every (a) and (b) turn, so a one-source chart is drawn with two sources on offer.
- A2-3. (b) "the reply's own sensitive line": the one line of the reply's text that starts
  `These are counts of `. The foot is point 3's base line, one space, then that line.
- A2-4. (d) "labelled plainly": the bar's label is the group's label as the table writes it,
  and `fewer than` is nowhere in chart.json.
- A2-5. S14's order: "one year" is a selection whose months (S2's window) fall in one calendar
  year; the base is the analysis's filters (batch S099 of stats_edges, made with a year of 99
  records); `min_base_year` is read from config/analysis.json. "R is not started" is checked
  as tests/s3s/test_s3s_s14.py checks it (the Rscript stand-in leaves no mark; no job folder).
- A2-6. C28's place: the line comes after the table and before the left-out line of the
  breakdown field, as C10 orders the parts (s3support.reply_re); line 1 is not checked here.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

from p1support import Step, finish
from s3support import (A_ID, C_ID, COPY_DATE_RE, NAMES, Q_BREAKDOWN, Q_COMPARE, CountyEnv, age,
                       assert_reply, check_county_reply, count, is_, left_out_line, made_rows,
                       sensitive_line, source_json, source_re, table_lines, too_fine, truth,
                       year)
from test_s3_c40 import PROMPTS, RULE9_TODAY, SYNTHETIC_PROMPTS, assert_no_chart, counts_turn
from test_s3_gaps_r8 import FLOOR, assert_subtitle, bar, chart_record, foot
from test_s3_round5 import A, C, C28_LINE, phrase, spec

TESTS = Path(__file__).resolve().parents[1]
REPO = TESTS.parent
if str(TESTS / "s3s") not in sys.path:
    sys.path.insert(0, str(TESTS / "s3s"))

import s3ssupport as T  # noqa: E402
from s3sagent import EDGES, EDGES_ID, Q_SHARES, StatsEnv, analyze  # noqa: E402
from test_s3s_engine import stand_in  # noqa: E402
from test_s3s_s14 import LINE as S14_LINE, assert_r_not_started  # noqa: E402

Y24, Y25, Y26 = year(2024), year(2025), year(2026)
SID = {A: A_ID, C: C_ID}
SEX = {A: "gender", C: "sex"}  # the sensitive person field of each fixture


def counts_text(n):
    return " ".join(f"I counted {{r{i}.count}}." for i in range(1, n + 1))


def plain_turn(env, specs, question=Q_COMPARE):
    """One turn of plain counts (round 5's specs), all in one step."""
    return counts_turn(env, question,
                       *[count(SID[s["name"]], s["period"], s["filters"]) for s in specs],
                       text=counts_text(len(specs)))


def two_sources_line(*names):
    """A2-1: the first answer's source line, one sentence per source, then the question."""
    out = ""
    for name in names:
        src = source_json(name)
        out += (re.escape(f"Source: {src['title']} (county open data), copy of ") + COPY_DATE_RE
                + re.escape(f". A count is of {src['unit']['many']}, not people. "))
    return out + re.escape("Want the details, or a different breakdown?")


def sensitive_lines(reply):
    return [line for line in reply.text.split("\n") if line.startswith("These are counts of ")]


# ==== (a) two or more plain counts of two sources: no chart =====================================

TWO_SOURCES = {
    # id: (the counts, in order; the sensitive line's records, or None)
    "arrests and intake, 2025": ([spec(Y25, name=A), spec(Y25, name=C)], None),
    "DEFECT 2's turn: arrests, then intake of women": (
        [spec(Y25, name=A), spec(Y25, [is_("sex", "female")], name=C)], "intake records"),
    "intake first, then arrests": ([spec(Y25, name=C), spec(Y24, name=A)], None),
    "three counts, two of one source": (
        [spec(Y24, name=A), spec(Y25, name=A), spec(Y25, name=C)], None),
}


@pytest.mark.parametrize("case", list(TWO_SOURCES))
def test_a_plain_counts_of_two_sources_get_no_chart(tmp_path, monkeypatch, case):
    specs, many = TWO_SOURCES[case]
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = plain_turn(env, specs)
    assert [r["kind"] for r in reply.results] == ["count"] * len(specs), reply.results
    assert len({r["source"] for r in reply.results}) == 2, "premise: two sources"
    assert_no_chart(env, reply)
    assert list(Path(env.runs_dir).glob("*/chart.json")) == [], "a chart.json was written"
    assert list(Path(env.runs_dir).glob("*/chart.png")) == [], "a chart.png was written"
    check_county_reply(reply)


@pytest.mark.parametrize("case", list(TWO_SOURCES))
def test_a_plain_counts_of_two_sources_the_reply_as_today(tmp_path, monkeypatch, case):
    """A2-1: line 1, the sensitive line when a count has it, the source line."""
    specs, many = TWO_SOURCES[case]
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = plain_turn(env, specs)
    assert reply.reply_style == "agent", (reply.reply_style, reply.draft_failures)
    names = list(dict.fromkeys(s["name"] for s in specs))
    assert_reply(reply.text, " ".join(f"I counted {phrase(s)}." for s in specs),
                 sensitive=sensitive_line(many) if many else None,
                 source=two_sources_line(*names))


ONE_SOURCE = {
    # id: (the counts, in order, title)
    "arrests 2024 and 2025": ([spec(Y24, name=A), spec(Y25, name=A)], "Arrest records compared"),
    "intake 2025 and 2026": ([spec(Y25, name=C), spec(Y26, name=C)], "Intake records compared"),
    "three counts of arrests": ([spec(Y24, name=A), spec(Y25, name=A),
                                 spec(Y25, [is_("district", "district 3")], name=A)],
                                "Arrest records compared"),
}


@pytest.mark.parametrize("case", list(ONE_SOURCE))
def test_a_plain_counts_of_one_source_get_the_chart_as_today(tmp_path, monkeypatch, case):
    """A2-2: both sources offered, every count of one: the chart of C40 points 2, 3 and 6."""
    specs, title = ONE_SOURCE[case]
    (name,) = {s["name"] for s in specs}
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = plain_turn(env, specs)
    record = chart_record(env, reply)
    assert record["title"] == title == reply.chart_title, (record["title"], reply.chart_title)
    assert_subtitle(record)
    read_as = [a["read_as"] for a in env.answers() if "result_id" in a]
    totals = [truth(name, s["period"], s["filters"])["total"] for s in specs]
    assert record["bars"] == [bar(label, n) for label, n in zip(read_as, totals)], record["bars"]
    assert record["foot"] == foot(env.source(name), False)
    check_county_reply(reply)


# ==== (b) the chart's sensitive line is the reply's own ========================================

@pytest.mark.parametrize("name", [A, C])
def test_b_the_foot_ends_with_the_replys_own_sensitive_line(tmp_path, monkeypatch, name):
    """Two plain counts of one source, the first not sensitive, the second by gender (sex):
    the reply carries one sensitive line, and the chart's foot ends with that very string."""
    specs = [spec(Y25, name=name), spec(Y25, [is_(SEX[name], "female")], name=name)]
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = plain_turn(env, specs)
    src = env.source(name)
    (line,) = sensitive_lines(reply)
    assert line == sensitive_line(src["unit"]["many"]), line
    record = chart_record(env, reply)
    assert record["foot"].endswith(" " + line), (record["foot"], line)
    assert record["foot"] == f"{src['title']}. Recorded {src['unit']['many']}, not people. {line}"
    check_county_reply(reply)


# ==== (c) rule 9's sentence word for word =======================================================

# C40 amendment 2 point c, written out by hand.
C40_A2_SENTENCE = (" If the person asks for a chart or graph of an answer: for change over time "
                   "call analyze with kind trend, whose chart shows every month and the trend; "
                   "for anything else count it again with one breakdown that shows it, as the "
                   "only count or analysis of the reply, and when that breakdown has two or more "
                   "groups it comes with a chart.")
# C40 point 5 as amended after CHAT-BUILDS-check-3, which amendment 2 replaces.
C40_A1_SENTENCE = (" If the person asks for a chart or graph of an answer: for change over time "
                   "call analyze with kind trend, whose chart shows every month and the trend; "
                   "for anything else count it again with one breakdown that shows it, as the "
                   "only count of the reply, and it comes with a chart.")


def prompt_lines(path):
    return path.read_bytes().decode("utf-8").split("\n")


def test_c_premise_the_two_sentences_differ_only_where_amendment_2_says():
    assert C40_A1_SENTENCE.replace("only count of the reply, and it comes", "only count or "
                                   "analysis of the reply, and when that breakdown has two or "
                                   "more groups it comes") == C40_A2_SENTENCE


@pytest.mark.parametrize("name", list(PROMPTS))
def test_c_rule_9_ends_with_amendment_2s_sentence_once(name):
    found = prompt_lines(PROMPTS[name])
    rule9 = [line for line in found if line.startswith("9. ")]
    assert rule9 == [RULE9_TODAY + C40_A2_SENTENCE], f"rule 9 of {name}: {rule9}"
    text = "\n".join(found)
    assert text.count(C40_A2_SENTENCE.strip()) == 1, f"the sentence is not once in {name}"
    assert C40_A1_SENTENCE.strip() not in text, f"the sentence it replaces is still in {name}"


@pytest.mark.parametrize("name", list(SYNTHETIC_PROMPTS))
def test_c_the_synthetic_prompts_do_not_get_it(name):
    text = SYNTHETIC_PROMPTS[name].read_text(encoding="utf-8")
    assert C40_A2_SENTENCE.strip() not in text
    assert "If the person asks for a chart or graph" not in text


# ==== (d) a group with 0 records is a shown bar of value 0 =====================================

ZERO = {
    # id: (made_rows groups, the breakdown field, the 0 group's label, title)
    "district 3 with no record among five shown": (
        ((12, {"district": "1"}), (12, {"district": "2"}), (12, {"district": "4"}), (30, {}),
         (12, {"district": "6"})), "district", "district 3", "Arrest records in 2025, by district"),
    "no female record": (((30, {}),), "gender", "female", "Arrest records in 2025, by gender"),
}


@pytest.mark.parametrize("case", list(ZERO))
def test_d_a_zero_group_is_a_shown_bar_of_value_0_labelled_plainly(tmp_path, monkeypatch, case):
    made, by, label, title = ZERO[case]
    rows = made_rows("arrests_like", *made)
    groups = truth("arrests_like", Y25, [], [by], rows=rows)["groups"]
    assert groups[label] == 0 and not too_fine(list(groups.values())), dict(groups)
    assert not any(1 <= n < FLOOR for n in groups.values()), "premise: nothing hidden"
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, Y25, [], [by]),
                        text="I counted {r1.count}. {r1.groups}.")
    assert f"{label}: 0" in reply.text.split("\n"), reply.text
    assert table_lines(groups) == [line for line in reply.text.split("\n")
                                   if line in table_lines(groups)], reply.text
    record = chart_record(env, reply)
    assert record["title"] == title
    assert record["bars"] == [{"label": k, "value": n, "hidden": False}
                              for k, n in groups.items()], record["bars"]
    (zero,) = [b for b in record["bars"] if b["value"] == 0]
    assert zero == {"label": label, "value": 0, "hidden": False}, zero
    assert "fewer than" not in json.dumps(record), record
    check_county_reply(reply)


# ==== S14's order: the years check comes first ==================================================

MIN_BASE_YEAR = json.loads((REPO / "config" / "analysis.json").read_text(encoding="utf-8"))[
    "min_base_year"]
S099 = T.batch("S099")
ORDER = {
    # id: (the period, the part is under the floor)
    "2023, a base of 99": ({"year": 2023}, False),
    "January to March 2023, a base under 100 and a part under 10": (
        {"year": 2023, "months": {"from": 1, "to": 3}}, True),
}


def shares_arguments(period, filters=S099):
    return {"kind": "shares", "source": EDGES_ID, "period": period, "filters": filters,
            "options": {"part": [T.is_(T.SCHOOL, True)]}}


def base_and_part(period, filters=S099):
    """No program code: the base and the part in each calendar year of S2's window."""
    src = T.source_json(EDGES)
    months = T.window(src, period)
    rows, _ = T.select(EDGES, date(*months[0], 1), T.last_day(*months[-1]), filters,
                       [T.SCHOOL])
    out = {}
    for r in rows:
        y = T.row_time(r, src)[0].year
        n, k = out.get(y, (0, 0))
        out[y] = (n + 1, k + (r.get(T.SCHOOL) == "1"))
    return out


def edges_env(tmp_path, monkeypatch):
    """StatsEnv of stats_edges whose Rscript is the stand-in (tests/s3s/test_s3s_s14.py)."""
    marks = tmp_path / "r_started.txt"
    rscript = stand_in(tmp_path, f'echo "$last" >> "{marks}"; exit 1')
    monkeypatch.setenv("MOCO_RSCRIPT", str(rscript))
    return StatsEnv(tmp_path, monkeypatch, names=(EDGES,), MOCO_RSCRIPT=str(rscript)), marks


@pytest.mark.parametrize("case", list(ORDER))
def test_s14_order_premise_one_year_and_its_base_under_min_base_year(case):
    period, hidden_part = ORDER[case]
    years = base_and_part(period)
    assert len(years) == 1, years
    ((n, k),) = years.values()
    assert n < MIN_BASE_YEAR, years
    assert (1 <= k < FLOOR) is hidden_part, years


@pytest.mark.parametrize("case", list(ORDER))
def test_s14_order_one_year_with_a_small_base_gets_s14s_line_and_r_is_not_started(
        tmp_path, monkeypatch, case):
    period, _ = ORDER[case]
    env, marks = edges_env(tmp_path, monkeypatch)
    reply = env.ask(Q_SHARES, Step(analyze(shares_arguments(period))),
                    Step(finish("finding", "I could not run that.")))
    assert_r_not_started(env, marks)
    answer = env.model.answer(0)
    assert answer == {"error": "TOO_LITTLE", "rule": "years", "why": S14_LINE}, answer
    assert (reply.reason_code, reply.text) == ("TOO_LITTLE", S14_LINE), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.status != "ANSWERED" and list(reply.run_ids) == []


def test_s14_order_premise_two_years_of_the_same_base_are_refused_for_the_base(tmp_path,
                                                                                monkeypatch):
    """The base check is reached when the years allow it: 2023 and 2024 of the same batch are
    refused TOO_LITTLE for the base (not S14's line), before R."""
    period = {"from": "2023-01-01", "to": "2024-12-31"}
    assert sorted(base_and_part(period)) == [2023, 2024]
    env, marks = edges_env(tmp_path, monkeypatch)
    env.ask(Q_SHARES, Step(analyze(shares_arguments(period))),
            Step(finish("finding", "I could not run that.")))
    assert_r_not_started(env, marks)
    answer = env.model.answer(0)
    assert answer.get("error") == "TOO_LITTLE" and answer.get("why") != S14_LINE, answer
    assert str(MIN_BASE_YEAR) in answer.get("why", ""), answer


# ==== C28's place: before the left-out line ====================================================

def test_c28_before_the_left_out_line_of_a_breakdown(tmp_path, monkeypatch):
    """16 alone is refused (C8.4); under 18 by district is counted, with 11 records of no
    district: the table, then C28's line, then the left-out line, then the source line."""
    made = [(12, {"age": "16", "district": d}) for d in "123456"] + \
        [(11, {"age": "16", "district": None})]
    rows = made_rows("arrests_like", *made)
    under_18 = [age(None, 17)]
    truth_ = truth("arrests_like", Y25, under_18, ["district"], rows=rows)
    assert truth_["left_out"] == {"age": 0, "district": 11}, truth_["left_out"]
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, Y25, [age(16, 16)]),
                                      count(A_ID, Y25, under_18, ["district"])),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    assert env.model.answer(0, 0).get("error") == "NOT_ALLOWED", env.model.answer(0, 0)
    assert env.model.answer(0, 1).get("result_id") == "r1", env.model.answer(0, 1)
    assert_reply(reply.text, re.compile(r"[^\n]+"), table=table_lines(truth_["groups"]),
                 left_out=[C28_LINE, left_out_line(11, "district")], source=source_re(A))
    assert reply.text.count(C28_LINE) == 1, reply.text
    text = reply.text
    assert text.index(C28_LINE) < text.index(left_out_line(11, "district")), text
    check_county_reply(reply)
