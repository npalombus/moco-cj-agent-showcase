"""T1's talk check on its own (docs/T-DESIGN.md T1 and T7's second point): a turn with no
result whose model ends it with finish(kind "talk", text).

What this file covers
- Texts that break no rule are sent exactly as written: TALKED, kind talk, style agent.
  They include what the talk check does not look at: judgement words ("a lot", "big"; JUDGE
  is T2's, for a finding only), words outside R1's list, "May" (not in month_names), "one"
  (not in number_words), "decent" (a month abbreviation inside a word), every mark of
  allowed_marks and the curly apostrophe.
- For each code, NUMBER, LABEL, CLAIM, CHARS and SHAPE, texts that fail with it and texts
  beside them that pass: a digit, "%", number words (with a * entry), month names and
  abbreviations in any case; the registry's age wordings in SYNTHETIC mode; the labels of
  the county fixture sources (category and flag fields, any case, of any loaded source);
  claim phrases (with a * entry); a brace (a slot written in a talk text holds a digit
  too, so NUMBER may come with it), a private-use character (C13), each kind of markup of
  reply_rules.json; empty, white space only.
- Round 2 (briefs/T2-A-tests.md step 3; each change is listed in
  kit-log/raw/T2-A-changed-tests.txt): a dash and quotation marks now pass (T11); `*` and
  the backtick are removed by tidying, and a line break becomes a space, so those texts
  pass (T10); five sentences and 501 characters now pass (T12, the limits are 6 and 700).
  The new edges, 6 and 7 sentences and 700 and 701 characters, are in test_t_round2.py.
- No code outside the five, ever.

Read through T3: a failing first text is answered with REWRITE, whose `problems` are the
check's codes (tsupport.first_try). Accepted both ways (kit-log/raw/T-A-notes.txt):
- A digit or "%" fails NUMBER; it is also not a letter, a space or an allowed mark, so
  CHARS may come with it. A line break fails SHAPE; CHARS may come with it. An age wording
  of the registry holds digits, so NUMBER comes with LABEL. Those cases are checked with
  the code among the codes, never as exactly that code.
- The order of the codes, and a code listed twice: compared as a set.
"""
import pytest

from p1support import Step, finish, sentences
from s3support import NAMES
from tsupport import (HELLO_TEXT, TALK_CODES, THANKS_TEXT, assert_talked, check_cases,
                      county_labels, county_talk_env, first_try, padded, premise_talk,
                      synthetic_labels, talk_env, talk_faults, talk_rules, thread)

QUESTION = "hello"

PASSING = [
    HELLO_TEXT,
    THANKS_TEXT,
    "I'm doing well, thanks for asking! How can I help you today?",
    "That's a lot of questions, and I'm happy to take them all.",
    "It’s a big help to hear that - thank you!",
    "Sure: I can say it more briefly next time; just ask (no problem).",
    "Good one. I hope you have a decent afternoon.",
    "Maybe later? May I help with anything else?",
]

CASES = {
    "NUMBER": [
        ("I can give you 2 answers.", {"NUMBER"}),
        ("I'm 100% sure about that.", {"NUMBER"}),
        ("That is my % guess.", {"NUMBER"}),
        ("I can look at two years for you.", "NUMBER"),
        ("TWICE as quick next time!", "NUMBER"),
        ("Happy to look through hundreds of records.", "NUMBER"),
        ("Happy to help in March or any time.", "NUMBER"),
        ("Sure, see you in DEC.", "NUMBER"),
        ("Glad to help, half the fun is asking.", "NUMBER"),
        ("Happy to help in May or any time.", None),
        ("That was a decent question.", None),
        ("Good one!", None),
    ],
    "CLAIM": [
        ("It went up because of summer.", "CLAIM"),
        ("In fact, I can help with that.", "CLAIM"),
        ("Happy to do more than that.", "CLAIM"),
        ("The data shows plenty, so ask away.", "CLAIM"),
        ("Things are TRENDING today.", "CLAIM"),
        ("Interest SURGED today, so ask away!", "CLAIM"),
        ("I can't say why, but I can count it for you.", None),
        ("The records cannot tell me that, sorry.", None),
    ],
    "CHARS": [
        ("Hi there — how can I help?", None),        # round 2, T11: was CHARS
        ("Hi there – how can I help?", None),        # round 2, T11: was CHARS
        ('You said "hello" to me.', None),            # round 2, T11: was CHARS
        ("Hello {friend}, how are you?", "CHARS"),
        ("Hello {r1.count}!", {"CHARS"}),
        ("Hello  there.", "CHARS"),
        ("Write to me @ any time.", "CHARS"),
        ("Look at the http page for that.", "CHARS"),
        ("Use *this* one.", None),                    # round 2, T10 step 2: was CHARS
        ("Use `this` one.", None),                    # round 2, T10 step 2: was CHARS
        ("Hash # marks are fine?", "CHARS"),
        ("Less <than> that.", "CHARS"),
        ("You & me, any time.", "CHARS"),
        ("Yes/no questions are fine.", "CHARS"),
        ("Sure: fine; (yes) - it's ok, isn’t it? Great!", None),
    ],
    "SHAPE": [
        ("", "SHAPE"),
        ("   ", "SHAPE"),
        ("Hi. How are you? I am well. Ask me anything. Thanks!", None),  # T12: was SHAPE
        ("Hello!\nHow can I help?", None),            # round 2, T10 step 3: was SHAPE
        ("Hello! How can I help?\r", None),           # round 2, T10 step 3: was SHAPE
        ("Hi. How are you? I am well. Ask me anything.", None),
    ],
}


def run_on(env, question=QUESTION):
    return lambda i, text: first_try(env, question, "talk", text, thread_key=thread(i))


def test_talk_texts_that_break_no_rule_are_sent_as_they_are(tmp_path):
    """T1: a text that passes is sent as it is: TALKED, kind talk, style agent, the text
    exactly as written, one model call. No whitelist of words, and no JUDGE, applies to
    talk."""
    labels = synthetic_labels()
    for text in PASSING:
        premise_talk(text, None, labels)
    assert any(" a lot " in t or " big " in t for t in PASSING)  # judgement words, allowed
    env = talk_env(tmp_path)
    for i, text in enumerate(PASSING):
        reply = env.ask(QUESTION, Step(finish("talk", text)), thread_key=thread(i))
        assert_talked(reply, text)
        assert len(env.model.calls) == 1


@pytest.mark.parametrize("code", list(CASES))
def test_each_code_both_ways(tmp_path, code):
    """T1: NUMBER, CLAIM, CHARS and SHAPE, each with texts that fail and texts that pass;
    every code returned is one of T1's five."""
    labels = synthetic_labels()
    for text, want in CASES[code]:
        premise_talk(text, want, labels)
    assert sum(1 for _, want in CASES[code] if want is not None) >= 2
    assert any(want is None for _, want in CASES[code])
    check_cases(run_on(talk_env(tmp_path)), CASES[code], TALK_CODES)


def test_label_in_synthetic_mode_is_an_age_wording_of_the_registry(tmp_path):
    """T1 LABEL in SYNTHETIC mode: any age wording of the registry, any case. Each wording
    holds digits, so NUMBER comes with it. A text naming no wording passes."""
    labels = synthetic_labels()
    assert "ages 18 to 25" in labels and "people under 18" in labels
    cases = [("Want me to look at ages 18 to 25 next?", {"LABEL", "NUMBER"}),
             ("PEOPLE UNDER 18 are a fine topic.", {"LABEL", "NUMBER"}),
             ("Ask me about ages 41 and over.", {"LABEL", "NUMBER"}),
             ("Want me to look at another age group next?", None)]
    for text, want in cases:
        premise_talk(text, want, labels)
    check_cases(run_on(talk_env(tmp_path)), cases, TALK_CODES)


def test_label_in_county_mode_is_a_label_of_a_fixture_source(tmp_path, monkeypatch):
    """T1 LABEL in county mode: any label of any category or flag field of a loaded source,
    whole words, any letter case. The labels are read from the fixture's source file: a
    category label of words only fails LABEL alone; the flag's label and a district hold
    digits, so NUMBER comes with them."""
    labels = county_labels("arrests_like")
    assert {"Hispanic", "group Alpha", "female", "within 500 feet of a school",
            "district 3"} <= set(labels)
    cases = [("Ask me about Hispanic records any time.", "LABEL"),
             ("I can count records for GROUP ALPHA too.", "LABEL"),
             ("Female and male are both fields I know.", "LABEL"),
             ("Ask me about within 500 feet of a school.", {"LABEL", "NUMBER"}),
             ("Want district 3 next?", {"LABEL", "NUMBER"}),
             ("Ask me about another field any time.", None),
             (HELLO_TEXT, None)]
    for text, want in cases:
        premise_talk(text, want, labels)
    env = county_talk_env(tmp_path, monkeypatch)
    check_cases(run_on(env), cases, TALK_CODES)


def test_label_of_any_loaded_source(tmp_path, monkeypatch):
    """T1 LABEL: "any loaded source": with both fixture sources loaded, a label that only
    the second one has (coded_like's "group W") fails too."""
    assert "group W" in county_labels("coded_like")
    assert "group W" not in county_labels("arrests_like")
    text = "I can count group W records as well."
    premise_talk(text, "LABEL", county_labels(*NAMES))
    env = county_talk_env(tmp_path, monkeypatch, names=NAMES)
    check_cases(run_on(env), [(text, "LABEL"), (HELLO_TEXT, None)], TALK_CODES)


def test_the_sentence_limit_at_its_edge(tmp_path):
    """T1 SHAPE: at most most_talk_sentences_in_talk sentences. Round 2 (T12): the limit is
    6 (was 4), so four pass and five now pass too (they failed SHAPE before)."""
    most = talk_rules()["most_talk_sentences_in_talk"]
    assert most == 6
    four = "Hi there. How are you? I am well! Ask me anything."
    five = four + " Thanks."
    assert (len(sentences(four)), len(sentences(five))) == (4, 5)
    premise_talk(four, None)
    premise_talk(five, None)
    check_cases(run_on(talk_env(tmp_path)), [(four, None), (five, None)], TALK_CODES)


def test_the_character_limit_at_its_edge(tmp_path):
    """T1 SHAPE: at most most_chars_talk characters. Round 2 (T12): the limit is 700 (was
    500), so 500 pass and 501 now pass too (they failed SHAPE before)."""
    most = talk_rules()["most_chars_talk"]
    assert most == 700
    at = padded("Hello there! ", "", 500)
    over = padded("Hello there! ", "", 501)
    premise_talk(at, None)
    premise_talk(over, None)
    check_cases(run_on(talk_env(tmp_path)), [(at, None), (over, None)], TALK_CODES)


def test_a_text_with_several_faults_gets_each_code(tmp_path):
    """T1: the check lists every code a text fails, not only the first. Round 2 (T11): the
    em dash is an allowed mark now, so the codes are NUMBER and CLAIM, and CHARS is not
    among them (it was)."""
    text = "It went up in March — because of summer."
    premise_talk(text, {"NUMBER", "CLAIM"})
    assert talk_faults(text) == {"NUMBER", "CLAIM"}
    _, problems = first_try(talk_env(tmp_path), QUESTION, "talk", text)
    assert problems is not None and set(problems) == {"NUMBER", "CLAIM"}, problems


def test_the_same_check_in_county_mode(tmp_path, monkeypatch):
    """T1 in county mode: the same rules for numbers, claims, characters and shape. Round 2:
    the em dash passes (T11) and five sentences pass (T12); both failed before."""
    cases = [(HELLO_TEXT, None), (THANKS_TEXT, None),
             ("I can look at two years for you.", "NUMBER"),
             ("It went up because of summer.", "CLAIM"),
             ("Hi there — how can I help?", None),                       # T11: was CHARS
             ("Hi. How are you? I am well. Ask me anything. Thanks!", None)]  # T12: was SHAPE
    labels = county_labels("arrests_like")
    for text, want in cases:
        premise_talk(text, want, labels)
    check_cases(run_on(county_talk_env(tmp_path, monkeypatch)), cases, TALK_CODES)
