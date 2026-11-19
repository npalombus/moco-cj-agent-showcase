"""T3 of docs/T-DESIGN.md, and T7's fourth point: one second try.

What this file covers, for each of the four kinds (talk, finding, about_data, background)
- A failing first text is answered with exactly {"error": "REWRITE", "problems": [codes],
  "found": [...], "do": <the rewrite_hints line of the first code>}, and the turn goes on.
- `found`: the offending words, phrases or characters, from the model's own text, in
  lower case, at most five; nothing that was not in the model's text, and no value from
  the data in any tool message.
- A passing second text is sent with style agent; a failing second text ends the turn as
  today: the fixed rendering (finding), the fixed ABOUT text (about_data), the fixed
  refusal (background), the fallback line of config/talk_rules.json (talk: TALKED, style
  fallback). The turn record keeps the codes of both tries (first_failures, failures).
- No second try when no step is left, or when less than five seconds are left (and one
  when exactly five are left); never a third try.

READINGS (kit-log/raw/T-A-notes.txt):
- "The saved turn keeps the codes of both tries (first_failures, failures)": the turn
  record runs/<turn id>/turn.json (A9) has the keys `first_failures` and `failures`;
  `failures` is [] when the second try passed. Compared as sets.
- "At least one step left": the step that made the failing finish is not the last of
  MOCO_MAX_STEPS. "Five seconds left": MOCO_TURN_SECONDS less the seconds since the turn
  began (the FakeClock, moved only by the FakeModel at each step) is 5 or more.
- The rewrite hints and the fallback line are written out by hand in tsupport.py; each
  test that uses them first checks that config/talk_rules.json still says so.
- For REASON (a phrase that is missing), `found` is only checked for holding nothing that
  was not in the text.
"""
import re
from pathlib import Path

import pytest

from p1support import (BACKGROUND_PREFIX, BACKGROUND_SUFFIX, DATA_TAG, ONE_COUNT_TEXT, Step,
                       about_text, assert_answered, assert_fixed, check_no_data_counts, count,
                       describe, fact_slots, fill_expect, finish, fixed_line1_re,
                       messages_text, numbers_in, one_count_line, single_sentence_facts,
                       tool_messages, tool_numbers_allowed)
from s3support import C62_MAKER_HINT, FALLBACK_LINE_C57, fallback_line_of
from tsupport import (BACKGROUND_CODES, FINDING_CODES, HELLO_TEXT, HINTS,
                      TALK_CODES, assert_talked, listed_in, premise_talk, talk_env, talk_rules,
                      turn_json)

A, B = single_sentence_facts()[:2]
BG_GOOD = ("Arrests may rise in summer because people spend more time outdoors. To check it, "
           "you would need records of arrests by season and by place.")
BG_NO_REASON = ("Arrests may rise in summer. To check it, you would need records of arrests by "
                "season and by place.")
BG_NO_CHECK = "Arrests may rise in summer because people spend more time outdoors."

# kind: (question, steps before the finish, a passing text, the codes it may give)
KINDS = {
    "talk": ("hello", (), HELLO_TEXT, TALK_CODES),
    "finding": ("How many arrests were recorded each month in 2025 for ages 18 to 25?",
                (Step(count(2025, "18_25")),), ONE_COUNT_TEXT, FINDING_CODES),
    "about_data": ("What data do you have?", (Step(describe()),), about_text(A),
                   FINDING_CODES),
    "background": ("Why might arrests rise in summer?", (), BG_GOOD, BACKGROUND_CODES),
}
# kind: (failing text, its codes, its found), and a second failing text with other codes.
FIRST = {
    "talk": ("I can look at two years for you.", ["NUMBER"], ["two"]),
    "finding": ("I counted {r1.count}. That is a lot.", ["JUDGE"], ["a lot"]),
    "about_data": (f"Here is what I know, in two parts. {{f{A}}}.", ["NUMBER"], ["two"]),
    "background": (BG_NO_REASON, ["REASON"], None),
}
SECOND = {
    "talk": ("It went up because of summer.", ["CLAIM"]),
    "finding": ("I counted {r1.count}. It went up because of summer.", ["CLAIM"]),
    "about_data": (f"Sadly, {{f{A}}}.", ["WORD"]),
    "background": (BG_NO_CHECK, ["REASON"]),
}


def env_for(tmp_path, kind, **settings_values):
    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    if kind == "background":
        background_premise()
        settings_values.setdefault("MOCO_BACKGROUND", "on")
    return talk_env(tmp_path, **settings_values)


def background_premise():
    """This file's background texts are what their names say, by talk_rules.json's lists
    (and each passes today's background check: tests/t/test_t_background.py)."""
    rules = talk_rules()
    reason, check = rules["reason_phrases"], rules["check_phrases"]
    assert listed_in(reason, BG_GOOD) and listed_in(check, BG_GOOD)
    assert not listed_in(reason, BG_NO_REASON) and listed_in(check, BG_NO_REASON)
    assert listed_in(reason, BG_NO_CHECK) and not listed_in(check, BG_NO_CHECK)


def assert_nothing_but_the_model_words(model, text):
    """No tool message holds a number other than the covered years, the fact sheet's
    numbers and the numbers the model itself typed in `text`; no message at all holds a
    total from the data."""
    allowed = tool_numbers_allowed() | numbers_in(text)
    for recorded in model.calls:
        for message in tool_messages(recorded["messages"]):
            extra = numbers_in(message["content"]) - allowed
            assert not extra, f"a tool message holds {extra}: {message['content']!r}"
        check_no_data_counts(messages_text(recorded["messages"]))


def ask(env, kind, *texts, **kw):
    """One turn of `kind`: its steps before the finish, then one finish per text."""
    question, before, _, _ = KINDS[kind]
    return env.ask(question, *before, *[Step(finish(kind, t)) for t in texts], **kw)


def assert_sent(reply, kind, text):
    """The reply of a text that passed, as each kind sends it (T1, T2 with R1, A7)."""
    assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
    if kind == "talk":
        assert_talked(reply, text)
    elif kind == "finding":
        assert (reply.status, reply.reply_kind) == ("ANSWERED", "finding")
        assert_answered(reply.text, re.escape(one_count_line(2025, "18_25")), first=True)
    elif kind == "about_data":
        assert (reply.status, reply.reply_kind) == ("EXPLAINED", "about_data")
        filled = fill_expect(text, fact_slots())
        assert re.fullmatch(re.escape(filled) + "[ \n]" + re.escape(DATA_TAG), reply.text)
    else:
        assert (reply.status, reply.reply_kind) == ("EXPLAINED", "background")
        assert reply.text == BACKGROUND_PREFIX + text + BACKGROUND_SUFFIX


def assert_fell_back(reply, kind):
    """T3: the turn ends as today when the second try fails or there is none."""
    assert reply.reply_style == "fallback", (reply.status, reply.reply_style, reply.text)
    if kind == "talk":
        # Changed by briefs/S3-R21-A-tests.md (C57 point 6 of docs/S3A-DESIGN.md; was today's line
        # in both): the file's line is C57's; SYNTHETIC mode's reply is today's line or C57's
        # (s3support.fallback_lines; a question in briefs/QUESTIONS.md).
        assert talk_rules()["fallback_line"] == FALLBACK_LINE_C57
        assert_talked(reply, fallback_line_of(reply.text, county=False), style="fallback")
    elif kind == "finding":
        assert reply.status == "ANSWERED"
        assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    elif kind == "about_data":
        assert reply.status == "EXPLAINED"
        assert_fixed(reply.text, "ABOUT")
    else:
        assert reply.status in ("UNSUPPORTED", "EXPLAINED"), reply.status  # as test_p1_replies
        assert_fixed(reply.text, "BACKGROUND_OFF")


@pytest.mark.parametrize("kind", list(KINDS))
def test_a_failing_first_text_gets_rewrite(tmp_path, kind):
    """T3: the first failing finish is answered with exactly error, problems, found and do;
    `do` is the rewrite_hints line of the first code; the turn goes on to a second step.
    Changed by briefs/S3-R24-A-tests.md (C62 point 1: rewrite_hints gains MAKER): the hints were
    `== HINTS`; now tsupport's hints and C62's MAKER hint (s3support.C62_MAKER_HINT).
    Changed by briefs/S3-R28-A-tests.md (C64 point 1): tsupport.HINTS["NUMBER"] is C64's hint
    (today's two sentences, one space, s3support.C64_HINT_SENTENCE), in SYNTHETIC mode too; the
    lines are unchanged."""
    assert talk_rules()["rewrite_hints"] == {**HINTS, "MAKER": C62_MAKER_HINT}
    text, codes, found = FIRST[kind]
    if kind == "talk":
        premise_talk(text, "NUMBER")
        premise_talk(SECOND[kind][0], "CLAIM")
    env = env_for(tmp_path, kind)
    n = len(KINDS[kind][1])
    ask(env, kind, text, KINDS[kind][2])
    assert len(env.model.calls) == n + 2, "the turn did not go on after the first finish"
    answer = env.model.answer(n)
    assert set(answer) == {"error", "problems", "found", "do"}, answer
    assert answer["error"] == "REWRITE"
    assert answer["problems"] == codes
    assert answer["do"] == HINTS[codes[0]]
    if found is not None:
        assert answer["found"] == found
    assert isinstance(answer["found"], list) and len(answer["found"]) <= 5
    assert all(isinstance(f, str) and f in text.lower() for f in answer["found"]), answer
    assert_nothing_but_the_model_words(env.model, text)


@pytest.mark.parametrize("kind", list(KINDS))
def test_a_passing_second_text_is_sent_with_style_agent(tmp_path, kind):
    """T3: if the second text passes, the reply's style is agent; the turn record keeps the
    first try's codes, and no failure of the second."""
    text, codes, _ = FIRST[kind]
    good = KINDS[kind][2]
    env = env_for(tmp_path, kind)
    reply = ask(env, kind, text, good)
    assert_sent(reply, kind, good)
    record = turn_json(reply, env.runs_dir)
    assert set(record["first_failures"]) == set(codes), record.get("first_failures")
    assert list(record["failures"]) == [], record.get("failures")


@pytest.mark.parametrize("kind", list(KINDS))
def test_a_failing_second_text_falls_back_and_both_tries_are_kept(tmp_path, kind):
    """T3: if the second text fails too, the turn ends as today for its kind; the turn
    record keeps the codes of both tries. None of the model's words reach the reply."""
    text, codes, _ = FIRST[kind]
    second, second_codes = SECOND[kind]
    env = env_for(tmp_path, kind)
    n = len(KINDS[kind][1])
    reply = ask(env, kind, text, second, KINDS[kind][2])
    assert len(env.model.calls) == n + 2, "a third finish was asked for"
    assert env.model.answer(n)["error"] == "REWRITE"
    assert_fell_back(reply, kind)
    assert "summer" not in reply.text and "a lot" not in reply.text
    record = turn_json(reply, env.runs_dir)
    assert set(record["first_failures"]) == set(codes), record.get("first_failures")
    assert set(record["failures"]) == set(second_codes), record.get("failures")


@pytest.mark.parametrize("kind", list(KINDS))
def test_never_a_third_try(tmp_path, kind):
    """T3: "The model may call finish once more", once: after the second failure the turn
    ends, though steps and time are left and a passing text would follow."""
    text, _, _ = FIRST[kind]
    second, _ = SECOND[kind]
    env = env_for(tmp_path, kind)
    n = len(KINDS[kind][1])
    reply = ask(env, kind, text, second, text, KINDS[kind][2])
    assert len(env.model.calls) == n + 2, len(env.model.calls)
    assert_fell_back(reply, kind)


@pytest.mark.parametrize("kind", ["talk", "finding"])
def test_no_second_try_without_a_step_left(tmp_path, kind):
    """T3: the failing finish made in the last step allowed (MOCO_MAX_STEPS) gets no
    REWRITE: the turn falls back at once. One step more, and it is asked to rewrite."""
    text, _, _ = FIRST[kind]
    n = len(KINDS[kind][1])
    last = env_for(tmp_path / "last", kind, MOCO_MAX_STEPS=n + 1)
    reply = ask(last, kind, text, KINDS[kind][2])
    assert len(last.model.calls) == n + 1
    assert_fell_back(reply, kind)
    spare = env_for(tmp_path / "spare", kind, MOCO_MAX_STEPS=n + 2)
    reply = ask(spare, kind, text, KINDS[kind][2])
    assert spare.model.answer(n)["error"] == "REWRITE"
    assert_sent(reply, kind, KINDS[kind][2])


@pytest.mark.parametrize("kind", ["talk", "finding"])
def test_no_second_try_with_less_than_five_seconds_left(tmp_path, kind):
    """T3: MOCO_TURN_SECONDS 15. Each model step takes `seconds` on the FakeClock. When the
    failing finish comes with exactly 5 seconds left there is a second try; with 4 or
    fewer left there is none and the turn falls back at once."""
    text, _, _ = FIRST[kind]
    n = len(KINDS[kind][1])
    steps_done = n + 1
    five_left = 10 / steps_done          # 15 - 10 = 5 left
    four_left = 11 / steps_done if kind == "talk" else 6.0   # 4 and 3 left
    tight = env_for(tmp_path / "tight", kind, MOCO_TURN_SECONDS=15)
    reply = ask(tight, kind, text, KINDS[kind][2], seconds=four_left)
    assert len(tight.model.calls) == n + 1
    assert_fell_back(reply, kind)
    enough = env_for(tmp_path / "enough", kind, MOCO_TURN_SECONDS=15)
    reply = ask(enough, kind, text, KINDS[kind][2], seconds=five_left)
    assert enough.model.answer(n)["error"] == "REWRITE"
    assert_sent(reply, kind, KINDS[kind][2])


def test_found_is_in_lower_case_and_taken_from_the_text(tmp_path):
    """T3: `found` is taken from the model's own text, in lower case."""
    env = env_for(tmp_path, "finding")
    text = "I counted {r1.count}. That is A LOT."
    ask(env, "finding", text, ONE_COUNT_TEXT)
    answer = env.model.answer(1)
    assert answer["error"] == "REWRITE", answer
    assert answer["problems"] == ["JUDGE"] and answer["found"] == ["a lot"], answer
    premise_talk("TWICE as quick next time!", "NUMBER")
    talk = env_for(tmp_path / "talk", "talk")
    ask(talk, "talk", "TWICE as quick next time!", HELLO_TEXT)
    assert talk.model.answer(0)["error"] == "REWRITE", talk.model.answer(0)
    assert talk.model.answer(0)["found"] == ["twice"], talk.model.answer(0)


def test_found_holds_at_most_five(tmp_path):
    """T3: at most five of the offending words, all of them from the text."""
    text = "Two, three, four, five, six or seven?"
    premise_talk(text, "NUMBER")
    env = env_for(tmp_path, "talk")
    ask(env, "talk", text, HELLO_TEXT)
    answer = env.model.answer(0)
    assert answer["error"] == "REWRITE", answer
    assert answer["problems"] == ["NUMBER"], answer
    assert 1 <= len(answer["found"]) <= 5, answer["found"]
    assert set(answer["found"]) <= {"two", "three", "four", "five", "six", "seven"}


def test_do_is_the_hint_of_the_first_code(tmp_path):
    """T3: with several codes, `do` is the rewrite_hints line of the first code given.
    Round 2 (T11): the em dash is an allowed mark now, so the codes are NUMBER and CLAIM,
    without CHARS (which came with them before). Changed by briefs/S3-R28-A-tests.md (C64 point
    1): NUMBER's hint in tsupport.HINTS is C64's (it was the first two sentences alone), in
    SYNTHETIC mode too; the lines are unchanged."""
    text = "It went up in March — because of summer."
    env = env_for(tmp_path, "talk")
    ask(env, "talk", text, HELLO_TEXT)
    answer = env.model.answer(0)
    assert answer["error"] == "REWRITE", answer
    assert set(answer["problems"]) == {"NUMBER", "CLAIM"}, answer
    assert answer["do"] == HINTS[answer["problems"][0]]
    assert all(f in text.lower() for f in answer["found"]), answer["found"]


@pytest.mark.parametrize("kind, text", [
    ("talk", "There were 4321 of them, says zebra-quartz zqx."),
    ("talk", "Hello  there {r1.count}."),
    ("finding", "I counted {r1.count}. There were 4321 more, zqx."),
    ("finding", "I counted roughly {r1.count}. Then some."),
    ("about_data", f"Here is what I know about 2024 and the twelve months. {{f{A}}}."),
], ids=["talk-digits", "talk-chars", "finding-digits", "finding-word", "about-number"])
def test_found_holds_nothing_that_was_not_in_the_text(tmp_path, kind, text):
    """T3: "Nothing but the model's own words is given back to it": each item of `found` is
    part of the model's text (lower case), and no tool message the model is given holds a
    number that is not a covered year, a fact sheet number or the model's own, nor any
    total from the data."""
    env = env_for(tmp_path, kind)
    n = len(KINDS[kind][1])
    ask(env, kind, text, KINDS[kind][2])
    answer = env.model.answer(n)
    assert answer["error"] == "REWRITE", answer
    assert answer["found"], "nothing found in a text that fails"
    assert all(isinstance(f, str) and f in text.lower() for f in answer["found"]), answer
    assert_nothing_but_the_model_words(env.model, text)
