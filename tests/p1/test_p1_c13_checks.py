"""The two repairs to R1's check, for both modes: docs/S3A-DESIGN.md C13. Added by the tests
session of brief S3A-A (C13: "The tests session adds tests for both").

1. Only `and` may join two slots in one sentence: when two slots stand in the same sentence,
   the text between them must be exactly " and " or ", and "; anything else there fails
   GLUE. Slots in different sentences are not affected (a sentence ends at ., ! or ?
   followed by white space or the end of the text, as R1 says).
2. No private-use character: any character from U+E000 to U+F8FF in the model's text fails
   CHARS.

These run in synthetic mode (the stage 2 turn, p1support.Env); county mode's slots get the
same rules in tests/s3/test_s3_reply.py. `results` is reply.results of one ANSWERED turn,
handed over unchanged, as in test_p1_reply_checks.py: r1 and r2 are counts of 2024 and 2025
for people under 18, r3 their compare.

Every text's premise is checked against the files first: its words are all on the list and
its marks are all allowed (p1support.unlisted_words, odd_chars), so a text meant to fail
only GLUE fails for the joining words alone.

Expected today (before the build): the GLUE texts below pass today's check, and so do the
texts with U+E000 (the build marks slots with that character inside its check), so those
tests fail until the build; the texts with other private-use characters already fail CHARS,
and the passing texts already pass.
"""
import itertools
from pathlib import Path

import pytest

from p1support import (R1_CODES, Env, Step, check_reply, compare, compare_expect, count,
                       fill_expect, count_slots, finish,
                       fixed_line1_re, assert_answered, mod, months, odd_chars,
                       single_sentence_facts, unlisted_words)

PAIR = [(2024, "under_18"), (2025, "under_18")]
QUESTION = "Compare 2024 and 2025 for people under 18."
_TURN = itertools.count()

# Rule 1: two slots in one sentence, joined by exactly " and " or ", and ": these pass.
JOINED_BY_AND = [
    "I counted {r1.count} and {r2.count}.",
    "I counted {r1.count}, and {r2.count}.",
    "{r1.count} and {r2.count}.",
    "I counted {r1.count}, and {r1.months}. I also counted {r2.count} and {r2.months}.",
    "I counted {r1.count} and {r2.count}. Here is the comparison: {r3.compare}.",
]
# Slots in different sentences: not affected (C13's own example first).
DIFFERENT_SENTENCES = [
    "I counted {r1.count}. {r1.months}. I also counted {r2.count}.",
    "I counted {r1.count}! Also {r2.count}.",
    "Here is the comparison: {r3.compare}. I counted {r1.count}.",
]
# Rule 1: two slots in one sentence with anything else between them: exactly GLUE.
NOT_JOINED_BY_AND = [
    "{r1.count} of the {r2.count}.",                       # C13's own example
    "I counted {r1.count} and also {r2.count}.",
    "I counted {r1.count}, also {r2.count}.",
    "I counted {r1.count}, so {r2.count}.",
    "I counted {r1.count} as {r2.count}.",
    "Here is the comparison: {r3.compare}, and here is {r1.count}.",
    "I counted {r1.count} and {r1.months}, and {r2.count} and also {r2.months}.",
]
# Rule 2: a private-use character anywhere in the text.
PRIVATE_USE = ["", "", ""]


def turn_results(tmp_path):
    """reply.results of one ANSWERED turn (r1, r2 counted; r3 their compare)."""
    folder = Path(tmp_path) / f"{next(_TURN)}-turn"
    folder.mkdir()
    reply = Env(folder).answered(QUESTION, *PAIR, compared=True)
    assert len(reply.results) == 3, reply.results
    return reply.results


def premise(text):
    assert not unlisted_words(text), (text, unlisted_words(text))
    assert not odd_chars(text), (text, odd_chars(text))


def codes_of(check, text):
    got = check(text)
    assert isinstance(got, list) and set(got) <= R1_CODES, got
    return set(got)


# ---- rule 1, in a finding ------------------------------------------------------------------

def test_two_slots_joined_by_and_still_pass(tmp_path):
    """C13 rule 1: " and " or ", and " between two slots of one sentence passes."""
    replies = mod("replies")
    results, words = turn_results(tmp_path), replies.load_words()
    for text in JOINED_BY_AND:
        premise(text)
        assert replies.check_finding(text, results, words) == [], text


def test_slots_in_different_sentences_are_not_affected(tmp_path):
    """C13 rule 1: "Slots in different sentences are not affected"."""
    replies = mod("replies")
    results, words = turn_results(tmp_path), replies.load_words()
    for text in DIFFERENT_SENTENCES:
        premise(text)
        assert replies.check_finding(text, results, words) == [], text


@pytest.mark.parametrize("text", NOT_JOINED_BY_AND)
def test_anything_else_between_two_slots_of_one_sentence_fails_glue(tmp_path, text):
    """C13 rule 1: anything other than " and " or ", and " between two slots of the same
    sentence fails GLUE, and only GLUE (every word is listed, every mark allowed)."""
    premise(text)
    replies = mod("replies")
    results = turn_results(tmp_path)
    check = lambda t: replies.check_finding(t, results, replies.load_words())  # noqa: E731
    assert codes_of(check, text) == {"GLUE"}, text


def test_a_slot_joined_by_more_than_and_is_sent_as_the_fixed_rendering(tmp_path):
    """C13 rule 1 end to end: `{r1.count} of the {r2.count}.` reads as one count being a part
    of the other; the reply is the fixed rendering (style fallback, GLUE)."""
    env = Env(tmp_path)
    reply = env.ask(QUESTION, Step(*[count(y, g) for y, g in PAIR]), Step(compare("r1", "r2")),
                    Step(finish("finding", "{r1.count} of the {r2.count}.")))
    check_reply(reply, env.model)
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert "GLUE" in reply.draft_failures, reply.draft_failures
    c = compare_expect([(y, g, sum(months(y, g))) for y, g in PAIR])
    assert_answered(reply.text, fixed_line1_re(PAIR, [c]), first=True)
    assert " of the " not in reply.text.split("\n")[0]


def test_two_slots_joined_by_and_end_to_end_are_filled(tmp_path):
    """C13 rule 1 leaves `and` alone: the text is used and filled (style agent)."""
    env = Env(tmp_path)
    text = "I counted {r1.count}, and {r2.count}."
    reply = env.ask(QUESTION, Step(*[count(y, g) for y, g in PAIR]), Step(finish("finding", text)))
    check_reply(reply, env.model)
    assert reply.reply_style == "agent", reply.draft_failures
    slots = {**count_slots("r1", *PAIR[0]), **count_slots("r2", *PAIR[1])}
    assert reply.text.split("\n")[0] == fill_expect(text, slots)


# ---- rule 1, in an about_data text --------------------------------------------------------

def test_rule_1_holds_for_about_data_too():
    """C13 is for R1's one check, so it holds for about_data texts (fact slots) too."""
    replies = mod("replies")
    facts, words = replies.load_facts(), replies.load_words()
    a, b = single_sentence_facts()[:2]
    for text in (f"{{f{a}}} and {{f{b}}}.", f"{{f{a}}}, and {{f{b}}}.",
                 f"{{f{a}}}. Also, {{f{b}}}."):
        premise(text)
        assert replies.check_about(text, facts, words) == [], text
    for text in (f"{{f{a}}}, also {{f{b}}}.", f"Here is what I know: {{f{a}}}, so {{f{b}}}.",
                 f"{{f{a}}} as {{f{b}}}."):
        premise(text)
        assert set(replies.check_about(text, facts, words)) == {"GLUE"}, text


# ---- rule 2 --------------------------------------------------------------------------------

@pytest.mark.parametrize("char", PRIVATE_USE, ids=["U+E000", "U+E123", "U+F8FF"])
def test_a_private_use_character_fails_chars(tmp_path, char):
    """C13 rule 2: any character from U+E000 to U+F8FF in the model's text fails CHARS. With
    the character standing alone (spaces round it) nothing else is wrong: exactly CHARS."""
    replies = mod("replies")
    results, words = turn_results(tmp_path), replies.load_words()
    check = lambda t: replies.check_finding(t, results, words)  # noqa: E731
    for text in (f"I counted {{r1.count}} {char}.", f"{char} I counted {{r1.count}}.",
                 f"I counted {{r1.count}} and {{r1.months}} {char}."):
        assert codes_of(check, text) == {"CHARS"}, (text, char)
    assert "CHARS" in codes_of(check, f"I counted {char}{{r1.count}}.")


@pytest.mark.parametrize("char", PRIVATE_USE, ids=["U+E000", "U+E123", "U+F8FF"])
def test_a_private_use_character_fails_chars_in_about_data(char):
    """C13 rule 2 holds for about_data texts too."""
    replies = mod("replies")
    (a,) = single_sentence_facts()[:1]
    assert set(replies.check_about(f"Here is what I know: {{f{a}}} {char}.",
                                   replies.load_facts(), replies.load_words())) == {"CHARS"}


def test_a_typed_private_use_character_never_reaches_the_reply(tmp_path):
    """C13 rule 2 end to end: the finding fails CHARS, the fixed rendering is sent, and the
    character is nowhere in the reply."""
    env = Env(tmp_path)
    reply = env.ask(QUESTION, Step(count(2025, "under_18")),
                    Step(finish("finding", "I counted {r1.count} .")))
    check_reply(reply, env.model)
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert "CHARS" in reply.draft_failures, reply.draft_failures
    assert not any("" <= ch <= "" for ch in reply.text)
    assert_answered(reply.text, fixed_line1_re([(2025, "under_18")]), first=True)
