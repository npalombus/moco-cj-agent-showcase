"""The gaps round of Part T: docs/T-DESIGN.md T16 point 8. Brief briefs/GAPS-A-tests.md step 4.
Why: kit-log/raw/CHAT-BUILDS-check.txt, PROOF GAP 2. Everything here runs with MOCO_TALK on.

T16 point 8: "Every run of white space" in T10 means every character Python's `\\s` matches,
not only the five T10 names: also the vertical tab, the form feed, U+0085, U+2002 to U+200A,
U+3000 and U+001C to U+001F. Each becomes one space.

For each character point 8 names (17, one case each) and for one text holding all of them in
a run (one more case):
- replies.tidy turns it into one space between two words, and trims it at the ends;
- a talk text with it between two words is sent with one space there, in both data modes;
- a finding with it between two words (in a talk sentence and in a fact sentence) is sent
  with one space there, in both data modes;
- the step log keeps the model's own text, the character included;
- a figure hidden behind it (a digit, and a number word, straight after it) still fails
  NUMBER, in a talk text and in a talk sentence of a finding, in both data modes.

The stand-ins and helpers are tests/p1's, tests/s3's and tests/t's, imported (tsupport, and
the round 2 file's own helpers from tests/t/test_t_round2.py); nothing is copied. Every
expected text and code is written out by hand. All data is SYNTHETIC.

Readings (each also in kit-log/raw/GAPS-A-notes.txt):
1. "In both data modes where T15 names a finding": the finding is tried in SYNTHETIC mode
   and in county mode (as test_t_round2.py does for T10). The talk text is tried in both
   modes too, so the case holds under either reading of the sentence.
2. U+2007 and U+2009 are in T10's step 1 as well (they become a space there); they are
   tried here again because point 8 names them (U+2002 to U+200A).
3. Python's `\\s` also matches U+1680, U+2000, U+2001 and U+205F, which point 8 does not
   name. Point 8's first sentence covers them, but the brief asks for "each character it
   names", so they are not tried here.
4. "The step log keeps the model's own text": a list of steps in turn.json (each an object
   with `text`, as test_t_round2.step_lists finds them) holds the model's finish text with
   the character in it, exactly.
"""
import re

import pytest

from p1support import Step, assert_answered, count, fill_expect, finish, has_leaf, mod
from s3support import (A_ID, C64_TALK_LINE, Q_COUNT, count as county_count, county_fallback_line,
                       fallback_lines, year)
from test_t_round2 import (COUNTY_LINE1, LINE1, Q, county_finding_reply, county_on, on,
                           step_lists)
from tsupport import (assert_talked, county_labels, first_try, mixed_faults,
                      premise_talk, synthetic_labels, talk_faults, thread, tidied, turn_json)

NAMED = {   # T16 point 8, by hand
    "U+000B vertical tab": "\x0b",
    "U+000C form feed": "\x0c",
    "U+0085 next line": "\x85",
    "U+2002 en space": " ",
    "U+2003 em space": " ",
    "U+2004 three-per-em space": " ",
    "U+2005 four-per-em space": " ",
    "U+2006 six-per-em space": " ",
    "U+2007 figure space": " ",
    "U+2008 punctuation space": " ",
    "U+2009 thin space": " ",
    "U+200A hair space": " ",
    "U+3000 ideographic space": "　",
    "U+001C file separator": "\x1c",
    "U+001D group separator": "\x1d",
    "U+001E record separator": "\x1e",
    "U+001F unit separator": "\x1f",
}
CASES = dict(NAMED, **{"all 17 in a run": "".join(NAMED.values())})
MODES = ["synthetic", "county"]


def test_the_named_characters_are_these_seventeen():
    """The premise of every case: the 17 characters point 8 names, each one Python's `\\s`
    matches, and none of them a plain space."""
    assert len(NAMED) == 17 and len(set(NAMED.values())) == 17
    assert sorted(ord(ch) for ch in NAMED.values()) == \
        [0x0B, 0x0C, 0x1C, 0x1D, 0x1E, 0x1F, 0x85] + list(range(0x2002, 0x200B)) + [0x3000]
    for ch in NAMED.values():
        assert re.fullmatch(r"\s", ch) and ch != " "


def env_for(mode, tmp_path, monkeypatch):
    return on(tmp_path) if mode == "synthetic" else county_on(tmp_path, monkeypatch)


def labels_for(mode):
    return synthetic_labels() if mode == "synthetic" else county_labels("arrests_like")


def kept_in_step_log(reply, env, raw):
    steps = step_lists(turn_json(reply, env.runs_dir))
    return bool(steps) and any(has_leaf(found, raw) for found in steps)


# ==== replies.tidy, on its own ================================================================

@pytest.mark.parametrize("ws", list(CASES.values()), ids=list(CASES))
def test_tidy_turns_it_into_one_space(ws):
    """Between two words the character (or the run) becomes one space; a run of it with a
    plain space, a tab and a line break is one space too; at the ends it is trimmed."""
    for text, want in [(f"Hello{ws}there", "Hello there"),
                       (f"Hello{ws} \t{ws}\nthere", "Hello there"),
                       (f"{ws}Hello there{ws}", "Hello there")]:
        assert tidied(text) == want, "the premise: the test's own reading of T10 and T16"
        assert mod("replies").tidy(text) == want, (text, mod("replies").tidy(text))


# ==== a talk text ==============================================================================

TALK_CLEAN = "Hello there! Ask me for a count whenever you like."


@pytest.mark.parametrize("ws", list(CASES.values()), ids=list(CASES))
@pytest.mark.parametrize("mode", MODES)
def test_a_talk_text_with_it_is_sent_with_one_space(tmp_path, monkeypatch, mode, ws):
    """The talk text passes at the first try and is sent with one plain space where the
    character was (TALKED, kind talk, style agent); the step log keeps the model's own."""
    raw = f"Hello{ws}there! Ask me for a count{ws}whenever you like."
    assert tidied(raw) == TALK_CLEAN
    premise_talk(TALK_CLEAN, None, labels_for(mode))
    env = env_for(mode, tmp_path, monkeypatch)
    reply = env.ask("hello", Step(finish("talk", raw)), Step(finish("talk", raw)))
    assert len(env.model.calls) == 1, "the text did not pass at the first try"
    assert_talked(reply, TALK_CLEAN)
    assert kept_in_step_log(reply, env, raw), "the step log lost the model's own text"


# ==== a finding =================================================================================

@pytest.mark.parametrize("ws", list(CASES.values()), ids=list(CASES))
@pytest.mark.parametrize("mode", MODES)
def test_a_finding_with_it_is_sent_with_one_space(tmp_path, monkeypatch, mode, ws):
    """The character stands between two words of a talk sentence and of a fact sentence. The
    finding passes at the first try; line 1 has one plain space at each place (style agent);
    the step log keeps the model's own text."""
    env = env_for(mode, tmp_path, monkeypatch)
    if mode == "synthetic":
        raw = f"Here{ws}you go! I{ws}counted {{r1.count}}. {{r1.months}}."
        clean = "Here you go! I counted {r1.count}. {r1.months}."
        before = Step(count(2025, "18_25"))
    else:
        raw = f"Here{ws}you go! I{ws}counted {{r1.count}}."
        clean = "Here you go! I counted {r1.count}."
        before = Step(county_count(A_ID, year(2025)))
    assert tidied(raw) == clean and mixed_faults(clean, labels_for(mode)) == set()
    reply = env.ask(Q if mode == "synthetic" else Q_COUNT, before,
                    Step(finish("finding", raw)), Step(finish("finding", raw)))
    assert len(env.model.calls) == 2, "the text did not pass at the first try"
    if mode == "synthetic":
        assert (reply.status, reply.reply_kind, reply.reply_style) == \
            ("ANSWERED", "finding", "agent"), (reply.status, reply.reply_style, reply.text)
        assert_answered(reply.text, re.escape(fill_expect(clean, LINE1)), first=True)
    else:
        county_finding_reply(reply, "Here you go! " + COUNTY_LINE1)
    assert kept_in_step_log(reply, env, raw), "the step log lost the model's own text"


# ==== a figure hidden behind it ==================================================================

@pytest.mark.parametrize("ws", list(CASES.values()), ids=list(CASES))
@pytest.mark.parametrize("mode", MODES)
def test_a_figure_behind_it_still_fails_number(tmp_path, monkeypatch, mode, ws):
    """A digit, or a number word, straight after the character still fails NUMBER: in a talk
    text (REWRITE with NUMBER, then the fallback line; no digit and no number word sent) and
    in a talk sentence of a finding (REWRITE with NUMBER, then the fixed rendering). Changed by
    briefs/S3-R28-A-tests.md (C64 point 1): in county mode the line is C64's
    (s3support.C64_TALK_LINE), as the text fails NUMBER; it was C61's county line. SYNTHETIC mode
    and the check that no figure is sent are unchanged."""
    env = env_for(mode, tmp_path, monkeypatch)
    wrong = []
    talks = [(f"There were{ws}7 of them.", "7"), (f"There were{ws}twelve of them.", "twelve")]
    for i, (text, figure) in enumerate(talks):
        assert "NUMBER" in talk_faults(text, labels_for(mode)), text
        reply, problems = first_try(env, "hello", "talk", text, thread_key=thread(i))
        if problems is None or "NUMBER" not in problems:
            wrong.append(f"{text!r}: the first try gave {problems}, want NUMBER among them")
        # Changed by briefs/S3-R21-A-tests.md (C57 point 6 of docs/S3A-DESIGN.md; was today's
        # line in both modes): C57's line in county mode, either line in SYNTHETIC mode
        # (s3support.fallback_lines; a question in briefs/QUESTIONS.md).
        # Changed by briefs/S3-R23-A-tests.md (C61 point 9): C61's line in county mode.
        # Changed by briefs/S3-R28-A-tests.md (C64 point 1): C64's line in county mode (the text
        # fails NUMBER); it was county_fallback_line(1).
        lines = (C64_TALK_LINE,) if mode == "county" else fallback_lines(county=False)
        if (reply.status, reply.reply_style) != ("TALKED", "fallback") or \
                reply.text not in lines:
            wrong.append(f"{text!r}: sent {reply.reply_style} {reply.text!r}")
        if figure in reply.text.lower() or re.search(r"\d", reply.text):
            wrong.append(f"{text!r}: {figure!r} or a digit was sent")
    text = f"I counted {{r1.count}}. Ask for{ws}7 more."
    assert "NUMBER" in talk_faults(text.split(". ", 1)[1], labels_for(mode)), text
    before = Step(count(2025, "18_25")) if mode == "synthetic" else \
        Step(county_count(A_ID, year(2025)))
    reply, problems = first_try(env, Q if mode == "synthetic" else Q_COUNT, "finding", text,
                                before, thread_key=thread(9))
    if problems is None or "NUMBER" not in problems:
        wrong.append(f"{text!r}: the first try gave {problems}, want NUMBER among them")
    if (reply.status, reply.reply_style) != ("ANSWERED", "fallback"):
        wrong.append(f"{text!r}: sent {reply.status} {reply.reply_style} {reply.text!r}")
    assert not wrong, "\n".join(wrong)
