"""Brief P1A-A point 4: Python fills the gaps and asks the questions (docs/P1A-DESIGN.md A5),
with A7's kept note and line 2 on the ANSWERED replies that result. Revision 2
(docs/P1A-R2-DESIGN.md): R4, a restricted turn never counts, whatever memory holds; and the
passing finish is now filled with R1's whole phrases (p1support.one_count_line).

Covered: the tidying of count_arrests' arguments, value by value; the order stated >
pending > base, and `carried` set only for kept values; a fresh thread with no year
(NEEDS_INPUT, the saved values, and the next turn using them); the live run's sequence
("and for people under 18?" after a 2025 answer for ages 18 to 25, both when the model
passes a null year and when it calls ask_user("year")); "all ages" overriding memory (base
and pending); stage 1's record of a value sent to the strict check; a refused turn between
two follow-ups; base from the most recent of several answered turns; a turn with two years
(no base year) or two age groups (no base age group); a base of all ages, alone and with a
year; memory_minutes for base, pending, the thread block, ask_user("year") and "first
answer"; ask_user's fixed questions and what they save.

How the checks are made: the counts that ran are the ANSWERED manifests a turn added to the
runs folder (their `filters`); a passing finish whose slots are a count and its months
(p1support.ONE_COUNT_TEXT) is compared, filled with R1's phrases, with the truth file's
numbers and the registry's wording; a fixed rendering with p1support.fixed_line1_re. Replies are compared
whole: line 1, the kept note, then line 2 (first or later).

Accepted both ways (kit-log/raw/P1A-A-notes.txt):
- When count_arrests ends a fresh turn as NEEDS_INPUT, A5 does not say whether the saved
  age group is the model's stated value or router.read_age_group of the question: every
  such question here names the same group the model states, so both readings agree.
- The ASKED_KNOWN_YEAR rendering: reply_style `fallback` or `fixed`; reason_code None or
  that code (check_reply).
- `carried` on a NEEDS_INPUT reply is not checked (A5 names kept values only for a count).
- A DM turn whose earlier turns are all too old: no THREAD SO FAR message, or one that
  lists no earlier turn (A5 hides the turns; A11.2 does not say the header goes too).

Not checked, because the design does not settle them:
- memory_minutes None on a DM key (no limit, or MOCO_DM_MEMORY_MINUTES): the no-limit
  case is a channel thread instead, which A13 step 4 gives no time limit.
- Upper-case spellings of the age group's not-stated words ("NONE", "Unspecified"): A5
  gives "any case" for the all-ages words and for the year's words only.
- An extra key in count_arrests' arguments: A3 builds the execute_call arguments from the
  year and the age group only, so whether an extra key reaches the strict check is open.
- Words the model adds as extra keys of ask_user's arguments (whether that object is still
  a good call is not said). The model's own words are put in the step's text and in an
  unlisted `missing` value instead, and must not reach the reply.
"""
import re
from datetime import timedelta

import pytest

from p1support import (DM_KEY, LEAVE_OUT, NOW, ONE_COUNT_TEXT, CHATTER, MARK,
                       RESTRICTED_CODES, THREAD_1, Env, Step, answered_manifests, ask_user,
                       assert_answered, assert_fixed, check_reply, count, decline, finish,
                       fixed_line1_re, kept_note, manifests, one_count_line, thread_block)
from support import REFUSED, SUPPORTED

Q_18_25 = SUPPORTED["S1"][0]           # 2025, ages 18 to 25
Q_UNDER_18 = SUPPORTED["S3"][0]        # 2025, people under 18
Q_ALL_2024 = SUPPORTED["S2"][0]        # 2024, all ages
Q_NO_YEAR = "How many arrests were there for people under 18?"  # loop case L11
FOLLOW_UNDER_18 = "and for people under 18?"                    # loop case L04, the live run
Q_COMPARE = "Compare 2024 and 2025 for people under 18."        # loop case L07
Q_26_40_NO_YEAR = "How many arrests were there for ages 26 to 40?"


# ---- local helpers -------------------------------------------------------------------

def answered_runs(env):
    """{run id: (year, age group or None)} of every ANSWERED count in the Env's runs folder."""
    return {m["run_id"]: (m["filters"]["year"], m["filters"]["age_group"])
            for m in answered_manifests(env.runs_dir)}


def ask(env, question, *steps, **kw):
    """One turn; returns the reply and the counts it ran (the ANSWERED runs it added)."""
    before = answered_runs(env)
    reply = env.ask(question, *steps, **kw)
    ran = [v for k, v in sorted(answered_runs(env).items()) if k not in before]
    return reply, ran


def one_count(year=LEAVE_OUT, age_group=LEAVE_OUT):
    """The model counts once with these arguments, then finishes with ONE_COUNT_TEXT, which
    passes the checks of A7."""
    return Step(count(year, age_group)), Step(finish("finding", ONE_COUNT_TEXT))


def filled(year, group):
    """R1's fill of ONE_COUNT_TEXT: each slot's whole phrase, from the truth file."""
    return one_count_line(year, group)


def check_count(reply, model, ran, year, group, *, kept_year=False, kept_age=False, first,
                fixed=False):
    """An ANSWERED reply for one count of (year, group): what ran, `carried`, and the whole
    text (line 1, the kept note A7 gives for what was kept, then line 2)."""
    check_reply(reply, model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert ran == [(year, group)], ran
    assert dict(reply.carried) == {"year": kept_year, "age_group": kept_age}, reply.carried
    line1 = fixed_line1_re([(year, group)]) if fixed else re.escape(filled(year, group))
    kept = kept_note(year if kept_year else None, group, age=kept_age)
    assert_answered(reply.text, line1, kept=kept, first=first)
    if not fixed:
        assert reply.reply_style == "agent", reply.reply_style
        assert list(reply.draft_failures) == [], reply.draft_failures


def check_asks(reply, model, ran, missing="year"):
    """NEEDS_INPUT / NEEDS_CLARIFICATION with A7's fixed question, and nothing counted."""
    check_reply(reply, model)
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert_fixed(reply.text, f"NEEDS_{missing}")
    assert ran == [], ran


def check_known_year(reply, model, ran, year, group, *, kept_age, first=False):
    """A5: ask_user("year") when memory holds a year is not asked: one count, the fixed
    rendering, failure code ASKED_KNOWN_YEAR, and nothing of the model's wording."""
    check_count(reply, model, ran, year, group, kept_year=True, kept_age=kept_age,
                first=first, fixed=True)
    assert "ASKED_KNOWN_YEAR" in reply.draft_failures, reply.draft_failures
    assert reply.reply_style in ("fallback", "fixed"), reply.reply_style  # notes: either


# ---- tidying, value by value (A5 "Tidying") ---------------------------------------------

@pytest.mark.parametrize("year", ["2025", 2025.0], ids=["text_2025", "float_2025.0"])
def test_a_four_digit_text_or_a_whole_float_year_becomes_that_year(year, tmp_path):
    """A5: a string of exactly four digits or a float with no fraction becomes that int."""
    env = Env(tmp_path)
    reply, ran = ask(env, Q_18_25, *one_count(year, "18_25"))
    check_count(reply, env.model, ran, 2025, "18_25", first=True)


YEAR_NOT_STATED = {"null": None, "empty": "", "null_text": "null", "NULL_text": "NULL",
                   "none_text": "none", "None_text": "None", "missing_key": LEAVE_OUT}


@pytest.mark.parametrize("year", YEAR_NOT_STATED.values(), ids=YEAR_NOT_STATED)
def test_a_year_not_stated_in_a_fresh_thread_asks_which_year(year, tmp_path):
    """A5: null, "", "null", "none" (any case) or a missing key mean not stated; with no
    pending and no base the turn ends as NEEDS_INPUT with missing = year."""
    env = Env(tmp_path)
    reply, ran = ask(env, Q_NO_YEAR, Step(count(year, "under_18")))
    check_asks(reply, env.model, ran)


@pytest.mark.parametrize("year", YEAR_NOT_STATED.values(), ids=YEAR_NOT_STATED)
def test_a_year_not_stated_after_a_2025_answer_keeps_2025(year, tmp_path):
    """A5: the year comes from base and is kept (carried, and the kept note names it)."""
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"))
    reply, ran = ask(env, FOLLOW_UNDER_18, *one_count(year, "under_18"))
    check_count(reply, env.model, ran, 2025, "under_18", kept_year=True, first=False)


AGE_NOT_STATED = {"null": None, "empty": "", "null_text": "null", "none_text": "none",
                  "unspecified": "unspecified", "missing_key": LEAVE_OUT}


@pytest.mark.parametrize("age_group", AGE_NOT_STATED.values(), ids=AGE_NOT_STATED)
def test_an_age_group_not_stated_after_an_under_18_answer_keeps_under_18(age_group, tmp_path):
    """A5: null, "", "null", "none", "unspecified" or a missing key mean not stated; the
    age group then comes from base and is kept."""
    env = Env(tmp_path)
    env.answered(Q_UNDER_18, (2025, "under_18"))
    reply, ran = ask(env, "and 2024?", *one_count(2024, age_group))
    check_count(reply, env.model, ran, 2024, "under_18", kept_age=True, first=False)


@pytest.mark.parametrize("age_group", AGE_NOT_STATED.values(), ids=AGE_NOT_STATED)
def test_an_age_group_not_stated_in_a_fresh_thread_is_all_ages(age_group, tmp_path):
    """A5: "Age group: stated, else pending, else base, else all ages" (nothing kept)."""
    env = Env(tmp_path)
    reply, ran = ask(env, Q_ALL_2024, *one_count(2024, age_group))
    check_count(reply, env.model, ran, 2024, None, first=True)


ALL_AGES = {"all": "all", "ALL": "ALL", "all_ages": "all_ages", "All_Ages": "All_Ages",
            "all_ages_space": "all ages", "ALL_AGES_space": "ALL AGES",
            "everyone": "everyone", "Everyone": "Everyone", "overall": "overall",
            "OVERALL": "OVERALL", "total": "total", "Total": "Total"}


@pytest.mark.parametrize("age_group", ALL_AGES.values(), ids=ALL_AGES)
def test_each_all_ages_word_means_all_ages_even_after_an_under_18_answer(age_group, tmp_path):
    """A5: "all", "all_ages", "all ages", "everyone", "overall", "total" (any case) mean all
    ages: stated, so memory's under_18 is not used and nothing is kept."""
    env = Env(tmp_path)
    env.answered(Q_UNDER_18, (2025, "under_18"))
    reply, ran = ask(env, "and 2024 for everyone?", *one_count(2024, age_group))
    check_count(reply, env.model, ran, 2024, None, first=False)


def test_an_all_ages_word_beats_pending(tmp_path):
    """A5 and brief point 4: an all-ages word is stated, so pending's under_18 is not used
    either; nothing is kept, and this is the thread's first answer."""
    env = Env(tmp_path)
    env.pending(Q_NO_YEAR, "under_18")
    reply, ran = ask(env, "2025 for everyone", *one_count(2025, "all"))
    check_count(reply, env.model, ran, 2025, None, first=True)


STRICT = {
    "year_twenty": ("twenty", "18_25"),
    "year_text_20250": ("20250", "18_25"),
    "year_True": (True, "18_25"),
    "year_text_2025.0": ("2025.0", "18_25"),
    "year_float_2025.5": (2025.5, "18_25"),
    "year_text_with_a_space": (" 2025", "18_25"),
    "age_unknown": (2025, "teenagers_" + MARK),
    "age_wording_not_code": (2025, "18-25"),
    "age_registry_wording": (2025, "people under 18"),
    "age_juveniles": (2025, "juveniles"),
    "age_all_with_spaces": (2025, " all "),
    "age_code_in_capitals": (2025, "UNDER_18"),
}


@pytest.mark.parametrize("year, age_group", STRICT.values(), ids=STRICT)
def test_any_other_value_goes_to_the_strict_check(year, age_group, tmp_path):
    """A5: anything else goes to stage 1's strict check unchanged, so the count answers
    INVALID_ARGUMENTS (A3) and nothing is counted. The model then finishes; with every count
    an error, A7 uses that error's row: ERROR / INVALID_ARGUMENTS."""
    env = Env(tmp_path)
    reply, ran = ask(env, Q_18_25, *one_count(year, age_group))
    check_reply(reply, env.model)
    assert env.model.answer(0)["error"] == "INVALID_ARGUMENTS", env.model.answer(0)
    assert ran == [], ran
    # A0 and A3: stage 1's record is saved, holding the value as received, unchanged (every
    # STRICT age value is truthy, so A3's `code or None` keeps it).
    (saved,) = [m for m in manifests(env.runs_dir) if m["reason_code"] == "INVALID_ARGUMENTS"]
    assert saved["arguments"] == {"year": year, "age_group": age_group}, saved["arguments"]
    assert (reply.status, reply.reason_code) == ("ERROR", "INVALID_ARGUMENTS"), reply.text
    assert_fixed(reply.text, "INVALID_ARGUMENTS")


# ---- the order: stated, then pending, then base (A5 "Filling a count") -----------------

AFTER_2025_18_25 = {
    # name: (question, count's year, count's age group, year, group, kept year, kept age)
    "both_stated_as_base": (Q_18_25, 2025, "18_25", 2025, "18_25", False, False),
    "both_stated_new": ("and 2024 for ages 26 to 40?", 2024, "26_40", 2024, "26_40", False,
                        False),
    "year_stated_age_kept": ("and 2024?", 2024, None, 2024, "18_25", False, True),
    "age_stated_year_kept": ("and for ages 26 to 40?", None, "26_40", 2025, "26_40", True,
                             False),
    "both_kept": ("And the same again?", None, None, 2025, "18_25", True, True),
}


@pytest.mark.parametrize("case", AFTER_2025_18_25.values(), ids=AFTER_2025_18_25)
def test_a_stated_value_beats_base_and_only_kept_values_are_carried(case, tmp_path):
    """A5: a stated value is used even when base holds another (or the same) one; a value
    from base is "kept": carried, and the kept note names the year, the age wording, or
    both (A7)."""
    question, year_arg, age_arg, year, group, kept_year, kept_age = case
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"))
    reply, ran = ask(env, question, *one_count(year_arg, age_arg))
    check_count(reply, env.model, ran, year, group, kept_year=kept_year, kept_age=kept_age,
                first=False)


def test_pending_beats_base_for_the_age_group(tmp_path):
    """A5: an answered compare of 2024 and 2025 for people under 18 gives base no year (two
    years) and the age group under_18. A count with no year for ages 26 to 40 then ends as
    NEEDS_INPUT and saves 26_40; the answer "2025" counts 2025 for ages 26 to 40, the age
    group from pending (kept), not base's under_18."""
    env = Env(tmp_path)
    env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True)
    reply, ran = ask(env, Q_26_40_NO_YEAR, Step(count(None, "26_40")))
    check_asks(reply, env.model, ran)
    reply, ran = ask(env, "2025", *one_count(2025, None))
    check_count(reply, env.model, ran, 2025, "26_40", kept_age=True, first=False)


def test_pending_is_gone_once_the_last_turn_is_not_needs_input(tmp_path):
    """A5: pending exists "only when the most recent earlier turn is NEEDS_INPUT". With a
    declined turn after the NEEDS_INPUT turn, "2025" takes the age group from base
    (under_18, from the compare), not the 26_40 that was saved."""
    env = Env(tmp_path)
    env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True)
    env.pending(Q_26_40_NO_YEAR, "26_40")
    question, code = REFUSED["U1"]
    declined = env.ask(question, Step(decline(code)))
    assert (declined.status, declined.reason_code) == ("UNSUPPORTED", code), declined.text
    reply, ran = ask(env, "2025", *one_count(2025, None))
    check_count(reply, env.model, ran, 2025, "under_18", kept_age=True, first=False)


def test_a_stated_age_group_beats_pending(tmp_path):
    """A5: stated before pending; nothing kept, and this is the thread's first answer."""
    env = Env(tmp_path)
    env.pending(Q_NO_YEAR, "under_18")
    reply, ran = ask(env, "2025, but for ages 26 to 40", *one_count(2025, "26_40"))
    check_count(reply, env.model, ran, 2025, "26_40", first=True)


# ---- a fresh thread with no year (A5, brief point 4) -----------------------------------

FRESH_ASKS = {"count_with_null_year": Step(count(None, "under_18")),
              "ask_user_year": Step(ask_user("year"), text=CHATTER)}


@pytest.mark.parametrize("first_step", FRESH_ASKS.values(), ids=FRESH_ASKS)
def test_a_fresh_thread_with_no_year_asks_then_the_next_turn_uses_the_saved_values(
        first_step, tmp_path):
    """A5: with no pending and no base, a count with no year, or ask_user("year"), ends as
    NEEDS_INPUT saving the age group (read_age_group of the question names people under 18,
    as the model does). The answer "2025" then counts 2025 for people under 18, the age
    group kept from pending, as the thread's first answer."""
    env = Env(tmp_path)
    reply, ran = ask(env, Q_NO_YEAR, first_step)
    check_asks(reply, env.model, ran)
    reply, ran = ask(env, "2025", *one_count(2025, None))
    check_count(reply, env.model, ran, 2025, "under_18", kept_age=True, first=True)


# ---- the live run's sequence (brief point 4) -------------------------------------------

def test_live_run_a_null_year_after_a_2025_answer_is_answered_for_2025(tmp_path):
    """After a 2025 answer for ages 18 to 25, "and for people under 18?" with a null year:
    the agent's filled finding for 2025 and people under 18, the kept note for 2025, and
    the later line 2."""
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"))
    reply, ran = ask(env, FOLLOW_UNDER_18, *one_count(None, "under_18"))
    check_count(reply, env.model, ran, 2025, "under_18", kept_year=True, first=False)


def test_live_run_ask_user_year_after_a_2025_answer_is_answered_for_2025(tmp_path):
    """A5: the same question, but the model calls ask_user("year"). Base holds 2025, so
    Python does not ask: it counts with the year not stated and the age group of
    read_age_group (people under 18), and answers with the fixed rendering
    (ASKED_KNOWN_YEAR). The model's words (the step's text) appear nowhere."""
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"))
    reply, ran = ask(env, FOLLOW_UNDER_18, Step(ask_user("year"), text=CHATTER))
    check_known_year(reply, env.model, ran, 2025, "under_18", kept_age=False)


KNOWN_YEAR = {
    # name: (question, the age group counted, kept from base)
    "no_age_wording_keeps_base": ("And the same again?", "18_25", True),
    "all_ages_in_the_question": ("and for all ages?", None, False),
}


@pytest.mark.parametrize("case", KNOWN_YEAR.values(), ids=KNOWN_YEAR)
def test_ask_user_year_with_a_known_year_takes_the_age_group_from_the_question(case, tmp_path):
    """A5: the count's age group is router.read_age_group(question), filled as a count's:
    None keeps base's ages 18 to 25; "all ages" counts all ages, kept from nowhere."""
    question, group, kept_age = case
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"))
    reply, ran = ask(env, question, Step(ask_user("year"), text=CHATTER))
    check_known_year(reply, env.model, ran, 2025, group, kept_age=kept_age)


# ---- R4: a restricted turn never counts ------------------------------------------------

RESTRICTED_QUESTIONS = {"REAL_DATA_NOT_AVAILABLE": REFUSED["U5"][0],  # stage 1's rule 2
                        "UNSUPPORTED_METRIC": REFUSED["U1"][0],       # rule 3
                        "UNSUPPORTED_FIELD": REFUSED["U3"][0]}        # rule 4


@pytest.mark.parametrize("memory", ["base_2025", "pending", "nothing"])
@pytest.mark.parametrize("code", RESTRICTED_CODES)
def test_a_restricted_turn_that_asks_for_the_year_never_counts(code, memory, tmp_path):
    """R4: when the guard restricted the turn and the model calls ask_user with `year`,
    Python does not count, whatever memory holds (a 2025 answer as base; a NEEDS_INPUT turn
    as pending; nothing): the turn ends UNSUPPORTED with the restricted code and its fixed
    row, no run is saved, and nothing the model wrote is in the reply."""
    assert set(RESTRICTED_QUESTIONS) == set(RESTRICTED_CODES)
    env = Env(tmp_path)
    if memory == "base_2025":
        env.answered(Q_18_25, (2025, "18_25"))
    elif memory == "pending":
        env.pending(Q_NO_YEAR, "under_18")
    saved = len(manifests(env.runs_dir))
    reply, ran = ask(env, RESTRICTED_QUESTIONS[code], Step(ask_user("year"), text=CHATTER))
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), \
        (reply.status, reply.reason_code, reply.text)
    assert_fixed(reply.text, code)
    assert ran == [] and list(reply.run_ids) == [] and len(reply.results) == 0
    assert len(manifests(env.runs_dir)) == saved, "a restricted turn saved a run"


# ---- a refused turn between two follow-ups (brief point 4) ------------------------------

REFUSALS = {"restricted_and_declined": ("U1", Step(decline("UNSUPPORTED_METRIC"))),
            "guard_rule_1": ("U6", Step())}


@pytest.mark.parametrize("refusal", REFUSALS.values(), ids=REFUSALS)
def test_a_refused_turn_between_two_follow_ups_does_not_break_the_chain(refusal, tmp_path):
    """A5: base is the most recent earlier turn that HAS count results, so a refusal in
    between (a restricted question the model declines, or a rule 1 question the guard
    refuses with no model call) leaves 2025 to be kept."""
    key, step = refusal
    question, code = REFUSED[key]
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"))
    refused = env.ask(question, step)
    assert (refused.status, refused.reason_code) == ("UNSUPPORTED", code), refused.text
    reply, ran = ask(env, FOLLOW_UNDER_18, *one_count(None, "under_18"))
    check_count(reply, env.model, ran, 2025, "under_18", kept_year=True, first=False)


# ---- what base holds after several counts (A5 "What memory offers") ---------------------

def test_base_comes_from_the_most_recent_turn_with_counts(tmp_path):
    """A5: base is the MOST RECENT earlier turn with counts, not an older one and not all of
    them together. After 2024 for all ages, then 2025 for ages 18 to 25, a count with neither
    value keeps 2025 and ages 18 to 25."""
    env = Env(tmp_path)
    env.answered(Q_ALL_2024, (2024, None))
    env.answered(Q_18_25, (2025, "18_25"))
    reply, ran = ask(env, "And the same again?", *one_count(None, None))
    check_count(reply, env.model, ran, 2025, "18_25", kept_year=True, kept_age=True,
                first=False)


TWO_YEARS_THEN = {"count_with_null_year": Step(count(None, "26_40")),
                  "ask_user_year": Step(ask_user("year"), text=CHATTER)}


@pytest.mark.parametrize("step", TWO_YEARS_THEN.values(), ids=TWO_YEARS_THEN)
def test_a_previous_turn_with_two_years_gives_no_base_year(step, tmp_path):
    """A5: base's year only "if those counts share exactly one year". After a compare of
    2024 and 2025, neither a count with no year nor ask_user("year") has a year: both end
    as NEEDS_INPUT with the year question."""
    env = Env(tmp_path)
    env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True)
    reply, ran = ask(env, "and for ages 26 to 40?", step)
    check_asks(reply, env.model, ran)


def test_a_previous_turn_with_two_age_groups_gives_no_base_age_group(tmp_path):
    """A5: base's age group only if the counts share exactly one. After counts for people
    under 18 and ages 18 to 25 in 2025, a count with neither value keeps 2025 and counts
    all ages, which is not kept."""
    env = Env(tmp_path)
    env.answered("Compare people under 18 and ages 18 to 25 in 2025.", (2025, "under_18"),
                 (2025, "18_25"), compared=True)
    reply, ran = ask(env, "and both together?", *one_count(None, None))
    check_count(reply, env.model, ran, 2025, None, kept_year=True, first=False)


def test_a_base_of_all_ages_is_kept_as_all_ages(tmp_path):
    """A5: base's age group is "a code, or all ages"; kept, it is carried and the kept note
    says "all ages" (A7: the age wording, or all ages)."""
    env = Env(tmp_path)
    env.answered(Q_ALL_2024, (2024, None))
    reply, ran = ask(env, "what about 2025?", *one_count(2025, None))
    check_count(reply, env.model, ran, 2025, None, kept_age=True, first=False)


def test_a_base_of_one_year_and_all_ages_is_kept_as_both(tmp_path):
    """A7: `<kept>` is `<year> and <age wording>`, here "2024 and all ages"."""
    env = Env(tmp_path)
    env.answered(Q_ALL_2024, (2024, None))
    reply, ran = ask(env, "And the same again?", *one_count(None, None))
    check_count(reply, env.model, ran, 2024, None, kept_year=True, kept_age=True, first=False)


# ---- memory_minutes (A5, for a direct-message conversation) -----------------------------

MEMORY = {
    # name: (minutes between the turns, memory_minutes, the earlier turn counts, thread key)
    "90_minutes_limit_60": (90, 60, False, DM_KEY),
    "30_minutes_limit_60": (30, 60, True, DM_KEY),
    # A13 step 4: a channel thread has no time limit on memory. (None on a DM key is not
    # used: whether a build then falls back to MOCO_DM_MEMORY_MINUTES is not said.)
    "90_minutes_no_limit": (90, None, True, THREAD_1),
}


@pytest.mark.parametrize("case", MEMORY.values(), ids=MEMORY)
def test_memory_minutes_for_base_and_the_thread_block(case, tmp_path):
    """A5: only turns newer than memory_minutes count for base and for the thread block
    (A11). Too old: no base year (NEEDS_INPUT) and the earlier turn is not shown to the
    model. Newer, or no limit: 2025 is kept, and the block is there."""
    gap, limit, remembered, key = case
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"), thread_key=key, now=NOW, memory_minutes=limit)
    reply, ran = ask(env, FOLLOW_UNDER_18, *one_count(None, "under_18"), thread_key=key,
                     now=NOW + timedelta(minutes=gap), memory_minutes=limit)
    block = thread_block(env.model.calls[0]["messages"])
    if remembered:
        check_count(reply, env.model, ran, 2025, "under_18", kept_year=True, first=False)
        assert block is not None, "the earlier turn is not shown to the model"
    else:
        check_asks(reply, env.model, ran)
        # Accepted both ways (A5 hides the turn; A11.2 does not say the header goes too): no
        # THREAD SO FAR message, or one that lists no earlier turn.
        assert block is None or ("User:" not in block and "counted" not in block), block


@pytest.mark.parametrize("case", MEMORY.values(), ids=MEMORY)
def test_memory_minutes_for_ask_user_year(case, tmp_path):
    """A5: ask_user("year") is not asked only when base holds a year, and base counts only
    turns newer than memory_minutes. Too old: NEEDS_INPUT with the year question. Newer, or
    no limit: one count for 2025 and people under 18, with the fixed rendering
    (ASKED_KNOWN_YEAR)."""
    gap, limit, remembered, key = case
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"), thread_key=key, now=NOW, memory_minutes=limit)
    reply, ran = ask(env, FOLLOW_UNDER_18, Step(ask_user("year"), text=CHATTER),
                     thread_key=key, now=NOW + timedelta(minutes=gap), memory_minutes=limit)
    if remembered:
        check_known_year(reply, env.model, ran, 2025, "under_18", kept_age=False)
    else:
        check_asks(reply, env.model, ran)


@pytest.mark.parametrize("case", MEMORY.values(), ids=MEMORY)
def test_memory_minutes_for_pending(case, tmp_path):
    """A5: an older NEEDS_INPUT turn gives no pending: "2025" counts all ages, nothing kept.
    Newer, or no limit: people under 18 is kept from pending. Either way it is the first
    answer."""
    gap, limit, remembered, key = case
    env = Env(tmp_path)
    env.pending(Q_NO_YEAR, "under_18", thread_key=key, now=NOW, memory_minutes=limit)
    reply, ran = ask(env, "2025", *one_count(2025, None), thread_key=key,
                     now=NOW + timedelta(minutes=gap), memory_minutes=limit)
    if remembered:
        check_count(reply, env.model, ran, 2025, "under_18", kept_age=True, first=True)
    else:
        check_count(reply, env.model, ran, 2025, None, first=True)


@pytest.mark.parametrize("case", MEMORY.values(), ids=MEMORY)
def test_memory_minutes_for_the_first_answer(case, tmp_path):
    """A5 and A7: an older ANSWERED turn does not count for "first answer", so the next
    answer gets the first line 2; a newer one, or no limit, gives the later line 2."""
    gap, limit, remembered, key = case
    env = Env(tmp_path)
    env.answered(Q_18_25, (2025, "18_25"), thread_key=key, now=NOW, memory_minutes=limit)
    reply, ran = ask(env, "and 2024 for people under 18?", *one_count(2024, "under_18"),
                     thread_key=key, now=NOW + timedelta(minutes=gap),
                     memory_minutes=limit)
    check_count(reply, env.model, ran, 2024, "under_18", first=not remembered)


# ---- ask_user for an age group or something else (A5 "ask_user") -----------------------

ASK_OTHER = {"age_group": ("age_group", "age_group"), "other": ("other", "other"),
             "unlisted_7": (7, "other"), "unlisted_text": ("month_" + MARK, "other")}


@pytest.mark.parametrize("case", ASK_OTHER.values(), ids=ASK_OTHER)
def test_ask_user_age_group_or_other_asks_and_saves_nothing_to_fill(case, tmp_path):
    """A5: ask_user("age_group") or ("other") (an unlisted value counts as other) is
    NEEDS_INPUT with A7's fixed question, Python's words only, and saves year and age group
    both null, even though the question names people under 18. The answer "2025" then
    counts all ages, nothing kept."""
    missing, asked = case
    env = Env(tmp_path)
    reply, ran = ask(env, Q_NO_YEAR, Step(ask_user(missing), text=CHATTER))
    check_asks(reply, env.model, ran, asked)
    reply, ran = ask(env, "2025", *one_count(2025, None))
    check_count(reply, env.model, ran, 2025, None, first=True)
