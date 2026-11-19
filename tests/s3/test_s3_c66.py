"""C66 of docs/S3A-DESIGN.md (D-081): three small wordings from the live check of 18 November. Brief:
briefs/S3-R30-A-tests.md (step 6). Tests only; red until the planning chat builds C66, except those
that pin what stays (named in their docstrings and in kit-log/raw/S3-R30-A-notes.txt). County mode
only; wording only.

Everything is SYNTHETIC: the fixtures of tests/s3 (arrests_like) and the model stand-in
(tests/p1/p1support.py's FakeModel). No figure of a real county source is used or quoted.

What is here:
1. "I've noted it as a request." once: a decline whose own text already holds the words, under each
   of the three codes whose row has the sentence (straight and curly apostrophe, capitals); a text
   without them; NEEDS_other and a row without the sentence unchanged.
2. The two prompt sentences: word for word, once, in place; in that prompt only; sent with talk on
   and not with talk off; the prompt hash tests take them out.
3. "age_rule": a single year asked outright that ends as a question back, a count refused by C21's
   check beside one that is made, a statistic refused by C65's, a plain refusal: each stores the key
   and the next turn's thread block holds the words once for that turn; no refused count, TOO_FINE
   and a SYNTHETIC-mode turn do not; after `reset` nothing of it is shown and the stripped records
   hold no such key. And this session's own (see each test).

Readings (also in the notes; the open ones in briefs/QUESTIONS.md):
- C66-1. Point 1, "holds the words": the lead, with each curly apostrophe (U+2019) read as a straight
  one and capitals not counting, holds `noted it as a request` anywhere in it. The reply is then the
  lead, one space, and the row's rest without NOTED (the can-ask sentence), word for word.
- C66-2. Point 1's "the three codes whose row has it": UNSUPPORTED_METRIC, UNSUPPORTED_FIELD and
  REAL_DATA_NOT_AVAILABLE (replies.county_text's rows with NOTED); the turns are C41's declines with
  a text (talk on), each text first checked to pass T1 (tests/t/tsupport.py's premise_talk).
- C66-3. Point 3's key is stored as `"age_rule": true` in the turn's memory record (read back with
  Store.recent_turns); a turn without it has no such key (not false).
- C66-4. Point 3's words in the thread block: the turn's "You:" line is what he did, then
  s3support.C66_NOTE, then ` and said: "..."` when the turn has a reply text; with no reply text the
  line ends with the note. "Once for that turn": the note is in that turn's line once, and in the
  block as many times as turns with the key are shown.
- C66-5. "Refused with NOT_ALLOWED": a count or a statistic answered NOT_ALLOWED by C5 (one year
  asked outright, C35's range in its `why`), by C21's check or by C65's. NOT_ALLOWED for age bands of
  the model's own ("age bands are the source's own") is not about single years: not tested
  (briefs/QUESTIONS.md, S3-R30-A question 2).
- C66-6. "After `reset` nothing of it is shown": the model's thread block is empty (None) after
  `reset`, and no stripped record (Store.given_before_reset) holds "age_rule" anywhere.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

import p1support as p1
from p1support import NOTED, THREAD_1, Step, call, decline, finish, mod, thread_block
from s3support import (C41_PROMPT_LINE, C66_NOTE, C66_PROMPT_SENTENCES, CountyEnv, age,
                       without_c66)
from test_s3_c41 import (CAN_ASK, DECLINED, FIRST, PROMPTS, RULE_10_TALK, ask_with, decline_with,
                         env_of, labels_of)
from test_s3_c54 import call_of
from test_s3_c65 import A10_16, Talk, analyze, given, plain, slack_env
from test_s3_c61d import assert_refused
from test_s3_round5 import U17, U18, WHY, Y25, spec

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import premise_talk  # noqa: E402

NOTED_CODES = ("UNSUPPORTED_METRIC", "UNSUPPORTED_FIELD", "REAL_DATA_NOT_AVAILABLE")
SAY = "I can't do that one, since my records hold nothing on it."
NOTED_TEXTS = {
    "straight apostrophe": f"{SAY} I've noted it as a request.",
    "curly apostrophe": f"{SAY} I’ve noted it as a request.",
    "capitals": f"{SAY} I've Noted It As A Request.",
    "the words in the middle": "I've noted it as a request, though my records hold nothing on it.",
}
WITHOUT = f"{SAY} Is there something else I can count?"
C66_SENTENCES = (
    "When a tool answered NOT_ALLOWED, the reason is a rule of this project: say that it is a rule, "
    "and never say that the records or the data cannot do it.",
    "When THREAD SO FAR says that a count was refused under that rule and someone asks why, call "
    "describe_data and answer with its fact about the rule: never call it your mistake, and never "
    "offer to count it after all.",
)
LINE = f"{C41_PROMPT_LINE} {C66_PROMPT_SENTENCES}"


def test_premise_the_sentences_and_texts():
    assert " ".join(C66_SENTENCES) == C66_PROMPT_SENTENCES
    for text in [*NOTED_TEXTS.values(), WITHOUT]:
        premise_talk(text, None, labels_of(1))


# ==== point 1: "I've noted it as a request." once ===================================================

@pytest.mark.parametrize("which", list(NOTED_TEXTS))
@pytest.mark.parametrize("code", NOTED_CODES)
def test_p1_a_decline_whose_text_holds_the_words_has_them_once(tmp_path, monkeypatch, code, which):
    """C66's test, point 1: the decline's text in place of the row's first sentence, then the
    can-ask sentence; the row's NOTED is left out (C66-1). Style agent, as C41."""
    text = NOTED_TEXTS[which]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, text)))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), reply.text
    assert reply.text == f"{text} {CAN_ASK[1]}", reply.text
    assert reply.text.lower().replace("’", "'").count("noted it as a request") == 1
    assert reply.reply_style == "agent", reply.reply_style


@pytest.mark.parametrize("code", NOTED_CODES)
def test_p1_a_text_without_the_words_keeps_the_rows_sentence(tmp_path, monkeypatch, code):
    """C66's test, point 1: a text without the words: the row's sentence as today (C41). Passes
    today; must still pass."""
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED[code], Step(decline_with(code, WITHOUT)))
    assert reply.text == f"{WITHOUT} {NOTED} {CAN_ASK[1]}", reply.text


@pytest.mark.parametrize("code", NOTED_CODES)
def test_p1_no_text_gives_the_whole_row(tmp_path, monkeypatch, code):
    """No text (talk off): the whole row, NOTED in it, as today. Passes today; must still pass."""
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK="off")
    reply = env.ask(DECLINED[code], Step(decline(code)))
    assert reply.text == f"{FIRST[code]} {NOTED} {CAN_ASK[1]}", reply.text


def test_p1_a_row_without_the_sentence_is_unchanged(tmp_path, monkeypatch):
    """C66's test, point 1: UNRECOGNIZED_QUESTION's row has no NOTED: a text that holds the words
    gives the text and the can-ask sentence, as today. Passes today; must still pass."""
    text = NOTED_TEXTS["straight apostrophe"]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNRECOGNIZED_QUESTION"],
                    Step(decline_with("UNRECOGNIZED_QUESTION", text)))
    assert reply.text == f"{text} {CAN_ASK[1]}", reply.text


def test_p1_needs_other_is_unchanged(tmp_path, monkeypatch):
    """C66's test, point 1: an ask_user (other) whose text holds the words is his text alone, as
    C43 point 3 has it today. Passes today; must still pass."""
    text = "I've noted it as a request. What would you like me to count?"
    premise_talk(text, None, labels_of(1))
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask("Can you count that for me?", Step(ask_with("other", text)))
    assert (reply.status, reply.text) == ("NEEDS_INPUT", text), (reply.status, reply.text)


def test_p1_own_other_words_with_noted_keep_the_sentence(tmp_path, monkeypatch):
    """This session's own: "noted" without the words (I've noted your question) is not the words:
    the row's NOTED stays."""
    text = f"{SAY} I've noted your question."
    premise_talk(text, None, labels_of(1))
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"],
                    Step(decline_with("UNSUPPORTED_METRIC", text)))
    assert reply.text == f"{text} {NOTED} {CAN_ASK[1]}", reply.text


# ==== point 2: the two prompt sentences =============================================================

def prompt_lines(name):
    return PROMPTS[name].read_bytes().decode("utf-8").split("\n")


def test_p2_the_two_sentences_word_for_word_once_in_place():
    """C66's test, point 2: the line after rule 10 of the county talk prompt is C41's line, one
    space and the two sentences; each sentence is in the file once."""
    lines = prompt_lines("agent_prompt_s3_talk")
    (i,) = [i for i, line in enumerate(lines) if line.startswith("10. ")]
    assert lines[i] == RULE_10_TALK, "rule 10 is not changed"
    assert lines[i + 1] == LINE, lines[i + 1]
    text = "\n".join(lines)
    for sentence in C66_SENTENCES:
        assert text.count(sentence) == 1, sentence


@pytest.mark.parametrize("name", [n for n in PROMPTS if n != "agent_prompt_s3_talk"])
def test_p2_in_that_prompt_only(name):
    """Point 2: the other county prompt has no such line and is not changed; the SYNTHETIC prompts
    neither. Passes today; must still pass."""
    text = "\n".join(prompt_lines(name))
    for mark in (*C66_SENTENCES, "a rule of this project", "never call it your mistake"):
        assert mark not in text, (name, mark)


@pytest.mark.parametrize("talk", ["off", "on"])
def test_p2_a_county_turn_is_sent_them_with_talk_on_only(tmp_path, monkeypatch, talk):
    """C66's test, point 2: talk on, the system message holds the line once, after rule 10; talk
    off, neither sentence."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    env.ask("Can you count that for me?", Step(decline("UNRECOGNIZED_QUESTION")))
    system = env.model.calls[0]["messages"][0]["content"]
    if talk == "on":
        lines = system.split("\n")
        assert lines.count(LINE) == 1, [x[-200:] for x in lines if x.startswith("When you decline")]
        assert lines[lines.index(LINE) - 1] == RULE_10_TALK
    else:
        for sentence in C66_SENTENCES:
            assert sentence not in system, sentence


def _hash_modules():
    import test_s2_r13
    import test_s3_c44
    import test_s3_c46
    return {"test_s3_c44": (test_s3_c44, "text_of"), "test_s3_c46": (test_s3_c46, "text_of"),
            "test_s2_r13": (test_s2_r13, "prompt")}


@pytest.mark.parametrize("module_name", ["test_s3_c44", "test_s3_c46", "test_s2_r13"])
def test_p2_the_prompt_hash_tests_take_them_out(monkeypatch, module_name):
    """C66's test "the prompt hash tests take them out": each prompt hash test, given the county
    talk prompt with the two sentences at the end of C41's line, finds today's sha256; given them
    on a line of their own after C41's line, or twice at its end, it does not. The prompt is made
    in memory from the file as it is; no file is written. Passes today (with the three hash tests
    as this round changes them); must still pass after the build."""
    module, reader = _hash_modules()[module_name]
    real = getattr(module, reader)
    lines = without_c66("\n".join(prompt_lines("agent_prompt_s3_talk"))).split("\n")
    (i,) = [k for k, line in enumerate(lines) if line == C41_PROMPT_LINE]

    def made(*new):
        return "\n".join(lines[:i] + list(new) + lines[i + 1:])
    cases = ((made(LINE), True), (made(C41_PROMPT_LINE, C66_PROMPT_SENTENCES), False),
             (made(f"{LINE} {C66_PROMPT_SENTENCES}"), False))
    for text, same in cases:
        def fake(arg, text=text):
            name = arg if isinstance(arg, str) else Path(arg).stem
            return text if name == "agent_prompt_s3_talk" else real(arg)
        monkeypatch.setattr(module, reader, fake)
        digest = hashlib.sha256(module.restored("agent_prompt_s3_talk").encode("utf-8")).hexdigest()
        assert (digest == module.TODAY_SHA256["agent_prompt_s3_talk"]) is same, (module_name, same)


# ==== point 3: the thread shows that the rule refused a count =======================================

ASK_BACK = "Would a range that includes that age work for you?"


def stored(env, thread_key=THREAD_1):
    return env.store.recent_turns(thread_key, 100)


def you_lines(env, call_index=0):
    """The "You:" lines of the thread block the model was sent in the last turn, oldest first."""
    block = thread_block(env.model.calls[call_index]["messages"]) or ""
    return [line for line in block.split("\n") if line.startswith("You: ")], block


def next_turn_block(env):
    """One more message (a plain answered count of adults), then its thread block's You lines."""
    env.ask("and 30 to 40 in 2025?", Step(call_of(spec(Y25, [age(30, 40)]))),
            Step(finish("finding", "I counted {r1.count}.")))
    return you_lines(env)


def assert_noted(line):
    """C66-4: the note once, after what he did and before ` and said:` when there is one."""
    assert line.count(C66_NOTE) == 1, line
    said = line.find(' and said: "')
    if said >= 0:
        assert line.index(C66_NOTE) + len(C66_NOTE) == said, line
    else:
        assert line.endswith(C66_NOTE), line


def single_year_asked_back(env):
    return env.ask("how many 16 year olds were arrested in 2025?",
                   Step(call_of(spec(Y25, [age(16, 16)]))), Step(ask_with("other", ASK_BACK)))


@pytest.mark.parametrize("talk", ["off", "on"])
def test_p3_a_single_year_asked_outright_then_asked_back(tmp_path, monkeypatch, talk):
    """C66's test, point 3 (trial 1): "how many 16 year olds were arrested in 2025?": the count of
    16 to 16 answered NOT_ALLOWED (C35), then a question back: the turn ends NEEDS_INPUT and stores
    "age_rule": true; the next turn's thread block holds the note once, in that turn's line."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = single_year_asked_back(env)
    assert env.model.answer(0).get("error") == "NOT_ALLOWED", env.model.answer(0)
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.text)
    (turn,) = stored(env)
    assert turn.get("age_rule") is True, turn
    lines, block = next_turn_block(env)
    assert block.count(C66_NOTE) == 1, block
    assert lines[0].startswith("You: asked what they meant"), lines
    assert_noted(lines[0])


@pytest.mark.parametrize("talk", ["off", "on"])
def test_p3_a_count_refused_by_c21_beside_one_that_is_made(tmp_path, monkeypatch, talk):
    """C66's test, point 3: under 18 and under 17 of 2025 in one message: the first counted, the
    second refused by C21's check; the turn ends ANSWERED and stores the key; the next turn's block
    holds the note once, in that turn's line."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = env.ask("how many under 18 and under 17 in 2025?",
                    Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [U17]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_refused(env.model.answer(0, 1), why=WHY)
    assert reply.status == "ANSWERED", (reply.status, reply.text)
    (turn,) = stored(env)
    assert turn.get("age_rule") is True, turn
    lines, block = next_turn_block(env)
    assert block.count(C66_NOTE) == 1, block
    assert lines[0].startswith("You: counted ("), lines
    assert_noted(lines[0])


@pytest.mark.parametrize("talk", ["off", "on"])
def test_p3_a_statistic_refused_by_c65(tmp_path, monkeypatch, talk):
    """C66's test, point 3: under 18 in 2025 (answered, no key), then the trend of 10 to 16 refused
    by C65's check before anything is computed: that turn stores the key; the next block holds the
    note once, in the second turn's line, and not in the first's."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    env.ask("how many under 18 in 2025?", Step(call_of(spec(Y25, [U18]))),
            Step(finish("finding", "I counted {r1.count}.")))
    reply = env.ask("is 10 to 16 going up?", Step(analyze("trend", {"from": "2024-01-01",
                                                                    "to": "2026-09-17"},
                                                          [A10_16])),
                    Step(finish("finding", "ok.")))
    assert env.model.answer(0).get("error") == "NOT_ALLOWED", env.model.answer(0)
    assert reply.status == "UNSUPPORTED", (reply.status, reply.text)
    first, second = stored(env)
    assert "age_rule" not in first and second.get("age_rule") is True, (first, second)
    lines, block = next_turn_block(env)
    assert block.count(C66_NOTE) == 1, block
    assert C66_NOTE not in lines[0], lines
    assert_noted(lines[1])


def test_p3_a_plain_refusal(tmp_path, monkeypatch):
    """C66's test, point 3: a single year asked outright and nothing else: the turn ends
    UNSUPPORTED with the NOT_ALLOWED row and stores the key; the next block notes it."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("how many 16 year olds in 2025?", Step(call_of(spec(Y25, [age(16, 16)]))),
                    Step(finish("finding", "ok.")))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
    (turn,) = stored(env)
    assert turn.get("age_rule") is True, turn
    lines, _ = next_turn_block(env)
    assert lines[0].startswith("You: declined (NOT_ALLOWED)"), lines
    assert_noted(lines[0])


@pytest.mark.parametrize("case", ["no refused count", "TOO_FINE"])
def test_p3_no_key_without_a_refusal_under_the_rule(tmp_path, monkeypatch, case):
    """C66's test, point 3: a turn with no refused count, and one whose count was refused TOO_FINE
    (under 18 by district in 2025), store no key; the next block reads as today, with no note.
    Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    counts = [call_of(spec(Y25, [U18]))] if case == "no refused count" else \
        [call_of(spec(Y25, [U18], ["district"])), call_of(spec(Y25, [U18]))]
    env.ask("a message", Step(*counts), Step(finish("finding", "I counted {r1.count}.")))
    if case == "TOO_FINE":
        assert env.model.answer(0, 0).get("error") == "TOO_FINE", env.model.answer(0, 0)
    (turn,) = stored(env)
    assert "age_rule" not in turn, turn
    _, block = next_turn_block(env)
    assert C66_NOTE.strip() not in block and "single years of age" not in block, block


def test_p3_a_synthetic_mode_turn_has_no_key(tmp_path):
    """C66's test, point 3: SYNTHETIC mode stores no key and its thread block has no note. Passes
    today; must still pass."""
    env = p1.Env(tmp_path)
    env.ask("How many arrests in 2025 for people under 18?",
            Step(call("count_arrests", {"year": 2025, "age_group": "under_18"})),
            Step(finish("finding", "I counted {r1.count}.")))
    env.ask("And in 2024?", Step(call("count_arrests", {"year": 2024, "age_group": "under_18"})),
            Step(finish("finding", "I counted {r1.count}.")))
    for turn in env.store.recent_turns(THREAD_1, 10):
        assert "age_rule" not in turn, turn
    block = thread_block(env.model.calls[0]["messages"]) or ""
    assert "single years of age" not in block, block


def test_p3_after_reset_nothing_of_it_is_shown_and_no_key_is_kept(tmp_path, monkeypatch):
    """C66's test, point 3 with C65 point 4 (C66-6): a turn with a refused count (key stored), then
    `reset`: the stripped records hold no "age_rule", and the next turn's model is shown no thread
    (so no note); the check still refuses what it refused."""
    env = slack_env(tmp_path, monkeypatch)
    talk = Talk(env)
    talk.send("how many under 18 and under 17 in 2025?",
              Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [U17]))),
              Step(finish("finding", "I counted {r1.count}.")))
    assert stored(env)[-1].get("age_rule") is True, "premise: the key was stored"
    label, _ = talk.send("reset")
    assert label == "reset"
    kept = json.dumps(plain(given(env)))
    assert "age_rule" not in kept, kept
    talk.count(spec(Y25, [age(30, 40)]), "and 30 to 40 in 2025?")
    assert thread_block(env.model.calls[0]["messages"]) is None, "the model was shown the thread"


# ---- this session's own -------------------------------------------------------------------------

def test_p3_own_the_notes_place_when_the_turn_also_said_something(tmp_path, monkeypatch):
    """Own (C66-4): talk on, a turn with a count made and one refused, whose finish text is the
    model's own: its line is what he did, the note, then ` and said: "..."` with his words."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    env.ask("how many under 18 and under 17 in 2025?",
            Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [U17]))),
            Step(finish("finding", "I counted {r1.count}.")))
    (turn,) = stored(env)
    assert turn.get("reply_text"), f"premise: the turn has a reply text: {turn}"
    lines, _ = next_turn_block(env)
    assert ' and said: "' in lines[0], lines
    assert_noted(lines[0])


def test_p3_own_two_refused_turns_in_one_thread_block(tmp_path, monkeypatch):
    """Own (C66-4): two turns with a refused count, then a turn: the block holds the note twice,
    once in each of the two turns' lines, and not in the line of a turn between them with no
    refusal."""
    env = CountyEnv(tmp_path, monkeypatch)
    single_year_asked_back(env)
    env.ask("and 30 to 40 in 2024?", Step(call_of(spec({"year": 2024}, [age(30, 40)]))),
            Step(finish("finding", "I counted {r1.count}.")))
    env.ask("how many 15 year olds in 2025?", Step(call_of(spec(Y25, [age(15, 15)]))),
            Step(finish("finding", "ok.")))
    lines, block = next_turn_block(env)
    assert block.count(C66_NOTE) == 2, block
    assert [C66_NOTE in line for line in lines] == [True, False, True], lines
    assert_noted(lines[0])
    assert_noted(lines[2])


def test_p3_own_declined_under_another_code_after_a_refusal(tmp_path, monkeypatch):
    """Own: point 3's "whatever its ending (... declined under another code ...)": a single year
    answered NOT_ALLOWED, then the model declines UNSUPPORTED_FIELD: the key is stored and the next
    block notes it once."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("how many 16 year olds at each address?",
                    Step(call_of(spec(Y25, [age(16, 16)]))), Step(decline("UNSUPPORTED_FIELD")))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD"), reply.text
    (turn,) = stored(env)
    assert turn.get("age_rule") is True, turn
    lines, _ = next_turn_block(env)
    assert_noted(lines[0])


def test_p3_own_a_single_year_asked_outright_of_a_statistic(tmp_path, monkeypatch):
    """Own: C66-5, "a single year asked outright" of a statistic: the trend of 16 to 16 is answered
    NOT_ALLOWED before anything is computed; the turn stores the key."""
    env = CountyEnv(tmp_path, monkeypatch)
    env.ask("are arrests of 16 year olds going up?",
            Step(analyze("trend", {"from": "2024-01-01", "to": "2026-09-17"}, [age(16, 16)])),
            Step(finish("finding", "ok.")))
    assert env.model.answer(0).get("error") == "NOT_ALLOWED", env.model.answer(0)
    (turn,) = stored(env)
    assert turn.get("age_rule") is True, turn


def test_p3_own_the_ninth_count_is_not_the_rule(tmp_path, monkeypatch):
    """Own: a turn of nine counts of adults (the ninth answered TOO_MANY) stores no key. Passes
    today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    counts = [call_of(spec(Y25, [age(20 + 5 * k, 24 + 5 * k)])) for k in range(9)]
    env.ask("nine counts", Step(*counts), Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0, 8).get("error") == "TOO_MANY", env.model.answer(0, 8)
    (turn,) = stored(env)
    assert "age_rule" not in turn, turn


def test_p3_own_the_key_is_the_turns_alone(tmp_path, monkeypatch):
    """Own: the turn after a refused one, with nothing refused, stores no key: the key is not
    carried from turn to turn."""
    env = CountyEnv(tmp_path, monkeypatch)
    single_year_asked_back(env)
    next_turn_block(env)
    first, second = stored(env)
    assert first.get("age_rule") is True and "age_rule" not in second, (first, second)


def test_p3_own_the_note_holds_no_figure_and_no_age():
    """Own: the note's words hold no digit (the thread block never shows a figure, C9). Passes."""
    assert not any(ch.isdigit() for ch in C66_NOTE.replace("18", ""))
    assert C66_NOTE == " (a count was refused under the rule about single years of age under 18)"
