"""C64 of docs/S3A-DESIGN.md (D-081): four weak spots the harder threads showed
(kit-log/raw/THREADS-2026-11-17.txt, "THE REST OF THE LIVE CHECK, READ" and "FOUR HARDER THREADS").
Brief: briefs/S3-R28-A-tests.md. Tests only; red until the planning chat builds C64, except those
named "Passes today" in their docstrings (they pin what stays; also in
kit-log/raw/S3-R28-A-notes.txt).

All data is SYNTHETIC: the tests/s3 fixtures (and round 3's visits_like where three sources are
needed). No real figure is quoted. Every turn goes through agent.handle_question with the model
stand-in. C64's fixed texts are written out by hand in s3support.py (C64_TALK_LINE,
C64_HINT_SENTENCE, C64_PROMPT_SENTENCES, C64_LINE_A to C64_LINE_C, C64_NINTH_FACT).
replies.ABOUT_AGENT points at a fixture copy (s3support.about_agent_fixture), except in point 4's
tests of config/about_agent.md itself, which point it at that file.

Readings (also in the notes):
- R28-1 (point 1). "The failure codes of the text that ended it": the codes of the talk text whose
  check ended the turn (with T3 and C61 point 8 the last talk text checked; with no step left the
  only one). An earlier try's codes are not that text's, nor are those of a failed try of his own
  words (decline, ask_user) that C50 point 1 puts on record beside them.
- R28-2 (point 1). "In place of `I can't put that in words I can back up.` and what follows it":
  the reply is the new line alone, with no can-ask sentence, whatever the number of sources.
  "Style fallback, the failures on record, as today": TALKED, kind talk, style fallback, the codes
  in draft_failures and turn.json, and the memory's `reply_text` and `sent` the line sent.
- R28-3 (point 1). The NUMBER hint "gains one sentence at its end": today's two sentences, one
  space, the new one. Every other hint stays.
- R28-4 (point 3a). Line a for every count answered NOT_ALLOWED with C21's `why` (it begins `with
  this count, the figures of this message would give`), with C61 point 10's added sentence or
  without it; never for C8.4's single age (C35's `why`), which C28 widens or not.
- R28-5 (point 3b). Line b only for count's TOO_MANY of the eight counts (`why` `at most 8 counts in
  one message`); count's other TOO_MANY (three breakdowns) gets no line. "With the program's own
  number": agent.MAX_COUNTS, today 8; the line is pinned with 8.
- R28-6 (point 3c). Line c only for compare's MIXED_SOURCES; BAD_COMPARE and BAD_SHARE get none.
- R28-7 (point 3, "directly after the kept line and the widened line (C10's order)"): the lines
  follow line 1, the table (or the full-table line), the kept line and C28's widened line, and come
  before every line C10 puts after those (left-out, hidden, sensitive, source). Expected texts are
  written by hand (assert_reply), or are today's reply of the same turn without the refusals (a
  twin turn in another thread of the same env, with the same earlier messages: a refused count
  leaves nothing behind) with the lines put in at that place (`with_lines`).
- R28-8 (point 3, "in every style"): agent (a text that passes), fallback (a text that names a
  slot it was not given, so SLOT; and end_fixed's fixed rendering), fixed (MOCO_REPLY_STYLE=fixed).
- R28-9 (point 4). "Becomes version 2": the file says "version 2" and no longer "version 1"; its
  facts are today's eight, word for word and in order, then the ninth.
- R28-10 (point 2). "In that prompt only": config/agent_prompt_s3_talk.md; not
  config/agent_prompt_s3.md and not the SYNTHETIC prompts. With talk off a county turn is not sent
  the sentences.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from p1support import (THREAD_1, THREAD_2, Env, Step, decline, describe, finish, mod,
                       thread_block)
from p1support import count as synthetic_count
from s3support import (A_ID, C_ID, C61_ABOUT_FACTS, C62_MAKER_HINT, C62_PROMPT_SENTENCES,
                       C62_REFUSAL, C64_HINT_SENTENCE, C64_LINE_A, C64_LINE_B, C64_LINE_C,
                       C64_LINES, C64_NINTH_FACT, C64_PROMPT_SENTENCES, C64_TALK_LINE,
                       FULL_TABLE_LINE, KEPT_ANY, Q_COUNT, REPO, CountyEnv, about_agent_fixture,
                       age_left_out_line, assert_reply, compare, count, county_fallback_line,
                       dates, fallback_lines, is_, months, share, source_re, turn_json, year,
                       years)
from test_s3_c41 import CAN_ASK, DECLINED, ask_with, decline_row, decline_with, env_of
from test_s3_c61b import C61_PROMPT_LINE, PROMPTS, SYNTHETIC_PROMPTS
from test_s3_c61d import P05_FIRST, P05_SECOND, WHY_THREAD, assert_refused, p05
from test_s3_round5 import (A, C28_LINE, NOT_ALLOWED_ROW, U17, U18, WHY, Y25, age,
                            assert_not_allowed, assert_result, call_of, counts_text, phrase, spec)

TESTS = Path(__file__).resolve().parents[1]
for folder in ("t", "s3s2"):
    if str(TESTS / folder) not in sys.path:
        sys.path.insert(0, str(TESTS / folder))

from tsupport import HINTS, county_labels, talk_env, talk_faults, talk_rules  # noqa: E402

TALK = ["off", "on"]
STYLES = ["agent", "fallback", "fixed"]
TWO = ("arrests_like", "coded_like")
PASSING = "Happy to help. Ask me for a count whenever you like."
LABEL_TEXT = "Most of them were group Gamma."  # fails LABEL (a label of arrests_like)
WRONG = "my professor says your number is wrong"  # thread P17's kind of message (C64 point 1)
OLD_NUMBER_HINT = "Write no number, month or year yourself. A figure may only come from a slot."
NEW_NUMBER_HINT = f"{OLD_NUMBER_HINT} {C64_HINT_SENTENCE}"  # R28-3


@pytest.fixture(autouse=True)
def _about_agent(tmp_path, monkeypatch):
    about_agent_fixture(tmp_path, monkeypatch)


def memory(env, thread_key=THREAD_1):
    return env.store.recent_turns(thread_key, 100)


def norm(text):
    return " ".join(str(text).split())


# ==== point 1: a figure in plain talk ============================================================

# id: (a talk text that fails NUMBER, the other codes it must fail with)
NUMBER_TEXTS = {
    "number alone": ("The county may say nine thousand, but I stand by my count.", ()),
    "a figure in digits": ("The county may say 9,112, but I stand by my count.", ()),
    "number and claim": ("In fact the county says nine thousand.", ("CLAIM",)),
    "number and label": ("Nine of them were group Gamma.", ("LABEL",)),
    "number and maker": ("Claude counted nine of them.", ("MAKER",)),
}
NUMBER_ALONE = NUMBER_TEXTS["number alone"][0]
# id: (a talk text that fails without NUMBER, its one code)
OTHER_TEXTS = {
    "label alone": (LABEL_TEXT, "LABEL"),
    "maker alone": ("Claude made me, and I stand by my count.", "MAKER"),
    "claim alone": ("That is due to the season, I think.", "CLAIM"),
}


def test_premise_the_talk_texts():
    labels = county_labels("arrests_like")
    for text, others in NUMBER_TEXTS.values():
        faults = talk_faults(text, labels)
        assert "NUMBER" in faults and set(others) - {"MAKER"} <= faults, (text, faults)
        assert ("MAKER" in others) == bool(re.search(r"\bclaude\b", text, re.IGNORECASE)), text
    for text, code in OTHER_TEXTS.values():
        assert talk_faults(text, labels) == ({code} - {"MAKER"}), (text, talk_faults(text, labels))
        assert (code == "MAKER") == bool(re.search(r"\bclaude\b", text, re.IGNORECASE)), text
    assert not re.search(r"\d", C64_TALK_LINE), "the new line holds no digit"


def talk_three_times(env, text, question=WRONG):
    """C61 point 8: a county talk text that fails gets two REWRITEs; the third ends the turn."""
    return env.ask(question, Step(finish("talk", text)), Step(finish("talk", text)),
                   Step(finish("talk", text)), Step(finish("talk", PASSING)))


def assert_talk_fallback(env, reply, line, codes, thread_key=THREAD_1):
    """R28-2: TALKED, kind talk, style fallback, `line` sent; `codes` on record (the reply,
    turn.json); the memory's reply_text and sent are the line."""
    assert (reply.status, reply.reply_kind, reply.reply_style) == ("TALKED", "talk", "fallback"), \
        (reply.status, reply.reply_kind, reply.reply_style, reply.draft_failures, reply.text)
    assert reply.text == line, reply.text
    assert set(codes) <= set(reply.draft_failures), reply.draft_failures
    record = turn_json(reply, env.runs_dir)
    assert set(codes) <= set(record.get("failures") or []), record.get("failures")
    assert (record["reply"], record["reply_style"]) == (line, "fallback"), record["reply"]
    stored = memory(env, thread_key)[-1]
    assert (stored.get("sent"), stored.get("reply_text"), stored.get("reply_style")) == \
        (line, line, "fallback"), stored


@pytest.mark.parametrize("case", list(NUMBER_TEXTS))
def test_p1_a_talk_text_that_fails_number_at_each_try_ends_on_the_new_line(tmp_path, monkeypatch,
                                                                           case):
    """C64's test: a talk text that fails NUMBER at each try (alone, and with another code too)
    ends on the new line; no digit is sent."""
    text, others = NUMBER_TEXTS[case]
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = talk_three_times(env, text)
    assert len(env.model.calls) == 3, "premise: two REWRITEs, then the end (C61 point 8)"
    assert_talk_fallback(env, reply, C64_TALK_LINE, ("NUMBER", *others))
    assert not re.search(r"\d", reply.text), reply.text


@pytest.mark.parametrize("n", [2, 3], ids=["two sources", "three sources"])
def test_p1_the_new_line_alone_whatever_the_sources(tmp_path, monkeypatch, n):
    """R28-2: the new line replaces C61 point 9's whole line, its can-ask sentence too."""
    env = env_of(tmp_path, monkeypatch, n)
    reply = talk_three_times(env, NUMBER_ALONE)
    assert_talk_fallback(env, reply, C64_TALK_LINE, ("NUMBER",))
    assert CAN_ASK[n] not in reply.text


@pytest.mark.parametrize("case", list(OTHER_TEXTS))
def test_p1_a_text_that_fails_without_number_ends_on_todays_line(tmp_path, monkeypatch, case):
    """C64's test: a text that fails only LABEL or only MAKER (and only CLAIM) ends on today's line
    (C61 point 9). Passes today; must still pass."""
    text, code = OTHER_TEXTS[case]
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = talk_three_times(env, text)
    assert_talk_fallback(env, reply, county_fallback_line(1), (code,))
    assert "NUMBER" not in reply.draft_failures, reply.draft_failures


def test_p1_the_hint():
    """C64's test, the hint (R28-3): NUMBER's hint is today's with the new sentence at its end;
    every other hint as today (tsupport.HINTS, changed in this round, and C62's MAKER)."""
    hints = talk_rules()["rewrite_hints"]
    assert hints["NUMBER"] == NEW_NUMBER_HINT, hints["NUMBER"]
    assert HINTS["NUMBER"] == NEW_NUMBER_HINT, "premise: tsupport's hint is C64's"
    assert hints == {**HINTS, "MAKER": C62_MAKER_HINT}


@pytest.mark.parametrize("mode", ["county", "synthetic"])
def test_p1_the_rewrite_of_a_text_that_fails_number_gives_the_new_hint(tmp_path, monkeypatch,
                                                                      mode):
    """Point 1: "the hint is one line of one file, so SYNTHETIC mode's REWRITE shows the sentence
    too": T3's `do` for a talk text failing NUMBER is the new hint in both modes."""
    text = "There were twelve of them."
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on") if mode == "county" \
        else talk_env(tmp_path)
    reply = env.ask("hello", Step(finish("talk", text)), Step(finish("talk", PASSING)))
    answer = env.model.answer(0)
    assert (answer.get("error"), answer.get("problems")) == ("REWRITE", ["NUMBER"]), answer
    assert answer.get("do") == NEW_NUMBER_HINT, answer.get("do")
    assert (reply.reply_style, reply.text) == ("agent", PASSING), reply.text


def test_p1_synthetic_modes_fallback_line_is_untouched(tmp_path):
    """C64's test: "SYNTHETIC mode's fallback line untouched": a SYNTHETIC talk text that fails
    NUMBER twice ends on talk_rules.json's line, never the new one. Passes today; must still
    pass."""
    env = talk_env(tmp_path)
    text = "There were twelve of them."
    reply = env.ask("hello", Step(finish("talk", text)), Step(finish("talk", text)))
    assert (reply.status, reply.reply_style) == ("TALKED", "fallback"), reply.text
    assert "NUMBER" in reply.draft_failures, reply.draft_failures
    assert reply.text in fallback_lines(county=False) and reply.text != C64_TALK_LINE, reply.text


# ---- point 1, own tests -------------------------------------------------------------------------

@pytest.mark.parametrize("order", ["number, number, then label", "label, label, then number"])
def test_own_1_the_codes_of_the_text_that_ended_the_turn(tmp_path, monkeypatch, order):
    """Own 1 (R28-1): three talk texts; the line is chosen by the third, the one that ended the
    turn: NUMBER in the first two only gives today's line; NUMBER in the third only, the new one."""
    texts = [NUMBER_ALONE, NUMBER_ALONE, LABEL_TEXT] if order.endswith("label") else \
        [LABEL_TEXT, LABEL_TEXT, NUMBER_ALONE]
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = env.ask(WRONG, *[Step(finish("talk", t)) for t in texts], Step(finish("talk", PASSING)))
    assert len(env.model.calls) == 3, "premise: the third text ended the turn"
    if order.endswith("label"):
        assert_talk_fallback(env, reply, county_fallback_line(1), ("LABEL",))
        assert reply.draft_failures == ["LABEL"], reply.draft_failures
    else:
        assert_talk_fallback(env, reply, C64_TALK_LINE, ("NUMBER",))


OWN_THEN_TALK = {  # id: (his own words that fail, the talk text, the line, the codes on record)
    "own words NUMBER, then a talk text LABEL": ("I can't count that twice over.", LABEL_TEXT,
                                                 "today", ["NUMBER", "LABEL"]),
    "own words CLAIM, then a talk text NUMBER": (
        "That would be due to things my records do not hold.", NUMBER_ALONE, "new",
        ["CLAIM", "NUMBER"]),
}


@pytest.mark.parametrize("case", list(OWN_THEN_TALK))
def test_own_2_a_failed_try_of_his_own_words_is_not_the_text_that_ended_it(tmp_path, monkeypatch,
                                                                           case):
    """Own 2 (R28-1 with C50 point 1): a decline's own words fail (REWRITE), then a talk text fails
    three times. Both tries' codes are on record (C50), but the line follows the talk text's."""
    own, text, line, codes = OWN_THEN_TALK[case]
    code = "UNSUPPORTED_METRIC"
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = env.ask(DECLINED[code], Step(decline_with(code, own)), Step(finish("talk", text)))
    assert env.model.answer(0).get("error") == "REWRITE", "premise: the own words failed"
    assert reply.draft_failures == codes, reply.draft_failures
    assert_talk_fallback(env, reply, C64_TALK_LINE if line == "new" else county_fallback_line(1),
                         codes)


@pytest.mark.parametrize("how", ["plain text read as talk", "no step left for a rewrite"])
def test_own_3_every_way_a_talk_text_ends_on_the_fallback(tmp_path, monkeypatch, how):
    """Own 3: a plain text with no tool call is read as talk (T1, T13) and gets the new line after
    its tries; with MOCO_MAX_STEPS=1 the first and only text ends the turn on the new line."""
    if how.startswith("plain"):
        env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
        reply = env.ask(WRONG, Step(text=NUMBER_ALONE))
        assert len(env.model.calls) == 3, "premise: two REWRITEs as notes (T13), then the end"
    else:
        env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", MOCO_MAX_STEPS="1")
        reply = env.ask(WRONG, Step(finish("talk", NUMBER_ALONE)))
        assert len(env.model.calls) == 1, "premise: no REWRITE"
    assert_talk_fallback(env, reply, C64_TALK_LINE, ("NUMBER",))


def test_own_4_a_declines_own_words_that_fail_number_keep_todays_row(tmp_path, monkeypatch):
    """Own 4: point 1 is about a talk text that ends on C61 point 9's fallback. Own words of a
    decline that fail NUMBER twice end on today's row (C41 point 3, C43), not on the new line.
    Passes today; must still pass."""
    code = "UNSUPPORTED_METRIC"
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = env.ask(DECLINED[code], Step(decline_with(code, "I can't count that twice over.")))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), reply.text
    assert reply.text == decline_row(code, 1), reply.text
    assert "NUMBER" in reply.draft_failures, reply.draft_failures


# ==== point 2: the start of a long thread ========================================================

C62_LINE = f"{C61_PROMPT_LINE} {C62_PROMPT_SENTENCES}"
C64_LINE = f"{C62_LINE} {C64_PROMPT_SENTENCES}"
C64_SENTENCES = (
    "When THREAD SO FAR says that earlier messages are not shown, you do not know how the "
    "conversation began.",
    "Never call a message, a question or a count the first, also when you count it again: call it "
    "the earliest one still shown to you.",
    "When asked for the first one, or for everything said or counted so far, say in your text that "
    "the start of the conversation is no longer shown to you, and go by what is shown.",
)


def prompt_lines(path):
    return path.read_bytes().decode("utf-8").split("\n")


def test_premise_the_three_sentences():
    assert " ".join(C64_SENTENCES) == C64_PROMPT_SENTENCES


def test_p2_the_three_sentences_word_for_word_once_in_place():
    """C64's test: in config/agent_prompt_s3_talk.md the line directly after rule 11 is C61's line,
    C62's two sentences and C64's three, one space between, and nothing else; each sentence is in
    the file once."""
    lines = prompt_lines(PROMPTS["agent_prompt_s3_talk"])
    eleven = [i for i, line in enumerate(lines) if line.startswith("11. ")]
    assert len(eleven) == 1, "premise: one rule 11"
    assert lines[eleven[0] + 1] == C64_LINE, lines[eleven[0] + 1][-500:]
    text = "\n".join(lines)
    for sentence in C64_SENTENCES:
        assert text.count(sentence) == 1, sentence


def test_p2_in_that_prompt_only():
    """C64's test, "in that prompt only" (R28-10). Passes today; must still pass."""
    marks = (*C64_SENTENCES, "how the conversation began", "the earliest one still shown",
             "no longer shown to you")
    for name, path in {"agent_prompt_s3": PROMPTS["agent_prompt_s3"], **SYNTHETIC_PROMPTS}.items():
        text = path.read_bytes().decode("utf-8")
        for mark in marks:
            assert mark not in text, (name, mark)


@pytest.mark.parametrize("talk", TALK)
def test_p2_a_county_turn_is_sent_them_with_talk_on_only(tmp_path, monkeypatch, talk):
    """Point 2 with R28-10: talk on, the system message holds the line once, after rule 11; talk
    off, none of the three sentences."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    env.ask("hello", Step(finish("talk", PASSING)) if talk == "on"
            else Step(decline("UNRECOGNIZED_QUESTION")))
    system = env.model.calls[0]["messages"][0]["content"]
    if talk == "on":
        lines = system.split("\n")
        assert lines.count(C64_LINE) == 1, [line[-300:] for line in lines
                                            if "THREAD SO FAR also" in line]
        assert lines[lines.index(C64_LINE) - 1].startswith("11. ")
    else:
        for sentence in C64_SENTENCES:
            assert sentence not in system, sentence


def _hash_modules():
    import test_s2_r13
    import test_s3_c44
    import test_s3_c46
    return {"test_s3_c44": (test_s3_c44, "text_of"), "test_s3_c46": (test_s3_c46, "text_of"),
            "test_s2_r13": (test_s2_r13, "prompt")}


@pytest.mark.parametrize("module_name", ["test_s3_c44", "test_s3_c46", "test_s2_r13"])
def test_p2_the_prompt_hash_tests_take_them_out(monkeypatch, module_name):
    """C64's test "the prompt hash tests take them out": each prompt hash test, given the county
    talk prompt with the line after rule 11 as C64 makes it, finds today's sha256; given C64's
    sentences on a line of their own before rule 11, or twice at the end of the line, it does not.
    The prompt is made in memory from the file as it is; no file is written. Passes today (with
    the three hash tests as this round changes them); must still pass after the build. Not changed
    by briefs/S3-R30-A-tests.md: with C66 built, the file's line after rule 10 holds C66 point 2's
    sentences, and the three modules' restored() now take them out (s3support.without_c66), so
    these three cases turn back with them."""
    module, reader = _hash_modules()[module_name]
    real = getattr(module, reader)
    lines = prompt_lines(PROMPTS["agent_prompt_s3_talk"])
    (eleven,) = [i for i, line in enumerate(lines) if line.startswith("11. ")]
    assert lines[eleven + 1].startswith(C61_PROMPT_LINE), "premise: C61's line after rule 11"

    def made(line, before_11=None):
        out = list(lines)
        out[eleven + 1] = line
        if before_11 is not None:
            out.insert(eleven, before_11)
        return "\n".join(out)
    cases = ((made(C64_LINE), True), (made(C62_LINE, C64_PROMPT_SENTENCES), False),
             (made(f"{C64_LINE} {C64_PROMPT_SENTENCES}"), False))
    for text, same in cases:
        def fake(arg, text=text):
            name = arg if isinstance(arg, str) else Path(arg).stem
            return text if name == "agent_prompt_s3_talk" else real(arg)
        monkeypatch.setattr(module, reader, fake)
        digest = hashlib.sha256(module.restored("agent_prompt_s3_talk").encode("utf-8")).hexdigest()
        assert (digest == module.TODAY_SHA256["agent_prompt_s3_talk"]) is same, (module_name, same)


# ==== point 3: a count that was not made is said =================================================

TABLE_LINE = re.compile(r"[^()\n]+: (?:[0-9][0-9,]*|fewer than [0-9]+)")


def with_lines(text, new):
    """R28-7: `text` with the lines `new` put in directly after line 1, the table (or the full-table
    line), the kept line and the widened line."""
    lines = text.split("\n")
    i = 1
    while i < len(lines) and (TABLE_LINE.fullmatch(lines[i]) or KEPT_ANY.fullmatch(lines[i])
                              or lines[i] in (FULL_TABLE_LINE, C28_LINE)):
        i += 1
    return "\n".join(lines[:i] + list(new) + lines[i:])


def env3(tmp_path, monkeypatch, style="agent", talk="off", names=("arrests_like",)):
    values = {"MOCO_TALK": talk}
    if style == "fixed":
        values["MOCO_REPLY_STYLE"] = "fixed"
    return CountyEnv(tmp_path, monkeypatch, names=names, **values)


def finish_text(style, n=1):
    """R28-8: a finding text that passes, or (fallback) one that also names a slot not given."""
    return counts_text(n) + (" {r9.count}." if style == "fallback" else "")


def assert_answered(reply, style):
    assert (reply.status, reply.reply_style) == ("ANSWERED", style), \
        (reply.status, reply.reason_code, reply.reply_style, reply.draft_failures, reply.text)


def assert_twin(reply, twin, want):
    """R28-7: the reply is its twin's text (today's reply of the same turn without the refusals)
    with the lines `want` put in at their place, each once."""
    assert twin.status == "ANSWERED" and not any(line in twin.text for line in C64_LINES), \
        f"premise: the twin is today's answer: {twin.text!r}"
    assert reply.text == with_lines(twin.text, want), \
        f"--- got ---\n{reply.text}\n--- want ---\n{with_lines(twin.text, want)}"
    for line in C64_LINES:
        assert reply.text.count(line) == (1 if line in want else 0), line


P16_FIRST = "how many people under 18 were arrested in 2025?"
P16_SECOND = "what share of them were aged 10 to 16?"


def p16(env, text, thread_key=THREAD_1, refuse=True):
    """Thread P16's "under 18, then the share aged 10 to 16": the second message counts under 18
    and 10 to 16 (refused by C21: the 17-year-olds), asks for the share (BAD_SHARE: the part was
    not made) and finishes. `refuse=False`: the twin, with the under-18 count alone."""
    first = env.ask(P16_FIRST, Step(call_of(spec(Y25, [U18]))),
                    Step(finish("finding", "I counted {r1.count}.")), thread_key=thread_key)
    assert first.status == "ANSWERED", (first.status, first.text)
    calls = [call_of(spec(Y25, [U18]))] + ([call_of(spec(Y25, [age(10, 16)]))] if refuse else [])
    steps = [Step(*calls)] + ([Step(share("r2", "r1"))] if refuse else []) + \
        [Step(finish("finding", text))]
    reply = env.ask(P16_SECOND, *steps, thread_key=thread_key)
    if refuse:
        assert_result(env.model.answer(0, 0), "r1")
        assert_not_allowed(env.model.answer(0, 1))
        assert env.model.answer(1).get("error") == "BAD_SHARE", env.model.answer(1)
    return reply


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("style", STYLES)
def test_p3_a_thread_p16_under_18_then_the_share_aged_10_to_16(tmp_path, monkeypatch, style, talk):
    """C64's test: P16 (line a), in every style (R28-8), written out by hand: line 1, line a, the
    left-out line, the later source line."""
    env = env3(tmp_path, monkeypatch, style, talk)
    reply = p16(env, finish_text(style))
    assert_answered(reply, style)
    assert_reply(reply.text, f"I counted {phrase(spec(Y25, [U18]))}.",
                 left_out=[C64_LINE_A, age_left_out_line(5)], source=source_re(A, first=False))


NINE = [(year(2024),), (year(2025),), (year(2026),), (years(2024, 2025),), (months(2025, 1, 6),),
        (months(2025, 7, 12),), (dates("2025-03-01", "2025-08-31"),),
        (year(2025), [is_("district", "district 1")]),
        (year(2025), [is_("district", "district 2")])]  # all ages, nine kinds (test_s3_count_spec)


def nine_counts(env, text, thread_key=THREAD_1, ninth=True):
    calls = [count(A_ID, *s) for s in NINE[:9 if ninth else 8]]
    reply = env.ask("list every count you can give me", Step(*calls),
                    Step(finish("finding", text)), thread_key=thread_key)
    if ninth:
        for i in range(8):
            assert_result(env.model.answer(0, i), f"r{i + 1}")
        assert env.model.answer(0, 8).get("error") == "TOO_MANY", env.model.answer(0, 8)
    return reply


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("style", STYLES)
def test_p3_b_nine_counts_in_one_message(tmp_path, monkeypatch, style, talk):
    """C64's test: nine counts in one message: line b, in every style."""
    env = env3(tmp_path, monkeypatch, style, talk)
    reply = nine_counts(env, finish_text(style))
    twin = nine_counts(env, finish_text(style), thread_key=THREAD_2, ninth=False)
    assert_answered(reply, style)
    assert_twin(reply, twin, [C64_LINE_B])


def two_sources(env, text, thread_key=THREAD_1, refuse=True):
    steps = [Step(count(A_ID, Y25), count(C_ID, Y25))] + \
        ([Step(compare("r1", "r2"))] if refuse else []) + [Step(finish("finding", text))]
    reply = env.ask("compare the arrests and the intake records of 2025", *steps,
                    thread_key=thread_key)
    if refuse:
        assert env.model.answer(1).get("error") == "MIXED_SOURCES", env.model.answer(1)
    return reply


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("style", STYLES)
def test_p3_c_a_compare_of_two_sources_counts(tmp_path, monkeypatch, style, talk):
    """C64's test: a compare of two sources' counts with a count made: line c, in every style."""
    env = env3(tmp_path, monkeypatch, style, talk, names=TWO)
    reply = two_sources(env, finish_text(style, 2))
    twin = two_sources(env, finish_text(style, 2), thread_key=THREAD_2, refuse=False)
    assert_answered(reply, style)
    assert_twin(reply, twin, [C64_LINE_C])


# All ages, eight counts of arrests_like of different kinds (none of them gives one year of age).
ALL_AGES = [count(A_ID, *s) for s in NINE[:1] + NINE[2:]]
MADE_U18, REFUSED_U17 = call_of(spec(Y25, [U18])), call_of(spec(Y25, [U17]))
C_COUNT = count(C_ID, Y25)
# id: (names, the steps with the refusals, the twin's steps, the lines)
TOGETHER = {
    "a and b": (("arrests_like",),
                [Step(MADE_U18, REFUSED_U17, *ALL_AGES[:7], ALL_AGES[7])],
                [Step(MADE_U18, *ALL_AGES[:7])], [C64_LINE_A, C64_LINE_B]),
    "a and c": (TWO, [Step(MADE_U18, REFUSED_U17, C_COUNT), Step(compare("r1", "r2"))],
                [Step(MADE_U18, C_COUNT)], [C64_LINE_A, C64_LINE_C]),
    "b and c, met as b then c": (TWO, [Step(*ALL_AGES[:7], C_COUNT, ALL_AGES[7]),
                                       Step(compare("r1", "r8"))],
                                 [Step(*ALL_AGES[:7], C_COUNT)], [C64_LINE_B, C64_LINE_C]),
    "all three, met as c, b, a": (TWO, [Step(C_COUNT, MADE_U18), Step(compare("r1", "r2")),
                                        Step(*ALL_AGES[:6], ALL_AGES[6], REFUSED_U17)],
                                  [Step(C_COUNT, MADE_U18), Step(*ALL_AGES[:6])],
                                  [C64_LINE_A, C64_LINE_B, C64_LINE_C]),
}


def errors_of(env):
    """The error codes of every tool answer of the last turn, in order."""
    return [a.get("error") for a in env.answers() if a.get("error")]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(TOGETHER))
def test_p3_two_of_them_in_one_turn_in_order_each_once(tmp_path, monkeypatch, case, talk):
    """C64's test: two of them (and all three) in one turn: in the order a, b, c, whatever order the
    refusals came in, each once."""
    names, steps, twin_steps, want = TOGETHER[case]
    env = env3(tmp_path, monkeypatch, "agent", talk, names=names)
    reply = env.ask(Q_COUNT, *steps, Step(finish("finding", counts_text(1))))
    want_errors = {C64_LINE_A: "NOT_ALLOWED", C64_LINE_B: "TOO_MANY", C64_LINE_C: "MIXED_SOURCES"}
    assert sorted(errors_of(env)) == sorted(want_errors[line] for line in want), errors_of(env)
    twin = env.ask(Q_COUNT, *twin_steps, Step(finish("finding", counts_text(1))),
                   thread_key=THREAD_2)
    assert_answered(reply, "agent")
    assert_twin(reply, twin, want)


@pytest.mark.parametrize("talk", TALK)
def test_p3_a_turn_with_none_of_the_three_has_no_such_line(tmp_path, monkeypatch, talk):
    """C64's test: a turn with none of the three (two sources counted, nothing refused) has no such
    line. Passes today; must still pass."""
    env = env3(tmp_path, monkeypatch, "agent", talk, names=TWO)
    reply = two_sources(env, counts_text(2), refuse=False)
    assert_answered(reply, "agent")
    assert not any(line in reply.text for line in C64_LINES), reply.text


@pytest.mark.parametrize("case", ["P05: the thread's figures", "17 to 20 by age band, alone"])
def test_p3_a_turn_that_ends_unsupported_has_none(tmp_path, monkeypatch, case):
    """C64's test: a turn that ends UNSUPPORTED (its one count refused by C21) has no such line:
    the code's own row says it. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    if case.startswith("P05"):
        reply, (answer,) = p05(env)
        assert_refused(answer)
        want = f"{C62_REFUSAL} {CAN_ASK[1]}"
    else:
        reply = env.ask(Q_COUNT, Step(call_of(spec(Y25, [age(17, 20)], ["age_band"]))),
                        Step(finish("finding", "I counted {r1.count}.")))
        assert_not_allowed(env.model.answer(0))
        want = f"{NOT_ALLOWED_ROW} {CAN_ASK[1]}"
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
    assert reply.text == want, reply.text


@pytest.mark.parametrize("talk", TALK)
def test_p3_sent_and_the_turn_record_hold_the_line(tmp_path, monkeypatch, talk):
    """C64's test, "`sent` holds the line": the memory's `sent` and turn.json's reply are the reply
    with its line (a: P16; c: two sources), and the next message's thread block shows it."""
    env = env3(tmp_path, monkeypatch, "agent", talk, names=TWO)
    for thread_key, reply, line in (
            (THREAD_1, p16(env, counts_text(1)), C64_LINE_A),
            (THREAD_2, two_sources(env, counts_text(2), thread_key=THREAD_2), C64_LINE_C)):
        assert line in reply.text.split("\n"), reply.text
        assert memory(env, thread_key)[-1].get("sent") == reply.text
        assert turn_json(reply, env.runs_dir)["reply"] == reply.text
        env.ask("thanks, and what else?", Step(decline("UNRECOGNIZED_QUESTION")),
                thread_key=thread_key)
        block = norm(thread_block(env.model.calls[0]["messages"]))
        assert norm(f'You said: "{reply.text}"') in block, block[-700:]


@pytest.mark.parametrize("talk", TALK)
def test_p3_a_single_age_that_the_program_widens_keeps_only_the_widened_line(tmp_path,
                                                                            monkeypatch, talk):
    """C64's test: C21's own single-age refusal (C8.4, C35's `why`) that the program widens (C28)
    keeps only the widened line. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = env.ask("how many 16 year olds were arrested in 2025?",
                    Step(call_of(spec(Y25, [age(16, 16)]))),
                    Step(call_of(spec(Y25, [age(16, 17)]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "NOT_ALLOWED" and answer.get("why", "").startswith(
        "under 18, an age range must cover at least two years"), answer
    assert_answered(reply, "agent")
    assert_reply(reply.text, f"I counted {phrase(spec(Y25, [age(16, 17)]))}.",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A))


# ---- point 3, own tests -------------------------------------------------------------------------

@pytest.mark.parametrize("talk", TALK)
def test_own_5_a_refused_count_beside_a_count_made_when_the_threads_figures_are_the_cause(
        tmp_path, monkeypatch, talk):
    """Own 5 (R28-4): P05's second message counts 10 to 16 in 2025 (refused: with the first
    message's under 18, C61 point 10's sentence in its `why`) and under 18 in 2024 (made): line a,
    and neither C62's sentence nor the NOT_ALLOWED row."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    turns = {}
    for thread_key, refuse in ((THREAD_1, True), (THREAD_2, False)):
        first = env.ask(P05_FIRST, Step(call_of(spec(Y25, [U18]))),
                        Step(finish("finding", "I counted {r1.count}.")), thread_key=thread_key)
        assert first.status == "ANSWERED", first.text
        calls = ([call_of(spec(Y25, [age(10, 16)]))] if refuse else []) + \
            [call_of(spec(year(2024), [U18]))]
        turns[thread_key] = env.ask(P05_SECOND, Step(*calls),
                                    Step(finish("finding", "I counted {r1.count}.")),
                                    thread_key=thread_key)
        if refuse:
            assert_refused(env.model.answer(0, 0), WHY_THREAD)
            assert_result(env.model.answer(0, 1), "r1")
    reply = turns[THREAD_1]
    assert_answered(reply, "agent")
    assert_twin(reply, turns[THREAD_2], [C64_LINE_A])
    assert C62_REFUSAL not in reply.text and NOT_ALLOWED_ROW not in reply.text, reply.text


@pytest.mark.parametrize("talk", TALK)
def test_own_6_the_lines_place_among_c10s_lines(tmp_path, monkeypatch, talk):
    """Own 6 (R28-7): one reply with a kept line (the period, from the first message), C28's
    widened line (16 asked alone, 15 to 17 made), line a (15 to 16 refused by C21: the
    17-year-olds) and a left-out line, written out by hand: line 1, kept, widened, line a,
    left-out, the later source line."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    first = env.ask(Q_COUNT, Step(count(A_ID, Y25)),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED", first.text
    reply = env.ask("and how many 16 year olds?", Step(count(A_ID, filters=[age(16, 16)])),
                    Step(count(A_ID, filters=[age(15, 17)])),
                    Step(count(A_ID, filters=[age(15, 16)])),
                    Step(finish("finding", "I counted {r1.count}.")))
    single = env.model.answer(0)
    assert single.get("error") == "NOT_ALLOWED" and WHY not in single.get("why", ""), single
    assert_result(env.model.answer(1), "r1")
    assert_not_allowed(env.model.answer(2))
    assert_answered(reply, "agent")
    assert_reply(reply.text, f"I counted {phrase(spec(Y25, [age(15, 17)]))}.",
                 kept="(I kept 2025 from earlier.)",
                 left_out=[C28_LINE, C64_LINE_A, age_left_out_line(5)],
                 source=source_re(A, first=False))


# id: (the steps with the refusals, the twin's steps, the line given twice)
TWICE = {
    "line a: two counts refused by C21": (
        ("arrests_like",), [Step(MADE_U18, REFUSED_U17, call_of(spec(Y25, [age(10, 16)])))],
        [Step(MADE_U18)], C64_LINE_A),
    "line b: a ninth and a tenth count": (
        ("arrests_like",), [Step(*[count(A_ID, *s) for s in NINE],
                                 count(A_ID, Y25, [is_("district", "district 3")]))],
        [Step(*[count(A_ID, *s) for s in NINE[:8]])], C64_LINE_B),
    "line c: two compares of two sources": (
        TWO, [Step(count(A_ID, Y25), C_COUNT), Step(compare("r1", "r2")),
              Step(compare("r2", "r1"))], [Step(count(A_ID, Y25), C_COUNT)], C64_LINE_C),
}


@pytest.mark.parametrize("case", list(TWICE))
def test_own_7_each_line_once_when_its_refusal_comes_twice(tmp_path, monkeypatch, case):
    """Own 7: "each line once": two refusals of one kind in one turn give their line once."""
    names, steps, twin_steps, line = TWICE[case]
    env = env3(tmp_path, monkeypatch, names=names)
    reply = env.ask(Q_COUNT, *steps, Step(finish("finding", counts_text(1))))
    assert len(errors_of(env)) == 2 and len(set(errors_of(env))) == 1, errors_of(env)
    twin = env.ask(Q_COUNT, *twin_steps, Step(finish("finding", counts_text(1))),
                   thread_key=THREAD_2)
    assert_answered(reply, "agent")
    assert_twin(reply, twin, [line])


BASE = call_of(spec(Y25, [age(18, 24)]))  # made; covers no age under 18
OTHER_REFUSALS = {  # id: (the call, its error)
    "TOO_MANY of three breakdowns (C5), not of the eight counts":
        (count(A_ID, Y25, [], ["district", "gender", "race"]), "TOO_MANY"),
    "BAD_COMPARE: one count compared": (compare("r1"), "BAD_COMPARE"),
    "BAD_SHARE: a part that was not made": (share("r2", "r1"), "BAD_SHARE"),
    "BAD_FIELD: a field the source does not have": (
        count(A_ID, Y25, [is_("no_such_field", "x")]), "BAD_FIELD"),
    "NOT_ALLOWED of one year asked (C8.4), not widened": (
        call_of(spec(Y25, [age(16, 16)])), "NOT_ALLOWED"),
}


@pytest.mark.parametrize("case", list(OTHER_REFUSALS))
def test_own_8_other_refusals_beside_a_count_made_give_no_line(tmp_path, monkeypatch, case):
    """Own 8 (R28-4 to R28-6): a count made and a request refused for another reason: the reply is
    today's, exactly as with the count alone. Passes today; must still pass."""
    call, code = OTHER_REFUSALS[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(BASE), Step(call), Step(finish("finding", counts_text(1))))
    assert env.model.answer(1).get("error") == code, env.model.answer(1)
    twin = env.ask(Q_COUNT, Step(BASE), Step(finish("finding", counts_text(1))),
                   thread_key=THREAD_2)
    assert_answered(reply, "agent")
    assert reply.text == twin.text, reply.text


@pytest.mark.parametrize("talk", TALK)
def test_own_9_an_answer_that_ends_on_the_fixed_rendering_holds_the_line(tmp_path, monkeypatch,
                                                                        talk):
    """Own 9 (R28-8): a decline after a count ends ANSWERED on the fixed rendering, style fallback,
    with DECLINED_AFTER_RESULTS (end_fixed): an ANSWERED end like any other, so line a is there."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    code = "UNSUPPORTED_METRIC"
    reply = env.ask(Q_COUNT, Step(MADE_U18, REFUSED_U17), Step(decline(code)))
    assert_not_allowed(env.model.answer(0, 1))
    twin = env.ask(Q_COUNT, Step(MADE_U18), Step(decline(code)), thread_key=THREAD_2)
    assert_answered(reply, "fallback")
    assert "DECLINED_AFTER_RESULTS" in reply.draft_failures, reply.draft_failures
    assert_twin(reply, twin, [C64_LINE_A])


@pytest.mark.parametrize("talk", TALK)
def test_own_10_a_question_back_after_a_refusal_has_no_line(tmp_path, monkeypatch, talk):
    """Own 10: "a turn that does not end ANSWERED is as today": a count made, one refused by C21,
    then ask_user: NEEDS_INPUT with Python's question and no such line. Passes today; must still
    pass."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = env.ask(Q_COUNT, Step(MADE_U18, REFUSED_U17), Step(ask_with("other")))
    assert_not_allowed(env.model.answer(0, 1))
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.text)
    assert not any(line in reply.text for line in C64_LINES), reply.text


def test_own_11_synthetic_mode_is_untouched(tmp_path):
    """Own 11: "County mode only": in SYNTHETIC mode nine counts give today's LIMIT and no line.
    Passes today; must still pass."""
    env = Env(tmp_path)
    nine = [(y, g) for y in (2024, 2025) for g in ("under_18", "18_25", "26_40", "41_plus",
                                                   "all")][:9]
    reply = env.ask("How many arrests were there in 2024 and 2025 for each age group?",
                    Step(*[synthetic_count(y, g) for y, g in nine]),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0, 8) == {"error": "LIMIT"}, env.model.answer(0, 8)
    assert reply.status == "ANSWERED", (reply.status, reply.text)
    assert not any(line in reply.text for line in C64_LINES), reply.text


# ==== point 4: who to write to ===================================================================

ABOUT_FILE = REPO / "config" / "about_agent.md"
EIGHT_FACTS = [  # config/about_agent.md version 1 (D-077), written out by hand
    "I am Jeffrey, an AI data agent built as a university course project.",
    "I am not a Montgomery County service, and the County has not taken part in, sponsored or "
    "endorsed me.",
    "An AI model reads each question and chooses what to count. A program then counts the records "
    "and writes every number, so no figure comes from the model's memory.",
    "All my data is public open data that Montgomery County, Maryland, publishes on its "
    "dataMontgomery site. I work from saved copies of it, not from the live site.",
    "I never give a figure for one single year of age under 18, in one answer or across a "
    "conversation. That is a rule of this project, set by its owner. It is not a law and not the "
    "County's rule.",
    "The resident numbers I use for rates come from the U.S. Census Bureau's American Community "
    "Survey one-year estimates for Montgomery County, Maryland.",
    "I cannot see the County's website or any other source, so I cannot check my figures against "
    "them. The County's open data has every record.",
    "I give counts, comparisons and statistics. I give no opinions, no causes and no advice about "
    "what anyone should do.",
]
MODEL_FACT = "The AI model behind me is "  # C61 point 2f, after the file's facts


def describe_facts(env, question="who do I complain to about you?"):
    """The fact texts describe_data offers in a county turn, in order."""
    env.ask(question, Step(describe()), Step(finish("about_data", "Here is what I know. {f1}.")))
    (facts,) = [a["facts"] for a in env.answers() if "facts" in a]
    return [f["text"] for f in facts]


def test_p4_the_file_is_version_2_with_nine_facts():
    """C64's test: nine facts from the file (R28-9)."""
    text = ABOUT_FILE.read_text(encoding="utf-8")
    facts = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
    assert facts == EIGHT_FACTS + [C64_NINTH_FACT], facts[8:] or facts
    assert "version 2" in text and "version 1" not in text, text.splitlines()[0]


@pytest.mark.parametrize("talk", TALK)
def test_p4_the_ninth_is_offered_by_describe_data_with_the_others(tmp_path, monkeypatch, talk):
    """C64's test: describe_data offers the nine facts of config/about_agent.md, in file order,
    before the model fact; an about answer that names the ninth sends it (C63)."""
    monkeypatch.setattr(mod("replies"), "ABOUT_AGENT", ABOUT_FILE)
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    facts = describe_facts(env)
    first = facts.index(EIGHT_FACTS[0])
    assert facts[first:first + 9] == EIGHT_FACTS + [C64_NINTH_FACT], facts[first:]
    assert facts[first + 9].startswith(MODEL_FACT), facts[first + 9]
    assert facts.count(C64_NINTH_FACT) == 1
    reply = env.ask("who do I complain to about you?", Step(describe()),
                    Step(finish("about_data", f"Here is what I know. {{f{first + 9}}}")))
    assert (reply.status, reply.reply_style) == ("EXPLAINED", "agent"), reply.text
    assert reply.text.startswith(f"Here is what I know. {C64_NINTH_FACT}\n"), reply.text


def test_p4_the_tests_own_fixture_of_the_file_is_theirs(tmp_path, monkeypatch):
    """C64's test: "the tests' own fixture of the file is theirs": with the fixture copy
    (C61_ABOUT_LINES), describe_data offers its three facts and not the ninth: the ninth comes from
    the file, not from the program. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    facts = describe_facts(env)
    first = facts.index(C61_ABOUT_FACTS[0])
    assert facts[first:first + 3] == C61_ABOUT_FACTS, facts[first:]
    assert facts[first + 3].startswith(MODEL_FACT), facts[first + 3]
    assert C64_NINTH_FACT not in facts and not any(f in facts for f in EIGHT_FACTS), facts


def test_premise_no_figure_in_lines_a_and_c_and_the_number_of_b():
    """The lines as written by hand: a and c hold no digit; b holds the program's eight (R28-5)."""
    assert not re.search(r"\d", C64_LINE_A.replace("under 18", "")) and \
        not re.search(r"\d", C64_LINE_C)
    assert re.findall(r"\d+", C64_LINE_B) == [str(mod("agent").MAX_COUNTS)] == ["8"]
    json.dumps(C64_LINES)
