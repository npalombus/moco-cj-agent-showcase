"""T2 of docs/T-DESIGN.md, and T7's third point: with MOCO_TALK on, a finding (and an
about_data text) is checked sentence by sentence. A fact sentence holds a slot and is
checked by R1 and C13 as today; a talk sentence holds none and is checked by the talk
check's NUMBER, LABEL, CLAIM and CHARS, and by JUDGE; the whole text by SLOT, ORDER and
SHAPE.

What this file covers
- Each example of T2 as a whole string: the one that passes (sent filled, style agent,
  with line 2 after it as today) and the three that fail (JUDGE, CLAIM, NUMBER).
- Every code both ways, in SYNTHETIC mode with one count of 2025, ages 18 to 25: SLOT,
  GLUE, CHARS and WORD in a fact sentence as today; NUMBER, LABEL, CLAIM, CHARS and JUDGE
  in a talk sentence; ORDER; SHAPE.
- That a word outside R1's list passes in a talk sentence and still fails WORD in a fact
  sentence; that a dash passes in a fact sentence (R1's marks) and, since round 2 (T11),
  in a talk sentence too, where a quotation mark now passes as well; that a judgement word
  in a fact sentence is a WORD.
- ORDER for {rN.months} with two counts, and for {rN.groups} in county mode.
- The limits at their edges: four fact sentences and two talk sentences pass, five fact
  sentences or three talk sentences fail; 700 characters once filled pass and 701 fail; a
  line break now passes (round 2, T10: tidied to a space).
- about_data the same way, and a county finding with sentences of its own.
- Round 2's changes here are listed in kit-log/raw/T2-A-changed-tests.txt.

Read through T3 (tsupport.first_try): a failing text's codes are the `problems` of
Python's REWRITE answer. Accepted both ways (kit-log/raw/T-A-notes.txt): a digit in a talk
sentence may bring CHARS with NUMBER; a line break may bring CHARS with SHAPE; an age
wording brings NUMBER with LABEL; an empty text may bring SLOT with SHAPE. Those are
checked with the code among the codes. Sentences are counted as R1 counts them.
"""
import re

import pytest

from p1support import (DATA_TAG, Step, assert_answered, compare, count,
                       count_slots, describe, fact_slots, fill_expect, finish,
                       single_sentence_facts, unlisted_words)
from s3support import A_ID, Q_BREAKDOWN, Q_COUNT, SCHOOL, count as county_count, is_, year
from tsupport import (FINDING_CODES, check_cases, county_labels, county_talk_env, first_try,
                      mixed_faults, padded, split_sentences, synthetic_labels, talk_env,
                      talk_rules, thread)

Q = "How many arrests were recorded each month in 2025 for ages 18 to 25?"
Q2 = "Compare 2024 and 2025 for people under 18."
ONE = (Step(count(2025, "18_25")),)
TWO = (Step(count(2024, "under_18"), count(2025, "under_18")), Step(compare("r1", "r2")))
CONTENT = {"WORD", "CHARS", "NUMBER", "LABEL", "CLAIM", "JUDGE"}
EXAMPLE = "Here you go. I counted {r1.count}. {r1.months}. Want it compared with another year?"


def premise(text, want, labels=None):
    """The content faults of a test's own text (tsupport.mixed_faults) are what its case
    says: none for None or for a code that is not about content, exactly the code of a str,
    the content codes of a set among others."""
    got = mixed_faults(text, synthetic_labels() if labels is None else labels)
    if want is None:
        assert got == set(), (text, got)
    elif isinstance(want, str):
        assert got == {want} & CONTENT, (text, got)
    else:
        assert set(want) & CONTENT <= got, (text, got)


def run_on(env, question, before, kind="finding"):
    return lambda i, text: first_try(env, question, kind, text, *before, thread_key=thread(i))


# ---- the examples of T2, each as a whole string ------------------------------------------------

def test_the_passing_example_is_sent_filled(tmp_path):
    """T2: `Here you go. I counted {r1.count}. {r1.months}. Want it compared with another
    year?` passes: ANSWERED, kind finding, style agent; line 1 is the text filled (R1),
    and what Python adds after line 1 is unchanged (line 2 of a first answer)."""
    premise(EXAMPLE, None)
    facts, talks = split_sentences(EXAMPLE)
    assert (len(facts), len(talks)) == (2, 2)
    env = talk_env(tmp_path)
    reply = env.ask(Q, *ONE, Step(finish("finding", EXAMPLE)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("ANSWERED", "finding", "agent"), (reply.status, reply.reply_style, reply.text)
    assert len(env.model.calls) == 2
    line1 = fill_expect(EXAMPLE, count_slots("r1", 2025, "18_25"))
    assert line1.startswith("Here you go. I counted ") and line1.endswith(
        ". Want it compared with another year?")
    assert_answered(reply.text, re.escape(line1), first=True)


@pytest.mark.parametrize("text, code", [
    ("I counted {r1.count}. That is a lot.", "JUDGE"),
    ("I counted {r1.count}. It went up because of summer.", "CLAIM"),
    ("I counted {r1.count}. Twice last year.", "NUMBER"),
], ids=["JUDGE", "CLAIM", "NUMBER"])
def test_the_failing_examples_fail_with_their_code(tmp_path, text, code):
    """T2: each example that fails, as written in the contract, fails with exactly its
    code."""
    premise(text, code)
    check_cases(run_on(talk_env(tmp_path), Q, ONE), [(text, code)], FINDING_CODES)


# ---- every code, both ways -------------------------------------------------------------------------

CASES = {
    "SLOT": [
        ("Here you go. Want more?", "SLOT"),
        ("I counted {r1.count}. Nice to see you. I counted {r1.count}.", "SLOT"),
        ("Here you go. I counted {r2.count}.", {"SLOT"}),
        ("Here you go. I counted {r1.count}.", None),
    ],
    "GLUE": [
        ("Here you go. I counted {r1.count} {r1.months}.", "GLUE"),
        ("Sure thing. I counted:{r1.count}.", "GLUE"),
        ("Sure thing. I counted {r1.count} and {r1.months}.", None),
    ],
    "CHARS-fact": [
        ('I "counted" {r1.count}. Happy to help.', "CHARS"),
        ("I counted {r1.count} . Happy to help.", "CHARS"),
        ("Sure — I counted {r1.count}.", None),
    ],
    "WORD": [
        ("I counted roughly {r1.count}. Happy to help.", "WORD"),
        ("Here you go: {r1.count}.", "WORD"),
        ("I counted only {r1.count}.", "WORD"),
        ("Lovely question. I counted {r1.count}.", None),
        ("Here you go. I counted {r1.count}.", None),
    ],
    "NUMBER": [
        ("I counted {r1.count}. {r1.months}. March stands out.", "NUMBER"),
        ("I counted {r1.count}. Say the word for a dozen more.", "NUMBER"),
        ("I counted {r1.count}. Over 9 more to come!", {"NUMBER"}),
        ("I counted {r1.count}. {r1.months}. May I help further?", None),
    ],
    "LABEL": [
        ("I counted {r1.count}. Want ages 26 to 40 next?", {"LABEL", "NUMBER"}),
        ("I counted {r1.count}. Want another age group next?", None),
    ],
    "CLAIM": [
        ("I counted {r1.count}. In fact, that is all.", "CLAIM"),
        ("I counted {r1.count}. This means something.", "CLAIM"),
        ("I counted {r1.count}. The records cannot say why.", None),
    ],
    "CHARS-talk": [
        ("I counted {r1.count}. Sure — glad to help.", None),    # round 2, T11: was CHARS
        ('I counted {r1.count}. Say "more" for more.', None),     # round 2, T11: was CHARS
        ("I counted {r1.count}. Sure - glad to help.", None),
        # Round 2: added, so the group still has a text that fails (markup, unchanged).
        ("I counted {r1.count}. Write to me @ any time.", "CHARS"),
    ],
    "JUDGE": [
        ("Only a quick look. I counted {r1.count}.", "JUDGE"),
        ("I counted {r1.count}. {r1.months}. Mostly in spring.", "JUDGE"),
        ("I counted {r1.count}. That was a big one!", "JUDGE"),
        ("I counted {r1.count}. That was a quick one!", None),
    ],
    "ORDER": [
        ("I counted {r1.count}. Thanks for waiting. {r1.months}.", "ORDER"),
        ("I counted {r1.count}. {r1.months}. Thanks for waiting.", None),
        ("Thanks for waiting. I counted {r1.count}. {r1.months}.", None),
    ],
    "SHAPE": [
        ("I counted {r1.count}.\nHappy to help.", None),  # round 2, T10 step 3: was SHAPE
        ("", {"SHAPE"}),
        ("Here you go. Hope it helps. I counted {r1.count}. Want more?", "SHAPE"),
        ("Here you go. I counted {r1.count}. {r1.months}. Want more?", None),
    ],
}


@pytest.mark.parametrize("group", list(CASES))
def test_each_code_both_ways(tmp_path, group):
    """T2: for each code, texts that fail with it and texts beside them that pass; fact
    sentences keep R1 and C13, talk sentences get NUMBER, LABEL, CLAIM, CHARS and JUDGE and
    no word list. Every code returned is one of R1's five or T2's five."""
    cases = CASES[group]
    for text, want in cases:
        premise(text, want)
    assert any(want is not None for _, want in cases) and any(want is None for _, want in cases)
    check_cases(run_on(talk_env(tmp_path), Q, ONE), cases, FINDING_CODES)


def test_a_word_off_the_list_passes_in_a_talk_sentence_and_fails_in_a_fact_sentence(tmp_path):
    """T2: "The whitelist does not" apply to a talk sentence; a fact sentence keeps it.
    The same words, in a sentence of their own and then beside the slot."""
    pairs = [("Lovely question, by the way. I counted {r1.count}.", None),
             ("I counted {r1.count}, lovely question by the way.", "WORD"),
             ("I counted {r1.count}. {r1.months}. Want it compared with another year?", None),
             ("I counted {r1.count}, want it compared with another year?", "WORD")]
    for text, want in pairs:
        premise(text, want)
    check_cases(run_on(talk_env(tmp_path), Q, ONE), pairs, FINDING_CODES)


# ---- ORDER with two results, and with {rN.groups} -------------------------------------------------

def test_order_between_a_count_and_its_months_with_two_counts(tmp_path):
    """T2 ORDER: no talk sentence between the sentence of {rN.count} and that of
    {rN.months}; a talk sentence between two results is fine."""
    cases = [("I counted {r1.count}. {r1.months}. Also. I counted {r2.count}. {r2.months}.", None),
             ("I counted {r1.count}. Also. {r1.months}. I counted {r2.count}. {r2.months}.",
              "ORDER"),
             ("I counted {r1.count}. {r1.months}. I counted {r2.count}. Hold on. {r2.months}.",
              "ORDER")]
    for text, want in cases:
        premise(text, want)
    check_cases(run_on(talk_env(tmp_path), Q2, TWO), cases, FINDING_CODES)


def test_order_between_a_count_and_its_groups_in_county_mode(tmp_path, monkeypatch):
    """T2 ORDER for {rN.groups} (county mode, a count of 2025 near a school by district)."""
    labels = county_labels("arrests_like")
    cases = [("I counted {r1.count}. Thanks for waiting. {r1.groups}.", "ORDER"),
             ("I counted {r1.count}. {r1.groups}. Thanks for waiting.", None)]
    for text, want in cases:
        premise(text, want, labels)
    env = county_talk_env(tmp_path, monkeypatch)
    before = (Step(county_count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"])),)
    check_cases(run_on(env, Q_BREAKDOWN, before), cases, FINDING_CODES)


# ---- the limits at their edges ------------------------------------------------------------------------

def test_four_fact_and_two_talk_sentences_pass_and_one_more_of_either_fails(tmp_path):
    """T2 SHAPE: at most 4 fact sentences and at most most_talk_sentences_in_finding (2) talk
    sentences. Two counts and a compare give five slots."""
    assert talk_rules()["most_talk_sentences_in_finding"] == 2
    six = "Here you go. {r1.count}. {r1.months}. {r2.count}. {r2.months}. Want more?"
    five_facts = "{r1.count}. {r1.months}. {r2.count}. {r2.months}. {r3.compare}."
    three_talks = "Here you go. Hope it helps. {r1.count}. {r1.months}. Want more?"
    counts = {text: tuple(map(len, split_sentences(text))) for text in (six, five_facts,
                                                                          three_talks)}
    assert counts == {six: (4, 2), five_facts: (5, 0), three_talks: (2, 3)}
    cases = [(six, None), (five_facts, "SHAPE"), (three_talks, "SHAPE")]
    for text, want in cases:
        premise(text, want)
    check_cases(run_on(talk_env(tmp_path), Q2, TWO), cases, FINDING_CODES)


def test_700_characters_once_filled_pass_and_701_fail(tmp_path):
    """T2 SHAPE: at most most_chars_finding (700) characters once filled. Both texts are
    two fact sentences and one long talk sentence of letters only."""
    assert talk_rules()["most_chars_finding"] == 700
    phrases = count_slots("r1", 2025, "18_25")

    def filled(text):
        return len(fill_expect(text, phrases))

    at = padded("I counted {r1.count}. {r1.months}. ", "", 700, measure=filled)
    over = padded("I counted {r1.count}. {r1.months}. ", "", 701, measure=filled)
    assert len(at) < 700 and len(over) < 701  # the slots make the difference
    for text in (at, over):
        premise(text, None if text is at else "SHAPE")
    check_cases(run_on(talk_env(tmp_path), Q, ONE), [(at, None), (over, "SHAPE")],
                FINDING_CODES)


# ---- about_data the same way --------------------------------------------------------------------------

def about_cases():
    a, b, c, d, e = single_sentence_facts()[:5]
    return [
        (f"Here is what I know. {{f{a}}}. Happy to help!", None),
        (f"Sadly, this is all I have. {{f{a}}}.", None),
        (f"Here is what I know. {{f{b}}}. Happy to help!", None),  # a fact naming age groups
        (f"Sadly, {{f{a}}}.", "WORD"),
        (f"Here is what I know. {{f{a}}}. It is only a little.", "JUDGE"),
        (f"Here is what I know, in two parts. {{f{a}}}. {{f{c}}}.", "NUMBER"),
        (f"Here is what I know. {{f{a}}}. In fact, that is it.", "CLAIM"),
        (f"Here is what I know — sorry. {{f{a}}}.", None),  # round 2, T11: was CHARS
        (f"Here is what I know. Hope it helps. {{f{a}}}. Ask again.", "SHAPE"),
        (f"{{f{a}}}. {{f{b}}}. {{f{c}}}. {{f{d}}}. {{f{e}}}.", "SHAPE"),
    ]


def test_about_data_is_checked_sentence_by_sentence(tmp_path):
    """T2 for about_data: talk sentences beside {fN} slots get the talk rules and JUDGE and
    no word list; fact sentences keep R1 (WORD); at most two talk sentences and four fact
    slots. A fact whose phrase names the age groups passes: only the model's own words are
    checked."""
    cases = about_cases()
    for text, want in cases:
        premise(text, want)
    check_cases(run_on(talk_env(tmp_path), "What data do you have?", (Step(describe()),),
                       kind="about_data"), cases, FINDING_CODES)


def test_a_passing_about_data_text_is_sent_as_today(tmp_path):
    """T2 with R1: a passing about_data text with a sentence of its own (words that are not
    on R1's list, so today's check would refuse it) is filled and gets DATA_TAG when it
    lacks SYNTHETIC; EXPLAINED, kind about_data, style agent."""
    text = about_cases()[1][0]
    assert text.startswith("Sadly, this is all I have. ")
    assert unlisted_words(text), "the premise: a word that R1's list does not have"
    filled = fill_expect(text, fact_slots())
    assert "SYNTHETIC" not in filled
    env = talk_env(tmp_path)
    reply = env.ask("What data do you have?", Step(describe()), Step(finish("about_data", text)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style, reply.text)
    assert re.fullmatch(re.escape(filled) + "[ \n]" + re.escape(DATA_TAG), reply.text), reply.text


# ---- a county finding ---------------------------------------------------------------------------------

def test_a_county_finding_with_sentences_of_its_own(tmp_path, monkeypatch):
    """T2 in county mode: a talk sentence passes and line 1 is sent filled, with the source
    line after it as today (C10); a talk sentence naming a label of the source fails
    LABEL."""
    labels = county_labels("arrests_like")
    good = "Here you go. I counted {r1.count}. Want a breakdown next?"
    bad = "I counted {r1.count}. Want the Hispanic records next?"
    premise(good, None, labels)
    premise(bad, "LABEL", labels)
    env = county_talk_env(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(county_count(A_ID, year(2025))), Step(finish("finding", good)))
    assert (reply.status, reply.reply_style) == ("ANSWERED", "agent"), reply.text
    assert reply.text.startswith("Here you go. I counted 240 arrest records in 2025. Want a "
                                 "breakdown next?"), reply.text
    assert "\n" in reply.text and "county open data" in reply.text.lower()
    before = (Step(county_count(A_ID, year(2025))),)
    check_cases(run_on(env, Q_COUNT, before), [(bad, "LABEL")], FINDING_CODES)

