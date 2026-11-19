"""Brief point 8, second part: `details` (docs/P1A-DESIGN.md A10, and A4 step 2), and
revision 2's R3 (docs/P1A-R2-DESIGN.md): show_details in a turn that already has a result
is read as "send the answer": ANSWERED with the fixed rendering and DETAILS_THIS_TURN.

An earlier turn is answered through agent.handle_question with a FakeModel (p1support.Env);
then "details" (Python, no model call) or the show_details tool must give A10's text,
line by line, from the saved records in the Env's runs folder in tmp_path. Numbers come
from the truth file; the limitations are read from the count's saved manifest.json.

Accepted both ways (the design allows either; kit-log/raw/P1A-A-notes.txt):
- A number of 1,000 or more may have its comma or not (A7 fixes the comma for fill only).
- `Run ids:` may separate the ids with "," or ", ", and may list them in either order (A10
  gives no order).
- The compare sentence's first letter may be a capital or not.
- With more than four counts only the number of `Read as:` lines is checked (exactly four),
  not which four, and not the run ids line.

- R3's ANSWERED reply, as for A7's other fixed renderings that no finish produced
  (kit-log/raw/P1A-A-notes.txt): reply_style `fallback` or `fixed`, reason_code None or
  DETAILS_THIS_TURN, reply_kind `finding` or None. DETAILS_THIS_TURN must be in
  draft_failures.

Cannot check here: which saved file `details` reads (manifest.json, turn.json or both);
the tests delete or spoil both.
"""
import itertools
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from p1support import (DETAILS_HEAD, DM_KEY, MONTH_ABBREVIATIONS, NOW, ONE_COUNT_TEXT,
                       THREAD_2, Env, Step, age_wording, assert_answered, assert_fixed,
                       check_reply, compare, compare_expect, compare_sentence_re, count,
                       decline, fixed_line1_re, kept_note, months, n_re, registry_source,
                       show_details)
from support import REFUSED, SUPPORTED

Q_COUNT = SUPPORTED["S1"][0]
Q_COMPARE = "Compare 2024 and 2025 for people under 18."
Q_SHOW = "Can you show me the months behind that answer?"  # no guard rule matches it


def manifest_of(runs_dir, run_id):
    return json.loads((Path(runs_dir) / run_id / "manifest.json").read_text(encoding="utf-8"))


def run_for(runs_dir, run_ids, year, group):
    """The run id, among run_ids, whose saved record counted this year and age group."""
    (found,) = [r for r in run_ids
                if manifest_of(runs_dir, r)["filters"] == {"year": year, "age_group": group}]
    return found


def read_as(year, group):
    return re.escape(f"Read as: arrest records per month in {year}, {age_wording(group)}.")


def by_month(year, group):
    values = months(year, group)
    listed = ", ".join(f"{abbr} {n_re(v)}" for abbr, v in zip(MONTH_ABBREVIATIONS, values))
    return f"By month: {listed}\\. Total {n_re(sum(values))}\\."


def details_re(runs_dir, answer, counts, compares=()):
    """A10's text, as a regex, for an earlier answer whose count results were `counts`
    [(year, group or None)] in result order, and whose compare results were `compares`
    (dicts from compare_expect)."""
    assert len(answer.run_ids) == len(counts), answer.run_ids
    run_ids = [run_for(runs_dir, answer.run_ids, y, g) for y, g in counts]
    limitations = manifest_of(runs_dir, run_ids[0])["limitations"]
    assert limitations, "the first count's saved record has no limitation"
    lines = [re.escape(DETAILS_HEAD)]
    for year, group in counts:
        lines += [read_as(year, group), by_month(year, group)]
    lines += ["Compared: " + compare_sentence_re(c) for c in compares]
    lines.append(re.escape(f"Data: {registry_source()['id']}, SYNTHETIC (made-up) test data, "
                           f"not real Montgomery County figures."))
    lines.append(re.escape("Limits:"))
    lines += [re.escape(f"- {sentence}") for sentence in limitations]
    orders = ["(?:,[ ]?)".join(re.escape(r) for r in order)
              for order in itertools.permutations(run_ids)]
    lines.append("Run ids: (?:" + "|".join(orders) + ")")
    return "\n".join(lines)


def assert_details(reply, pattern):
    assert (reply.status, reply.reason_code) == ("DETAILS", None), (reply.status,
                                                                     reply.reason_code)
    assert re.fullmatch(pattern, reply.text), f"not A10's details text:\n{reply.text}"


@pytest.mark.parametrize("year, group", [(2025, "18_25"), (2024, None)],
                         ids=["18_25", "all_ages"])
def test_details_after_one_count_is_a10s_text(year, group, tmp_path):
    """A10 for one count; A4 step 2: no model call. All ages read "all ages"."""
    env = Env(tmp_path)
    answer = env.answered(Q_COUNT, (year, group))
    reply = env.ask("details")
    check_reply(reply, env.model)
    assert env.model.calls == [] and reply.model_called is False
    assert_details(reply, details_re(env.runs_dir, answer, [(year, group)]))


@pytest.mark.parametrize("word", ["details", "Details", "DETAIL", "more", "More Details",
                                  "details?", "detail.", "more!", "more details?"])
def test_each_details_word_gives_details_without_the_model(word, tmp_path):
    """A4 step 2: exactly details, detail, more or more details, any letter case, a final
    ?, . or ! ignored."""
    env = Env(tmp_path)
    answer = env.answered(Q_COUNT, (2025, "18_25"))
    reply = env.ask(word)
    assert env.model.calls == [], word
    assert_details(reply, details_re(env.runs_dir, answer, [(2025, "18_25")]))


def test_a_longer_text_is_not_the_details_word(tmp_path):
    """A4 step 2 says "exactly": other text goes to the model."""
    env = Env(tmp_path)
    reply = env.ask("more details on 2024")
    assert env.model.calls, "the model was not called"
    assert reply.status != "DETAILS"


def test_details_after_a_comparison(tmp_path):
    """A10: each count's two lines in order, then `Compared:` with render_fixed's compare
    sentence; the limits of the first count's record; both run ids."""
    env = Env(tmp_path)
    answer = env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True)
    reply = env.ask("details")
    check_reply(reply, env.model)
    counts = [(2024, "under_18"), (2025, "under_18")]
    expect = compare_expect([(y, g, sum(months(y, g))) for y, g in counts])
    assert_details(reply, details_re(env.runs_dir, answer, counts, [expect]))


def test_details_shows_at_most_four_counts(tmp_path):
    """A10: for each count result, at most four."""
    env = Env(tmp_path)
    counts = [(2024, None), (2024, "under_18"), (2024, "18_25"), (2024, "26_40"),
              (2024, "41_plus")]
    env.answered("Arrests per month in 2024 for every age group", *counts,
                 text=ONE_COUNT_TEXT)
    reply = env.ask("details")
    assert reply.status == "DETAILS", (reply.status, reply.reason_code, reply.text)
    lines = reply.text.split("\n")
    assert lines[0] == DETAILS_HEAD
    read_lines = [line for line in lines if line.startswith("Read as:")]
    assert len(read_lines) == 4, read_lines
    assert len([line for line in lines if line.startswith("By month:")]) == 4
    allowed = [read_as(y, g) for y, g in counts]
    assert all(any(re.fullmatch(p, line) for p in allowed) for line in read_lines), read_lines


def test_the_show_details_tool_gives_the_same_text(tmp_path):
    """A3: show_details ends the turn with the details text (A10)."""
    env = Env(tmp_path)
    answer = env.answered(Q_COUNT, (2025, "18_25"))
    reply = env.ask(Q_SHOW, Step(show_details()))
    check_reply(reply, env.model)
    assert len(env.model.calls) == 1
    assert_details(reply, details_re(env.runs_dir, answer, [(2025, "18_25")]))


@pytest.mark.parametrize("how", ["word", "tool", "answer_in_another_thread"])
def test_no_earlier_answer_gives_no_previous_answer(how, tmp_path):
    """A10: no earlier turn of the thread with results: UNSUPPORTED / NO_PREVIOUS_ANSWER."""
    env = Env(tmp_path)
    if how == "answer_in_another_thread":
        env.answered(Q_COUNT, (2025, "18_25"), thread_key=THREAD_2)
    if how == "tool":
        reply = env.ask(Q_SHOW, Step(show_details()))
    else:
        reply = env.ask("details")
        assert env.model.calls == []
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NO_PREVIOUS_ANSWER")
    assert_fixed(reply.text, "NO_PREVIOUS_ANSWER")


def delete_every_file(runs_dir):
    files = [p for p in Path(runs_dir).rglob("*") if p.is_file()]
    assert files
    for path in files:
        path.unlink()


def spoil_every_record(runs_dir):
    records = [p for name in ("manifest.json", "turn.json")
               for p in Path(runs_dir).rglob(name)]
    assert {p.name for p in records} == {"manifest.json", "turn.json"}, records
    for path in records:
        path.write_text("not a record {", encoding="utf-8")


@pytest.mark.parametrize("damage", [delete_every_file, spoil_every_record],
                         ids=["deleted", "unreadable"])
def test_a_missing_or_unreadable_record_gives_record_not_found(damage, tmp_path):
    """A10: a saved record missing or unreadable: ERROR / RECORD_NOT_FOUND."""
    env = Env(tmp_path)
    env.answered(Q_COUNT, (2025, "18_25"))
    damage(env.runs_dir)
    reply = env.ask("details")
    check_reply(reply, env.model)
    assert (reply.status, reply.reason_code) == ("ERROR", "RECORD_NOT_FOUND")
    assert_fixed(reply.text, "RECORD_NOT_FOUND")


def test_details_has_no_time_limit(tmp_path):
    """A10: "no time limit": an answer two hours old, with memory_minutes 60."""
    env = Env(tmp_path)
    answer = env.answered(Q_COUNT, (2025, "18_25"), thread_key=DM_KEY, memory_minutes=60,
                          now=NOW)
    reply = env.ask("details", thread_key=DM_KEY, memory_minutes=60,
                    now=NOW + timedelta(hours=2))
    assert_details(reply, details_re(env.runs_dir, answer, [(2025, "18_25")]))


@pytest.mark.parametrize("how", ["word", "tool"])
def test_details_are_of_the_most_recent_answer(how, tmp_path):
    """A10: "the most recent earlier turn of the thread that has results": with two earlier
    answers, only the newer one's counts and run id are shown."""
    env = Env(tmp_path)
    env.answered(Q_COUNT, (2025, "18_25"))
    answer = env.answered(SUPPORTED["S2"][0], (2024, None))
    reply = env.ask(Q_SHOW, Step(show_details())) if how == "tool" else env.ask("details")
    check_reply(reply, env.model)
    assert_details(reply, details_re(env.runs_dir, answer, [(2024, None)]))


@pytest.mark.parametrize("between", ["refused", "details"])
def test_a_later_turn_without_results_does_not_hide_the_answer(between, tmp_path):
    """A10: the most recent earlier turn that has results."""
    env = Env(tmp_path)
    answer = env.answered(Q_COUNT, (2025, "18_25"))
    if between == "refused":
        refused = env.ask(REFUSED["U1"][0], Step(decline("UNSUPPORTED_METRIC")))
        assert refused.status == "UNSUPPORTED", (refused.status, refused.reason_code)
    else:
        assert env.ask("details").status == "DETAILS"
    reply = env.ask("details")
    assert_details(reply, details_re(env.runs_dir, answer, [(2025, "18_25")]))


# ---- R3: show_details in a turn that already has a result ------------------------------

def check_details_this_turn(reply, model, counts, compares=(), *, kept="", first):
    """R3: ANSWERED with this turn's fixed rendering (A7, with the kept note and line 2) and
    DETAILS_THIS_TURN among the failure codes; not A10's details text."""
    check_reply(reply, model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert "DETAILS_THIS_TURN" in reply.draft_failures, reply.draft_failures
    assert reply.reason_code in (None, "DETAILS_THIS_TURN"), reply.reason_code
    assert reply.reply_style in ("fallback", "fixed"), reply.reply_style
    assert reply.reply_kind in ("finding", None), reply.reply_kind
    assert DETAILS_HEAD not in reply.text
    assert_answered(reply.text, fixed_line1_re(counts, compares), kept=kept, first=first)


@pytest.mark.parametrize("same_step", [False, True], ids=["next_step", "same_step"])
def test_show_details_after_counting_in_a_fresh_thread_sends_the_answer(same_step, tmp_path):
    """R3 (the chat check's live case): a fresh question is counted, then show_details,
    in the next step or in the same step after the count: the answer is sent, not "There's
    no answer in this conversation to give details on yet." """
    env = Env(tmp_path)
    steps = ([Step(count(2025, "18_25"), show_details())] if same_step
             else [Step(count(2025, "18_25")), Step(show_details())])
    reply = env.ask(Q_COUNT, *steps)
    check_details_this_turn(reply, env.model, [(2025, "18_25")], first=True)
    assert len(env.model.calls) == len(steps)
    assert len(reply.run_ids) == 1


def test_show_details_after_counting_answers_this_turn_not_the_earlier_answer(tmp_path):
    """R3: with an earlier answer in the thread, a turn that counts (the year kept from
    that answer) and then calls show_details sends its own answer, with the kept note and
    the later line 2; A10 is not used."""
    env = Env(tmp_path)
    env.answered(Q_COUNT, (2025, "18_25"))
    reply = env.ask("and for people under 18?", Step(count(None, "under_18")),
                    Step(show_details()))
    check_details_this_turn(reply, env.model, [(2025, "under_18")], kept=kept_note(2025),
                            first=False)


def test_show_details_after_two_counts_and_a_compare_sends_their_fixed_rendering(tmp_path):
    """R3: the fixed rendering of every result of this turn (A7: two counts and the compare
    sentence)."""
    env = Env(tmp_path)
    counts = [(2024, "under_18"), (2025, "under_18")]
    reply = env.ask(Q_COMPARE, Step(*[count(y, g) for y, g in counts]),
                    Step(compare("r1", "r2")), Step(show_details()))
    c = compare_expect([(y, g, sum(months(y, g))) for y, g in counts])
    check_details_this_turn(reply, env.model, counts, [c], first=True)


def test_details_after_such_a_turn_are_of_its_results(tmp_path):
    """R3 and A10: that turn is ANSWERED with its result, so the next "details" gives the
    details of its count."""
    env = Env(tmp_path)
    answer = env.ask(Q_COUNT, Step(count(2025, "26_40")), Step(show_details()))
    assert answer.status == "ANSWERED", (answer.status, answer.reason_code, answer.text)
    reply = env.ask("details")
    check_reply(reply, env.model)
    assert_details(reply, details_re(env.runs_dir, answer, [(2025, "26_40")]))


def test_show_details_after_a_count_that_made_no_result_is_a10_as_before(tmp_path):
    """R3: "With no result in this turn, A10 applies as before": a count that answered
    OUT_OF_COVERAGE made no result, so show_details gives the earlier answer's details."""
    env = Env(tmp_path)
    answer = env.answered(Q_COUNT, (2025, "18_25"))
    reply = env.ask(Q_SHOW, Step(count(2019, "all")), Step(show_details()))
    check_reply(reply, env.model)
    assert_details(reply, details_re(env.runs_dir, answer, [(2025, "18_25")]))
