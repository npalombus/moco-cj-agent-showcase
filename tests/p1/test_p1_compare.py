"""Point 5: comparing counts (docs/P1A-DESIGN.md A6, with A3's compare tool and A7's fill and
render_fixed; brief P1A-A point 5; answer A2 of briefs/QUESTIONS.md).

What this file covers
- analysis.compare_counts(counts, registry) -> dict, called directly (answer A2): `counts`
  is a list, in compare order, of {"year", "age_group" (a code or None), "total"}; the dict
  has exactly the keys top_label, top_value, bottom_label, bottom_value, difference and
  all_equal. Labels when only the years differ (the year as text), only the age groups
  differ (the registry's wording, "all ages" for None) and both differ ("<year>, <age
  wording>"); a tie for the top and for the bottom, two and three tied, joined "A and B" or
  "A, B and C" in compare order; all equal (both labels hold every label, difference 0,
  all_equal True); the difference is the highest minus the lowest; 2 and 8 counts.
  Here, and only here, totals are made up and typed in, as direct input to compare_counts
  (answer A2: ties and all-equal cannot be reached from the truth file's numbers).
  Expectations are built with p1support.compare_expect.
- The compare tool through agent.handle_question with a FakeModel, on the truth file's
  numbers: 2024 against 2025 for people under 18, the four age groups of 2025, and a case
  where both differ (2024 all ages against 2025 ages 18 to 25, whose top value is over
  1,000). A passing finish with the compare's fact slot is filled with its whole phrase
  (docs/P1A-R2-DESIGN.md R1: compare_expect's values, a comma from 1,000, the first label
  as the registry writes it, a capital only at a sentence start). With
  MOCO_REPLY_STYLE=fixed, line 1 is render_fixed's: fixed_line1_re(counts,
  [compare_expect(...)]).

Accepted both ways (as in kit-log/raw/P1A-A-notes.txt, through p1support.fixed_line1_re):
render_fixed's numbers of 1,000 and up with or without the comma, and the first letter of
its top label in either case.

Cannot check: whether a real model chooses to compare, or how its wording reads (A16).
Not tested because A6 is silent: what compare_counts does with fewer than 2 or more than 8
counts, or with two counts of the same filters (the compare tool's BAD_COMPARE is A3's).
"""
import re

import pytest

from p1support import (Env, Step, age_wording, assert_answered, check_reply, compare,
                       compare_expect, compare_slots, count, fill_expect, finish,
                       fixed_line1_re, join_and, load_registry, mod, months, registry_copy)
from support import AGE_GROUPS

KEYS = {"top_label", "top_value", "bottom_label", "bottom_value", "difference", "all_equal"}


def compare_counts(counts, registry=None):
    """analysis.compare_counts on (year, age group or None, total) triples, in compare order."""
    analysis = mod("analysis")
    return analysis.compare_counts(
        [{"year": y, "age_group": g, "total": t} for y, g, t in counts],
        registry if registry is not None else load_registry())


def check(counts):
    """compare_counts gives exactly A6's keys and compare_expect's values."""
    got = compare_counts(counts)
    want = compare_expect(counts)
    assert isinstance(got, dict), type(got)
    assert set(got) == KEYS, sorted(got)
    assert got == want, f"\n got: {got}\nwant: {want}"
    assert got["all_equal"] is want["all_equal"], got["all_equal"]
    return got


# ---- analysis.compare_counts with made-up totals (answer A2) ----------------------------

def test_only_years_differ_labels_are_the_years():
    """A6: when only the years differ, the label is the year (`2025`)."""
    got = check([(2024, "under_18", 120), (2025, "under_18", 95)])
    assert (got["top_label"], got["bottom_label"]) == ("2024", "2025")
    got = check([(2025, None, 310), (2024, None, 420)])  # all ages, latest year first
    assert (got["top_label"], got["bottom_label"]) == ("2024", "2025")


def test_only_age_groups_differ_labels_are_the_age_wordings():
    """A6: when only the age groups differ, the age wording (`people under 18`, `all
    ages`)."""
    got = check([(2025, "41_plus", 40), (2025, None, 200), (2025, "under_18", 15)])
    assert got["top_label"] == "all ages"
    assert got["bottom_label"] == age_wording("under_18")
    check([(2024, g, t) for g, t in zip(AGE_GROUPS, (61, 84, 77, 52))])


def test_both_differ_labels_are_year_and_age_wording():
    """A6: when both differ, `<year>, <age wording>`; once the list holds two years and two
    age groups, every label has both, even where two counts share a year."""
    got = check([(2024, "under_18", 30), (2025, None, 210)])
    assert got["top_label"] == "2025, all ages"
    assert got["bottom_label"] == f"2024, {age_wording('under_18')}"
    got = check([(2024, "18_25", 64), (2025, "18_25", 71), (2025, "26_40", 58)])
    assert got["top_label"] == f"2025, {age_wording('18_25')}"
    assert got["bottom_label"] == f"2025, {age_wording('26_40')}"


def test_labels_use_the_wording_of_the_registry_given(tmp_path):
    """A6 and A7: the age wording is the registry's (compare_counts is given the registry);
    "all ages" is A6's own words."""
    wording = "people younger than 18 in a test registry"

    def change(data):
        data["approved_sources"][0]["age_groups"]["under_18"] = wording

    registry = load_registry(registry_copy(tmp_path, change, name="0-registry.json"))
    got = compare_counts([(2025, "under_18", 12), (2025, None, 30)], registry)
    assert (got["top_label"], got["bottom_label"]) == ("all ages", wording)


def test_a_tie_for_the_top_joins_the_labels_in_compare_order():
    """A6: labels that tie are joined (`A and B`, or `A, B and C`) in the order compared,
    not in the registry's order."""
    got = check([(2025, "under_18", 60), (2025, "18_25", 90), (2025, "26_40", 90)])
    assert got["top_label"] == join_and([age_wording("18_25"), age_wording("26_40")])
    got = check([(2025, "41_plus", 70), (2025, "under_18", 20), (2025, "26_40", 70),
                 (2025, "18_25", 70)])
    assert got["top_label"] == (f"{age_wording('41_plus')}, {age_wording('26_40')} and "
                                f"{age_wording('18_25')}")
    assert got["bottom_label"] == age_wording("under_18")
    assert got["all_equal"] is False


def test_a_tie_for_the_bottom_joins_the_labels_in_compare_order():
    """A6: as for the top."""
    got = check([(2025, "under_18", 25), (2025, "18_25", 60), (2025, "41_plus", 25)])
    assert got["bottom_label"] == f"{age_wording('under_18')} and {age_wording('41_plus')}"
    got = check([(2025, None, 300), (2025, "26_40", 40), (2025, "under_18", 40),
                 (2025, "18_25", 40)])
    assert got["bottom_label"] == (f"{age_wording('26_40')}, {age_wording('under_18')} and "
                                   f"{age_wording('18_25')}")
    assert got["top_label"] == "all ages"


def test_ties_at_both_ends():
    got = check([(2024, "under_18", 50), (2024, "18_25", 10), (2024, "26_40", 50),
                 (2024, "41_plus", 10)])
    assert got["top_label"] == f"{age_wording('under_18')} and {age_wording('26_40')}"
    assert got["bottom_label"] == f"{age_wording('18_25')} and {age_wording('41_plus')}"
    assert got["difference"] == 40


@pytest.mark.parametrize("counts, labels", [
    ([(2024, "26_40", 77), (2025, "26_40", 77)], ["2024", "2025"]),
    ([(2025, "under_18", 33), (2025, "18_25", 33), (2025, None, 33)],
     [age_wording("under_18"), age_wording("18_25"), "all ages"]),
], ids=["two years", "three age groups"])
def test_all_equal_gives_every_label_and_difference_0(counts, labels):
    """A6: all totals equal: top_label and bottom_label both hold every label, difference
    is 0, and all_equal is true."""
    got = check(counts)
    assert got["top_label"] == got["bottom_label"] == join_and(labels)
    assert got["top_value"] == got["bottom_value"] == counts[0][2]
    assert got["difference"] == 0
    assert got["all_equal"] is True


def test_difference_is_the_highest_minus_the_lowest():
    """A6: `difference`: highest minus lowest, whatever the order compared."""
    counts = [(2024, "under_18", 1250), (2025, "under_18", 980)]
    for order in (counts, counts[::-1]):
        got = check(order)
        assert got["difference"] == max(t for *_, t in counts) - min(t for *_, t in counts)
        assert (got["top_value"], got["bottom_value"]) == (1250, 980)


def test_two_counts_and_eight_counts():
    """A3 and A6: 2 to 8 counts. Eight: both years times the four age groups."""
    check([(2024, None, 5), (2025, None, 6)])
    filters = [(year, group) for year in (2024, 2025) for group in AGE_GROUPS]
    totals = (41, 77, 63, 18, 55, 90, 12, 70)
    got = check([(y, g, t) for (y, g), t in zip(filters, totals)])
    assert got["top_label"] == f"2025, {age_wording('18_25')}"
    assert got["bottom_label"] == f"2025, {age_wording('26_40')}"
    assert got["difference"] == max(totals) - min(totals)


# ---- the compare tool on the truth file's numbers -----------------------------------

CASES = {
    "years": ("Compare 2024 and 2025 for people under 18.",
              [(2024, "under_18"), (2025, "under_18")]),
    "age groups": ("Compare the four age groups in 2025.",
                   [(2025, group) for group in AGE_GROUPS]),
    "both": ("Compare all ages in 2024 with ages 18 to 25 in 2025.",
             [(2024, None), (2025, "18_25")]),
}


# R1: finish texts with the compare's one fact slot, mid-sentence and at the start.
TEXTS = {"after a colon": "Here is the comparison: {rid}.",
         "at the start": "{rid}. Want the details?"}


def every_compare_slot(rid, where="after a colon"):
    """A finish text with compare result `rid`'s fact slot that passes R1's checks."""
    return TEXTS[where].replace("{rid}", f"{{{rid}.compare}}")


def filled(c, rid, where="after a colon"):
    """every_compare_slot as R1's fill writes it (p1support.fill_expect)."""
    return fill_expect(every_compare_slot(rid, where), compare_slots(rid, c))


def truth_compare(counts):
    """compare_expect on the truth file's totals."""
    return compare_expect([(y, g, sum(months(y, g))) for y, g in counts])


def compare_turn(env, question, counts, where="after a colon"):
    """The FakeModel counts in one step, compares every count, then finishes."""
    rid = f"r{len(counts) + 1}"
    return env.ask(question,
                   Step(*[count(y, "all" if g is None else g) for y, g in counts]),
                   Step(compare(*[f"r{i + 1}" for i in range(len(counts))])),
                   Step(finish("finding", every_compare_slot(rid, where))))


@pytest.mark.parametrize("where", list(TEXTS))
@pytest.mark.parametrize("case", list(CASES))
def test_compare_tool_fills_the_compare_slot_with_the_truth_files_numbers(tmp_path, case,
                                                                          where):
    """A3 compare, A6 and R1: a passing finish is filled with the compare phrase of
    compare_expect's values on the truth file's totals (its first label lower case
    mid-sentence, a capital at the start); style agent; line 2 for a first answer."""
    question, counts = CASES[case]
    c = truth_compare(counts)
    if case == "both":
        assert c["top_value"] >= 1000, "this case is meant to show the comma"
    env = Env(tmp_path)
    reply = compare_turn(env, question, counts, where)
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_kind == "finding"
    assert reply.reply_style == "agent", (reply.reply_style, reply.draft_failures)
    assert list(reply.draft_failures) == []
    assert len(reply.results) == len(counts) + 1
    assert_answered(reply.text, re.escape(filled(c, f"r{len(counts) + 1}", where)),
                    first=True)


@pytest.mark.parametrize("case", list(CASES))
def test_compare_tool_with_fixed_style_renders_line_1(tmp_path, case):
    """A7: with MOCO_REPLY_STYLE at fixed the text is never used: line 1 is render_fixed
    (two counts: both count sentences and the compare sentence; more than two: the compare
    sentence only) and the style is fixed."""
    question, counts = CASES[case]
    env = Env(tmp_path, MOCO_REPLY_STYLE="fixed")
    reply = compare_turn(env, question, counts)
    check_reply(reply, env.model)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "fixed"
    assert_answered(reply.text, fixed_line1_re(counts, [truth_compare(counts)]), first=True)
