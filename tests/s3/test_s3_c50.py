"""Stage 3 Part A, C50 (docs/S3A-DESIGN.md; D-069): a failed try of his own words is always on
record, and two loose ends of C41 and C43. Brief: briefs/S3-R13-A-tests.md. Tests only; the
planning chat builds point 1 (points 2 and 3 are built, so their tests pass today). The finding
point 1 answers is DEFECT 4 of kit-log/raw/FABLE-REVIEW-OF-OPUS.md (probes `rewrite_then_talk` and
`rewrite_then_count` of kit-log/raw/FABLE-REVIEW-probe-turns.py); points 2 and 3 are
CHAT-BUILDS-check-5's PROOF GAP 1 and RECORD ERROR 1. All data is SYNTHETIC fixtures; no real
figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3, county mode with MOCO_TALK on.

C50's tests:
- point 1: a failing decline text, REWRITE, then a talk text: TALKED, failures the try's codes;
  the same then a count and a finding: ANSWERED, failures the try's codes; and (the rest of
  point 1's list) the fixed rendering, a limit, an `ask_user` try, its own codes after the try's,
  no repeats;
- point 2: a text failing SHAPE alone gets the `do` of point 2 word for word;
- point 3: a `text` with stars, backticks, a picture and a line break is sent without them.

READINGS (also in kit-log/raw/S3-R13-A-notes.txt):
- C50-1. "Its failures" are the reply's `draft_failures` and the turn record's `failures` (C41-3,
  C43-1). "That try's codes first, then its own, without repeats": the REWRITE's `problems`, then
  the codes the turn's own end has (a passing talk text or finding has none; a finding that falls
  back has the codes of its last try; the fixed rendering after a decline has
  DECLINED_AFTER_RESULTS, after the step limit LOOP_LIMIT), each code once.
- C50-2. T3's `first_failures` (the codes of a finish's first try) are not C50's: not tested here.
- C50-3. Point 3, "as T10 tidies a finish text": the text sent is the tidied one (stars, the
  backtick and pictures gone, white space one plain space), it is checked tidied (so a text whose
  only faults are those passes, no REWRITE), and it is saved tidied (turn.json's reply, the stored
  turn's reply_text); the step log keeps the model's own arguments exactly (T10).
"""
import json
import sys
from pathlib import Path

import pytest

import p1support as p1
from p1support import THREAD_1, Step, decline, finish
from s3support import A_ID, C64_TALK_LINE, count, county_fallback_line, turn_json
from test_s3_c41 import (CAN_ASK, DECLINE_CODES, DECLINED, OTHER, PASSING, ask_with,
                         decline_rest, decline_with, env_of, failures_of, labels_of)
from test_s3_c43 import FAULTS, SHAPE_TEXT, T3_FAILING, rewrite_of
from test_s3_round5 import Y25, line1, phrase, spec

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import HELLO_TEXT, premise_talk, tidied  # noqa: E402

COUNTED = "I counted {r1.count}."
JUDGED = "I counted {r1.count}. That is a lot."   # a finding that fails JUDGE (T2's example)
# Changed by briefs/S3-R21-A-tests.md (C57 point 6 of docs/S3A-DESIGN.md; was "I'd rather not say
# something I can't back up. Ask me for a count and I'll show you the numbers.").
FALLBACK_LINE = ("I can't answer that without running a count. Tell me what to count and for which "
                 "period, and I'll show you the numbers.")  # config/talk_rules.json's, by hand
SHAPE_DO = "Say it again in other words, in one or two short sentences."   # point 2


def test_premise_the_texts():
    labels = labels_of(1)
    premise_talk(HELLO_TEXT, None, labels)
    premise_talk(T3_FAILING, "NUMBER", labels)
    premise_talk(FAULTS["CLAIM"][0], "CLAIM", labels)
    premise_talk(FAULTS["NUMBER"][0], "NUMBER", labels)
    premise_talk(SHAPE_TEXT, "SHAPE", labels)


def premise_fallback_line():
    rules = json.loads((TESTS.parent / "config" / "talk_rules.json").read_text(encoding="utf-8"))
    assert rules["fallback_line"] == FALLBACK_LINE


def first_try(tool, fault):
    text = FAULTS[fault][0]
    return decline_with("UNSUPPORTED_METRIC", text) if tool == "decline" else \
        ask_with("other", text)


# ==== point 1: the try's codes, however the turn ends ============================================

@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_a_failing_try_then_a_talk_text_talked_failures_the_trys_codes(tmp_path, monkeypatch,
                                                                       tool):
    """The review's rewrite_then_talk."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(first_try(tool, "NUMBER")),
                    Step(finish("talk", HELLO_TEXT)))
    rewrite_of(env, 0)
    assert (reply.status, reply.reply_kind, reply.reply_style, reply.text) == \
        ("TALKED", "talk", "agent", HELLO_TEXT), (reply.status, reply.text)
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


@pytest.mark.parametrize("code", DECLINE_CODES)
def test_a_failing_decline_then_a_count_and_a_finding_answered_failures_the_trys_codes(
        tmp_path, monkeypatch, code):
    """The review's rewrite_then_count."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, FAULTS["CLAIM"][0])),
                    Step(count(A_ID, Y25)), Step(finish("finding", COUNTED)))
    rewrite_of(env, 0)
    assert (reply.status, reply.reason_code, reply.reply_style) == ("ANSWERED", None, "agent"), \
        (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert failures_of(env, reply) == (["CLAIM"], ["CLAIM"])


def test_a_failing_ask_user_then_a_count_and_a_finding(tmp_path, monkeypatch):
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(first_try("ask_user", "LABEL")),
                    Step(count(A_ID, Y25)), Step(finish("finding", COUNTED)))
    rewrite_of(env, 0)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert failures_of(env, reply) == (["LABEL"], ["LABEL"])


def test_then_a_finding_that_falls_back_its_codes_after_the_trys(tmp_path, monkeypatch):
    """The fixed rendering of a finding that fails twice (T3): the try's codes, then JUDGE."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(first_try("decline", "NUMBER")),
                    Step(count(A_ID, Y25)), Step(finish("finding", JUDGED)),
                    Step(finish("finding", JUDGED)))
    rewrite_of(env, 0)
    t3 = rewrite_of(env, 2)
    assert t3["problems"] == ["JUDGE"], t3
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), \
        (reply.status, reply.reply_style, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert failures_of(env, reply) == (["NUMBER", "JUDGE"], ["NUMBER", "JUDGE"])


def test_then_a_decline_after_a_count_the_fixed_rendering(tmp_path, monkeypatch):
    """The fixed rendering of a decline after a count (C41-5): the try's codes, then
    DECLINED_AFTER_RESULTS."""
    code = "UNSUPPORTED_METRIC"
    env = env_of(tmp_path, monkeypatch, 1)
    twin = env.ask(DECLINED[code], Step(count(A_ID, Y25)), Step(decline(code)),
                   thread_key=p1.THREAD_2)
    assert twin.draft_failures == ["DECLINED_AFTER_RESULTS"], "premise: today's own code"
    reply = env.ask(DECLINED[code], Step(decline_with(code, FAULTS["CHARS"][0])),
                    Step(count(A_ID, Y25)), Step(decline(code)))
    rewrite_of(env, 0)
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert reply.text == twin.text, reply.text
    assert failures_of(env, reply) == (["CHARS", "DECLINED_AFTER_RESULTS"],
                                       ["CHARS", "DECLINED_AFTER_RESULTS"])


def test_then_the_step_limit_with_a_count(tmp_path, monkeypatch):
    """A limit: REWRITE in step 1, a count in step 2, the last (MOCO_MAX_STEPS 2): the fixed
    rendering, the try's codes then LOOP_LIMIT."""
    env = env_of(tmp_path, monkeypatch, 1, MOCO_MAX_STEPS=2)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(first_try("decline", "NUMBER")),
                    Step(count(A_ID, Y25)), Step(finish("finding", COUNTED)))
    rewrite_of(env, 0)
    assert len(env.model.calls) == 2
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert failures_of(env, reply) == (["NUMBER", "LOOP_LIMIT"], ["NUMBER", "LOOP_LIMIT"])


def test_then_a_talk_text_that_falls_back_its_codes_after_the_trys(tmp_path, monkeypatch):
    """A talk text failing twice ends with the fallback line (T3): the try's codes (CLAIM), then
    the talk text's own (NUMBER). Changed by briefs/S3-R28-A-tests.md (C64 point 1): the talk text
    that ended the turn failed NUMBER, so the line is C64's (s3support.C64_TALK_LINE); it was C61's
    county line (county_fallback_line(1))."""
    premise_fallback_line()
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(first_try("decline", "CLAIM")),
                    Step(finish("talk", T3_FAILING)), Step(finish("talk", T3_FAILING)))
    rewrite_of(env, 0)
    rewrite_of(env, 1)
    # Changed by briefs/S3-R23-A-tests.md (C61 point 9: the county line; it was FALLBACK_LINE,
    # config/talk_rules.json's). Changed by briefs/S3-R28-A-tests.md (C64 point 1): C64's line.
    assert (reply.status, reply.reply_style, reply.text) == ("TALKED", "fallback",
                                                             C64_TALK_LINE), reply.text
    assert failures_of(env, reply) == (["CLAIM", "NUMBER"], ["CLAIM", "NUMBER"])


def test_without_repeats(tmp_path, monkeypatch):
    """The try fails NUMBER and the talk text that falls back fails NUMBER too: NUMBER once."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(first_try("ask_user", "NUMBER")),
                    Step(finish("talk", T3_FAILING)), Step(finish("talk", T3_FAILING)))
    assert reply.reply_style == "fallback", reply.text
    assert failures_of(env, reply) == (["NUMBER"], ["NUMBER"])


def test_no_failed_try_no_codes(tmp_path, monkeypatch):
    """No own words failed: a talk text ends the turn with none, as today."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(finish("talk", HELLO_TEXT)))
    assert (reply.status, reply.reply_style) == ("TALKED", "agent")
    assert failures_of(env, reply) == ([], [])


# ==== point 2: SHAPE alone, `do` word for word ===================================================

@pytest.mark.parametrize("n", [1, 3], ids=["one source", "three sources"])
@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_shape_alone_gets_the_do_of_point_2_word_for_word(tmp_path, monkeypatch, tool, n):
    env = env_of(tmp_path, monkeypatch, n)
    shaped = decline_with("UNSUPPORTED_METRIC", SHAPE_TEXT) if tool == "decline" else \
        ask_with("other", SHAPE_TEXT)
    env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(shaped), Step(first_try(tool, "NUMBER")))
    answer = rewrite_of(env, 0)
    assert answer == {"error": "REWRITE", "problems": ["SHAPE"], "found": [], "do": SHAPE_DO}, \
        answer


def test_shape_alone_over_700_characters(tmp_path, monkeypatch):
    """SHAPE from the length alone (T12: at most 700 characters), nothing found."""
    text = " ".join(["I can only count the records I have for you."] * 16)
    assert len(text) > 700 and len(text.split(". ")) <= 16
    env = env_of(tmp_path, monkeypatch, 1)
    env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(ask_with("other", text)),
            Step(ask_with("other", PASSING["one sentence"])))
    answer = rewrite_of(env, 0)
    assert answer["problems"] == ["SHAPE"] and answer["found"] == [], answer
    assert answer["do"] == SHAPE_DO, answer["do"]


# ==== point 3: the text is tidied before it is checked, sent and saved ===========================

MARKED = ("That is *outside* what my `records` can tell me. \U0001F642\nIs there something about "
          "the **records** themselves I can count for you?")
TIDIED = PASSING["two sentences"]
MARKED_ONE = "A *forecast* is something I can't make, since I count\nrecords that already exist. ✨"
TIDIED_ONE = PASSING["one sentence"]


def test_premise_the_marked_texts_tidy_to_c41s_passing_texts():
    assert tidied(MARKED) == TIDIED and tidied(MARKED_ONE) == TIDIED_ONE
    for raw in (MARKED, MARKED_ONE):
        assert "*" in raw and "\n" in raw and any(ord(ch) > 0x2000 for ch in raw)
    assert "`" in MARKED


@pytest.mark.parametrize("which", ["two sentences, a backtick", "one sentence"])
@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_a_text_with_stars_backticks_a_picture_and_a_line_break_is_sent_without_them(
        tmp_path, monkeypatch, tool, which):
    raw, tidy = (MARKED, TIDIED) if which.startswith("two") else (MARKED_ONE, TIDIED_ONE)
    code = "UNSUPPORTED_METRIC"
    env = env_of(tmp_path, monkeypatch, 1)
    call = decline_with(code, raw) if tool == "decline" else ask_with("other", raw)
    reply = env.ask(DECLINED[code], Step(call), Step(decline_with(code)))
    assert len(env.model.calls) == 1, f"the tidied text was not what was checked: {env.answers()}"
    sent = f"{tidy} {decline_rest(code, 1)}" if tool == "decline" else tidy
    assert reply.text == sent, reply.text
    assert (reply.reply_style, reply.draft_failures) == ("agent", [])
    record = turn_json(reply, env.runs_dir)
    assert record["reply"] == sent, "saved: the tidied text"
    stored = env.store.recent_turns(THREAD_1, 1)[-1]
    assert stored["reply_text"] in (tidy, sent), stored["reply_text"]
    logged = record["steps"][0]["tool_calls"][0]["arguments"]
    assert json.loads(logged)["text"] == raw, "T10: the step log keeps the model's own words"
    for ch in ("*", "`", "\n", "\U0001F642", "✨"):
        assert ch not in reply.text


def test_a_tidied_text_that_still_fails_gets_rewrite_on_the_tidied_words(tmp_path, monkeypatch):
    """Tidying takes away only what T10 names: a number left in the text still fails NUMBER."""
    raw = "I *can't* count that `twice` over. \U0001F642"
    env = env_of(tmp_path, monkeypatch, 1)
    env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(decline_with("UNSUPPORTED_METRIC", raw)),
            Step(decline_with("UNSUPPORTED_METRIC", TIDIED_ONE)))
    answer = rewrite_of(env, 0)
    assert answer["problems"] == ["NUMBER"] and answer["found"] == ["twice"], answer


def test_talk_off_the_text_is_not_used(tmp_path, monkeypatch):
    """T0 and C41 point 4: with MOCO_TALK off the row is today's, whatever the text holds."""
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK="off")
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"],
                    Step(ask_with("other", MARKED)))
    assert reply.text == f"{OTHER} {CAN_ASK[1]}", reply.text
    assert (reply.reply_style, reply.draft_failures) == ("fixed", [])
