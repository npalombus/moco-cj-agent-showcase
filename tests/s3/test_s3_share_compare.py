"""`share` and `compare`: docs/S3A-DESIGN.md C7 (with C1's "Sources are never blended" and
C8.5), and C12's "`share`, `compare`, `MIXED_SOURCES`, `PARTIAL_YEAR`". The phrases they
fill are test_s3_phrases.py's; the floor's part (a hidden value) is test_s3_floor.py's.

What this file covers
- share(part_id, whole_id): a part that is the whole's spec plus one or two filters gives a
  share result ({"result_id", "slots": ["{rN.share}"]}, no value) and its phrase; anything
  else is BAD_SHARE: another period, a filter changed, no filter added, the two the wrong
  way round, two sources, a result of an earlier turn, an unknown id, a compare result, a
  hidden value. Never called a rate.
- compare(result_ids): counts of one source give a compare result and its phrase; counts of
  two sources give MIXED_SOURCES; a breakdown, one id, an unknown id or a share result is
  not compared.
- PARTIAL_YEAR: whole years compared where one is the copy's last, unfinished year (either
  order, either fixture): the answer carries the last finished month M, decided by Python
  (8 for arrests_like, whose newest record is 17 September 2026; 7 for coded_like, 20 August
  2026); counted again with months 1 to M, the compare is made and filled. Finished years,
  or the same months of two years, are compared at once.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- share's answer is shaped like count's: {"result_id": "rN", "slots": ["{rN.share}"]}.
- A compare of a breakdown, of one id, of an unknown id or of a share result gets an error
  (its code is not given: BAD_COMPARE as in stage 2, or MIXED_SOURCES); nothing is compared.
- PARTIAL_YEAR's answer holds M as a whole number somewhere in it.
- After a PARTIAL_YEAR the counts of whole years stay results of the turn (they were made);
  the model's new counts come next (r3, r4) and their compare r5. The labels of the two
  compared periods may be the years alone or the whole period phrases.
"""
import json
import re

import pytest

from p1support import Step, finish, has_leaf
from s3support import (A_ID, C_ID, NAMES, Q_COMPARE, Q_SHARE, SCHOOL, CountyEnv, age,
                       check_county_reply, compare, count, figures, is_, months, share,
                       truth, year)


def share_answer(env, step=1):
    return env.model.answer(step)


def share_turn(env, *counts, part="r2", whole="r1", text="Here is what I found: {r3.share}."):
    return env.ask(Q_SHARE, Step(*counts), Step(share(part, whole)),
                   Step(finish("finding", text)))


def compare_turn(env, *counts, ids=("r1", "r2"), text="Here is the comparison: {r3.compare}."):
    return env.ask(Q_COMPARE, Step(*counts), Step(compare(*ids)), Step(finish("finding", text)))


def line1_is(reply, expected):
    text = reply.text
    assert text == expected or (text.startswith(expected) and text[len(expected)] in " \n"), \
        f"line 1 is not {expected!r}:\n{text}"


# ---- share ----------------------------------------------------------------------------------

def test_a_share_of_a_whole_and_its_part(tmp_path, monkeypatch):
    """C7: both from this turn and the same source; the part's spec is the whole's spec plus
    one filter. Python answers with a result and its slot, no value; the phrase is C6's."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, count(A_ID, year(2025)), count(A_ID, year(2025), [is_(SCHOOL, True)]))
    check_county_reply(reply)
    answer = share_answer(env)
    assert answer.get("result_id") == "r3" and "{r3.share}" in answer.get("slots", []), answer
    assert figures(json.dumps(answer)) == set(), answer
    assert reply.status == "ANSWERED" and reply.reply_style == "agent", \
        (reply.status, reply.draft_failures, reply.text)
    line1_is(reply, "Here is what I found: 32% of the 240 arrest records in 2025 were within 500 "
                    "feet of a school.")
    assert len(reply.run_ids) == 2


def test_a_share_whose_part_adds_two_filters(tmp_path, monkeypatch):
    """C7: "plus one or more filters"; C6 writes the part's added filters in C6's order (a
    person filter, then a place). 20 of the 76 records near a school in 2025 are of men in
    district 6: 26%."""
    added = [is_("district", "district 6"), is_("gender", "male")]
    assert truth("arrests_like", year(2025), [is_(SCHOOL, True)] + added)["total"] == 20
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, count(A_ID, year(2025), [is_(SCHOOL, True)]),
                       count(A_ID, year(2025), [is_(SCHOOL, True)] + added))
    line1_is(reply, "Here is what I found: 26% of the 76 arrest records within 500 feet of a "
                    "school in 2025 were of people recorded as male in district 6.")


def test_a_share_is_never_called_a_rate(tmp_path, monkeypatch):
    """C7: "Never called a rate": not in the answer the model gets, nor in line 1."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, count(A_ID, year(2025)), count(A_ID, year(2025), [age(None, 17)]))
    assert "rate" not in json.dumps(share_answer(env)).lower()
    assert "rate" not in reply.text.split("\n")[0].lower()


BAD_SHARES = {
    "another period": ((year(2025), []), (year(2024), [is_(SCHOOL, True)])),
    "a filter changed": ((year(2025), [is_("district", "district 3")]),
                         (year(2025), [is_("district", "district 4"), is_(SCHOOL, True)])),
    "the whole's filter dropped": ((year(2025), [is_("district", "district 3")]),
                                   (year(2025), [is_(SCHOOL, True)])),
    "the wrong way round": ((year(2025), [is_(SCHOOL, True)]), (year(2025), [])),
    "the same spec, no filter added": ((year(2025), [is_(SCHOOL, True)]),
                                       (year(2025), [is_(SCHOOL, True)])),
    "a hidden part": ((year(2025), [is_(SCHOOL, True)]),
                      (year(2025), [is_(SCHOOL, True), is_("district", "district 2")])),
}


@pytest.mark.parametrize("case", list(BAD_SHARES))
def test_bad_share(tmp_path, monkeypatch, case):
    """C7: the part's spec must be the whole's spec plus one or more filters, and neither
    value hidden; else BAD_SHARE. Nothing shared reaches the reply."""
    whole, part = BAD_SHARES[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, count(A_ID, *whole), count(A_ID, *part))
    assert share_answer(env).get("error") == "BAD_SHARE", share_answer(env)
    assert "%" not in reply.text


def test_a_share_of_one_result_with_itself_is_bad(tmp_path, monkeypatch):
    """C7: the part must add at least one filter: a result is not a part of itself."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, count(A_ID, year(2025)), part="r1", whole="r1",
                       text="I counted {r1.count}.")
    assert share_answer(env).get("error") == "BAD_SHARE", share_answer(env)
    assert "%" not in reply.text


def test_a_share_across_two_sources_is_bad(tmp_path, monkeypatch):
    """C7 and C1: both from the same source; sources are never blended."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = share_turn(env, count(A_ID, year(2025)),
                       count(C_ID, year(2025), [is_("station", "station 3")]))
    assert share_answer(env).get("error") == "BAD_SHARE", share_answer(env)
    assert "%" not in reply.text


@pytest.mark.parametrize("ids", [("r2", "r1"), ("r9", "r1"), ("r3", "r1")],
                         ids=["results of an earlier turn", "an unknown id", "a compare result"])
def test_a_share_of_what_is_not_a_count_of_this_turn_is_bad(tmp_path, monkeypatch, ids):
    """C7: both from this turn, and both counts."""
    env = CountyEnv(tmp_path, monkeypatch)
    first = env.ask(Q_SHARE, Step(count(A_ID, year(2025)), count(A_ID, year(2024))),
                    Step(compare("r1", "r2")),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED", (first.status, first.reason_code, first.text)
    if ids[0] == "r2":  # a new turn with no count of its own
        reply = env.ask(Q_SHARE, Step(share(*ids)), Step(finish("finding", "{r1.count}.")))
        answer = env.model.answer(0)
    else:
        reply = env.ask(Q_SHARE, Step(count(A_ID, year(2025)), count(A_ID, year(2024))),
                        Step(compare("r1", "r2")), Step(share(*ids)),
                        Step(finish("finding", "I counted {r1.count}.")))
        answer = env.model.answer(2)
    assert answer.get("error") == "BAD_SHARE", answer
    assert "%" not in reply.text


# ---- compare --------------------------------------------------------------------------------------

def test_a_compare_of_two_counts_of_one_source(tmp_path, monkeypatch):
    """C7: compare(result_ids) of single counts of the same source: a compare result, its
    slot offered, no value in the answer."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = compare_turn(env, count(A_ID, year(2024)), count(A_ID, year(2025)))
    check_county_reply(reply)
    answer = env.model.answer(1)
    assert answer.get("result_id") == "r3" and "{r3.compare}" in answer.get("slots", []), answer
    assert figures(json.dumps(answer)) == set(), answer
    line1_is(reply, "Here is the comparison: 2025 had the highest count (240) and 2024 the "
                    "lowest (230), a difference of 10.")


def test_a_compare_of_two_sources_is_mixed_sources(tmp_path, monkeypatch):
    """C7: `MIXED_SOURCES` otherwise; C1: no comparison across two sources."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = compare_turn(env, count(A_ID, year(2025)), count(C_ID, year(2025)),
                         text="I counted {r1.count}. I also counted {r2.count}.")
    assert env.model.answer(1).get("error") == "MIXED_SOURCES", env.model.answer(1)
    assert "difference" not in reply.text and "highest" not in reply.text


@pytest.mark.parametrize("case", ["one id", "an unknown id", "a share result"])
def test_what_is_not_two_counts_is_not_compared(tmp_path, monkeypatch, case):
    """C7: compare takes counts (2 to 8, as stage 2): one id, an unknown id or a share result
    gets an error and no compare is made. (Whether a breakdown is a "single count" is not
    tested: see the notes.)"""
    env = CountyEnv(tmp_path, monkeypatch)
    counts = [count(A_ID, year(2025)), count(A_ID, year(2025), [is_(SCHOOL, True)])]
    steps = [Step(*counts)]
    ids = {"one id": ("r1",), "an unknown id": ("r1", "r9"), "a share result": ("r1", "r3")}[case]
    if case == "a share result":
        steps.append(Step(share("r2", "r1")))
    steps += [Step(compare(*ids)), Step(finish("finding", "I counted {r1.count}."))]
    reply = env.ask(Q_COMPARE, *steps)
    answer = env.model.answer(len(steps) - 2)
    assert answer.get("error") in ("BAD_COMPARE", "MIXED_SOURCES"), answer
    assert "highest" not in reply.text and "difference" not in reply.text


# ---- PARTIAL_YEAR (C7) ------------------------------------------------------------------------------

def partial_year_turn(env, sid, first, last, m):
    """Whole years `first` and `last` compared; on PARTIAL_YEAR, both counted again with months
    1 to m, compared, and the compare filled."""
    return env.ask(Q_COMPARE, Step(count(sid, year(first)), count(sid, year(last))),
                   Step(compare("r1", "r2")),
                   Step(count(sid, months(first, 1, m)), count(sid, months(last, 1, m))),
                   Step(compare("r3", "r4")),
                   Step(finish("finding", "Here is the comparison: {r5.compare}.")))


@pytest.mark.parametrize("name, first, last, m", [
    ("arrests_like", 2025, 2026, 8), ("arrests_like", 2026, 2025, 8),
    ("coded_like", 2025, 2026, 7),
], ids=["2025 and 2026", "2026 and 2025", "coded: 2025 and 2026"])
def test_partial_year(tmp_path, monkeypatch, name, first, last, m):
    """C7: when compared periods are whole years and one of them is the copy's last,
    unfinished year, compare answers PARTIAL_YEAR with the last finished month M (Python,
    not the model, decides M); the model counts both again with months 1 to M and the
    compare is made from those counts."""
    sid = A_ID if name == "arrests_like" else C_ID
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = partial_year_turn(env, sid, first, last, m)
    answer = env.model.answer(1)
    assert answer.get("error") == "PARTIAL_YEAR", answer
    assert has_leaf(answer, m), f"the answer does not carry M = {m}: {answer}"
    assert env.model.answer(3).get("result_id") == "r5", env.model.answer(3)
    check_county_reply(reply)
    assert reply.status == "ANSWERED" and reply.reply_style == "agent", \
        (reply.status, reply.draft_failures, reply.text)
    totals = {y: truth(name, months(y, 1, m))["total"] for y in (first, last)}
    high, low = max(totals, key=totals.get), min(totals, key=totals.get)
    month = ["January", "February", "March", "April", "May", "June", "July", "August"][m - 1]

    def label(y):
        return f"(?:{y}|from January to {month} {y})"

    pattern = (f"Here is the comparison: {label(high)} had the highest count "
               f"\\({totals[high]}\\) and {label(low)} the lowest \\({totals[low]}\\), a "
               f"difference of {totals[high] - totals[low]}\\.")
    assert re.match(pattern + r"(?:[ \n]|$)", reply.text), (pattern, reply.text)


@pytest.mark.parametrize("periods", [(year(2024), year(2025)), (months(2025, 1, 8),
                                                                  months(2026, 1, 8))],
                         ids=["two finished years", "the same months of two years"])
def test_no_partial_year_when_none_is_needed(tmp_path, monkeypatch, periods):
    """C7: PARTIAL_YEAR only when one of the whole years compared is the unfinished one."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = compare_turn(env, count(A_ID, periods[0]), count(A_ID, periods[1]))
    assert env.model.answer(1).get("result_id") == "r3", env.model.answer(1)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    one, two = (truth("arrests_like", p)["total"] for p in periods)
    assert f"a difference of {abs(one - two)}" in reply.text


def test_partial_year_gives_no_result_and_no_value(tmp_path, monkeypatch):
    """C7 with C5: PARTIAL_YEAR is an error answer: no compare result, no figure from the
    data (only M, a month)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = compare_turn(env, count(A_ID, year(2025)), count(A_ID, year(2026)),
                         text="I counted {r1.count}. I also counted {r2.count}.")
    answer = env.model.answer(1)
    assert answer.get("error") == "PARTIAL_YEAR" and "result_id" not in answer, answer
    assert not ({240, 130} & figures(json.dumps(answer))), answer
    assert "difference" not in reply.text
