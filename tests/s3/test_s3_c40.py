"""C40 of docs/S3A-DESIGN.md: a chart with counts (county mode). Brief: briefs/S3-R7-A-tests.md.
Tests only; the planning chat makes the change.

When a county turn ends ANSWERED and made no analysis, and its counts hold one count with a
breakdown of two or more groups, or two or more counts with no breakdown, Python draws one bar
chart and attaches it to the reply as an analysis's chart is (`chart_path`, `chart_title`;
Slack uploads it with the text). C40's tests:
- each case of point 1 (a breakdown of 6 groups and of 2; two and three counts, also with a
  compare or a share made from them; a second source with its own unit), and the cases that
  get none: one plain count; a two-way breakdown; a turn with an analysis, whose own chart
  stands;
- a hidden group (a breakdown by gender with 5 female records);
- the title word for word (point 3), the source line (see the gap below);
- the file exists, is a PNG of 1600 by 1000 pixels (point 3) and is `chart.png` in the run
  folder of the turn's first count (point 4);
- Slack uploads it with the reply's text;
- SYNTHETIC mode unchanged;
- the prompt line of point 5 word for word in both county prompts (as amended after
  CHAT-BUILDS-check-3; changed by briefs/S3-R8-A-tests.md).
What the chart shows (chart.json, point 6) is tests/s3/test_s3_gaps_r8.py's (PROOF GAP 5).

GAP (briefs/QUESTIONS.md, S3-R7-A question 4): a chart's content is read from its record, not
the picture, and C40 gives the count chart no record (Part S's charts have result.json's
`chart_labels`, S12 item 5). So what only the picture holds is not tested: the bars, their
order and values, a hidden group's bar left out and its label `<label> (fewer than 10)`, the
subtitle (`Copy of the county's data of <date>.`), the foot line (`<source title>. Recorded
<unit.many>, not people.`) and the look of point 3. The reply carries the title
(`chart_title`), which is checked word for word; the size is read from the PNG's header.

READINGS (also in kit-log/raw/S3-R7-A-notes.txt):
- C40-1 `chart_title` is point 3's title, as an analysis's `chart_title` is its title today
  (`cap(read_as)`).
- C40-2 "two or more counts with no breakdown": every count of the turn has no group_by; a
  compare or a share among the results does not change that (they are not analyses).
- C40-3 (open, question 5) a turn whose counts are one breakdown and one plain count, or two
  breakdowns, is in neither case of point 1 as written. Not tested.
- C40-4 the reply style does not matter ("ends ANSWERED"): the chart comes with the model's
  own text, with the fixed rendering after a failing text, with MOCO_REPLY_STYLE=fixed and
  with MOCO_TALK on.
"""
import re
import sys
from pathlib import Path

import pytest

from p1support import (AGENT_USER, Env, FakeSlack, PNG_SIGNATURE, Step, compare as
                       synthetic_compare, count as synthetic_count, finish, mention, process,
                       slack_settings)
from s3support import (A_ID, C_ID, NAMES, Q_BREAKDOWN, Q_COMPARE, Q_COUNT, SCHOOL, CountyEnv,
                       assert_no_hidden_figure, compare, count, is_, made_rows, share,
                       too_fine, truth, year)

TESTS = Path(__file__).resolve().parents[1]
REPO = TESTS.parent
if str(TESTS / "s3s") not in sys.path:
    sys.path.insert(0, str(TESTS / "s3s"))

import s3ssupport as S  # noqa: E402
from s3sagent import MAIN_ID, StatsEnv, analyze  # noqa: E402

WIDTH, HEIGHT = 1600, 1000

# ---- point 3's titles, written out by hand ---------------------------------------------------

BY_DISTRICT = "Arrest records in 2025, by district"
BY_GENDER = "Arrest records in 2025, by gender"
NEAR_SCHOOL_BY_DISTRICT = "Arrest records within 500 feet of a school in 2025, by district"
ARRESTS_COMPARED = "Arrest records compared"
INTAKE_BY_STATION = "Intake records in 2025, by station"
INTAKE_COMPARED = "Intake records compared"

# ---- point 5: rule 9 of both county prompts --------------------------------------------------

PROMPTS = {"agent_prompt_s3": REPO / "config" / "agent_prompt_s3.md",
           "agent_prompt_s3_talk": REPO / "config" / "agent_prompt_s3_talk.md"}
SYNTHETIC_PROMPTS = {"agent_prompt_v2": REPO / "config" / "agent_prompt_v2.md",
                     "agent_prompt_talk": REPO / "config" / "agent_prompt_talk.md"}
RULE9_TODAY = ("9. If the user wants more about an answer you already sent, or says yes to your "
               "offer of details, call show_details.")
# Changed by briefs/S3-R8-A-tests.md to C40 point 5 as amended on 14 Nov after CHAT-BUILDS-check-3
# (DEFECT 1); the first words ended "count it again with the breakdown that shows it, and a count
# with two or more groups comes with a chart."
# Changed by briefs/S3-R10-A-tests.md to C40 amendment 2 point c (after CHAT-BUILDS-check-4,
# DEFECT 1); the words before ended "as the only count of the reply, and it comes with a chart."
C40_SENTENCE = (" If the person asks for a chart or graph of an answer: for change over time call "
                "analyze with kind trend, whose chart shows every month and the trend; for "
                "anything else count it again with one breakdown that shows it, as the only count "
                "or analysis of the reply, and when that breakdown has two or more groups it "
                "comes with a chart.")
RULE9_C40 = RULE9_TODAY + C40_SENTENCE


# ---- helpers ---------------------------------------------------------------------------------

def png_size(path):
    """(width, height) from a PNG's IHDR chunk, after checking the signature."""
    data = Path(path).read_bytes()
    assert data[:8] == PNG_SIGNATURE, f"not a PNG: {path}"
    assert data[12:16] == b"IHDR", f"no IHDR first: {path}"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def assert_chart(env, reply, title):
    """C40: ANSWERED; the chart is chart.png in the run folder of the first count (point 4), a
    PNG of 1600 by 1000 (point 3); chart_title is the title word for word (point 3); the chart
    is not also among the attachments."""
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.chart_path, f"no chart (C40 point 1): {reply.text}"
    path = Path(reply.chart_path)
    assert path.resolve() == (Path(env.runs_dir) / reply.run_ids[0] / "chart.png").resolve(), \
        (path, reply.run_ids)
    assert path.is_file(), path
    assert png_size(path) == (WIDTH, HEIGHT), png_size(path)
    assert reply.chart_title == title, reply.chart_title
    assert str(path) not in [str(p) for p in (reply.attachments or [])], reply.attachments
    assert_no_hidden_figure(reply.chart_title, "chart_title")
    return path


def assert_no_chart(env, reply):
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.chart_path is None and reply.chart_title is None, \
        (reply.chart_path, reply.chart_title)
    for run_id in reply.run_ids:
        assert not (Path(env.runs_dir) / run_id / "chart.png").exists(), run_id


def counts_turn(env, question, *calls, text="I counted {r1.count}."):
    return env.ask(question, Step(*calls), Step(finish("finding", text)),
                   Step(finish("finding", text)))


# ---- premises ----------------------------------------------------------------------------------

def test_premises():
    """No program code: the breakdowns used have the groups their cases say, none is too fine,
    and today's rule 9 is the line the C40 sentence is added to."""
    assert len(truth("arrests_like", year(2025), [], ["district"])["groups"]) == 6
    assert len(truth("arrests_like", year(2025), [], ["gender"])["groups"]) == 2
    grid = truth("arrests_like", year(2025), [], ["district", "gender"])
    assert not too_fine(list(grid["grid"].values()))
    assert len(truth("coded_like", year(2025), [], ["station"])["groups"]) >= 2
    assert RULE9_C40.startswith(RULE9_TODAY + " ") and RULE9_C40.endswith("comes with a chart.")


# ---- point 1: the cases that get a chart --------------------------------------------------------

def test_a_breakdown_of_six_groups_gets_a_chart(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], ["district"]),
                        text="I counted {r1.count}. {r1.groups}.")
    assert_chart(env, reply, BY_DISTRICT)


def test_a_breakdown_of_two_groups_gets_a_chart(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], ["gender"]),
                        text="I counted {r1.count}. {r1.groups}.")
    assert_chart(env, reply, BY_GENDER)


def test_the_title_is_the_counts_read_as_with_its_filters(tmp_path, monkeypatch):
    """Point 3: the count's read_as (here with a filter), first letter capital, then `, by
    <its dimension>`."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_BREAKDOWN,
                        count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"]),
                        text="I counted {r1.count}. {r1.groups}.")
    (answer,) = env.answers()[:1]
    assert answer["read_as"] == "arrest records within 500 feet of a school in 2025", answer
    assert_chart(env, reply, NEAR_SCHOOL_BY_DISTRICT)


@pytest.mark.parametrize("years_", [(2024, 2025), (2024, 2025, 2026)], ids=["two", "three"])
def test_two_or_more_counts_with_no_breakdown_get_a_chart(tmp_path, monkeypatch, years_):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_COMPARE, *[count(A_ID, year(y)) for y in years_],
                        text=" ".join(f"I counted {{r{i}.count}}." for i in
                                      range(1, len(years_) + 1)))
    assert len(reply.run_ids) == len(years_)
    assert_chart(env, reply, ARRESTS_COMPARED)


def test_two_counts_and_their_compare_get_a_chart(tmp_path, monkeypatch):
    """C40-2: a compare of the two counts is not an analysis."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(count(A_ID, year(2024)), count(A_ID, year(2025))),
                    Step(compare("r1", "r2")), Step(finish("finding", "{r3.compare}.")),
                    Step(finish("finding", "{r3.compare}.")))
    assert [r["kind"] for r in reply.results] == ["count", "count", "compare"], reply.results
    assert_chart(env, reply, ARRESTS_COMPARED)


def test_two_counts_and_their_share_get_a_chart(tmp_path, monkeypatch):
    """C40-2: a share of the two counts is not an analysis."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("What part of the 2025 arrests were near a school?",
                    Step(count(A_ID, year(2025)), count(A_ID, year(2025), [is_(SCHOOL, True)])),
                    Step(share("r2", "r1")), Step(finish("finding", "{r3.share}.")),
                    Step(finish("finding", "{r3.share}.")))
    assert [r["kind"] for r in reply.results] == ["count", "count", "share"], reply.results
    assert_chart(env, reply, ARRESTS_COMPARED)


def test_another_source_names_its_own_unit(tmp_path, monkeypatch):
    """Point 3 with coded_like: its read_as, and `Intake records compared` (its unit.many in
    place of "arrest records")."""
    env = CountyEnv(tmp_path / "by", monkeypatch, names=NAMES)
    reply = counts_turn(env, Q_BREAKDOWN, count(C_ID, year(2025), [], ["station"]),
                        text="I counted {r1.count}. {r1.groups}.")
    assert_chart(env, reply, INTAKE_BY_STATION)
    env = CountyEnv(tmp_path / "two", monkeypatch, names=NAMES)
    reply = counts_turn(env, Q_COMPARE, count(C_ID, year(2025)),
                        count(C_ID, {"year": 2026}),
                        text="I counted {r1.count}. I counted {r2.count}.")
    assert_chart(env, reply, INTAKE_COMPARED)


STYLES = {
    "the model's text": ({}, "I counted {r1.count}. {r1.groups}.", "agent"),
    "the fixed rendering after a failing text": ({}, "Sadly, {r1.count}.", "fallback"),
    "MOCO_REPLY_STYLE fixed": ({"MOCO_REPLY_STYLE": "fixed"}, "I counted {r1.count}.", "fixed"),
    "MOCO_TALK on": ({"MOCO_TALK": "on"}, "Here you go. I counted {r1.count}. {r1.groups}.",
                     "agent"),
}


@pytest.mark.parametrize("style", list(STYLES))
def test_the_chart_comes_whatever_the_reply_style(tmp_path, monkeypatch, style):
    """C40-4."""
    settings, text, want = STYLES[style]
    env = CountyEnv(tmp_path, monkeypatch, **settings)
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], ["district"]), text=text)
    assert reply.reply_style == want, (reply.reply_style, reply.draft_failures)
    assert_chart(env, reply, BY_DISTRICT)


def test_a_breakdown_with_a_hidden_group_gets_a_chart(tmp_path, monkeypatch):
    """Point 2: a value under the floor is never drawn as a height (its bar and its label are
    in the picture only: the GAP above). The chart is made, its title is the title, and
    nothing the reply carries for it holds the hidden figure."""
    rows = made_rows("arrests_like", (30, {}), (5, {"gender": "Female"}))
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], ["gender"]),
                        text="I counted {r1.count}. {r1.groups}.")
    assert "female: fewer than 10" in reply.text.split("\n"), reply.text
    assert_chart(env, reply, BY_GENDER)
    assert not re.search(r"(?<!\d)5(?!\d)", reply.chart_title or "")


# ---- point 1 and 4: the cases that get none --------------------------------------------------------

def test_one_plain_count_gets_no_chart(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_COUNT, count(A_ID, year(2025)))
    assert_no_chart(env, reply)


def test_a_two_way_breakdown_gets_no_chart(tmp_path, monkeypatch):
    """Point 4: a count with two group_by fields gets no chart."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], ["district", "gender"]))
    assert reply.results[0]["grid"] is not None, "premise: a two-way table"
    assert_no_chart(env, reply)


@pytest.mark.needs_r
def test_a_turn_with_an_analysis_keeps_the_analysis_chart(tmp_path, monkeypatch):
    """Point 1: "made no analysis". A breakdown and an analysis in one turn: the analysis's
    chart stands (S5), and the count's run folder gets no chart.png."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask("How did arrests go by shift in 2025, and over the years?",
                    Step(count(MAIN_ID, year(2025), [], ["shift"])),
                    Step(analyze(S.analyze_arguments("trend_all"))),
                    Step(finish("finding", "I counted {r1.count}. {a1.trend}.")),
                    Step(finish("finding", "I counted {r1.count}. {a1.trend}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    (analysis,) = [r for r in reply.results if r["kind"] == "analysis"]
    assert reply.chart_path is not None and Path(reply.chart_path) == Path(analysis["chart"])
    assert reply.chart_title == analysis["read_as"][:1].upper() + analysis["read_as"][1:]
    (run_id,) = reply.run_ids
    assert not (Path(env.runs_dir) / run_id / "chart.png").exists()


# ---- Slack -------------------------------------------------------------------------------------

def test_slack_uploads_the_chart_with_the_replys_text(tmp_path, monkeypatch):
    """C40 point 1: Slack uploads the chart with the text, as an analysis's chart (one upload
    titled chart_title, the reply's text as its comment; the text is not posted again)."""
    env = CountyEnv(tmp_path, monkeypatch)
    made = []

    def agent(question, thread_key, user_id, memory_minutes=None):
        made.append(counts_turn(env, question, count(A_ID, year(2025), [], ["district"]),
                                text="I counted {r1.count}. {r1.groups}."))
        return made[-1]

    settings = slack_settings(tmp_path, MOCO_DATA="county", MOCO_STATE_DIR=str(env.state_dir))
    slack = FakeSlack()
    label = process(mention(f"<@{AGENT_USER}> Break the 2025 arrests down by district."),
                    settings=settings, store=env.store, agent=agent, slack=slack)
    (reply,) = made
    path = assert_chart(env, reply, BY_DISTRICT)
    assert label == "answered", label
    (upload,) = slack.uploads
    assert upload[3:] == (str(path), BY_DISTRICT, reply.text), upload
    assert reply.text not in [p[3] for p in slack.posts], slack.posts


# ---- SYNTHETIC mode unchanged --------------------------------------------------------------------

def test_synthetic_mode_is_unchanged(tmp_path):
    """C40 is county mode only: a SYNTHETIC count keeps its stage 1 chart and title; two counts
    and a compare get no chart, as today (A4)."""
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    env = Env(tmp_path / "one")
    reply = env.ask("How many arrests in 2025 for ages 18 to 25?",
                    Step(synthetic_count(2025, "18_25")),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED"
    assert reply.chart_title == ("Arrest records per month, 2025, ages 18 to 25 (SYNTHETIC test "
                                 "data)"), reply.chart_title
    assert reply.chart_path and Path(reply.chart_path).is_file(), reply.chart_path
    assert Path(reply.chart_path).read_bytes()[:8] == PNG_SIGNATURE
    env = Env(tmp_path / "two")
    reply = env.ask("Compare 2024 and 2025 for people under 18.",
                    Step(synthetic_count(2024, "under_18"), synthetic_count(2025, "under_18")),
                    Step(synthetic_compare("r1", "r2")),
                    Step(finish("finding", "{r3.compare}.")))
    assert reply.status == "ANSWERED"
    assert reply.chart_path is None and reply.chart_title is None


# ---- point 5: the prompt line --------------------------------------------------------------------

def lines(path):
    return path.read_bytes().decode("utf-8").split("\n")


@pytest.mark.parametrize("name", list(PROMPTS))
def test_rule_9_gains_the_chart_sentence_word_for_word(name):
    found = lines(PROMPTS[name])
    assert found.count(RULE9_C40) == 1, f"C40 point 5's rule 9 is not in {name} once"
    assert RULE9_TODAY not in found, f"today's rule 9 is still in {name}"
    assert sum(C40_SENTENCE.strip() in line for line in found) == 1


@pytest.mark.parametrize("name", list(SYNTHETIC_PROMPTS))
def test_the_synthetic_prompts_do_not_get_it(name):
    text = SYNTHETIC_PROMPTS[name].read_text(encoding="utf-8")
    assert C40_SENTENCE.strip() not in text
