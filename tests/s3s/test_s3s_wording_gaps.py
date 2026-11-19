"""Two proof gaps of the S11 build (brief S3S-R2b-A; kit-log/raw/CHAT-BUILDS-check-2.txt,
PROOF GAP 1 and PROOF GAP 3, breaks S11-9 and S11-10). Tests only.

- PROOF GAP 1 (S11 2b and 2c with C8.1): a trend answer and a before-and-after answer whose
  yearly table has a year of 1 to 9 records: a whole year (2022) and a first year the
  window covers in part, so that 2c's label is on the same line (two months, `2021
  (November to December)`; one month, `2021 (December)`, S11 answer 4). In the reply, in
  the fixed rendering and in `details`: that line says `fewer than 10`, as C8 writes a
  hidden count; the count is nowhere a figure; the hidden line of 2b is there. A year with
  0 and a year with exactly 10 are written as numbers (C8.1: 0 is shown as `0`).
- PROOF GAP 3 (S11 answer 7): with MOCO_TALK on, a finding that fills k odds slots (k = 3
  and k = 4) may have the larger of 4 and k + 2 fact sentences and the larger of 700 and
  200 k + 200 characters once filled; one fact sentence more, or one character more, is
  refused as T2's check refuses it today (Python's REWRITE answer with exactly SHAPE). With
  k = 1 the limits are today's 4 and 700.
  Changed by briefs/S3-R7-A-tests.md (C38 of docs/S3A-DESIGN.md: in county mode with MOCO_TALK
  on, SHAPE counts only the model's own words, at most 400 characters of them, and no longer
  the fact sentences or the length once filled). These turns are county mode with MOCO_TALK
  on, so the texts with one fact sentence more now pass, and the character texts are judged
  by their own words alone (listed in kit-log/raw/S3-R7-A-notes.txt).

The data of PROOF GAP 1 is SYNTHETIC: rows made here in the form of the Part S fixture
stats_like (ids FIXTURE-G-..., data_class SYNTHETIC, one district, no field missing),
served by the fake transport instead of the fixture's rows, with the fixture's own anchor
row (its newest record, 14 October 2026), so that S2's window ends in August 2026 as for
the fixture. Every count below is made up.

READINGS (each in kit-log/raw/S3S-R2b-A-notes.txt):
- `details` and the hidden line (asked in briefs/QUESTIONS.md, both accepted at that one
  place): S11 2b puts C8.2's line on "a statistical reply"; S7 lists what `details` shows
  and does not name it; C8.1 says only that the floor covers `details`. Today's `details`
  states the floor in its limits (`- Counts under 10 are never shown, in a table or on a
  chart.`) and the page in its data line. Either that or C8.2's line is accepted there.
- Line 1 of the PROOF GAP 1 replies is not checked word by word: its estimates are not this
  file's subject (the phrases are checked against the truth helper in the other files), and
  the made-up series is only there to put a small year in the table. It is checked for no
  hidden figure like the rest. The fit line is accepted when it comes, in its place (S5.2).
- PROOF GAP 3, five fact sentences with one odds slot: a turn has at most two analyses
  (S1), and a yes_no and a before_after give four slots without a second odds slot, so the
  fifth is a count's `{r1.count}` in the same turn (county mode offers both tools).
- The texts refused for one fact sentence too many are within the character limit once
  filled (a premise below, from the hand strings of test_s3s_wording.py), so that the
  sentence limit alone refuses them.
"""
import re
import sys
from datetime import date
from pathlib import Path

import pytest

import s3ssupport as T
from p1support import Step, finish, show_details
from s3sagent import MAIN, MAIN_ID, Q_BEFORE_AFTER, Q_TREND, Q_YES_NO, SEP, StatsEnv, analyze, \
    answered, first_source
from s3support import count, figures
from test_s3s_wording import BEND, arguments, filled_length, truth

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "t"))
from tsupport import FINDING_CODES, check_cases, first_try, mixed_faults, padded, \
    split_sentences, thread  # noqa: E402

SRC = T.source_json(MAIN)
FLOOR = SRC["floor"]
HIDDEN_RE = T.hidden_line_re(SRC)
ASSOC_RE = re.escape(T.association_line("arrest records"))
FIT_RE = (r"The last six months were about \d+\.\d% (?:below|above) the trend line, so a "
          r"straight line describes the recent period poorly\.")
FLOOR_LIMIT = "- Counts under 10 are never shown, in a table or on a chart."  # details today


# ==== PROOF GAP 1: a yearly count from 1 to 9 ======================================================

# SYNTHETIC monthly counts, (year, month): records; every other month has none. 2021 and 2022
# hold 4 and 7 (hidden), 2023 none, 2024 exactly 10, then a busy 2025 and 2026.
SPARSE = {(2021, 12): 4, (2022, 6): 7, (2024, 10): 10,
          **{(2025, m): 10 for m in range(1, 13)}, **{(2026, m): 20 for m in range(1, 10)}}
HIDDEN_COUNTS = (4, 7)

CASES = {
    # the window: November 2021 to August 2026 (S2: the copy's newest full month, September
    # 2026, is dropped), so 2021 is two months and 2026 eight
    "trend": dict(arguments={"kind": "trend", "source": MAIN_ID,
                             "period": {"from": "2021-11-01", "to": "2026-08-31"},
                             "filters": []},
                  question=Q_TREND, text="I found that {a1.trend}.",
                  months=((2021, 11), (2026, 8)), records=301,
                  lines=["2021 (November to December): fewer than 10", "2022: fewer than 10",
                         "2023: 0", "2024: 10", "2025: 120", "2026 (January to August): 160"]),
    # December 2021 to January 2026, the date in the middle (25 months on each side): the
    # first and the last year are one month each (S11 answer 4)
    "before_after": dict(arguments={"kind": "before_after", "source": MAIN_ID,
                                    "period": {"from": "2021-12-01", "to": "2026-01-31"},
                                    "filters": [], "options": {"date": "2024-01-01"}},
                         question=Q_BEFORE_AFTER, text="{a1.step}. {a1.bend}.",
                         months=((2021, 12), (2026, 1)), records=161,
                         lines=["2021 (December): fewer than 10", "2022: fewer than 10",
                                "2023: 0", "2024: 10", "2025: 120", "2026 (January): 20"]),
}


def sparse_rows():
    anchor = [r for r in T.fixture_rows(MAIN) if r["id"] == "FIXTURE-S-ANCHOR"]
    assert len(anchor) == 1 and anchor[0]["event_date_time"].startswith("2026-10-14")
    rows, serial = [], 0
    for (y, m), n in SPARSE.items():
        for i in range(n):
            serial += 1
            rows.append({"id": f"FIXTURE-G-{serial:05d}",
                         "event_date_time": f"{y}-{m:02d}-{i % 28 + 1:02d}T{(7 * i) % 24:02d}"
                                            f":15:00.000",
                         "age": "30", "gender": "Male", "district": "1", "shift": "A",
                         "adjacent_to_school": "0", "weapon": "0", "data_class": "SYNTHETIC"})
    return rows + anchor


def yearly(case):
    """The case's yearly totals over its window, from the rows (no program code)."""
    months = T.month_range(*CASES[case]["months"])
    out = {}
    for row in sparse_rows():
        day = date.fromisoformat(row["event_date_time"][:10])
        if (day.year, day.month) in months:
            out[day.year] = out.get(day.year, 0) + 1
    return {y: out.get(y, 0) for y in sorted({y for y, _ in months})}


def no_hidden_count(text, where):
    """The hidden yearly counts stand nowhere as a figure (decimals and `95%` taken out, as
    s3sagent.assert_no_hidden_stat_figure does)."""
    found = figures(re.sub(r"[+-]?\d+\.\d+%?", " ", text).replace("95%", " "))
    assert not set(HIDDEN_COUNTS) & set(found), (f"a hidden yearly count stands as a figure in "
                                                 f"the {where}: {text}")


def reply_re(case):
    """S5 with S11: line 1 (any text, see READINGS), the yearly table exactly, the hidden line
    (2b), the fit line if it comes, the before-and-after line, the used line, the association
    line, the source line."""
    c = CASES[case]
    out = r"[^\n]+" + "".join(r"\n" + re.escape(line) for line in c["lines"])
    out += SEP + HIDDEN_RE + f"(?:{SEP}{FIT_RE})?"
    if case == "before_after":
        out += SEP + re.escape(T.BEFORE_AFTER_LINE)
    months = len(T.month_range(*c["months"]))
    return out + SEP + T.used_re(c["records"], months) + SEP + ASSOC_RE + SEP + first_source()


def ask_sparse(env, case):
    c = CASES[case]
    return env.ask(c["question"], Step(analyze(c["arguments"])), Step(finish("finding", c["text"])))


def test_the_sparse_series_is_what_the_cases_need():
    """No program code. Each window is long enough and has enough records (S1: 24 months, 100
    records); fewer than half of its quarters that are not 0 are hidden (S10 answers 6 and
    17: not TOO_FINE); each table line by hand is the year's total as C8 writes it, with 2c's
    label (answer 4 for one month)."""
    for case, c in CASES.items():
        months = T.month_range(*c["months"])
        assert len(months) >= T.MIN_MONTHS and c["records"] >= T.MIN_RECORDS, case
        assert months == T.window(SRC, c["arguments"]["period"]), case
        counts = [SPARSE.get(ym, 0) for ym in months]
        assert sum(counts) == c["records"], case
        quarters = [n for n in (sum(counts[i:i + 3]) for i in range(0, len(counts), 3)) if n]
        assert 2 * sum(1 for n in quarters if n < FLOOR) <= len(quarters), case
        totals = yearly(case)
        assert list(totals.values())[:4] == [4, 7, 0, 10], (case, totals)
        for (y, n), line in zip(totals.items(), c["lines"], strict=True):
            ms = [m for yy, m in months if yy == y]
            label = str(y) if len(ms) == 12 else f"{y} ({T.MONTH_NAMES[ms[0] - 1]}" + (
                ")" if len(ms) == 1 else f" to {T.MONTH_NAMES[ms[-1] - 1]})")
            assert line == f"{label}: {T.count_text(n)}", (case, line)
    assert CASES["before_after"]["lines"][0] == "2021 (December): fewer than 10"
    when = date.fromisoformat(CASES["before_after"]["arguments"]["options"]["date"])
    months = T.month_range(*CASES["before_after"]["months"])
    assert min(sum(1 for ym in months if ym < (when.year, when.month)),
               sum(1 for ym in months if ym >= (when.year, when.month))) >= 12


@pytest.mark.needs_r
@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.parametrize("style", ["agent", "fixed"])
def test_a_yearly_count_under_10_is_hidden_in_the_reply(tmp_path, monkeypatch, case, style):
    """In the reply (style agent) and the fixed rendering (MOCO_REPLY_STYLE=fixed): the small
    years' lines say `fewer than 10`, also with 2c's label; 0 and 10 are numbers; the hidden
    line of 2b follows the table; the counts 4 and 7 are nowhere a figure."""
    settings = {"MOCO_REPLY_STYLE": "fixed"} if style == "fixed" else {}
    env = StatsEnv(tmp_path, monkeypatch, rows={MAIN: sparse_rows()}, **settings)
    reply = answered(ask_sparse(env, case))
    assert reply.reply_style == style, (reply.reply_style, reply.draft_failures)
    pattern = reply_re(case)
    assert re.fullmatch(pattern, reply.text), (f"not the expected reply.\n--- got ---\n"
                                               f"{reply.text}\n--- expected (regex) ---\n"
                                               f"{pattern}")
    lines = reply.text.split("\n")
    for line in CASES[case]["lines"]:
        assert lines.count(line) == 1, (line, reply.text)
    assert reply.text.count("Counts under 10 are not shown here") == 1, reply.text
    no_hidden_count(reply.text, f"{style} reply")


@pytest.mark.needs_r
@pytest.mark.parametrize("case", list(CASES))
def test_a_yearly_count_under_10_is_hidden_in_details(tmp_path, monkeypatch, case):
    """`details` after the answer: the same yearly lines (S7's full table), the counts 4 and 7
    nowhere a figure, and the hidden line: C8.2's, or (READING, asked) the floor in the
    limits as today."""
    env = StatsEnv(tmp_path, monkeypatch, rows={MAIN: sparse_rows()})
    answered(ask_sparse(env, case))
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    assert details.status == "DETAILS", (details.status, details.reason_code, details.text)
    lines = details.text.split("\n")
    for line in CASES[case]["lines"]:
        assert lines.count(line) == 1, (line, details.text)
    assert not any(re.fullmatch(rf"20\d\d(?: \([A-Za-z ]+\))?: {n}", line)
                   for line in lines for n in HIDDEN_COUNTS), details.text
    hidden_line = any(re.fullmatch(HIDDEN_RE, line) for line in lines)
    assert hidden_line or FLOOR_LIMIT in lines, details.text
    no_hidden_count(details.text, "details")


# ==== PROOF GAP 3: with MOCO_TALK on, the room for k odds slots ====================================

BA = T.analyze_arguments("ba_d6")
STEP = ("from July 2023 on, the monthly level was about 40.6% higher than the earlier trend "
        "pointed to (95% range +3.8% to +90.4%)")        # ba_d6's step, test_s3s_wording.py
COUNT_MOST = 60   # a generous bound on `{r1.count}` filled: `<n> arrest records in 2025`

ODDS = {1: "{a1.odds.1}. {a1.held}.",
        3: "{a1.odds.1}. {a1.odds.2}. {a1.odds.3}. {a1.held}.",
        4: "{a1.odds.1}. {a1.odds.2}. {a1.odds.3}. {a1.odds.4}. {a1.held}."}
CASE_OF = {1: "yn_main", 3: "yn_main", 4: "yn_four"}

# k: (the most fact sentences, the most characters) by hand from answer 7
ROOM = {1: (4, 700), 3: (5, 800), 4: (6, 1000)}

# k: (a text at the most fact sentences, one with a fact sentence more)
SENTENCES = {
    1: (ODDS[1] + " {a2.step}. {a2.bend}.", ODDS[1] + " {a2.step}. {a2.bend}. {r1.count}."),
    3: (ODDS[3] + " {a2.step}.", ODDS[3] + " {a2.step}. {a2.bend}."),
    4: (ODDS[4] + " {a2.step}.", ODDS[4] + " {a2.step}. {a2.bend}."),
}


def before(k):
    """The turn's steps before the finish: for k = 1 a count of 2025 first (so that it is r1:
    a count's id counts every result before it), then the yes_no and the before_after
    (ba_d6)."""
    steps = [Step(analyze(arguments(CASE_OF[k]))), Step(analyze(BA))]
    return ([Step(count(MAIN_ID, {"year": 2025}, []))] if k == 1 else []) + steps


def filled_most(k, text):
    """The text's length once filled, at most: the yes_no slots by the truth helper (as
    test_s3s_wording.filled_length), ba_d6's step and bend by hand, `{r1.count}` bounded."""
    text = (text.replace("{a2.step}", STEP).replace("{a2.bend}", BEND["ba_d6"])
            .replace("{r1.count}", "x" * COUNT_MOST))
    return filled_length(CASE_OF[k], text)


def test_the_talk_texts_are_what_the_cases_need():
    """No program code. The odds slots each text fills; its fact and talk sentences (T2: a
    sentence with a slot is a fact sentence); no content fault; the texts refused for
    sentences are within the character room once filled."""
    for k, (at, over) in SENTENCES.items():
        most, chars = ROOM[k]
        assert (most, chars) == (max(4, k + 2), max(700, 200 * k + 200))
        for text, n in ((at, most), (over, most + 1)):
            assert len(re.findall(r"\{a1\.odds\.\d\}", text)) == k
            assert tuple(map(len, split_sentences(text))) == (n, 0), text
            assert mixed_faults(text) == set(), text
            assert filled_most(k, text) <= chars, (k, filled_most(k, text), text)
    assert len(truth("yn_main")["odds"]) == 3 and len(truth("yn_four")["odds"]) == 4


@pytest.mark.needs_r
@pytest.mark.parametrize("k", [1, 3, 4])
def test_talk_fact_sentences_with_odds_slots_no_longer_count(tmp_path, monkeypatch, k):
    """Answer 7, changed by briefs/S3-R7-A-tests.md (C38; was
    test_talk_fact_sentences_with_odds_slots: the larger of 4 and k + 2 fact sentences passed
    and one more was refused, SHAPE). In county mode with MOCO_TALK on the number of fact
    sentences no longer counts: both texts pass (neither has a sentence of its own)."""
    env = StatsEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    at, over = SENTENCES[k]
    check_cases(lambda i, text: first_try(env, Q_YES_NO, "finding", text, *before(k),
                                          thread_key=thread(i)),
                [(at, None), (over, None)], FINDING_CODES)


# k: the characters of the model's own words (C38: the text with every slot taken out) of the
# text at the room of answer 7 and of the one a character over it, measured by hand from the
# texts below, and C38's verdict on each (over 400: SHAPE).
OWN_WORDS = {1: ((546, "SHAPE"), (547, "SHAPE")),
             3: ((366, None), (367, None)),
             4: ((438, "SHAPE"), (439, "SHAPE"))}


@pytest.mark.needs_r
@pytest.mark.parametrize("k", [1, 3, 4])
def test_talk_characters_with_odds_slots_count_only_its_own_words(tmp_path, monkeypatch, k):
    """Answer 7, changed by briefs/S3-R7-A-tests.md (C38; was
    test_talk_characters_with_odds_slots: the larger of 700 and 200 k + 200 characters once
    filled passed, one more was refused, SHAPE). In county mode with MOCO_TALK on the length
    once filled no longer counts; more than 400 characters of the model's own words fail
    SHAPE. The same texts: the odds slots and the held slot, each a fact sentence, and one
    talk sentence of letters only (tsupport.padded)."""
    most, chars = ROOM[k]
    name = CASE_OF[k]

    def measure(text):
        return filled_length(name, text)

    at = padded(ODDS[k] + " ", "", chars, measure=measure)
    over = padded(ODDS[k] + " ", "", chars + 1, measure=measure)
    for text in (at, over):
        assert tuple(map(len, split_sentences(text))) == (k + 1, 1), text
        assert mixed_faults(text) == set(), text
    own = [len(re.sub(r"\{[^{}]*\}", "", text)) for text in (at, over)]
    assert own == [n for n, _ in OWN_WORDS[k]], own
    env = StatsEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    check_cases(lambda i, text: first_try(env, Q_YES_NO, "finding", text,
                                          Step(analyze(arguments(name))), thread_key=thread(i)),
                [(at, OWN_WORDS[k][0][1]), (over, OWN_WORDS[k][1][1])], FINDING_CODES)
