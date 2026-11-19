"""Trick sentences against the new reply check (docs/P1A-R2-DESIGN.md R1 and R9; brief
P1A2-A point 4).

- The planning chat's 49 trick sentences (kit-log/raw/P1A-B-chat-adversarial.py), each
  rewritten for the new slots, every one failing check_finding. Where the old sentence used
  a slot that no longer exists, the nearest sentence with the new slots is used: the old
  {r1.total} becomes {r1.count}, two old value slots glued become {r1.count} and
  {r1.months} glued, the old year beside the wrong total becomes a typed year beside
  {r1.count}, and the old compare labels the wrong way round become two counts with a
  direction word. The old control sentence now fails too (its slots are gone); the new
  control, "I counted {r1.count}.", passes.
- R9's list: a digit, a number word, a month name, an age word, `per day`, `roughly`,
  `over`, `not`, `people`, a place name, an offense, a direction word, a judgement word, a
  second language, a slot glued to a letter, to a sign and to another slot, an old slot, a
  slot of another turn, {f1} in a finding and {r1.count} in an about_data text.
- Every trick sentence, end to end through agent.handle_question: the reply is exactly
  Python's fixed rendering and line 2, style fallback, the code in draft_failures, so
  nothing the model wrote reaches the reply.
- Every example sentence of config/agent_prompt_v2.md (the text after each "might read:"
  and the `{f1}. {f2}.` sentence) passes the new checks.

The results are those of the adversarial script: r1 counts 2025 for ages 18 to 25, r2
counts 2024 for ages 18 to 25, r3 compares them; numbers come from the truth file.

Each trick names the code it must fail with (other codes may come too: "fails the new
checks" is what R9 asks). A trick's own premise is checked against the word list file
first (p1support.unlisted_words, odd_chars): a WORD trick holds a word the list lacks, a
CHARS trick a mark R1 does not allow.
"""
import itertools
import re
from pathlib import Path

import pytest

from p1support import (AGENT_PROMPT_MD, R1_CODES, Env, Step, compare, compare_expect, count, finish,
                       fixed_line1_re, assert_answered, check_reply, fact_lines, mod,
                       months, odd_chars, unlisted_words)

QUESTION = "Compare 2024 and 2025 for ages 18 to 25."
PAIR = [(2025, "18_25"), (2024, "18_25")]
_TURN = itertools.count()

# (name, text, codes it must fail with among its codes)
TRICKS = [
    ("old control (its slots are gone)",
     "In {r1.year} there were {r1.total} arrest records for {r1.age}.", {"SLOT"}),
    ("two slots glued", "There were {r1.count}{r1.months}.", {"GLUE"}),
    ("two slots, comma", "There were {r1.count},{r1.months}.", {"GLUE"}),
    ("two slots, dot", "There were {r1.count}.{r1.months}.", {"GLUE"}),
    ("two slots, space", "There were {r1.count} {r1.months}.", {"GLUE"}),
    ("year glued to total: two counts glued", "There were {r2.count}{r1.count}.", {"GLUE"}),
    ("k suffix", "There were {r1.count}k.", {"GLUE"}),
    ("K suffix spaced", "There were {r1.count} K.", {"WORD"}),
    ("x suffix (times)", "There were {r1.count}x.", {"GLUE"}),
    ("minus sign", "The change was -{r1.count}.", {"GLUE"}),
    ("plus sign", "There were {r1.count}+.", {"GLUE", "CHARS"}),
    ("superscript", "There were {r1.count}².", {"GLUE", "CHARS"}),
    ("fraction char", "There were {r1.count}½.", {"GLUE", "CHARS"}),
    ("roman numeral char", "There were Ⅻ arrest records and {r1.count}.", {"CHARS"}),
    ("fullwidth digits", "There were ４００ arrest records, {r1.count}.",
     {"CHARS"}),
    ("word one", "There was one arrest record beyond {r1.count}.", {"WORD"}),
    ("word zero/no", "There were zero arrest records beyond {r1.count}.", {"WORD"}),
    ("several/few/many", "There were many arrest records, {r1.count}.", {"WORD"}),
    ("about/roughly", "There were roughly {r1.count}.", {"WORD"}),
    ("nearly/almost", "There were nearly {r1.count}.", {"WORD"}),
    ("over/above", "There were over {r1.count}.", {"WORD"}),
    ("at least", "There were at least {r1.count}.", {"WORD"}),
    ("under/below", "There were under {r1.count}.", {"WORD"}),
    ("up to", "There were up to {r1.count}.", {"WORD"}),
    ("per day", "There were {r1.count} per day.", {"WORD"}),
    ("each month (false scope)", "There were {r1.count} each month.", {"WORD"}),
    ("daily", "There were {r1.count} daily.", {"WORD"}),
    ("wrong label for slot: a typed year", "In 2024 there were {r1.count}.", {"CHARS"}),
    ("wrong meaning of slot", "The quietest month had {r1.count}.", {"WORD"}),
    ("rise without compare word", "Arrest records went up to {r1.count}.", {"WORD"}),
    ("trend claim", "Arrest records are rising, with {r1.count}.", {"WORD"}),
    ("doubled", "Arrest records doubled to {r1.count}.", {"WORD"}),
    ("same as", "The count of arrest records was the same, {r1.count}.", {"WORD"}),
    ("direction with compare slot, wrong way",
     "The lower count had more arrest records: {r3.compare}.", {"WORD"}),
    ("unchanged/steady", "Arrest records held steady at {r1.count}.", {"WORD"}),
    ("people (unit)", "People had {r1.count}.", {"WORD"}),
    ("arrests of people", "There were {r1.count} of people arrested.", {"WORD"}),
    ("residents", "Residents had {r1.count}.", {"WORD"}),
    ("men/women", "Men had {r1.count}.", {"WORD"}),
    ("Black/Hispanic", "There were {r1.count}, all Hispanic.", {"WORD"}),
    ("place", "There were {r1.count} in Rockville.", {"WORD"}),
    ("offense", "There were {r1.count} for burglary.", {"WORD"}),
    ("May (a month)", "In May there were {r1.count}.", {"WORD"}),
    ("ages typed as words", "There were {r1.count} for teenagers.", {"WORD"}),
    ("county claim", "The county recorded {r1.count}.", {"WORD"}),
    ("police claim", "Police made {r1.count}.", {"WORD"}),
    ("safe/dangerous", "A dangerous year: {r1.count}.", {"WORD"}),
    ("good/bad news", "Good news: {r1.count}.", {"WORD"}),
    ("unusually", "An unusually high {r1.count}.", {"WORD"}),
    ("record high (pun)", "A record {r1.count}.", {"WORD"}),
]

# R9's own list, beyond the planning chat's sentences.
R9_LIST = [
    ("a digit", "I counted {r1.count}, 12 in all.", {"CHARS"}),
    ("a number word", "I counted {r1.count}, twelve in all.", {"WORD"}),
    ("a month name", "I counted {r1.count}, most in April.", {"WORD"}),
    ("an age word", "I counted {r1.count} for juveniles.", {"WORD"}),
    ("per day", "I counted {r1.count} per day.", {"WORD"}),
    ("roughly", "I counted roughly {r1.count}.", {"WORD"}),
    ("over", "I counted over {r1.count}.", {"WORD"}),
    ("not", "I counted {r1.count}, not {r2.count}.", {"WORD"}),
    ("people", "I counted {r1.count} of people.", {"WORD"}),
    ("a place name", "I counted {r1.count} in Silver Spring.", {"WORD"}),
    ("an offense", "I counted {r1.count} for theft.", {"WORD"}),
    ("a direction word", "Here is the comparison: {r1.count}, down from {r2.count}.",
     {"WORD"}),
    ("a direction word: rose", "Arrest records rose to {r1.count}.", {"WORD"}),
    ("a judgement word", "I counted a worrying {r1.count}.", {"WORD"}),
    ("a second language, ASCII", "Hay {r1.count}.", {"WORD"}),
    ("a second language, accents", "Conté {r1.count}.", {"CHARS"}),
    ("a slot glued to a letter, after", "I counted {r1.count}s.", {"GLUE"}),
    ("a slot glued to a letter, before", "I counted a{r1.count}.", {"GLUE"}),
    ("a slot glued to a sign, before", "I counted ~{r1.count}.", {"GLUE"}),
    ("a slot glued to a sign, after", "I counted {r1.count}%.", {"GLUE"}),
    ("a slot glued to another slot", "{r1.count}{r2.count}.", {"GLUE"}),
    ("an old slot", "I counted {r1.total}.", {"SLOT"}),
    ("an old label slot", "There were {r1.total} arrest records in {r1.year}.", {"SLOT"}),
    ("a slot of another turn", "I counted {r4.count}.", {"SLOT"}),
    ("a fact slot in a finding", "I counted {r1.count}. {f1}.", {"SLOT"}),
]

CONTROL = "I counted {r1.count}."


def trick_results(tmp_path):
    """reply.results of one ANSWERED turn: r1 and r2 counted, r3 their compare (handed over
    unchanged, answer A2 of briefs/QUESTIONS.md)."""
    folder = Path(tmp_path) / f"{next(_TURN)}-turn"
    folder.mkdir()
    reply = Env(folder).answered(QUESTION, *PAIR, compared=True)
    assert len(reply.results) == 3, reply.results
    return reply.results


def check_premise(text, codes):
    if "WORD" in codes:
        assert unlisted_words(text), f"{text!r} holds no word missing from the list"
    if "CHARS" in codes:
        assert odd_chars(text), f"{text!r} holds no mark R1 disallows"


def must_fail(got, text, codes):
    assert isinstance(got, list) and got, f"{text!r} passed the check"
    assert codes <= set(got), f"{text!r}: {sorted(codes)} not among {got}"
    assert set(got) <= {"SLOT", "GLUE", "CHARS", "WORD", "SHAPE"}, got


def test_the_new_control_passes(tmp_path):
    """The planning chat's control, rewritten: one count slot and listed words."""
    replies = mod("replies")
    assert not unlisted_words(CONTROL) and not odd_chars(CONTROL)
    results = trick_results(tmp_path)
    assert replies.check_finding(CONTROL, results, replies.load_words()) == []


def test_there_are_49_trick_sentences_and_the_old_control():
    """The planning chat's 49 trick sentences, plus its control (which now fails)."""
    assert len(TRICKS) == 50
    assert len({text for _, text, _ in TRICKS}) == 50


@pytest.mark.parametrize("name, text, codes", TRICKS + R9_LIST,
                         ids=[name for name, _, _ in TRICKS + R9_LIST])
def test_each_trick_sentence_fails_the_finding_check(tmp_path, name, text, codes):
    """R1 and R9: each trick fails check_finding, with the named code among its codes."""
    check_premise(text, codes)
    replies = mod("replies")
    results = trick_results(tmp_path)
    must_fail(replies.check_finding(text, results, replies.load_words()), text, codes)


def test_a_count_slot_in_an_about_data_text_fails(tmp_path):
    """R9: {r1.count} in an about_data text (it offers {f1} to {fN} only)."""
    replies = mod("replies")
    facts, words = replies.load_facts(), replies.load_words()
    for text in ("Here is what I know: {r1.count}.", "{f1}. I counted {r1.count}."):
        must_fail(replies.check_about(text, facts, words), text, {"SLOT"})


@pytest.mark.parametrize("name, text, codes", TRICKS + R9_LIST,
                         ids=[name for name, _, _ in TRICKS + R9_LIST])
def test_each_trick_sentence_end_to_end_gives_the_fixed_rendering(tmp_path, name, text,
                                                                  codes):
    """R1 and R9: when a finding fails, render_fixed is sent with line 2 and nothing else:
    the reply is exactly Python's text, so nothing the model wrote is in it. Style
    fallback, the code among draft_failures, and no code but R1's five ("the old codes ...
    are gone for them")."""
    env = Env(tmp_path)
    reply = env.ask(QUESTION, Step(*[count(y, g) for y, g in PAIR]),
                    Step(compare("r1", "r2")), Step(finish("finding", text)))
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert (reply.reply_kind, reply.reply_style) == ("finding", "fallback"), reply.reply_style
    assert codes <= set(reply.draft_failures), reply.draft_failures
    assert set(reply.draft_failures) <= R1_CODES, reply.draft_failures  # old codes gone (R1)
    c = compare_expect([(y, g, sum(months(y, g))) for y, g in PAIR])
    assert_answered(reply.text, fixed_line1_re(PAIR, [c]), first=True)


# ---- the prompt's own examples (brief P1A2-A point 4) ------------------------------------

def prompt_examples():
    """The text after each "might read:" of config/agent_prompt_v2.md, and its `{f1}.
    {f2}.` sentence (the about_data example), read from the file."""
    text = AGENT_PROMPT_MD.read_text(encoding="utf-8")
    findings = [line.split("might read:", 1)[1].strip() for line in text.splitlines()
                if "might read:" in line]
    about = re.findall(r"\{f\d+\}\.(?: \{f\d+\}\.)*", text)
    assert findings, "no 'might read:' example in the prompt"
    assert about, "no {f1}. {f2}. example in the prompt"
    return findings, about


def test_every_example_sentence_of_the_prompt_passes_the_new_checks(tmp_path):
    """Brief point 4: each finding example passes check_finding with the results of two
    counts and their compare (r1, r2, r3: every slot the examples use), and the about_data
    example passes check_about."""
    findings, about = prompt_examples()
    for text in findings + about:
        assert not unlisted_words(text) and not odd_chars(text), text
    replies = mod("replies")
    results, words, facts = trick_results(tmp_path), replies.load_words(), replies.load_facts()
    wrong = [f"finding {t!r}: {replies.check_finding(t, results, words)}" for t in findings
             if replies.check_finding(t, results, words) != []]
    wrong += [f"about_data {t!r}: {replies.check_about(t, facts, words)}" for t in about
              if replies.check_about(t, facts, words) != []]
    assert len(fact_lines()) >= 2
    assert not wrong, "\n".join(wrong)
