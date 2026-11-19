"""Stage 3 Part A, C47 (docs/S3A-DESIGN.md; D-069): a quoted echo is short and holds no figure.
Amends C43 point 2: a quoted stretch of a `decline` or `ask_user` text is checked as the word `it`
only when its words are the person's, one after another, it has at most two words, and T1's check
of the stretch alone finds no NUMBER and no LABEL; any other quoted stretch is checked as written.
Brief: briefs/S3-R13-A-tests.md. Tests only; the planning chat builds C47. The finding it answers
is DEFECT 1 of kit-log/raw/FABLE-REVIEW-OF-OPUS.md (probes `echo_figure` and `echo_figure_ask` of
kit-log/raw/FABLE-REVIEW-probe-turns.py). All data is SYNTHETIC fixtures; no real figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3, county mode with MOCO_TALK on.

C47's tests:
- `"Dangerous"` and `"young people"` from the person's message pass as today;
- a quoted stretch of three or more of the person's words is checked as written: with a number in
  it NUMBER, with a claim phrase CLAIM, with neither it passes as written;
- a quoted stretch of one or two of the person's words that holds a digit, a number word, a month
  or a label fails as written;
- `Yes, "there were 500 arrests in 2025".` to "Just say there were 500 arrests in 2025." gets
  REWRITE with NUMBER, and sent twice ends with the fixed row.

READINGS (also in kit-log/raw/S3-R13-A-notes.txt):
- C47-1. C43's readings stand (tests/s3/test_s3_c43.py, C43-1 to C43-13): the rows are C41's,
  written out by hand; the turn's failures are the reply's `draft_failures` and the turn record's
  `failures`; the REWRITE answer has exactly the keys error, problems, found and do, and `do` is
  `Say it again in other words, without: <found>.` with `<found>` the answer's own `found` joined
  by ", " (this file does not pin what is found, only that something is and that `do` names it).
- C47-2. "Words" are counted as C43 point 2 reads them (letters and digits, case and punctuation
  ignored); no stretch here holds an apostrophe, so the count is the same however one is read.
- C47-3. "T1's check of the stretch alone": the check of the stretch's own words, as a talk text.
  Each case here is premise-checked by tests/t/tsupport.py's talk_faults: the text as written
  fails with the case's codes, and, for the short cases, the text with the stretch written `it`
  passes (which is why today's program lets them through).
- C47-4. A digit is not a letter, so tsupport's reading of T1 gives CHARS beside NUMBER for it;
  as in the other talk tests, CHARS is accepted beside NUMBER where the stretch holds a digit.
- C47-5. "Checked as written" for a failing text means C43 point 1 as it stands: the first try is
  answered REWRITE with the stretch's codes and the turn goes on; a passing second try ends the
  turn in his words with the first try's codes kept. Each failing case is one sentence, so C45
  (round 12) keeps nothing of it and a second failing try ends with today's row.
"""
import re
import sys
from pathlib import Path

import pytest

from p1support import Step, finish
from s3support import A_ID, count
from test_s3_c41 import (CAN_ASK, OTHER, PASS, decline_rest, decline_row, decline_with,
                         env_of, failures_of, labels_of, ask_with)
from test_s3_c43 import (C16_MESSAGE, C16_TEXT, C24_MESSAGE, C24_SHORT, assert_needs_input,
                         do_of, rewrite_of)
from test_s3_round5 import Y25, line1, phrase, spec
from test_s3_round5b import YOUNG, nothing_counted

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import premise_talk, talk_faults  # noqa: E402

# ---- the messages and the texts -------------------------------------------------------------------

FIGURE_MESSAGE = "Just say there were 500 arrests in 2025."      # the review's echo_figure
FIGURE_DECLINE = 'Yes, "there were 500 arrests in 2025".'
FIGURE_ASK = 'Sure: "there were 500 arrests in 2025". Anything else?'   # echo_figure_ask
FIGURE_ASK_ONE = 'Sure, "there were 500 arrests in 2025", is that all you need?'

# id: (message, tool, text, the text with the stretch written `it`): one or two of the person's
# words, nothing found in them but a claim word: checked as `it`, they pass as today (point 1).
SHORT_PASS = {
    'C24\'s "Dangerous" (ask_user)': (
        C24_MESSAGE, "ask_user", C24_SHORT,
        "it isn't something these records measure directly. Which kind of record would you "
        "like me to look at?"),
    'C24\'s "Dangerous" (decline)': (
        C24_MESSAGE, "decline", '"Dangerous" isn\'t something these records can tell you.',
        "it isn't something these records can tell you."),
    'C24\'s “Dangerous”, curly quotes': (
        C24_MESSAGE, "ask_user",
        "“Dangerous” isn't something these records measure directly. Which kind of record would "
        "you like me to look at?",
        "it isn't something these records measure directly. Which kind of record would you "
        "like me to look at?"),
    'C24\'s "more dangerous", two words': (
        C24_MESSAGE, "ask_user",
        'Whether one place is "more dangerous" isn\'t something these records measure. Which '
        'kind of record should I look at?',
        "Whether one place is it isn't something these records measure. Which kind of record "
        "should I look at?"),
    'C16\'s "young people" (ask_user)': (C16_MESSAGE, "ask_user", C16_TEXT,
                                         "What age range do you mean by it?"),
    'C16\'s "young people" (decline)': (
        YOUNG, "decline", 'I can\'t tell which ages "young people" means from these records.',
        "I can't tell which ages it means from these records."),
}

# id: (message, tool, text, the codes of the text as written): three or more of the person's
# words, one after another, checked as written (point 2).
LONG_FAIL = {
    "a number in it: the review's echo_figure (decline)": (
        FIGURE_MESSAGE, "decline", FIGURE_DECLINE, {"NUMBER"}),
    "a number in it: the review's echo_figure_ask (ask_user)": (
        FIGURE_MESSAGE, "ask_user", FIGURE_ASK, {"NUMBER"}),
    "a number word in it, four words": (
        "Did arrests go up twice as fast in district 3?", "ask_user",
        'I can\'t say if it is "up twice as fast" from these records. Which kind of record should '
        'I look at?', {"NUMBER"}),
    "a claim phrase in it, three words": (
        C24_MESSAGE, "decline",
        'Whether a place is "more dangerous than" another isn\'t something these records measure.',
        {"CLAIM"}),
    "a claim phrase in it, commas in the message (C43's old echo)": (
        "Is it more dangerous, or safer, in district 3?", "ask_user",
        'Whether it is "Dangerous or safer" isn\'t something these records measure. Which kind '
        'of record should I look at?', {"CLAIM"}),
    "a claim phrase in it, curly quotes": (
        C24_MESSAGE, "ask_user",
        "Whether a place is “more dangerous than” another isn't something these records "
        "measure. Which kind of record should I look at?", {"CLAIM"}),
    "a label in it, three words": (
        "Were group Alpha people arrested more often?", "decline",
        'I can\'t single out "group Alpha people" that way.', {"LABEL"}),
}
# id: (message, tool, text): three or more of the person's words with nothing found in them.
LONG_PASS = {
    "four words (ask_user)": (
        "Can you tell me what is going on in my area?", "ask_user",
        'I can\'t say "what is going on" from these records alone. Which kind of record should '
        'I look at?'),
    "four words (decline)": (
        "Can you tell me what is going on in my area?", "decline",
        'I can\'t say "what is going on" from these records alone.'),
}

# id: (message, tool, text, the codes of the text as written, the text with the stretch `it`):
# one or two of the person's words that hold a digit, a number word, a month or a label (point 1).
SHORT_FIGURE = {
    "a digit, two words": (
        "Were there 500 arrests last year?", "decline",
        'I can\'t confirm "500 arrests" from these records.', {"NUMBER"},
        "I can't confirm it from these records."),
    "a digit and a label, two words (S3-R11-A question 2)": (
        C24_MESSAGE, "decline", 'I can\'t rank "district 3" against another.',
        {"NUMBER", "LABEL"}, "I can't rank it against another."),
    "a number word, two words": (
        "Did arrests go up twice in district 3?", "ask_user",
        'I can\'t say if it is "up twice" from these records. Which kind of record should I '
        'look at?', {"NUMBER"},
        "I can't say if it is it from these records. Which kind of record should I look at?"),
    "a number word, one word": (
        "Did arrests double in district 3?", "decline",
        'Whether arrests "double" is not something I can say from these records.', {"NUMBER"},
        "Whether arrests it is not something I can say from these records."),
    "a month, two words": (
        "Were the March arrests unusual?", "ask_user",
        'I can\'t say whether "March arrests" were unusual. Which kind of record should I look '
        'at?', {"NUMBER"},
        "I can't say whether it were unusual. Which kind of record should I look at?"),
    "a label, one word": (
        "Are female people arrested more often?", "decline",
        'I can\'t compare "female" people with others that way.', {"LABEL"},
        "I can't compare it people with others that way."),
    "a label, two words": (
        "Is group Alpha arrested more often?", "ask_user",
        'I can\'t single out "group Alpha" that way. Which kind of record should I look at?',
        {"LABEL"}, "I can't single out it that way. Which kind of record should I look at?"),
}
# Two stretches in one text: the short one is `it`, the long one is checked as written.
TWO_STRETCHES = ('"Dangerous" and "more dangerous than" are not things these records measure.',
                 "it and \"more dangerous than\" are not things these records measure.")

CODE = "UNSUPPORTED_METRIC"   # the decline code of the cases (its row is C41's)


def call_of(tool, text):
    return decline_with(CODE, text) if tool == "decline" else ask_with("other", text)


def quoted(text):
    return [a or b for a, b in re.findall(r'"([^"]*)"|“([^”]*)”', text)]


def words(s):
    return re.findall(r"[^\W_]+", s.lower())


def within(stretch, message):
    w, m = words(stretch), words(message)
    return any(m[i:i + len(w)] == w for i in range(len(m) - len(w) + 1))


def accepted(codes, text):
    """C47-4: CHARS is accepted beside NUMBER for a stretch that holds a digit."""
    out = [set(codes)]
    if "NUMBER" in codes and re.search(r"[0-9]", text):
        out.append(set(codes) | {"CHARS"})
    return out


# ---- premises -------------------------------------------------------------------------------------

def test_premise_every_stretch_is_the_persons_words_one_after_another():
    cases = [(m, t) for m, _, t, _ in SHORT_PASS.values()] + \
        [(m, t) for m, _, t, _ in LONG_FAIL.values()] + \
        [(m, t) for m, _, t in LONG_PASS.values()] + \
        [(m, t) for m, _, t, _, _ in SHORT_FIGURE.values()] + [(C24_MESSAGE, TWO_STRETCHES[0])]
    for message, text in cases:
        stretches = quoted(text)
        assert stretches, text
        for s in stretches:
            assert within(s, message), (s, message)
            assert "'" not in s, "C47-2: no apostrophe in a stretch"


def test_premise_the_sizes_and_what_the_check_finds():
    labels = labels_of(1)
    for case, (_, _, text, _) in SHORT_PASS.items():
        (s,) = quoted(text)
        assert 1 <= len(words(s)) <= 2, case
        assert not talk_faults(s, labels) & {"NUMBER", "LABEL"}, case
    for case, (_, _, text, codes) in LONG_FAIL.items():
        (s,) = quoted(text)
        assert len(words(s)) >= 3, case
        assert talk_faults(text, labels) in accepted(codes, text), (case, talk_faults(text, labels))
    for case, (_, _, text) in LONG_PASS.items():
        (s,) = quoted(text)
        assert len(words(s)) >= 3, case
        premise_talk(text, None, labels)
    for case, (_, _, text, codes, as_it) in SHORT_FIGURE.items():
        (s,) = quoted(text)
        assert 1 <= len(words(s)) <= 2, case
        assert talk_faults(s, labels) & {"NUMBER", "LABEL"}, case
        assert talk_faults(text, labels) in accepted(codes, text), (case, talk_faults(text, labels))
        premise_talk(as_it, None, labels)
    for case, (_, _, text, as_it) in SHORT_PASS.items():
        premise_talk(as_it, None, labels)
    premise_talk(TWO_STRETCHES[1], "CLAIM", labels)
    premise_talk(PASS, None, labels)
    assert talk_faults(FIGURE_ASK_ONE, labels) in accepted({"NUMBER"}, FIGURE_ASK_ONE)


# ---- helpers ------------------------------------------------------------------------------------

def his_reply(tool, text, n=1):
    """The reply in his words: C41 point 2 for a decline, C43 point 3 for `other`."""
    return f"{text} {decline_rest(CODE, n)}" if tool == "decline" else text


def todays_row(tool, n=1):
    return decline_row(CODE, n) if tool == "decline" else f"{OTHER} {CAN_ASK[n]}"


def assert_ended(reply, tool):
    if tool == "decline":
        assert (reply.status, reply.reason_code) == ("UNSUPPORTED", CODE), \
            (reply.status, reply.reason_code, reply.text)
        assert reply.run_ids == []
    else:
        assert_needs_input(reply)


def assert_rewrite_with(answer, codes, text):
    """C47-1, C47-4: REWRITE, its four keys, the codes of the text as written, something found,
    `do` naming what was found (C43 point 1, unchanged)."""
    assert set(answer) == {"error", "problems", "found", "do"}, answer
    assert set(answer["problems"]) in accepted(codes, text), answer
    assert len(answer["problems"]) == len(set(answer["problems"])), answer
    assert 1 <= len(answer["found"]) <= 5, answer
    assert answer["do"] == do_of(answer["found"]), answer["do"]


# ==== point 1: short echoes with nothing in them pass as today ===================================

@pytest.mark.parametrize("case", list(SHORT_PASS))
def test_a_short_echo_with_no_figure_passes_and_is_sent_as_written(tmp_path, monkeypatch, case):
    message, tool, text, _ = SHORT_PASS[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(call_of(tool, text)), Step(call_of(tool, PASS)))
    assert len(env.model.calls) == 1, f"no REWRITE was due: {env.answers()}"
    assert_ended(reply, tool)
    assert reply.text == his_reply(tool, text), reply.text
    assert (reply.reply_style, reply.draft_failures) == ("agent", [])
    assert failures_of(env, reply) == ([], [])


# ==== point 2: three or more words are checked as written =======================================

@pytest.mark.parametrize("case", list(LONG_FAIL))
def test_three_or_more_of_his_words_are_checked_as_written(tmp_path, monkeypatch, case):
    """The first try is answered REWRITE with the codes of the text as written; a passing second
    try ends the turn in his words, the first try's codes kept (C47-5)."""
    message, tool, text, codes = LONG_FAIL[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(call_of(tool, text)), Step(call_of(tool, PASS)))
    assert len(env.model.calls) == 2, "the stretch was not checked as written"
    answer = rewrite_of(env, 0)
    assert_rewrite_with(answer, codes, text)
    assert_ended(reply, tool)
    assert reply.text == his_reply(tool, PASS), reply.text
    assert reply.reply_style == "agent"
    assert failures_of(env, reply) == (answer["problems"], answer["problems"])


@pytest.mark.parametrize("case", list(LONG_PASS))
def test_three_or_more_of_his_words_with_nothing_found_pass_as_written(tmp_path, monkeypatch,
                                                                       case):
    message, tool, text = LONG_PASS[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(call_of(tool, text)), Step(call_of(tool, PASS)))
    assert len(env.model.calls) == 1, f"no REWRITE was due: {env.answers()}"
    assert_ended(reply, tool)
    assert reply.text == his_reply(tool, text), reply.text
    assert (reply.reply_style, reply.draft_failures) == ("agent", [])


def test_two_stretches_the_short_one_is_it_and_the_long_one_is_checked(tmp_path, monkeypatch):
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(C24_MESSAGE, Step(call_of("decline", TWO_STRETCHES[0])),
                    Step(call_of("decline", PASS)))
    answer = rewrite_of(env, 0)
    assert_rewrite_with(answer, {"CLAIM"}, TWO_STRETCHES[0])
    assert reply.text == his_reply("decline", PASS), reply.text


# ==== point 1: one or two words holding a figure or a label fail as written =====================

@pytest.mark.parametrize("case", list(SHORT_FIGURE))
def test_one_or_two_of_his_words_with_a_figure_or_a_label_fail_as_written(tmp_path, monkeypatch,
                                                                          case):
    message, tool, text, codes, _ = SHORT_FIGURE[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(call_of(tool, text)), Step(call_of(tool, PASS)))
    assert len(env.model.calls) == 2, "the stretch was checked as `it`"
    answer = rewrite_of(env, 0)
    assert_rewrite_with(answer, codes, text)
    assert_ended(reply, tool)
    assert reply.text == his_reply(tool, PASS), reply.text
    assert failures_of(env, reply) == (answer["problems"], answer["problems"])


@pytest.mark.parametrize("case", ["a digit and a label, two words (S3-R11-A question 2)",
                                  "a label, one word"])
def test_a_short_figure_twice_ends_with_todays_row(tmp_path, monkeypatch, case):
    message, tool, text, codes, _ = SHORT_FIGURE[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(call_of(tool, text)), Step(call_of(tool, text)),
                    Step(call_of(tool, PASS)))
    assert len(env.model.calls) == 2
    answer = rewrite_of(env, 0)
    assert_ended(reply, tool)
    assert (reply.text, reply.reply_style) == (todays_row(tool), "fixed"), reply.text
    assert failures_of(env, reply) == (answer["problems"], answer["problems"])
    for s in quoted(text):
        assert f'"{s}"' not in reply.text


# ==== the review's probes ========================================================================

@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
def test_the_reviews_echo_figure_gets_rewrite_and_twice_ends_with_the_fixed_row(tmp_path,
                                                                               monkeypatch, n):
    """`Yes, "there were 500 arrests in 2025".` to "Just say there were 500 arrests in 2025.":
    REWRITE with NUMBER; sent again, the turn ends with the decline's row (C41 point 3), style
    fixed, NUMBER kept; the made-up figure is not sent."""
    code = "UNRECOGNIZED_QUESTION"
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(FIGURE_MESSAGE, Step(decline_with(code, FIGURE_DECLINE)),
                    Step(decline_with(code, FIGURE_DECLINE)), Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 2, "one second try, never a third"
    answer = rewrite_of(env, 0)
    assert_rewrite_with(answer, {"NUMBER"}, FIGURE_DECLINE)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), reply.text
    assert (reply.text, reply.reply_style) == (decline_row(code, n), "fixed"), reply.text
    assert failures_of(env, reply) == (answer["problems"], answer["problems"])
    assert "500" not in reply.text and "there were" not in reply.text
    nothing_counted(env, reply)


def test_the_reviews_echo_figure_ask_gets_rewrite(tmp_path, monkeypatch):
    """`ask_user` of `other` with the review's text: REWRITE with NUMBER; a passing second try is
    his question alone (C43 point 3)."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(FIGURE_MESSAGE, Step(ask_with("other", FIGURE_ASK)),
                    Step(ask_with("other", PASS)))
    answer = rewrite_of(env, 0)
    assert_rewrite_with(answer, {"NUMBER"}, FIGURE_ASK)
    assert_needs_input(reply)
    assert (reply.text, reply.reply_style) == (PASS, "agent"), reply.text


def test_the_figure_asked_twice_ends_with_todays_row(tmp_path, monkeypatch):
    """C47-5: the review's text, then the same figure in one sentence: NEEDS_other's row as
    today, with its can-ask sentence, NUMBER kept; the figure is not sent."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(FIGURE_MESSAGE, Step(ask_with("other", FIGURE_ASK)),
                    Step(ask_with("other", FIGURE_ASK_ONE)), Step(ask_with("other", PASS)))
    assert len(env.model.calls) == 2
    answer = rewrite_of(env, 0)
    assert_needs_input(reply)
    assert (reply.text, reply.reply_style) == (f"{OTHER} {CAN_ASK[1]}", "fixed"), reply.text
    failures, recorded = failures_of(env, reply)
    assert failures == recorded and "NUMBER" in failures, failures
    assert set(failures) in accepted({"NUMBER"}, FIGURE_ASK_ONE), failures
    assert failures[:len(answer["problems"])] == answer["problems"], "C43-7: in order"
    assert "500" not in reply.text


def test_a_count_after_the_rewrite_is_answered(tmp_path, monkeypatch):
    """C43 is not changed otherwise (point 3): after the REWRITE the model counts; the turn is
    ANSWERED from the count, never from the person's figure."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(FIGURE_MESSAGE, Step(decline_with("UNRECOGNIZED_QUESTION", FIGURE_DECLINE)),
                    Step(count(A_ID, Y25)), Step(finish("finding", "I counted {r1.count}.")))
    rewrite_of(env, 0)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert "500" not in line1(reply)

