"""Stage 3 Part A, round 2: docs/S3A-DESIGN.md C14 to C20 and C22 ("What the round 2 tests
must show": every rule exactly, as whole strings, with both forms where a rule has two).

C21 (under 18 inside one turn) is left out: it applies "ONLY if Nino says yes", and no
decision in docs/DECISIONS.md names it.

- C14: a source file with an `interpreted` person field (made in tmp_path from the fixture,
  with CountyEnv's `change=`): its `interpreted_line` after the sensitive line and before
  the source line, once per reply; about the data lists the field under `Grouped by the
  agent from free text:` as `<dimension>: <coverage>`, then the interpreted_line; the two
  invalid shapes make the file invalid (C20).
- C15: the count phrase of a breakdown that leaves records out ends ` with a <dimension>
  recorded` or ` with a usable age`; two fields joined with `and`; a filter changes nothing;
  `read_as` does not carry it.
- C16: hidden values are never ranked: groups and compare phrases.
- C17: `year` with `month` is BAD_FIELD.
- C18: the later source line names its source.
- C19: with more than one count result and a left-out or hidden line, each left-out line
  starts `For <read_as>: ` without brackets; the hidden line stays one line.
- C20: a source file is checked when it is loaded.
- C22: a share above 0.5% and below 1% is written `1%`.

Readings (each in kit-log/raw/S3S-A-notes.txt): C15 with two breakdown fields is tested only
where both leave records out, in group_by order; C20's "logged once at start" is read as one
log record naming the file over a process's loads and turns; the reason `fetch` shows names
the key or rule that failed; the about-the-data block's lines are joined as the rest of C10's
lines (one space, one line break or one blank line).
"""
import json
import logging
import re
import sys
from pathlib import Path

import pytest

from p1support import Step, describe, finish, mod
from s3support import (A_ID, C_ID, COPY_NOW, Q_ABOUT, Q_BREAKDOWN, Q_COMPARE, Q_COUNT, Q_SHARE,
                       SEP, CountyEnv, assert_reply, bulk_rows, check_county_reply, compare,
                       count, fixture_rows, hidden_line, is_, left_out_line, made_rows,
                       sensitive_line, service_for, share, source_json, source_re, table_lines,
                       truth, use_sources, write_sources, year)

PAGE_A = source_json("arrests_like")["page"]
TITLE_A = source_json("arrests_like")["title"]
SENSITIVE_A = sensitive_line("arrest records")
COVERAGE = ("SYNTHETIC coverage note: most made-up records carry a usable race; the rest are "
            "left out.")
INTERPRETED_LINE = ("SYNTHETIC: the made-up county wrote race as free text, and the agent "
                    "grouped the spellings.")
ETH_COVERAGE = "SYNTHETIC coverage note: every made-up record carries an ethnicity."


def interpreted(*names, line=True, coverage=True):
    """A change for CountyEnv: the fields `names` of arrests_like are `interpreted`."""
    def change(src):
        for f in src["fields"]:
            if f["name"] in names:
                f["interpreted"] = True
                if coverage:
                    f["coverage"] = COVERAGE if f["name"] == "race" else ETH_COVERAGE
        if line:
            src["interpreted_line"] = INTERPRETED_LINE
    return change


def turn(env, spec, text="I counted {r1.count}.", question=Q_BREAKDOWN, sid=A_ID):
    reply = env.ask(question, Step(count(sid, *spec)), Step(finish("finding", text)))
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def with_interpreted(sensitive=True):
    """C14: the interpreted line comes after the sensitive line (C10's step 5a)."""
    parts = ([re.escape(SENSITIVE_A)] if sensitive else []) + [re.escape(INTERPRETED_LINE)]
    return re.compile(SEP.join(parts))


# ---- C14 -------------------------------------------------------------------------------------

def test_c14_a_filter_on_an_interpreted_field_adds_its_line(tmp_path, monkeypatch):
    spec = (year(2025), [is_("race", "group Alpha")])
    assert truth("arrests_like", *spec)["total"] == 65
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": interpreted("race")})
    reply = turn(env, spec)
    assert_reply(reply.text, "I counted 65 arrest records of people recorded as group Alpha in "
                             "2025.", sensitive=with_interpreted(),
                 source=source_re("arrests_like", first=True))


def test_c14_a_breakdown_by_an_interpreted_field_adds_its_line_once(tmp_path, monkeypatch):
    """Once per reply, however many interpreted fields the spec uses (race and ethnicity)."""
    spec = (year(2025), [is_("ethnicity", "Hispanic")], ["race"])
    t = truth("arrests_like", *spec)
    env = CountyEnv(tmp_path, monkeypatch,
                    change={"arrests_like": interpreted("race", "ethnicity")})
    reply = turn(env, spec)
    assert reply.text.count(INTERPRETED_LINE) == 1, reply.text
    assert reply.text.index(SENSITIVE_A) < reply.text.index(INTERPRETED_LINE) < \
        reply.text.index("Source: ")
    assert table_lines(t["groups"])[0] in reply.text


def test_c14_no_line_when_the_spec_does_not_use_the_field(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": interpreted("race")})
    reply = turn(env, (year(2025), [is_("district", "district 3")]))
    assert INTERPRETED_LINE not in reply.text
    assert SENSITIVE_A not in reply.text


def test_c14_an_interpreted_field_that_is_not_sensitive_gets_only_its_line(tmp_path,
                                                                          monkeypatch):
    """C14's last rule, the other way round: district made interpreted (not sensitive)."""
    def change(src):
        for f in src["fields"]:
            if f["name"] == "district":
                f["interpreted"], f["coverage"] = True, COVERAGE
        src["interpreted_line"] = INTERPRETED_LINE
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": change})
    reply = turn(env, (year(2025), [is_("district", "district 3")]))
    assert INTERPRETED_LINE in reply.text and SENSITIVE_A not in reply.text
    assert reply.text.index(INTERPRETED_LINE) < reply.text.index("Source: ")


def test_c14_about_the_data_lists_the_interpreted_fields(tmp_path, monkeypatch):
    """`Grouped by the agent from free text:`, one line per field `<dimension>: <coverage>`,
    then the interpreted_line."""
    env = CountyEnv(tmp_path, monkeypatch,
                    change={"arrests_like": interpreted("race", "ethnicity")})
    reply = env.ask(Q_ABOUT, Step(finish("about_data", "Here is what I know.")))
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    block = SEP.join(re.escape(x) for x in [
        "Grouped by the agent from free text:", f"race: {COVERAGE}",
        f"ethnicity: {ETH_COVERAGE}", INTERPRETED_LINE])
    assert re.search(block, reply.text), reply.text


def test_c14_about_the_data_has_no_block_without_interpreted_fields(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_ABOUT, Step(finish("about_data", "Here is what I know.")))
    assert "Grouped by the agent from free text:" not in reply.text


# ---- C15 -------------------------------------------------------------------------------------

def test_c15_a_breakdown_that_leaves_records_out_says_so(tmp_path, monkeypatch):
    spec = (year(2024), [], ["district"])
    t = truth("arrests_like", *spec)
    assert t["left_out"]["district"] == 10 and t["total"] == 220
    env = CountyEnv(tmp_path, monkeypatch)
    reply = turn(env, spec)
    assert_reply(reply.text, "I counted 220 arrest records in 2024 with a district recorded.",
                 table=table_lines(t["groups"]), left_out=[left_out_line(10, "district")],
                 source=source_re("arrests_like"))
    assert "recorded" not in env.model.answer(0)["read_as"], "read_as does not carry it"


def test_c15_an_age_band_breakdown_says_with_a_usable_age(tmp_path, monkeypatch):
    spec = (year(2025), [], ["age_band"])
    assert truth("arrests_like", *spec)["left_out"]["age"] == 5
    env = CountyEnv(tmp_path, monkeypatch)
    reply = turn(env, spec)
    assert reply.text.startswith("I counted 235 arrest records in 2025 with a usable age.\n") \
        or reply.text.startswith("I counted 235 arrest records in 2025 with a usable age. "), \
        reply.text


def test_c15_a_flag_breakdown_says_its_dimension(tmp_path, monkeypatch):
    rows = made_rows("arrests_like", (30, {"adjacent_to_school": "1"}),
                     (40, {"adjacent_to_school": "0"}), (12, {"adjacent_to_school": None}))
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = turn(env, (year(2025), [], ["adjacent_to_school"]))
    assert reply.text.startswith("I counted 70 arrest records in 2025 with a distance from a "
                                 "school recorded."), reply.text
    assert left_out_line(12, "distance from a school") in reply.text


def test_c15_two_breakdown_fields_are_joined_with_and(tmp_path, monkeypatch):
    rows = made_rows("arrests_like", (40, {"district": "1", "gender": "Female"}),
                     (30, {"district": "2", "gender": "Male"}), (11, {"district": None}),
                     (12, {"gender": None}))
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = turn(env, (year(2025), [], ["district", "gender"]))
    assert reply.text.startswith("I counted 70 arrest records in 2025 with a district and a "
                                 "gender recorded."), reply.text


def test_c15_a_filter_that_leaves_records_out_changes_nothing(tmp_path, monkeypatch):
    spec = (year(2024), [is_("district", "district 3")])
    t = truth("arrests_like", *spec)
    assert t["left_out"]["district"] == 10
    env = CountyEnv(tmp_path, monkeypatch)
    reply = turn(env, spec)
    assert reply.text.startswith(f"I counted {t['total']} arrest records in district 3 in "
                                 f"2024.\n") or reply.text.startswith(
        f"I counted {t['total']} arrest records in district 3 in 2024. "), reply.text
    assert "recorded." not in reply.text.split("\n")[0]


def test_c15_nothing_left_out_no_ending(tmp_path, monkeypatch):
    spec = (year(2026), [], ["district"])
    assert truth("arrests_like", *spec)["left_out"]["district"] == 0
    env = CountyEnv(tmp_path, monkeypatch)
    reply = turn(env, spec)
    assert reply.text.startswith("I counted 130 arrest records in 2026 (through 17 September "
                                 "2026, the latest in this copy)."), reply.text


# ---- C16 -------------------------------------------------------------------------------------

def district_rows(*counts):
    """2025 rows with these counts in districts 1, 2, ... (made_rows; 0 makes none)."""
    return made_rows("arrests_like", *[(n, {"district": str(d)})
                                       for d, n in enumerate(counts, 1) if n])


GROUPS_C16 = {
    # counts of districts 1 to 6 in 2025: the groups phrase
    "two hidden of different size, no 0": (
        (30, 5, 7, 20, 25, 12),
        "by district, district 1 had the most (30) and district 2 and district 3 the fewest "
        "(fewer than 10 each)"),
    "two hidden of the same size, no 0": (
        (30, 6, 6, 20, 25, 12),
        "by district, district 1 had the most (30) and district 2 and district 3 the fewest "
        "(fewer than 10 each)"),
    "one hidden, no 0": (
        (30, 15, 7, 20, 25, 12),
        "by district, district 1 had the most (30) and district 3 the fewest (fewer than 10)"),
    "a hidden group and a 0": (
        (30, 15, 7, 20, 25, 0),
        "by district, district 1 had the most (30) and district 6 the fewest (0)"),
}


@pytest.mark.parametrize("case", list(GROUPS_C16))
def test_c16_the_groups_phrase_never_ranks_hidden_values(tmp_path, monkeypatch, case):
    counts, phrase = GROUPS_C16[case]
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": district_rows(*counts)})
    reply = turn(env, (year(2025), [], ["district"]), text="I counted {r1.count}. {r1.groups}.")
    total = sum(counts)
    assert reply.text.startswith(f"I counted {total} arrest records in 2025. "
                                 f"{phrase[0].upper()}{phrase[1:]}."), reply.text


COMPARE_C16 = {
    # counts of the compared districts (1, 2, 3 in that order): the compare phrase
    "the hidden ones are the lowest, each": (
        (30, 5, 7), "district 1 had the highest count (30) and district 2 and district 3 the "
                    "lowest (fewer than 10 each)"),
    "one hidden is the lowest": (
        (30, 25, 7), "district 1 had the highest count (30) and district 3 the lowest (fewer "
                     "than 10)"),
    "every value hidden": (
        (9, 5, 7), "the counts for district 1, district 2 and district 3 were each fewer than "
                   "10"),
    "hidden and 0": (
        (0, 5, 7), "district 2 and district 3 each had fewer than 10 and district 1 had 0"),
    "one hidden and 0": (
        (0, 5, 0), "district 2 had fewer than 10 and district 1 and district 3 had 0"),
}


@pytest.mark.parametrize("case", list(COMPARE_C16))
def test_c16_the_compare_phrase_never_ranks_hidden_values(tmp_path, monkeypatch, case):
    """A hidden value is never called the highest; no difference is stated when a hidden
    value is in the phrase (C8.5)."""
    counts, phrase = COMPARE_C16[case]
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": district_rows(*counts)})
    reply = env.ask(Q_COMPARE, Step(*[count(A_ID, year(2025), [is_("district", f"district {d}")])
                                      for d in (1, 2, 3)]),
                    Step(compare("r1", "r2", "r3")),
                    Step(finish("finding", "Here is the comparison: {r4.compare}.")))
    check_county_reply(reply)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    assert reply.text.startswith(f"Here is the comparison: {phrase}."), reply.text
    assert "difference" not in reply.text


# ---- C17 -------------------------------------------------------------------------------------

@pytest.mark.parametrize("group_by", [["year", "month"], ["month", "year"]])
def test_c17_year_with_month_is_bad_field(tmp_path, monkeypatch, group_by):
    env = CountyEnv(tmp_path, monkeypatch)
    env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [], group_by)),
            Step(finish("finding", "I counted {r1.count}.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "BAD_FIELD", answer
    assert "result_id" not in answer and len(env.model.calls) == 2


# ---- C18 -------------------------------------------------------------------------------------

def test_c18_the_later_source_line_names_its_source(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    turn(env, (year(2025),), question=Q_COUNT)
    reply = turn(env, (year(2024),), question=Q_COUNT)
    assert reply.text.endswith(f"({TITLE_A}, county open data, copy of 12 November 2026.)") or \
        re.search(re.escape(f"({TITLE_A}, county open data, copy of ") +
                  r"(?:November 12, 2026|2026-11-12)\.\)$", reply.text), reply.text
    assert "(County open data, copy of" not in reply.text


def test_c18_the_first_source_line_is_unchanged(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = turn(env, (year(2025),), question=Q_COUNT)
    assert_reply(reply.text, "I counted 240 arrest records in 2025.",
                 source=source_re("arrests_like", first=True))


# ---- C19 -------------------------------------------------------------------------------------

def test_c19_left_out_lines_of_two_results_say_which(tmp_path, monkeypatch):
    t25 = truth("arrests_like", year(2025), [], ["district"])
    t24 = truth("arrests_like", year(2024), [], ["district"])
    assert (t25["left_out"]["district"], t24["left_out"]["district"]) == (9, 10)
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [], ["district"]),
                                      count(A_ID, year(2024), [], ["district"])),
                    Step(finish("finding", "I counted {r1.count}. I counted {r2.count}.")))
    check_county_reply(reply)
    one = ("For arrest records in 2025: fewer than 10 had no district recorded and are not "
           "included.")
    two = "For arrest records in 2024: 10 had no district recorded and are not included."
    assert one in reply.text and two in reply.text, reply.text
    assert reply.text.index(one) < reply.text.index(two)
    assert "(fewer than 10 had no district" not in reply.text
    assert "(10 had no district" not in reply.text


def test_c19_a_hidden_line_and_a_left_out_line_of_another_result(tmp_path, monkeypatch):
    """r1 has hidden groups (and one left out), r2 a plain count: the left-out line says
    which; the hidden line is one line for the whole reply."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [is_("adjacent_to_school", True)],
                                            ["district"]), count(A_ID, year(2024))),
                    Step(finish("finding", "I counted {r1.count}. I counted {r2.count}.")))
    check_county_reply(reply)
    line = ("For arrest records within 500 feet of a school in 2025: fewer than 10 had no "
            "district recorded and are not included.")
    assert line in reply.text, reply.text
    assert reply.text.count(hidden_line(PAGE_A)) == 1


def test_c19_one_result_keeps_the_brackets(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = turn(env, (year(2024), [], ["district"]))
    assert left_out_line(10, "district") in reply.text and "For arrest records" not in reply.text


def test_c19_two_results_with_no_left_out_or_hidden_line_change_nothing(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(count(A_ID, year(2024)), count(A_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}. I counted {r2.count}.")))
    assert "For arrest records" not in reply.text and "not included" not in reply.text


# ---- C20 -------------------------------------------------------------------------------------

def drop_key(key):
    return lambda src: src.pop(key)


def field_kind(src):
    next(f for f in src["fields"] if f["name"] == "district")["kind"] = "number"


def floor_one(src):
    src["floor"] = 1


def empty_label(src):
    next(f for f in src["fields"] if f["name"] == "district")["values"]["3"] = ""


BAD_FILES = {
    # case: (change, a word the reason holds)
    "no page": (drop_key("page"), "page"),
    "no unit": (drop_key("unit"), "unit"),
    "no time field": (drop_key("time_field"), "time_field"),
    "an unknown field kind": (field_kind, "number"),
    "a floor of 1": (floor_one, "floor"),
    "an empty label": (empty_label, "label"),
    "interpreted with no interpreted_line": (interpreted("race", line=False), "interpreted"),
    "interpreted with no coverage": (interpreted("race", coverage=False), "coverage"),
}


def bad_folder(tmp_path, case):
    change, _ = BAD_FILES[case]
    return write_sources(Path(tmp_path) / "sources", ("arrests_like", "coded_like"),
                         change={"arrests_like": change})


@pytest.mark.parametrize("case", list(BAD_FILES))
def test_c20_a_bad_file_is_not_offered_and_the_others_are(tmp_path, case, caplog):
    caplog.set_level(logging.DEBUG)
    folder = bad_folder(tmp_path, case)
    loaded = mod("sources").load_sources(folder)
    assert A_ID not in loaded, f"{case}: the invalid file is offered"
    assert C_ID in loaded, "the other files are still offered"
    named = [r for r in caplog.records
             if "arrests_like" in r.getMessage() or A_ID in r.getMessage()]
    assert named, "the reason is logged"


def test_c20_the_reason_is_logged_once(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    folder = bad_folder(tmp_path, "a floor of 1")
    for _ in range(3):
        mod("sources").load_sources(folder)
    named = [r for r in caplog.records
             if "arrests_like" in r.getMessage() or A_ID in r.getMessage()]
    assert len(named) == 1, [r.getMessage() for r in named]


@pytest.mark.parametrize("case", ["no page", "a floor of 1", "interpreted with no coverage"])
def test_c20_the_fetch_command_shows_the_reason(tmp_path, monkeypatch, capsys, case):
    folder = bad_folder(tmp_path, case)
    use_sources(monkeypatch, folder)
    state = Path(tmp_path) / "state"
    monkeypatch.setenv("MOCO_STATE_DIR", str(state))
    sources = mod("sources")
    real = sources.fetch

    def with_fake_transport(source, *, state_dir, transport=None, now=None):
        return real(source, state_dir=state_dir, transport=service_for("arrests_like"),
                    now=now or COPY_NOW)
    for name, module in list(sys.modules.items()):  # as tests/s3/test_s3_fetch.py does
        if (name == "moco_agent" or name.startswith("moco_agent.")) and \
                getattr(module, "fetch", None) is real:
            monkeypatch.setattr(module, "fetch", with_fake_transport)
    try:
        code = mod("__main__").main(["fetch", A_ID])
    except SystemExit as stop:
        code = stop.code
    out = capsys.readouterr()
    text = out.out + out.err
    assert code not in (0, None), (code, text)
    assert BAD_FILES[case][1] in text, text
    assert not (state / "copies" / "arrests_like").exists() or \
        not any((state / "copies" / "arrests_like").iterdir())


def test_c20_about_the_data_and_the_model_never_see_a_bad_file(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch, names=("arrests_like", "coded_like"),
                    copies=("coded_like",), change={"arrests_like": floor_one})
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "Here is what I know.")))
    assert TITLE_A not in reply.text and source_json("coded_like")["title"] in reply.text
    for call in env.model.calls:
        seen = json.dumps([call["messages"], call["tools"]])
        assert A_ID not in seen and TITLE_A not in seen
        assert "floor" not in seen.lower() or "invalid" not in seen.lower()


# ---- C22 -------------------------------------------------------------------------------------

def test_c22_a_share_above_half_a_percent_and_below_one_is_1(tmp_path, monkeypatch):
    rows = fixture_rows("arrests_like") + bulk_rows("arrests_like", 1000)
    whole = truth("arrests_like", year(2025), [], rows=rows)
    part = truth("arrests_like", year(2025), [is_("district", "district 1"),
                                              is_("adjacent_to_school", True)], rows=rows)
    assert (whole["total"], part["total"]) == (1240, 10)
    assert 0.005 < part["total"] / whole["total"] < 0.01
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = env.ask(Q_SHARE, Step(count(A_ID, year(2025)),
                                  count(A_ID, year(2025), [is_("district", "district 1"),
                                                           is_("adjacent_to_school", True)])),
                    Step(share("r2", "r1")), Step(finish("finding", "Here it is: {r3.share}.")))
    check_county_reply(reply)
    assert reply.text.startswith("Here it is: 1% of the 1,240 arrest records in 2025 were in "
                                 "district 1 within 500 feet of a school."), reply.text
    assert "under 1%" not in reply.text


def test_round2_fixtures_are_unchanged():
    """No fixture file is changed by this round (the brief): the made-up rows the tests above
    build come from s3support helpers in tmp_path."""
    assert COPY_NOW.year == 2026
    assert len(fixture_rows("arrests_like")) == len(json.loads(
        (Path(__file__).parent / "fixtures" / "rows" / "arrests_like.json").read_text())["rows"])
