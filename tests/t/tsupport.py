"""Helpers for the Part T tests. The contract is docs/T-DESIGN.md (T0 to T9); it adds to the
agent of docs/P1A-DESIGN.md with docs/P1A-R2-DESIGN.md and docs/S3A-DESIGN.md, which still
hold. Brief: briefs/T-A-tests.md.

What is here, and the readings it takes (each is also in kit-log/raw/T-A-notes.txt):

- The stand-ins are tests/p1's and tests/s3's, imported: the FakeModel, the FakeClock, the
  FakeSlack, p1support.Env (SYNTHETIC mode) and s3support.CountyEnv (county mode, with the
  SYNTHETIC fixture sources and copies made through the fake transport). Turns go through
  agent.handle_question exactly as in stage 2 and stage 3; nothing new is called.
- READING (the contract names no function for the talk check or for T2's check): every
  check is seen through a turn. A text that passes is sent as it is (or filled); a text
  that fails gets Python's REWRITE answer (T3), whose `problems` are the codes. So
  `first_try` runs a turn whose model calls finish once with the text and, if it is asked
  to rewrite, once more with the same text, and hands back the codes of the first try.
- `talk_env` and `county_talk_env`: the settings with MOCO_TALK=on (T0).
- `talk_rules()` reads config/talk_rules.json. It is used to build texts and to check a
  test's OWN text against the lists (talk_faults, judge_hits, mixed_faults: premises, as
  p1support.unlisted_words is for R1). No expected result is computed from it: every
  expected code, status and text is written out by hand in the tests. The fallback line
  and the rewrite hints are written out by hand below and checked against the file in
  test_t_rewrite.py.
- Sentences are counted as R1 counts them (p1support.sentences: a sentence ends at ., ! or
  ? followed by white space or the end of the text); the contract gives no other rule.

Round 2 (T10 to T15, brief briefs/T2-A-tests.md): the build makes config/talk_rules.json
version 2. Its new values are written out by hand below (TALK_MARKS, MOST_TALK_SENTENCES,
MOST_CHARS_TALK), never read from the file; `round2_rules()` checks the file says them.
The premises on a test's own talk texts (talk_faults, mixed_faults) read the text as T10
tidies it (`tidied`, the rule as written, for premises only) with those values.
"""
import json
import re
import unicodedata
from pathlib import Path

from p1support import (CHANNEL, R1_CODES, REPO, TEAM, Env, Step, finish, odd_chars,
                       registry_source, reply_rules, sentences, unlisted_words)
from s3support import CountyEnv, source_json

CONFIG = REPO / "config"
TALK_RULES_JSON = CONFIG / "talk_rules.json"
AGENT_PROMPT_TALK = CONFIG / "agent_prompt_talk.md"        # T0, SYNTHETIC mode
AGENT_PROMPT_S3_TALK = CONFIG / "agent_prompt_s3_talk.md"  # T0, county mode

TALK_CODES = frozenset({"NUMBER", "LABEL", "CLAIM", "CHARS", "SHAPE"})            # T1
FINDING_CODES = R1_CODES | {"NUMBER", "LABEL", "CLAIM", "JUDGE", "ORDER"}         # T2
BACKGROUND_CODES = frozenset({"SLOT", "NUMBER", "ADVICE", "CERTAIN", "HEDGE", "SHAPE",
                              "REASON"})                                         # A7 and T6

# Written out by hand from config/talk_rules.json (test_t_rewrite.py checks the file still
# says this).
FALLBACK_LINE = ("I'd rather not say something I can't back up. Ask me for a count and I'll "
                 "show you the numbers.")
HINTS = {
    "WORD": "In a sentence that holds a slot use only plain joining words. Put anything else "
            "in its own sentence without a slot.",
    "GLUE": "Put each slot in its own sentence, or join two slots with and, exactly as given.",
    "SLOT": "Use only the slots you were given, each once, written exactly as given.",
    "CHARS": "Use only letters and plain punctuation.",
    # Changed by briefs/S3-R28-A-tests.md (C64 point 1 of docs/S3A-DESIGN.md): the hint gains one
    # sentence at its end (one space before it; s3support.C64_HINT_SENTENCE). It was the first
    # two sentences alone.
    "NUMBER": "Write no number, month or year yourself. A figure may only come from a slot. In "
              'talk, point at a figure with the words "the figure I gave" and write no number.',
    "LABEL": "Do not name a group or a place in your own words.",
    "CLAIM": "Do not explain, compare or judge the figures in your own words.",
    "JUDGE": "Do not judge the figures in your own words. Leave that sentence out or keep it "
             "neutral.",
    "ORDER": "Keep a count slot and its months or groups slot next to each other.",
    "SHAPE": "Shorter, on one line: fewer sentences.",
    "REASON": "Say why the possibility is plausible (your reasoning), and what records would "
              "be needed to check it.",
}

# Talk texts that break no rule of T1 (each is premise-checked where it is used).
HELLO_TEXT = "Hello! Good to see you. Ask me for a count whenever you like."
THANKS_TEXT = "You're welcome! Want me to look at another year next?"

# Round 2, written out by hand from briefs/T2-A-tests.md (config/talk_rules.json version 2).
MOST_TALK_SENTENCES = 6        # T12 (was 4)
MOST_CHARS_TALK = 700          # T12 (was 500)
MOST_TALK_SENTENCES_IN_FINDING = 2   # T12: unchanged
MOST_CHARS_FINDING = 700             # T12: unchanged
NEW_MARKS = ('"', "“", "”", "–", "—", "…")       # T11
TALK_MARKS = (".", ",", "!", "?", "'", "’", "-", ":", ";", "(", ")") + NEW_MARKS


def talk_rules():
    return json.loads(TALK_RULES_JSON.read_text(encoding="utf-8"))


def round2_rules():
    """The premise of the round 2 tests: config/talk_rules.json is version 2 with the values
    written out above, and the finding limits and the lists it had are still there."""
    rules = talk_rules()
    assert rules["version"] == 2, f"config/talk_rules.json is version {rules['version']}"
    assert rules["most_talk_sentences_in_talk"] == MOST_TALK_SENTENCES
    assert rules["most_chars_talk"] == MOST_CHARS_TALK
    assert rules["most_talk_sentences_in_finding"] == MOST_TALK_SENTENCES_IN_FINDING
    assert rules["most_chars_finding"] == MOST_CHARS_FINDING
    assert sorted(rules["allowed_marks"]) == sorted(TALK_MARKS), rules["allowed_marks"]
    return rules


def tidied(text):
    """T10 as written, for the premises on a test's own texts only (replies.tidy itself is
    tested with every expected text written out by hand): 1. U+2010 and U+2011 become `-`;
    U+00A0, U+2007, U+2009 and U+202F a space. 2. `*`, the backtick, U+FE0F, U+200D, every
    character of category So and U+1F3FB to U+1F3FF are removed. 3. Every run of white
    space becomes one space; the ends are trimmed."""
    for ch in "‐‑":
        text = text.replace(ch, "-")
    for ch in "    ":
        text = text.replace(ch, " ")
    text = "".join(ch for ch in text if ch not in "*`️‍"
                   and unicodedata.category(ch) != "So" and not 0x1F3FB <= ord(ch) <= 0x1F3FF)
    return re.sub(r"\s+", " ", text).strip()


def thread(n):
    """A thread key of its own for case n, so the cases of one test do not share a thread."""
    return f"{TEAM}:{CHANNEL}:1762791{n:03d}.000100"


# ---- the settings (T0) ------------------------------------------------------------------------

def talk_env(tmp_path, **settings_values):
    """p1support.Env (SYNTHETIC mode) with MOCO_TALK=on."""
    return Env(tmp_path, MOCO_TALK="on", **settings_values)


def county_talk_env(tmp_path, monkeypatch, **kw):
    """s3support.CountyEnv (county mode, the fixture sources) with MOCO_TALK=on."""
    return CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", **kw)


# ---- the lists, for a test's own texts (premises) ---------------------------------------------

def _entry_re(entry):
    stem = entry[:-1] if entry.endswith("*") else entry
    body = r"\s+".join(re.escape(word) for word in stem.split())
    return body + (r"[A-Za-z]*" if entry.endswith("*") else "")


def listed_in(entries, text):
    """The entries a text holds: whole words or phrases, any letter case; an entry ending in
    * matches any word that starts with it (the files' own note)."""
    return [e for e in entries
            if re.search(rf"(?<![A-Za-z0-9]){_entry_re(e)}(?![A-Za-z0-9])", text, re.IGNORECASE)]


def synthetic_labels():
    """T1 LABEL in SYNTHETIC mode: the registry's age wordings."""
    return list(registry_source()["age_groups"].values())


def county_labels(*names):
    """T1 LABEL in county mode: every label of every category or flag field of the fixture
    sources `names`, read from their files."""
    out = []
    for name in names:
        for f in source_json(name)["fields"]:
            if f["kind"] == "category":
                out += list(f["values"].values())
            elif f["kind"] == "flag":
                out += [f["yes"], f["no"]]
    return list(dict.fromkeys(out))


def talk_faults(text, labels=()):
    """The codes of T1's talk check on the plain reading of each rule, for a test's own
    text, as tidied (T10) and with round 2's marks and limits (T11, T12; written out by hand
    above). A digit and "%" are not letters, so they give CHARS here as well as NUMBER (the
    tests accept either reading for them: NUMBER among the codes)."""
    rules, words = talk_rules(), reply_rules()
    text = tidied(text)
    marks = set(TALK_MARKS)
    codes = set()
    if re.search(r"[0-9%]", text) or listed_in(words["number_words"] + words["month_names"],
                                               text):
        codes.add("NUMBER")
    if listed_in(labels, text):
        codes.add("LABEL")
    if listed_in(rules["claim_phrases"], text):
        codes.add("CLAIM")
    if any(not (ch.isascii() and ch.isalpha()) and ch != " " and ch not in marks
           for ch in text) or any(m.lower() in text.lower() for m in words["markup"]):
        codes.add("CHARS")
    # T10: a line break cannot be left after tidying, so it no longer gives SHAPE.
    if not text or len(sentences(text)) > MOST_TALK_SENTENCES or len(text) > MOST_CHARS_TALK:
        codes.add("SHAPE")
    return codes


def judge_hits(text):
    return listed_in(talk_rules()["judgement_words"], text)


_SLOT = re.compile(r"\{[^{}]*\}")


def split_sentences(text):
    """(fact sentences, talk sentences): a fact sentence holds a {...} (T2)."""
    parts = sentences(text)
    return [s for s in parts if _SLOT.search(s)], [s for s in parts if not _SLOT.search(s)]


def mixed_faults(text, labels=()):
    """T2 on the plain reading, for a test's own text, the content codes only: in a fact
    sentence R1's WORD and CHARS (p1support's word list and marks); in a talk sentence the
    talk check's NUMBER, LABEL, CLAIM and CHARS, and JUDGE. (SLOT, GLUE, ORDER and SHAPE are
    stated by hand in each case.) The text is read as tidied (T10)."""
    facts, talks = split_sentences(tidied(text))
    codes = set()
    for s in facts:
        if unlisted_words(s):
            codes.add("WORD")
        if odd_chars(s):
            codes.add("CHARS")
    for s in talks:
        codes |= talk_faults(s, labels) - {"SHAPE"}
        if judge_hits(s):
            codes.add("JUDGE")
    return codes


def premise_talk(text, want, labels=()):
    """A talk text holds what its case says: no fault when want is None, exactly the code of
    a str, the codes of a set among others."""
    got = talk_faults(text, labels)
    if want is None:
        assert got == set(), (text, got)
    elif isinstance(want, str):
        assert got == {want}, (text, got)
    else:
        assert set(want) <= got, (text, got)


def padded(before, after, length, measure=len):
    """`before` + "S" + "o" * n + " glad to help." + `after`, with n chosen so that
    measure(text) is exactly `length`. The padding is one talk sentence of letters only."""
    def text(n):
        return f"{before}S{'o' * n} glad to help.{after}"
    n = length - measure(text(0))
    assert n >= 1, (length, measure(text(0)))
    out = text(n)
    assert measure(out) == length, (measure(out), length)
    return out


# ---- one turn, read through REWRITE (T3) -------------------------------------------------------

def first_try(env, question, kind, text, *before, **ask_kw):
    """One turn: the steps `before`, then finish(kind, text), and if Python asks for a
    rewrite, finish(kind, text) once more. Returns (reply, problems): problems is None when
    the turn ended at the first finish, else the `problems` of Python's REWRITE answer to
    it (which must be a REWRITE)."""
    n = len(before)
    reply = env.ask(question, *before, Step(finish(kind, text)), Step(finish(kind, text)),
                    **ask_kw)
    if len(env.model.calls) == n + 1:
        return reply, None
    answer = env.model.answer(n)
    assert isinstance(answer, dict) and answer.get("error") == "REWRITE", \
        f"the first finish was not answered with REWRITE: {answer!r}"
    return reply, answer["problems"]


def check_cases(run, cases, allowed):
    """cases: (text, want). want None: the first try passes (the turn ends there with style
    agent). A str: the problems are exactly that one code (as a set). A set: each of its
    codes is among the problems. Every problem must be one of `allowed`. Every case is
    tried; all wrong ones are listed."""
    wrong = []
    for i, (text, want) in enumerate(cases):
        reply, problems = run(i, text)
        if problems is None:
            if reply.reply_style != "agent":
                wrong.append(f"{text!r}: the turn ended at the first finish without a REWRITE "
                             f"({reply.status}, style {reply.reply_style})")
            elif want is not None:
                wrong.append(f"{text!r} should fail with {want}, but it passed")
            continue
        if not isinstance(problems, list) or not all(isinstance(c, str) for c in problems):
            wrong.append(f"{text!r}: problems is not a list of codes: {problems!r}")
        elif not set(problems) <= set(allowed):
            wrong.append(f"{text!r}: codes outside {sorted(allowed)}: "
                         f"{sorted(set(problems) - set(allowed))}")
        elif want is None:
            wrong.append(f"{text!r} should pass, got {problems}")
        elif isinstance(want, str) and set(problems) != {want}:
            wrong.append(f"{text!r} should fail with exactly {want}, got {problems}")
        elif isinstance(want, set) and not want <= set(problems):
            wrong.append(f"{text!r} should fail with {sorted(want)} among its codes, "
                         f"got {problems}")
    assert not wrong, "\n".join(wrong)


# ---- the reply of a talk turn (T1) ---------------------------------------------------------------

def assert_talked(reply, text, style="agent"):
    """T1: status TALKED, kind talk, the style; the text exactly as given (one plain
    message: no data tag, no second line, no kept note); no chart, no run, no result."""
    assert (reply.status, reply.reply_kind, reply.reply_style) == ("TALKED", "talk", style), \
        (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style, reply.text)
    assert reply.text == text, reply.text
    assert reply.chart_path is None and reply.chart_title is None
    assert list(reply.run_ids) == [] and list(reply.results) == []
    json.dumps(reply.to_dict())


def turn_json(reply, runs_dir):
    path = Path(runs_dir) / reply.turn_id / "turn.json"
    assert path.is_file(), f"no turn record at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def finish_kinds(tools):
    """The kinds the finish tool offers (its `kind` enum), from the tools given to the
    model."""
    (tool,) = [t for t in tools if t["function"]["name"] == "finish"]
    return list(tool["function"]["parameters"]["properties"]["kind"]["enum"])

