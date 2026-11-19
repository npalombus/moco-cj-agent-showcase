"""Brief point 2: the tools the model is offered and the limits of one turn (design P1A, A3,
with A4 step 5 for the limits and A5's tidying where a count needs it). Revision 2
(docs/P1A-R2-DESIGN.md R2): a count answers its fact slots instead of field names
({"result_id", "year", "age_group", "slots": ["{rN.count}", "{rN.months}"]}), a compare
{"result_id", "slots": ["{rN.compare}"]}, describe_data {"facts": [{"slot": "{fN}", "text":
<fact line N>}, ...]}; the key `fields` is gone.

Every test runs a real agent.handle_question with a FakeModel (p1support.Env) and reads what
Python answered each tool call from the tool messages a later step was given
(FakeModel.answer). Numbers come from the truth file; nothing from the data is typed here.

Accepted both ways (the design allows either):
- A tool that takes no argument may leave out "parameters" or "properties" (A3 names no
  argument for it; an empty properties object is the same thing).
- An enum on decline's reason_code or finish's kind is not required; when given it must be
  exactly the listed values.
- The age_group a count answers for all ages may be "all" or None (A3 shows a code only).
- An extra argument to count_arrests may give INVALID_ARGUMENTS (A5: "anything else goes to
  stage 1's strict check unchanged") or a count (A3: Python calls execute_call with only
  year and age_group). Either way its words never reach the reply.
- describe_data's fact text may keep or drop the leading "- " of each fact line (as P1A's
  tests read A3; R2 writes "<fact line 1>").
- After the 8-count or the 12-call limit, the loop may stop or go on to the step limit
  (kit-log/raw/P1A-A-notes.txt). The LIMIT answer is checked only when a later step
  happens.
- A reply that a limit ended with results: reply_style `fallback` or `fixed` (notes).

Cannot check here: what a real model sends; whether Python's tool messages read well to a
model; the inside of AgentReply.results (answer A2 of briefs/QUESTIONS.md).

Note for the build: check_tools_hold_no_data looks at the whole message list, system
message included, so the agent prompt (A11 lets the build reword it) and the DATA block
must hold none of the data totals (p1support.all_totals()), not even as a length limit.
"""
import json
import re

import pytest

from p1support import (ALL_TOOLS, DECLINE_CODES, MONTH_NAMES,
                       ONE_COUNT_TEXT, RESTRICTED_TOOLS, ROUTER_MODEL, Env, Step,
                       answered_manifests, assert_answered, assert_fixed, call,
                       check_reply, check_tools_hold_no_data, compare, count,
                       coverage_years, decline, describe, fact_lines, finish,
                       fixed_line1_re, manifests)
from support import (AGE_GROUPS, DATA_CSV, NOT_SYNTHETIC_COPIES, REFUSED, SUPPORTED,
                     check_common, check_saved, snapshot_of)

Q_COUNT = SUPPORTED["S1"][0]  # 2025, ages 18 to 25; no guard rule matches it
Q_COMPARE = "Compare 2024 and 2025 for people under 18."
Q_ABOUT = "What data do you have?"
FINISH_ONE = Step(finish("finding", ONE_COUNT_TEXT))  # passes R1's checks
FINISH_KINDS = ("finding", "about_data", "background")

# A3: the argument names of each tool.
ARGUMENTS = {"count_arrests": {"year", "age_group"}, "compare": {"result_ids", "field"},
             "describe_data": set(), "ask_user": {"missing"}, "show_details": set(),
             "decline": {"reason_code"}, "finish": {"kind", "text"}}

# Stage 1's status for each refusal code (design P0): the record still saved by
# execute_call when a count is refused.
RECORD_STATUS = {"OUT_OF_COVERAGE": "UNSUPPORTED", "INVALID_ARGUMENTS": "ERROR",
                 "DATA_CLASS_MISMATCH": "ERROR", "DATA_UNREADABLE": "ERROR"}


# ---- local helpers ------------------------------------------------------------------

def covers():
    """A3's "covers" text, from the registry's coverage ("2024 to 2025")."""
    years = coverage_years()
    return f"{years[0]} to {years[-1]}"


def count_answer(rid, year, group):
    """R2: a count's answer: its id, its filters and its two fact slots."""
    return {"result_id": rid, "year": year, "age_group": group,
            "slots": [f"{{{rid}.count}}", f"{{{rid}.months}}"]}


def compare_answer(rid):
    """R2: a compare's answer: its id and its fact slot."""
    return {"result_id": rid, "slots": [f"{{{rid}.compare}}"]}


def tools_by_name(model, index):
    tools = model.calls[index]["tools"]
    named = {tool["function"]["name"]: tool for tool in tools}
    assert len(named) == len(tools), "a tool is offered twice"
    return named


def argument_names(tool):
    # Accepted both ways: a tool with no argument may leave out parameters or properties.
    return set((tool["function"].get("parameters") or {}).get("properties") or {})


def answers_are_objects(model):
    """A3: every tool answer any step was given is a JSON object."""
    for recorded in model.calls:
        for message in recorded["messages"]:
            if message.get("role") == "tool":
                assert isinstance(json.loads(message["content"]), dict), message["content"]


def check_no_month_in_tools(model):
    """A3: no tool message holds a month name (busiest_month and quietest_month are values
    from the data). Case-sensitive, so a lower-case "may" is not caught."""
    month = re.compile(r"\b(?:" + "|".join(MONTH_NAMES) + r")\b")
    for recorded in model.calls:
        for message in recorded["messages"]:
            if message.get("role") == "tool":
                assert not month.search(message["content"]), message["content"]


def refusal_record(runs_dir, code, question, data_path=DATA_CSV):
    """The stage 1 refusal record execute_call saved for a refused count (design P0
    sections 6 and 7), with the model's router (P1 section 9, unchanged by A3)."""
    found = [m for m in manifests(runs_dir) if m["reason_code"] == code]
    assert len(found) == 1, [m["reason_code"] for m in manifests(runs_dir)]
    d = found[0]
    check_common(d, question=question, router=ROUTER_MODEL)
    assert d["status"] == RECORD_STATUS[code], d["status"]
    assert d["computed_values"] == {}
    assert d["chart_uri"] is None and d["chart_title"] is None
    if code == "DATA_UNREADABLE":
        assert d["snapshot_id"] is None
    else:
        assert d["snapshot_id"] in (None, snapshot_of(data_path))
    assert code in d["technical_summary"]
    run_dir = check_saved(d, runs_dir)
    assert not (run_dir / "chart.png").exists(), "a refusal must not save a chart"
    return d


# ---- the tools offered (A3, A11) ------------------------------------------------------

def test_an_unrestricted_turn_is_offered_the_seven_tools(tmp_path):
    """A3 and A11: the seven tools, at every step of a turn the guard did not restrict."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25")), FINISH_ONE)
    check_reply(reply, env.model)
    assert len(env.model.calls) == 2
    for i in range(len(env.model.calls)):
        assert env.model.tools_offered(i) == ALL_TOOLS


@pytest.mark.parametrize("name", ARGUMENTS)
def test_each_tool_has_the_argument_names_of_a3(name, tmp_path):
    env = Env(tmp_path)
    env.ask(Q_COUNT, Step(count(2025, "18_25")), FINISH_ONE)
    assert argument_names(tools_by_name(env.model, 0)[name]) == ARGUMENTS[name]


@pytest.mark.parametrize("name, argument, values", [
    ("decline", "reason_code", DECLINE_CODES),
    ("finish", "kind", FINISH_KINDS),
], ids=["decline_reason_code", "finish_kind"])
def test_an_enum_when_given_holds_exactly_the_listed_values(name, argument, values, tmp_path):
    """A3 lists the values; an enum is not required (accepted both ways)."""
    env = Env(tmp_path)
    env.ask(Q_COUNT, Step(count(2025, "18_25")), FINISH_ONE)
    schema = tools_by_name(env.model, 0)[name]["function"]["parameters"]["properties"][argument]
    if "enum" in schema:
        assert sorted(schema["enum"]) == sorted(values), schema["enum"]


@pytest.mark.parametrize("key, code", [("U5", "REAL_DATA_NOT_AVAILABLE"),
                                       ("U1", "UNSUPPORTED_METRIC"),
                                       ("U3", "UNSUPPORTED_FIELD")])
def test_a_restricted_turn_is_offered_five_tools_and_counts_nothing(key, code, tmp_path):
    """A2 and A3: a question matching stage 1's rule 2, 3 or 4 (P1 section 6's guard rows)
    is offered five tools, never count_arrests or compare. A count_arrests or compare call
    anyway runs nothing and gets an error object (any code: BAD_CALL and BAD_COMPARE are
    both reasonable for the compare)."""
    question, stage1_code = REFUSED[key]
    assert stage1_code == code
    env = Env(tmp_path)
    reply = env.ask(question, Step(count(2025, None), compare("r1", "r2")),
                    Step(decline(code)))
    check_reply(reply, env.model)
    assert len(env.model.calls) == 2
    for i in range(len(env.model.calls)):
        assert env.model.tools_offered(i) == RESTRICTED_TOOLS
    answer = env.model.answer(0, 0)
    assert isinstance(answer, dict) and "error" in answer, answer
    second = env.model.answer(0, 1)
    assert isinstance(second, dict) and "error" in second, second
    assert manifests(env.runs_dir) == []
    assert list(reply.run_ids) == []
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code)


# ---- count_arrests (A3, A5) -------------------------------------------------------------

def test_count_arrests_answers_the_result_id_filters_and_slots(tmp_path):
    """A3 and R2: r1, r2, r3 in the order made; the year, the age group and the count's two
    fact slots; no key `fields`."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(2025, "under_18"), count(2024, "all"),
                                  count(2025, "18_25")), FINISH_ONE)
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    assert env.model.answer(0, 0) == count_answer("r1", 2025, "under_18")
    # Accepted both ways: all ages answered as "all" or None.
    assert env.model.answer(0, 1) in (count_answer("r2", 2024, "all"),
                                      count_answer("r2", 2024, None))
    assert env.model.answer(0, 2) == count_answer("r3", 2025, "18_25")
    assert all("fields" not in env.model.answer(0, i) for i in range(3))
    assert len(answered_manifests(env.runs_dir)) == 3
    answers_are_objects(env.model)


SCRIPTS = {
    "one_count": (Q_COUNT, [Step(count(2025, "18_25")), FINISH_ONE]),
    "several_counts": (Q_COUNT, [Step(*[count(2025, g) for g in ("all", *AGE_GROUPS)]),
                                 Step(count(2024, "all")), FINISH_ONE]),
    "a_compare": (Q_COMPARE, [Step(count(2024, "under_18"), count(2025, "under_18")),
                              Step(compare("r1", "r2")), FINISH_ONE]),
}


@pytest.mark.parametrize("script", SCRIPTS.values(), ids=SCRIPTS)
def test_no_message_given_to_the_model_holds_a_value_from_the_data(script, tmp_path):
    """A0, A1, A3 and R2: the model is told ids and slots, never a value. The whole
    message list of every step is checked against the truth file's totals, and every
    tool message holds no number but the covered years and the fact sheet's."""
    question, steps = script
    env = Env(tmp_path)
    reply = env.ask(question, *steps)
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    assert len(env.model.calls) == len(steps)
    check_tools_hold_no_data(env.model)
    check_no_month_in_tools(env.model)
    answers_are_objects(env.model)


REPEATS = {
    "same_values": (count(2025, "18_25"), count(2025, "18_25")),
    "year_as_text": (count(2025, "18_25"), count("2025", "18_25")),
    "year_as_float": (count(2025, "18_25"), count(2025.0, "18_25")),
    "null_then_all": (count(2025, None), count(2025, "all")),
    "all_then_null": (count(2025, "all"), count(2025, None)),
    "all_then_missing": (count(2025, "all"), count(2025)),
}


@pytest.mark.parametrize("first, again", REPEATS.values(), ids=REPEATS)
def test_a_repeated_count_returns_the_earlier_id_and_saves_no_second_run(first, again,
                                                                         tmp_path):
    """A3: the same year and age group already counted in this turn (after A5's tidying;
    in a fresh thread a year-only count is all ages) returns the earlier id and counts
    nothing again."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(first), Step(again), FINISH_ONE)
    check_reply(reply, env.model)
    assert env.model.answer(0, 0)["result_id"] == "r1"
    assert env.model.answer(1, 0)["result_id"] == "r1"
    assert len(answered_manifests(env.runs_dir)) == 1
    assert len(reply.run_ids) == 1
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    check_tools_hold_no_data(env.model)
    check_no_month_in_tools(env.model)


def check_error_then_go_on(env, reply, code, question=Q_COUNT):
    """A3: the error answer exactly; stage 1's refusal record still saved; the turn went on
    to a later count (r1: an error makes no result) and a passing finish."""
    check_reply(reply, env.model)
    assert env.model.answer(0, 0) == {"error": code, "covers": covers()}
    refusal_record(env.runs_dir, code, question)
    assert env.model.answer(1, 0) == count_answer("r1", 2025, "18_25")
    assert len(answered_manifests(env.runs_dir)) == 1
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    answers_are_objects(env.model)


@pytest.mark.parametrize("year", [2019, 20250], ids=["2019", "whole_number_20250"])
def test_a_year_with_no_data_is_out_of_coverage_and_the_turn_goes_on(year, tmp_path):
    """A3: OUT_OF_COVERAGE. The whole number 20250 passes the strict check and has no
    rows (design P0 sections 4 and 8)."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(year, "18_25")), Step(count(2025, "18_25")),
                    FINISH_ONE)
    check_error_then_go_on(env, reply, "OUT_OF_COVERAGE")


# Arguments A5's tidying leaves alone, so stage 1's strict check refuses them (carried
# over from the P1 tests, less those A5 now tidies or reads as "not stated").
NOT_TIDIED = {
    "year_twenty": {"year": "twenty", "age_group": "18_25"},
    "year_text_20250": {"year": "20250", "age_group": "18_25"},
    "year_True": {"year": True, "age_group": "18_25"},
    "year_text_2025.0": {"year": "2025.0", "age_group": "18_25"},
    "year_float_2025.5": {"year": 2025.5, "age_group": "18_25"},
    "year_text_with_a_space": {"year": " 2025", "age_group": "18_25"},
    "age_group_code_in_capitals": {"year": 2025, "age_group": "UNDER_18"},
    "age_group_wording_not_code": {"year": 2025, "age_group": "18-25"},
    "age_group_unknown": {"year": 2025, "age_group": "teenagers_zqx"},
}


@pytest.mark.parametrize("arguments", NOT_TIDIED.values(), ids=NOT_TIDIED)
def test_invalid_arguments_are_an_error_answer_and_the_turn_goes_on(arguments, tmp_path):
    """A3 and A5: anything the tidying does not change goes to stage 1's strict check;
    INVALID_ARGUMENTS comes back as an error and the turn goes on."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(call("count_arrests", arguments)),
                    Step(count(2025, "18_25")), FINISH_ONE)
    check_error_then_go_on(env, reply, "INVALID_ARGUMENTS")
    assert "twenty" not in reply.text.lower()


def test_an_extra_argument_gives_invalid_arguments_or_a_count(tmp_path):
    """Accepted both ways (module docstring). The extra argument's words never reach the
    reply (check_reply looks for the zqx mark)."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25", county_zqx="Montgomery")),
                    Step(count(2025, "18_25")), FINISH_ONE)
    check_reply(reply, env.model)
    first = env.model.answer(0, 0)
    assert first in ({"error": "INVALID_ARGUMENTS", "covers": covers()},
                     count_answer("r1", 2025, "18_25")), first
    assert env.model.answer(1, 0)["result_id"] == "r1"
    assert len(answered_manifests(env.runs_dir)) == 1
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    assert "county_zqx" not in reply.text


def check_data_problem(env, reply, code, data_path):
    """A3: the turn ends at the count, with the code's fixed text (A7's table)."""
    check_reply(reply, env.model)
    assert len(env.model.calls) == 1, "the turn must end at once"
    assert (reply.status, reply.reason_code) == ("ERROR", code), reply.text
    assert_fixed(reply.text, code)
    refusal_record(env.runs_dir, code, Q_COUNT, data_path=data_path)
    assert answered_manifests(env.runs_dir) == []
    assert reply.chart_path is None


# A second count in the same step: refusal_record's "exactly one record" fails if it ran.
BAD_DATA_STEP = Step(count(2025, "18_25"), count(2024, "18_25"))


@pytest.mark.parametrize("key", ["first_row_VERIFIED_OFFICIAL", "no_data_class_column",
                                 "middle_row_REAL"])
def test_data_that_is_not_synthetic_ends_the_turn(key, tmp_path):
    bad = NOT_SYNTHETIC_COPIES[key](tmp_path)
    env = Env(tmp_path, data_path=bad)
    reply = env.ask(Q_COUNT, BAD_DATA_STEP, FINISH_ONE)
    check_data_problem(env, reply, "DATA_CLASS_MISMATCH", bad)


def test_a_missing_data_file_ends_the_turn(tmp_path):
    missing = tmp_path / "no-such-data.csv"
    env = Env(tmp_path, data_path=missing)
    reply = env.ask(Q_COUNT, BAD_DATA_STEP, FINISH_ONE)
    check_data_problem(env, reply, "DATA_UNREADABLE", missing)


# ---- compare (A3, A6) -------------------------------------------------------------------

def test_compare_with_good_ids_makes_a_compare_result(tmp_path):
    env = Env(tmp_path)
    reply = env.ask(Q_COMPARE, Step(count(2024, "under_18"), count(2025, "under_18")),
                    Step(compare("r1", "r2")), FINISH_ONE)
    check_reply(reply, env.model)
    assert env.model.answer(1, 0) == compare_answer("r3")
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    check_tools_hold_no_data(env.model)


BAD_COMPARES = {
    "one_id": ([], compare("r1")),
    "an_unknown_id": ([], compare("r1", "r9")),
    "the_same_id_twice": ([], compare("r1", "r1")),
    "a_compare_results_id": ([compare("r1", "r2")], compare("r1", "r3")),
    "field_busiest_count": ([], compare("r1", "r2", field="busiest_count")),
    "result_ids_not_a_list": ([], call("compare", {"result_ids": "r1,r2", "field": "total"})),
}


@pytest.mark.parametrize("before, bad", BAD_COMPARES.values(), ids=BAD_COMPARES)
def test_compare_with_bad_arguments_answers_bad_compare(before, bad, tmp_path):
    """A3: 2 to 8 different ids of count results of this turn, and field "total"."""
    env = Env(tmp_path)
    reply = env.ask(Q_COMPARE, Step(count(2024, "under_18"), count(2025, "under_18"), *before),
                    Step(bad), FINISH_ONE)
    check_reply(reply, env.model)
    if before:  # r3 exists and is a compare result, so BAD_COMPARE is for the reason named
        assert env.model.answer(0, 2) == compare_answer("r3")
    assert env.model.answer(1, 0) == {"error": "BAD_COMPARE"}
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    answers_are_objects(env.model)


# ---- describe_data and bad calls (A3) -------------------------------------------------------

def test_describe_data_answers_each_fact_line_with_its_slot(tmp_path):
    """A3, A8 and R2: {"facts": [{"slot": "{f1}", "text": <fact line 1>}, ...]}, the fact
    sheet's lines in order (accepted with or without "- ")."""
    env = Env(tmp_path)
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "Here is {f1}.")))
    check_reply(reply, env.model)
    facts = fact_lines()
    assert facts, "the fact sheet has no fact lines"
    answers = [{"facts": [{"slot": f"{{f{n}}}", "text": prefix + line}
                          for n, line in enumerate(facts, 1)]} for prefix in ("", "- ")]
    assert env.model.answer(0, 0) in answers, env.model.answer(0, 0)
    check_tools_hold_no_data(env.model)


def test_an_unknown_tool_gets_bad_call_and_the_turn_goes_on(tmp_path):
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(call("erase_records_zqx", {"year": 2025})),
                    Step(count(2025, "18_25")), FINISH_ONE)
    check_reply(reply, env.model)
    assert env.model.answer(0, 0) == {"error": "BAD_CALL"}
    assert env.model.answer(1, 0) == count_answer("r1", 2025, "18_25")
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)


NOT_AN_OBJECT = {"a_list": "[2025]", "not_json": "not json", "a_string": '"x"',
                 "a_number": "2025", "null": "null", "empty": ""}


@pytest.mark.parametrize("arguments_json", NOT_AN_OBJECT.values(), ids=NOT_AN_OBJECT)
def test_arguments_that_are_not_a_json_object_get_bad_call(arguments_json, tmp_path):
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(call("count_arrests", arguments_json)),
                    Step(count(2025, "18_25")), FINISH_ONE)
    check_reply(reply, env.model)
    assert env.model.answer(0, 0) == {"error": "BAD_CALL"}
    assert env.model.answer(1, 0) == count_answer("r1", 2025, "18_25")
    assert len(manifests(env.runs_dir)) == 1  # the bad call ran nothing
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)


@pytest.mark.parametrize("name", ["compare", "decline", "ask_user", "finish", "describe_data"])
def test_arguments_that_are_not_a_json_object_get_bad_call_for_every_tool(name, tmp_path):
    """A3: the BAD_CALL rule holds for every tool; a turn-ending tool with bad arguments
    does not end the turn."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25"), call(name, "[1]")), FINISH_ONE)
    check_reply(reply, env.model)
    assert env.model.answer(0, 1) == {"error": "BAD_CALL"}
    assert len(env.model.calls) == 2  # the turn went on
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)


def test_every_tool_answer_is_a_json_object(tmp_path):
    """A3: "Every tool result is a small JSON object", for each kind of answer."""
    env = Env(tmp_path)
    first = Step(count(2025, "18_25"), count(2019, "18_25"), count("twenty", "18_25"),
                 call("erase_records_zqx", {}), call("count_arrests", "not json"),
                 describe(), compare("r1"))
    second = Step(count(2024, "18_25"), compare("r1", "r2"), count(2025, "18_25"))
    reply = env.ask(Q_COUNT, first, second, FINISH_ONE)
    check_reply(reply, env.model)
    for step, scripted in enumerate((first, second)):
        for position in range(len(scripted.calls)):
            assert isinstance(env.model.answer(step, position), dict), (step, position)


def test_a_tool_after_an_ending_tool_in_the_same_step_is_not_run(tmp_path):
    """A4 step 5: the loop goes on until a tool ends the turn; a call after it is not run."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25")),
                    Step(finish("finding", ONE_COUNT_TEXT), count(2024, "18_25")))
    check_reply(reply, env.model)
    assert len(env.model.calls) == 2
    assert len(manifests(env.runs_dir)) == 1
    assert len(reply.run_ids) == 1
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)


# ---- limits (A3, A4 step 5) -------------------------------------------------------------

def check_limit_with_a_result(env, reply):
    """A4: ANSWERED with the fixed rendering (A7) and LOOP_LIMIT among the failure codes."""
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    assert "LOOP_LIMIT" in reply.draft_failures, reply.draft_failures
    assert reply.reply_style in ("fallback", "fixed")  # accepted both ways (notes)


def check_limit_without_a_result(env, reply):
    """A4: ERROR / MODEL_BAD_OUTPUT with its fixed text."""
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("ERROR", "MODEL_BAD_OUTPUT"), reply.text
    assert_fixed(reply.text, "MODEL_BAD_OUTPUT")


NEVER_ENDS = Step(describe())  # repeated by the FakeModel for every later step
STEP_LIMITS = {"default_6": ({}, 6), "set_to_3": ({"MOCO_MAX_STEPS": 3}, 3)}


@pytest.mark.parametrize("settings, limit", STEP_LIMITS.values(), ids=STEP_LIMITS)
def test_the_step_limit_with_a_result_answers_with_the_fixed_rendering(settings, limit,
                                                                       tmp_path):
    env = Env(tmp_path, **settings)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25")), NEVER_ENDS)
    assert len(env.model.calls) == limit
    check_limit_with_a_result(env, reply)


@pytest.mark.parametrize("settings, limit", STEP_LIMITS.values(), ids=STEP_LIMITS)
def test_the_step_limit_without_a_result_is_model_bad_output(settings, limit, tmp_path):
    env = Env(tmp_path, **settings)
    reply = env.ask(Q_COUNT, NEVER_ENDS)
    assert len(env.model.calls) == limit
    check_limit_without_a_result(env, reply)


def test_at_most_eight_counts_run_in_a_turn(tmp_path):
    """A3: nine distinct counts in one step run exactly eight; the ninth gets LIMIT."""
    nine = [(year, group) for year in (2024, 2025) for group in ("all", *AGE_GROUPS)][:9]
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(*[count(y, g) for y, g in nine]), FINISH_ONE)
    check_reply(reply, env.model)
    saved = answered_manifests(env.runs_dir)
    assert len(saved) == 8 and len(manifests(env.runs_dir)) == 8
    assert sorted(reply.run_ids) == sorted(m["run_id"] for m in saved)
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    if len(env.model.calls) > 1:  # the loop went on (accepted both ways)
        assert env.model.answer(0, 8) == {"error": "LIMIT"}
    check_tools_hold_no_data(env.model)


def test_at_most_twelve_tool_calls_run_in_a_turn(tmp_path):
    """A3: after 12 calls a count is not run and gets LIMIT; with no result the turn ends
    ERROR / MODEL_BAD_OUTPUT."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(*[describe() for _ in range(12)]),
                    Step(count(2025, "18_25")))
    assert manifests(env.runs_dir) == []
    if len(env.model.calls) > 2:  # a step after the count happened (accepted both ways)
        assert env.model.answer(1, 0) == {"error": "LIMIT"}
    check_limit_without_a_result(env, reply)


def test_the_twelfth_tool_call_runs_and_the_thirteenth_does_not(tmp_path):
    """A3: call 12 (a count) runs and call 13 (another count) gets LIMIT. LOOP_LIMIT is not
    asserted: A4 names it only for the step and time limits, and the loop may stop or go
    on after the LIMIT (notes)."""
    env = Env(tmp_path)
    reply = env.ask(Q_COUNT, Step(*[describe() for _ in range(11)], count(2025, "18_25")),
                    Step(count(2024, "18_25")))
    check_reply(reply, env.model)
    assert len(manifests(env.runs_dir)) == 1 and len(reply.run_ids) == 1
    assert reply.status == "ANSWERED", (reply.reason_code, reply.text)
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    if len(env.model.calls) > 2:  # a step after call 13 happened (accepted both ways)
        assert env.model.answer(1, 0) == {"error": "LIMIT"}


# FakeModel seconds=40 on Env.clock: the time is read before each step, so the default 90
# allows steps at 0, 40 and 80 seconds (3 calls), and 30 allows only the first.
TIME_LIMITS = {"default_90": ({}, 3), "set_to_30": ({"MOCO_TURN_SECONDS": 30}, 1)}


@pytest.mark.parametrize("settings, calls", TIME_LIMITS.values(), ids=TIME_LIMITS)
def test_the_time_limit_with_a_result_answers_with_the_fixed_rendering(settings, calls,
                                                                       tmp_path):
    env = Env(tmp_path, **settings)
    reply = env.ask(Q_COUNT, Step(count(2025, "18_25")), NEVER_ENDS, seconds=40)
    assert len(env.model.calls) == calls
    check_limit_with_a_result(env, reply)


@pytest.mark.parametrize("settings, calls", TIME_LIMITS.values(), ids=TIME_LIMITS)
def test_the_time_limit_without_a_result_is_model_bad_output(settings, calls, tmp_path):
    env = Env(tmp_path, **settings)
    reply = env.ask(Q_COUNT, NEVER_ENDS, seconds=40)
    assert len(env.model.calls) == calls
    check_limit_without_a_result(env, reply)
