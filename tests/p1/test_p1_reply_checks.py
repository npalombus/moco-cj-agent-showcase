"""The reply functions, called directly: docs/P1A-R2-DESIGN.md R1 (revision 2) for findings
and about_data, docs/P1A-DESIGN.md A7 for background and render_fixed (unchanged, R7), A8 for
the facts. Brief P1A2-A point 4.

What this file covers
- replies.load_words() is config/reply_words.json's allowed words, lower case, and
  load_words(path) reads the file given; load_rules (background only now, R7) and
  load_facts as before. All compared with the files read here, never with copied content.
- `results` is always reply.results of a turn run with the FakeModel through
  agent.handle_question (answer A2 of briefs/QUESTIONS.md, unchanged by R1): turn_results()
  runs one ANSWERED turn and hands its results over unchanged. `words` is
  replies.load_words(), `facts` replies.load_facts().
- slot_phrases(result, registry): the exact phrase of each fact slot, with numbers from the
  truth file, a tie in the months, every month equal, a total of 1, a comparison, all_equal,
  and a total over 1,000 (comma).
- fill(text, results, registry, facts=None): each slot filled with its phrase, a capital
  first letter at the start of the text and after a sentence end (".", "!" and "?"), and
  none elsewhere; fact slots without their final full stop.
- check_finding(text, results, words) and check_about(text, facts, words): passing texts
  ([] exactly), and for each of R1's codes (SLOT, GLUE, CHARS, WORD, SHAPE) at least two
  texts that fail with exactly that code; texts that must fail with a code among others; no
  code outside R1's five, ever. Which slots a finding offers (count and months of counts,
  compare of compares) and an about_data text offers ({f1} to {fN}). SHAPE's 600
  characters once filled and four fact slots.
- A copy of the word list with a word added lets that word pass (the list is read).
- check_background and render_fixed: unchanged (R7, R1 "render_fixed ... unchanged").

Every text's own premise is checked against the files first (p1support.unlisted_words and
odd_chars, read from config/reply_words.json and R1's list of marks): a text meant to fail
only WORD holds a word not on the list and no other fault, and so on.

Accepted both ways (kit-log/raw/P1A2-A-notes.txt)
- A {...} that is not a slot this turn offers (an old slot, another turn's, a fact slot in
  a finding): SLOT, and CHARS or WORD for what is inside its braces may come too. So those
  texts are checked with SLOT among the codes, never as exactly SLOT.
- SHAPE's "more than four sentences": counted on the text as written or once filled. Every
  text here reads the same both ways (fact slots of one sentence where it matters).
- The order of the codes, and whether a code is listed twice: compared as a set.

Not checked
- What fill does with a slot that the check would reject (R1 does not say).
- The CLAIM, NUMBER, MONTH, AGE, UNIT, COMPARE, MEASURE and FINDING texts of P1A: R1 removes
  those codes for findings and about_data; their attacks are the trick sentences of
  test_p1_reply_tricks.py, failing as WORD or CHARS.
"""
import itertools
import json
import re
from pathlib import Path

import pytest

from p1support import (FACT_SHEET_MD, ONE_COUNT_TEXT, R1_CODES, REPLY_WORDS_JSON, Env, Step,
                       about_text, cap, changed_data, compare, compare_expect, compare_phrase,
                       count, count_phrase, count_slots, compare_slots, fact_lines,
                       fact_phrase, fact_slots, fill_expect, finish, fixed_line1_re,
                       load_registry, mod, month_list, months, months_phrase, numbers_in,
                       odd_chars, reply_rules, reply_words, sentences, single_sentence_facts,
                       synthetic_fact, unlisted_words)
from support import AGE_GROUPS, SUPPORTED

COUNT_QUESTION = SUPPORTED["S1"][0]
COMPARE_QUESTION = "Compare 2024 and 2025 for people under 18."
_TURN = itertools.count()


def turn_results(tmp_path, *counts, compared=False, data_path=None):
    """reply.results of one ANSWERED turn, handed over unchanged (answer A2). The FakeModel
    counts `counts` [(year, age group or None)] in one step, compares them all when
    `compared`, and ends with a finish (p1support.Env.answered). The turn is ANSWERED
    whether its text passes or not, so this works before and after the build. Each turn
    gets its own numbered folder, store and runs folder."""
    folder = Path(tmp_path) / f"{next(_TURN)}-turn"
    folder.mkdir()
    env = Env(folder) if data_path is None else Env(folder, data_path=data_path)
    question = COUNT_QUESTION if len(counts) == 1 else COMPARE_QUESTION
    reply = env.answered(question, *counts, compared=compared)
    assert len(reply.results) == len(counts) + (1 if compared else 0), reply.results
    return reply.results


def check_cases(check, cases):
    """cases: (text, want). want None: check(text) must be [] (pass). A str: the codes must
    be exactly that one code (as a set). A set: each of its codes must be among the codes.
    Every returned code must be one of R1's five. Every case is tried; all problems are
    listed."""
    wrong = []
    for text, want in cases:
        got = check(text)
        if not isinstance(got, list) or not all(isinstance(c, str) for c in got):
            wrong.append(f"{text!r}: not a list of codes: {got!r}")
        elif not set(got) <= R1_CODES:
            wrong.append(f"{text!r}: codes outside R1's five: {sorted(set(got) - R1_CODES)}")
        elif want is None and got != []:
            wrong.append(f"{text!r} should pass, got {got}")
        elif isinstance(want, str) and set(got) != {want}:
            wrong.append(f"{text!r} should fail with exactly {want}, got {got}")
        elif isinstance(want, set) and not want <= set(got):
            wrong.append(f"{text!r} should fail with {sorted(want)} among its codes, got {got}")
    assert not wrong, "\n".join(wrong)


def premise(text, *, word_fault, char_fault, slots=None):
    """A test text's own premise, read from the files: it holds a word that is not on the
    list (word_fault) or not, a mark R1 does not allow (char_fault) or not, and only slots
    of `slots` (when given)."""
    assert bool(unlisted_words(text)) is word_fault, (text, unlisted_words(text))
    assert bool(odd_chars(text)) is char_fault, (text, odd_chars(text))
    if slots is not None:
        used = set(re.findall(r"\{[^{}]*\}", text))
        assert used <= set(slots), (text, used - set(slots))


def sized(start, piece, end, low, high, measure=len):
    """`start`, `piece` as often as fits, then `end`: measure(text) above `low`, at most
    `high`."""
    k = 0
    while measure(start + piece * (k + 1) + end) <= high:
        k += 1
    text = start + piece * k + end
    assert low < measure(text) <= high, (measure(text), low, high)
    return text


# ---- load_words, load_rules and load_facts ---------------------------------------------

def test_load_words_is_the_word_list_lower_case():
    """R1: load_words(path=None) -> the allowed words of config/reply_words.json, lower
    case. Compared as a set (R1 does not say list or set)."""
    replies = mod("replies")
    words = replies.load_words()
    assert all(isinstance(w, str) for w in words)
    assert set(words) == reply_words()


def test_load_words_reads_the_file_it_is_given(tmp_path):
    """R1: the list is read from the file given, in lower case."""
    replies = mod("replies")
    data = json.loads(REPLY_WORDS_JSON.read_text(encoding="utf-8"))
    data["allowed"] = data["allowed"] + ["Zebrafinch"]
    path = tmp_path / "0-words-copy.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert set(replies.load_words(path)) == reply_words() | {"zebrafinch"}


def test_load_rules_is_the_parsed_rules_file():
    """A7 and R7: load_rules(path=None) -> dict, the parsed config/reply_rules.json (for
    check_background, unchanged)."""
    replies = mod("replies")
    assert replies.load_rules() == reply_rules()


def test_load_rules_reads_the_file_it_is_given(tmp_path):
    replies = mod("replies")
    rules = reply_rules()
    rules["number_words"] = rules["number_words"] + ["zebraquartztestword"]
    path = tmp_path / "0-rules-copy.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    assert replies.load_rules(path) == rules


def test_load_facts_are_the_fact_lines():
    """A7 and A8: load_facts(path=None) -> the fact lines, in order, without "- "."""
    replies = mod("replies")
    assert replies.load_facts() == fact_lines()


def test_load_facts_reads_the_file_it_is_given(tmp_path):
    replies = mod("replies")
    path = tmp_path / "0-facts-copy.md"
    path.write_text(FACT_SHEET_MD.read_text(encoding="utf-8")
                    + "\nA line that is not a fact.\n- A made-up fact line for this test.\n",
                    encoding="utf-8")
    assert replies.load_facts(path) == fact_lines() + ["A made-up fact line for this test."]


# ---- slot_phrases (R1 "Fact slots") ------------------------------------------------------

@pytest.mark.parametrize("year, group", [
    (2025, "18_25"), (2025, "under_18"), (2025, "41_plus"), (2024, None),
], ids=["2025 18_25", "2025 under_18 quietest tie", "2025 41_plus busiest tie",
        "2024 all ages over 1000"])
def test_slot_phrases_of_a_count(tmp_path, year, group):
    """R1: {"count": `<total> arrest records <age phrase> in <year>`, "months": the months
    sentence without its full stop}. The truth file has a tie for the quietest month of 2025
    for people under 18 and for the busiest of 2025 for ages 41 and over; 2024 for all ages
    is over 1,000 (a comma)."""
    replies = mod("replies")
    values = months(year, group)
    if group == "under_18":
        assert values.count(min(values)) > 1, "the tie this case needs"
    if group == "41_plus":
        assert values.count(max(values)) > 1, "the tie this case needs"
    if group is None:
        assert sum(values) >= 1000, "the comma this case needs"
    (result,) = turn_results(tmp_path, (year, group))
    got = replies.slot_phrases(result, load_registry())
    assert got == {"count": count_phrase(year, group), "months": months_phrase(values)}


def test_slot_phrases_of_a_count_with_every_month_equal(tmp_path):
    """R1: when every month is equal, `every month had the same count (<n>)`. A changed
    copy of the data gives every month of 2025 the January count of ages 18 to 25."""
    replies = mod("replies")

    def change(counts):
        for m in range(2, 13):
            counts[f"2025-{m:02d}"]["18_25"] = counts["2025-01"]["18_25"]

    path, counts = changed_data(tmp_path, "0-every-month-equal", change)
    values = months(2025, "18_25", counts)
    assert len(set(values)) == 1
    (result,) = turn_results(tmp_path, (2025, "18_25"), data_path=path)
    got = replies.slot_phrases(result, load_registry())
    assert got == {"count": count_phrase(2025, "18_25", counts),
                   "months": f"every month had the same count ({values[0]})"}


def test_slot_phrases_of_a_count_with_a_total_of_1(tmp_path):
    """R1: a total of 1 gives `1 arrest record`. A changed copy of the data keeps one
    arrest record of 2025 for ages 26 to 40, in March; the other eleven months tie at 0."""
    replies = mod("replies")

    def change(counts):
        for m in range(1, 13):
            counts[f"2025-{m:02d}"]["26_40"] = 1 if m == 3 else 0

    path, counts = changed_data(tmp_path, "0-total-of-one", change)
    values = months(2025, "26_40", counts)
    assert sum(values) == 1
    results = turn_results(tmp_path, (2025, "26_40"), data_path=path)
    (result,) = results
    got = replies.slot_phrases(result, load_registry())
    assert got == {"count": count_phrase(2025, "26_40", counts),
                   "months": months_phrase(values)}
    assert got["count"].startswith("1 arrest record for ") and "records" not in got["count"]
    assert replies.fill("{r1.count}.", results, load_registry()) == \
        cap(count_phrase(2025, "26_40", counts)) + "."


@pytest.mark.parametrize("counts", [
    [(2024, "under_18"), (2025, "under_18")],
    [(2025, group) for group in AGE_GROUPS],
    [(2024, None), (2025, "18_25")],
], ids=["years", "four age groups", "both differ, over 1000"])
def test_slot_phrases_of_a_compare(tmp_path, counts):
    """R1: {"compare": render_fixed's compare sentence without its full stop, its first
    label as the registry writes it (not capitalised)}. Labels as A6 makes them."""
    replies = mod("replies")
    results = turn_results(tmp_path, *counts, compared=True)
    c = compare_expect([(y, g, sum(months(y, g))) for y, g in counts])
    got = replies.slot_phrases(results[-1], load_registry())
    assert got == {"compare": compare_phrase(c)}


def test_slot_phrases_of_an_all_equal_compare(tmp_path):
    """R1: when all_equal, `the counts were the same (<n>) for <labels>`. A changed copy of
    the data gives 2024 the 2025 months of people under 18."""
    replies = mod("replies")

    def change(counts):
        for m in range(1, 13):
            counts[f"2024-{m:02d}"]["under_18"] = counts[f"2025-{m:02d}"]["under_18"]

    path, data_counts = changed_data(tmp_path, "0-equal-totals", change)
    pair = [(2024, "under_18"), (2025, "under_18")]
    totals = [sum(months(y, g, data_counts)) for y, g in pair]
    c = compare_expect([(y, g, t) for (y, g), t in zip(pair, totals)])
    assert c["all_equal"] is True
    results = turn_results(tmp_path, *pair, compared=True, data_path=path)
    got = replies.slot_phrases(results[-1], load_registry())
    assert got == {"compare": f"the counts were the same ({totals[0]}) for 2024 and 2025"}


# ---- fill (R1) ---------------------------------------------------------------------------

def test_fill_writes_each_count_phrase_with_a_capital_only_at_a_sentence_start(tmp_path):
    """R1: a slot that is the first thing in the text, or the first thing after a sentence
    end (".", "!" or "?" and white space), gets a capital first letter; elsewhere the phrase
    is as written. Two counts: 2024 for all ages (over 1,000) and 2025 for ages 18 to 25."""
    replies = mod("replies")
    results = turn_results(tmp_path, (2024, None), (2025, "18_25"))
    phrases = {**count_slots("r1", 2024, None), **count_slots("r2", 2025, "18_25")}
    texts = [
        ONE_COUNT_TEXT,
        "{r1.count}. {r2.count}.",
        "I counted {r1.count} and {r2.count}.",
        "Here it is! {r2.months}? {r1.months}.",
        "Here is what I found: {r2.count}, and {r1.months}.",
    ]
    registry = load_registry()
    got = {text: replies.fill(text, results, registry) for text in texts}
    assert got == {text: fill_expect(text, phrases) for text in texts}
    assert got["{r1.count}. {r2.count}."] == \
        f"{sum(months(2024, None)):,} arrest records across all ages in 2024. " \
        f"{sum(months(2025, '18_25'))} arrest records for ages 18 to 25 in 2025."


def test_fill_capitalises_a_lower_case_phrase_only_at_a_sentence_start(tmp_path):
    """R1: the compare phrase of four age groups starts with an age wording in lower case
    ("ages 26 to 40 had ..."): a capital at the start and after a sentence end (".", "!"
    and "?"), lower case after a colon or a word."""
    replies = mod("replies")
    counts = [(2025, group) for group in AGE_GROUPS]
    results = turn_results(tmp_path, *counts, compared=True)
    c = compare_expect([(y, g, sum(months(y, g))) for y, g in counts])
    phrase = compare_phrase(c)
    assert phrase[0].islower(), "this test needs a label that starts in lower case"
    registry = load_registry()
    assert replies.fill("{r5.compare}.", results, registry) == cap(phrase) + "."
    assert replies.fill("Here is the comparison: {r5.compare}.", results, registry) == \
        f"Here is the comparison: {phrase}."
    assert replies.fill("I compared them. {r5.compare}!", results, registry) == \
        f"I compared them. {cap(phrase)}!"
    assert replies.fill("Is that it? {r5.compare}.", results, registry) == \
        f"Is that it? {cap(phrase)}."
    assert replies.fill("Here it is! {r5.compare}.", results, registry) == \
        f"Here it is! {cap(phrase)}."
    assert replies.fill("I compared them and {r5.compare}.", results, registry) == \
        f"I compared them and {phrase}."


def test_fill_of_every_month_equal_and_all_equal(tmp_path):
    """R1: `every month had the same count (<n>)` and `the counts were the same (<n>) for
    <labels>`: a capital at a sentence start, lower case after a word. A changed copy of
    the data makes both true for people under 18 (2024 gets 2025's months, and every month
    of 2025 the January count)."""
    replies = mod("replies")

    def change(counts):
        for m in range(1, 13):
            counts[f"2025-{m:02d}"]["under_18"] = counts["2025-01"]["under_18"]
            counts[f"2024-{m:02d}"]["under_18"] = counts["2025-01"]["under_18"]

    path, data_counts = changed_data(tmp_path, "0-flat", change)
    pair = [(2024, "under_18"), (2025, "under_18")]
    totals = [sum(months(y, g, data_counts)) for y, g in pair]
    c = compare_expect([(y, g, t) for (y, g), t in zip(pair, totals)])
    assert c["all_equal"] is True
    results = turn_results(tmp_path, *pair, compared=True, data_path=path)
    phrases = {**count_slots("r1", 2024, "under_18", data_counts),
               **count_slots("r2", 2025, "under_18", data_counts), **compare_slots("r3", c)}
    assert phrases["{r2.months}"].startswith("every month had the same count (")
    texts = ["{r2.months}.", "I counted {r2.count} and {r2.months}.", "{r3.compare}.",
             "Here is the comparison, and {r3.compare}."]
    registry = load_registry()
    got = {text: replies.fill(text, results, registry) for text in texts}
    assert got == {text: fill_expect(text, phrases) for text in texts}
    assert got["{r3.compare}."].startswith("The counts were the same (")
    assert "and every month had the same count (" in got["I counted {r2.count} and {r2.months}."]


def test_fill_of_fact_slots(tmp_path):
    """R1: {fN} fills with fact line N as the fact sheet has it, without its final full
    stop; fill(text, [], registry, facts) is how an about_data text is filled."""
    replies = mod("replies")
    facts = replies.load_facts()
    n = len(fact_lines())
    some = single_sentence_facts()[:2]
    texts = [f"{{f1}}. {{f{n}}}.", about_text(*some), "Here is what I know: " +
             " and ".join(f"{{f{k}}}" for k in some) + "."]
    got = {text: replies.fill(text, [], load_registry(), facts) for text in texts}
    assert got == {text: fill_expect(text, fact_slots()) for text in texts}
    assert got[texts[0]] == f"{fact_phrase(1)}. {fact_phrase(n)}."
    assert fact_lines()[0].endswith(".") and not fact_phrase(1).endswith(".")


def test_fill_and_render_fixed_list_three_tied_months_in_calendar_order(tmp_path):
    """A7 and R1: `A, B and C` in calendar order, `were`, `months`, ` each`, in the months
    phrase and in render_fixed. A changed copy of the data gives January and December the
    busiest count of April (2025, ages 18 to 25)."""
    replies = mod("replies")

    def change(counts):
        high = max(counts[f"2025-{m:02d}"]["18_25"] for m in range(1, 13))
        for m in (1, 12):
            counts[f"2025-{m:02d}"]["18_25"] = high

    path, counts = changed_data(tmp_path, "0-three-busiest", change)
    values = months(2025, "18_25", counts)
    assert values.count(max(values)) == 3, "the tie this test needs"
    results = turn_results(tmp_path, (2025, "18_25"), data_path=path)
    registry = load_registry()
    phrase = replies.fill("{r1.months}.", results, registry)
    assert phrase.startswith(month_list(values, max(values)) + " were the busiest months (")
    assert phrase == months_phrase(values) + "."
    line = replies.render_fixed(results, registry)
    assert re.fullmatch(fixed_line1_re([(2025, "18_25")], data_counts=counts), line), line


# ---- check_finding (R1) --------------------------------------------------------------------
# Texts for the results of one count of 2025, ages 18 to 25 (r1).

ONE_SLOTS = ("{r1.count}", "{r1.months}")

FINDING_PASS = [
    ONE_COUNT_TEXT,
    "{r1.count}. {r1.months}.",
    "{r1.count} and {r1.months}.",
    "HERE IS WHAT I FOUND: {r1.count}.",
    "Here’s what I found: {r1.count}. Want the details?",
    # C13 rule 1 (docs/S3A-DESIGN.md): two slots in one sentence need exactly " and " or
    # ", and " between them; was "... – here it is; {r1.months}!" (S3A-A notes).
    "I counted {r1.count} (test-data) – here it is! {r1.months}; thanks!",
    "Sure — I counted {r1.count}, so that's the total.",
    "Hi! I've counted {r1.count}? {r1.months}.",
    "I counted {r1.count}. Here it is. That is it. Thanks.",  # four sentences: the most
]

FINDING_EXACT = {
    "SLOT": [
        "I counted them.",                                   # no fact slot at all
        "I counted {r1.count}. I counted {r1.count}.",       # the same slot twice
        "Here is what I found: {r1.months}, and {r1.months}.",
    ],
    "GLUE": [
        "I counted:{r1.count}.",                     # a mark before the slot
        "I counted ({r1.count}).",                   # a bracket before it
        "I counted {r1.count}-and that is it.",      # a hyphen after it
        "I counted {r1.count} {r1.months}.",         # two slots, only a space between
        "I counted {r1.count}; {r1.months}.",        # ... only a mark between
        "I counted {r1.count}, {r1.months}.",
    ],
    "CHARS": [
        "I counted {r1.count} 2.",                   # a digit
        "I counted {r1.count} %.",
        'I "counted" {r1.count}.',                   # quotation marks
        "I counted {r1.count}.\nThat is the count.",  # a line break
        "I counted {r1.count}. 你好.",          # another script
        "I *counted* {r1.count}.",                   # markup
        "I\tcounted {r1.count}.",                    # a tab
    ],
    "WORD": [
        "I counted roughly {r1.count}.",
        "There were {r1.count} per day.",
        "I counted {r1.count}, not more.",
        "I counted {r1.count}. {r1.months}, made-up data.",  # a hyphen separates two words
    ],
    "SHAPE": [
        "I counted {r1.count}. Here it is. That is it. Thanks. Hello.",  # five sentences
        "I counted {r1.count}! Is that it? Yes. Thanks. Hello.",
    ],
}

# Each must fail with these codes among its codes (see "Accepted both ways" above).
FINDING_AMONG = [
    ("I counted {r1.total}.", {"SLOT"}),                    # an old slot
    ("In {r1.year} I counted {r1.count}.", {"SLOT"}),
    ("I counted {r2.count}.", {"SLOT"}),                    # no such result in this turn
    ("I counted {r1.count} and {r2.count}.", {"SLOT"}),
    ("I counted {r1.compare}.", {"SLOT"}),                  # a count has no compare slot
    ("Here is what I know: {f1}.", {"SLOT"}),               # a fact slot in a finding
    ("I counted {}.", {"SLOT"}),
    ("", {"SHAPE"}),                                        # empty (and no fact slot)
    ("I counted {r1.count}, 4321 in all, says zebra-quartz.", {"CHARS", "WORD"}),
    ("In 2024 there were {r1.count}.", {"CHARS"}),
]


def one_count_check(tmp_path):
    """check_finding with the results of one count of 2025, ages 18 to 25, and the words.
    Called in each test body after the texts' premises are checked."""
    replies = mod("replies")
    results = turn_results(tmp_path, (2025, "18_25"))
    words = replies.load_words()
    return lambda text: replies.check_finding(text, results, words)


def test_check_finding_passes_fact_slots_with_listed_words(tmp_path):
    """R1: fact slots that stand on their own, words from the list in any case (the curly
    apostrophe as the straight one, a hyphen between two listed words), the marks R1 allows,
    at most four sentences: [] exactly."""
    for text in FINDING_PASS:
        premise(text, word_fault=False, char_fault=False, slots=ONE_SLOTS)
        assert len(sentences(text)) <= 4, text
    check_cases(one_count_check(tmp_path), [(text, None) for text in FINDING_PASS])


@pytest.mark.parametrize("code", list(FINDING_EXACT))
def test_check_finding_fails_with_exactly_one_code(tmp_path, code):
    """R1: at least two texts that fail with exactly SLOT, GLUE, CHARS, WORD or SHAPE."""
    texts = FINDING_EXACT[code]
    assert len(texts) >= 2
    for text in texts:
        premise(text, word_fault=code == "WORD", char_fault=code == "CHARS", slots=ONE_SLOTS)
        if code == "SHAPE":
            assert len(sentences(text)) > 4, text
    check_cases(one_count_check(tmp_path), [(text, code) for text in texts])


def test_check_finding_fails_unknown_slots_and_other_faults(tmp_path):
    """R1 SLOT: a {...} that is not a fact slot this turn offers; SHAPE: empty; CHARS: a
    digit. Other codes may come with these."""
    check_cases(one_count_check(tmp_path), FINDING_AMONG)


def test_check_finding_shape_counts_characters_once_filled(tmp_path):
    """R1 SHAPE: more than 600 characters once filled. One text is at most 600 as written
    and over it once filled; its twin is at most 600 once filled and passes. One sentence,
    listed words only."""
    phrases = count_slots("r1", 2025, "18_25")

    def filled(text):
        return len(fill_expect(text, phrases))

    start = "I counted {r1.count} and {r1.months}"
    grows = sized(start, " and the data", ".", 600, 650, measure=filled)
    assert len(grows) <= 600
    twin = sized(start, " and the data", ".", 540, 600, measure=filled)
    for text in (grows, twin):
        premise(text, word_fault=False, char_fault=False, slots=ONE_SLOTS)
    replies = mod("replies")
    results = turn_results(tmp_path, (2025, "18_25"))
    assert len(replies.fill(twin, results, load_registry())) == filled(twin)
    check_cases(one_count_check(tmp_path), [(grows, "SHAPE"), (twin, None)])


def test_check_finding_offers_count_and_months_of_counts_and_compare_of_compares(tmp_path):
    """R1: a finding offers the count and months slots of this turn's count results and the
    compare slot of its compare results, and nothing else. Two counts (r1, r2) and a
    compare (r3)."""
    replies = mod("replies")
    offered = ("{r1.count}", "{r1.months}", "{r2.count}", "{r2.months}", "{r3.compare}")
    passing = ["Here is the comparison: {r3.compare}.", "{r3.compare}.",
               "I counted {r1.count} and {r2.count}.",
               "I counted {r1.count} and {r2.count}. {r3.compare}.",
               "{r1.count}. {r1.months}. {r2.count}. {r2.months}."]  # was months alone: see below
    for text in passing:
        premise(text, word_fault=False, char_fault=False, slots=offered)
    results = turn_results(tmp_path, (2024, "under_18"), (2025, "under_18"), compared=True)
    words = replies.load_words()
    check_cases(lambda text: replies.check_finding(text, results, words),
                [(text, None) for text in passing]
                + [("I counted {r3.count}.", {"SLOT"}), ("Here it is: {r3.months}.", {"SLOT"}),
                   ("Here it is: {r1.compare}.", {"SLOT"}),
                   ("Here it is: {r4.compare}.", {"SLOT"}),
                   ("Here it is: {r3.compare} and {r3.compare}.", "SLOT"),
                   ("There were more in {r2.count} than in {r1.count}.", {"WORD", "GLUE"})])


def test_check_finding_takes_a_months_slot_only_straight_after_its_own_count(tmp_path):
    """R1's SLOT, as amended by the planning chat on 2026-11-11 after the tests session's
    note (kit-log/raw/P1A2-A-notes.txt, "For the planning chat to decide"): the months
    phrase names no year and no age group, so {rN.months} passes only when the slot before
    it in the text is {rN.count} of the same result. Anything else is SLOT, and nothing but
    SLOT. Written by the planning chat, with this file's own helpers. Two counts (r1, r2)
    and a compare (r3)."""
    replies = mod("replies")
    offered = ("{r1.count}", "{r1.months}", "{r2.count}", "{r2.months}", "{r3.compare}")
    passing = ["{r1.count}. {r1.months}.",
               "I counted {r1.count} and {r1.months}. I also counted {r2.count}. {r2.months}.",
               "{r2.count}. {r2.months}. {r1.count}."]
    failing = ["{r1.months}.",                               # no count before it
               "Here is what I found: {r1.months}.",
               "{r1.months}. {r1.count}.",                   # its count comes after
               "{r1.count}. {r2.months}.",                   # another result's count
               "{r1.count}. {r2.count}. {r1.months}.",       # another slot in between
               "{r1.count}. {r3.compare}. {r1.months}.",
               "{r2.count}. {r1.months}. {r1.count}."]
    for text in passing + failing:
        premise(text, word_fault=False, char_fault=False, slots=offered)
        assert len(sentences(text)) <= 4, text
    results = turn_results(tmp_path, (2024, "under_18"), (2025, "under_18"), compared=True)
    words = replies.load_words()
    check_cases(lambda text: replies.check_finding(text, results, words),
                [(text, None) for text in passing] + [(text, "SLOT") for text in failing])


def test_a_word_added_to_a_copy_of_the_word_list_passes(tmp_path):
    """R9: the list is read, not copied. "roughly" fails as WORD with the real list and
    passes with a copy of the file that adds it (findings and about_data)."""
    replies = mod("replies")
    assert "roughly" not in reply_words()
    data = json.loads(REPLY_WORDS_JSON.read_text(encoding="utf-8"))
    data["allowed"] = data["allowed"] + ["roughly"]
    path = tmp_path / "0-words-plus-roughly.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    wider = replies.load_words(path)
    results = turn_results(tmp_path, (2025, "18_25"))
    finding = "I counted roughly {r1.count}."
    about = f"Here is roughly what I know. {{f{single_sentence_facts()[0]}}}."
    facts = replies.load_facts()
    assert set(replies.check_finding(finding, results, replies.load_words())) == {"WORD"}
    assert replies.check_finding(finding, results, wider) == []
    assert set(replies.check_about(about, facts, replies.load_words())) == {"WORD"}
    assert replies.check_about(about, facts, wider) == []


# ---- check_about (R1) ----------------------------------------------------------------------

def about_cases():
    """(passing texts, {code: texts failing with exactly that code}, texts failing with codes
    among others), built from the fact sheet when the test runs."""
    one = single_sentence_facts()
    assert len(one) >= 5, "the fact sheet needs five facts of one sentence for these texts"
    a, b, c, d, e = one[:5]
    n = len(fact_lines())
    passing = [about_text(a), about_text(synthetic_fact(), a), f"{{f{a}}}.",
               f"Here is what I know: {{f{a}}} and {{f{b}}}.",
               f"{{f{a}}}. {{f{b}}}. {{f{c}}}. {{f{d}}}.",                  # four: the most
               # C13 rule 1: was "— {fa}; also, {fn}." (S3A-A notes)
               f"Here’s what I know — {{f{a}}}, and {{f{n}}}; also, thanks."]
    exact = {
        "SLOT": ["Here is what I know.", f"{{f{a}}}. {{f{a}}}."],
        "GLUE": [f"Here is what I know:{{f{a}}}.", f"{{f{a}}} {{f{b}}}.", f"({{f{a}}})."],
        "CHARS": [f'Here is what I "know": {{f{a}}}.', f"Here is what I know: {{f{a}}} 2.",
                  f"Here is what I know.\nThat is it: {{f{a}}}."],
        "WORD": [f"Here is what I know for certain: {{f{a}}}.", f"Sadly, {{f{a}}}."],
        "SHAPE": [f"{{f{a}}} and {{f{b}}}. {{f{c}}} and {{f{d}}}. {{f{e}}}.",  # five slots
                  f"Here is what I know. {{f{a}}}. Thanks. Hello. Hi."],        # five sentences
    }
    among = [("Here is what I know: {r1.count}.", {"SLOT"}), ("Here it is: {f0}.", {"SLOT"}),
             (f"Here it is: {{f{n + 1}}}.", {"SLOT"}), ("", {"SHAPE"}),
             ("Arrests rose in the made-up data.", {"SLOT", "WORD"}),
             (f"It holds 4321 records. {{f{a}}}.", {"CHARS", "WORD"})]
    return passing, exact, among


def test_check_about_passes_fact_slots_with_listed_words():
    """R1: {f1} to {fN}, each on its own, up to four, with listed words: [] exactly."""
    passing, _, _ = about_cases()
    for text in passing:
        premise(text, word_fault=False, char_fault=False, slots=fact_slots())
        assert len(sentences(fill_expect(text, fact_slots()))) <= 4, text
    replies = mod("replies")
    facts, words = replies.load_facts(), replies.load_words()
    check_cases(lambda text: replies.check_about(text, facts, words),
                [(text, None) for text in passing])


@pytest.mark.parametrize("code", ["SLOT", "GLUE", "CHARS", "WORD", "SHAPE"])
def test_check_about_fails_with_exactly_one_code(code):
    """R1: the same five codes for about_data, with at least two texts each; SHAPE also
    for more than four fact slots."""
    _, exact, _ = about_cases()
    texts = exact[code]
    assert len(texts) >= 2
    for text in texts:
        premise(text, word_fault=code == "WORD", char_fault=code == "CHARS",
                slots=fact_slots())
        if code != "SHAPE":
            assert len(sentences(fill_expect(text, fact_slots()))) <= 4, text
    replies = mod("replies")
    facts, words = replies.load_facts(), replies.load_words()
    check_cases(lambda text: replies.check_about(text, facts, words),
                [(text, code) for text in texts])


def test_check_about_fails_other_slots_and_faults():
    """R1: an about_data text offers {f1} to {fN} only; a digit fails, even one the fact
    sheet holds (CHARS); old about_data codes (NUMBER, FINDING, ADVICE) are gone."""
    replies = mod("replies")
    facts, words = replies.load_facts(), replies.load_words()
    _, _, among = about_cases()
    fact_year = sorted(numbers_in(" ".join(fact_lines())))[-1]
    among = among + [(f"Here is what I know about {fact_year}: {{f1}}.", {"CHARS"})]
    check_cases(lambda text: replies.check_about(text, facts, words), among)


def test_check_about_shape_counts_characters_once_filled():
    """R1 SHAPE: more than 600 characters once filled, with four fact slots or fewer. The
    long facts are chosen from the sheet; the twin is at most 600 once filled and passes."""
    one = single_sentence_facts()
    longest = sorted(one, key=lambda k: len(fact_phrase(k)))[-3:]
    start = "Here is what I know: " + " and ".join(f"{{f{k}}}" for k in longest)

    def filled(text):
        return len(fill_expect(text, fact_slots()))

    grows = sized(start, ", and the data", ".", 600, 650, measure=filled)
    twin = sized(start, ", and the data", ".", 520, 600, measure=filled)
    for text in (grows, twin):
        premise(text, word_fault=False, char_fault=False, slots=fact_slots())
        assert len(sentences(fill_expect(text, fact_slots()))) == 1
    replies = mod("replies")
    facts, words = replies.load_facts(), replies.load_words()
    check_cases(lambda text: replies.check_about(text, facts, words),
                [(grows, "SHAPE"), (twin, None)])


# ---- check_background (A7, unchanged by R7) -----------------------------------------------

def listed(list_name, *entries):
    """Each entry is in that list of config/reply_rules.json (a test text relies on it)."""
    words = [word.lower() for word in reply_rules()[list_name]]
    missing = [entry for entry in entries if entry not in words]
    assert not missing, f"not in reply_rules.json {list_name}: {missing}"


def check_background_cases(check, cases):
    """cases: (text, code). code None: [] (pass); otherwise the code is among the codes."""
    wrong = []
    for text, code in cases:
        got = check(text)
        if not isinstance(got, list) or not all(isinstance(c, str) for c in got):
            wrong.append(f"{text!r}: not a list of codes: {got!r}")
        elif code is None and got != []:
            wrong.append(f"{text!r} should pass, got {got}")
        elif code is not None and code not in got:
            wrong.append(f"{text!r} should fail with {code}, got {got}")
    assert not wrong, "\n".join(wrong)


def background_sized(start, piece, low, high):
    text = start + piece * ((high - len(start) - 1) // len(piece)) + "."
    assert low < len(text) <= high, (len(text), low, high)
    return text


MARKS = reply_rules()["markup"]
BACKGROUND_PASS = ("Arrest numbers may differ between places for many reasons, and it depends "
                   "on how records are kept.")

BACKGROUND = {
    "SLOT": (None, [
        ("Counts like {r1.total} may differ between places.", "SLOT"),
        ("Counts may differ between places.", None),
        ("It may depend on {r1.year}.", "SLOT"),
        ("It may depend on the year.", None),
    ]),
    "NUMBER": (("number_words", "two"), [
        ("Counts may differ by 10 points.", "NUMBER"),
        ("Counts may differ by a few points.", None),
        ("Counts may differ by a few %.", "NUMBER"),
        ("Counts may differ in two ways.", "NUMBER"),
        ("Counts may differ in several ways.", None),
        ("Counts may be higher in July.", "NUMBER"),
        ("Counts may be higher in summer.", None),
    ]),
    "ADVICE": (("advice_words", "should", "policy should", "the county should", "recommend*",
                "need to"), [
        ("Policy should change, though it may depend on the place.", "ADVICE"),
        ("Policy may change, depending on the place.", None),
        ("The county should hire more staff, though it could vary.", "ADVICE"),
        ("The county could hire more staff, though it depends.", None),
        ("I recommend caution, since results might vary.", "ADVICE"),
        ("Results might vary.", None),
        ("Places NEED TO track arrests, and it may depend on rules.", "ADVICE"),
        ("Places may track arrests in different ways.", None),
    ]),
    "CERTAIN": (("certain_words", "studies show", "always", "according to", "montgomery",
                 "this data"), [
        ("Studies show that arrests may vary by place.", "CERTAIN"),
        ("Arrests may vary by place.", None),
        ("Arrests always vary, and it depends on the place.", "CERTAIN"),
        ("Arrests often vary, and it depends on the place.", None),
        ("According to experts, arrests might rise in summer.", "CERTAIN"),
        ("Arrests might rise in summer.", None),
        ("In MONTGOMERY, arrests may vary.", "CERTAIN"),
        ("In some places, arrests may vary.", None),
        ("This data may show a pattern.", "CERTAIN"),
        ("Such data may show a pattern.", None),
    ]),
    "HEDGE": (("hedge_words", "often", "can vary"), [
        ("Arrest counts differ between places for many reasons.", "HEDGE"),
        ("Arrest counts often differ between places for many reasons.", None),
        ("Recording practices differ between places.", "HEDGE"),
        ("Recording practices can vary between places.", None),
    ]),
    "SHAPE": (None, [
        ("", "SHAPE"),
        # more than five sentences
        ("Counts may differ. Places differ. Records differ. Rules differ. That is all. "
         "Thanks.", "SHAPE"),
        ("Counts may differ! Why? Places differ. Records differ. Rules differ. That is all.",
         "SHAPE"),
        ("Counts may differ. Places differ. Records differ. Rules differ. That is all.", None),
        ("Counts may differ.\nPlaces differ.", "SHAPE"),
        ("Counts may differ. Places differ.", None),
        *[(f"Counts may differ {mark}.", "SHAPE") for mark in MARKS + ["_"]],
        # 700 characters
        (background_sized("Arrest counts may differ between places", ", and between seasons",
                          700, 800), "SHAPE"),
        (background_sized("Arrest counts may differ between places", ", and between seasons",
                          600, 700), None),
    ]),
}


def test_check_background_passes_a_hedged_text():
    """A7 check_background(text, rules) -> [] for a hedged text that breaks no rule."""
    replies = mod("replies")
    listed("hedge_words", "may", "it depends", "one explanation", "could")
    rules = replies.load_rules()
    check_background_cases(lambda text: replies.check_background(text, rules), [
        (BACKGROUND_PASS, None),
        ("One explanation could be how police record arrests in each place.", None),
    ])


@pytest.mark.parametrize("code", list(BACKGROUND))
def test_check_background_codes(code):
    """A7 check_background: SLOT; NUMBER (a digit, "%", a number word, a month name);
    ADVICE (with "policy should" and "the county should"); CERTAIN; HEDGE (no hedge word);
    SHAPE (five sentences and 700 characters)."""
    replies = mod("replies")
    relied, cases = BACKGROUND[code]
    if relied:
        listed(*relied)
    if code == "NUMBER":
        listed("month_names", "july")
        # any digit, even a number of the fact lines
        fact_numbers = sorted(numbers_in(" ".join(fact_lines())))
        cases = cases + [(f"Counts may differ in {n}.", "NUMBER")
                         for n in (fact_numbers[0], fact_numbers[-1])]
    rules = replies.load_rules()
    assert sum(1 for _, c in cases if c == code) >= 2
    check_background_cases(lambda text: replies.check_background(text, rules), cases)


# ---- render_fixed (A7, unchanged) --------------------------------------------------------

@pytest.mark.parametrize("year, group", [
    (2025, "18_25"), (2025, "under_18"), (2025, "41_plus"), (2024, None),
], ids=["2025 18_25", "2025 under_18 quietest tie", "2025 41_plus busiest tie",
        "2024 all ages over 1000"])
def test_render_fixed_one_count(tmp_path, year, group):
    """A7: `In <year> there were <total> arrest records <age phrase>.` then the months
    sentence, with ties listed `A and B`, `were`, `months` and ` each`."""
    replies = mod("replies")
    results = turn_results(tmp_path, (year, group))
    line = replies.render_fixed(results, load_registry())
    assert re.fullmatch(fixed_line1_re([(year, group)]), line), line


def test_render_fixed_one_count_with_every_month_equal(tmp_path):
    """A7: every month equal: `Every month had the same count (<n>).` A changed copy of the
    data gives every month of 2025 the January count of ages 18 to 25."""
    replies = mod("replies")

    def change(counts):
        for m in range(2, 13):
            counts[f"2025-{m:02d}"]["18_25"] = counts["2025-01"]["18_25"]

    path, counts = changed_data(tmp_path, "0-every-month-equal", change)
    assert len(set(months(2025, "18_25", counts))) == 1
    results = turn_results(tmp_path, (2025, "18_25"), data_path=path)
    line = replies.render_fixed(results, load_registry())
    assert re.fullmatch(fixed_line1_re([(2025, "18_25")], data_counts=counts), line), line


@pytest.mark.parametrize("counts", [
    [(2024, "under_18"), (2025, "under_18")],
    [(2025, "under_18"), (2025, "18_25"), (2024, None)],
], ids=["two counts", "three counts"])
def test_render_fixed_counts_without_a_compare(tmp_path, counts):
    """A7: two counts, or more than two and no compare: the first sentence for each, no
    months sentence."""
    replies = mod("replies")
    results = turn_results(tmp_path, *counts)
    line = replies.render_fixed(results, load_registry())
    assert re.fullmatch(fixed_line1_re(counts), line), line


@pytest.mark.parametrize("counts", [
    [(2024, "under_18"), (2025, "under_18")],
    [(2025, group) for group in AGE_GROUPS],
], ids=["two counts and a compare", "four counts and a compare"])
def test_render_fixed_with_a_compare(tmp_path, counts):
    """A7: each compare result: `<Top label> had the highest count (<top_value>) and
    <bottom label> the lowest (<bottom_value>), a difference of <difference>.` With more
    than two counts, only the compare sentences are written."""
    replies = mod("replies")
    results = turn_results(tmp_path, *counts, compared=True)
    c = compare_expect([(y, g, sum(months(y, g))) for y, g in counts])
    line = replies.render_fixed(results, load_registry())
    assert re.fullmatch(fixed_line1_re(counts, [c]), line), line


def test_render_fixed_with_an_all_equal_compare(tmp_path):
    """A7: when all_equal, `The counts were the same (<top_value>) for <labels>.` A changed
    copy of the data gives 2024 the 2025 months of people under 18, so both totals are
    equal."""
    replies = mod("replies")

    def change(counts):
        for m in range(1, 13):
            counts[f"2024-{m:02d}"]["under_18"] = counts[f"2025-{m:02d}"]["under_18"]

    path, data_counts = changed_data(tmp_path, "0-equal-totals", change)
    pair = [(2024, "under_18"), (2025, "under_18")]
    totals = [sum(months(y, g, data_counts)) for y, g in pair]
    assert totals[0] == totals[1], "the equal totals this test needs"
    c = compare_expect([(y, g, t) for (y, g), t in zip(pair, totals)])
    assert c["all_equal"] is True
    results = turn_results(tmp_path, *pair, compared=True, data_path=path)
    line = replies.render_fixed(results, load_registry())
    assert re.fullmatch(fixed_line1_re(pair, [c], data_counts=data_counts), line), line


@pytest.mark.parametrize("equal", [False, True], ids=["truth", "all equal"])
def test_render_fixed_with_two_compares_of_three_counts(tmp_path, equal):
    """A7: one sentence per compare result, in order, and with more than two counts only
    the compare sentences, also when every compare is all_equal (a changed copy of the data
    gives 2025's ages 18 to 25 and 26 to 40 the months of people under 18)."""
    replies = mod("replies")
    triple = [(2025, "under_18"), (2025, "18_25"), (2025, "26_40")]

    def change(counts):
        for m in range(1, 13):
            for group in ("18_25", "26_40"):
                counts[f"2025-{m:02d}"][group] = counts[f"2025-{m:02d}"]["under_18"]

    path, data_counts = (changed_data(tmp_path, "0-equal-three", change) if equal
                         else (None, None))
    totals = [sum(months(y, g, data_counts)) for y, g in triple]
    compares = [compare_expect([(y, g, t) for (y, g), t in zip(triple[:n], totals)])
                for n in (2, 3)]
    assert all(c["all_equal"] is equal for c in compares), compares
    env = Env(tmp_path) if path is None else Env(tmp_path, data_path=path)
    reply = env.ask(COMPARE_QUESTION,
                    Step(*[count(y, g) for y, g in triple]),
                    Step(compare("r1", "r2")),
                    Step(compare("r1", "r2", "r3")),
                    Step(finish("finding", "Here is the comparison: {r5.compare}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.results) == 5, reply.results
    line = replies.render_fixed(reply.results, load_registry())
    assert re.fullmatch(fixed_line1_re(triple, compares, data_counts=data_counts), line), line
