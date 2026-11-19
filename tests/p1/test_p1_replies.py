"""Replies end to end (docs/P1A-R2-DESIGN.md R1 for findings and about_data, revision 2;
docs/P1A-DESIGN.md A7 for the rest; brief P1A2-A point 4). Every reply here comes from a
real agent.handle_question turn driven by a FakeModel, never from the replies functions
called alone (those are in test_p1_reply_checks.py and test_p1_reply_tricks.py).

Covers:
- a passing `finish` after two counts and a compare: line 1 is the model's text with each
  fact slot filled with its whole phrase (R1), from the truth file's numbers, style `agent`,
  kind `finding`; line 2 is the long SYNTHETIC line for the thread's first ANSWERED turn and
  the short tag for a later one (per thread, ANSWERED turns only, and for a direct message
  only turns newer than `memory_minutes`, A5);
- the kept note on line 1 when the year, the age group or both came from memory (a chained
  compare that keeps the age group included);
- a failing `finish` for every failure code of R1 (SLOT, GLUE, CHARS, WORD, SHAPE): line 1 is
  the fixed rendering, style `fallback`, the code in `draft_failures`, and nothing the fake
  wrote anywhere in the reply (the reply is exactly Python's text; TYPED and the zqx mark are
  looked for too); a slot of an earlier turn's result;
- MOCO_REPLY_STYLE=fixed; `about_data` (R1: fact slots, filled, DATA_TAG when the filled text
  lacks SYNTHETIC) and `background` (A7, unchanged) in each branch, and both treated as a
  finding when the turn has results;
- every fixed row of A7's table, ABOUT and the background refusal, word for word, each
  reached by its real path, with the years and age wordings read from the registry (a
  registry copy in tmp_path shows they are not typed into the program);
- unless the status is ANSWERED or DETAILS, no count from the data in the reply
  (check_reply, on every reply).

Accepted both ways (kit-log/raw/P1A-A-notes.txt):
- The parts A7 joins with "+" (and DATA_TAG after an about_data text) may be joined by one
  space or one line break.
- render_fixed may write a number of 1,000 or more with or without its comma; its compare
  sentence may start with a capital or not (fixed_line1_re). fill's comma is exact.
- A fixed rendering that no finish produced (DECLINED_AFTER_RESULTS): style `fallback` or
  `fixed`, kind `finding` or None, reason_code None or the code (check_reply).
- BACKGROUND_OFF, and the fixed ABOUT text: kind `background` / `about_data` or None. Style
  of a non-finding fixed reply is only checked to be one of the three (check_reply).
- `background` with the setting on and a failing text: A7 gives the text and the style
  (`fallback`) but not the status, so UNSUPPORTED and EXPLAINED are both accepted.
- The fixed ABOUT text has status EXPLAINED: A7's about_data paragraph ends "Status
  EXPLAINED", and A4 lists no other status or code that fits it.

Cannot check here: whether the real model writes texts that pass (the live loop check);
draft_failures for a failing about_data or background text (A7 and R1 name failure codes in
the reply only for findings).

Read as given: an EXPLAINED reply has reason_code None (checked in check_reply).
"""
import json
import re
from datetime import timedelta

import pytest

from p1support import (BACKGROUND_PREFIX, BACKGROUND_SUFFIX, DATA_TAG, DECLINE_CODES,
                       DM_KEY, LINE2_FIRST, LINE2_LATER, MARK, NOW, ONE_COUNT_TEXT,
                       THREAD_2, TYPED, Env, Step, about_text, assert_answered, assert_fixed,
                       R1_CODES, ask_user, check_reply, compare, compare_expect,
                       compare_slots, count, has_leaf, turn_record,
                       count_slots, decline, describe, fact_slots, fill_expect, finish,
                       fixed_line1_re, kept_note, load_registry, mod, months, odd_chars,
                       registry_copy, reply_rules, single_sentence_facts, synthetic_fact,
                       unlisted_words)
from support import NOT_SYNTHETIC_COPIES, REFUSED

# P1-DESIGN section 4, the settings table: MOCO_MAX_QUESTION_CHARS defaults to 500
# (unchanged by P1A). A design default, not a number from the data.
DEFAULT_MAX_QUESTION_CHARS = 500

QUESTION = "How many arrests were there each month in 2025 for ages 18 to 25?"

# A finding text that passes R1's check with two counts (r1, r2) and a compare (r3).
CHAIN_TEXT = "I counted {r1.count} and {r2.count}. {r3.compare}."

# Text with no fact slot: a finding or an about_data text that fails SLOT (R1).
NO_SLOT_TEXT = "Here is what I know."
# A background text that passes check_background (its hedge word is "may").
BACKGROUND_TEXT = ("Arrest counts may change over a year for many reasons, such as how "
                   "records are kept.")


# ---- local helpers ----------------------------------------------------------------------

def total(year, group):
    return sum(months(year, group))


def one_count(year, group):
    """The phrases of ONE_COUNT_TEXT's slots for one count (R1)."""
    return count_slots("r1", year, group)


def chain_phrases(pair):
    """The phrases of CHAIN_TEXT's slots: r1 and r2 counted, r3 their compare (R1)."""
    (y1, g1), (y2, g2) = pair
    c = compare_expect([(y1, g1, total(y1, g1)), (y2, g2, total(y2, g2))])
    return {**count_slots("r1", y1, g1), **count_slots("r2", y2, g2), **compare_slots("r3", c)}


def listed(list_name, word):
    """True when `word` matches an entry of config/reply_rules.json's list (A7: whole word
    or phrase, any case; an entry ending in * matches any word that starts with it)."""
    word = word.lower()
    return any(word == entry or (entry.endswith("*") and word.startswith(entry[:-1]))
               for entry in reply_rules()[list_name])


def assert_listed(list_name, word):
    if list_name == "markup":  # marks match as written: the entry "*" is not a wildcard
        assert word in reply_rules()["markup"], f"{word!r} is not in reply_rules.json markup"
    elif list_name is not None:
        assert listed(list_name, word), f"{word!r} is not in reply_rules.json {list_name}"


def group_arg(group):
    return "all" if group is None else group


def assert_finding(reply, style):
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_kind == "finding", reply.reply_kind
    assert reply.reply_style == style, reply.reply_style


# ---- a passing finding, filled (A7) -------------------------------------------------------

@pytest.mark.parametrize("pair", [
    pytest.param([(2024, "under_18"), (2025, "under_18")], id="years-differ"),
    pytest.param([(2025, "18_25"), (2025, "under_18")], id="age-groups-differ"),
    pytest.param([(2024, None), (2025, None)], id="all-ages-totals-over-1000"),
])
def test_two_counts_a_compare_and_a_passing_finish_give_the_filled_text(tmp_path, pair):
    """R1 and R9: the model's text, each fact slot filled by Python with its whole phrase
    from the truth file's numbers, is line 1 exactly; style agent, kind finding; line 2 is
    LINE2_FIRST for the thread's first ANSWERED turn."""
    env = Env(tmp_path)
    (y1, g1), (y2, g2) = pair
    reply = env.ask("Compare those two counts, please.",
                    Step(count(y1, group_arg(g1)), count(y2, group_arg(g2))),
                    Step(compare("r1", "r2")),
                    Step(finish("finding", CHAIN_TEXT)))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(CHAIN_TEXT, chain_phrases(pair))
    assert reply.text == line1 + "\n" + LINE2_FIRST
    assert reply.draft_failures == []
    assert reply.carried == {"year": False, "age_group": False}
    assert len(reply.results) == 3  # two counts and a compare (A2: only the length)


def test_a_later_answered_turn_in_the_thread_gets_the_short_tag(tmp_path):
    """A7: line 2 is the short tag for every ANSWERED turn after the thread's first."""
    env = Env(tmp_path)
    first = env.answered(QUESTION, (2025, "18_25"))
    check_reply(first, env.model)
    assert first.text.endswith("\n" + LINE2_FIRST), first.text
    reply = env.ask("And for people under 18 in 2024?", Step(count(2024, "under_18")),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(ONE_COUNT_TEXT, one_count(2024, "under_18"))
    assert reply.text == line1 + "\n" + LINE2_LATER


@pytest.mark.parametrize("earlier", ["declined", "asked"])
def test_only_an_answered_turn_makes_a_later_answer_short(tmp_path, earlier):
    """A7: "the first ANSWERED turn of the thread". An earlier turn that was declined or
    asked a question does not count, so the first answer still gets LINE2_FIRST."""
    env = Env(tmp_path)
    if earlier == "declined":
        env.ask("Can you help me with something?", Step(decline("UNRECOGNIZED_QUESTION")))
    else:
        env.ask("Can you help me with something?", Step(ask_user("other")))
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(ONE_COUNT_TEXT, one_count(2025, "18_25"))
    assert reply.text == line1 + "\n" + LINE2_FIRST


def test_the_first_answer_is_counted_per_thread(tmp_path):
    """A7: first ANSWERED turn "of the thread": an answer in another thread does not count."""
    env = Env(tmp_path)
    env.answered(QUESTION, (2025, "18_25"))
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)),
                    thread_key=THREAD_2)
    check_reply(reply, env.model)
    assert reply.text.endswith("\n" + LINE2_FIRST), reply.text


@pytest.mark.parametrize("minutes_later, line2", [
    pytest.param(120, LINE2_FIRST, id="earlier-answer-older-than-memory_minutes"),
    pytest.param(30, LINE2_LATER, id="earlier-answer-within-memory_minutes"),
])
def test_a_direct_message_counts_only_recent_turns_for_the_first_answer(tmp_path,
                                                                        minutes_later, line2):
    """A5: for a direct-message conversation only turns newer than memory_minutes count for
    "first answer" (A7)."""
    env = Env(tmp_path)
    env.answered(QUESTION, (2025, "18_25"), thread_key=DM_KEY, memory_minutes=60, now=NOW)
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)),
                    thread_key=DM_KEY, memory_minutes=60,
                    now=NOW + timedelta(minutes=minutes_later))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(ONE_COUNT_TEXT, one_count(2025, "18_25"))
    assert reply.text == line1 + "\n" + line2


# ---- the kept note (A5, A7) ---------------------------------------------------------------

@pytest.mark.parametrize("base, stated, counted, note, carried", [
    pytest.param((2025, "18_25"), (None, "under_18"), (2025, "under_18"),
                 kept_note(2025), {"year": True, "age_group": False}, id="year-kept"),
    pytest.param((2025, "18_25"), (2024, None), (2024, "18_25"),
                 kept_note(group="18_25", age=True), {"year": False, "age_group": True},
                 id="age-group-kept"),
    pytest.param((2025, "18_25"), (None, None), (2025, "18_25"),
                 kept_note(2025, "18_25", age=True), {"year": True, "age_group": True},
                 id="both-kept"),
    pytest.param((2025, None), (2024, None), (2024, None),
                 kept_note(group=None, age=True), {"year": False, "age_group": True},
                 id="all-ages-kept"),
])
def test_a_kept_value_is_noted_on_line_1(tmp_path, base, stated, counted, note, carried):
    """A5: a value from `base` is kept and AgentReply.carried records it; A7: line 1 then
    ends with ` (I kept <kept> from earlier.)` on the same line. The base turn was ANSWERED,
    so line 2 is the short tag."""
    env = Env(tmp_path)
    env.answered("How many arrests were there in that year?", (base[0], base[1]))
    reply = env.ask("And what about the other one?", Step(count(*stated)),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(ONE_COUNT_TEXT, one_count(*counted))
    assert reply.text == line1 + note + "\n" + LINE2_LATER
    assert reply.carried == carried


def test_a_pending_value_is_noted_and_the_answer_is_still_the_first(tmp_path):
    """A5: a value from `pending` is kept too. The NEEDS_INPUT turn before it was not an
    ANSWERED turn, so line 2 is LINE2_FIRST (A7)."""
    env = Env(tmp_path)
    env.pending("How many arrests were there for ages 18 to 25?", "18_25")
    reply = env.ask("2025", Step(count(2025, None)), Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(ONE_COUNT_TEXT, one_count(2025, "18_25"))
    assert reply.text == line1 + kept_note(group="18_25", age=True) + "\n" + LINE2_FIRST
    assert reply.carried == {"year": False, "age_group": True}


def test_a_chained_compare_after_an_answer_notes_the_kept_age_group(tmp_path):
    """A5 and A7: after an answer, two counts with no age group stated, a compare and a
    passing finish: both counts take the age group from `base`, line 1 is the filled text,
    then the kept note, then the short tag. Every count is filled from base the same way,
    so only one note is possible."""
    env = Env(tmp_path)
    env.answered(QUESTION, (2025, "18_25"))
    reply = env.ask("Compare 2024 and 2025.", Step(count(2024, None), count(2025, None)),
                    Step(compare("r1", "r2")), Step(finish("finding", CHAIN_TEXT)))
    check_reply(reply, env.model)
    assert_finding(reply, "agent")
    line1 = fill_expect(CHAIN_TEXT, chain_phrases([(2024, "18_25"), (2025, "18_25")]))
    assert reply.text == line1 + kept_note(group="18_25", age=True) + "\n" + LINE2_LATER
    assert reply.carried == {"year": False, "age_group": True}


def test_the_kept_note_follows_the_fixed_rendering_too(tmp_path):
    """A7: the kept note goes after line 1 of any ANSWERED reply, the fixed rendering
    included."""
    env = Env(tmp_path)
    env.answered(QUESTION, (2025, "18_25"))
    text = f"I counted {{r1.count}}, not {TYPED}."
    reply = env.ask("and for people under 18?", Step(count(None, "under_18")),
                    Step(finish("finding", text)))
    check_reply(reply, env.model)
    assert_finding(reply, "fallback")
    assert "CHARS" in reply.draft_failures
    assert_answered(reply.text, fixed_line1_re([(2025, "under_18")]), kept=kept_note(2025),
                    first=False)


# ---- a failing finding (R1, R9) -----------------------------------------------------------
# Each text is the model's finish after one count (2025, ages 18 to 25). Each fails with the
# given code (other codes may come too: the zqx mark is a word the list lacks). Each holds
# the mark, so check_reply shows that no part of it reached the reply; the reply is also
# exactly Python's fixed text.

FAILING_FINDINGS = [
    pytest.param("SLOT", f"I counted them ({MARK}).", id="SLOT-no-fact-slot"),
    pytest.param("SLOT", f"I counted {{r1.total}} ({MARK}).", id="SLOT-old-slot"),
    pytest.param("SLOT", f"I counted {{r1.count}}. I counted {{r1.count}} ({MARK}).",
                 id="SLOT-twice"),
    pytest.param("SLOT", f"I counted {{r9.count}} ({MARK}).", id="SLOT-unknown-result"),
    pytest.param("GLUE", f"I counted {{r1.count}}{{r1.months}} ({MARK}).", id="GLUE-slots"),
    pytest.param("GLUE", f"I counted -{{r1.count}} ({MARK}).", id="GLUE-sign"),
    pytest.param("CHARS", f"I counted {{r1.count}}, not {TYPED} ({MARK}).", id="CHARS-digits"),
    pytest.param("CHARS", f"I counted {{r1.count}}.\nThat is the count ({MARK}).",
                 id="CHARS-line-break"),
    pytest.param("CHARS", f"I counted **{{r1.count}}** ({MARK}).", id="CHARS-markup"),
    pytest.param("WORD", f"I counted roughly {{r1.count}} ({MARK}).", id="WORD-roughly"),
    pytest.param("WORD", f"I counted {{r1.count}} for juveniles ({MARK}).", id="WORD-age"),
    pytest.param("SHAPE", f"I counted {{r1.count}}. Here it is. That is it. Thanks. Hello "
                          f"({MARK}).", id="SHAPE-five-sentences"),
]


@pytest.mark.parametrize("code, text", FAILING_FINDINGS)
def test_a_failing_finding_is_replaced_by_the_fixed_rendering(tmp_path, code, text):
    """R1: on a failed check, line 1 is render_fixed, style fallback, and draft_failures
    lists the codes. R9: nothing the model wrote appears in the reply (check_reply checks
    TYPED and the mark; the reply is exactly Python's text)."""
    if code == "CHARS":
        assert odd_chars(text), text
    if code == "WORD":
        assert set(unlisted_words(text)) - {MARK}, text
    env = Env(tmp_path)
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", text)))
    check_reply(reply, env.model)
    assert_finding(reply, "fallback")
    assert code in reply.draft_failures, reply.draft_failures
    assert set(reply.draft_failures) <= R1_CODES, reply.draft_failures  # old codes gone (R1)
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)


@pytest.mark.parametrize("compared, code, text", [
    pytest.param(False, "WORD",
                 f"I counted {{r1.count}}, more than {{r2.count}} ({MARK}).",
                 id="WORD-direction-with-no-compare"),
    pytest.param(True, "CHARS",
                 f"Here is the comparison: {{r3.compare}}, {TYPED} above the lowest ({MARK}).",
                 id="CHARS-with-compare"),
])
def test_a_failing_finding_after_two_counts_gets_their_fixed_rendering(tmp_path, compared,
                                                                       code, text):
    """A7 render_fixed: two count results give each one's first sentence and no months
    sentence; with a compare result, the compare sentence follows (A6 labels: the years)."""
    pair = [(2024, "under_18"), (2025, "under_18")]
    steps = [Step(count(2024, "under_18"), count(2025, "under_18"))]
    if compared:
        steps.append(Step(compare("r1", "r2")))
    env = Env(tmp_path)
    reply = env.ask("Compare 2024 and 2025 for people under 18.", *steps,
                    Step(finish("finding", text)))
    check_reply(reply, env.model)
    assert_finding(reply, "fallback")
    assert code in reply.draft_failures, reply.draft_failures
    assert set(reply.draft_failures) <= R1_CODES, reply.draft_failures
    compares = [compare_expect([(y, g, total(y, g)) for y, g in pair])] if compared else []
    assert_answered(reply.text, fixed_line1_re(pair, compares), first=True)


def test_a_slot_of_an_earlier_turns_result_fails(tmp_path):
    """R1 SLOT and R9 "a slot of another turn": the earlier turn had r1 and r2; this turn
    has only r1, so {r2.count} is not offered: the fixed rendering of this turn's count."""
    env = Env(tmp_path)
    env.answered("Compare 2024 and 2025 for people under 18.", (2024, "under_18"),
                 (2025, "under_18"))
    reply = env.ask("And for ages 18 to 25 in 2025?", Step(count(2025, "18_25")),
                    Step(finish("finding", "I counted {r1.count} and {r2.count}.")))
    check_reply(reply, env.model)
    assert_finding(reply, "fallback")
    assert "SLOT" in reply.draft_failures, reply.draft_failures
    assert set(reply.draft_failures) <= R1_CODES, reply.draft_failures
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=False)


# ---- MOCO_REPLY_STYLE = fixed (A7) --------------------------------------------------------

@pytest.mark.parametrize("text", [
    pytest.param("Here is the count for you: {r1.count}.", id="passing-text"),
    pytest.param(f"Here is the count for you: {{r1.count}}, not {TYPED} ({MARK}).",
                 id="failing-text"),
])
def test_reply_style_fixed_never_uses_the_text(tmp_path, text):
    """A7 and R1: with MOCO_REPLY_STYLE at fixed, the text is never used: line 1 is
    render_fixed and the style is fixed."""
    env = Env(tmp_path, MOCO_REPLY_STYLE="fixed")
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", text)))
    check_reply(reply, env.model)
    assert_finding(reply, "fixed")
    assert "count for you" not in reply.text
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)


# ---- about_data (R1) ----------------------------------------------------------------------

def plain_fact():
    """A fact line of one sentence without the word SYNTHETIC."""
    return single_sentence_facts()[0]


def test_about_data_passing_without_synthetic_gets_data_tag(tmp_path):
    """R1: after describe_data, a text that passes is sent as fill(text, [], registry,
    facts), with DATA_TAG added when the filled text lacks SYNTHETIC; status EXPLAINED, style
    agent (the checked text is used), kind about_data. Joined by a space or a line break
    (A7 does not say which)."""
    text = about_text(plain_fact())
    filled = fill_expect(text, fact_slots())
    assert "SYNTHETIC" not in filled
    env = Env(tmp_path)
    reply = env.ask("What data do you have?", Step(describe()),
                    Step(finish("about_data", text)))
    check_reply(reply, env.model)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_kind == "about_data"
    assert reply.reply_style == "agent"
    assert re.fullmatch(re.escape(filled) + "[ \n]" + re.escape(DATA_TAG), reply.text), \
        reply.text


def test_about_data_passing_with_synthetic_is_sent_as_is(tmp_path):
    """R1: DATA_TAG is added only when the filled text lacks SYNTHETIC: a fact line that
    holds it makes the reply the filled text alone."""
    text = about_text(synthetic_fact(), plain_fact())
    filled = fill_expect(text, fact_slots())
    assert "SYNTHETIC" in filled
    env = Env(tmp_path)
    reply = env.ask("What data do you have?", Step(describe()),
                    Step(finish("about_data", text)))
    check_reply(reply, env.model)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_kind == "about_data"
    assert reply.reply_style == "agent"
    assert reply.text == filled


def test_about_data_without_describe_data_is_the_fixed_about_text(tmp_path):
    """A7 and R1: without describe_data in this turn the reply is the fixed ABOUT text,
    style fallback, even for a text that would pass."""
    env = Env(tmp_path)
    reply = env.ask("What data do you have?",
                    Step(finish("about_data", about_text(plain_fact()))))
    check_reply(reply, env.model)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "fallback"
    assert reply.reply_kind in ("about_data", None)  # accepted both ways, as BACKGROUND_OFF
    assert_fixed(reply.text, "ABOUT")


def failing_about(code):
    """An about_data text that fails with `code` (R1), holding the zqx mark."""
    a, b, c, d, e = single_sentence_facts()[:5]
    return {
        "SLOT": f"Here is what I know: {{r1.count}} ({MARK}).",
        "GLUE": f"Here is what I know:{{f{a}}} ({MARK}).",
        "CHARS": f"It holds {TYPED} records ({MARK}). {{f{a}}}.",
        "WORD": f"Here is what I know for certain ({MARK}): {{f{a}}}.",
        "SHAPE": f"{{f{a}}} and {{f{b}}}. {{f{c}}} and {{f{d}}}. {{f{e}}} ({MARK}).",
    }[code]


@pytest.mark.parametrize("code", ["SLOT", "GLUE", "CHARS", "WORD", "SHAPE"])
def test_about_data_failing_the_check_is_the_fixed_about_text(tmp_path, code):
    """R1: when check_about fails, the reply is the fixed ABOUT text, style fallback, and
    nothing of the model's text is in it. A9: the turn record holds the check's failure
    code (R1's code, so the failing rule is the one named)."""
    env = Env(tmp_path)
    reply = env.ask("What data do you have?", Step(describe()),
                    Step(finish("about_data", failing_about(code))))
    check_reply(reply, env.model)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "fallback"
    assert reply.reply_kind in ("about_data", None)
    assert_fixed(reply.text, "ABOUT")
    assert has_leaf(turn_record(reply, env.runs_dir), code), f"{code} is not in turn.json"


@pytest.mark.parametrize("kind, text, passes", [
    pytest.param("about_data", ONE_COUNT_TEXT, True, id="about_data-passing"),
    pytest.param("background", ONE_COUNT_TEXT, True, id="background-passing"),
    pytest.param("about_data", NO_SLOT_TEXT, False, id="about_data-no-fact-slot"),
    pytest.param("background", BACKGROUND_TEXT, False, id="background-no-fact-slot"),
])
def test_about_data_or_background_with_results_is_a_finding(tmp_path, kind, text, passes):
    """A7 and R1: finish with kind about_data or background in a turn that has results is
    treated as finding: checked by check_finding, filled or replaced by the fixed
    rendering. (MOCO_BACKGROUND is off: the finding rule comes first.)"""
    env = Env(tmp_path)
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish(kind, text)))
    check_reply(reply, env.model)
    if passes:
        assert_finding(reply, "agent")
        line1 = fill_expect(ONE_COUNT_TEXT, one_count(2025, "18_25"))
        assert reply.text == line1 + "\n" + LINE2_FIRST
    else:
        assert_finding(reply, "fallback")
        assert "SLOT" in reply.draft_failures, reply.draft_failures
        assert set(reply.draft_failures) <= R1_CODES, reply.draft_failures
        assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)


# ---- background (A7) ----------------------------------------------------------------------

@pytest.mark.parametrize("setting", [pytest.param({}, id="default"),
                                     pytest.param({"MOCO_BACKGROUND": "off"}, id="off")])
def test_background_off_gives_the_fixed_refusal(tmp_path, setting):
    """A7: MOCO_BACKGROUND off (the default): UNSUPPORTED / BACKGROUND_OFF with the fixed
    text, whatever the model wrote."""
    assert listed("hedge_words", "may")
    env = Env(tmp_path, **setting)
    text = f"{BACKGROUND_TEXT[:-1]} ({MARK})."
    reply = env.ask("Why do arrest counts change over a year?",
                    Step(finish("background", text)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "BACKGROUND_OFF"), reply.text
    assert reply.reply_kind in ("background", None)  # accepted both ways (notes)
    assert_fixed(reply.text, "BACKGROUND_OFF")


def test_background_on_and_passing_is_wrapped(tmp_path):
    """A7: on and passing: BACKGROUND_PREFIX + the text + BACKGROUND_SUFFIX, status
    EXPLAINED, style agent, kind background."""
    assert listed("hedge_words", "may")
    env = Env(tmp_path, MOCO_BACKGROUND="on")
    reply = env.ask("Why do arrest counts change over a year?",
                    Step(finish("background", BACKGROUND_TEXT)))
    check_reply(reply, env.model)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_kind == "background"
    assert reply.reply_style == "agent"
    assert reply.text == BACKGROUND_PREFIX + BACKGROUND_TEXT + BACKGROUND_SUFFIX


@pytest.mark.parametrize("text, rule_list, word", [
    pytest.param(f"Arrest counts may change by {TYPED} for many reasons ({MARK}).", None,
                 None, id="NUMBER"),
    pytest.param(f"Studies show that arrest counts may change for many reasons ({MARK}).",
                 "certain_words", "studies show", id="CERTAIN"),
    pytest.param(f"The county should count arrests, which may change ({MARK}).",
                 "advice_words", "the county should", id="ADVICE"),
    pytest.param(f"Arrest counts may change, as {{r1.total}} did ({MARK}).", None, None,
                 id="SLOT"),
    pytest.param(f"Arrest counts may change.\nThey may change for many reasons ({MARK}).",
                 None, None, id="SHAPE-line-break"),
])
def test_background_on_and_failing_gives_the_fixed_text(tmp_path, text, rule_list, word):
    """A7: on and the check failed: the same fixed text as off, style fallback. The status
    is not given for this case: UNSUPPORTED or EXPLAINED are both accepted."""
    assert_listed(rule_list, word)
    check_background_on_failing(tmp_path, text)


def test_background_on_with_no_hedge_word_gives_the_fixed_text(tmp_path):
    """A7: HEDGE, a background text with none of hedge_words (each word and pair of words
    of it is checked against the list), fails like the others."""
    text = f"Arrest counts change over a year for many reasons ({MARK})."
    words = re.findall(r"[a-z]+", text.lower())
    phrases = {" ".join(words[i:i + n]) for n in (1, 2) for i in range(len(words) - n + 1)}
    assert not any(listed("hedge_words", p) for p in phrases)
    check_background_on_failing(tmp_path, text)


def check_background_on_failing(tmp_path, text):
    env = Env(tmp_path, MOCO_BACKGROUND="on")
    reply = env.ask("Why do arrest counts change over a year?",
                    Step(finish("background", text)))
    check_reply(reply, env.model)
    assert reply.status in ("UNSUPPORTED", "EXPLAINED"), (reply.status, reply.reason_code)
    assert reply.reply_style == "fallback"
    assert_fixed(reply.text, "BACKGROUND_OFF")


# ---- decline (A7) -------------------------------------------------------------------------

@pytest.mark.parametrize("code", DECLINE_CODES)
def test_decline_gives_its_row_word_for_word(tmp_path, code):
    """A7: decline uses the row for its code: UNSUPPORTED with that code."""
    env = Env(tmp_path)
    reply = env.ask("Can you help me with something?", Step(decline(code)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), reply.text
    assert reply.model_called
    assert_fixed(reply.text, code)


def test_a_decline_after_results_is_answered_with_the_fixed_rendering(tmp_path):
    """A7: a decline in a turn that already has results is not obeyed: ANSWERED with the
    fixed rendering and DECLINED_AFTER_RESULTS in draft_failures. Style fallback or fixed,
    kind finding or None (accepted both ways)."""
    env = Env(tmp_path)
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(decline("UNSUPPORTED_METRIC")))
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert "DECLINED_AFTER_RESULTS" in reply.draft_failures, reply.draft_failures
    assert reply.reply_style in ("fallback", "fixed")
    assert reply.reply_kind in ("finding", None)
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)


# ---- every other fixed row, by its real path (A4, A5, A7) ---------------------------------

@pytest.mark.parametrize("path", ["finish-with-no-result", "empty-question", "guard-rule-1"])
def test_the_unrecognized_row_by_its_other_paths(tmp_path, path):
    """A7: finish(finding) with no result; A4 step 1: an empty question; A2: stage 1's rule
    1 refuses with no model call. Each gives the UNRECOGNIZED_QUESTION row."""
    env = Env(tmp_path)
    if path == "finish-with-no-result":
        reply = env.ask("Can you help me with something?",
                        Step(finish("finding", ONE_COUNT_TEXT)))
    elif path == "empty-question":
        reply = env.ask("")
    else:
        question, code = REFUSED["U6"]
        assert code == "UNRECOGNIZED_QUESTION"
        reply = env.ask(question, Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNRECOGNIZED_QUESTION")
    assert reply.model_called is (path == "finish-with-no-result")
    assert_fixed(reply.text, "UNRECOGNIZED_QUESTION")


@pytest.mark.parametrize("counts, status, code", [
    pytest.param([count(2019, "all")], "UNSUPPORTED", "OUT_OF_COVERAGE", id="one-2019-count"),
    pytest.param([count(2019, "all"), count(2030, "under_18")], "UNSUPPORTED",
                 "OUT_OF_COVERAGE", id="two-years-out-of-coverage"),
    pytest.param([count("last year", "all")], "ERROR", "INVALID_ARGUMENTS", id="year-as-words"),
    pytest.param([count(2025, "ages_30_35")], "ERROR", "INVALID_ARGUMENTS",
                 id="unknown-age-group"),
])
def test_finish_after_only_failed_counts_gives_that_codes_row(tmp_path, counts, status, code):
    """A7: when the model ends a turn with finish but every count returned an error, the row
    for that error code is used (A4: OUT_OF_COVERAGE is UNSUPPORTED, INVALID_ARGUMENTS is
    ERROR). A5: a year that is not four digits goes to stage 1's strict check unchanged."""
    env = Env(tmp_path)
    reply = env.ask("How many arrests were there?", Step(*counts),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == (status, code), reply.text
    assert_fixed(reply.text, code)


@pytest.mark.parametrize("limit", [None, 40])
def test_input_too_long_names_the_limit(tmp_path, limit):
    """A4 step 1 and A7: longer than MOCO_MAX_QUESTION_CHARS (the default, or a set value):
    UNSUPPORTED / INPUT_TOO_LONG with the limit in the text, and no model call."""
    settings = {} if limit is None else {"MOCO_MAX_QUESTION_CHARS": limit}
    limit = DEFAULT_MAX_QUESTION_CHARS if limit is None else limit
    env = Env(tmp_path, **settings)
    reply = env.ask("a" * (limit + 1), Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "INPUT_TOO_LONG"), reply.text
    assert not reply.model_called
    assert_fixed(reply.text, "INPUT_TOO_LONG", limit=limit)


@pytest.mark.parametrize("steps, row", [
    pytest.param([Step(ask_user("year"))], "NEEDS_year", id="ask_user-year"),
    pytest.param([Step(count(None, "18_25"))], "NEEDS_year", id="count-with-no-year"),
    pytest.param([Step(ask_user("age_group"))], "NEEDS_age_group", id="ask_user-age_group"),
    pytest.param([Step(ask_user("other"))], "NEEDS_other", id="ask_user-other"),
    pytest.param([Step(ask_user("weather"))], "NEEDS_other", id="ask_user-unlisted-value"),
])
def test_needs_clarification_rows(tmp_path, steps, row):
    """A5: in a fresh thread, ask_user and a count with no year anywhere end the turn as
    NEEDS_INPUT / NEEDS_CLARIFICATION; Python writes the question (A7 rows). An unlisted
    `missing` counts as other."""
    env = Env(tmp_path)
    reply = env.ask("How many arrests were there for ages 18 to 25?", *steps)
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION")
    assert_fixed(reply.text, row)


@pytest.mark.parametrize("start, end, years_text", [
    pytest.param("2030-01-01", "2030-12-31", "2030", id="only-2030"),
    pytest.param("2024-01-01", "2027-12-31", "2024 to 2027", id="2024-to-2027"),
])
def test_the_year_question_reads_the_years_from_the_registry(tmp_path, start, end,
                                                             years_text):
    """A7: <years> comes from the registry's coverage (`2024`; `2024 or 2025`; `2024 to
    2027`)."""
    def change(data):
        data["approved_sources"][0]["coverage"] = {"start": start, "end": end}

    path = registry_copy(tmp_path, change)
    data = json.loads(path.read_text(encoding="utf-8"))
    env = Env(tmp_path, registry=load_registry(path))
    reply = env.ask("How many arrests were there?", Step(ask_user("year")))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION")
    assert reply.text == f"Which year do you mean, {years_text}?"
    assert_fixed(reply.text, "NEEDS_year", data=data)


def _wider_coverage(data):
    data["approved_sources"][0]["coverage"] = {"start": "2024-01-01", "end": "2027-12-31"}


def _other_wording(data):
    data["approved_sources"][0]["age_groups"]["41_plus"] = "ages 41 and up"


@pytest.mark.parametrize("change, steps, row", [
    pytest.param(_wider_coverage, [Step(ask_user("other"))], "NEEDS_other",
                 id="CAN_ASK-years"),
    pytest.param(_wider_coverage, [Step(finish("about_data", NO_SLOT_TEXT))], "ABOUT",
                 id="ABOUT-years"),
    pytest.param(_other_wording, [Step(ask_user("age_group"))], "NEEDS_age_group",
                 id="groups-wording"),
    pytest.param(_other_wording, [Step(decline("UNSUPPORTED_FIELD"))], "UNSUPPORTED_FIELD",
                 id="CAN_ASK-groups"),
])
def test_fixed_wording_reads_years_and_groups_from_the_registry(tmp_path, change, steps,
                                                                row):
    """A7: <years> and <groups> (the registry's wordings joined) come from the registry, in
    CAN_ASK, ABOUT and the age group question."""
    path = registry_copy(tmp_path, change)
    data = json.loads(path.read_text(encoding="utf-8"))
    env = Env(tmp_path, registry=load_registry(path))
    reply = env.ask("Can you help me with something?", *steps)
    check_reply(reply, env.model)
    assert_fixed(reply.text, row, data=data)


def test_model_unavailable_with_no_result_gives_its_row(tmp_path):
    """A4 step 5: ModelUnavailable with no results: ERROR / MODEL_UNAVAILABLE, the row."""
    env = Env(tmp_path)
    error = mod("llm").ModelUnavailable("the model is down for this test")
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), error=error)
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("ERROR", "MODEL_UNAVAILABLE"), reply.text
    assert_fixed(reply.text, "MODEL_UNAVAILABLE")


@pytest.mark.parametrize("limit", ["step-limit", "time-limit"])
def test_a_limit_with_no_result_gives_the_bad_output_row(tmp_path, limit):
    """A4 step 5: the step limit (MOCO_MAX_STEPS, default 6; a step with neither text nor a
    tool call counts) or the time limit (MOCO_TURN_SECONDS, default 90, on the injected
    clock) with no results: ERROR / MODEL_BAD_OUTPUT, the row."""
    env = Env(tmp_path)
    if limit == "step-limit":
        reply = env.ask(QUESTION, Step())
    else:
        reply = env.ask(QUESTION, Step(describe()), seconds=100)
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("ERROR", "MODEL_BAD_OUTPUT"), reply.text
    assert_fixed(reply.text, "MODEL_BAD_OUTPUT")


def test_the_daily_cap_gives_the_rate_limited_row(tmp_path):
    """A4 step 4 (as P1): with MOCO_DAILY_MODEL_CALLS at 1, the second turn of the UTC day
    that would call the model is ERROR / RATE_LIMITED, with no model call."""
    env = Env(tmp_path, MOCO_DAILY_MODEL_CALLS=1)
    env.answered(QUESTION, (2025, "18_25"))
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("ERROR", "RATE_LIMITED"), reply.text
    assert not reply.model_called
    assert_fixed(reply.text, "RATE_LIMITED")


@pytest.mark.parametrize("code", ["DATA_CLASS_MISMATCH", "DATA_UNREADABLE"])
def test_a_bad_data_file_ends_the_turn_with_its_row(tmp_path, code):
    """A3: DATA_CLASS_MISMATCH or DATA_UNREADABLE from count_arrests ends the turn with that
    code's fixed text (A4: status ERROR)."""
    if code == "DATA_CLASS_MISMATCH":
        data_path = NOT_SYNTHETIC_COPIES["middle_row_REAL"](tmp_path)
    else:
        data_path = tmp_path / "no-such-data.csv"
    env = Env(tmp_path, data_path=data_path)
    reply = env.ask(QUESTION, Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("ERROR", code), reply.text
    assert_fixed(reply.text, code)
