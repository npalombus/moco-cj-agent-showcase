"""Stage 3 Part A, C43 (docs/S3A-DESIGN.md; D-048, D-066): his own words, a second time. In county
mode with MOCO_TALK on, a `decline` or `ask_user` text that fails T1's talk check gets one second
try (REWRITE) before the turn ends with today's row; a quoted stretch of the person's own words is
checked as the word `it`; an `ask_user` of `missing` `other` in his own words is sent alone, with
no can-ask sentence. Brief: briefs/S3-R11-A-tests.md. Tests only; the planning chat builds C43,
on C41 (tests/s3/test_s3_c41.py, round 9). All data is SYNTHETIC fixtures; no real figure is
quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel, which repeats its last step when its steps run out) on the SYNTHETIC fixtures of
tests/s3, with MOCO_TALK on unless a test says.

C43's tests:
- a failing `text` gets REWRITE (its four keys, `do` word for word) and the turn goes on, then a
  passing second `text` ends the turn in his words;
- two failing tries end with today's row and both codes;
- no step left after the first failure ends with today's row at once (and, as T3, less than five
  seconds left);
- the quoted echo of C24's message passes and a quoted stretch not in the message fails;
- C16's case is his question alone;
- a decline keeps NOTED and the can-ask sentence.
And point 4, "Not changed": C32's question; SYNTHETIC mode; MOCO_TALK off; the status, reason code
and `missing` of the end.

READINGS (also in kit-log/raw/S3-R11-A-notes.txt; the open ones also in briefs/QUESTIONS.md):
- C43-1. C41's readings stand (C41-1 to C41-9): the rows, written out by hand in test_s3_c41.py
  from round 5's texts; the turn's failures are the reply's `draft_failures` and the turn
  record's `failures`; "as today" is the same turn with no `text` (another thread or agent).
- C43-2. "Fails T1's check": as in C41, each text here is checked first, as a premise, by
  tests/t/tsupport.py's talk_faults with the env's labels; for a quoted echo the premise checks
  the text as written (it fails) and the text with the stretch written `it` (it passes).
- C43-3. The REWRITE answer is Python's JSON answer to the failing call, as the next model step
  sees it (FakeModel.answer). Its keys are exactly error, problems, found and do. `problems` is
  the check's codes; each failing text here fails one code, so its order is not in question.
  `found` is "the first five things it found, without repeats": every text here has its found
  words in lower case already, so whether the check lower-cases them changes nothing; `do` is
  "Say it again in other words, without: <found>." with `<found>` those joined by ", ".
- C43-4. A text that fails SHAPE alone has nothing found; its `do` is "Say it again in other words,
  in one or two short sentences." word for word (S3-R11-A answer 1, now C50 point 2). Was OPEN,
  with any `do` starting "Say it again in other words" accepted; changed by
  briefs/S3-R13-A-tests.md.
- C43-5. "The turn goes on: nothing is ended, noted or asked yet": the model is called again;
  when it then counts and finishes, the turn is ANSWERED, nothing pending is stored and no
  request is noted (memory.refused_turns, A12's list of declined requests, holds nothing).
- C43-6. "A step and five seconds left (as T3)": T3's reading in tests/t/test_t_rewrite.py: the
  failing call is not made in the last step of MOCO_MAX_STEPS, and MOCO_TURN_SECONDS less the
  seconds since the turn began (the FakeClock, moved by the FakeModel at each step) is 5 or more.
  "Or no step or time is left" also covers a REWRITE after which the turn runs out of steps with
  nothing made: it ends with the first try's row (style fixed, its codes), as T3 ends after a
  REWRITE with no step left (T16 point 4).
- C43-7. "Codes of every try that failed, in order, without repeats": the first try's codes, then
  the second's not already there. A passing second try keeps the first try's codes; a second call
  with no `text` (today's row) keeps them too, since only the first try failed.
- C43-8. "One second try per turn for own words": across both tools. A failing first try of
  `decline` and a failing second try of `ask_user` end the turn with the row of the second call,
  as today. "Apart from T3's for a finish": an own-words REWRITE does not use up T3's second try
  for a finish, nor the other way round.
- C43-9. The `period` question is sent as C41-1 sends it: its first call is answered
  NO_PERIOD_QUESTION (C25 point 0) and does not end the turn, so its text plays no part (C41
  point 2: the text replaces part of "the row the turn would end with"); the REWRITE comes at the
  call that would end the turn.
- C43-10. Point 2's stretch: the words inside one pair of straight (`"..."`) or curly (`“...”`)
  quotation marks; its words (letter case and punctuation ignored) must stand one after another
  in the person's message. "Checked as the word it": the check is run as if the stretch, with its
  marks, were `it` (the quotation marks are allowed marks either way, T11). "Sent as written": the
  reply holds the stretch exactly as he wrote it. Point 2 is for a `decline` or `ask_user` text
  only: a talk `finish` quoting the person is checked as today (point 4: "what counts as failing
  T1's check" is not changed outside point 2's stretches). Since C47 (docs/S3A-DESIGN.md, which
  amends point 2; its tests are tests/s3/test_s3_c47.py) a stretch is `it` only with at most two
  words and no NUMBER and no LABEL in it: every echo here has one or two words and neither.

Changed by briefs/S3-R13-A-tests.md (C47 and C50 point 2), each listed old and new in
kit-log/raw/S3-R13-A-notes.txt: the echo "commas in the message, another letter case" had three
words ("Dangerous or safer"), which C47 checks as written (it fails CLAIM; that case is now in
test_s3_c47.py), so it is replaced by a two-word echo across a comma of its message; the SHAPE-alone
test pins C50 point 2's `do` word for word (C43-4).
- C43-11. Point 3, "ends the turn with his own text (style agent)": the reply is his text alone,
  for one, two and three sources, after a first or a second try. A row that ends with no text or
  a failing one (style fixed) keeps NEEDS_other's can-ask sentence (C41 point 3, as today).
- C43-12. A text that is not used is not checked, so it gets no REWRITE and no failures: the
  planning chat's answer 1 to S3-R9-A for NEEDS_source with one or two sources (14 Nov 15:51 EST:
  "not checked, so it has no failures and gets no second try (C43)"). The same is read for C32's
  question (point 4: not changed) and for a decline after a count (it ends with the fixed
  rendering, C41-5): no REWRITE, the turn as today.
- C43-13. Talk off: the text is not read at all (T0, C41 point 4), so a failing one gets no REWRITE
  and no failures. SYNTHETIC mode with talk on: the tools carry no `text` (C41 point 4); a call
  that sends one anyway ends the turn exactly as one without it.
"""
import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest

import p1support as p1
from p1support import LEAVE_OUT, THREAD_2, Step, finish
from s3support import A_ID, C62_MAKER_HINT, NOW_S3, count, turn_json
from support import SUPPORTED
from test_s3_c36 import ages_not_stated
from test_s3_c41 import (ASKS, CAN_ASK, DECLINE_CODES, DECLINED, FIRST, OTHER, PASS, Q_ASK,
                         SOURCE_AS_TODAY, ask_env, ask_with, decline_rest, decline_row,
                         decline_with, env_of, failures_of, labels_of, rest_of, stored)
from test_s3_round5 import Y25
from test_s3_round5b import YOUNG, YOUNG_AGES, ages_question, nothing_counted

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import HELLO_TEXT, HINTS, premise_talk, talk_faults, talk_rules  # noqa: E402

# ---- C43's words, written out by hand ----------------------------------------------------------

DO_LEAD = "Say it again in other words"


def do_of(found):
    """Point 1: "Say it again in other words, without: <found>." (`found` joined by ", ")."""
    return f"Say it again in other words, without: {', '.join(found)}."


# ---- the model's own texts ----------------------------------------------------------------------

# id (the code): a text that fails T1's talk check with that code alone, and what the check finds
# in it (every found word is in lower case in the text: C43-3).
FAULTS = {
    "NUMBER": ("I can't count that twice over.", ["twice"]),
    "LABEL": ("I can't single out female people that way.", ["female"]),
    "CLAIM": ("That would be due to things my records do not hold.", ["due to"]),
    "CHARS": ("I can't answer that one @ the moment.", ["@"]),
}
SHAPE_TEXT = "Sorry. I can't. Not that. Not here. Not now. Try again. Ask me something else."
BOTH = "That is due to twice the work."  # NUMBER and CLAIM, in the check's order (C43-7)
# Seven number words, "two" twice: the first five, without repeats, are found (point 1).
MANY = "I cannot say two or three, maybe four, five, six, seven, or two again."
MANY_FOUND = ["two", "three", "four", "five", "six"]

C16_MESSAGE = YOUNG  # "How many arrests of young people were there in 2025?" (the live case C16)
C16_TEXT = 'What age range do you mean by "young people"?'  # his question in live round 14
C24_MESSAGE = "Is district 3 more dangerous than district 4?"  # the live case C24
# His ask_user text in live round 14, word for word from C43: NUMBER ("two") and CLAIM
# ("dangerous", the person's own word, in quotation marks).
C24_LIVE = ('"Dangerous" isn\'t something these records measure directly. I can compare things '
            'like arrests, use of force, or service calls between the two districts. Which kind '
            'of record would you like me to look at?')
C24_SHORT = ('"Dangerous" isn\'t something these records measure directly. Which kind of record '
             'would you like me to look at?')

# id: (message, text with a quoted echo of the message, the text with the stretch written `it`)
ECHOES = {
    "C24, straight quotes, another letter case": (
        C24_MESSAGE, C24_SHORT,
        "it isn't something these records measure directly. Which kind of record would you "
        "like me to look at?"),
    "C24, curly quotes": (
        C24_MESSAGE,
        "“Dangerous” isn't something these records measure directly. Which kind of record would "
        "you like me to look at?",
        "it isn't something these records measure directly. Which kind of record would you "
        "like me to look at?"),
    "C24, two words one after another": (
        C24_MESSAGE,
        'Whether one place is "more dangerous" isn\'t something these records measure. Which '
        'kind of record should I look at?',
        "Whether one place is it isn't something these records measure. Which kind of record "
        "should I look at?"),
    "C24, a question mark inside the quote": (
        C24_MESSAGE,
        "“Dangerous?” isn't something these records measure directly. Which kind of record "
        "would you like me to look at?",
        "it isn't something these records measure directly. Which kind of record would you "
        "like me to look at?"),
    "commas in the message, another letter case": (   # changed by briefs/S3-R13-A-tests.md (C47)
        "Which district is the most dangerous, overall?",
        'Whether a district is "Dangerous overall" isn\'t something these records measure. Which '
        'kind of record should I look at?',
        "Whether a district is it isn't something these records measure. Which kind of record "
        "should I look at?"),
}
# id: (text, what the check finds): a quoted stretch that is not the person's words one after
# another, checked as today: CLAIM (C24's message).
NOT_ECHOES = {
    "a word not in the message": (
        'Whether a place is "safer" isn\'t something these records measure. Which kind of '
        'record should I look at?', ["safer"]),
    "words of the message, not one after another": (
        'A "dangerous district" isn\'t something these records measure. Which kind of record '
        'should I look at?', ["dangerous"]),
    "the message's words and one more": (
        'Whether a place is "more dangerous now" isn\'t something these records measure. Which '
        'kind of record should I look at?', ["dangerous"]),
    "no quotation marks": (
        "Dangerous isn't something these records measure directly. Which kind of record would "
        "you like me to look at?", ["dangerous"]),
}
DECLINE_ECHO = '"Dangerous" isn\'t something these records can tell you.'
DECLINE_ECHO_AS_IT = "it isn't something these records can tell you."

COUNTED = "I counted {r1.count}."   # a county finding that passes (as round 5's kept_by_counts)
T3_FAILING = "I can look at two years for you."   # a talk finish that fails NUMBER (T3's tests)


def premises():
    for n in (1, 2, 3):
        labels = labels_of(n)
        for code, (text, found) in FAULTS.items():
            premise_talk(text, code, labels)
            assert all(f in text for f in found), (code, found)
        premise_talk(SHAPE_TEXT, "SHAPE", labels)
        premise_talk(MANY, "NUMBER", labels)
        assert talk_faults(BOTH, labels) == {"NUMBER", "CLAIM"}
        premise_talk(PASS, None, labels)
        premise_talk(C16_TEXT, None, labels)
        premise_talk(HELLO_TEXT, None, labels)
        premise_talk(T3_FAILING, "NUMBER", labels)
        assert talk_faults(C24_LIVE, labels) == {"NUMBER", "CLAIM"}
        premise_talk(C24_LIVE.replace('"Dangerous"', "it"), "NUMBER", labels)
        for message, text, as_it in ECHOES.values():
            premise_talk(text, "CLAIM", labels)
            premise_talk(as_it, None, labels)
        for text, found in NOT_ECHOES.values():
            premise_talk(text, "CLAIM", labels)
        premise_talk(DECLINE_ECHO, "CLAIM", labels)
        premise_talk(DECLINE_ECHO_AS_IT, None, labels)


def test_premise_the_texts_pass_and_fail_as_their_cases_say():
    premises()


def test_premise_the_echoes_are_the_messages_words_and_the_others_are_not():
    """C43-10, on this file's own texts: each echo's quoted words stand one after another in its
    message (case and punctuation ignored); each other stretch's do not."""
    def words(s):
        return re.findall(r"[a-z0-9']+", s.lower())

    def quoted(text):
        return [a or b for a, b in re.findall(r'"([^"]*)"|“([^”]*)”', text)]

    def within(stretch, message):
        w, m = words(stretch), words(message)
        return any(m[i:i + len(w)] == w for i in range(len(m) - len(w) + 1))

    for case, (message, text, _) in ECHOES.items():
        (stretch,) = quoted(text)
        assert within(stretch, message), case
    for case, (text, _) in NOT_ECHOES.items():
        assert all(not within(s, C24_MESSAGE) for s in quoted(text)), case
    assert "it" not in words(C24_MESSAGE), "premise: `it` is not a word of C24's message"


def test_premise_the_hints_of_t3_are_tsupports():
    """Changed by briefs/S3-R24-A-tests.md (C62 point 1: rewrite_hints gains MAKER): it was
    `== HINTS`; now tsupport's hints and C62's MAKER hint (s3support.C62_MAKER_HINT).
    Changed by briefs/S3-R28-A-tests.md (C64 point 1): tsupport.HINTS["NUMBER"] is C64's hint
    (today's two sentences, one space, s3support.C64_HINT_SENTENCE); the line is unchanged."""
    assert talk_rules()["rewrite_hints"] == {**HINTS, "MAKER": C62_MAKER_HINT}


# ---- helpers ------------------------------------------------------------------------------------

def rewrite_of(env, step):
    """C43-3: Python's answer to the call of model step `step` (0 = the first)."""
    answer = env.model.answer(step)
    assert isinstance(answer, dict) and answer.get("error") == "REWRITE", \
        f"step {step} was not answered REWRITE: {answer!r}"
    return answer


def assert_rewrite(answer, codes, found):
    """Point 1: the four keys, exactly; `do` word for word."""
    assert set(answer) == {"error", "problems", "found", "do"}, answer
    assert answer["error"] == "REWRITE"
    assert answer["problems"] == codes, answer
    assert answer["found"] == found, answer
    assert answer["do"] == do_of(found), answer["do"]


def ask_steps(missing, *texts):
    """C43-9: for `period`, a first call with no text (answered NO_PERIOD_QUESTION), then one
    call per text; else one call per text. Returns (steps, the index of the first text's step)."""
    first = [Step(ask_with("period"))] if missing == "period" else []
    return first + [Step(ask_with(missing, t)) for t in texts], len(first)


def ask_reply(case, text):
    """The row of `case` with his text: C41 point 2, and C43 point 3 for `other`."""
    _, missing, _, _, _ = ASKS[case]
    return text if missing == "other" else f"{text} {rest_of(case)}"


def assert_needs_input(reply):
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == []


def refused(env):
    """A12: the requests noted (declined with a request code), newest first (the turns of a
    CountyEnv are at NOW_S3 plus one minute each)."""
    return env.store.refused_turns(30, now=NOW_S3 + timedelta(hours=1))


# ---- point 1: REWRITE, the turn goes on, a passing second text ---------------------------------

@pytest.mark.parametrize("fault", list(FAULTS))
@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_failing_decline_text_gets_rewrite_then_a_passing_one_ends_in_his_words(
        tmp_path, monkeypatch, code, n, fault):
    text, found = FAULTS[fault]
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(DECLINED[code], Step(decline_with(code, text)), Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 2, "the turn did not go on after the REWRITE"
    assert_rewrite(rewrite_of(env, 0), [fault], found)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.text == f"{PASS} {decline_rest(code, n)}", reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == ([fault], [fault]), "C43-7: the first try's codes kept"
    nothing_counted(env, reply)


@pytest.mark.parametrize("fault", list(FAULTS))
@pytest.mark.parametrize("case", list(ASKS))
def test_a_failing_ask_user_text_gets_rewrite_then_a_passing_one_ends_in_his_words(
        tmp_path, monkeypatch, case, fault):
    text, found = FAULTS[fault]
    _, missing, _, _, first = ASKS[case]
    twin_env = ask_env(tmp_path / "today", monkeypatch, case)
    twin_steps, _ = ask_steps(missing, LEAVE_OUT)
    twin = twin_env.ask(Q_ASK, *twin_steps)
    env = ask_env(tmp_path / "text", monkeypatch, case)
    steps, at = ask_steps(missing, text, PASS)
    reply = env.ask(Q_ASK, *steps)
    assert len(env.model.calls) == at + 2, "the turn did not go on after the REWRITE"
    if missing == "period":
        assert env.model.answer(0).get("error") == "NO_PERIOD_QUESTION", env.model.answer(0)
    assert_rewrite(rewrite_of(env, at), [fault], found)
    assert_needs_input(reply)
    assert reply.text == ask_reply(case, PASS), reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == ([fault], [fault]), "C43-7: the first try's codes kept"
    assert not reply.text.startswith(first)
    assert (reply.status, reply.reason_code) == (twin.status, twin.reason_code)
    assert stored(env) == stored(twin_env), "point 4: pending and missing as today"


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_shape_alone_gets_rewrite_and_its_do_word_for_word(tmp_path, monkeypatch, tool):
    """C43-4: nothing is found in a text that fails SHAPE alone. Changed by
    briefs/S3-R13-A-tests.md (C50 point 2; was test_shape_alone_gets_rewrite_and_its_do_starts_as_
    point_1_says, any `do` starting "Say it again in other words" accepted): word for word."""
    env = env_of(tmp_path, monkeypatch, 1)
    make = (lambda t: decline_with("UNSUPPORTED_METRIC", t)) if tool == "decline" else \
        (lambda t: ask_with("other", t))
    env.ask(Q_ASK, Step(make(SHAPE_TEXT)), Step(make(PASS)))
    answer = rewrite_of(env, 0)
    assert set(answer) == {"error", "problems", "found", "do"}, answer
    assert answer["problems"] == ["SHAPE"] and answer["found"] == [], answer
    assert answer["do"].startswith(DO_LEAD)
    assert answer["do"] == "Say it again in other words, in one or two short sentences.", \
        answer["do"]


def test_found_is_the_first_five_without_repeats(tmp_path, monkeypatch):
    env = env_of(tmp_path, monkeypatch, 1)
    env.ask(Q_ASK, Step(ask_with("other", MANY)), Step(ask_with("other", PASS)))
    assert_rewrite(rewrite_of(env, 0), ["NUMBER"], MANY_FOUND)
    assert rewrite_of(env, 0)["do"] == ("Say it again in other words, without: two, three, four, "
                                        "five, six.")


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_after_a_rewrite_the_turn_goes_on_and_nothing_is_noted(tmp_path, monkeypatch, code):
    """C43-5: a decline answered REWRITE, then a count and a finding: ANSWERED, nothing noted,
    nothing pending."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, FAULTS["NUMBER"][0])),
                    Step(count(A_ID, Y25)), Step(finish("finding", COUNTED)))
    rewrite_of(env, 0)
    assert len(env.model.calls) == 3
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == 1
    assert refused(env) == [], "a request was noted"
    assert stored(env) == (None, None)


def test_after_a_rewrite_of_ask_user_nothing_is_asked(tmp_path, monkeypatch):
    """C43-5: an ask_user answered REWRITE, then a count and a finding: nothing is asked."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(ask_with("other", FAULTS["CLAIM"][0])), Step(count(A_ID, Y25)),
                    Step(finish("finding", COUNTED)))
    rewrite_of(env, 0)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert stored(env) == (None, None), "something was asked"
    assert refused(env) == []


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_after_a_rewrite_the_same_tool_with_no_text_gives_todays_row(tmp_path, monkeypatch,
                                                                     code):
    """Point 1: "the same tool again (with or without text)"; C43-7: the first try's codes."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, FAULTS["LABEL"][0])),
                    Step(decline_with(code)))
    rewrite_of(env, 0)
    assert (reply.status, reply.reason_code, reply.text) == ("UNSUPPORTED", code,
                                                             decline_row(code, 1)), reply.text
    assert reply.reply_style == "fixed", reply.reply_style
    assert failures_of(env, reply) == (["LABEL"], ["LABEL"])


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_after_a_rewrite_of_ask_user_a_decline_in_his_words(tmp_path, monkeypatch, code):
    """Point 1: "or anything else": the second try may be another tool (C43-8)."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(ask_with("other", FAULTS["CHARS"][0])),
                    Step(decline_with(code, PASS)))
    rewrite_of(env, 0)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), (reply.status, reply.text)
    assert reply.text == f"{PASS} {decline_rest(code, 1)}", reply.text
    assert reply.reply_style == "agent"
    assert failures_of(env, reply) == (["CHARS"], ["CHARS"])


# ---- point 1: two failing tries -----------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
@pytest.mark.parametrize("code", DECLINE_CODES)
def test_two_failing_decline_texts_end_with_todays_row_and_both_codes(tmp_path, monkeypatch,
                                                                      code, n):
    """Never a third: the passing third step is not reached."""
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(DECLINED[code], Step(decline_with(code, FAULTS["NUMBER"][0])),
                    Step(decline_with(code, FAULTS["CLAIM"][0])), Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 2, "a third try was asked for"
    rewrite_of(env, 0)
    assert (reply.status, reply.reason_code, reply.text) == ("UNSUPPORTED", code,
                                                             decline_row(code, n)), reply.text
    assert reply.reply_style == "fixed", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER", "CLAIM"], ["NUMBER", "CLAIM"])
    assert PASS not in reply.text


@pytest.mark.parametrize("case", list(ASKS))
def test_two_failing_ask_user_texts_end_with_todays_row_and_both_codes(tmp_path, monkeypatch,
                                                                       case):
    _, missing, _, row, _ = ASKS[case]
    twin_env = ask_env(tmp_path / "today", monkeypatch, case)
    twin_steps, _ = ask_steps(missing, LEAVE_OUT)
    twin_env.ask(Q_ASK, *twin_steps)
    env = ask_env(tmp_path / "text", monkeypatch, case)
    steps, at = ask_steps(missing, FAULTS["LABEL"][0], FAULTS["CHARS"][0], PASS)
    reply = env.ask(Q_ASK, *steps)
    assert len(env.model.calls) == at + 2, "a third try was asked for"
    rewrite_of(env, at)
    assert_needs_input(reply)
    assert reply.text == row, reply.text   # for `other`: with its can-ask sentence (C43-11)
    assert reply.reply_style == "fixed", reply.reply_style
    assert failures_of(env, reply) == (["LABEL", "CHARS"], ["LABEL", "CHARS"])
    assert stored(env) == stored(twin_env), "point 4: pending and missing as today"


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_the_same_code_twice_is_kept_once(tmp_path, monkeypatch, tool):
    env = env_of(tmp_path, monkeypatch, 1)
    make = (lambda t: decline_with("UNSUPPORTED_FIELD", t)) if tool == "decline" else \
        (lambda t: ask_with("other", t))
    reply = env.ask(Q_ASK, Step(make(FAULTS["NUMBER"][0])), Step(make(MANY)), Step(make(PASS)))
    assert len(env.model.calls) == 2
    assert reply.reply_style == "fixed"
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


def test_the_codes_of_both_tries_in_order(tmp_path, monkeypatch):
    """C43-7: first CLAIM, then NUMBER and CLAIM: CLAIM, NUMBER."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(ask_with("other", FAULTS["CLAIM"][0])),
                    Step(ask_with("other", BOTH)), Step(ask_with("other", PASS)))
    assert len(env.model.calls) == 2
    assert reply.text == f"{OTHER} {CAN_ASK[1]}", reply.text
    assert failures_of(env, reply) == (["CLAIM", "NUMBER"], ["CLAIM", "NUMBER"])


def test_one_own_words_try_per_turn_across_both_tools(tmp_path, monkeypatch):
    """C43-8: a failing decline, then a failing ask_user: NEEDS_other's row as today."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(decline_with("UNSUPPORTED_METRIC", FAULTS["NUMBER"][0])),
                    Step(ask_with("other", FAULTS["CLAIM"][0])), Step(ask_with("other", PASS)))
    assert len(env.model.calls) == 2, "a third try was asked for"
    rewrite_of(env, 0)
    assert_needs_input(reply)
    assert reply.text == f"{OTHER} {CAN_ASK[1]}", reply.text
    assert reply.reply_style == "fixed"
    assert failures_of(env, reply) == (["NUMBER", "CLAIM"], ["NUMBER", "CLAIM"])


# ---- point 1: no step or no time left ------------------------------------------------------------

@pytest.mark.parametrize("code", DECLINE_CODES)
def test_no_step_left_after_the_first_failure_ends_with_todays_row_at_once(tmp_path, monkeypatch,
                                                                            code):
    """C43-6: the failing decline is made in the last step (MOCO_MAX_STEPS 1): no REWRITE.
    With one step more it is asked to say it again."""
    text = FAULTS["NUMBER"][0]
    last = env_of(tmp_path / "last", monkeypatch, 1, MOCO_MAX_STEPS=1)
    reply = last.ask(DECLINED[code], Step(decline_with(code, text)),
                     Step(decline_with(code, PASS)))
    assert len(last.model.calls) == 1
    assert (reply.status, reply.reason_code, reply.text) == ("UNSUPPORTED", code,
                                                             decline_row(code, 1)), reply.text
    assert reply.reply_style == "fixed"
    assert failures_of(last, reply) == (["NUMBER"], ["NUMBER"])
    spare = env_of(tmp_path / "spare", monkeypatch, 1, MOCO_MAX_STEPS=2)
    reply = spare.ask(DECLINED[code], Step(decline_with(code, text)),
                      Step(decline_with(code, PASS)))
    rewrite_of(spare, 0)
    assert reply.text == f"{PASS} {decline_rest(code, 1)}", reply.text


@pytest.mark.parametrize("case", ["other, one source", "period, one source",
                                  "source, three sources (split after its question)"])
def test_no_step_left_after_a_failing_ask_user_ends_with_todays_row_at_once(tmp_path, monkeypatch,
                                                                             case):
    _, missing, _, row, _ = ASKS[case]
    steps, at = ask_steps(missing, FAULTS["CLAIM"][0], PASS)
    last = ask_env(tmp_path / "last", monkeypatch, case, MOCO_MAX_STEPS=at + 1)
    reply = last.ask(Q_ASK, *steps)
    assert len(last.model.calls) == at + 1
    assert_needs_input(reply)
    assert reply.text == row, reply.text
    assert reply.reply_style == "fixed"
    assert failures_of(last, reply) == (["CLAIM"], ["CLAIM"])
    spare = ask_env(tmp_path / "spare", monkeypatch, case, MOCO_MAX_STEPS=at + 2)
    reply = spare.ask(Q_ASK, *steps)
    rewrite_of(spare, at)
    assert reply.text == ask_reply(case, PASS), reply.text


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_less_than_five_seconds_left_ends_with_todays_row_at_once(tmp_path, monkeypatch, tool):
    """C43-6 (as T3): MOCO_TURN_SECONDS 15. With 4 seconds left after the failing call there is
    no REWRITE; with exactly 5 left there is."""
    if tool == "decline":
        def make(t):
            return decline_with("UNSUPPORTED_METRIC", t)
        row, sent = decline_row("UNSUPPORTED_METRIC", 1), \
            f"{PASS} {decline_rest('UNSUPPORTED_METRIC', 1)}"
    else:
        def make(t):
            return ask_with("other", t)
        row, sent = f"{OTHER} {CAN_ASK[1]}", PASS
    steps = (Step(make(FAULTS["NUMBER"][0])), Step(make(PASS)))
    tight = env_of(tmp_path / "tight", monkeypatch, 1, MOCO_TURN_SECONDS=15)
    reply = tight.ask(Q_ASK, *steps, seconds=11.0)
    assert len(tight.model.calls) == 1
    assert (reply.text, reply.reply_style) == (row, "fixed"), reply.text
    assert failures_of(tight, reply) == (["NUMBER"], ["NUMBER"])
    enough = env_of(tmp_path / "enough", monkeypatch, 1, MOCO_TURN_SECONDS=15)
    reply = enough.ask(Q_ASK, *steps, seconds=10.0)
    rewrite_of(enough, 0)
    assert (reply.text, reply.reply_style) == (sent, "agent"), reply.text


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_no_step_left_after_the_rewrite_ends_with_the_first_tries_row(tmp_path, monkeypatch,
                                                                       tool):
    """C43-6: REWRITE in step 1, then describe_data in step 2, the last (MOCO_MAX_STEPS 2): the
    turn ends with the first try's row, style fixed, its codes."""
    if tool == "decline":
        first, row = decline_with("UNSUPPORTED_FIELD", FAULTS["NUMBER"][0]), \
            decline_row("UNSUPPORTED_FIELD", 1)
    else:
        first, row = ask_with("other", FAULTS["NUMBER"][0]), f"{OTHER} {CAN_ASK[1]}"
    env = env_of(tmp_path, monkeypatch, 1, MOCO_MAX_STEPS=2)
    reply = env.ask(Q_ASK, Step(first), Step(p1.call("describe_data", {})))
    rewrite_of(env, 0)
    assert len(env.model.calls) == 2
    assert reply.text == row, (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "fixed"
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


# ---- point 1: apart from T3's second try for a finish --------------------------------------------

def test_an_own_words_rewrite_leaves_t3s_try_for_a_finish(tmp_path, monkeypatch):
    """C43-8: decline answered REWRITE; a failing talk finish then gets T3's REWRITE; a passing
    one is sent. Changed by briefs/S3-R28-A-tests.md (C64 point 1): T3's `do` is
    tsupport.HINTS["NUMBER"], now C64's hint (it was the first two sentences alone); the line is
    unchanged."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(decline_with("UNRECOGNIZED_QUESTION", FAULTS["NUMBER"][0])),
                    Step(finish("talk", T3_FAILING)), Step(finish("talk", HELLO_TEXT)))
    assert rewrite_of(env, 0)["do"] == do_of(["twice"])
    t3 = rewrite_of(env, 1)
    assert t3["problems"] == ["NUMBER"] and t3["do"] == HINTS["NUMBER"], t3
    assert len(env.model.calls) == 3
    assert (reply.status, reply.reply_kind, reply.reply_style, reply.text) == (
        "TALKED", "talk", "agent", HELLO_TEXT), (reply.status, reply.text)


def test_t3s_try_for_a_finish_leaves_the_own_words_try(tmp_path, monkeypatch):
    """C43-8: a failing talk finish gets T3's REWRITE; a failing decline then gets its own; a
    passing decline is sent in his words. Changed by briefs/S3-R28-A-tests.md (C64 point 1): the
    first `do` is tsupport.HINTS["NUMBER"], now C64's hint (it was the first two sentences
    alone); the line is unchanged."""
    code = "UNRECOGNIZED_QUESTION"
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(finish("talk", T3_FAILING)),
                    Step(decline_with(code, FAULTS["CLAIM"][0])), Step(decline_with(code, PASS)))
    assert rewrite_of(env, 0)["do"] == HINTS["NUMBER"]
    assert_rewrite(rewrite_of(env, 1), ["CLAIM"], ["due to"])
    assert len(env.model.calls) == 3
    assert (reply.status, reply.reason_code, reply.text) == ("UNSUPPORTED", code,
                                                             f"{PASS} {decline_rest(code, 1)}")
    assert reply.reply_style == "agent"


# ---- point 2: the quoted echo --------------------------------------------------------------------

@pytest.mark.parametrize("case", list(ECHOES))
def test_a_quoted_echo_of_the_message_passes_and_is_sent_as_written(tmp_path, monkeypatch, case):
    """An ask_user of `other` (C24's live call): his text alone (point 3), first try."""
    message, text, _ = ECHOES[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(ask_with("other", text)), Step(ask_with("other", PASS)))
    assert len(env.model.calls) == 1, f"no REWRITE was due: {env.answers()}"
    assert_needs_input(reply)
    assert reply.text == text, reply.text
    assert (reply.reply_style, reply.draft_failures) == ("agent", [])
    assert failures_of(env, reply) == ([], [])


@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
def test_a_quoted_echo_in_a_decline(tmp_path, monkeypatch, n):
    code = "UNSUPPORTED_METRIC"
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(C24_MESSAGE, Step(decline_with(code, DECLINE_ECHO)),
                    Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 1
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code)
    assert reply.text == f"{DECLINE_ECHO} {decline_rest(code, n)}", reply.text
    assert (reply.reply_style, reply.draft_failures) == ("agent", [])


def test_c24s_live_text_fails_only_number(tmp_path, monkeypatch):
    """C24's own text of live round 14: its quoted "Dangerous" is the person's word, so only
    NUMBER ("two") is left; the second try passes and is sent alone (point 3)."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(C24_MESSAGE, Step(ask_with("other", C24_LIVE)),
                    Step(ask_with("other", C24_SHORT)))
    assert_rewrite(rewrite_of(env, 0), ["NUMBER"], ["two"])
    assert rewrite_of(env, 0)["do"] == "Say it again in other words, without: two."
    assert_needs_input(reply)
    assert reply.text == C24_SHORT, reply.text
    assert reply.reply_style == "agent"
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("case", list(NOT_ECHOES))
def test_a_quoted_stretch_not_in_the_message_is_checked_as_today(tmp_path, monkeypatch, case):
    text, found = NOT_ECHOES[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(C24_MESSAGE, Step(ask_with("other", text)), Step(ask_with("other", C24_SHORT)))
    assert_rewrite(rewrite_of(env, 0), ["CLAIM"], found)
    assert reply.text == C24_SHORT, reply.text
    assert failures_of(env, reply) == (["CLAIM"], ["CLAIM"])


def test_a_quoted_echo_in_a_talk_finish_is_checked_as_today(tmp_path, monkeypatch):
    """C43-10: point 2 is for decline and ask_user only; a talk finish gets T3's REWRITE."""
    env = env_of(tmp_path, monkeypatch, 1)
    talk = "\"Dangerous\" isn't a word I can put on these records. Ask me for a count instead."
    premise_talk(talk, "CLAIM", labels_of(1))
    env.ask(C24_MESSAGE, Step(finish("talk", talk)), Step(finish("talk", HELLO_TEXT)))
    answer = rewrite_of(env, 0)
    assert answer["problems"] == ["CLAIM"] and answer["do"] == HINTS["CLAIM"], answer


# ---- point 3: no can-ask sentence after his own question -----------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3], ids=["one source", "two sources", "three sources"])
def test_c16s_case_is_his_question_alone(tmp_path, monkeypatch, n):
    env = env_of(tmp_path, monkeypatch, n)
    twin = env.ask(C16_MESSAGE, Step(ask_with("other")), thread_key=THREAD_2)
    assert twin.text == f"{OTHER} {CAN_ASK[n]}", "premise: today's row ends with can-ask"
    reply = env.ask(C16_MESSAGE, Step(ask_with("other", C16_TEXT)))
    assert len(env.model.calls) == 1
    assert_needs_input(reply)
    assert reply.text == C16_TEXT, reply.text
    assert CAN_ASK[n] not in reply.text
    assert (reply.reply_style, reply.draft_failures) == ("agent", [])
    assert stored(env) == stored(env, THREAD_2), "point 4: pending and missing as today"
    assert stored(env)[1] == "other"


def test_c16s_case_after_a_second_try_is_his_question_alone(tmp_path, monkeypatch):
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(C16_MESSAGE, Step(ask_with("other", FAULTS["NUMBER"][0])),
                    Step(ask_with("other", C16_TEXT)))
    rewrite_of(env, 0)
    assert reply.text == C16_TEXT, reply.text
    assert reply.reply_style == "agent"


@pytest.mark.parametrize("n", [1, 2, 3], ids=["one source", "two sources", "three sources"])
@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_decline_keeps_noted_and_the_can_ask_sentence(tmp_path, monkeypatch, code, n):
    """Point 3: a decline in his words keeps NOTED (not in UNRECOGNIZED_QUESTION's row) and the
    can-ask sentence, and the request is noted as today (A12)."""
    env = env_of(tmp_path, monkeypatch, n)
    twin = env.ask(DECLINED[code], Step(decline_with(code)), thread_key=THREAD_2)
    reply = env.ask(DECLINED[code], Step(decline_with(code, PASS)))
    assert reply.text == f"{PASS} {decline_rest(code, n)}", reply.text
    assert reply.text.endswith(CAN_ASK[n])
    assert FIRST[code] not in reply.text and FIRST[code] in twin.text
    assert reply.reply_style == "agent"
    assert (reply.status, reply.reason_code) == (twin.status, twin.reason_code)
    noted = [r["reason_code"] for r in refused(env)]
    assert noted == ([] if code == "UNRECOGNIZED_QUESTION" else [code, code]), noted


# ---- point 4: not changed ------------------------------------------------------------------------

@pytest.mark.parametrize("case", list(SOURCE_AS_TODAY))
def test_needs_source_with_one_or_two_sources_gets_no_rewrite(tmp_path, monkeypatch, case):
    """C43-12 (answer 1 to S3-R9-A): the text is not used, so not checked: no REWRITE and no
    failures."""
    n, row = SOURCE_AS_TODAY[case]
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(Q_ASK, Step(ask_with("source", FAULTS["NUMBER"][0])),
                    Step(ask_with("source", PASS)))
    assert len(env.model.calls) == 1, "a REWRITE was given"
    assert reply.text == row, reply.text
    assert (reply.reply_style, reply.draft_failures) == ("fixed", [])
    assert failures_of(env, reply) == ([], [])


@pytest.mark.parametrize("missing", ["other", "period", "source"])
def test_c32s_question_is_unchanged_with_a_failing_text(tmp_path, monkeypatch, missing):
    """Point 4 and C43-12: ask_user after AGES_NOT_STATED asks C32's question at once."""
    env = env_of(tmp_path, monkeypatch, 1)
    twin = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), Step(ask_with(missing)),
                   thread_key=THREAD_2)
    reply = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)),
                    Step(ask_with(missing, FAULTS["NUMBER"][0])), Step(ask_with(missing, PASS)))
    assert env.model.answer(0) == ages_not_stated("young people")
    assert len(env.model.calls) == 2, "a REWRITE was given"
    assert reply.text == twin.text == ages_question("young people"), reply.text
    assert (reply.status, reply.reason_code, reply.reply_style, reply.draft_failures) == \
        (twin.status, twin.reason_code, twin.reply_style, twin.draft_failures)
    assert stored(env) == stored(env, THREAD_2)
    nothing_counted(env, reply)


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_decline_after_a_count_with_a_failing_text_is_as_today(tmp_path, monkeypatch, code):
    """C43-12: the fixed rendering (C41-5) uses no text: no REWRITE."""
    env = env_of(tmp_path, monkeypatch, 1)
    twin = env.ask(DECLINED[code], Step(count(A_ID, Y25)), Step(decline_with(code)),
                   thread_key=THREAD_2)
    reply = env.ask(DECLINED[code], Step(count(A_ID, Y25)),
                    Step(decline_with(code, FAULTS["NUMBER"][0])), Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 2, "a REWRITE was given"
    assert (reply.status, reply.reason_code, reply.text, reply.reply_style,
            reply.draft_failures) == (twin.status, twin.reason_code, twin.text,
                                      twin.reply_style, twin.draft_failures)


@pytest.mark.parametrize("call", ["decline", "ask_user other", "ask_user period"])
def test_talk_off_a_failing_text_is_as_today(tmp_path, monkeypatch, call):
    """C43-13: no REWRITE, today's row, no failures."""
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK="off")
    text = FAULTS["NUMBER"][0]
    if call == "decline":
        reply = env.ask(DECLINED["UNSUPPORTED_METRIC"],
                        Step(decline_with("UNSUPPORTED_METRIC", text)),
                        Step(decline_with("UNSUPPORTED_METRIC", PASS)))
        calls, row = 1, decline_row("UNSUPPORTED_METRIC", 1)
    else:
        case = "other, one source" if call == "ask_user other" else "period, one source"
        _, missing, _, row, _ = ASKS[case]
        steps, at = ask_steps(missing, text, PASS)
        reply = env.ask(Q_ASK, *steps)
        calls = at + 1
    assert len(env.model.calls) == calls, "a REWRITE was given"
    assert reply.text == row, reply.text
    assert (reply.reply_style, reply.draft_failures) == ("fixed", [])


@pytest.mark.parametrize("call", ["decline UNSUPPORTED_FIELD", "decline UNSUPPORTED_METRIC",
                                  "ask_user other"])
def test_synthetic_mode_with_talk_on_is_as_today(tmp_path, call):
    """C43-13: the same call with and without a failing text (two threads of one agent)."""
    tool, value = call.split(" ")
    make = decline_with if tool == "decline" else ask_with
    env = p1.Env(tmp_path, MOCO_TALK="on")
    question = SUPPORTED["S1"][0]
    twin = env.ask(question, Step(make(value)), thread_key=THREAD_2)
    assert twin.model_called is True, "premise: the guard lets the question through"
    reply = env.ask(question, Step(make(value, FAULTS["NUMBER"][0])), Step(make(value, PASS)))
    assert len(env.model.calls) == 1, "a REWRITE was given"
    assert (reply.status, reply.reason_code, reply.text, reply.reply_style,
            reply.draft_failures) == (twin.status, twin.reason_code, twin.text,
                                      twin.reply_style, twin.draft_failures)


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_point_4_a_declines_status_and_stored_turn_after_a_second_try(tmp_path, monkeypatch,
                                                                      code):
    env = env_of(tmp_path, monkeypatch, 1)
    twin = env.ask(DECLINED[code], Step(decline_with(code)), thread_key=THREAD_2)
    reply = env.ask(DECLINED[code], Step(decline_with(code, FAULTS["CHARS"][0])),
                    Step(decline_with(code, PASS)))
    rewrite_of(env, 0)
    assert (reply.status, reply.reason_code) == (twin.status, twin.reason_code)
    assert stored(env) == stored(env, THREAD_2)
    record = turn_json(reply, env.runs_dir)
    assert (record["status"], record["reason_code"]) == (twin.status, twin.reason_code)
