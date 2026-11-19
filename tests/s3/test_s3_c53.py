"""Stage 3 Part A, C53 of docs/S3A-DESIGN.md: two small corrections from
kit-log/raw/CHAT-BUILDS-check-7.txt (its DEFECT 4 and DEFECT 3). Brief: briefs/S3-R16-A-tests.md.
Tests only; the planning chat builds C53. All data is SYNTHETIC fixtures; no real figure.

Point 1: C30's "names of" is withdrawn. C30's answer (NOT_RECORDED, then the UNSUPPORTED_FIELD row
if the model makes nothing) is given only for `who` then was / were / got / has been / have been,
then one of its seven words. A message that asks for names in other words goes to the model:
its count is counted. Each `who` form still gets C30's answer once a turn (C48).
Point 2: a year filter whose value has a fraction (2024.5), in `is`, `in`, `from` or `to`, is not
read as a period (C34): the filters are left as they are, so with no period the turn ends with
C5's period question, as for any year filter C34 does not read. 2024.0 and "2024" are read as
today.

The tests changed elsewhere for C53 (tests/s3/test_s3_round5b.py, test_s3_c36.py,
test_s3_c48.py) are listed, old and new, in kit-log/raw/S3-R16-A-notes.txt.

READINGS (also in the notes):
- R53-1. "No C30 answer and the count runs": the model's first count is answered with a result
  (r1), as the same request is after a message with no C29 word and no C30 question, and the
  turn is ANSWERED. Which words the model then writes is the model's (D-065), not tested.
- R53-2. "Each of the four places with a fraction is left unread": with no period and nothing
  in the thread, the turn ends with C5's period question and `missing` "period", nothing
  counted, as tests/s3/test_s3_round5b.py's C34_TODAY cases do. A fraction written as text
  ("2024.5") is left unread today already (int() refuses it); it is here as a case that passes.
- R53-3. "2024.0 and "2024" are read": the request with the year filter and no period gives the
  same answer, reply and saved spec as the same request with that period (round 5b's
  assert_same_turn).
"""
import pytest

from p1support import LEAVE_OUT, THREAD_2, Step, finish
from s3support import A_ID, CountyEnv, count, is_, year, years
from test_s3_c36 import NOT_RECORDED_C30
from test_s3_round5 import QUESTION, Y25, asked, stored_missing
from test_s3_round5b import A, C30_ENDS, assert_same_turn, nothing_counted, year_filter

D3 = is_("district", "district 3")
BY_DISTRICT = count(A_ID, Y25, group_by=["district"])
GROUPS = "I counted {r1.count}. {r1.groups}."
ONE = "I counted {r1.count}."

# ---- point 1: "names of" is withdrawn ---------------------------------------------------------------

NAMES = {
    # id: (the message, the model's count, its finding, a twin message with no C30 words)
    "C53: the name of the district with the most arrests": (
        "What is the name of the district with the most arrests in 2025?", BY_DISTRICT, GROUPS,
        "Which district had the most arrests in 2025?"),
    "C53: names of the districts": (
        "Can you give me the names of the districts with arrests in 2025?", BY_DISTRICT, GROUPS,
        "Can you give me the districts with arrests in 2025?"),
    "the review's names_of (was test_s3_c48.py's case)": (
        "What are the names of the districts with the most arrests in 2025?", BY_DISTRICT, GROUPS,
        "Which districts had the most arrests in 2025?"),
    "round 5b's the names of (people)": (
        "What are the names of the people arrested in district 3 in 2025?",
        count(A_ID, Y25, [D3]), ONE, "How many people were arrested in district 3 in 2025?"),
    "round 5b's the names of, another wording": (
        "Give me the names of everyone stopped in 2025.", count(A_ID, Y25), ONE,
        "Give me everyone stopped in 2025."),
    "name of, capitalised": (
        "NAME OF the district with the most arrests in 2025?", BY_DISTRICT, GROUPS,
        "The district with the most arrests in 2025?"),
}


@pytest.mark.parametrize("talk", [{}, {"MOCO_TALK": "on"}], ids=["talk off", "talk on"])
@pytest.mark.parametrize("case", list(NAMES))
def test_c53_1_a_names_message_gets_no_c30_answer_and_the_count_runs(tmp_path, monkeypatch,
                                                                       case, talk):
    message, request, text, twin_message = NAMES[case]
    env = CountyEnv(tmp_path, monkeypatch, **talk)
    twin = env.ask(twin_message, Step(request), Step(finish("finding", text)), thread_key=THREAD_2)
    twin_answer = env.model.answer(0)
    assert twin.status == "ANSWERED" and twin_answer.get("result_id") == "r1", "premise"
    reply = env.ask(message, Step(request), Step(finish("finding", text)))
    assert len(env.model.calls) == 2, (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) != NOT_RECORDED_C30, "C53 point 1: no C30 answer"
    assert env.model.answer(0) == twin_answer
    assert (reply.status, reply.reason_code) == ("ANSWERED", None), \
        (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == 1


@pytest.mark.parametrize("case", list(C30_ENDS))
def test_c53_1_each_who_form_still_gets_c30s_answer_once_a_turn(tmp_path, monkeypatch, case):
    """C53 point 1 with C48: the first count of the turn is answered NOT_RECORDED, the same count
    sent again is counted, and the turn is ANSWERED."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(C30_ENDS[case], Step(count(A_ID, Y25, [D3])), Step(count(A_ID, Y25, [D3])),
                    Step(finish("finding", ONE)))
    assert env.model.answer(0) == NOT_RECORDED_C30
    assert env.model.answer(1).get("result_id") == "r1", env.model.answer(1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def test_c53_1_a_who_form_with_names_in_one_message_is_answered_once(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("Who was arrested in district 3 in 2025, and what are the names of them?",
                    Step(count(A_ID, Y25, [D3])), Step(count(A_ID, Y25, [D3])),
                    Step(finish("finding", ONE)))
    assert env.model.answer(0) == NOT_RECORDED_C30
    assert env.model.answer(1).get("result_id") == "r1", env.model.answer(1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ---- point 2: a year with a fraction is not read as a period ---------------------------------------

FRACTIONS = {
    # id: the year filter, sent with no period
    "is 2024.5": year_filter(is_=2024.5),
    "in [2024.9, 2025]": year_filter(**{"in": [2024.9, 2025]}),
    "in [2025, 2024.5] (the fraction second)": year_filter(**{"in": [2025, 2024.5]}),
    "from 2024.5 to 2025": year_filter(**{"from": 2024.5, "to": 2025}),
    "from 2024 to 2025.5": year_filter(**{"from": 2024, "to": 2025.5}),
    "from 2024.0 to 2025.5 (a whole number and a fraction)":
        year_filter(**{"from": 2024.0, "to": 2025.5}),
    'is "2024.5", a fraction as text (left unread today already)': year_filter(is_="2024.5"),
}


@pytest.mark.parametrize("case", list(FRACTIONS))
def test_c53_2_a_year_with_a_fraction_is_left_unread(tmp_path, monkeypatch, case):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("How many arrests in district 3?",
                    Step(count(A_ID, LEAVE_OUT, [FRACTIONS[case], D3])), Step(finish("finding", ONE)))
    assert asked(env, reply) == QUESTION[A]
    assert stored_missing(env) == "period"
    nothing_counted(env, reply)


WHOLE = {
    # id: (the year filter, the period it gives) -- read as today
    "is 2024.0": (year_filter(is_=2024.0), year(2024)),
    'is "2024"': (year_filter(is_="2024"), year(2024)),
    'in ["2024", 2025.0]': (year_filter(**{"in": ["2024", 2025.0]}), years(2024, 2025)),
    'from 2024.0 to "2025"': (year_filter(**{"from": 2024.0, "to": "2025"}), years(2024, 2025)),
}


@pytest.mark.parametrize("case", list(WHOLE))
def test_c53_2_a_whole_number_is_read_as_today(tmp_path, monkeypatch, case):
    flt, period = WHOLE[case]
    env = CountyEnv(tmp_path, monkeypatch)
    assert_same_turn(env, "How many arrests in district 3?", count(A_ID, LEAVE_OUT, [flt, D3]),
                     count(A_ID, period, [D3]))
