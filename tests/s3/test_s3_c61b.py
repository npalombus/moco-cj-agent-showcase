"""C61 Part B of docs/S3A-DESIGN.md (D-076): he sees what he said. Points 4 to 7, with "C61, four
corrections before its tests" (2: point 7's line goes into the county talk prompt only; 3: `sent`
and the not-shown line are county mode only, THREAD_BLOCK_MAX and the default of
MOCO_THREAD_TURNS_IN_CONTEXT are the program's in both modes) and "C61, two additions after the
threads" (6: point 7's line ends with one more sentence). With the proof Nino asked for (D-076,
"re-prove the guard"; brief S3-R23-A, 18:26 EST): with a figure in a `You said:` line, a talk text,
a finding text and an about_data text that repeat that figure, or a figure worked out from it, each
fail their check and are not sent. Brief: briefs/S3-R23-A-tests.md. Tests only; red until the
planning chat builds C61, except those that pin what stays (named in their docstrings).

All data is SYNTHETIC (the tests/s3 fixtures); replies.ABOUT_AGENT points at a fixture copy made in
tmp_path (s3support.about_agent_fixture), never at config/about_agent.md.

Readings (also in kit-log/raw/S3-R23-A-notes.txt):
- R23-B1. `sent` is in the thread memory's record (store.recent_turns, what `_Turn.run` reads). It
  is the reply text exactly as sent (line breaks kept), with the notices lines (each source's
  notices and the course-project line, C11) or C57's one line taken out with the line break before
  each, and C56's note taken out with its line break. A reply of 600 characters or fewer is kept
  whole.
- R23-B2. "Cut to 600 characters (at a word's end, then ` ...`)": the part before ` ...` is the
  start of the text, at most 600 characters, ends at a word's end (the next character of the text
  is a space or a line break), and is cut no more than one word short of 600.
- R23-B3. The `You said:` line shows `sent` in quotation marks. Whether its line breaks are kept or
  made spaces is not said: the tests compare with white space made single spaces.
- R23-B4. "The block's second line": the line straight after the THREAD SO FAR header.
"""
import json
import re
from datetime import timedelta

import pytest

from p1support import (THREAD_1, Env, Step, count as synthetic_count, decline, describe, finish,
                       make_settings, mod, show_details, thread_block)
from s3support import (A_ID, C61_NOT_SHOWN, C62_PROMPT_SENTENCES, C64_PROMPT_SENTENCES,
                       C64_TALK_LINE, NOW_S3, Q_ABOUT, Q_COUNT, REPO, CountyEnv,
                       about_agent_fixture, county_fallback_line, count, figures, truth,
                       turn_json, year)
from test_s3_c56 import World, down, standin
from test_s3_c57 import NOTICES_SHOWN, full_notices

TALK = ["off", "on"]
NOTE = ("Note: I'm temporarily running on a smaller backup model, so this answer may be less "
        "sharp than usual.")  # C56 point 5

# Point 7, with addition 6's sentence at its end (one space between), word for word.
C61_PROMPT_LINE = (
    'THREAD SO FAR also shows what you said ("You said:"). Stay consistent with it: never deny or '
    "change something you said unless it was wrong, and then say so once. You may point back to a "
    'figure you gave ("the figure I gave for district 4"), but never write, add, subtract or judge '
    "a figure yourself: figures come only from this turn's slots. If the thread says earlier "
    "messages are not shown, say that you only see the recent part when someone asks about them. "
    "Before you decline, or say that you do not know something about the data or about yourself, "
    "call describe_data and read its facts: decline only when no fact answers the question.")
PROMPTS = {"agent_prompt_s3": REPO / "config" / "agent_prompt_s3.md",
           "agent_prompt_s3_talk": REPO / "config" / "agent_prompt_s3_talk.md"}
SYNTHETIC_PROMPTS = {name: REPO / "config" / f"{name}.md" for name in
                     ("agent_prompt_talk", "agent_prompt_v2", "agent_prompt_v1",
                      "system_prompt_v1")}


@pytest.fixture(autouse=True)
def _about_agent(tmp_path, monkeypatch):
    about_agent_fixture(tmp_path, monkeypatch)


def norm(text):
    return " ".join(str(text).split())


def memory(env, thread_key=THREAD_1):
    return env.store.recent_turns(thread_key, 100)


def block(env, call=0):
    return thread_block(env.model.calls[call]["messages"])


def without_notices(text, env, names=("arrests_like",)):
    """R23-B1: the reply's lines without the notices lines and without C57's one line."""
    dropped = set(full_notices(env, names)) | {NOTICES_SHOWN}
    return "\n".join(line for line in text.split("\n") if line not in dropped)


def count_turn(env, y=2025, **kw):
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(y))),
                    Step(finish("finding", "I counted {r1.count}.")), **kw)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def about_turn(env, text="Here is what I know. {f1}.", **kw):
    return env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", text)), **kw)


def refused_turn(env, question="whats the weather today?", **kw):
    return env.ask(question, Step(decline("UNRECOGNIZED_QUESTION")), **kw)


# ==== point 4: `sent` ============================================================================

@pytest.mark.parametrize("talk", TALK)
def test_b4_a_count_reply_is_kept_as_sent(tmp_path, monkeypatch, talk):
    """Point 4: a count reply (it carries no notices) is kept exactly, figures and all."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = count_turn(env)
    assert len(reply.text) <= 600, "premise: not cut"
    (record,) = memory(env)
    assert record.get("sent") == reply.text, record.get("sent")


@pytest.mark.parametrize("talk", TALK)
def test_b4_an_about_reply_is_kept_without_the_notices(tmp_path, monkeypatch, talk):
    """Point 4 with C57 point 5: the first about reply (the notices in full) and the second (C57's
    one line) are both kept without them: the same text twice."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    first, second = about_turn(env), about_turn(env)
    assert first.reply_style == second.reply_style == "agent", (first.text, second.text)
    sent = [r.get("sent") for r in memory(env)]
    assert sent == [without_notices(first.text, env), without_notices(second.text, env)], sent
    assert sent[0] == sent[1] and sent[0].startswith("Here is what I know. "), sent
    for line in full_notices(env, ("arrests_like",)) + [NOTICES_SHOWN]:
        assert line not in sent[0], line


def test_b4_a_details_reply_is_kept_without_the_notices(tmp_path, monkeypatch):
    """Point 4: `details` carries the notices (C11); its `sent` is its lines without them."""
    env = CountyEnv(tmp_path, monkeypatch)
    count_turn(env)
    details = env.ask("details", Step(show_details()))
    assert details.status == "DETAILS", (details.status, details.text)
    assert any(line in details.text for line in full_notices(env, ("arrests_like",))), \
        "premise: the details carry the notices"
    kept_as(memory(env)[-1].get("sent"), without_notices(details.text, env))


@pytest.mark.parametrize("talk", TALK)
def test_b4_a_refusal_and_a_question_are_kept_as_sent(tmp_path, monkeypatch, talk):
    """Point 4, "a turn's memory record": a refusal and Python's question are kept too."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    refused = refused_turn(env)
    asked = env.ask("Can you count the arrests for me?", Step(count(A_ID)))
    assert asked.status == "NEEDS_INPUT", (asked.status, asked.text)
    assert [r.get("sent") for r in memory(env)] == [refused.text, asked.text]


def test_b4_a_talk_fallback_is_kept_as_sent(tmp_path, monkeypatch):
    """Point 4 with point 9: a talk text that failed: the fallback that was sent is kept."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = env.ask("hello", Step(finish("talk", "Most of them were group Gamma.")))
    assert reply.reply_style == "fallback", reply.text
    assert memory(env)[-1].get("sent") == reply.text == county_fallback_line(1)


def test_b4_c56s_note_is_not_kept(tmp_path, monkeypatch):
    """Point 4: a second try on the backup model: the reply ends with C56's note; `sent` is the
    reply without it (and the thread holds that one turn, as C56 point 6 has it)."""
    world = World(tmp_path, monkeypatch, "county")
    reply = world.ask(Q_COUNT, down(), standin(Step(count(A_ID, year(2025))),
                                               Step(finish("finding", "I counted {r1.count}."))))
    assert reply.status == "ANSWERED" and reply.text.endswith("\n" + NOTE), reply.text
    (record,) = world.memory()
    assert record.get("sent") == reply.text[:-len("\n" + NOTE)], record.get("sent")


def kept_as(sent, whole):
    """Point 4: the whole text when it has 600 characters or fewer, else cut (R23-B2)."""
    if len(whole) <= 600:
        assert sent == whole, sent
    else:
        assert_cut(sent, whole)


def assert_cut(sent, text):
    """R23-B2."""
    assert isinstance(sent, str) and sent.endswith(" ..."), sent
    head = sent[:-4]
    assert text.startswith(head) and len(head) <= 600, (len(head), head)
    assert text[len(head)].isspace() and not head[-1].isspace(), "not cut at a word's end"
    longest = max(len(word) for word in text.split())
    assert len(head) >= 600 - longest - 1, f"cut {600 - len(head)} characters short of 600"


def test_b4_a_long_reply_is_cut_to_600_at_a_words_end(tmp_path, monkeypatch):
    """Point 4: an about reply of four facts, over 600 characters without the notices."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")  # C38: four long facts pass
    reply = about_turn(env, "{f1}. {f2}. {f3}. {f4}.")
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    whole = without_notices(reply.text, env)
    assert len(whole) > 600, f"premise: {len(whole)} characters"
    assert_cut(memory(env)[-1].get("sent"), whole)


def test_b4_synthetic_mode_keeps_no_sent(tmp_path):
    """Correction 3: `sent` is kept in county mode only. Passes today; must still pass."""
    env = Env(tmp_path)
    env.ask("How many arrests were there in 2025 for people under 18?",
            Step(synthetic_count(2025, "under_18")),
            Step(finish("finding", "I counted {r1.count}.")))
    env.ask("whats the weather today?", Step(decline("UNRECOGNIZED_QUESTION")))
    records = env.store.recent_turns(THREAD_1, 10)
    assert len(records) == 2 and not any("sent" in r for r in records), records


# ==== point 5: the third line, the not-shown line, the two defaults ============================

def you_said(sent):
    return norm(f'You said: "{sent}"')


@pytest.mark.parametrize("talk", TALK)
def test_b5_each_turn_with_sent_gets_a_third_line_after_you(tmp_path, monkeypatch, talk):
    """Point 5: `You said: "<sent>"` straight after each turn's `You: ...` line, oldest first."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    count_turn(env)
    about_turn(env)
    refused_turn(env, "and the weather tomorrow?")
    sent = [r["sent"] for r in memory(env)]
    lines = block(env).split("\n")
    you = [i for i, line in enumerate(lines) if line.startswith("You: ")]
    assert len(you) == 2, lines
    for i, s in zip(you, sent):
        after = norm("\n".join(lines[i + 1:]))
        assert lines[i + 1].startswith('You said: "'), lines[i + 1]
        assert after.startswith(you_said(s)), (after[:300], s)
    text = norm(block(env))
    assert text.index(you_said(sent[0])) < text.index(you_said(sent[1])), text


def test_b5_the_model_is_shown_its_own_figure(tmp_path, monkeypatch):
    """Point 6: "the model now sees the figures of its own earlier replies": the count of the
    first message is in the second message's block, in the `You said:` line only."""
    env = CountyEnv(tmp_path, monkeypatch)
    first = count_turn(env)
    total = truth("arrests_like", year(2025))["total"]
    assert total in figures(first.text), "premise"
    refused_turn(env)
    lines = block(env).split("\n")
    said = [line for line in lines if line.startswith("You said: ")]
    assert said and total in figures(said[0]), lines
    rest = "\n".join(line for line in lines if not line.startswith("You said: ")
                     and not line.startswith(("(", "Source: ")))
    assert total not in figures(rest), rest


def plain_turns(env, n, start=0):
    for i in range(start, start + n):
        refused_turn(env, f"whats the weather on day {chr(97 + i)}?")


@pytest.mark.parametrize("earlier, shown, line", [(10, 10, False), (11, 10, True)],
                         ids=["ten earlier: no line", "eleven earlier: the line"])
def test_b5_the_default_ten_and_the_not_shown_line(tmp_path, monkeypatch, earlier, shown, line):
    """Point 5: the default of MOCO_THREAD_TURNS_IN_CONTEXT is 10; with more remembered turns
    than the block shows, its second line is the not-shown line."""
    env = CountyEnv(tmp_path, monkeypatch)
    plain_turns(env, earlier)
    refused_turn(env, "one more?")
    lines = block(env).split("\n")
    users = [l for l in lines if l.startswith("User: ")]
    assert len(users) == shown, users
    assert users[-1] == f'User: "whats the weather on day {chr(97 + earlier - 1)}?"'
    assert (lines[1] == C61_NOT_SHOWN) is line, lines[:3]
    assert lines.count(C61_NOT_SHOWN) == (1 if line else 0)


@pytest.mark.parametrize("earlier, line", [(2, False), (3, True)])
def test_b5_the_not_shown_line_with_the_setting(tmp_path, monkeypatch, earlier, line):
    env = CountyEnv(tmp_path, monkeypatch, MOCO_THREAD_TURNS_IN_CONTEXT="2")
    plain_turns(env, earlier)
    refused_turn(env, "one more?")
    lines = block(env).split("\n")
    assert len([l for l in lines if l.startswith("User: ")]) == 2
    assert (lines[1] == C61_NOT_SHOWN) is line, lines[:3]


def test_b5_turns_outside_the_memory_window_are_not_remembered(tmp_path, monkeypatch):
    """Point 5 "remembered turns": three turns two hours back and two recent ones, a memory of
    60 minutes and MOCO_THREAD_TURNS_IN_CONTEXT=2: all remembered turns are shown, no line."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_THREAD_TURNS_IN_CONTEXT="2")
    for i in range(3):
        refused_turn(env, f"old question {chr(97 + i)}?", now=NOW_S3 + timedelta(minutes=i),
                     memory_minutes=60)
    for i in range(2):
        refused_turn(env, f"new question {chr(97 + i)}?",
                     now=NOW_S3 + timedelta(hours=2, minutes=i), memory_minutes=60)
    refused_turn(env, "one more?", now=NOW_S3 + timedelta(hours=2, minutes=5), memory_minutes=60)
    lines = block(env).split("\n")
    assert C61_NOT_SHOWN not in lines and not any("old question" in l for l in lines), lines


def test_b5_synthetic_mode_default_ten_no_third_line_no_not_shown_line(tmp_path):
    """Correction 3: in SYNTHETIC mode the default is 10 too, and there is no `You said:` line
    and no not-shown line."""
    env = Env(tmp_path)
    for i in range(11):
        env.ask(f"whats the weather on day {chr(97 + i)}?", Step(decline("UNRECOGNIZED_QUESTION")))
    env.ask("one more?", Step(decline("UNRECOGNIZED_QUESTION")))
    lines = block(env).split("\n")
    users = [l for l in lines if l.startswith("User: ")]
    assert len(users) == 10 and users[0] == 'User: "whats the weather on day b?"', users
    assert C61_NOT_SHOWN not in lines and not any(l.startswith("You said:") for l in lines)


def test_b5_thread_block_max_is_8000_and_the_default_is_10(tmp_path):
    assert mod("context").THREAD_BLOCK_MAX == 8000
    assert make_settings(tmp_path).moco_thread_turns_in_context == 10


def test_b5_the_block_holds_up_to_8000_characters_newest_kept(tmp_path, monkeypatch):
    """Point 5: fourteen about turns of about 750 characters each in the block (a `sent` cut
    near 600): more than 3,000 characters are shown, at most 8,000, the newest kept, not all,
    and the not-shown line is there."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", MOCO_THREAD_TURNS_IN_CONTEXT="30")
    tags = [f"turnmark{i:02d}x" for i in range(14)]
    for tag in tags:
        reply = env.ask(f"What data do you have, {tag}?", Step(describe()),
                        Step(finish("about_data", "{f1}. {f2}. {f3}. {f4}.")))
        assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    refused_turn(env, "one more?")
    text = block(env)
    shown = [tag in text for tag in tags]
    assert 7000 < len(text) <= 8000, len(text)
    assert shown[-1] and not all(shown) and shown == sorted(shown), shown
    assert text.split("\n")[1] == C61_NOT_SHOWN


# ==== point 6 and the guard, proved again (D-076) ==============================================

F = truth("arrests_like", year(2025))["total"]   # the first message's count (240)
G = truth("arrests_like", year(2024))["total"]   # the second message's count (230)


def test_premise_the_guards_figures():
    assert (F, G) == (240, 230), (F, G)
    assert F // 2 not in (G, F) and F // 12 not in (G, F) and F - G not in (G, F)


def thread_with_the_figure(env):
    """The first message counted F; the second message's model is shown F in `You said:`
    (asserted on its first call by `shown_the_figure`)."""
    first = count_turn(env)
    assert F in figures(first.text), first.text
    return first


def shown_the_figure(env):
    said = [l for l in block(env).split("\n") if l.startswith("You said: ")]
    assert said and F in figures(said[0]), f"premise: {F} is not in a You said: line: {said}"
    answers = [m["content"] for m in env.model.calls[-1]["messages"] if m.get("role") == "tool"
               and '"REWRITE"' not in m["content"]]  # T3's `found` gives back his own words
    assert F not in figures(json.dumps(answers)), "a tool answer holds the figure"


def assert_not_sent(env, reply, *values):
    for n in values:
        assert n not in figures(reply.text), f"{n} was sent: {reply.text!r}"
        assert n not in figures(memory(env)[-1].get("sent") or ""), "kept as sent"
        assert n not in figures(json.dumps(turn_json(reply, env.runs_dir).get("reply")))


TALK_REPEATS = {
    "the figure": f"I said there were {F} of them, and that still stands.",
    "half of it": f"Half of that would be {F // 2}.",
    "a month of it": f"That comes to {F // 12} in a month.",
    "the figure in words": "That was two hundred and forty records.",
    "the difference in words": "That is ten more than the year before.",
}


@pytest.mark.parametrize("case", list(TALK_REPEATS))
def test_guard_a_talk_text_that_repeats_the_figure_fails_number_and_is_not_sent(
        tmp_path, monkeypatch, case):
    """Point 6 and C61's test: "a talk text that repeats a figure from You said: still fails
    NUMBER", and D-076's proof: each try fails NUMBER, the county fallback is sent, and the
    figure (or the one worked out from it) is in no reply, no `sent` and no turn record.
    Changed by briefs/S3-R28-A-tests.md (C64 point 1): the text that ends the turn fails NUMBER,
    so the line sent is C64's (s3support.C64_TALK_LINE, no digit in it); it was C61's county line
    (county_fallback_line(1)). The proof that no figure is sent is unchanged."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    thread_with_the_figure(env)
    reply = env.ask("is that a lot?", Step(finish("talk", TALK_REPEATS[case])))
    shown_the_figure(env)
    assert (reply.status, reply.reply_style) == ("TALKED", "fallback"), reply.text
    assert "NUMBER" in reply.draft_failures, reply.draft_failures
    assert reply.text == C64_TALK_LINE, reply.text  # briefs/S3-R28-A-tests.md: was C61's line
    assert_not_sent(env, reply, F, F // 2, F // 12, F - G)


FINDING_REPEATS = {
    "the figure": f"I counted {{r1.count}}. Before that I said {F}.",
    "worked out": f"I counted {{r1.count}}. That is {F - G} fewer than the year after.",
    "in words": "I counted {r1.count}. That is ten fewer than the year after.",
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(FINDING_REPEATS))
def test_guard_a_finding_text_that_repeats_the_figure_fails_and_is_not_sent(
        tmp_path, monkeypatch, case, talk):
    """D-076's proof for a finding: the text fails (NUMBER in a talk sentence with talk on;
    R1's check with talk off), the fixed rendering of this message's count is sent, and the
    earlier figure (or the difference) is not."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    thread_with_the_figure(env)
    reply = env.ask("and 2024?", Step(count(A_ID, year(2024))),
                    Step(finish("finding", FINDING_REPEATS[case])))
    shown_the_figure(env)
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert reply.draft_failures, reply.draft_failures
    if talk == "on":
        assert "NUMBER" in reply.draft_failures, reply.draft_failures
    assert reply.text.startswith(f"I counted {G} arrest records in 2024."), reply.text
    assert_not_sent(env, reply, F, F - G)


ABOUT_REPEATS = {
    "the figure": f"Here is what I know. {{f1}}. You were told {F} before.",
    "worked out": f"Here is what I know. {{f1}}. That is {F // 2} for each half year.",
    "in words": "Here is what I know. {f1}. That is ten more than the year before.",
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(ABOUT_REPEATS))
def test_guard_an_about_text_that_repeats_the_figure_fails_and_is_not_sent(
        tmp_path, monkeypatch, case, talk):
    """D-076's proof for about_data: the text fails, and the reply is addition 5's rendering of
    the fact it named (`Here is what I know.` and {f1}'s fact), without the figure."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    thread_with_the_figure(env)
    reply = about_turn(env, ABOUT_REPEATS[case])
    shown_the_figure(env)
    (facts,) = [a["facts"] for a in env.answers() if "facts" in a]
    assert (reply.status, reply.reply_style) == ("EXPLAINED", "fallback"), reply.text
    assert reply.draft_failures, reply.draft_failures
    if talk == "on":
        assert "NUMBER" in reply.draft_failures, reply.draft_failures
    assert reply.text.startswith("Here is what I know. " + facts[0]["text"]), reply.text
    assert_not_sent(env, reply, F, F // 2, F - G)


# ==== point 7: the line in the county talk prompt ===============================================

def prompt_lines(path):
    return path.read_bytes().decode("utf-8").split("\n")


# Since C62 point 3 the line ends with C62's two sentences (round 25, briefs/S3-R25-A-tests.md, on
# the planning chat's answer 1 to S3-R24-A's question 1): C61's line, one space, the two sentences,
# and nothing else.
# Changed by briefs/S3-R28-A-tests.md (C64 point 2): C64's three sentences follow C62's two, one
# space before them; it was C61's line and C62's two sentences.
THE_LINE = f"{C61_PROMPT_LINE} {C62_PROMPT_SENTENCES} {C64_PROMPT_SENTENCES}"


def test_b7_the_line_directly_after_rule_11_of_the_talk_prompt():
    """Point 7 as C62 point 3 makes it (changed by round 25): the line directly after rule 11 is
    C61's line, one space and C62's two sentences, nothing else; it is in the file once.
    Changed by briefs/S3-R28-A-tests.md (C64 point 2): and then one space and C64's three
    sentences (THE_LINE)."""
    lines = prompt_lines(PROMPTS["agent_prompt_s3_talk"])
    eleven = [i for i, line in enumerate(lines) if line.startswith("11. ")]
    assert len(eleven) == 1, "premise: one rule 11"
    assert lines[eleven[0] + 1] == THE_LINE, lines[eleven[0] + 1][-400:]
    assert lines.count(THE_LINE) == 1
    assert "\n".join(lines).count("THREAD SO FAR also shows what you said") == 1


def test_b7_not_in_the_other_county_prompt_nor_the_synthetic_ones():
    """Correction 2: the talk prompt only. Passes today; must still pass."""
    for name, path in {"agent_prompt_s3": PROMPTS["agent_prompt_s3"], **SYNTHETIC_PROMPTS}.items():
        text = path.read_bytes().decode("utf-8")
        assert "You said:" not in text and "never deny or change something you said" not in text, \
            name
        assert "decline only when no fact answers the question" not in text, name


def test_b7_the_line_is_sent_with_talk_on(tmp_path, monkeypatch):
    """Point 7 as C62 point 3 makes it (changed by round 25): a county turn with talk on is sent
    that line once, directly after rule 11. Changed by briefs/S3-R28-A-tests.md (C64 point 2): the
    line ends with C64's three sentences (THE_LINE)."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    env.ask("hello", Step(finish("talk", "Hello! Ask me for a count whenever you like.")))
    system = env.model.calls[0]["messages"][0]["content"].split("\n")
    assert system.count(THE_LINE) == 1, [line[-200:] for line in system if "THREAD SO FAR" in line]
    i = system.index(THE_LINE)
    assert system[i - 1].startswith("11. "), system[i - 1][:80]


def test_b7_premise_the_line_is_point_7s_then_addition_6s():
    point7, addition6 = C61_PROMPT_LINE.split(" Before you decline, ")
    assert point7.endswith("say that you only see the recent part when someone asks about them.")
    assert re.fullmatch(r"or say that .* no fact answers the question\.", addition6)
