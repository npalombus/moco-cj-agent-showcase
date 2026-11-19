"""Round 2 of Part T: docs/T-DESIGN.md T10 to T14, every point of T15. Brief
briefs/T2-A-tests.md. Everything here runs with MOCO_TALK on unless a test says otherwise.

What this file covers
- T10, tidying: `replies.tidy(text)` on its own, each of the three steps alone and
  together, in their order; the same through whole turns, for a talk text and for a
  finding (both data modes), for a plain-text reply and for about_data and background;
  the text sent and saved is the tidied one and the step log keeps the model's own; a text
  of only removed characters is empty (SHAPE); a private-use character still fails CHARS;
  a keycap digit still fails NUMBER; with MOCO_TALK unset or off nothing is tidied.
- T11: each new mark passes in a talk text and in a talk sentence of a finding (both
  modes), and in a fact sentence keeps R1's characters (see the READING below).
- T12: the edges at 6 and 7 sentences and at 700 and 701 characters; the limits are
  measured on the tidied text; the finding limits do not change.
- T13: a plain-text reply that fails gets a second try: the two added messages exactly;
  a passing second try as a finish call and as plain text; a failing second try falls
  back and there is never a third; no second try without a step or without five seconds;
  for talk, a finding (both modes) and about_data.
- T14: seven short sentences are cut to six; a text over 700 characters is cut at a
  sentence end; one sentence over 700 characters gets the fallback line; SHAPE with any
  other code is not cut; "cut": true is saved; nothing is cut in a finding (both modes),
  an about_data text or a background text; only the text that ends the turn is cut.
- No figure through talk still holds after tidying: digits, number words, months and
  labels (brief step 5: test_no_figure_reaches_a_talk_reply_after_tidying).

Every expected text, code and message is written out by hand. The round 2 values of
config/talk_rules.json are in tsupport.py, written out by hand; each turn test first checks
the file says them (tsupport.round2_rules), so until the build it fails there.

READINGS (each is also in kit-log/raw/T2-A-notes.txt)
- T11 and T15 disagree on the dashes: T15 says each new mark "still fails CHARS in a fact
  sentence", T11 says "A fact sentence keeps R1's characters", and R1's characters already
  include the en dash and the em dash (they pass in a fact sentence today, and
  test_t_mixed.py says so). Taken: T11 and R1. The straight and curly quotation marks and
  the ellipsis fail CHARS in a fact sentence; the two dashes pass there, as today.
- T10 "saved as the reply": the turn record's `reply` and the text stored with the turn in
  the database (shown to the model in later turns) are the tidied text; the model's raw
  text is in the step log of turn.json only.
- T13 "the REWRITE object of T3, as JSON": the note is the fixed words followed by JSON
  text; the JSON is compared as an object (its spacing is not given).
- T14 "the saved turn ... gets "cut": true": the turn record, turn.json (where T3's
  first_failures and failures are, as tests/t read them). A turn that was not cut has no
  "cut" or "cut": false.
- T10 step 3 "every run of white space": tested with the characters the contract names
  (spaces, tabs, line breaks, U+2028, U+2029) only.
"""
import json
import re
from collections.abc import Mapping

import pytest

from p1support import (BACKGROUND_PREFIX, BACKGROUND_SUFFIX, DATA_TAG, ONE_COUNT_TEXT,
                       THREAD_1, Env, Step, about_text, assert_answered, assert_fixed,
                       check_no_model_text, count, count_slots, describe, fact_slots,
                       fill_expect, finish, fixed_line1_re, has_leaf, make_settings, mod,
                       odd_chars, one_count_line, sentences, single_sentence_facts,
                       thread_block)
from s3support import (A_ID, C64_TALK_LINE, Q_COUNT, count as county_count, county_fallback_line,
                       fallback_line_of, fallback_lines,
                       year)
from tsupport import (FINDING_CODES, HELLO_TEXT, HINTS, MOST_CHARS_TALK,
                      MOST_TALK_SENTENCES, NEW_MARKS, TALK_CODES, THANKS_TEXT, assert_talked,
                      check_cases, county_labels, county_talk_env, first_try, mixed_faults,
                      padded, premise_talk, round2_rules, split_sentences, synthetic_labels,
                      talk_env, talk_faults, thread, tidied, turn_json)

Q = "How many arrests were recorded each month in 2025 for ages 18 to 25?"
Q_ABOUT = "What data do you have?"
Q_BACKGROUND = "Why might arrests rise in summer?"
A = single_sentence_facts()[0]
NOTE_HEAD = "PROGRAM NOTE (not from the person). Your reply was not sent. "
LINE1 = count_slots("r1", 2025, "18_25")
COUNTY_LINE1 = "I counted 240 arrest records in 2025."   # the fixture's count, as test_t_mixed


def on(tmp_path, **settings_values):
    """SYNTHETIC mode with MOCO_TALK on, once config/talk_rules.json is version 2."""
    round2_rules()
    tmp_path.mkdir(parents=True, exist_ok=True)
    return talk_env(tmp_path, **settings_values)


def county_on(tmp_path, monkeypatch, **kw):
    round2_rules()
    tmp_path.mkdir(parents=True, exist_ok=True)
    return county_talk_env(tmp_path, monkeypatch, **kw)


def tidy(text):
    """T10's function, as the brief names it: moco_agent.replies.tidy."""
    return mod("replies").tidy(text)


def step_lists(record):
    """The step log (R6): every list in the record whose items are all objects holding the
    key `text` (as tests/p1/test_p1_turn_record.py reads it)."""
    found = []

    def walk(obj):
        if isinstance(obj, Mapping):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            if obj and all(isinstance(item, Mapping) and "text" in item for item in obj):
                found.append(obj)
            for value in obj:
                walk(value)
    walk(record)
    return found


def saved_turn(env, thread_key=THREAD_1):
    """The newest turn of the thread as the database keeps it."""
    turns = env.store.recent_turns(thread_key, 10)
    assert turns, "no turn saved in the thread"
    return turns[-1]


def not_cut(record):
    assert record.get("cut") in (None, False), record.get("cut")


def county_finding_reply(reply, line1):
    """A county finding sent in the model's words: line 1 is the text filled, and Python's
    lines (the source line) come after it, as today (C10)."""
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("ANSWERED", "finding", "agent"), (reply.status, reply.reply_style, reply.text)
    assert reply.text.startswith(line1 + "\n"), reply.text


# ==== T10: tidying, on its own ===============================================================

TIDY = [
    ("step 1, the hyphens", "a well‑read, self‐taught helper",
     "a well-read, self-taught helper"),
    ("step 1, the spaces", "one two three four five",
     "one two three four five"),
    ("step 2, the marks", "Use *this* `one`️ now", "Use this one now"),
    ("step 2, the pictures", "Hi\U0001F44B\U0001F3FD there✅ friend\U0001F468‍\U0001F4BB!",
     "Hi there friend!"),
    ("step 2, other So characters", "Thanks❤️ a lot☺ and© done™°",
     "Thanks a lot and done"),
    ("step 3, white space", "  Hello\tthere\n\nfriend\r\nhow are you  ",
     "Hello there friend how are you"),
    ("together", " **Hi** \U0001F44B there!\n\nI’m a well‑read `helper`. ",
     "Hi there! I’m a well-read helper."),
    ("together, in this order", "Done *\n*  \U0001F44D next", "Done next"),
    ("what is kept", "Hithere 1️⃣ {r1.count} 50% … “ok” — "
                     "café ’",
     "Hithere 1⃣ {r1.count} 50% … “ok” — café ’"),
    ("nothing to tidy", HELLO_TEXT, HELLO_TEXT),
    ("only removed characters", " \U0001F44B✨ **`` ️‍\n\t ", ""),
]


@pytest.mark.parametrize("name, text, want", TIDY, ids=[t[0] for t in TIDY])
def test_tidy(name, text, want):
    """T10: 1. U+2010 and U+2011 become `-`; U+00A0, U+2007, U+2009 and U+202F a space.
    2. `*`, the backtick, U+FE0F, U+200D, every So character and U+1F3FB to U+1F3FF are
    removed. 3. Every run of white space becomes one space; the ends are trimmed. A
    private-use character, a digit, a slot, U+20E3 (the keycap's ring, not So) and the
    marks of T11 are kept. A text of only removed characters is empty."""
    assert tidied(text) == want, "the premise: the test's own reading of T10"
    assert tidy(text) == want


# ==== T10: through whole turns ==================================================================

TALK_TIDY = {
    "step 1": ("Hello there! Ask me anything, any time at all. I’m a "
               "well‑read and self‐taught helper.",
               "Hello there! Ask me anything, any time at all. I’m a well-read and "
               "self-taught helper."),
    "step 2": ("Hello there!\U0001F44B\U0001F3FD Ask me *anything*, any `time`."
               "\U0001F468‍\U0001F4BB",
               "Hello there! Ask me anything, any time."),
    "step 3": ("  Hello there!\nAsk me anything,\tany time.\r\n\r\nSee you. Bye.  ",
               "Hello there! Ask me anything, any time. See you. Bye."),
    "together": (" Hello there!\U0001F44B\n\n**Ask** me anything, any time."
                 " I’m a well‑read helper. ",
                 "Hello there! Ask me anything, any time. I’m a well-read helper."),
}
FINDING_TIDY = {
    "step 1": ("A follow‑up is welcome. I counted {r1.count}. {r1.months}.",
               "A follow-up is welcome. I counted {r1.count}. {r1.months}."),
    "step 2": ("**Here** you go!\U0001F44D I counted {r1.count}. {r1.months}.",
               "Here you go! I counted {r1.count}. {r1.months}."),
    "step 3": ("Here you go!\nI counted {r1.count}.  {r1.months}.\t",
               "Here you go! I counted {r1.count}. {r1.months}."),
    "together": (" **Here** you go!\U0001F44D\nI counted {r1.count}. {r1.months}. A "
                 "follow‑up is welcome. ",
                 "Here you go! I counted {r1.count}. {r1.months}. A follow-up is welcome."),
}


def talk_premise(raw, clean):
    assert tidied(raw) == clean and raw != clean
    premise_talk(clean, None, synthetic_labels())


def finding_premise(raw, clean, labels=None):
    assert tidied(raw) == clean and raw != clean
    assert mixed_faults(clean, synthetic_labels() if labels is None else labels) == set()


@pytest.mark.parametrize("step", list(TALK_TIDY))
def test_a_talk_text_is_tidied_then_checked_and_sent(tmp_path, step):
    """T10 for a talk text: each step alone and all together. The tidied text passes and
    is sent at the first try (TALKED, kind talk, style agent, one model call)."""
    raw, clean = TALK_TIDY[step]
    talk_premise(raw, clean)
    env = on(tmp_path)
    reply = env.ask("hello", Step(finish("talk", raw)), Step(finish("talk", raw)))
    assert len(env.model.calls) == 1, "the tidied text did not pass at the first try"
    assert_talked(reply, clean)


@pytest.mark.parametrize("step", list(FINDING_TIDY))
def test_a_finding_is_tidied_then_checked_and_sent(tmp_path, step):
    """T10 for a finding: each step alone and all together. The tidied text passes and line
    1 is the tidied text filled (style agent, no second try)."""
    raw, clean = FINDING_TIDY[step]
    finding_premise(raw, clean)
    env = on(tmp_path)
    reply = env.ask(Q, Step(count(2025, "18_25")), Step(finish("finding", raw)),
                    Step(finish("finding", raw)))
    assert len(env.model.calls) == 2, "the tidied text did not pass at the first try"
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("ANSWERED", "finding", "agent"), (reply.status, reply.reply_style, reply.text)
    assert_answered(reply.text, re.escape(fill_expect(clean, LINE1)), first=True)


def test_a_county_finding_is_tidied_then_checked_and_sent(tmp_path, monkeypatch):
    """T10 for a finding in county mode: all three steps together."""
    raw = " **Here** you go!\U0001F44D\nI counted {r1.count}.  A follow‑up is welcome. "
    clean = "Here you go! I counted {r1.count}. A follow-up is welcome."
    finding_premise(raw, clean, county_labels("arrests_like"))
    env = county_on(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(county_count(A_ID, year(2025))), Step(finish("finding", raw)),
                    Step(finish("finding", raw)))
    assert len(env.model.calls) == 2, "the tidied text did not pass at the first try"
    county_finding_reply(reply, "Here you go! " + COUNTY_LINE1 + " A follow-up is welcome.")


@pytest.mark.parametrize("kind", ["talk", "finding"])
def test_a_plain_text_reply_is_tidied_too(tmp_path, kind):
    """T10: "a plain-text reply read as one" is tidied first: plain text that only needs
    tidying passes at once and is sent tidied; the step keeps the model's own text."""
    raw, clean = (TALK_TIDY if kind == "talk" else FINDING_TIDY)["together"]
    env = on(tmp_path)
    before = () if kind == "talk" else (Step(count(2025, "18_25")),)
    reply = env.ask("hello" if kind == "talk" else Q, *before, Step(text=raw), Step(text=raw))
    assert len(env.model.calls) == len(before) + 1, "the tidied text did not pass at once"
    if kind == "talk":
        assert_talked(reply, clean)
    else:
        assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
        assert_answered(reply.text, re.escape(fill_expect(clean, LINE1)), first=True)
    texts = [[item["text"] for item in found] for found in step_lists(turn_json(reply,
                                                                                env.runs_dir))]
    assert any(raw in found for found in texts), texts


def test_about_data_and_background_texts_are_tidied_too(tmp_path):
    """T10: "Every finish text of every kind": an about_data text and a background text that
    only need tidying pass and are sent tidied, with Python's words as today."""
    about_raw = f"Here is what I know!\U0001F44B\n{{f{A}}}."
    about_clean = f"Here is what I know! {{f{A}}}."
    assert tidied(about_raw) == about_clean
    env = on(tmp_path / "about")
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", about_raw)),
                    Step(finish("about_data", about_raw)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style, reply.text)
    filled = fill_expect(about_clean, fact_slots())
    assert re.fullmatch(re.escape(filled) + "[ \n]" + re.escape(DATA_TAG), reply.text), reply.text

    bg_raw = ("Arrests may rise in summer **because** people spend more time outdoors.\nTo "
              "check it, you would need records of arrests by season and by place. "
              "\U0001F914")
    bg_clean = ("Arrests may rise in summer because people spend more time outdoors. To check "
                "it, you would need records of arrests by season and by place.")
    assert tidied(bg_raw) == bg_clean
    env = on(tmp_path / "background", MOCO_BACKGROUND="on")
    reply = env.ask(Q_BACKGROUND, Step(finish("background", bg_raw)),
                    Step(finish("background", bg_raw)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "background", "agent"), (reply.status, reply.reply_style, reply.text)
    assert reply.text == BACKGROUND_PREFIX + bg_clean + BACKGROUND_SUFFIX


@pytest.mark.parametrize("kind", ["talk", "finding"])
def test_the_tidied_text_is_sent_and_saved_and_the_step_log_keeps_the_models_own(tmp_path,
                                                                                kind):
    """T10: "The tidied text is what is checked, what is sent and what is saved as the
    reply. The step log keeps what the model wrote, exactly." The turn record's reply and
    the turn stored in the thread (and shown to the model next time) hold the tidied text;
    the step log holds the model's own; the stored turn does not."""
    raw, clean = (TALK_TIDY if kind == "talk" else FINDING_TIDY)["together"]
    env = on(tmp_path)
    before = () if kind == "talk" else (Step(count(2025, "18_25")),)
    reply = env.ask("hello" if kind == "talk" else Q, *before, Step(finish(kind, raw)))
    assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
    sent = clean if kind == "talk" else None
    if sent is not None:
        assert reply.text == sent
    record = turn_json(reply, env.runs_dir)
    assert record["reply"] == reply.text
    steps = step_lists(record)
    assert steps and any(has_leaf(found, raw) for found in steps), "the step log lost the " \
                                                                   "model's own text"
    saved = saved_turn(env)
    assert has_leaf(saved, clean), saved
    assert not has_leaf(saved, raw), "the model's untidied text was stored with the turn"
    env.ask("thanks", Step(finish("talk", THANKS_TEXT)))
    block = thread_block(env.model.calls[0]["messages"])
    assert block is not None and clean in block and raw not in block, block


@pytest.mark.parametrize("kind", ["talk", "finding"])
def test_a_text_of_only_removed_characters_is_empty(tmp_path, kind):
    """T10: "A text that is empty after tidying fails SHAPE as an empty text does." It gets
    the second try; when that is empty too the turn falls back (talk: the fallback line,
    T14 does not cut an empty text; a finding: the fixed rendering)."""
    raw = "\U0001F44B✨ **" if kind == "talk" else "\U0001F44D **\n"
    assert tidied(raw) == ""
    env = on(tmp_path)
    before = () if kind == "talk" else (Step(count(2025, "18_25")),)
    reply, problems = first_try(env, "hello" if kind == "talk" else Q, kind, raw, *before)
    if kind == "talk":
        assert problems == ["SHAPE"], problems
        # Changed by briefs/S3-R21-A-tests.md (C57 point 6; SYNTHETIC: either line, see the top).
        assert_talked(reply, fallback_line_of(reply.text, county=False), style="fallback")
        not_cut(turn_json(reply, env.runs_dir))
    else:
        assert problems is not None and "SHAPE" in problems, problems   # SLOT may come too
        assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
        assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)


@pytest.mark.parametrize("kind", ["talk", "finding"])
def test_a_private_use_character_and_a_keycap_digit_still_fail(tmp_path, kind):
    """T10: a private-use character is not removed and still fails CHARS (C13); the `1` of a
    keycap is left behind and still fails NUMBER (the keycap's ring, U+20E3, is not a So
    character and stays, so CHARS may come with it); a digit drawn as a picture (KEYCAP
    TEN, So) is removed with the other pictures, and the rest passes."""
    if kind == "talk":
        cases = [("Hello  there!\U0001F44B", "CHARS"),
                 ("Ask me 1️⃣ more thing.", {"NUMBER"}),
                 ("We can do \U0001F51F more.", None)]
        for text, want in cases:
            premise_talk(text, want, synthetic_labels())
        check_cases(lambda i, text: first_try(on(tmp_path / str(i)), "hello", "talk", text),
                    cases, TALK_CODES)
    else:
        cases = [("I counted {r1.count}. Gladto help.\U0001F44B", "CHARS"),
                 ("I counted {r1.count}. Pick 1️⃣ more.", {"NUMBER"}),
                 ("I counted {r1.count}. Ask for \U0001F51F more.", None)]
        for text, want in cases:
            got = mixed_faults(text, synthetic_labels())
            if isinstance(want, set):
                assert want <= got, (text, got)
            else:
                assert got == ({want} if want else set()), (text, got)
        check_cases(lambda i, text: first_try(on(tmp_path / str(i)), Q, "finding", text,
                                              Step(count(2025, "18_25"))),
                    cases, FINDING_CODES)


@pytest.mark.parametrize("values", [{}, {"MOCO_TALK": "off"}], ids=["unset", "off"])
def test_with_talk_off_nothing_is_tidied(tmp_path, values):
    """T10 applies only with MOCO_TALK on. With it unset or off, a finding holding a line
    break fails R1's CHARS as today and gets the fixed rendering at once (no second try),
    and a background text holding one fails today's SHAPE and gets the fixed refusal. With
    it on, the same texts are tidied and sent."""
    finding = "I counted {r1.count}.\n{r1.months}."
    background = ("Arrests may rise in summer because people spend more time outdoors.\nTo "
                  "check it, you would need records of arrests by season.")
    assert odd_chars(finding) == ["\n"] and tidied(finding) == ONE_COUNT_TEXT
    off_dir = tmp_path / "off"
    off_dir.mkdir()
    assert make_settings(off_dir, **values).moco_talk == "off"
    off = Env(off_dir, MOCO_BACKGROUND="on", **values)
    reply = off.ask(Q, Step(count(2025, "18_25")), Step(finish("finding", finding)),
                    Step(finish("finding", ONE_COUNT_TEXT)), thread_key=thread(1))
    assert len(off.model.calls) == 2, "a second try was given with talk off"
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert "CHARS" in reply.draft_failures, reply.draft_failures
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    reply = off.ask(Q_BACKGROUND, Step(finish("background", background)), thread_key=thread(2))
    assert reply.reply_style == "fallback", (reply.status, reply.reply_style, reply.text)
    assert_fixed(reply.text, "BACKGROUND_OFF")

    talk_on = on(tmp_path / "on", MOCO_BACKGROUND="on")
    reply = talk_on.ask(Q, Step(count(2025, "18_25")), Step(finish("finding", finding)),
                        thread_key=thread(1))
    assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
    assert_answered(reply.text, re.escape(one_count_line(2025, "18_25")), first=True)
    reply = talk_on.ask(Q_BACKGROUND, Step(finish("background", background)),
                        thread_key=thread(2))
    assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
    assert reply.text == BACKGROUND_PREFIX + tidied(background) + BACKGROUND_SUFFIX


# ==== T11: more marks in a talk sentence ==========================================================

TALK_WITH = {
    '"': 'Sure, "hello" to you too!',
    "“": "You wrote “hello and I wave back.",
    "”": "Hello there” is what I heard.",
    "–": "Hi there – how can I help?",
    "—": "Hi there — how can I help?",
    "…": "Hmm… let me think about that.",
}
FINDING_TALK_WITH = {
    '"': 'Say "compare" for another year.',
    "“": "Say “compare for another year.",
    "”": "Say compare” for another year.",
    "–": "Glad to help – ask again any time.",
    "—": "Glad to help — ask again any time.",
    "…": "Glad to help… ask again any time.",
}
R1_DASHES = ("–", "—")   # R1's characters already hold them (READING above)
MARK_IDS = ["straight quote", "left quote", "right quote", "en dash", "em dash", "ellipsis"]


def test_the_new_marks_are_these_six():
    """T11 as the brief writes it: `"`, U+201C, U+201D, U+2013, U+2014 and U+2026."""
    assert NEW_MARKS == ('"', "“", "”", "–", "—", "…")
    assert sorted(TALK_WITH) == sorted(FINDING_TALK_WITH) == sorted(NEW_MARKS)
    assert round2_rules()


@pytest.mark.parametrize("mark", NEW_MARKS, ids=MARK_IDS)
def test_each_new_mark(tmp_path, mark):
    """T11: the mark passes in a talk text (sent as it is) and in a talk sentence of a
    finding (sent filled); in a fact sentence R1's characters still apply: a quotation mark
    or the ellipsis fails CHARS there (and `found` holds the mark), a dash passes as
    today."""
    talk, said = TALK_WITH[mark], FINDING_TALK_WITH[mark]
    assert mark in talk and mark in said
    premise_talk(talk, None, synthetic_labels())
    env = on(tmp_path)
    reply = env.ask("hello", Step(finish("talk", talk)), Step(finish("talk", talk)),
                    thread_key=thread(1))
    assert len(env.model.calls) == 1, "the mark did not pass in a talk text"
    assert_talked(reply, talk)

    text = f"I counted {{r1.count}}. {{r1.months}}. {said}"
    assert mixed_faults(text) == set() and split_sentences(text)[1] == [said]
    reply = env.ask(Q, Step(count(2025, "18_25")), Step(finish("finding", text)),
                    Step(finish("finding", text)), thread_key=thread(2))
    assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
    assert_answered(reply.text, re.escape(fill_expect(text, LINE1)), first=True)

    fact = f"I counted {mark} {{r1.count}}. {{r1.months}}."
    if mark in R1_DASHES:
        assert odd_chars(fact) == []
        reply = env.ask(Q, Step(count(2025, "18_25")), Step(finish("finding", fact)),
                        thread_key=thread(3))
        assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
        assert_answered(reply.text, re.escape(fill_expect(fact, LINE1)), first=True)
    else:
        assert odd_chars(fact) == [mark]
        reply, problems = first_try(env, Q, "finding", fact, Step(count(2025, "18_25")),
                                    thread_key=thread(3))
        assert problems == ["CHARS"], problems
        assert mark in env.model.answer(1)["found"], env.model.answer(1)


def test_the_new_marks_in_a_county_finding(tmp_path, monkeypatch):
    """T11 in county mode: each new mark passes in a talk sentence of a finding; in a fact
    sentence a quotation mark or the ellipsis fails CHARS and a dash passes (R1)."""
    env = county_on(tmp_path, monkeypatch)
    before = (Step(county_count(A_ID, year(2025))),)
    wrong = []
    for i, mark in enumerate(NEW_MARKS):
        said = FINDING_TALK_WITH[mark]
        reply = env.ask(Q_COUNT, *before, Step(finish("finding", f"I counted {{r1.count}}. {said}")),
                        thread_key=thread(10 + i))
        if reply.reply_style != "agent" or not reply.text.startswith(f"{COUNTY_LINE1} {said}\n"):
            wrong.append(f"{mark!r} in a talk sentence: {reply.reply_style} {reply.text!r}")
        fact = f"I counted {mark} {{r1.count}}."
        reply, problems = first_try(env, Q_COUNT, "finding", fact, *before,
                                    thread_key=thread(20 + i))
        want = None if mark in R1_DASHES else ["CHARS"]
        if problems != want:
            wrong.append(f"{mark!r} in a fact sentence: {problems}, want {want}")
    assert not wrong, "\n".join(wrong)


# ==== T12: longer talk ==============================================================================

SIX = "Hi there. How are you? I am well! Ask me anything. I count records. I can compare them."
SEVEN = SIX + " Have a nice day."


def test_six_sentences_pass_and_seven_fail(tmp_path):
    """T12: most_talk_sentences_in_talk is 6 (was 4): six pass, seven fail SHAPE."""
    assert (len(sentences(SIX)), len(sentences(SEVEN))) == (MOST_TALK_SENTENCES,
                                                            MOST_TALK_SENTENCES + 1) == (6, 7)
    premise_talk(SIX, None)
    premise_talk(SEVEN, "SHAPE")
    env = on(tmp_path)
    check_cases(lambda i, text: first_try(env, "hello", "talk", text, thread_key=thread(i)),
                [(SIX, None), (SEVEN, "SHAPE")], TALK_CODES)


def test_700_characters_pass_and_701_fail(tmp_path):
    """T12: most_chars_talk is 700 (was 500): 700 characters pass, 701 fail SHAPE."""
    at = padded("Hello there! ", "", 700)
    over = padded("Hello there! ", "", 701)
    assert (len(at), len(over)) == (MOST_CHARS_TALK, MOST_CHARS_TALK + 1) == (700, 701)
    premise_talk(at, None)
    premise_talk(over, "SHAPE")
    env = on(tmp_path)
    check_cases(lambda i, text: first_try(env, "hello", "talk", text, thread_key=thread(i)),
                [(at, None), (over, "SHAPE")], TALK_CODES)


def test_the_limits_are_measured_on_the_tidied_text(tmp_path):
    """T10 with T12: a text of more than 700 characters as written but 700 once tidied
    passes and is sent tidied."""
    at = padded("Hello there! ", "", 700)
    raw = at.replace("Hello there! ", "Hello there!\U0001F44B\n\n  ", 1)
    assert len(raw) > 700 and tidied(raw) == at
    env = on(tmp_path)
    reply = env.ask("hello", Step(finish("talk", raw)), Step(finish("talk", raw)))
    assert len(env.model.calls) == 1
    assert_talked(reply, at)


def test_the_finding_limits_do_not_change(tmp_path):
    """T12: "The two limits for a finding do not change": two talk sentences pass and three
    fail SHAPE; 700 characters once filled pass and 701 fail."""
    rules = round2_rules()
    assert (rules["most_talk_sentences_in_finding"], rules["most_chars_finding"]) == (2, 700)

    def filled(text):
        return len(fill_expect(text, LINE1))

    cases = [("Here you go. I counted {r1.count}. {r1.months}. Want more?", None),
             ("Here you go. Hope it helps. I counted {r1.count}. Want more?", "SHAPE"),
             (padded("I counted {r1.count}. {r1.months}. ", "", 700, measure=filled), None),
             (padded("I counted {r1.count}. {r1.months}. ", "", 701, measure=filled), "SHAPE")]
    for text, _ in cases:
        assert mixed_faults(text) == set(), text
    env = on(tmp_path)
    check_cases(lambda i, text: first_try(env, Q, "finding", text, Step(count(2025, "18_25")),
                                          thread_key=thread(i)),
                cases, FINDING_CODES)


# ==== T13: a plain-text reply gets its second try too ===================================================

# kind: (question, steps before, a failing plain text holding a line break, its codes, its
#        found, a second failing text, its codes, a passing text)
PLAIN = {
    "talk": ("hello", (), "Sure!\nI can look at two years for you.", ["NUMBER"], ["two"],
             "It went up because of summer.", ["CLAIM"], HELLO_TEXT),
    "finding": (Q, (Step(count(2025, "18_25")),), "I counted {r1.count}.\nThat is a lot.",
                ["JUDGE"], ["a lot"], "I counted {r1.count}. It went up because of summer.",
                ["CLAIM"], ONE_COUNT_TEXT),
    "about_data": (Q_ABOUT, (Step(describe()),), f"Here is what I know, in two parts.\n{{f{A}}}.",
                   ["NUMBER"], ["two"], f"Sadly, {{f{A}}}.", ["WORD"], about_text(A)),
}


def assert_sent(reply, kind, text):
    """The reply of a text that passed (T1, T2 with R1)."""
    assert reply.reply_style == "agent", (reply.status, reply.reply_style, reply.text)
    if kind == "talk":
        assert_talked(reply, text)
    elif kind == "finding":
        assert (reply.status, reply.reply_kind) == ("ANSWERED", "finding")
        assert_answered(reply.text, re.escape(one_count_line(2025, "18_25")), first=True)
    else:
        assert (reply.status, reply.reply_kind) == ("EXPLAINED", "about_data")
        filled = fill_expect(text, fact_slots())
        assert re.fullmatch(re.escape(filled) + "[ \n]" + re.escape(DATA_TAG), reply.text)


def assert_fell_back(reply, kind):
    """T3's ends: the fallback line, the fixed rendering, the fixed ABOUT text."""
    assert reply.reply_style == "fallback", (reply.status, reply.reply_style, reply.text)
    if kind == "talk":  # changed by briefs/S3-R21-A-tests.md (C57 point 6; SYNTHETIC)
        assert_talked(reply, fallback_line_of(reply.text, county=False), style="fallback")
    elif kind == "finding":
        assert reply.status == "ANSWERED"
        assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    else:
        assert reply.status == "EXPLAINED"
        assert_fixed(reply.text, "ABOUT")


def added_messages(model, step):
    """What the call after `step` was given beyond what `step` was given."""
    seen, then = model.calls[step]["messages"], model.calls[step + 1]["messages"]
    assert then[:len(seen)] == seen, "the messages the model had seen were changed"
    return then[len(seen):]


def assert_note(added, text, codes, found):
    """T13: exactly two messages: the model's text exactly as it wrote it, and the note with
    T3's REWRITE object."""
    assert len(added) == 2, added
    assert added[0] == {"role": "assistant", "content": text}, added[0]
    assert set(added[1]) == {"role", "content"} and added[1]["role"] == "user", added[1]
    content = added[1]["content"]
    assert content.startswith(NOTE_HEAD), content
    rewrite = json.loads(content[len(NOTE_HEAD):])
    assert rewrite == {"error": "REWRITE", "problems": codes, "found": found,
                       "do": HINTS[codes[0]]}, rewrite


@pytest.mark.parametrize("kind", list(PLAIN))
def test_a_failing_plain_text_gets_the_two_messages_exactly(tmp_path, kind):
    """T13: the model's text, exactly as written (not tidied), as an assistant message, then
    `PROGRAM NOTE (not from the person). Your reply was not sent. ` + the REWRITE object;
    nothing else is added, and the turn goes on to the second try. Changed by
    briefs/S3-R28-A-tests.md (C64 point 1): the talk and about_data cases fail NUMBER, whose hint
    in tsupport.HINTS (read by assert_note) is C64's (it was the first two sentences alone), in
    SYNTHETIC mode too; the lines are unchanged."""
    question, before, bad, codes, found, _, _, good = PLAIN[kind]
    assert "\n" in bad
    n = len(before)
    env = on(tmp_path)
    reply = env.ask(question, *before, Step(text=bad), Step(finish(kind, good)))
    assert len(env.model.calls) == n + 2, "the plain text got no second try"
    assert_note(added_messages(env.model, n), bad, codes, found)
    assert_sent(reply, kind, good)


@pytest.mark.parametrize("how", ["finish", "plain text"])
@pytest.mark.parametrize("kind", list(PLAIN))
def test_a_passing_second_try_is_sent_with_style_agent(tmp_path, kind, how):
    """T13: the model's next step is its second try, "whether it calls finish or writes
    plain text again"; a passing one is sent, style agent; the turn record keeps the first
    try's codes and no failure of the second."""
    question, before, bad, codes, _, _, _, good = PLAIN[kind]
    second = Step(finish(kind, good)) if how == "finish" else Step(text=good)
    env = on(tmp_path)
    reply = env.ask(question, *before, Step(text=bad), second)
    assert len(env.model.calls) == len(before) + 2
    assert_sent(reply, kind, good)
    record = turn_json(reply, env.runs_dir)
    assert list(record["first_failures"]) == codes, record.get("first_failures")
    assert list(record["failures"]) == [], record.get("failures")


@pytest.mark.parametrize("kind", list(PLAIN))
def test_a_failing_second_try_falls_back_and_there_is_never_a_third(tmp_path, kind):
    """T13 with T3: a second try that fails (here plain text again) ends the turn with the
    same fallback; no third try though a passing text would follow; both tries' codes are
    saved; none of the model's words are sent."""
    question, before, bad, codes, _, worse, worse_codes, good = PLAIN[kind]
    n = len(before)
    env = on(tmp_path)
    reply = env.ask(question, *before, Step(text=bad), Step(text=worse),
                    Step(finish(kind, good)), Step(text=good))
    assert len(env.model.calls) == n + 2, "a third try was asked for"
    assert_fell_back(reply, kind)
    assert "summer" not in reply.text and "Sadly" not in reply.text
    record = turn_json(reply, env.runs_dir)
    assert list(record["first_failures"]) == codes, record.get("first_failures")
    assert list(record["failures"]) == worse_codes, record.get("failures")


@pytest.mark.parametrize("kind", list(PLAIN))
def test_no_second_try_without_a_step_or_five_seconds_left(tmp_path, kind):
    """T13 on T3's conditions. The failing plain text in the last step allowed gets no note
    and falls back at once; one step more and it gets its second try. With
    MOCO_TURN_SECONDS 15, the plain text read with 4 or 3 seconds left falls back at once;
    read with exactly 5 left it gets its second try."""
    question, before, bad, _, _, _, _, good = PLAIN[kind]
    n = len(before)
    steps = (*before, Step(text=bad), Step(text=good))

    last = on(tmp_path / "last", MOCO_MAX_STEPS=n + 1)
    reply = last.ask(question, *steps)
    assert len(last.model.calls) == n + 1
    assert_fell_back(reply, kind)
    spare = on(tmp_path / "spare", MOCO_MAX_STEPS=n + 2)
    reply = spare.ask(question, *steps)
    assert len(spare.model.calls) == n + 2
    assert_sent(reply, kind, good)

    done = n + 1
    five_left = 10 / done
    four_left = 11 / done if kind == "talk" else 6.0   # 4 and 3 seconds left
    tight = on(tmp_path / "tight", MOCO_TURN_SECONDS=15)
    reply = tight.ask(question, *steps, seconds=four_left)
    assert len(tight.model.calls) == n + 1
    assert_fell_back(reply, kind)
    enough = on(tmp_path / "enough", MOCO_TURN_SECONDS=15)
    reply = enough.ask(question, *steps, seconds=five_left)
    assert len(enough.model.calls) == n + 2
    assert_sent(reply, kind, good)


def test_a_county_finding_in_plain_text_gets_its_second_try(tmp_path, monkeypatch):
    """T13 for a finding in county mode: the two messages exactly, then a passing second
    try in plain text is sent filled."""
    bad = "I counted {r1.count}.\nThat is a lot."
    good = "Here you go. I counted {r1.count}."
    env = county_on(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(county_count(A_ID, year(2025))), Step(text=bad),
                    Step(text=good))
    assert len(env.model.calls) == 3
    assert_note(added_messages(env.model, 1), bad, ["JUDGE"], ["a lot"])
    county_finding_reply(reply, "Here you go. " + COUNTY_LINE1)


# ==== T14: a talk text that is only too long is cut ==================================================

def sentence(length):
    """One talk sentence of letters only, exactly `length` characters long."""
    text = "S" + "o" * (length - len("S glad to help.")) + " glad to help."
    assert len(text) == length and len(sentences(text)) == 1
    return text


@pytest.mark.parametrize("how", ["finish", "plain text"])
def test_seven_short_sentences_are_cut_to_six(tmp_path, how):
    """T14: the text that ends a talk turn fails SHAPE and no other code: the six leading
    sentences are sent (TALKED, kind talk, style agent); the turn record keeps failures
    ["SHAPE"] and gets "cut": true; the turn stored in the thread holds the text sent. Both
    tries are the seven sentences, as a finish call or as plain text (T13)."""
    premise_talk(SEVEN, "SHAPE")
    premise_talk(SIX, None)
    step = Step(finish("talk", SEVEN)) if how == "finish" else Step(text=SEVEN)
    env = on(tmp_path)
    reply = env.ask("tell me about yourself", step, step, Step(finish("talk", HELLO_TEXT)))
    assert len(env.model.calls) == 2, "no second try, or a third"
    assert_talked(reply, SIX)
    record = turn_json(reply, env.runs_dir)
    assert list(record["failures"]) == ["SHAPE"], record.get("failures")
    assert record.get("cut") is True, record.get("cut")
    saved = saved_turn(env)
    assert has_leaf(saved, SIX) and not has_leaf(saved, SEVEN), saved


def test_a_too_long_text_with_no_second_try_left_is_cut(tmp_path):
    """T14: "after the second try, or with none left": the seven sentences in the last step
    allowed are cut at once."""
    env = on(tmp_path, MOCO_MAX_STEPS=1)
    reply = env.ask("tell me about yourself", Step(finish("talk", SEVEN)))
    assert len(env.model.calls) == 1
    assert_talked(reply, SIX)
    record = turn_json(reply, env.runs_dir)
    assert list(record["failures"]) == ["SHAPE"] and record.get("cut") is True, record


def test_a_text_over_700_characters_is_cut_at_a_sentence_end(tmp_path):
    """T14: as many whole sentences from the start as fit within both limits (6 sentences,
    700 characters), joined by one space: five sentences of 150 characters are cut to
    four; four sentences making exactly 700 and a fifth are cut to the four; a first
    sentence of exactly 700 and a second are cut to the first; seven sentences of 130
    characters are cut to five (six would be 785 characters)."""
    s150, s130 = sentence(150), sentence(130)
    four_700 = " ".join([sentence(175), sentence(175), sentence(175), sentence(172)])
    cases = [(" ".join([s150] * 5), " ".join([s150] * 4)),
             (four_700 + " Thanks.", four_700),
             (sentence(700) + " Thanks.", sentence(700)),
             (" ".join([s130] * 7), " ".join([s130] * 5))]
    assert len(four_700) == 700 and len(" ".join([s130] * 6)) == 785
    for text, cut in cases:
        premise_talk(text, "SHAPE")
        premise_talk(cut, None)
    env = on(tmp_path)
    wrong = []
    for i, (text, cut) in enumerate(cases):
        reply = env.ask("hello", Step(finish("talk", text)), Step(finish("talk", text)),
                        thread_key=thread(i))
        record = turn_json(reply, env.runs_dir)
        if (reply.status, reply.reply_kind, reply.reply_style, reply.text) != \
                ("TALKED", "talk", "agent", cut) or record.get("cut") is not True:
            wrong.append(f"case {i}: {reply.reply_style}, cut={record.get('cut')}, "
                         f"{len(reply.text)} characters sent, want {len(cut)}")
    assert not wrong, "\n".join(wrong)


def test_one_sentence_over_700_characters_gets_the_fallback_line(tmp_path):
    """T14: "If the first sentence alone is over most_chars_talk, the fallback line as
    today": a first sentence of 701 characters, alone and with a short one after it."""
    cases = [sentence(701), sentence(701) + " Thanks."]
    for text in cases:
        premise_talk(text, "SHAPE")
    env = on(tmp_path)
    for i, text in enumerate(cases):
        reply = env.ask("hello", Step(finish("talk", text)), Step(finish("talk", text)),
                        thread_key=thread(i))
        # Changed by briefs/S3-R21-A-tests.md (C57 point 6; SYNTHETIC: either line).
        assert_talked(reply, fallback_line_of(reply.text, county=False), style="fallback")
        not_cut(turn_json(reply, env.runs_dir))


def test_shape_with_any_other_code_is_not_cut(tmp_path):
    """T14: "fails SHAPE and no other code": seven sentences of which one also fails NUMBER,
    CLAIM, CHARS or LABEL get the fallback line, not cut."""
    cases = {"NUMBER": SIX + " I can look at two years.",
             "CLAIM": SIX + " In fact, I can help.",
             "CHARS": SIX + " Write to me @ any time.",
             "LABEL": SIX + " Ask about people under 18."}   # a wording holds digits: NUMBER too
    env = on(tmp_path)
    wrong = []
    for i, (code, text) in enumerate(cases.items()):
        premise_talk(text, {code, "SHAPE"}, synthetic_labels())
        reply, problems = first_try(env, "hello", "talk", text, thread_key=thread(i))
        if problems is None or not {code, "SHAPE"} <= set(problems):
            wrong.append(f"{code}: the first try gave {problems}")
        # Changed by briefs/S3-R21-A-tests.md (C57 point 6; SYNTHETIC: either line).
        if reply.reply_style != "fallback" or reply.text not in fallback_lines(county=False):
            wrong.append(f"{code}: {reply.reply_style} {reply.text!r}")
        if turn_json(reply, env.runs_dir).get("cut") not in (None, False):
            wrong.append(f"{code}: saved as cut")
    assert not wrong, "\n".join(wrong)


BG_SIX = ("Arrests may rise in summer because people spend more time outdoors. To check it, "
          "you would need records of arrests by season. It might not hold everywhere. Places "
          "can vary. Seasons can vary too. Weather could matter as well.")
NOT_CUT = {
    "finding": (Q, (Step(count(2025, "18_25")),),
                "Here you go. Hope it helps. I counted {r1.count}. Want more?"),
    "about_data": (Q_ABOUT, (Step(describe()),),
                   f"Here is what I know. Hope it helps. {{f{A}}}. Ask again."),
    "background": (Q_BACKGROUND, (), BG_SIX),
}


@pytest.mark.parametrize("kind", list(NOT_CUT))
def test_nothing_is_cut_in_a_finding_about_data_or_background(tmp_path, kind):
    """T14: "Nothing is cut in a finding, an about_data text or a background text": a text
    that fails SHAPE alone, twice, ends as T3 says (the fixed rendering, the fixed ABOUT
    text, the fixed refusal), and none of its sentences is sent."""
    question, before, text = NOT_CUT[kind]
    if kind == "background":
        assert len(sentences(text)) == 6   # today's background limit is 5 sentences
    else:
        assert mixed_faults(text) == set() and len(split_sentences(text)[1]) == 3
    env = on(tmp_path, MOCO_BACKGROUND="on")
    reply, problems = first_try(env, question, kind, text, *before)
    assert problems == ["SHAPE"], problems
    assert reply.reply_style == "fallback", (reply.status, reply.reply_style, reply.text)
    if kind == "finding":
        assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    elif kind == "about_data":
        assert_fixed(reply.text, "ABOUT")
    else:
        assert_fixed(reply.text, "BACKGROUND_OFF")
    assert "Hope it helps" not in reply.text and "Weather" not in reply.text
    not_cut(turn_json(reply, env.runs_dir))


def test_nothing_is_cut_in_a_county_finding(tmp_path, monkeypatch):
    """T14 in county mode: a finding with three talk sentences, twice, gets the fixed
    rendering; none of its sentences is sent."""
    text = "Here you go. Hope it helps. I counted {r1.count}. Want more?"
    env = county_on(tmp_path, monkeypatch)
    reply, problems = first_try(env, Q_COUNT, "finding", text,
                                Step(county_count(A_ID, year(2025))))
    assert problems == ["SHAPE"], problems
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert "Hope it helps" not in reply.text and "Want more" not in reply.text
    not_cut(turn_json(reply, env.runs_dir))


NUMBER_TEXT = "I can look at two years for you."
ONLY_THE_END = {
    "too long, then passing": (SEVEN, HELLO_TEXT, HELLO_TEXT, "agent", ["SHAPE"], []),
    "too long, then NUMBER": (SEVEN, NUMBER_TEXT, None, "fallback", ["SHAPE"],  # None: the
                              # fallback line (changed by briefs/S3-R21-A-tests.md, C57 point 6)
                              ["NUMBER"]),
    "NUMBER, then too long": (NUMBER_TEXT, SEVEN, SIX, "agent", ["NUMBER"], ["SHAPE"]),
}


@pytest.mark.parametrize("case", list(ONLY_THE_END))
def test_only_the_text_that_ends_the_turn_is_cut(tmp_path, case):
    """T14: "the text that ends a talk turn (after the second try, or with none left)": a
    first text that is only too long gets T3's REWRITE, not a cut; a second text that
    fails another code gets the fallback line; a second text that is only too long is
    cut, whatever the first failed."""
    first, second, sent, style, first_codes, codes = ONLY_THE_END[case]
    env = on(tmp_path)
    reply = env.ask("hello", Step(finish("talk", first)), Step(finish("talk", second)),
                    Step(finish("talk", HELLO_TEXT)))
    assert len(env.model.calls) == 2
    assert env.model.answer(0)["problems"] == first_codes, env.model.answer(0)
    if sent is None:  # changed by briefs/S3-R21-A-tests.md (C57 point 6; SYNTHETIC: either line)
        sent = fallback_line_of(reply.text, county=False)
    assert_talked(reply, sent, style=style)
    record = turn_json(reply, env.runs_dir)
    assert list(record["first_failures"]) == first_codes, record.get("first_failures")
    assert list(record["failures"]) == codes, record.get("failures")
    if sent == SIX:
        assert record.get("cut") is True, record.get("cut")
    else:
        not_cut(record)


# ==== no figure through talk, after tidying (brief step 5) =============================================

AFTER_TIDYING = [
    # (mode, the model's text, a code it must fail with once tidied, what must not be sent)
    ("synthetic", "I counted 4‍321 of them.", "NUMBER", "4321"),
    ("synthetic", "I counted 2 025 records.", "NUMBER", "2025"),
    ("synthetic", "Pick 1️⃣ more.", "NUMBER", "1"),
    ("synthetic", "There were t*w*o of them.", "NUMBER", "two"),
    ("synthetic", "There were twelve\nhundred of them.", "NUMBER", "twelve"),
    ("synthetic", "There were thou`sands of them.", "NUMBER", "thousands"),
    ("synthetic", "Most of them came in Ma`rch.", "NUMBER", "march"),
    ("synthetic", "Most of them came in Ju‍ly.", "NUMBER", "july"),
    ("synthetic", "Most of them came in \U0001F338Oct\U0001F338.", "NUMBER", "oct"),
    ("synthetic", "Ask me about ages 18 to 25.", "LABEL", "18"),
    ("county", "Most of them were His*panic.", "LABEL", "hispanic"),
    ("county", "Most of them were group \U0001F44BGamma.", "LABEL", "gamma"),
    ("county", "Ask me about fe‍male records.", "LABEL", "female"),
    ("county", "Most of them were in district\n3.", "LABEL", "district"),
    ("county", "Most of them came in Ma**y and Ju‍ne.", "NUMBER", "june"),
]


def test_no_figure_reaches_a_talk_reply_after_tidying(tmp_path, monkeypatch):
    """T15's last point and the brief's step 5: after tidying, a talk text still fails if
    it holds a digit, a number word, a month name, or a label of the county fixture source,
    including when tidying is what puts the figure together (a removed mark or joiner inside
    a word, a no-break space inside a label). Each text, sent twice, gets REWRITE with that
    code, then the fallback line; nothing of the figure is sent, and no digit at all. Changed by
    briefs/S3-R28-A-tests.md (C64 point 1): a county text that fails NUMBER (by this test's own
    reading of its text, tsupport.talk_faults: the month names, and the digit of "district 3")
    ends on C64's line (s3support.C64_TALK_LINE); one that fails without NUMBER on C61's county
    line, as before. The figure is looked for outside either line, as before."""
    envs = {"synthetic": on(tmp_path / "synthetic"),
            "county": county_on(tmp_path / "county", monkeypatch)}
    labels = {"synthetic": synthetic_labels(), "county": county_labels("arrests_like")}
    wrong = []
    for i, (mode, text, code, figure) in enumerate(AFTER_TIDYING):
        assert code in talk_faults(text, labels[mode]), (text, talk_faults(text, labels[mode]))
        env = envs[mode]
        reply, problems = first_try(env, "hello", "talk", text, thread_key=thread(i))
        if problems is None or code not in problems:
            wrong.append(f"{text!r} ({mode}): the first try gave {problems}, want {code}")
        # Changed by briefs/S3-R21-A-tests.md (C57 point 6): C57's line in county mode, either
        # line in SYNTHETIC mode (s3support.fallback_lines).
        # Changed by briefs/S3-R23-A-tests.md (C61 point 9): C61's line in county mode.
        # Changed by briefs/S3-R28-A-tests.md (C64 point 1): C64's line when the text fails NUMBER.
        number = "NUMBER" in talk_faults(text, labels[mode])
        lines = ((C64_TALK_LINE if number else county_fallback_line(1)),) if mode == "county" \
            else fallback_lines(county=False)
        if (reply.status, reply.reply_style) != ("TALKED", "fallback") or \
                reply.text not in lines:
            wrong.append(f"{text!r} ({mode}): sent {reply.reply_style} {reply.text!r}")
        # Changed by briefs/S3-R23-A-tests.md: C61's county line names the fields it can break
        # down by ("district" among them), so the figure is looked for outside that line.
        # briefs/S3-R28-A-tests.md: and outside C64's line.
        rest = reply.text.replace(county_fallback_line(1), "").replace(C64_TALK_LINE, "") \
            if mode == "county" else reply.text
        if figure in rest.lower() or re.search(r"\d", reply.text):
            wrong.append(f"{text!r} ({mode}): {figure!r} or a digit was sent")
        check_no_model_text(reply.text)
    assert not wrong, "\n".join(wrong)
