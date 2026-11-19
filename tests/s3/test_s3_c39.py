"""C39 of docs/S3A-DESIGN.md (D-048): a short fixed answer about the data in county mode. Brief:
briefs/S3-R7-A-tests.md. Tests only; the planning chat makes the change.

With three or more sources (C23's SHORT_FROM) `replies.county_about_text` becomes one short
paragraph, then the notices lines as today; with one or two sources it is as today;
describe_data and its fact slots are unchanged. C39's tests:
- the text word for word with the two fixtures plus a third (tests/s3/fixtures/round3's
  visits_like, as round 3 adds it), and as today with one and with two (written out by hand
  from today's program);
- the notices follow it;
- nothing else in an about answer changes: its status, kind and style, the passing about
  text (filled, then the notices), and describe_data's facts, which still cover every source.

The fixed about text is reached three ways, each tested: an about_data finish with no
describe_data in the turn (style fallback), a text that fails the check after describe_data
(style fallback) and MOCO_REPLY_STYLE=fixed (style fixed).

READINGS (also in kit-log/raw/S3-R7-A-notes.txt):
- C39-1 "<n>" is written in digits, and counts the sources offered, whether or not each has a
  copy (C23's answer (c)): three sources with one copy missing give the same text.
- C39-2 "the sources by what they count, as help names them": C23's help list, each source's
  `unit.many`, joined as analysis.join_and does, in file order.
- C39-3 "then the notices lines as today": as today's about reply adds them, each on its own
  line after the text (one line break), C11's notices word for word, then the course line.
- C39-4 (open, briefs/QUESTIONS.md S3-R7-A question 3) C14's free-text lines ("Grouped by the
  agent from free text: ...") follow today's about text for a source with an interpreted
  field. C39 does not say whether they stay with three or more sources. No fixture source has
  such a field, so nothing here depends on it.
"""
import pytest

from p1support import THREAD_2, Step, describe, finish
from s3support import NAMES, Q_ABOUT, CountyEnv
from test_s3_round3 import LONG_A, LONG_C, LONG_PART, LONG_V, add_visits, three_sources

COURSE_LINE = "This agent is a university course project. It is not a county service."

# C39, with three sources, word for word.
ABOUT_THREE = ("I work with 3 sources of Montgomery County open data: arrest records, intake "
               "records and visit records. I count records, not people, and I never show a "
               "single record. Ask about any one of them for its dates and what it can be broken "
               "down by.")

# Today's text with one and with two sources (C11 as built), written out by hand.
TITLE_A = "SYNTHETIC fixture arrests (made up for tests)"
TITLE_C = "SYNTHETIC fixture intake records (made up for tests)"
COVERS_A = "covering 1 January 2024 to 17 September 2026"
COVERS_C = "covering 1 January 2025 to 20 August 2026"
TODAY = {
    ("arrests_like",): (f"I work with county open data: {TITLE_A}, {COVERS_A}. I count records, "
                        f"not people, and I never show a single record. {LONG_A}"),
    ("coded_like",): (f"I work with county open data: {TITLE_C}, {COVERS_C}. I count records, "
                      f"not people, and I never show a single record. {LONG_C}"),
    NAMES: (f"I work with county open data: {TITLE_A}, {COVERS_A}; {TITLE_C}, {COVERS_C}. I "
            f"count records, not people, and I never show a single record. {LONG_A} {LONG_C}"),
}
THREE = NAMES + ("visits_like",)


def notices(env, names):
    """C11: every notice of each source, word for word, in file order, then the course line."""
    lines = []
    for name in names:
        for notice in env.source(name)["notices"]:
            if notice not in lines:
                lines.append(notice)
    return lines + [COURSE_LINE]


def expected(env, text, names):
    return "\n".join([text] + notices(env, names))


def no_describe(env):
    return env.ask(Q_ABOUT, Step(finish("about_data", "Here is what I know.")))


def failing_check(env):
    return env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "Sadly, {f1}.")))


WAYS = {"no describe_data": (no_describe, "fallback"),
        "a text that fails": (failing_check, "fallback")}


def rendering_of_f1(env):
    """C61 addition 5 (point 9b of docs/S3A-DESIGN.md; added by briefs/S3-R23-A-tests.md): a failed
    about_data text that named {f1} is answered `Here is what I know.` and that fact."""
    (answer,) = [a for a in env.answers() if "facts" in a]
    return "Here is what I know. " + answer["facts"][0]["text"]


def assert_about(reply, text, style):
    assert (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", None, "about_data", style), (reply.status, reply.reason_code,
                                                   reply.reply_kind, reply.reply_style)
    assert reply.text == text, f"--- got ---\n{reply.text}\n--- expected ---\n{text}"
    assert list(reply.run_ids) == [] and reply.chart_path is None


def test_premise_the_three_sources_and_their_notices(tmp_path, monkeypatch):
    """No check of C39: the three-source env, and the notices the fixture files hold."""
    env = three_sources(tmp_path, monkeypatch)
    assert [env.source(n)["unit"]["many"] for n in THREE] == \
        ["arrest records", "intake records", "visit records"]
    assert len(notices(env, THREE)) == 5
    assert COURSE_LINE not in [n for name in THREE for n in env.source(name)["notices"]]


# ---- three sources: C39's text, then the notices ---------------------------------------------

@pytest.mark.parametrize("way", list(WAYS))
def test_three_sources_the_short_text_word_for_word_then_the_notices(tmp_path, monkeypatch,
                                                                     way):
    env = three_sources(tmp_path, monkeypatch)
    ask, style = WAYS[way]
    reply = ask(env)
    # Changed by briefs/S3-R23-A-tests.md (C61 addition 5: "Sadly, {f1}." names {f1}, so the reply
    # is that fact, not the short text; it was ABOUT_THREE for both ways).
    text = rendering_of_f1(env) if way == "a text that fails" else ABOUT_THREE
    assert_about(reply, expected(env, text, THREE), style)
    assert LONG_PART not in reply.text
    for sentence in (LONG_A, LONG_C, LONG_V):
        assert sentence not in reply.text


def test_three_sources_with_the_fixed_reply_style(tmp_path, monkeypatch):
    env = add_visits(CountyEnv(tmp_path, monkeypatch, names=NAMES, MOCO_REPLY_STYLE="fixed"))
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    assert_about(reply, expected(env, ABOUT_THREE, THREE), "fixed")


def test_three_sources_one_without_a_copy_the_same_text(tmp_path, monkeypatch):
    """C39-1: <n> counts the sources offered; one with no copy changes nothing."""
    env = add_visits(CountyEnv(tmp_path, monkeypatch, names=NAMES), copy=False)
    reply = no_describe(env)
    assert_about(reply, expected(env, ABOUT_THREE, THREE), "fallback")


def test_three_sources_a_passing_about_text_is_as_today(tmp_path, monkeypatch):
    """Nothing else changes: a passing about_data text is filled from the facts, then the
    notices of every source and the course line.
    Changed by briefs/S3-R26-A-tests.md (C63): "{f1}." is a plain facts text, so it is sent as
    C63's rendering, `Here is what I know.` and the fact (it was the fact alone). The fill of a
    passing text is kept alive with a text that is not plain ("Here is the data. {f1}.", in a
    second thread so its notices are in full too): the fact filled after it, as before."""
    env = three_sources(tmp_path, monkeypatch)
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    (answer,) = [a for a in env.answers() if "facts" in a]
    first = answer["facts"][0]
    assert first["slot"] == "{f1}"
    assert_about(reply, expected(env, "Here is what I know. " + first["text"], THREE), "agent")
    reply = env.ask(Q_ABOUT, Step(describe()),
                    Step(finish("about_data", "Here is the data. {f1}.")), thread_key=THREAD_2)
    assert_about(reply, expected(env, "Here is the data. " + first["text"], THREE), "agent")


def test_three_sources_describe_data_still_covers_every_source(tmp_path, monkeypatch):
    """C39: describe_data and its fact slots are unchanged, so every source's title, dates and
    fields are still there for the follow-up question."""
    env = three_sources(tmp_path, monkeypatch)
    env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    (answer,) = [a for a in env.answers() if "facts" in a]
    facts = [f["text"] for f in answer["facts"]]
    assert [f["slot"] for f in answer["facts"]] == [f"{{f{n}}}" for n in range(1, len(facts) + 1)]
    for name in THREE:
        src = env.source(name)
        assert any(f.startswith(f"My copy of {src['title']} covers ") for f in facts), name
        assert any(f.startswith(f"{src['title']} can be filtered or broken down by ")
                   for f in facts), name
    with_two = CountyEnv(tmp_path / "two", monkeypatch, names=NAMES)
    with_two.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    (two,) = [a for a in with_two.answers() if "facts" in a]
    # Changed by briefs/S3-R23-A-tests.md, as the planning chat's answer to S3-R21-A's question 5
    # ("C61, four corrections before its tests"): only the facts of before C57 are compared, the
    # first seven of each of the first two sources (C57's and C61's facts follow, and the one
    # naming every source differs with three). It compared facts[:len(two["facts"])] whole.
    assert facts[:14] == [f["text"] for f in two["facts"]][:14], \
        "the first two sources' facts are as with two sources"


# ---- one and two sources: as today -----------------------------------------------------------

@pytest.mark.parametrize("way", list(WAYS))
@pytest.mark.parametrize("names", list(TODAY), ids=" and ".join)
def test_one_or_two_sources_as_today(tmp_path, monkeypatch, names, way):
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    ask, style = WAYS[way]
    reply = ask(env)
    # Changed by briefs/S3-R23-A-tests.md (C61 addition 5; it was TODAY[names] for both ways).
    text = rendering_of_f1(env) if way == "a text that fails" else TODAY[names]
    assert_about(reply, expected(env, text, names), style)
    assert "Montgomery County" not in reply.text
