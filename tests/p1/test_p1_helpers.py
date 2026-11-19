"""Checks on the stage 2 tests' own helpers and guards (tests/p1/p1support.py and
conftest.py). These need no moco_agent, so they run now and show that the guards, matchers
and fakes do what they claim, and that the helpers that write the design's fixed wording
give the design's own examples (docs/P1A-DESIGN.md A6, A7, A13).

Expected numbers come from the truth file (months, all_totals); the design's example
sentences are quoted from the design and checked against helpers fed made-up values (or a
registry copy with made-up wordings), so the helper is checked and not the data.
FakeModel needs moco_agent.llm, so it is not checked here.
"""
import re
import socket
from collections import Counter

import pytest

from p1support import (CHATTER, DATA_TAG, FAKE_SECRETS, HELP_LINE, LINE2_FIRST, LINE2_LATER,
                       FakeAgent, FakeSlack, FakeTimer, age_wording, all_totals,
                       assert_no_secret, can_ask, changed_data, chart_title, compare_expect,
                       fixed_parts, groups_wording, join_and, months, months_sentence, n_re,
                       number_in, numbers_in, registry_json, years_wording)
from support import COLUMNS, load_truth, read_rows


def test_the_network_is_blocked_and_recorded(_stage2_guards):
    with pytest.raises(RuntimeError, match="network use is blocked"):
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    with pytest.raises(RuntimeError, match="network use is blocked"):
        socket.getaddrinfo("example.invalid", 443)
    assert len(_stage2_guards) == 2  # recorded, so a caught attempt still fails a test
    _stage2_guards.clear()          # this test made them on purpose


def test_no_real_settings_are_visible(tmp_path_factory):
    """No real NVIDIA_/SLACK_ variable; MOCO_ENV_FILE is an empty file; "~" is inside
    pytest's temporary folder, so ~/.config/... cannot reach the real secrets file."""
    import os
    from pathlib import Path
    assert not any(k.startswith(("NVIDIA_", "SLACK_", "OPENAI_")) for k in os.environ)
    assert Path(os.environ["MOCO_ENV_FILE"]).read_text() == ""
    base = tmp_path_factory.getbasetemp().resolve()
    assert Path.home().resolve().is_relative_to(base)
    assert Path(os.environ["MOCO_ENV_FILE"]).resolve().is_relative_to(base)


@pytest.mark.parametrize("form, text, found", [
    ("400", "a total of 400.", True),
    ("400", "(400)", True),
    ("400", "run 20261110T150000Z-ab400cd1", False),  # inside a run id
    ("400", "1,400 records", False),
    ("400", "4000", False),
    ("400", "400.5", False),
    ("1,393", "1,393 records", True),
    ("7777", "says 7777.", True),
    ("50", "500 characters", False),
])
def test_number_in(form, text, found):
    assert number_in(form, text) is found


def test_the_fake_model_chatter_number_is_not_a_count_from_the_data():
    assert 7777 not in all_totals() and "7777" in CHATTER


def test_no_total_collides_with_numbers_a_reply_may_hold():
    """Years, the question limits used in the tests: none is a total from the data."""
    assert not all_totals() & {2024, 2025, 2030, 2031, 500, 80, 200, 1500}


@pytest.mark.parametrize("shown", ["whole", "start", "last_3", "first_3_of_tail"])
@pytest.mark.parametrize("key", FAKE_SECRETS)
def test_assert_no_secret_catches_a_value_and_any_part(key, shown):
    value = FAKE_SECRETS[key]
    text = {"whole": value, "start": value[:12] + "...", "last_3": "..." + value[-3:],
            "first_3_of_tail": value[len("test-key-not-real-"):][:3] + "..."}[shown]
    with pytest.raises(AssertionError):
        assert_no_secret(f"{key.lower()}={text}")


def test_assert_no_secret_lets_honest_text_through():
    assert_no_secret("NVIDIA_API_KEY=set SLACK_BOT_TOKEN=missing SLACK_APP_TOKEN=set "
                     "nvidia_model=nvidia/nemotron-3.5-lightning-30b-a3b run 20261110T150000Z-ab12cd34")


def test_fake_slack_keeps_one_ordered_log():
    """A13: post_message(channel, thread_ts, text) and upload_file(channel, thread_ts, path,
    title, comment), by position or keyword, in one log shared with a FakeAgent."""
    log = []
    slack = FakeSlack(log=log)
    agent = FakeAgent(reply="the reply", log=log)
    slack.post_message("C1", "1.0", "first")
    agent("a question", "T:C1:1.0", "U1")
    slack.upload_file(channel="C1", thread_ts="1.0", path="chart.png", title="t",
                      comment="the reply")
    slack.upload_file("C1", None, "chart-2.png", "t2", "the reply 2")
    slack.post_message(channel="C1", thread_ts=None, text="second")
    assert [e[0] for e in slack.log] == ["post", "agent", "upload", "upload", "post"]
    assert [p[3] for p in slack.posts] == ["first", "second"]
    assert slack.uploads == [("upload", "C1", "1.0", "chart.png", "t", "the reply"),
                             ("upload", "C1", None, "chart-2.png", "t2", "the reply 2")]


def test_fake_slack_upload_error_is_raised_after_the_upload_is_recorded():
    slack = FakeSlack(upload_error=OSError("upload refused"))
    with pytest.raises(OSError):
        slack.upload_file("C1", "1.0", "chart.png", "t", "the reply")
    assert slack.uploads == [("upload", "C1", "1.0", "chart.png", "t", "the reply")]


def test_fake_timer_fire_runs_the_function_even_after_cancel():
    """A13 step 8: start_timer(seconds, function) returns something with cancel(). The fake
    runs nothing by itself; fire() runs the function, cancelled or not (a real timer can
    fire at the moment it is cancelled)."""
    timer = FakeTimer()
    ran = []
    handle = timer(3, lambda: ran.append("fired"))
    assert timer.handles == [handle] and handle.seconds == 3
    assert ran == [] and handle.cancelled is False
    handle.cancel()
    assert handle.cancelled is True and ran == []
    handle.fire()
    assert ran == ["fired"]


def test_fake_agent_records_memory_minutes_by_keyword_or_position():
    """A13: agent(question, thread_key, user_id, memory_minutes=None) -> AgentReply."""
    reply = object()
    agent = FakeAgent(reply)
    assert agent("q1", "K1", "U1") is reply
    assert agent("q2", "K2", "U2", 60) is reply
    assert agent("q3", "K3", "U3", memory_minutes=45) is reply
    assert agent.memory_minutes == [None, 60, 45]
    assert agent.calls == [("q1", "K1", "U1"), ("q2", "K2", "U2"), ("q3", "K3", "U3")]


def test_fake_agent_raises_its_error_after_recording_the_call():
    agent = FakeAgent(error=RuntimeError("agent failed"))
    with pytest.raises(RuntimeError):
        agent("q", "K", "U", 30)
    assert agent.calls == [("q", "K", "U")] and agent.memory_minutes == [30]


# ---- the fixed wording helpers against the design's own examples (A6, A7) ---------------

# Twelve made-up monthly values that reproduce A7's example sentence (not the data's: the
# helper is checked, not the data, so a new synthetic data file cannot break these).
DESIGN_EXAMPLE_VALUES = [8, 20, 30, 50, 21, 22, 23, 8, 24, 25, 26, 27]


def test_months_sentence_gives_the_design_example():
    """A7's example sentence, quoted from the design, from made-up values."""
    design_example = ("April was the busiest month (50) and January and August the quietest "
                      "(8 each).")
    assert months_sentence(DESIGN_EXAMPLE_VALUES) == design_example


@pytest.mark.parametrize("tied, names", [
    ([11], "April and December"),
    ([5, 11], "April, June and December"),
])
def test_months_sentence_with_a_tie_for_the_busiest(tied, names):
    """A7: months that tie are listed in calendar order, the verb becomes `were`, `month`
    becomes `months` for the busiest, and the number is followed by ` each`."""
    values = list(DESIGN_EXAMPLE_VALUES)
    high, low = max(values), min(values)
    for i in tied:
        values[i] = high
    assert months_sentence(values) == (f"{names} were the busiest months ({high} each) and "
                                       f"January and August the quietest ({low} each).")


def test_months_sentence_when_every_month_is_equal():
    value = months(2025, "under_18")[0]
    assert months_sentence([value] * 12) == f"Every month had the same count ({value})."


@pytest.mark.parametrize("items, joined", [
    (["A"], "A"),
    (["A", "B"], "A and B"),
    (["A", "B", "C"], "A, B and C"),
    ([2024, 2025], "2024 and 2025"),
])
def test_join_and(items, joined):
    """A6 and A7: `A and B`, or `A, B and C`."""
    assert join_and(items) == joined


@pytest.mark.parametrize("end, wording", [
    ("2024-12-31", "2024"),
    ("2025-12-31", "2024 or 2025"),
    ("2027-12-31", "2024 to 2027"),
])
def test_years_wording_gives_the_design_examples(end, wording):
    """A7: `<years>` from the registry's coverage: `2024`; `2024 or 2025`; `2024 to 2027`."""
    data = registry_json()
    data["approved_sources"][0]["coverage"].update(start="2024-01-01", end=end)
    assert years_wording(data) == wording
    assert f"for {wording}, for all ages" in can_ask(data)


def test_groups_wording_joins_the_registry_wordings_as_the_design_example_does():
    """A7: `<groups>` is the registry's wordings joined in order, as in the design's example
    `people under 18, ages 18 to 25, ages 26 to 40, or ages 41 and over`. Checked on a copy
    of the registry with made-up wordings, so a reworded group does not break it."""
    data = registry_json()
    data["approved_sources"][0]["age_groups"] = {"g1": "alpha", "g2": "beta", "g3": "gamma",
                                                 "g4": "delta"}
    assert groups_wording(data) == "alpha, beta, gamma, or delta"


# The codes fixed_parts knows (A7's table, ABOUT, the background refusal, A10's two).
FIXED_CODES = ["REAL_DATA_NOT_AVAILABLE", "UNSUPPORTED_METRIC", "UNSUPPORTED_FIELD",
               "UNRECOGNIZED_QUESTION", "OUT_OF_COVERAGE", "INVALID_ARGUMENTS", "INPUT_TOO_LONG",
               "NEEDS_year", "NEEDS_age_group", "NEEDS_other", "MODEL_UNAVAILABLE",
               "MODEL_BAD_OUTPUT", "RATE_LIMITED", "DATA_CLASS_MISMATCH", "DATA_UNREADABLE",
               "ABOUT", "BACKGROUND_OFF", "NO_PREVIOUS_ANSWER", "RECORD_NOT_FOUND"]
# The rows of A7 that hold CAN_ASK (`+ CAN_ASK`, or `<CAN_ASK>` in ABOUT).
WITH_CAN_ASK = {"REAL_DATA_NOT_AVAILABLE", "UNSUPPORTED_METRIC", "UNSUPPORTED_FIELD",
                "UNRECOGNIZED_QUESTION", "OUT_OF_COVERAGE", "INVALID_ARGUMENTS", "NEEDS_other",
                "ABOUT", "BACKGROUND_OFF"}


def test_every_fixed_reply_that_lists_what_can_be_asked_says_synthetic():
    """A0: every list of what can be asked says SYNTHETIC. CAN_ASK itself does not, so every
    part list that holds it must hold SYNTHETIC in another part."""
    holding = set()
    for code in FIXED_CODES:
        parts = fixed_parts(code, limit=500)
        assert all(isinstance(p, str) and p for p in parts), code
        if can_ask() in parts:
            holding.add(code)
            assert "SYNTHETIC" in " ".join(parts), code
    assert holding == WITH_CAN_ASK


@pytest.mark.parametrize("text", [DATA_TAG, LINE2_FIRST, LINE2_LATER, HELP_LINE,
                                  chart_title(2025, "under_18"), chart_title(2024, None)])
def test_the_fixed_lines_of_an_answer_a_chart_and_help_say_synthetic(text):
    """A0: every answer with a number (line 2), every chart and the HELP line say SYNTHETIC."""
    assert "SYNTHETIC" in text


def test_chart_title_gives_the_design_wording():
    """A4: `Arrest records per month, <year>, <age wording or "all ages"> (SYNTHETIC test
    data)`."""
    assert chart_title(2025, "18_25") == (f"Arrest records per month, 2025, "
                                          f"{age_wording('18_25')} (SYNTHETIC test data)")
    assert chart_title(2024, None) == ("Arrest records per month, 2024, all ages "
                                       "(SYNTHETIC test data)")


def test_n_re_writes_a_number_with_or_without_its_comma_from_1000_up():
    """A7 fill: a comma from 1,000 up (render_fixed and details may leave it out, notes)."""
    big = [t for t in all_totals() if t >= 1000]
    small = [t for t in all_totals() if t < 1000] + [250]
    assert big and small
    for n in big:
        assert re.fullmatch(n_re(n), f"{n:,}") and re.fullmatch(n_re(n), str(n)), n
        for wrong in (f"{n:,}".replace(",", "."), f"{n:,}".replace(",", " ")):
            assert not re.fullmatch(n_re(n), wrong), (n, wrong)
    for n in small:
        assert n_re(n) == str(n) and re.fullmatch(n_re(n), str(n)), n
        assert not re.fullmatch(n_re(n), f"0,{n}"), n


def test_numbers_in_ignores_digits_next_to_letters_and_reads_commas():
    """Result ids (r1), tool call ids (call_0_1) and run ids are not numbers."""
    big = max(all_totals())
    text = (f"Result r1 and r12 from call_0_1, run 20261110T150000Z-ab12cd34, "
            f"turn T20261110T150000Z-0a1b2c3d: {big:,} records in 2025.")
    assert numbers_in(text) == {big, 2025}
    assert numbers_in("r1 r2 call_0_1 call_3_0 x9 9x _9 9_") == set()


def test_compare_expect_on_a_tie_for_the_top():
    """A6: when only the age groups differ the label is the age wording; labels that tie
    are joined in the order compared. The totals are the truth file's."""
    high, low = max(all_totals()), min(all_totals())
    got = compare_expect([(2025, "under_18", low), (2025, "18_25", high),
                          (2025, "26_40", high)])
    assert got == {"top_label": f"{age_wording('18_25')} and {age_wording('26_40')}",
                   "top_value": high, "bottom_label": age_wording("under_18"),
                   "bottom_value": low, "difference": high - low, "all_equal": False}


def test_compare_expect_when_all_are_equal():
    """A6: all totals equal: both labels hold every label, difference 0, all_equal true.
    When only the years differ the label is the year."""
    total = min(all_totals())
    got = compare_expect([(2024, None, total), (2025, None, total)])
    assert got == {"top_label": "2024 and 2025", "top_value": total,
                   "bottom_label": "2024 and 2025", "bottom_value": total, "difference": 0,
                   "all_equal": True}
    groups = ["under_18", "18_25", "26_40"]
    got = compare_expect([(2025, g, total) for g in groups])
    assert got["top_label"] == got["bottom_label"] == join_and([age_wording(g) for g in groups])
    assert got["all_equal"] is True and got["difference"] == 0


def test_changed_data_writes_a_synthetic_file_whose_rows_match_its_counts(tmp_path):
    """Every row SYNTHETIC, the real file's columns, and one row per counted record."""
    def change(counts):
        counts["2025-04"]["under_18"] += 2
        counts["2024-01"]["41_plus"] -= 1

    path, counts = changed_data(tmp_path, "changed-1", change)
    truth = load_truth()["counts"]
    assert counts["2025-04"]["under_18"] == truth["2025-04"]["under_18"] + 2
    assert counts["2024-01"]["41_plus"] == truth["2024-01"]["41_plus"] - 1
    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNS)
    rows = read_rows(path)
    assert rows and all(row["data_class"] == "SYNTHETIC" for row in rows)
    assert len({row["arrest_id"] for row in rows}) == len(rows)
    assert all(row["arrest_date"][:7] in counts for row in rows)
    assert Counter((row["arrest_date"][:7], row["age_group"]) for row in rows) == Counter(
        {(month, group): n for month, groups in counts.items()
         for group, n in groups.items() if n})
