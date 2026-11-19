"""Brief point 8, first part: the turn record (docs/P1A-DESIGN.md A9, with answer A3 of
briefs/QUESTIONS.md), and revision 2's R6 (docs/P1A-R2-DESIGN.md): each step also holds
`text`, what the model wrote in that step exactly as given or null, and a failed check adds
`check_details`, the words and characters that failed. Neither is logged, stored in the
database or put in a reply. R2: Python's answers name slots, not field names.

Every turn in which a tool ran saves runs/<turn id>/turn.json. Each test runs a real
agent.handle_question with a FakeModel (p1support.Env) and reads turn.json from the Env's
runs folder in tmp_path. Numbers come from the truth file.

A9 names only one key, "data_class": "SYNTHETIC". Every other item A9 lists is looked for as
a value anywhere in the record (a value at the end of its structure, p1support.has_leaf).

Accepted both ways (the design allows either):
- A tool call's arguments and Python's answer to it may be kept as objects or as the JSON
  text that was sent: a string value that is JSON text is searched inside too
  (p1support.deep_leaves).
- The turn id's UTC time may be written in digits with any of T, Z, -, :, . and + (the hex
  in either case; p1support.TURN_ID, kit-log/raw/P1A-A-notes.txt).
- The prompt version may put up to 3 separator marks, and "sha256", between the prompt
  file's name and the 8 hex characters (p1support.prompt_version_pattern, as test_p1_context
  reads A11's "as now").
- A result's values may be kept as numbers or as numeric text, with or without a comma (A9
  gives no form). The tool calls' arguments must be the numbers the fake model sent.
- The status of a failing background text with MOCO_BACKGROUND on (A7 does not give it).

- R6 names the keys `text` and `check_details` but not where the steps are kept: the steps
  are any list in the record with one object per model call, each holding `text`, in the
  order of the calls (p1support.deep_leaves is not needed: R6's keys are real keys).
  `check_details` may be anywhere in the record, in any shape; its words in either letter
  case.

Cannot check here: "what was kept" (A9 gives neither its key nor its form, and true/false
values are everywhere in a record); a log line written by a logger that does not pass its
records on to the root logger (caplog sees only those).
"""
import json
import logging

import pytest

from collections.abc import Mapping

from p1support import (AGENT_PROMPT_MD, CHATTER, FAKE_MODEL_ID, MARK, ONE_COUNT_TEXT, TURN_ID,
                       TYPED, Env, Step, about_text, call, check_reply, compare,
                       compare_expect, compare_text, count, db_bytes, db_cells, decline,
                       deep_leaves, describe, finish, has_leaf, has_number, mod, months,
                       prompt_version_pattern, show_details, single_sentence_facts,
                       synthetic_fact, turn_record)
from support import NOT_SYNTHETIC_COPIES, REFUSED, SUPPORTED

Q_COUNT = SUPPORTED["S1"][0]  # 2025, ages 18 to 25; no guard rule matches it
Q_COMPARE = "Compare 2024 and 2025 for people under 18."
COMPARE_TEXT = compare_text("r3")
Q_BACKGROUND = "Why do arrest counts change over a year?"  # no guard rule matches it
Q_SHOW = "Can you show me the months behind that answer?"  # no guard rule matches it
TRAP = "zebra-quartz"  # a word only the failing texts below hold (CHATTER holds it too)
FAILING_TEXT = (f"I counted {TYPED} arrest records, {{r1.count}} in all, says {TRAP} "
                f"{MARK}.")  # CHARS (a typed digit) and WORD (R1)
# Passes R1's check for about_data: fact slots and listed words.
ABOUT_TEXT = about_text(synthetic_fact())


def has_value(record, n):
    """A result's value n is in the record as a number, or as numeric text with or without
    its comma (A9 does not give the form)."""
    return has_leaf(record, n) or has_leaf(record, str(n)) or has_leaf(record, f"{n:,}")


def compare_turn(env):
    """Two counts, a compare and a finish that passes the checks."""
    reply = env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True,
                         text=COMPARE_TEXT)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    return reply, turn_record(reply, env.runs_dir)


def log_text(caplog):
    return caplog.text + "\n".join(record.getMessage() for record in caplog.records)


def catch_every_log_line(caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="moco_agent")


def test_a_turn_that_ran_a_tool_saves_turn_json_under_its_turn_id(tmp_path):
    """A9: runs/<turn id>/turn.json; the id is T + the UTC time + - + 8 hex characters."""
    env = Env(tmp_path)
    reply = env.answered(Q_COUNT, (2025, "18_25"))
    assert isinstance(reply.turn_id, str) and TURN_ID.fullmatch(reply.turn_id), reply.turn_id
    record = turn_record(reply, env.runs_dir)
    assert record.get("data_class") == "SYNTHETIC", record.get("data_class")


def test_the_record_holds_the_question_the_model_id_and_the_prompt_version(tmp_path):
    """A9: the question; the model id and the prompt version (A11: the prompt file's name
    and the first 8 hex characters of its sha256, read from the file now)."""
    env = Env(tmp_path)
    reply = env.answered(Q_COUNT, (2025, "18_25"))
    record = turn_record(reply, env.runs_dir)
    assert has_leaf(record, Q_COUNT)
    assert has_leaf(record, FAKE_MODEL_ID)
    version = prompt_version_pattern(AGENT_PROMPT_MD)
    found = [leaf for leaf in deep_leaves(record)
             if isinstance(leaf, str) and version.fullmatch(leaf)]
    assert found, f"no prompt version matching {version.pattern} in the record"


def test_the_record_holds_every_tool_call_with_its_arguments(tmp_path):
    """A9: every step's tool calls with their arguments. The second turn sends a value only
    an argument can hold, to a tool that does not exist (so nothing tidies it)."""
    env = Env(tmp_path)
    _, record = compare_turn(env)
    for name in ("count_arrests", "compare", "finish"):
        assert has_leaf(record, name), name
    for value in (2024, 2025, "under_18", "r1", "r2", "total", "finding"):
        assert has_leaf(record, value), value
    reply = env.ask(Q_COUNT, Step(call("no_such_tool", {"note": "kestrel-argument"}),
                                  count(2025, "18_25")),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    assert has_leaf(turn_record(reply, env.runs_dir), "kestrel-argument")


# Each turn ends ANSWERED with one count, so the code is in the record only as Python's
# answer to the call (A3), never as the turn's status or reason code.
PYTHON_ANSWERS = {
    "BAD_CALL": [Step(call("no_such_tool", {}), count(2025, "18_25"))],
    "OUT_OF_COVERAGE": [Step(count(2019, "all"), count(2025, "18_25"))],
    "BAD_COMPARE": [Step(count(2025, "18_25"), compare("r1", "r1"))],
    "LIMIT": [Step(count(2025, "18_25"), *[describe()] * 12)],  # call 13 is past the limit
}


@pytest.mark.parametrize("code", PYTHON_ANSWERS)
def test_the_record_holds_what_python_answered(code, tmp_path):
    """A9: what Python answered each tool call, including its errors (A3)."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, *PYTHON_ANSWERS[code], Step(finish("finding", ONE_COUNT_TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert has_leaf(turn_record(reply, env.runs_dir), code), code


def test_the_record_holds_pythons_answer_to_a_count_and_a_compare(tmp_path):
    """A9: what Python answered; R2: those answers list the result's fact slots."""
    env = Env(tmp_path)
    _, record = compare_turn(env)
    for slot in ("{r1.count}", "{r1.months}", "{r2.count}", "{r2.months}", "{r3.compare}"):
        assert has_leaf(record, slot), slot


def test_the_record_holds_every_result_with_its_values_and_run_id(tmp_path):
    """A9: every result with its values and, for counts, its run id."""
    env = Env(tmp_path)
    reply, record = compare_turn(env)
    totals = [sum(months(year, "under_18")) for year in (2024, 2025)]
    for total in totals:
        assert has_value(record, total), "a count's total is not in the record"
    expect = compare_expect([(2024, "under_18", totals[0]), (2025, "under_18", totals[1])])
    assert has_value(record, expect["difference"]), "the compare's difference is not in it"
    for result_id in ("r1", "r2", "r3"):
        assert has_leaf(record, result_id), result_id
    assert len(reply.run_ids) == 2, reply.run_ids
    for run_id in reply.run_ids:
        assert has_leaf(record, run_id), run_id


def test_the_record_holds_the_finish_text_exactly_and_the_reply_sent(tmp_path):
    """A9: the text the model gave finish, exactly as given; the reply that was sent; the
    status."""
    env = Env(tmp_path)
    reply, record = compare_turn(env)
    assert has_leaf(record, COMPARE_TEXT)
    assert has_leaf(record, reply.text)
    assert has_leaf(record, "ANSWERED")


def test_the_record_holds_the_status_and_reason_code(tmp_path):
    """A9: the status and reason code, and the reply sent, for a turn the model declined."""
    env = Env(tmp_path)
    question = REFUSED["U3"][0]
    reply = env.ask(question, Step(decline("UNSUPPORTED_FIELD")))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD"), reply.text
    record = turn_record(reply, env.runs_dir)
    for value in ("UNSUPPORTED", "UNSUPPORTED_FIELD", "decline", question, reply.text):
        assert has_leaf(record, value), value
    assert record.get("data_class") == "SYNTHETIC"


# kind: (question, settings, steps, the failing text). CHATTER fails R1 (CHARS, WORD, no
# fact slot) for about_data, and A7's NUMBER and HEDGE for background.
FAILING = {
    "finding": (Q_COUNT, {}, [Step(count(2025, "18_25")), Step(finish("finding", FAILING_TEXT))],
                FAILING_TEXT),
    "about_data": (Q_COUNT, {}, [Step(describe()), Step(finish("about_data", CHATTER))],
                   CHATTER),
    "background": (Q_BACKGROUND, {"MOCO_BACKGROUND": "on"},
                   [Step(finish("background", CHATTER))], CHATTER),
}


@pytest.mark.parametrize("kind", FAILING)
def test_a_failing_finish_text_is_kept_in_turn_json_and_nowhere_else(kind, tmp_path, caplog):
    """A9 and answer A3: a text that failed the checks is in turn.json with the failure
    codes; never in the database, never in a log line. For each kind of finish (A7: a
    failing about_data or background text gives style fallback). The status of a failing
    background text is not checked (A7 does not give it)."""
    question, settings_values, steps, text = FAILING[kind]
    catch_every_log_line(caplog)
    env = Env(tmp_path, **settings_values)
    reply = env.ask(question, *steps)
    check_reply(reply, env.model)
    assert reply.reply_style == "fallback", (reply.reply_style, reply.status, reply.text)
    if kind == "finding":
        assert reply.status == "ANSWERED", (reply.status, reply.reason_code)
        assert "CHARS" in reply.draft_failures, reply.draft_failures
        assert not has_number(TYPED, reply.text)

    record = turn_record(reply, env.runs_dir)
    assert has_leaf(record, text), "the failing text is not in turn.json as given"
    for code in reply.draft_failures:
        assert has_leaf(record, code), code

    logged = log_text(caplog)
    assert text not in logged and TRAP not in logged, "the model's text was logged"
    env.store.close()
    for cell in db_cells(tmp_path):
        if isinstance(cell, str):
            assert text not in cell and TRAP not in cell, "the failing text is stored"
    assert TRAP not in db_bytes(tmp_path), "the failing text is in the database file"


def test_a_passing_finish_text_is_stored_with_the_turn_and_in_no_log_line(tmp_path, caplog):
    """A9, A12 and answer A3: a text that passed is stored with the turn (slots unfilled),
    and no text the model wrote is ever logged."""
    catch_every_log_line(caplog)
    env = Env(tmp_path)
    reply = env.answered(Q_COUNT, (2025, "18_25"), text=ONE_COUNT_TEXT)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    assert has_leaf(turn_record(reply, env.runs_dir), ONE_COUNT_TEXT)
    assert ONE_COUNT_TEXT not in log_text(caplog), "the model's text was logged"
    env.store.close()
    assert any(isinstance(cell, str) and ONE_COUNT_TEXT in cell for cell in db_cells(tmp_path)), \
        "the passing text is not stored with the turn"


def test_every_turn_that_ran_a_tool_gets_its_own_record(tmp_path):
    """A9: every turn in which a tool ran saves its own turn.json."""
    env = Env(tmp_path)
    first = env.answered(Q_COUNT, (2025, "18_25"))
    second = env.ask(REFUSED["U3"][0], Step(decline("UNSUPPORTED_FIELD")))
    assert first.turn_id != second.turn_id
    assert has_leaf(turn_record(first, env.runs_dir), Q_COUNT)
    assert has_leaf(turn_record(second, env.runs_dir), REFUSED["U3"][0])
    assert len(list(env.runs_dir.glob("*/turn.json"))) == 2


def _explained(env):
    return env.ask(Q_COUNT, Step(describe()), Step(finish("about_data", ABOUT_TEXT)))


def _details_by_tool(env):
    env.answered(Q_COUNT, (2025, "18_25"))  # an earlier answer, so the turn is DETAILS
    return env.ask(Q_SHOW, Step(show_details()))


def _data_class_mismatch(env):
    return env.ask(Q_COUNT, Step(count(2025, "18_25")),
                   data_path=NOT_SYNTHETIC_COPIES["first_row_VERIFIED_OFFICIAL"](env.tmp_path))


def _model_fails_after_a_count(env):
    return env.ask(Q_COUNT, Step(count(2025, "18_25")),
                   error=mod("llm").ModelUnavailable("down"), fail_at=1)


@pytest.mark.parametrize("turn", [_explained, _details_by_tool, _data_class_mismatch,
                                  _model_fails_after_a_count],
                         ids=["explained", "details_by_tool", "data_class_mismatch",
                              "model_fails_after_a_count"])
def test_each_kind_of_turn_that_ran_a_tool_saves_a_record(turn, tmp_path):
    """A9 and A0: every turn that ran a tool saves turn.json, not only a finish or a decline:
    an EXPLAINED turn, a DETAILS turn through show_details, an ERROR after a count ran, and
    a fixed rendering after the model failed. data_class is SYNTHETIC except where the data
    file is not (the mismatch)."""
    env = Env(tmp_path)
    reply = turn(env)
    record = turn_record(reply, env.runs_dir)
    question = Q_SHOW if turn is _details_by_tool else Q_COUNT
    assert has_leaf(record, question), "the question is not in the record"
    if turn is not _data_class_mismatch:
        assert record.get("data_class") == "SYNTHETIC", record.get("data_class")



# ---- R6: what the model wrote at each step, and what failed ----------------------------

STEP_TEXT = "  Counting first,\n kestrel-one \u2019 4321  "  # odd spacing kept exactly


def step_lists(record):
    """Every list in the record whose items are all objects holding the key `text`."""
    found = []

    def walk(obj):
        if isinstance(obj, Mapping):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            if obj and all(isinstance(item, Mapping) and "text" in item for item in obj):
                found.append(obj)
            for value in obj:
                walk(value)
    walk(record)
    return found


def values_of(record, key):
    """Every value held under `key` anywhere in the record."""
    out = []

    def walk(obj):
        if isinstance(obj, Mapping):
            for k, value in obj.items():
                if k == key:
                    out.append(value)
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
    walk(record)
    return out


def test_each_step_holds_what_the_model_wrote_exactly_or_null(tmp_path, caplog):
    """R6: each step in turn.json holds `text`: what the model wrote in that step, exactly
    as given, or null. Three steps: neither text nor a tool call (null); a count with text
    beside it; a finish with no text (null). The step text is never logged, never stored in
    the database and not in the reply."""
    catch_every_log_line(caplog)
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(), Step(count(2025, "18_25"), text=STEP_TEXT),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    record = turn_record(reply, env.runs_dir)
    wanted = [None, STEP_TEXT, None]
    lists = [[item["text"] for item in found] for found in step_lists(record)]
    assert wanted in lists, f"no list of the {len(wanted)} steps' texts: {lists}"
    assert "kestrel-one" not in reply.text
    assert "kestrel-one" not in log_text(caplog), "a step's text was logged"
    env.store.close()
    for cell in db_cells(tmp_path):
        if isinstance(cell, str):
            assert "kestrel-one" not in cell, "a step's text is stored in the database"
    assert "kestrel-one" not in db_bytes(tmp_path)


def test_a_last_step_of_text_only_is_kept_as_its_text(tmp_path):
    """R6 with A4: a step with text and no tool call (read as finish) keeps its text in its
    step too, exactly as given."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25")), Step(text=ONE_COUNT_TEXT))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    record = turn_record(reply, env.runs_dir)
    lists = [[item["text"] for item in found] for found in step_lists(record)]
    assert [None, ONE_COUNT_TEXT] in lists, lists


CHECK_FAILS = {
    # kind: (question, steps, a failing word, a failing character)
    "finding": (Q_COUNT, [Step(count(2025, "18_25")),
                          Step(finish("finding", "I counted Roughly {r1.count} %."))],
                "roughly", "%"),
    "about_data": (Q_COUNT, [Step(describe()),
                             Step(finish("about_data", f"Here is Certainly what I know # "
                                                       f"{{f{single_sentence_facts()[0]}}}."))],
                   "certainly", "#"),
}


@pytest.mark.parametrize("kind", CHECK_FAILS)
def test_a_failed_check_keeps_its_details_in_turn_json_only(kind, tmp_path, caplog):
    """R6: when a check fails, the record also holds `check_details`: the words and
    characters that failed (here one of each). Not logged, not in the database, not in the
    reply."""
    question, steps, word, char = CHECK_FAILS[kind]
    catch_every_log_line(caplog)
    env = Env(tmp_path)
    reply = env.ask(question, *steps)
    check_reply(reply, env.model)
    assert reply.reply_style == "fallback", (reply.reply_style, reply.text)
    record = turn_record(reply, env.runs_dir)
    details = values_of(record, "check_details")
    assert details, "no check_details in turn.json"
    shown = json.dumps(details, ensure_ascii=False)
    assert word in shown.lower(), f"{word!r} is not in check_details: {shown}"
    assert char in shown, f"{char!r} is not in check_details: {shown}"
    assert word not in reply.text.lower()
    assert word not in log_text(caplog).lower(), "check_details were logged"
    env.store.close()
    for cell in db_cells(tmp_path):
        if isinstance(cell, str):
            assert word not in cell.lower(), "check_details are stored in the database"
