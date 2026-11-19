"""C38 of docs/S3A-DESIGN.md (D-048, D-065): in county mode with MOCO_TALK on, T2's SHAPE check
on a `finding` and on an `about_data` text counts only the model's own words. Brief:
briefs/S3-R7-A-tests.md. Tests only; the planning chat makes the change.

C38's tests, each through the talk finding check (tsupport.first_try: the codes are the
`problems` of Python's REWRITE answer, T3) and, for the texts that pass, through a whole
county turn with the model stand-in (the reply sent):
- a finding with all seven rate slots of an age-band rate (Part S2's fixture, age_5y: seven
  bands shown) and one short sentence of its own passes; with three sentences of its own it
  fails SHAPE;
- a finding with 401 characters of its own words fails SHAPE and one with 400 passes;
- an about_data text with four facts of 250 characters each passes, with five it fails;
- a slot used twice fails; a line break fails (both: see the questions below).
And what C38 keeps: an empty text fails SHAPE; the other codes are unchanged; SYNTHETIC mode
and MOCO_TALK off are unchanged (the same texts are checked as today there).

READINGS (also in kit-log/raw/S3-R7-A-notes.txt):
- C38-1 "through the talk finding check": the contract names no function (as T7's reading
  in tests/t/tsupport.py); the check is seen through a turn, its codes in REWRITE's
  `problems`. "Through a county turn": the whole reply of a turn whose text passes.
- C38-2 "the model's own words (the text with every slot taken out)": the text as T10 tidies
  it, with each `{...}` slot removed and nothing else changed, measured in characters
  (spaces and the marks around a slot count). The texts put the slot first, so no space
  stands before it and no reading of "taken out" moves the count.
- C38-3 "the model's own sentences" are T2's talk sentences (sentences with no slot); a
  sentence that holds a slot is not one, whatever words it has (as today: the county test
  tests/t/test_t_mixed.py::test_a_county_finding_with_sentences_of_its_own passes "Here you
  go. I counted {r1.count}. Want a breakdown next?").
- C38-4 "four facts of 250 characters each": four facts whose text, as describe_data gives
  it, is 250 characters (made so by lengthening two fields of each fixture source in the
  test's own copy of the files: `row_meaning` and `is_not`). Their fill is 249 each (C11:
  the line without its final full stop) and the text filled is about 1,000 characters.
- C38-5 (open, briefs/QUESTIONS.md S3-R7-A question 1) "a slot used more than once" is in
  C38's list of SHAPE failures, and SLOT is "unchanged" (today it fails SLOT): SLOT is
  required, SHAPE with it is accepted.
- C38-6 (open, question 2) "a line break" fails SHAPE, but T10 (round 2) tidies every line
  break to a space before the check, so no line break is left to fail: SHAPE, or the text
  passing with the line break sent as one space, is accepted.
"""
import re
import sys
from pathlib import Path

import pytest

from p1support import (THREAD_1, THREAD_2, Step, count as synthetic_count, describe, finish,
                       fill_expect, count_slots)
from s3support import A_ID, C_ID, NAMES, Q_ABOUT, Q_COUNT, CountyEnv, count, truth, year

TESTS = Path(__file__).resolve().parents[1]
for _sub in ("t", "s3s", "s3s2"):
    if str(TESTS / _sub) not in sys.path:
        sys.path.insert(0, str(TESTS / _sub))

from tsupport import (FINDING_CODES, check_cases, county_labels, county_talk_env,  # noqa: E402
                      first_try, mixed_faults, padded, split_sentences, talk_env, talk_rules,
                      thread)
import s2support as T2  # noqa: E402
from s2agent import S2Env, rate_call  # noqa: E402

OWN_MOST = 400                 # C38: at most 400 characters of the model's own words
AGE_CASE = "age_5y"            # Part S2's age-band rate: seven bands shown (premise below)
COUNT_PHRASE = "240 arrest records in 2025"   # {r1.count} of a count of arrests_like, 2025
LABELS = county_labels(*NAMES)


@pytest.fixture(autouse=True)
def _no_census_key(monkeypatch):
    """As tests/s3s2/conftest.py: no Census key from the environment (the S2 fixture sets the
    made-up one itself when it fetches)."""
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)


def own(text):
    """C38-2: the text with every slot taken out (the test's own texts need no tidying)."""
    return re.sub(r"\{[^{}]*\}", "", text)


def run_on(env, question, before, kind="finding"):
    return lambda i, text: first_try(env, question, kind, text, *before, thread_key=thread(i))


def county_on(tmp_path, monkeypatch, **kw):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return county_talk_env(tmp_path, monkeypatch, **kw)


ONE_COUNT = (Step(count(A_ID, year(2025))),)


def test_premises():
    """No program code: T12's finding limit (2 talk sentences) stands; the age-band case shows
    seven bands; the count of arrests_like in 2025 is 240."""
    assert talk_rules()["most_talk_sentences_in_finding"] == 2
    t = T2.truth(AGE_CASE)
    assert t["by"] == "age_band" and len(t["shown"]) == 7, t["shown"]
    assert truth("arrests_like", year(2025))["total"] == 240


# ==== seven rate slots of an age-band rate ========================================================

def rate_slots():
    t = T2.truth(AGE_CASE)
    slots = [s for s in T2.slots(t) if ".rate." in s]
    assert slots == [f"{{a1.rate.{k}}}" for k in range(1, 8)], slots
    return t, slots


def seven(slots):
    return " ".join(f"{s}." for s in slots)


def rate_env(tmp_path, monkeypatch, **settings):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return S2Env(tmp_path, monkeypatch, names=(T2.MAIN,), **settings)


@pytest.mark.needs_r
def test_seven_rate_slots_with_one_sentence_of_its_own_pass_and_three_fail(tmp_path,
                                                                           monkeypatch):
    """C38: seven fact sentences (one rate slot each) and one short talk sentence pass; three
    talk sentences fail SHAPE."""
    t, slots = rate_slots()
    one_own = "Here you go. " + seven(slots)
    three_own = "Here you go. Hope it helps. " + seven(slots) + " Want more?"
    assert tuple(map(len, split_sentences(one_own))) == (7, 1)
    assert tuple(map(len, split_sentences(three_own))) == (7, 3)
    for text in (one_own, three_own):
        assert mixed_faults(text, LABELS) == set(), text
    env = rate_env(tmp_path, monkeypatch, MOCO_TALK="on")
    before = (Step(rate_call(T2.analyze_arguments(AGE_CASE))),)
    check_cases(run_on(env, "What is the arrest rate per resident by age?", before),
                [(one_own, None), (three_own, "SHAPE")], FINDING_CODES)


@pytest.mark.needs_r
def test_seven_rate_slots_with_one_sentence_of_its_own_are_sent_filled(tmp_path, monkeypatch):
    """C38 through a county turn: the finding is sent in the model's words, every rate slot
    filled with its phrase (Part S2 R10 point 2), with Python's lines after it as today."""
    t, slots = rate_slots()
    text = "Here you go. " + seven(slots)
    phrases = T2.phrases(t)
    line1 = "Here you go. " + " ".join(T2.cap(phrases[s]) + "." for s in slots)
    assert len(line1) > 700, "premise: the text filled is over T2's 700 characters"
    env = rate_env(tmp_path, monkeypatch, MOCO_TALK="on")
    reply = env.ask("What is the arrest rate per resident by age?",
                    Step(rate_call(T2.analyze_arguments(AGE_CASE))),
                    Step(finish("finding", text)), Step(finish("finding", text)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("ANSWERED", "finding", "agent"), (reply.status, reply.reply_style,
                                           reply.draft_failures, reply.text)
    assert len(env.model.calls) == 2, "the first finish passed: no REWRITE"
    assert reply.text.startswith(line1 + "\n"), reply.text


@pytest.mark.needs_r
def test_seven_rate_slots_with_talk_off_are_checked_as_today(tmp_path, monkeypatch):
    """C38: MOCO_TALK off is unchanged: R1 refuses seven sentences (SHAPE) and the fixed
    rendering is sent."""
    t, slots = rate_slots()
    env = rate_env(tmp_path, monkeypatch)
    reply = env.ask("What is the arrest rate per resident by age?",
                    Step(rate_call(T2.analyze_arguments(AGE_CASE))),
                    Step(finish("finding", seven(slots))))
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert list(reply.draft_failures) == ["SHAPE"], reply.draft_failures
    assert reply.text.startswith(T2.line1(t) + "\n"), reply.text


# ==== 400 and 401 characters of the model's own words =============================================

def own_texts(length):
    """`{r1.count}. ` and one talk sentence of letters only, with `length` characters of the
    model's own words (C38-2)."""
    text = padded("{r1.count}. ", "", length, measure=lambda s: len(own(s)))
    assert len(own(text)) == length
    assert tuple(map(len, split_sentences(text))) == (1, 1), text
    assert mixed_faults(text, LABELS) == set(), text
    return text


def test_400_characters_of_its_own_pass_and_401_fail(tmp_path, monkeypatch):
    """C38: more than 400 characters of the model's own words fail SHAPE; 400 pass. Both are
    well under 700 once filled, so only C38's limit can refuse the second."""
    at, over = own_texts(OWN_MOST), own_texts(OWN_MOST + 1)
    for text in (at, over):
        assert len(text.replace("{r1.count}", COUNT_PHRASE)) < 700
    env = county_on(tmp_path, monkeypatch)
    check_cases(run_on(env, Q_COUNT, ONE_COUNT), [(at, None), (over, "SHAPE")], FINDING_CODES)


def test_400_characters_of_its_own_are_sent_filled(tmp_path, monkeypatch):
    """C38 through a county turn: the passing text is line 1, filled; the source line follows
    as today (C10)."""
    text = own_texts(OWN_MOST)
    env = county_on(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, *ONE_COUNT, Step(finish("finding", text)),
                    Step(finish("finding", text)))
    assert (reply.status, reply.reply_style) == ("ANSWERED", "agent"), \
        (reply.status, reply.reply_style, reply.draft_failures)
    assert reply.text.startswith(text.replace("{r1.count}", COUNT_PHRASE) + "\n"), reply.text
    assert "county open data" in reply.text.lower()


def test_401_characters_of_its_own_are_not_sent(tmp_path, monkeypatch):
    """C38 through a county turn: the text fails twice (the same text again after REWRITE),
    so the fixed rendering is sent and none of the model's words."""
    text = own_texts(OWN_MOST + 1)
    env = county_on(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, *ONE_COUNT, Step(finish("finding", text)),
                    Step(finish("finding", text)))
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text
    assert "glad to help" not in reply.text
    assert reply.text.startswith(f"I counted {COUNT_PHRASE}."), reply.text


def test_synthetic_mode_keeps_todays_limits(tmp_path):
    """C38: SYNTHETIC mode with MOCO_TALK on is unchanged: 401 characters of its own pass
    there, since T2's limit is 700 once filled (five fact sentences still failing SHAPE there
    is tests/t/test_t_mixed.py's)."""
    phrases = count_slots("r1", 2025, "18_25")
    over = padded("{r1.count}. ", "", OWN_MOST + 1, measure=lambda s: len(own(s)))
    assert len(fill_expect(over, phrases)) < 700
    assert mixed_faults(over) == set(), over
    env = talk_env(tmp_path)
    check_cases(run_on(env, "How many arrests were recorded in 2025 for ages 18 to 25?",
                       (Step(synthetic_count(2025, "18_25")),)),
                [(over, None)], FINDING_CODES)


# ==== about_data: four facts of 250 characters ====================================================

def _pad(n):
    """A plain phrase of exactly n characters, letters and spaces (SYNTHETIC filler)."""
    words = ("made up words that only pad this SYNTHETIC test fact and mean nothing at all "
             * 4)
    out = words[:n]
    return out[:-1] + "x" if out.endswith(" ") else out


# Today's fact lines (describe_data, C11) with the fixture files: f1 is 184 characters with a
# row_meaning of 18; f4 is 146 with six is_not items; f8 is 191 with a row_meaning of 18; f11
# is 129 with four is_not items. Lengthened by hand to 250 each (an is_not item X added last
# turns "... or a rate" into "..., a rate or X": 2 more characters than X).
LONG = {
    "arrests_like": {"row_meaning": "one made-up arrest, " + _pad(84 - 20),
                     "is_not_extra": _pad(104 - 2)},
    "coded_like": {"row_meaning": "one made-up intake, " + _pad(77 - 20),
                   "is_not_extra": _pad(121 - 2)},
}
FOUR = ("{f1}", "{f4}", "{f8}", "{f11}")   # arrests_like f1 and f4, coded_like f1 and f4
FIFTH = "{f2}"


def _lengthen(name):
    def change(data):
        data["row_meaning"] = LONG[name]["row_meaning"]
        data["is_not"] = list(data["is_not"]) + [LONG[name]["is_not_extra"]]
    return change


def long_facts_env(tmp_path, monkeypatch, **settings):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return CountyEnv(tmp_path, monkeypatch, names=NAMES,
                     change={n: _lengthen(n) for n in NAMES}, **settings)


def facts_of(env):
    (answer,) = [a for a in env.answers() if "facts" in a]
    return {f["slot"]: f["text"] for f in answer["facts"]}


def notices(env):
    lines = [n for name in NAMES for n in env.source(name)["notices"]]
    return lines + ["This agent is a university course project. It is not a county service."]


def four_text():
    return " ".join(f"{s}." for s in FOUR)


def five_text():
    return " ".join(f"{s}." for s in FOUR + (FIFTH,))


def test_the_four_facts_are_250_characters(tmp_path, monkeypatch):
    """Premise (C38-4), read from the turn's own describe_data answer: f1, f4, f8 and f11 are
    250 characters each, the first two of arrests_like and the other two of coded_like."""
    env = long_facts_env(tmp_path, monkeypatch)
    env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    facts = facts_of(env)
    assert {s: len(facts[s]) for s in FOUR} == {s: 250 for s in FOUR}, \
        {s: len(facts[s]) for s in FOUR}
    titles = {n: env.source(n)["title"] for n in NAMES}
    assert facts["{f1}"].startswith(titles["arrests_like"] + " is published by")
    assert facts["{f4}"].startswith("A count of " + titles["arrests_like"])
    assert facts["{f8}"].startswith(titles["coded_like"] + " is published by")
    assert facts["{f11}"].startswith("A count of " + titles["coded_like"])
    assert len(" ".join(facts[s] for s in FOUR)) > 1000


def test_four_facts_of_250_pass_and_five_fail(tmp_path, monkeypatch):
    """C38: how long the slots are once filled no longer counts; at most four fact slots
    (C11's "up to four") still does: five fail SHAPE.
    Changed by briefs/S3-R26-A-tests.md (C63): four_text() and five_text() are plain facts
    texts, so neither is checked and both end the turn at the first finish (it was five failing
    SHAPE). C38's check is kept alive with texts that are not plain: the same slots after a
    sentence of the model's own ("Here is the data."), four passing and five failing SHAPE."""
    env = long_facts_env(tmp_path, monkeypatch, MOCO_TALK="on")
    own = "Here is the data. "
    check_cases(run_on(env, Q_ABOUT, (Step(describe()),), kind="about_data"),
                [(four_text(), None), (five_text(), None), (own + four_text(), None),
                 (own + five_text(), "SHAPE")], FINDING_CODES)


def test_four_facts_of_250_are_sent_filled_with_the_notices(tmp_path, monkeypatch):
    """C38 through a county turn: EXPLAINED, kind about_data, style agent; the text is the four
    facts filled (each the line without its full stop, then the text's own full stop), then
    the notices word for word and the course line (C11), as today.
    Changed by briefs/S3-R26-A-tests.md (C63): four_text() is a plain facts text, so it is sent
    as C63's rendering, `Here is what I know.` and the four facts (it was the four facts alone).
    C38's fill is kept alive with a text that is not plain ("Here is the data." and the same
    slots, in a second thread so its notices are in full too): sent filled, as before."""
    env = long_facts_env(tmp_path, monkeypatch, MOCO_TALK="on")
    facts = None
    for thread_key, own in ((THREAD_1, None), (THREAD_2, "Here is the data.")):
        text = four_text() if own is None else f"{own} {four_text()}"
        reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", text)),
                        Step(finish("about_data", text)), thread_key=thread_key)
        assert (reply.status, reply.reply_kind, reply.reply_style) == \
            ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style,
                                                   reply.draft_failures)
        facts = facts or facts_of(env)
        filled = " ".join(facts[s] for s in FOUR)
        lead = "Here is what I know." if own is None else own
        assert reply.text == "\n".join([f"{lead} {filled}"] + notices(env)), reply.text


def test_four_facts_of_250_with_talk_off_are_checked_as_today(tmp_path, monkeypatch):
    """C38: MOCO_TALK off is unchanged: R1 refuses the text for its length once filled (SHAPE)
    and the fixed about text is sent.
    Changed by briefs/S3-R26-A-tests.md (C63, "with talk on or off"): four_text() is a plain
    facts text, so with talk off too it is sent as C63's rendering, unchecked, style agent, no
    failure (it was refused, SHAPE). R1's length check is kept alive with a text that is not
    plain, one word of its own ("Also {f1}. {f4}. {f8}. {f11}.", four sentences as before): SHAPE
    alone, style fallback."""
    env = long_facts_env(tmp_path, monkeypatch)
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", four_text())))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), reply.text
    assert list(reply.draft_failures) == [], reply.draft_failures
    facts = facts_of(env)
    assert reply.text.startswith("Here is what I know. " + " ".join(facts[s] for s in FOUR)
                                 + "\n"), reply.text
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "Also " + four_text())),
                    thread_key=THREAD_2)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fallback"), reply.text
    assert list(reply.draft_failures) == ["SHAPE"], reply.draft_failures


# ==== a slot twice, a line break, an empty text, the other codes ==================================

def test_a_slot_used_twice_fails(tmp_path, monkeypatch):
    """C38: a slot used more than once fails (C38-5: SLOT, with SHAPE accepted beside it), in a
    finding and in an about_data text.
    Changed by briefs/S3-R26-A-tests.md (C63): "{f1}. Here is what I know. {f1}." is a plain
    facts text, so it is not checked: the turn ends at the first finish with C63's rendering, the
    fact once, style agent (it failed SLOT). The check is kept alive in an about_data text with a
    text that is not plain, one word of its own in place of the opening ("{f1}. Here is the
    data. {f1}."): SLOT, as before."""
    env = county_on(tmp_path / "finding", monkeypatch)
    text = "{r1.count}. Here you go. {r1.count}."
    reply, problems = first_try(env, Q_COUNT, "finding", text, *ONE_COUNT)
    assert problems is not None and set(problems) in ({"SLOT"}, {"SLOT", "SHAPE"}), problems
    assert reply.reply_style == "fallback"
    env = county_on(tmp_path / "about", monkeypatch)
    text = "{f1}. Here is what I know. {f1}."
    reply, problems = first_try(env, Q_ABOUT, "about_data", text, Step(describe()))
    assert problems is None and reply.reply_style == "agent", (problems, reply.reply_style)
    (answer,) = [a for a in env.answers() if "facts" in a]
    assert reply.text.split("\n")[0] == "Here is what I know. " + answer["facts"][0]["text"], \
        reply.text
    env = county_on(tmp_path / "about-not-plain", monkeypatch)
    text = "{f1}. Here is the data. {f1}."
    reply, problems = first_try(env, Q_ABOUT, "about_data", text, Step(describe()))
    assert problems is not None and set(problems) in ({"SLOT"}, {"SLOT", "SHAPE"}), problems


def test_a_line_break_fails_or_is_tidied_away(tmp_path, monkeypatch):
    """C38: a line break fails SHAPE (C38-6, open: T10 tidies it to one space first, so the
    text passing as tidied is accepted too)."""
    text = "{r1.count}.\nHappy to help."
    env = county_on(tmp_path, monkeypatch)
    reply, problems = first_try(env, Q_COUNT, "finding", text, *ONE_COUNT)
    if problems is None:
        assert reply.reply_style == "agent", reply.text
        assert reply.text.startswith(COUNT_PHRASE + ". Happy to help.\n"), reply.text
    else:
        assert problems == ["SHAPE"], problems


def test_an_empty_text_fails_shape(tmp_path, monkeypatch):
    """C38: an empty text fails SHAPE (SLOT may come with it, as tests/t reads T2)."""
    env = county_on(tmp_path, monkeypatch)
    reply, problems = first_try(env, Q_COUNT, "finding", "", *ONE_COUNT)
    assert problems is not None and "SHAPE" in problems, problems
    assert set(problems) <= {"SHAPE", "SLOT"}, problems


OTHER_CODES = [
    ("{r1.count}. That is a lot.", "JUDGE"),
    ("{r1.count}. It went up because of summer.", "CLAIM"),
    ("{r1.count}. Twice last year.", "NUMBER"),
    ("{r1.count}. Want the Hispanic records next?", "LABEL"),
    ("I counted roughly {r1.count}.", "WORD"),
    ("Here you go. I counted:{r1.count}.", "GLUE"),
    ("Here you go. I counted {r2.count}.", "SLOT"),
    ('I "counted" {r1.count}.', "CHARS"),
]


def test_every_other_code_is_unchanged(tmp_path, monkeypatch):
    """C38: NUMBER, LABEL, CLAIM, CHARS, JUDGE, GLUE, SLOT and WORD are unchanged in county mode
    with MOCO_TALK on (ORDER: tests/t/test_t_mixed.py's county test). Premise: the content
    codes are the texts' own (tsupport.mixed_faults); GLUE and SLOT texts have none."""
    for text, code in OTHER_CODES:
        want = {code} if code in ("JUDGE", "CLAIM", "NUMBER", "LABEL", "WORD", "CHARS") else set()
        assert mixed_faults(text, LABELS) == want, (text, mixed_faults(text, LABELS))
    env = county_on(tmp_path, monkeypatch)
    check_cases(run_on(env, Q_COUNT, ONE_COUNT), OTHER_CODES, FINDING_CODES)


def test_a_slot_of_no_tool_answer_of_this_turn_fails(tmp_path, monkeypatch):
    """C38: "a slot must be one the tool answers of this turn listed": a count's slot from an
    earlier turn of the thread is not offered in a turn that counted nothing new."""
    env = county_on(tmp_path, monkeypatch)
    first = env.ask(Q_COUNT, *ONE_COUNT, Step(finish("finding", "{r1.count}.")))
    assert first.reply_style == "agent", first.text
    reply, problems = first_try(env, Q_ABOUT, "about_data", "Here you go. {r1.count}.",
                                Step(describe()))
    assert problems is not None and "SLOT" in problems, problems


def test_coded_like_source_is_checked_the_same_way(tmp_path, monkeypatch):
    """C38 holds for any county source: 401 characters of its own fail with a count of
    coded_like too."""
    env = county_on(tmp_path, monkeypatch, names=NAMES)
    text = own_texts(OWN_MOST + 1)
    reply, problems = first_try(env, Q_COUNT, "finding", text,
                                Step(count(C_ID, year(2025))))
    assert problems == ["SHAPE"], problems
