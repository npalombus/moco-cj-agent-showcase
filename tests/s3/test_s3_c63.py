"""C63 of docs/S3A-DESIGN.md (D-080): an about answer that is only facts is written by the program.
Brief: briefs/S3-R26-A-tests.md. Tests only; red until the planning chat builds C63, except those
that pin what stays (named "Passes today" in their docstrings and in kit-log/raw/S3-R26-A-notes.txt).

All data is SYNTHETIC: the tests/s3 fixtures, with replies.ABOUT_AGENT pointed at a fixture copy
(C61 correction 1). No real figure is quoted. Every turn goes through agent.handle_question with the
model stand-in, talk off and on; the model calls are counted.

Readings (also in the notes):
- R26-1 (point 2) "the facts it named, each once, at most the first four, in its order, each as its
  own sentence ending with a full stop ... (the words of replies.facts_rendering)": `Here is what I
  know.`, then each fact as describe_data gave it (its line ends in its own full stop; a line
  without one gets one), joined by one space; then a line break and the notices as C57 point 5 has
  them (in full on the thread's first reply that carries them, C57's one line after). "Each once"
  comes before "the first four": a slot named again takes no second place.
- R26-2 (point 2) "the draft on record is the model's text": the stored memory record's
  `reply_text` is the finish text as the turn read it (talk on: as T10 tidies it; talk off: as
  written), not the rendering; turn.json's `finish_text` is the model's text as written (as today).
- R26-3 (point 2) "no failure is recorded, no REWRITE is given": the reply's and turn.json's
  `draft_failures` are [] (talk on: `first_failures` and `failures` too) and turn.json's
  `check_details` holds no failure; the model is called once after describe_data (two calls).
- R26-4 (point 1c) "every `Here is what I know` (capitals not counting)": the phrase, its words
  with one space between, in any letter case; what stands around it is left as it is.
- R26-5 (open, briefs/QUESTIONS.md S3-R26-A question 1) "`{f1}. {f2}.` gives what it gives today":
  that text is plain by point 1, so point 2 sends `Here is what I know.` and the two facts, which
  is today's reply with the opening put in front ("the opening left out is put in"); read as
  "today's reply exactly" it would not have the opening. Both are accepted in that one test; the
  changed old tests and the other tests here pin point 2's words.
- R26-6 (point 1) "a finish text that reaches county_about": also a step's plain text with no
  tool call after describe_data (A4 and T13 read it as a finish of kind about_data).
"""
import pytest

from p1support import THREAD_1, THREAD_2, Env, Step, describe, finish, mod, thread_block
from s3support import (A_ID, Q_ABOUT, Q_COUNT, CountyEnv, about_agent_fixture, age, count,
                       turn_json, year)
from test_s3_c41 import CAN_ASK
from test_s3_c57 import NOTICES_SHOWN, full_notices
from test_s3_c62 import DISTRICTS
from test_s3_round5 import NOT_ALLOWED_ROW

TALK = ["off", "on"]
OPENING = "Here is what I know."
PLAIN = "Here is what I know. {f1} {f2}"   # the first form seen live (thread P05 and others)
PROGRAM_NOTE = "PROGRAM NOTE (not from the person)."


@pytest.fixture(autouse=True)
def _about_agent(tmp_path, monkeypatch):
    about_agent_fixture(tmp_path, monkeypatch)


def env_for(tmp_path, monkeypatch, talk, **values):
    return CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk, **values)


def about(env, text, kind="about_data", question=Q_ABOUT, **kw):
    """describe_data, then a finish of `kind` with `text`; the same finish is scripted twice more,
    for the REWRITEs the program may ask for (the stand-in repeats its last step anyway)."""
    return env.ask(question, Step(describe()), *[Step(finish(kind, text))] * 3, **kw)


def facts_of(env):
    (answer,) = [a for a in env.answers() if "facts" in a]
    return [f["text"] for f in answer["facts"]]


def sentence(fact):
    return fact if fact.endswith(".") else fact + "."


def rendering(facts, picks):
    """R26-1: the opening, then each picked fact (numbered from 1) as its own sentence."""
    return " ".join([OPENING] + [sentence(facts[n - 1]) for n in picks])


def full_tail(env, names=("arrests_like",)):
    return "\n" + "\n".join(full_notices(env, names))


def records(env, thread_key=THREAD_1):
    return env.store.recent_turns(thread_key, 100)


def fixed_about(env):
    srcs = mod("sources").county_sources()
    copies = {sid: mod("sources").latest(sid, state_dir=env.state_dir) for sid in srcs}
    return mod("replies").county_about_text(srcs, copies)


def assert_sent_plain(env, reply, picks, tail=None):
    """Point 2: sent as the rendering, EXPLAINED, kind about_data, style agent, no failure, and the
    turn ended at its first finish (describe_data, then one finish: two model calls)."""
    facts = facts_of(env)
    assert (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", None, "about_data", "agent"), \
        (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style, reply.draft_failures,
         reply.text)
    assert list(reply.draft_failures) == [], reply.draft_failures
    assert reply.text == rendering(facts, picks) + (full_tail(env) if tail is None else tail), \
        reply.text
    assert len(env.model.calls) == 2, \
        f"{len(env.model.calls)} model calls: a plain facts text ends the turn at its first finish"


def assert_checked_as_today(env, reply, picks, talk, code):
    """Point 3 with C61 point 9b: the text is checked and fails (`code` among the failures); with
    talk on the first finish gets a REWRITE and the text comes again; the reply is 9b's rendering
    of the facts it named, style fallback."""
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fallback"), (reply.status, reply.reply_style, reply.text)
    assert code in reply.draft_failures, reply.draft_failures
    assert reply.text == rendering(facts_of(env), picks) + full_tail(env), reply.text
    if talk == "on":
        assert env.model.answer(1).get("error") == "REWRITE", env.model.answer(1)
    assert len(env.model.calls) == (3 if talk == "on" else 2), len(env.model.calls)


def no_failure_in(details):
    return not details or all(not v for v in details.values())


# ==== points 1 and 2: the three forms seen live ==================================================

FORMS = {
    "opening and slots with spaces": ("Here is what I know. {f1} {f2} {f3}", [1, 2, 3]),
    "the slots on lines of their own": ("Here is what I know.\n{f1}\n{f2}", [1, 2]),
    "one slot with no full stop": ("Here is what I know. {f1}", [1]),
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("form", list(FORMS))
def test_p2_the_three_forms_seen_live_are_sent_as_the_rendering(tmp_path, monkeypatch, form, talk):
    """C63's test: the three forms seen live are sent as the rendering, style agent, no failures,
    one finish and no REWRITE, talk off and on."""
    text, picks = FORMS[form]
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, text)
    assert_sent_plain(env, reply, picks)


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("text, picks", [
    ("Here is what I know. Here is what I know. {f1}", [1]),
    ("Here is what I know. {f1} Here is what I know. {f2}", [1, 2]),   # thread P05, reply 8
], ids=["twice at the start", "again between the facts"])
def test_p2_the_opening_twice_is_sent_once(tmp_path, monkeypatch, talk, text, picks):
    """C63's test: the opening twice is sent once."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, text)
    assert_sent_plain(env, reply, picks)
    assert reply.text.count(OPENING) == 1, reply.text


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("text, picks", [("{f1} {f2}", [1, 2]), ("{f3}", [3])],
                         ids=["two slots", "one slot"])
def test_p2_the_opening_left_out_is_put_in(tmp_path, monkeypatch, talk, text, picks):
    """C63's test: the opening left out is put in."""
    env = env_for(tmp_path, monkeypatch, talk)
    assert_sent_plain(env, about(env, text), picks)


@pytest.mark.parametrize("talk", TALK)
def test_p2_five_slots_give_the_first_four_in_its_order(tmp_path, monkeypatch, talk):
    """C63's test: five slots give the first four (in the text's order, not the slots' numbers)."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, "Here is what I know. {f5} {f3} {f1} {f2} {f4}")
    assert_sent_plain(env, reply, [5, 3, 1, 2])


@pytest.mark.parametrize("talk", TALK)
def test_p2_a_slot_twice_is_given_once(tmp_path, monkeypatch, talk):
    """C63's test: a slot twice is given once (where it first stands)."""
    env = env_for(tmp_path, monkeypatch, talk)
    assert_sent_plain(env, about(env, "Here is what I know. {f2} {f1} {f2}"), [2, 1])


@pytest.mark.parametrize("talk", TALK)
def test_p2_f1_f2_with_its_full_stops(tmp_path, monkeypatch, talk):
    """C63's test "`{f1}. {f2}.` gives what it gives today" (R26-5, answered by the planning chat,
    answer 1 to S3-R26-A: `{f1}. {f2}.` is a plain facts text, so the opening is put in front):
    the two facts, each once with one full stop, with the opening in front; style agent, no
    failure, one finish. Changed by briefs/S3-R27-A-tests.md: it accepted the reply without the
    opening too."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, "{f1}. {f2}.")
    facts = facts_of(env)
    assert all(f[:1].isupper() and f.endswith(".") for f in facts[:2]), "premise: as fill gives"
    today = f"{facts[0]} {facts[1]}"
    assert reply.text == f"{OPENING} {today}" + full_tail(env), reply.text
    assert reply.text.startswith(OPENING), reply.text
    assert (reply.status, reply.reply_kind, reply.reply_style, list(reply.draft_failures)) == \
        ("EXPLAINED", "about_data", "agent", []), (reply.reply_style, reply.draft_failures)
    assert ".." not in reply.text and len(env.model.calls) == 2


@pytest.mark.parametrize("talk", TALK)
def test_p1_c62s_finding_with_a_plain_facts_text_is_sent_the_same_way(tmp_path, monkeypatch, talk):
    """C63's test: C62 point 4's `finding` (describe_data, nothing counted) with a plain facts text
    is sent the same way."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, PLAIN, kind="finding", question=DISTRICTS)
    assert_sent_plain(env, reply, [1, 2])


# ==== point 2: the record, the notices ==========================================================

@pytest.mark.parametrize("talk", TALK)
def test_p2_the_record(tmp_path, monkeypatch, talk):
    """Point 2 with R26-2 and R26-3: the memory record (EXPLAINED, about_data, style agent, the
    model's text as `reply_text`, `sent` the rendering, notices full) and turn.json (the model's
    text as `finish_text`, no failure, the reply as sent)."""
    raw = "Here is what I know.\n{f1}\n{f2}"
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, raw)
    assert_sent_plain(env, reply, [1, 2])
    (record,) = records(env)
    assert (record["status"], record.get("reply_kind"), record.get("reply_style")) == \
        ("EXPLAINED", "about_data", "agent"), record
    assert record.get("reply_text") in (raw, "Here is what I know. {f1} {f2}"), record
    assert record.get("sent") == rendering(facts_of(env), [1, 2]), record.get("sent")
    assert record.get("notices") == "full", record
    saved = turn_json(reply, env.runs_dir)
    assert saved["finish_text"] == raw, saved["finish_text"]
    assert saved["draft_failures"] == [] and no_failure_in(saved.get("check_details")), saved
    assert (saved["status"], saved["reply_kind"], saved["reply_style"], saved["reply"]) == \
        ("EXPLAINED", "about_data", "agent", reply.text)
    if talk == "on":
        assert (saved["first_failures"], saved["failures"]) == ([], []), saved


@pytest.mark.parametrize("talk", TALK)
def test_p2_the_notices_in_full_once_a_thread_short_after(tmp_path, monkeypatch, talk):
    """C63's test: the notices in full once a thread, C57's one line after; another thread full
    again; the records say so."""
    env = env_for(tmp_path, monkeypatch, talk)
    assert_sent_plain(env, about(env, PLAIN), [1, 2])
    assert_sent_plain(env, about(env, "Here is what I know.\n{f3}\n{f1}"), [3, 1],
                      tail="\n" + NOTICES_SHOWN)
    assert_sent_plain(env, about(env, "{f2} {f4}", thread_key=THREAD_2), [2, 4])
    assert [r.get("notices") for r in records(env)] == ["full", "short"]
    assert [r.get("notices") for r in records(env, THREAD_2)] == ["full"]


# ==== point 3: every other text is as today ======================================================

NOT_PLAIN = {
    "a word of its own": ("Here is what I know. {f1} {f2} zqx.", [1, 2], "WORD"),
    "a slot that was not offered": ("Here is what I know. {f1} {f99}", [1], "SLOT"),
    "a digit outside the slots": ("Here is what I know. {f1} 2 {f2}", [1, 2], "CHARS"),
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(NOT_PLAIN))
def test_p3_a_text_that_is_not_plain_and_fails_is_checked_as_today(tmp_path, monkeypatch, talk,
                                                                   case):
    """C63's test: a text with a word of its own, with a slot that was not offered, or with a digit
    outside the slots is checked as today, and 9b's reply stands for one that fails and names
    facts (talk on: after a REWRITE). Passes today; must still pass."""
    text, picks, code = NOT_PLAIN[case]
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, text)
    assert len(facts_of(env)) < 99, "premise: {f99} is not offered"
    assert_checked_as_today(env, reply, picks, talk, code)


@pytest.mark.parametrize("talk", TALK)
def test_p3_a_text_with_a_word_of_its_own_that_passes_is_filled_as_today(tmp_path, monkeypatch,
                                                                         talk):
    """Point 3, a text with words of its own that passes the check: filled from its slots as today
    (the word kept, no opening added), style agent. Passes today; must still pass."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, "Here is what I know. Also {f1}.")
    facts = facts_of(env)
    assert (reply.status, reply.reply_kind, reply.reply_style, list(reply.draft_failures)) == \
        ("EXPLAINED", "about_data", "agent", []), (reply.reply_style, reply.draft_failures)
    assert reply.text == f"{OPENING} Also {facts[0]}" + full_tail(env), reply.text
    assert len(env.model.calls) == 2


@pytest.mark.parametrize("talk", TALK)
def test_p3_synthetic_mode_is_untouched(tmp_path, talk):
    """C63's test: SYNTHETIC mode is untouched: the same plain text fails today's check (GLUE) and
    the fixed about text is sent (talk on: after a REWRITE). Passes today; must still pass."""
    env = Env(tmp_path, MOCO_TALK=talk)
    reply = env.ask(Q_ABOUT, Step(describe()), *[Step(finish("about_data", PLAIN))] * 3)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fallback"), (reply.reply_style, reply.text)
    assert "GLUE" in reply.draft_failures, reply.draft_failures
    assert reply.text == mod("replies").fixed_text("ABOUT", env.registry), reply.text
    assert len(env.model.calls) == (3 if talk == "on" else 2)


@pytest.mark.parametrize("talk", TALK)
def test_p3_a_turn_with_no_describe_data_is_untouched(tmp_path, monkeypatch, talk):
    """C63's test: a turn that did not call describe_data gets the fixed about text as today, style
    fallback, no failure, one model call. Passes today; must still pass."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = env.ask(Q_ABOUT, *[Step(finish("about_data", PLAIN))] * 3)
    assert (reply.status, reply.reply_kind, reply.reply_style, list(reply.draft_failures)) == \
        ("EXPLAINED", "about_data", "fallback", []), (reply.reply_style, reply.text)
    assert reply.text == fixed_about(env) + full_tail(env), reply.text
    assert len(env.model.calls) == 1


@pytest.mark.parametrize("talk", TALK)
def test_p3_moco_reply_style_fixed_is_untouched(tmp_path, monkeypatch, talk):
    """C63's test: MOCO_REPLY_STYLE=fixed gets the fixed about text as today, style fixed. Passes
    today; must still pass."""
    env = env_for(tmp_path, monkeypatch, talk, MOCO_REPLY_STYLE="fixed")
    reply = about(env, PLAIN)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fixed"), (reply.reply_style, reply.text)
    assert reply.text == fixed_about(env) + full_tail(env), reply.text
    assert len(env.model.calls) == 2


# ==== replies.plain_facts =========================================================================

SYNTHETIC_FACTS = ["SYNTHETIC first fixture fact.", "SYNTHETIC second fixture fact.",
                   "SYNTHETIC third fixture fact.", "SYNTHETIC fourth fixture fact.",
                   "SYNTHETIC fifth fixture fact with no full stop"]
F = [f"SYNTHETIC {n} fixture fact." for n in ("first", "second", "third", "fourth")]


@pytest.mark.parametrize("text, expected", [
    ("Here is what I know. {f1} {f2}", f"{OPENING} {F[0]} {F[1]}"),
    ("{f3}\n{f1}", f"{OPENING} {F[2]} {F[0]}"),
    ("here is what i know {f2} {f2}. HERE IS WHAT I KNOW.", f"{OPENING} {F[1]}"),
    ("{f5}", f"{OPENING} SYNTHETIC fifth fixture fact with no full stop."),
    ("{f4} {f3} {f2} {f1} {f5}", f"{OPENING} {F[3]} {F[2]} {F[1]} {F[0]}"),
    ("Here is what I know. {f1} zqx", None),
    ("Here is what I know. {f6}", None),
    ("Here is what I know. {f1} {f6}", None),
    ("Here is what I know. {f1} 2", None),
    ("Here is what I know. {f1} {r1.count}", None),
    ("Here is what I know.", None),
    ("", None),
], ids=["opening and two", "lines, no opening", "capitals and repeats", "no full stop in the fact",
        "five", "a word", "not offered", "one not offered", "a digit", "a count slot",
        "no slot", "empty"])
def test_plain_facts(text, expected):
    """C63's function: replies.plain_facts(text, facts) is the rendering (R26-1, without the
    notices, which are the turn's) or None when the text is not plain."""
    assert mod("replies").plain_facts(text, SYNTHETIC_FACTS) == expected


# ==== own tests: what C63's words decide and its examples do not name =============================

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("earlier", [False, True], ids=["no count in the thread",
                                                        "a count earlier in the thread"])
def test_own_1_an_offered_fact_and_a_count_slot_is_checked_as_today(tmp_path, monkeypatch, talk,
                                                                     earlier):
    """Own 1 (point 1b and point 3): `{r1.count}` is not a slot describe_data offered, even when an
    earlier turn of the thread counted r1, so a text naming {f1} and {r1.count} is not plain: it is
    checked (SLOT) and 9b's reply of {f1} stands. Passes today; must still pass."""
    env = env_for(tmp_path, monkeypatch, talk)
    if earlier:
        first = env.ask(Q_COUNT, Step(count(A_ID, year(2025))),
                        Step(finish("finding", "I counted {r1.count}.")))
        assert first.status == "ANSWERED", first.text
    reply = about(env, "Here is what I know. {f1}. {r1.count}.")
    assert_checked_as_today(env, reply, [1], talk, "SLOT")


@pytest.mark.parametrize("talk", TALK)
def test_own_2_a_plain_text_with_no_tool_call_is_sent_the_same_way(tmp_path, monkeypatch, talk):
    """Own 2 (R26-6): after describe_data, a step's plain text with no tool call is read as a finish
    of kind about_data; a plain facts text is sent at once, with no PROGRAM NOTE."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = env.ask(Q_ABOUT, Step(describe()), *[Step(text=PLAIN)] * 3)
    assert_sent_plain(env, reply, [1, 2])
    notes = [m for c in env.model.calls for m in c["messages"] if m.get("role") == "user"
             and str(m.get("content")).startswith(PROGRAM_NOTE)]
    assert notes == [], notes


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("text, picks", [
    ("HERE IS WHAT I KNOW: {f1}, {f2}; {f3}!", [1, 2, 3]),
    ("here is what i know - {f2} - {f1}", [2, 1]),
    ("({f1}) ({f2})...", [1, 2]),
], ids=["capitals, colon, comma, semicolon", "small letters and dashes", "brackets and dots"])
def test_own_3_capitals_and_marks_between_the_slots_do_not_count(tmp_path, monkeypatch, talk,
                                                                text, picks):
    """Own 3 (point 1c and R26-4): the opening in any letter case, and commas, colons, semicolons,
    dashes, brackets and dots between the slots, leave the text plain; the opening is sent once,
    as written in point 2."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, text)
    assert_sent_plain(env, reply, picks)
    assert reply.text.lower().count("here is what i know") == 1, reply.text


@pytest.mark.parametrize("talk", TALK)
def test_own_4_a_slot_named_again_takes_no_place_of_the_four(tmp_path, monkeypatch, talk):
    """Own 4 (point 2, R26-1): "each once, at most the first four": {f1} three times, then {f2} to
    {f5}, gives f1 to f4."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, "{f1} {f1} {f2} {f1} {f3} {f4} {f5}")
    assert_sent_plain(env, reply, [1, 2, 3, 4])


DOORS = ["only the opening", "a count refused first", "a count made first"]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("door", DOORS)
def test_own_5_texts_that_never_reach_c63_are_as_today(tmp_path, monkeypatch, talk, door):
    """Own 5 (points 1 and 3): the opening with no slot is not plain (1a): checked, SLOT, the fixed
    about text; and a plain text after a count was refused, or after a count was made, never
    reaches county_about: the refusal's row, or the finding checked against the count's slots.
    Passes today; must still pass."""
    env = env_for(tmp_path, monkeypatch, talk)
    if door == "only the opening":
        reply = about(env, "Here is what I know.")
        assert (reply.status, reply.reply_kind, reply.reply_style) == \
            ("EXPLAINED", "about_data", "fallback"), (reply.reply_style, reply.text)
        assert "SLOT" in reply.draft_failures, reply.draft_failures
        assert reply.text == fixed_about(env) + full_tail(env), reply.text
        assert len(env.model.calls) == (3 if talk == "on" else 2)
        return
    made = count(A_ID, year(2025), [age(16, 16)]) if door == "a count refused first" \
        else count(A_ID, year(2025))
    reply = env.ask("how many 16 year olds were arrested in 2025?", Step(describe()), Step(made),
                    *[Step(finish("about_data", PLAIN))] * 3)
    if door == "a count refused first":
        assert env.model.answer(1).get("error") == "NOT_ALLOWED", env.model.answer(1)
        assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
        assert reply.text == f"{NOT_ALLOWED_ROW} {CAN_ASK[1]}", reply.text
    else:
        assert (reply.status, reply.reply_kind, reply.reply_style) == \
            ("ANSWERED", "finding", "fallback"), (reply.status, reply.reply_style, reply.text)
        assert "SLOT" in reply.draft_failures, reply.draft_failures
        assert OPENING not in reply.text, reply.text


@pytest.mark.parametrize("talk", TALK)
def test_own_6_the_next_turn_sees_what_was_sent(tmp_path, monkeypatch, talk):
    """Own 6 (point 2 "the memory's sent is what was sent", with C61 point 5): the next turn's
    THREAD SO FAR shows `You said: "<the rendering>"`, not the model's text (thread P05, reply 8's
    form)."""
    env = env_for(tmp_path, monkeypatch, talk)
    first = about(env, "Here is what I know. {f1} Here is what I know. {f2}")
    sent = rendering(facts_of(env), [1, 2])
    assert first.text.startswith(sent + "\n"), first.text
    about(env, "Here is what I know. {f3}")
    block = thread_block(env.model.calls[0]["messages"])
    assert block is not None and f'You said: "{sent}"' in block, block
    assert records(env)[0].get("sent") == sent


# ==== round 27 (briefs/S3-R27-A-tests.md): C63's addition, point 4, and its "Tests (round 27)" ====
# The whole word `and` (capitals not counting) between slots does not count either (point 1c); any
# other word keeps the text out of C63. Answer 1 to S3-R26-A is pinned in
# test_p2_f1_f2_with_its_full_stops above (the opening in front of `{f1}. {f2}.`).

AND_PLAIN = ["{f1} and {f2}.", "{f1}, and {f2}", "{f1} AND {f2}"]
AND_NOT_PLAIN = ["{f1} and also {f2}", "{f1} band {f2}"]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("text", AND_PLAIN)
def test_r27_and_between_the_slots_is_sent_as_the_rendering(tmp_path, monkeypatch, talk, text):
    """C63's test (round 27): `{f1} and {f2}.`, `{f1}, and {f2}` and `{f1} AND {f2}` are sent as the
    rendering (the opening, then the two facts as two sentences, then the notices), style agent, no
    failure, one finish, talk off and on; `and` is not sent. Fails on the wrong build "`and`
    counted as a word of its own" (kit-log/raw/S3-R27-A-breaks.txt)."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, text)
    assert_sent_plain(env, reply, [1, 2])
    facts = facts_of(env)
    assert f"{sentence(facts[0])} {sentence(facts[1])}\n" in reply.text, reply.text
    assert not any(f"{sentence(facts[0])} {w}" in reply.text for w in ("and", "AND")), reply.text


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("text", AND_NOT_PLAIN)
def test_r27_another_word_beside_and_is_checked_as_today(tmp_path, monkeypatch, talk, text):
    """C63's test (round 27): `{f1} and also {f2}` (a word of its own after `and`) and `{f1} band
    {f2}` (`and` only inside a longer word) are not plain facts texts: they are checked as today.
    Both fail it (GLUE), so with talk on the first finish gets a REWRITE, and C61 point 9b's reply
    of the two facts is sent, style fallback. Passes today; must still pass."""
    env = env_for(tmp_path, monkeypatch, talk)
    reply = about(env, text)
    assert mod("replies").plain_facts(text, facts_of(env)) is None
    assert_checked_as_today(env, reply, [1, 2], talk, "GLUE")
