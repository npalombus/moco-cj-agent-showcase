"""Stage 3 Part A, C55 of docs/S3A-DESIGN.md: in C32, a `from` at or below the source's lowest
usable age and a `to` at or above its highest usable age are not ends; they are read as left out.
An end that is left is stated or not as today; a filter with no end left is not stated, so it is
asked. Nothing else of C32 or C36 point 4 changes. Brief: briefs/S3-R19-A-tests.md. Tests only;
the planning chat builds C55. The finding it answers is check 9's M14d
(kit-log/raw/CHAT-BUILDS-check-9.txt, PINNED, PROOF GAP 2). All data is SYNTHETIC: the fixtures of
tests/s3, and rows made for one test in that test's own copy (ids FIXTURE-R19-...); no real figure
is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel), county mode, talk on and talk off, for `count` and for `analyze` (a trend over 2024 and
2025). arrests_like's usable ages are 10 to 98, coded_like's 12 to 90 (test_premises_of_this_file).

What each test shows:
- counted: the request gets no AGES_NOT_STATED; it is answered exactly as the same request is
  answered after a message with no word of C32's list (a twin turn, in another thread of the same
  agent): the same tool answer, the same saved spec (the model's ages), the same reply; the turn
  is ANSWERED. For `analyze`, R is started (and runs, as the twin's).
- asked: as C32's tests show it today (round 5b's assert_ages_asked): AGES_NOT_STATED, then the
  model's finish gives NEEDS_INPUT with C32's question word for word, nothing counted, `missing`
  `ages`; for `analyze`, R is not started.

READINGS (also in kit-log/raw/S3-R19-A-notes.txt):
- R19-1. "Counted" is read as the brief writes it: no AGES_NOT_STATED, the count made with the
  model's ages, the turn ANSWERED. "With the model's ages" is checked against the twin: the
  same request after a message with no word of C32's list, where C32 plays no part, so the
  saved spec is whatever the program makes of those ages anyway (C5 and C28 unchanged).
- R19-2. "The lowest usable age to 24" (C55's own example) is 10 to 24 on arrests_like.
- R19-3. "At or above" and "at or below" are exact: one above the lowest (11) and one below the
  highest (97) are ends, and are asked when the message does not state them.
- R19-4. "The source's" usable ages: coded_like's 90 is its highest, so "older adults over 65"
  with the model's 66 to 90 is counted there and asked on arrests_like (count only: coded_like's
  copy starts in 2025 and has too few months for a trend).
- R19-5. Open (briefs/QUESTIONS.md, S3-R19-A question 1): a message that states both limits as
  numbers ("young people aged 10 to 98", the model's 10 to 98). By C55's words no end is left, so
  it is not stated and is asked; by C55's reason ("the person did state the ages") and C32 as it
  is today, it is counted. Both are accepted.
"""
import pytest

from p1support import THREAD_1, THREAD_2, Step, call, finish, manifests
from s3support import A_ID, C_ID, CountyEnv, NAMES, age, count, fixture_rows, made_rows, \
    run_records, source_json, turn_json, years
from test_s3_c36 import no_r
from test_s3_c48 import r_starts
from test_s3_round5 import Y25, line1, phrase, spec, stored_missing
from test_s3_round5b import FINISH, assert_ages_asked, not_refused

TALK = ["on", "off"]
A, C = NAMES
LOW, HIGH = 10, 98                # arrests_like's usable ages (premise below)
CODED_LOW, CODED_HIGH = 12, 90    # coded_like's
P = years(2024, 2025)             # the trend's period
TREND_TEXT = "Here it is. {a1.trend}."
TWIN = {"count": "How many arrests were there in 2025?",
        "analyze": "Did arrests go up from 2024 to 2025?"}

# ==== the cases =================================================================================
# id: (the message for `count`, the message for `analyze`, the ages the model sends, the words as
#      the message has them). arrests_like.

COUNTED = {
    # C55's own examples
    "C55: older adults over 65, the model's 66 to 98": (
        "How many arrests of older adults over 65 were there in 2025?",
        "Did arrests of older adults over 65 go up from 2024 to 2025?", age(66, HIGH)),
    "C55: seniors 70 and older, the model's 70 to 98": (
        "How many arrests of seniors 70 and older were there in 2025?",
        "Did arrests of seniors 70 and older go up from 2024 to 2025?", age(70, HIGH)),
    "C55: young people under 25, the model's 10 (the lowest usable age) to 24": (
        "How many arrests of young people under 25 were there in 2025?",
        "Did arrests of young people under 25 go up from 2024 to 2025?", age(LOW, 24)),
    # this file's own
    "a `to` above the highest usable age: older adults over 65, the model's 66 to 120": (
        "How many arrests of older adults over 65 were there in 2025?",
        "Did arrests of older adults over 65 go up from 2024 to 2025?", age(66, 120)),
    "a `from` below the lowest usable age: young people under 25, the model's 0 to 24": (
        "How many arrests of young people under 25 were there in 2025?",
        "Did arrests of young people under 25 go up from 2024 to 2025?", age(0, 24)),
    "a stated `to`, a `from` at the lowest usable age: teenagers under 20, the model's 10 to 19": (
        "How many teenagers under 20 were arrested in 2025?",
        "Did arrests of teenagers under 20 go up from 2024 to 2025?", age(LOW, 19)),
    "a stated `from`, a `to` one above the highest: seniors 70 and older, the model's 70 to 99": (
        "How many arrests of seniors 70 and older were there in 2025?",
        "Did arrests of seniors 70 and older go up from 2024 to 2025?", age(70, HIGH + 1)),
}

ASKED = {
    # C55's own examples
    "C55: older adults over 65, the model's 66 to 80": (
        "How many arrests of older adults over 65 were there in 2025?",
        "Did arrests of older adults over 65 go up from 2024 to 2025?", age(66, 80),
        "older adults"),
    "C55: young people, the model's 18 to 24": (
        "How many arrests of young people were there in 2025?",
        "Did arrests of young people go up from 2024 to 2025?", age(18, 24), "young people"),
    "C55: young people, the model's 10 to 98 (the lowest usable age to the highest)": (
        "How many arrests of young people were there in 2025?",
        "Did arrests of young people go up from 2024 to 2025?", age(LOW, HIGH), "young people"),
    "C55: young people under 25, the model's 18 to 24": (
        "How many arrests of young people under 25 were there in 2025?",
        "Did arrests of young people under 25 go up from 2024 to 2025?", age(18, 24),
        "young people"),
    # this file's own
    "a `to` above the highest, `from` not stated: older adults, the model's 66 to 120": (
        "How many arrests of older adults were there in 2025?",
        "Did arrests of older adults go up from 2024 to 2025?", age(66, 120), "older adults"),
    "a `from` below the lowest, `to` not stated: young people, the model's 0 to 24": (
        "How many arrests of young people were there in 2025?",
        "Did arrests of young people go up from 2024 to 2025?", age(0, 24), "young people"),
    "both ends at the limits with a vague word: seniors, the model's 10 to 98": (
        "How many seniors were arrested in 2025?",
        "Did arrests of seniors go up from 2024 to 2025?", age(LOW, HIGH), "seniors"),
    "both ends past the limits: teenagers, the model's 0 to 120": (
        "How many teenagers were arrested in 2025?",
        "Did arrests of teenagers go up from 2024 to 2025?", age(0, 120), "teenagers"),
    "a stated `to`, a `from` one above the lowest: young people under 25, the model's 11 to 24": (
        "How many arrests of young people under 25 were there in 2025?",
        "Did arrests of young people under 25 go up from 2024 to 2025?", age(LOW + 1, 24),
        "young people"),
    "a stated `from`, a `to` one below the highest: older adults over 65, the model's 66 to 97": (
        "How many arrests of older adults over 65 were there in 2025?",
        "Did arrests of older adults over 65 go up from 2024 to 2025?", age(66, HIGH - 1),
        "older adults"),
}

# ==== rows for the trend (the test's own copy; the shared fixture files unchanged) ==============


def _trend_rows():
    """SYNTHETIC rows over arrests_like's base row (s3support.made_rows): 10 aged 70 and 10 aged
    15 on the 15th of every month of 2024 and 2025, so a trend of each age range here has records
    enough (S1) and no hidden month; made_rows' anchor row left out, so the fixture's own newest
    record stays the copy's newest."""
    groups = [(10, {"age": years_old, "event_date_time": f"{y}-{m:02d}-15T14:00:00.000"})
              for y in (2024, 2025) for m in range(1, 13) for years_old in ("70", "15")]
    made = made_rows(A, *groups, prefix="FIXTURE-R19-")
    return fixture_rows(A) + [r for r in made if not r["id"].endswith("ANCHOR")]


def env_for(tmp_path, monkeypatch, tool, talk, n=1):
    rows = {A: _trend_rows()} if tool == "analyze" else None
    return CountyEnv(tmp_path, monkeypatch, names=NAMES[:n], rows=rows, MOCO_TALK=talk)


def request(tool, filters, sid=A_ID):
    if tool == "count":
        return count(sid, Y25, filters)
    return call("analyze", {"kind": "trend", "source": sid, "period": P, "filters": filters})


def finish_of(tool):
    return FINISH if tool == "count" else Step(finish("finding", TREND_TEXT))


def message_of(tool, case):
    return case[0] if tool == "count" else case[1]


# ==== counted ===================================================================================

def assert_counted_as_the_twin(env, monkeypatch, tool, message, filters, sid=A_ID):
    """R19-1: the twin first (another thread), then the turn; both the same."""
    started = r_starts(monkeypatch) if tool == "analyze" else []
    twin = env.ask(TWIN[tool], Step(request(tool, filters, sid)), finish_of(tool),
                   thread_key=THREAD_2)
    twin_answer = env.model.answer(0)
    assert "error" not in twin_answer, f"premise: the twin is answered: {twin_answer}"
    assert twin.status == "ANSWERED", ("premise", twin.status, twin.reason_code, twin.text)
    assert started == (["trend"] if tool == "analyze" else []), "premise: the twin's R runs"

    reply = env.ask(not_refused(message), Step(request(tool, filters, sid)), finish_of(tool))
    answer = env.model.answer(0)
    assert answer.get("error") != "AGES_NOT_STATED", \
        f"asked: an end at the usable limit was taken as an end (C55): {answer}"
    assert answer == twin_answer, (answer, twin_answer)
    assert len(env.model.calls) == 2
    assert (reply.status, reply.reason_code, reply.text) == ("ANSWERED", None, twin.text), \
        (reply.status, reply.reason_code, reply.text)
    if tool == "analyze":
        assert started == ["trend", "trend"], "R was not started"
    else:
        assert len(run_records(reply, env.runs_dir)) == 1 and len(manifests(env.runs_dir)) == 2
    assert [(r["kind"], r["spec"]) for r in reply.results] == \
        [(r["kind"], r["spec"]) for r in twin.results], "not counted with the model's ages"
    assert turn_json(reply, env.runs_dir)["status"] == "ANSWERED"
    return reply


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("tool", ["count", "analyze"])
@pytest.mark.parametrize("case", list(COUNTED))
def test_c55_counted(tmp_path, monkeypatch, case, tool, talk):
    filters = COUNTED[case][2]
    env = env_for(tmp_path, monkeypatch, tool, talk)
    reply = assert_counted_as_the_twin(env, monkeypatch, tool, message_of(tool, COUNTED[case]),
                                       [filters])
    if tool == "count" and LOW <= filters["from"] and filters["to"] <= HIGH:
        assert line1(reply) == f"I counted {phrase(spec(Y25, [filters]))}.", reply.text


# ==== asked =====================================================================================

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("tool", ["count", "analyze"])
@pytest.mark.parametrize("case", list(ASKED))
def test_c55_asked_as_today(tmp_path, monkeypatch, case, tool, talk):
    _, _, filters, words = ASKED[case]
    started = no_r(monkeypatch)
    env = env_for(tmp_path, monkeypatch, tool, talk)
    reply = env.ask(not_refused(message_of(tool, ASKED[case])), Step(request(tool, [filters])),
                    finish_of(tool))
    assert started == [], "R was started"
    assert_ages_asked(env, reply, words)


# ==== the source's own limits (R19-4) ===========================================================

OVER_65 = "How many arrests of older adults over 65 were there in 2025?"
CODED_OVER_65 = "How many intake records of older adults over 65 were there in 2025?"


@pytest.mark.parametrize("talk", TALK)
def test_c55_the_other_sources_highest_usable_age_is_its_own(tmp_path, monkeypatch, talk):
    """coded_like's highest usable age is 90: 66 to 90 there is counted."""
    env = env_for(tmp_path, monkeypatch, "count", talk, n=2)
    assert_counted_as_the_twin(env, monkeypatch, "count", CODED_OVER_65,
                               [age(66, CODED_HIGH, "age_years")], sid=C_ID)


@pytest.mark.parametrize("talk", TALK)
def test_c55_90_is_not_arrests_likes_highest_so_it_is_asked(tmp_path, monkeypatch, talk):
    """The same 66 to 90 on arrests_like (highest 98): 90 is an end, not stated: asked."""
    env = env_for(tmp_path, monkeypatch, "count", talk, n=2)
    reply = env.ask(not_refused(OVER_65), Step(count(A_ID, Y25, [age(66, CODED_HIGH)])), FINISH)
    assert_ages_asked(env, reply, "older adults")


# ==== C55 point 2: nothing else changes =========================================================

@pytest.mark.parametrize("talk", TALK)
def test_c55_point_2_the_question_pending_and_missing_as_today(tmp_path, monkeypatch, talk):
    """An end left that is not stated (C55's "young people under 25", 18 to 24, beside a district
    filter): the question, the pending request (source, period, filters other than age) and
    `missing`, as C36 point 4 has them; and a second request with ages the message does not
    state in the same turn is answered AGES_NOT_STATED again."""
    d3 = {"field": "district", "is": "district 3"}
    env = env_for(tmp_path, monkeypatch, "count", talk)
    reply = env.ask(not_refused("How many arrests of young people under 25 were there in "
                                "district 3 in 2025?"),
                    Step(count(A_ID, Y25, [age(18, 24), d3])),
                    Step(count(A_ID, Y25, [age(LOW + 1, HIGH), d3])), FINISH)
    assert env.model.answer(1).get("error") == "AGES_NOT_STATED", env.model.answer(1)
    assert_ages_asked(env, reply, "young people", calls=3)
    assert stored_missing(env) == "ages"
    pending = env.store.recent_turns(THREAD_1, 1)[-1].get("pending")
    assert pending == {"source": A_ID, "period": Y25, "filters": [d3]}, pending


# ==== open (R19-5) ==============================================================================

@pytest.mark.parametrize("talk", TALK)
def test_c55_open_both_limits_stated_as_numbers(tmp_path, monkeypatch, talk):
    """R19-5, pinned by brief S3-R22-A to the answer to S3-R19-A's question (17 Nov 10:20 EST):
    "young people aged 10 to 98", the model's 10 to 98. An end at the limit that the message
    states is a stated end: counted, as the twin."""
    env = env_for(tmp_path, monkeypatch, "count", talk)
    reply = assert_counted_as_the_twin(
        env, monkeypatch, "count",
        "How many arrests of young people aged 10 to 98 were there in 2025?", [age(LOW, HIGH)])
    assert line1(reply) == f"I counted {phrase(spec(Y25, [age(LOW, HIGH)]))}.", reply.text


# ==== premises ==================================================================================

def test_premises_of_this_file():
    usable = {name: [f["usable"] for f in source_json(name)["fields"] if f["kind"] == "age"]
              for name in NAMES}
    assert usable == {A: [[LOW, HIGH]], C: [[CODED_LOW, CODED_HIGH]]}, usable
    rows = _trend_rows()
    made = [r for r in rows if r["id"].startswith("FIXTURE-R19-")]
    assert len(made) == 480 and all(r["data_class"] == "SYNTHETIC" for r in made)
    assert len({r["id"] for r in rows}) == len(rows), "a made id repeats a fixture id"
    assert max(r["event_date_time"] for r in made) < "2026-09-17", "past the copy's newest"
