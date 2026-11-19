"""Stage 3 Part A, C45 (docs/S3A-DESIGN.md; D-066): keep the sentences of his own words that pass.
In county mode with MOCO_TALK on, when a `decline` or `ask_user` text fails T1's talk check and the
turn would end with C41 point 3's row (no second try left under C43 point 1), the text is split
into sentences as T1 splits them and each is checked alone (with C43 point 2's quoted echo); the
sentences that pass, in their order, become his own words, if at least one passes and, for
`ask_user`, the last kept sentence ends with `?`. Brief: briefs/S3-R12-A-tests.md. Tests only; the
planning chat builds C45, on C41 (tests/s3/test_s3_c41.py) and C43 (tests/s3/test_s3_c43.py). All
data is SYNTHETIC fixtures; no real figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel, which repeats its last step when its steps run out) on the SYNTHETIC fixtures of
tests/s3, with MOCO_TALK on unless a test says.

C45's tests:
- C24's two failing tries end with the first and last sentences of the second try, style agent,
  failures NUMBER;
- a decline whose only sentence fails ends with today's row;
- an `ask_user` whose kept sentences end without `?` ends with today's row;
- with no step left after a first failing try, its passing sentences are kept;
- the kept sentences keep their order and are joined with one space.
And point 2 (only the text of the try that ends the turn is split) and point 3, "Not changed": a
text that passes whole; C43's second try (it comes first); C32's question; SYNTHETIC mode;
MOCO_TALK off.

READINGS (also in kit-log/raw/S3-R12-A-notes.txt; the open ones also in briefs/QUESTIONS.md):
- C45-1. C41's and C43's readings stand (C41-1 to C41-9, C43-1 to C43-13): the rows written out
  by hand in test_s3_c41.py; the turn's failures are the reply's `draft_failures` and the turn
  record's `failures`; `period` is sent as C43-9 sends it (a first call with no text, answered
  NO_PERIOD_QUESTION, then the call that would end the turn).
- C45-2. "Split as T1 does" (`replies._sentences`): a sentence ends at ., ! or ? followed by white
  space or the end of the text, as p1support.sentences reads R1. Each text here is checked first,
  as a premise, sentence by sentence with tests/t/tsupport.py's talk_faults and the env's labels;
  a sentence with a quoted echo of the person's words is premise-checked as written (it fails)
  and with the stretch written `it` (it passes), as C43-2.
- C45-3. "Made with them as in C41 point 2": the kept sentences joined by one space are the text
  that replaces the row's first sentence (the rest word for word), or, for `missing` `other`,
  the reply alone (C43 point 3). Style `agent`. "The turn's failures are still every failed
  try's codes": the codes of the whole text of each try that failed, in order, without repeats
  (C43-7), so a kept text has failures, unlike a text that passes whole.
- C45-4. "No second try is left under C43 point 1": the second own-words try failed, or the first
  failed with no step left (made in the last step of MOCO_MAX_STEPS) or less than five seconds
  left (MOCO_TURN_SECONDS less the FakeClock's seconds), as C43-6.
- C45-5. Point 2: when both tries fail, only the second try's text is split: a first try's
  passing sentences are never used, whether the second try keeps sentences or not.
- C45-6. Point 3, "C43's second try (it comes first)": a failing text with passing sentences, made
  with a step and five seconds left and no own-words second try used yet, is answered REWRITE
  (C43 point 1) as today, not kept at once.
- C45-7. "Joined with one space": also when the model wrote more white space, or a line break,
  between its sentences (T10 makes every run of white space one space before the check, so both
  readings of where C45 splits give the same sentences).
- C45-8. A text not used is not checked and not split (C43-12): NEEDS_source with one or two
  sources, C32's question, a decline after a count. Talk off: the text is not read. SYNTHETIC
  mode with talk on: a call with a text ends as one without it.
- C45-9. A text that fails SHAPE alone (more than six sentences) has every sentence pass alone.
  Pinned by brief S3-R14-A to C45's answer 1 (planning chat, 16 Nov 22:45 EST): what is kept
  must also pass T1's check as a whole, so it ends with today's row, style fixed, its codes.
  (Round 12 accepted both this and the whole text kept, style agent.) For `ask_user` the case's
  last sentence ends without `?`, so it was today's row already.
- C45-10. After a REWRITE, a turn that runs out of steps with nothing made ends with the first
  try's row (C43-6). Pinned by brief S3-R14-A to C45's answer 2: today's row for the first try,
  style fixed, its codes (a second try was given, so point 1 never applied to that try). (Round
  12 accepted both this and the row made with the first try's passing sentences, style agent.)
"""
import sys
from pathlib import Path

import pytest

import p1support as p1
from p1support import THREAD_2, Step, sentences
from s3support import A_ID, count
from support import SUPPORTED
from test_s3_c36 import ages_not_stated
from test_s3_c41 import (ASKS, DECLINE_CODES, DECLINED, FIRST, PASS, PASSING, Q_ASK,
                         SOURCE_AS_TODAY, ask_env, ask_with, decline_rest, decline_row,
                         decline_with, env_of, failures_of, labels_of, rest_of, stored)
from test_s3_c43 import (C24_LIVE, C24_MESSAGE, FAULTS, NOT_ECHOES, SHAPE_TEXT, ask_steps,
                         assert_needs_input, assert_rewrite, rewrite_of)
from test_s3_round5 import Y25
from test_s3_round5b import YOUNG, YOUNG_AGES, ages_question, nothing_counted

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import premise_talk, talk_faults  # noqa: E402

# ---- the model's own texts ----------------------------------------------------------------------

# C24, live round 16: the same question twice; only its middle sentence fails (NUMBER, "two").
# C45 elides the middle sentence ("I can compare ... between the two districts."): it is written
# here with C43's words of live round 14, the sentence C45 shortens.
C24_FIRST = '"Dangerous" could mean a few different things in these records.'
C24_FIRST_AS_IT = "it could mean a few different things in these records."
C24_MIDDLE = ("I can compare things like arrests, use of force, or service calls between the two "
              "districts.")
C24_LAST = "Which kind of record would you like me to look at?"
C24_R16 = f"{C24_FIRST} {C24_MIDDLE} {C24_LAST}"
C24_KEPT = f"{C24_FIRST} {C24_LAST}"

# A decline: the middle sentence fails NUMBER ("twice").
D_PASS_1 = "A forecast is something I can't make."
D_FAIL = "It would take twice the guesswork."
D_PASS_2 = "I count records that already exist."
DECLINE_TEXT = f"{D_PASS_1} {D_FAIL} {D_PASS_2}"
DECLINE_KEPT = f"{D_PASS_1} {D_PASS_2}"
DECLINE_BOTH_FAIL = f"{D_FAIL} {FAULTS['CLAIM'][0]}"   # two sentences, neither passes

# An ask_user: the middle sentence fails NUMBER ("two").
A_PASS = "I want to get this right for you."
A_FAIL = "I could look at two kinds of record."
A_QUESTION = "What would you like me to look at?"
ASK_TEXT = f"{A_PASS} {A_FAIL} {A_QUESTION}"
ASK_KEPT = f"{A_PASS} {A_QUESTION}"
# The kept sentences end without "?": the question is the sentence that fails.
ASK_NO_Q = f"{A_PASS} Which of the two do you mean?"
# The last kept sentence, not the last sentence of the text, must end with "?".
ASK_Q_THEN_FAIL = f"{A_QUESTION} {A_FAIL}"                  # kept: A_QUESTION
ASK_Q_NOT_LAST = f"{A_QUESTION} {A_FAIL} {A_PASS}"          # kept ends with A_PASS

# Five sentences, two failing (NUMBER, then CLAIM), with ! and ? endings: order and joining.
O_1 = "Happy to help with that!"
O_2 = "It might be twice as hard."
O_3 = "I need a little more to go on."
O_4 = "That is due to how the records are kept."
O_5 = "Which kind of record do you mean?"
ORDER_TEXT = f"{O_1} {O_2} {O_3} {O_4} {O_5}"
ORDER_UNTIDY = f"{O_1}  {O_2}\n{O_3}   {O_4} {O_5}"          # C45-7
ORDER_KEPT = f"{O_1} {O_3} {O_5}"


def premises():
    for n in (1, 2, 3):
        labels = labels_of(n)
        for passing in (C24_FIRST_AS_IT, C24_LAST, D_PASS_1, D_PASS_2, A_PASS, A_QUESTION, O_1, O_3,
                        O_5):
            premise_talk(passing, None, labels)
        premise_talk(C24_FIRST, "CLAIM", labels)            # as written: "dangerous"
        for failing in (C24_MIDDLE, D_FAIL, A_FAIL, "Which of the two do you mean?", O_2):
            premise_talk(failing, "NUMBER", labels)
        premise_talk(O_4, "CLAIM", labels)
        premise_talk(FAULTS["CLAIM"][0], "CLAIM", labels)
        premise_talk(C24_R16.replace('"Dangerous"', "it"), "NUMBER", labels)
        assert talk_faults(C24_R16, labels) == {"NUMBER", "CLAIM"}
        for text in (DECLINE_TEXT, ASK_TEXT, ASK_NO_Q, ASK_Q_THEN_FAIL, ASK_Q_NOT_LAST):
            premise_talk(text, "NUMBER", labels)
        assert talk_faults(ORDER_TEXT, labels) == {"NUMBER", "CLAIM"}
        assert talk_faults(ORDER_UNTIDY, labels) == {"NUMBER", "CLAIM"}
        assert talk_faults(DECLINE_BOTH_FAIL, labels) == {"NUMBER", "CLAIM"}
        premise_talk(SHAPE_TEXT, "SHAPE", labels)
        for one in sentences(SHAPE_TEXT):                    # C45-9: each passes alone
            premise_talk(one, None, labels)
        for text, _ in NOT_ECHOES.values():                  # C43's: its last sentence passes
            *rest, last = sentences(text)
            premise_talk(last, None, labels)
            assert last.endswith("?") and all(talk_faults(s, labels) for s in rest), text


def test_premise_the_texts_and_their_sentences_pass_and_fail_as_their_cases_say():
    premises()


def test_premise_the_texts_split_into_their_sentences():
    """C45-2: each text splits, as T1 splits, into the sentences it is written from."""
    assert sentences(C24_R16) == [C24_FIRST, C24_MIDDLE, C24_LAST]
    assert sentences(DECLINE_TEXT) == [D_PASS_1, D_FAIL, D_PASS_2]
    assert sentences(ASK_TEXT) == [A_PASS, A_FAIL, A_QUESTION]
    assert sentences(ORDER_TEXT) == sentences(ORDER_UNTIDY) == [O_1, O_2, O_3, O_4, O_5]
    assert len(sentences(SHAPE_TEXT)) == 7
    for single in FAULTS.values():
        assert sentences(single[0]) == [single[0]]


def test_premise_c24s_text_differs_from_c43s_only_in_its_first_sentence():
    """C45's C24 text is C43's live text with the first sentence of live round 16."""
    assert sentences(C24_LIVE)[1:] == [C24_MIDDLE, C24_LAST]


# ---- helpers ------------------------------------------------------------------------------------

def ask_reply(case, words):
    """C45-3: the row of `case` made with his kept words (C41 point 2; C43 point 3 for other)."""
    _, missing, _, _, _ = ASKS[case]
    return words if missing == "other" else f"{words} {rest_of(case)}"


def assert_unsupported(reply, code):
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), \
        (reply.status, reply.reason_code, reply.text)


# ---- C24: two failing tries, the first and last sentences of the second kept ------------------

@pytest.mark.parametrize("n", [1, 2, 3], ids=["one source", "two sources", "three sources"])
def test_c24s_two_failing_tries_end_with_the_first_and_last_sentences(tmp_path, monkeypatch, n):
    env = env_of(tmp_path, monkeypatch, n)
    twin = env.ask(C24_MESSAGE, Step(ask_with("other")), thread_key=THREAD_2)
    reply = env.ask(C24_MESSAGE, Step(ask_with("other", C24_R16)),
                    Step(ask_with("other", C24_R16)), Step(ask_with("other", PASS)))
    assert len(env.model.calls) == 2, "one second try, never a third"
    assert_rewrite(rewrite_of(env, 0), ["NUMBER"], ["two"])
    assert_needs_input(reply)
    assert reply.text == C24_KEPT, reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])
    assert (reply.status, reply.reason_code) == (twin.status, twin.reason_code)
    assert stored(env) == stored(env, THREAD_2), "C43 point 4: pending and missing as today"


def test_c24_after_c43s_live_text_the_second_tries_sentences_are_kept(tmp_path, monkeypatch):
    """Point 2: round 14's text, then round 16's: the kept words are the second try's."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(C24_MESSAGE, Step(ask_with("other", C24_LIVE)),
                    Step(ask_with("other", C24_R16)))
    assert_rewrite(rewrite_of(env, 0), ["NUMBER"], ["two"])
    assert (reply.text, reply.reply_style) == (C24_KEPT, "agent"), reply.text
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("case", list(NOT_ECHOES))
def test_a_sentence_quoting_words_not_in_the_message_is_dropped(tmp_path, monkeypatch, case):
    """C43 point 2 within C45: the quoted stretch is not the person's words one after another,
    so its sentence fails alone (CLAIM); the question after it is kept."""
    text, found = NOT_ECHOES[case]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(C24_MESSAGE, Step(ask_with("other", text)), Step(ask_with("other", text)))
    assert_rewrite(rewrite_of(env, 0), ["CLAIM"], found)
    assert (reply.text, reply.reply_style) == (sentences(text)[-1], "agent"), reply.text
    assert failures_of(env, reply) == (["CLAIM"], ["CLAIM"])


# ---- decline: kept sentences, and an only sentence that fails --------------------------------

@pytest.mark.parametrize("n", [1, 2, 3], ids=["one source", "two sources", "three sources"])
@pytest.mark.parametrize("code", DECLINE_CODES)
def test_two_failing_decline_tries_keep_the_second_tries_passing_sentences(tmp_path, monkeypatch,
                                                                           code, n):
    env = env_of(tmp_path, monkeypatch, n)
    twin = env.ask(DECLINED[code], Step(decline_with(code)), thread_key=THREAD_2)
    reply = env.ask(DECLINED[code], Step(decline_with(code, DECLINE_TEXT)),
                    Step(decline_with(code, DECLINE_TEXT)), Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 2, "one second try, never a third"
    assert_rewrite(rewrite_of(env, 0), ["NUMBER"], ["twice"])
    assert_unsupported(reply, code)
    assert reply.text == f"{DECLINE_KEPT} {decline_rest(code, n)}", reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])
    assert FIRST[code] not in reply.text
    assert stored(env) == stored(env, THREAD_2)
    assert (reply.status, reply.reason_code) == (twin.status, twin.reason_code)
    nothing_counted(env, reply)


@pytest.mark.parametrize("fault", ["NUMBER", "LABEL", "CLAIM", "CHARS"])
@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_decline_whose_only_sentence_fails_ends_with_todays_row(tmp_path, monkeypatch, code, n,
                                                                  fault):
    text = FAULTS[fault][0]
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(DECLINED[code], Step(decline_with(code, text)),
                    Step(decline_with(code, text)), Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 2
    rewrite_of(env, 0)
    assert_unsupported(reply, code)
    assert reply.text == decline_row(code, n), reply.text
    assert reply.reply_style == "fixed", reply.reply_style
    assert failures_of(env, reply) == ([fault], [fault])


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_decline_whose_sentences_all_fail_ends_with_todays_row(tmp_path, monkeypatch, code):
    """Point 1: "if at least one passes"."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, DECLINE_BOTH_FAIL)),
                    Step(decline_with(code, DECLINE_BOTH_FAIL)))
    rewrite_of(env, 0)
    assert (reply.text, reply.reply_style) == (decline_row(code, 1), "fixed"), reply.text
    assert failures_of(env, reply) == (["NUMBER", "CLAIM"], ["NUMBER", "CLAIM"])


def test_a_declines_kept_sentences_need_no_question_mark(tmp_path, monkeypatch):
    """The `?` rule is for ask_user only: a decline's kept words end with "." and are used."""
    code = "UNSUPPORTED_METRIC"
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, ASK_NO_Q)),
                    Step(decline_with(code, ASK_NO_Q)))
    rewrite_of(env, 0)
    assert (reply.text, reply.reply_style) == (f"{A_PASS} {decline_rest(code, 1)}", "agent"), \
        reply.text


# ---- ask_user: kept sentences, and kept sentences that end without "?" ------------------------

@pytest.mark.parametrize("case", list(ASKS))
def test_two_failing_ask_user_tries_keep_the_second_tries_passing_sentences(tmp_path, monkeypatch,
                                                                            case):
    _, missing, _, _, first = ASKS[case]
    twin_env = ask_env(tmp_path / "today", monkeypatch, case)
    twin_steps, _ = ask_steps(missing, p1.LEAVE_OUT)
    twin = twin_env.ask(Q_ASK, *twin_steps)
    env = ask_env(tmp_path / "text", monkeypatch, case)
    steps, at = ask_steps(missing, ASK_TEXT, ASK_TEXT, PASS)
    reply = env.ask(Q_ASK, *steps)
    assert len(env.model.calls) == at + 2, "one second try, never a third"
    assert_rewrite(rewrite_of(env, at), ["NUMBER"], ["two"])
    assert_needs_input(reply)
    assert reply.text == ask_reply(case, ASK_KEPT), reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])
    assert not reply.text.startswith(first)
    assert (reply.status, reply.reason_code) == (twin.status, twin.reason_code)
    assert stored(env) == stored(twin_env), "C43 point 4: pending and missing as today"


@pytest.mark.parametrize("text", [ASK_NO_Q, ASK_Q_NOT_LAST],
                         ids=["the question fails", "a statement kept after the question"])
@pytest.mark.parametrize("case", list(ASKS))
def test_an_ask_user_whose_kept_sentences_end_without_a_question_mark_is_todays_row(
        tmp_path, monkeypatch, case, text):
    _, missing, _, row, _ = ASKS[case]
    env = ask_env(tmp_path, monkeypatch, case)
    steps, at = ask_steps(missing, text, text, PASS)
    reply = env.ask(Q_ASK, *steps)
    assert len(env.model.calls) == at + 2
    rewrite_of(env, at)
    assert_needs_input(reply)
    assert reply.text == row, reply.text   # for `other`: with its can-ask sentence (C43-11)
    assert reply.reply_style == "fixed", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("case", ["other, one source", "period, one source",
                                  "source, three sources (split after its question)"])
def test_the_last_kept_sentence_not_the_last_sentence_must_end_with_a_question_mark(
        tmp_path, monkeypatch, case):
    _, missing, _, _, _ = ASKS[case]
    env = ask_env(tmp_path, monkeypatch, case)
    steps, at = ask_steps(missing, ASK_Q_THEN_FAIL, ASK_Q_THEN_FAIL)
    reply = env.ask(Q_ASK, *steps)
    rewrite_of(env, at)
    assert (reply.text, reply.reply_style) == (ask_reply(case, A_QUESTION), "agent"), reply.text


# ---- no step or no time left after a first failing try: its passing sentences kept ------------

@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
@pytest.mark.parametrize("code", DECLINE_CODES)
def test_no_step_left_after_a_first_failing_decline_its_passing_sentences_are_kept(
        tmp_path, monkeypatch, code, n):
    env = env_of(tmp_path, monkeypatch, n, MOCO_MAX_STEPS=1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, DECLINE_TEXT)),
                    Step(decline_with(code, PASS)))
    assert len(env.model.calls) == 1, "no REWRITE in the last step"
    assert_unsupported(reply, code)
    assert reply.text == f"{DECLINE_KEPT} {decline_rest(code, n)}", reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("case", list(ASKS))
def test_no_step_left_after_a_first_failing_ask_user_its_passing_sentences_are_kept(
        tmp_path, monkeypatch, case):
    _, missing, _, _, _ = ASKS[case]
    steps, at = ask_steps(missing, ASK_TEXT, PASS)
    env = ask_env(tmp_path, monkeypatch, case, MOCO_MAX_STEPS=at + 1)
    reply = env.ask(Q_ASK, *steps)
    assert len(env.model.calls) == at + 1, "no REWRITE in the last step"
    assert_needs_input(reply)
    assert reply.text == ask_reply(case, ASK_KEPT), reply.text
    assert reply.reply_style == "agent", reply.reply_style
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


def test_no_step_left_after_c24s_first_try_its_first_and_last_sentences_are_kept(tmp_path,
                                                                                  monkeypatch):
    env = env_of(tmp_path, monkeypatch, 1, MOCO_MAX_STEPS=1)
    reply = env.ask(C24_MESSAGE, Step(ask_with("other", C24_R16)))
    assert len(env.model.calls) == 1
    assert (reply.text, reply.reply_style) == (C24_KEPT, "agent"), reply.text
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("case", ["other, one source", "period, one source"])
def test_no_step_left_an_ask_user_without_a_kept_question_is_todays_row(tmp_path, monkeypatch,
                                                                        case):
    _, missing, _, row, _ = ASKS[case]
    steps, at = ask_steps(missing, ASK_NO_Q)
    env = ask_env(tmp_path, monkeypatch, case, MOCO_MAX_STEPS=at + 1)
    reply = env.ask(Q_ASK, *steps)
    assert len(env.model.calls) == at + 1
    assert (reply.text, reply.reply_style) == (row, "fixed"), reply.text
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_less_than_five_seconds_left_after_a_first_failing_try_its_passing_sentences_are_kept(
        tmp_path, monkeypatch, tool):
    """C45-4 (as C43's test): MOCO_TURN_SECONDS 15, 4 seconds left after the failing call: no
    REWRITE, the passing sentences kept; with exactly 5 left, REWRITE first (C45-6)."""
    code = "UNSUPPORTED_METRIC"
    if tool == "decline":
        def make(t):
            return decline_with(code, t)
        text, kept = DECLINE_TEXT, f"{DECLINE_KEPT} {decline_rest(code, 1)}"
    else:
        def make(t):
            return ask_with("other", t)
        text, kept = ASK_TEXT, ASK_KEPT
    tight = env_of(tmp_path / "tight", monkeypatch, 1, MOCO_TURN_SECONDS=15)
    reply = tight.ask(Q_ASK, Step(make(text)), Step(make(PASS)), seconds=11.0)
    assert len(tight.model.calls) == 1
    assert (reply.text, reply.reply_style) == (kept, "agent"), reply.text
    assert failures_of(tight, reply) == (["NUMBER"], ["NUMBER"])
    enough = env_of(tmp_path / "enough", monkeypatch, 1, MOCO_TURN_SECONDS=15)
    reply = enough.ask(Q_ASK, Step(make(text)), Step(make(PASS)), seconds=10.0)
    rewrite_of(enough, 0)
    assert len(enough.model.calls) == 2


# ---- order and one space ------------------------------------------------------------------------

@pytest.mark.parametrize("text", [ORDER_TEXT, ORDER_UNTIDY], ids=["one space", "more white space"])
@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_the_kept_sentences_keep_their_order_and_are_joined_with_one_space(tmp_path, monkeypatch,
                                                                           tool, text):
    """Five sentences, the second and fourth failing: the first, third and fifth, in that order,
    each with its own end mark, joined by one space (C45-7)."""
    code = "UNSUPPORTED_FIELD"
    make = (lambda t: decline_with(code, t)) if tool == "decline" else \
        (lambda t: ask_with("other", t))
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(make(text)), Step(make(text)))
    assert_rewrite(rewrite_of(env, 0), ["NUMBER", "CLAIM"], ["twice", "due to"])
    want = ORDER_KEPT if tool == "ask_user" else f"{ORDER_KEPT} {decline_rest(code, 1)}"
    assert reply.text == want, reply.text
    assert reply.reply_style == "agent"
    assert failures_of(env, reply) == (["NUMBER", "CLAIM"], ["NUMBER", "CLAIM"])


# ---- point 2: only the text of the try that ends the turn ---------------------------------------

@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_a_first_tries_passing_sentences_are_not_used(tmp_path, monkeypatch, tool):
    """The first try keeps sentences, the second's only sentence fails: today's row, the codes
    of both tries."""
    code = "UNSUPPORTED_METRIC"
    if tool == "decline":
        first, second = decline_with(code, DECLINE_TEXT), decline_with(code, FAULTS["CLAIM"][0])
        row = decline_row(code, 1)
        words = (D_PASS_1, D_PASS_2)
    else:
        first, second = ask_with("other", ASK_TEXT), ask_with("other", FAULTS["CLAIM"][0])
        row = ASKS["other, one source"][3]
        words = (A_PASS, A_QUESTION)
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(first), Step(second))
    rewrite_of(env, 0)
    assert (reply.text, reply.reply_style) == (row, "fixed"), reply.text
    assert failures_of(env, reply) == (["NUMBER", "CLAIM"], ["NUMBER", "CLAIM"])
    assert not any(w in reply.text for w in words)


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_the_second_tries_sentences_are_kept_after_another_first_try(tmp_path, monkeypatch, tool):
    """A first try that fails whole (CLAIM), a second that keeps sentences (NUMBER): its kept
    words, the codes of both tries in order."""
    code = "UNSUPPORTED_METRIC"
    if tool == "decline":
        make, text, want = (lambda t: decline_with(code, t)), DECLINE_TEXT, \
            f"{DECLINE_KEPT} {decline_rest(code, 1)}"
    else:
        make, text, want = (lambda t: ask_with("other", t)), ASK_TEXT, ASK_KEPT
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(make(FAULTS["CLAIM"][0])), Step(make(text)))
    assert_rewrite(rewrite_of(env, 0), ["CLAIM"], ["due to"])
    assert (reply.text, reply.reply_style) == (want, "agent"), reply.text
    assert failures_of(env, reply) == (["CLAIM", "NUMBER"], ["CLAIM", "NUMBER"])


def test_a_decline_then_an_ask_user_the_ask_users_sentences_are_kept(tmp_path, monkeypatch):
    """C43-8: one own-words second try across both tools; the ask_user ends the turn, so its text
    is split."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(Q_ASK, Step(decline_with("UNSUPPORTED_METRIC", DECLINE_TEXT)),
                    Step(ask_with("other", ASK_TEXT)))
    rewrite_of(env, 0)
    assert_needs_input(reply)
    assert (reply.text, reply.reply_style) == (ASK_KEPT, "agent"), reply.text
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_no_step_left_after_the_rewrite_ends_with_the_first_tries_row(tmp_path, monkeypatch, tool):
    """C45-10: REWRITE in step 1, describe_data in step 2, the last: today's row for the first
    try, style fixed, its codes (C45's answer 2; changed by brief S3-R14-A, which pins it: round
    12 also accepted the row made with the first try's kept sentences, style agent)."""
    code = "UNSUPPORTED_FIELD"
    if tool == "decline":
        first, row = decline_with(code, DECLINE_TEXT), decline_row(code, 1)
    else:
        first, row = ask_with("other", ASK_TEXT), ASKS["other, one source"][3]
    env = env_of(tmp_path, monkeypatch, 1, MOCO_MAX_STEPS=2)
    reply = env.ask(Q_ASK, Step(first), Step(p1.call("describe_data", {})))
    rewrite_of(env, 0)
    assert len(env.model.calls) == 2
    assert (reply.text, reply.reply_style) == (row, "fixed"), (reply.status, reply.reason_code,
                                                               reply.text, reply.reply_style)
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


# ---- point 3: not changed ------------------------------------------------------------------------

@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_c43s_second_try_comes_first_and_a_passing_one_is_sent_whole(tmp_path, monkeypatch, tool):
    """C45-6: with a step and five seconds left, the first try is answered REWRITE, not kept at
    once; a second try that passes whole is sent whole, as today."""
    code = "UNSUPPORTED_METRIC"
    whole = PASSING["two sentences"]
    if tool == "decline":
        make, want = (lambda t: decline_with(code, t)), f"{whole} {decline_rest(code, 1)}"
    else:
        make, want = (lambda t: ask_with("other", t)), whole
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(make(DECLINE_TEXT)), Step(make(whole)))
    assert len(env.model.calls) == 2, "the first try was not answered REWRITE"
    assert_rewrite(rewrite_of(env, 0), ["NUMBER"], ["twice"])
    assert (reply.text, reply.reply_style) == (want, "agent"), reply.text
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_a_text_that_passes_whole_is_sent_whole_with_no_failures(tmp_path, monkeypatch, tool):
    code = "UNSUPPORTED_METRIC"
    whole = PASSING["two sentences"]
    if tool == "decline":
        make, want = (lambda t: decline_with(code, t)), f"{whole} {decline_rest(code, 1)}"
    else:
        make, want = (lambda t: ask_with("other", t)), whole
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(make(whole)))
    assert len(env.model.calls) == 1
    assert (reply.text, reply.reply_style, reply.draft_failures) == (want, "agent", [])
    assert failures_of(env, reply) == ([], [])


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_shape_alone_every_sentence_passes_alone(tmp_path, monkeypatch, tool):
    """C45-9: SHAPE_TEXT twice ends with today's row, style fixed, its codes (C45's answer 1:
    what is kept must pass T1's check as a whole). A decline: changed by brief S3-R14-A, which
    pins it (round 12 also accepted the whole text kept, style agent). An ask_user: its last
    sentence ends without "?", so today's row, as before."""
    code = "UNSUPPORTED_METRIC"
    env = env_of(tmp_path, monkeypatch, 1)
    if tool == "decline":
        make, row = (lambda t: decline_with(code, t)), decline_row(code, 1)
    else:
        make, row = (lambda t: ask_with("other", t)), ASKS["other, one source"][3]
    reply = env.ask(DECLINED[code], Step(make(SHAPE_TEXT)), Step(make(SHAPE_TEXT)))
    rewrite_of(env, 0)
    assert (reply.text, reply.reply_style) == (row, "fixed"), (reply.text, reply.reply_style)
    assert failures_of(env, reply) == (["SHAPE"], ["SHAPE"])


@pytest.mark.parametrize("case", list(SOURCE_AS_TODAY))
def test_needs_source_with_one_or_two_sources_does_not_split_the_text(tmp_path, monkeypatch, case):
    """C45-8: the text is not used, so not checked or split: today's row, no failures."""
    n, row = SOURCE_AS_TODAY[case]
    env = env_of(tmp_path, monkeypatch, n)
    reply = env.ask(Q_ASK, Step(ask_with("source", ASK_TEXT)), Step(ask_with("source", ASK_TEXT)))
    assert len(env.model.calls) == 1, "a REWRITE was given"
    assert (reply.text, reply.reply_style, reply.draft_failures) == (row, "fixed", [])
    assert failures_of(env, reply) == ([], [])


@pytest.mark.parametrize("missing", ["other", "period", "source"])
def test_c32s_question_is_unchanged_with_a_text_that_keeps_sentences(tmp_path, monkeypatch,
                                                                     missing):
    env = env_of(tmp_path, monkeypatch, 1)
    twin = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), Step(ask_with(missing)),
                   thread_key=THREAD_2)
    reply = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), Step(ask_with(missing, ASK_TEXT)),
                    Step(ask_with(missing, ASK_TEXT)))
    assert env.model.answer(0) == ages_not_stated("young people")
    assert len(env.model.calls) == 2, "a REWRITE was given"
    assert reply.text == twin.text == ages_question("young people"), reply.text
    assert (reply.status, reply.reason_code, reply.reply_style, reply.draft_failures) == \
        (twin.status, twin.reason_code, twin.reply_style, twin.draft_failures)
    assert stored(env) == stored(env, THREAD_2)
    nothing_counted(env, reply)


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_decline_after_a_count_with_a_text_that_keeps_sentences_is_as_today(tmp_path,
                                                                             monkeypatch, code):
    env = env_of(tmp_path, monkeypatch, 1)
    twin = env.ask(DECLINED[code], Step(count(A_ID, Y25)), Step(decline_with(code)),
                   thread_key=THREAD_2)
    reply = env.ask(DECLINED[code], Step(count(A_ID, Y25)),
                    Step(decline_with(code, DECLINE_TEXT)), Step(decline_with(code, DECLINE_TEXT)))
    assert len(env.model.calls) == 2, "a REWRITE was given"
    assert (reply.status, reply.reason_code, reply.text, reply.reply_style,
            reply.draft_failures) == (twin.status, twin.reason_code, twin.text,
                                      twin.reply_style, twin.draft_failures)
    assert D_PASS_1 not in reply.text


@pytest.mark.parametrize("call", ["decline", "ask_user other", "ask_user period"])
@pytest.mark.parametrize("steps", [1, None], ids=["no step left", "steps left"])
def test_talk_off_a_text_that_keeps_sentences_is_as_today(tmp_path, monkeypatch, call, steps):
    """C45-8: no REWRITE, no kept words, today's row, no failures."""
    settings = {"MOCO_TALK": "off"}
    if call == "decline":
        code = "UNSUPPORTED_METRIC"
        if steps:
            settings["MOCO_MAX_STEPS"] = steps
        env = env_of(tmp_path, monkeypatch, 1, **settings)
        reply = env.ask(DECLINED[code], Step(decline_with(code, DECLINE_TEXT)),
                        Step(decline_with(code, DECLINE_TEXT)))
        calls, row = 1, decline_row(code, 1)
    else:
        case = "other, one source" if call == "ask_user other" else "period, one source"
        _, missing, _, row, _ = ASKS[case]
        texts, at = ask_steps(missing, ASK_TEXT, ASK_TEXT)
        if steps:
            settings["MOCO_MAX_STEPS"] = at + 1
        env = env_of(tmp_path, monkeypatch, 1, **settings)
        reply = env.ask(Q_ASK, *texts)
        calls = at + 1
    assert len(env.model.calls) == calls, "a REWRITE was given"
    assert (reply.text, reply.reply_style, reply.draft_failures) == (row, "fixed", [])


@pytest.mark.parametrize("call", ["decline UNSUPPORTED_FIELD", "decline UNSUPPORTED_METRIC",
                                  "ask_user other"])
def test_synthetic_mode_with_talk_on_is_as_today(tmp_path, call):
    """C45-8: the same call with and without a text that keeps sentences (two threads)."""
    tool, value = call.split(" ")
    make = decline_with if tool == "decline" else ask_with
    text = DECLINE_TEXT if tool == "decline" else ASK_TEXT
    env = p1.Env(tmp_path, MOCO_TALK="on")
    question = SUPPORTED["S1"][0]
    twin = env.ask(question, Step(make(value)), thread_key=THREAD_2)
    assert twin.model_called is True, "premise: the guard lets the question through"
    reply = env.ask(question, Step(make(value, text)), Step(make(value, text)))
    assert len(env.model.calls) == 1, "a REWRITE was given"
    assert (reply.status, reply.reason_code, reply.text, reply.reply_style,
            reply.draft_failures) == (twin.status, twin.reason_code, twin.text,
                                      twin.reply_style, twin.draft_failures)
