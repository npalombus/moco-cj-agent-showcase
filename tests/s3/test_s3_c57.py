"""C57 of docs/S3A-DESIGN.md: what Nino saw in Slack on 17 Nov (D-075): the list, the districts,
the notice, two lines; with "C57, the exact prompt texts" (after C58). Brief:
briefs/S3-R21-A-tests.md. Tests only: the planning chat builds C57 and edits config/; these
tests are red until then, except those that pin what stays (named in each docstring and in
kit-log/raw/S3-R21-A-notes.txt). Every source here is a SYNTHETIC fixture (tests/s3/fixtures/),
the new keys are added to copies of it in tmp_path, never to a file under config/. Every text
C57 gives is written out here by hand from the contract.

Readings (also in kit-log/raw/S3-R21-A-notes.txt; the open ones are questions in
briefs/QUESTIONS.md, both readings accepted):
- R21-1. Point 3a's `<names>` "as county_about_text joins them today": C39's join (the
  sources by what they count, `unit.many`, joined as join_and does, in file order). OPEN: the
  titles joined the same way are accepted too. `<n>` is written in digits (as C39's text and
  C23's write it); with one source the contract's own words, `one source`.
- R21-2. "Today's facts" are the fact lines describe_data gives today, written out here from
  the program of commit 595e73d (seven per fixture source, in this order); C57 keeps them first
  and unchanged, so {f1} to {f7} (one source) or {f14} (two) or {f21} (three) stay.
- R21-3. Point 2 "texts, not empty": a `notes` list holding an empty sentence, or an empty
  `meaning`, makes the file one the loader does not offer (C20's rule for an empty text).
  "Refuses any other new key as today": today the loader does not look at keys it does not
  know, so nothing here tests another new key (asked in briefs/QUESTIONS.md).
- R21-4. Point 5's reply "carries, in their place, exactly this one line": an about reply is
  its text, a line break, then NOTICES_SHOWN (today: the text, a line break, the notices
  lines); in details the line stands where the notices lines stood (the line after it is the
  run ids line, as today). The stored record is the thread memory's record
  (store.recent_turns, what `_Turn.run` reads).
- R21-5. Point 7's block comes after today's date with a blank line between, as the blocks
  before it are joined; one line break is accepted too.
- R21-6. Point 6 in SYNTHETIC mode is asked (s3support.fallback_lines): county mode must give
  C57's line; here only county mode's reply is pinned.
"""
import json
import os
import re
from datetime import timedelta

import pytest

from p1support import (FAKE_ANTHROPIC_KEY, FAKE_SECRETS, THREAD_1, THREAD_2, USER, Env, Step,
                       count as synthetic_count, describe, finish, make_settings, mod,
                       show_details)
from s3support import (A_ID, FALLBACK_LINE_C57, NAMES, NOW_S3, Q_ABOUT, Q_COUNT, REAL_SOURCES,
                       TODAY_S3, CountyEnv, count, county_fallback_line, source_json, year)
from test_s3_c41 import DECLINED, PASSING, decline_with
from test_s3_round3 import add_visits, three_sources

REPO = REAL_SOURCES.parents[1]
PROMPTS = {"agent_prompt_s3": REPO / "config" / "agent_prompt_s3.md",
           "agent_prompt_s3_talk": REPO / "config" / "agent_prompt_s3_talk.md"}
TALK = ["off", "on"]


@pytest.fixture(autouse=True)
def _no_real_anthropic_variable(monkeypatch):
    """As tests/s3/test_s3_c51.py: no ANTHROPIC_ variable of the real environment is seen."""
    for key in list(os.environ):
        if key.startswith("ANTHROPIC_"):
            monkeypatch.delenv(key)


# ==== the texts, written out by hand from C57 ==================================================

# Point 1.
SHORT_C57 = ('I can count records from 3 county sources, filter them, break them down, compare '
             'counts and give one as a share of another. Ask "what data do you have?" for the '
             'list.')
SHORT_BEFORE = ('I can count records from 3 county sources, filter them, break them down, '
                'compare counts and give one as a share of another. Say "help" for the list.')
# Point 5.
NOTICES_SHOWN = ("The county's data notice and the course-project note shown earlier in this "
                 "thread still apply.")
COURSE_LINE = "This agent is a university course project. It is not a county service."
# Point 7.
ABOUT_YOU = ("About you: you run on {label}. If someone asks what model or company is behind you, "
             "say so plainly, as talk.")
LABELS = {  # (MOCO_MODEL_PROVIDER, the active model id): the label
    ("anthropic", "claude-haiku-5-5"): "a Claude model made by Anthropic",
    ("anthropic", "test-org/anthropic-model-zz"): "a model served by Anthropic",
    ("nvidia", "nvidia/nemotron-3-ultra-550b-a55b"): "a Nemotron model made by NVIDIA",
    ("nvidia", "test-org/nvidia-model-zz"): "a model served by NVIDIA",
}
# "C57, the exact prompt texts".
START_LINE = ('- Start with "Here is what I know." and nothing else before the slots. Never write '
              'a fact in your own words. Write it all on one line.')
C57_PROMPT_LINE = ('- For a question about which sources or what data there is, use the fact that '
                   'names every source. For what a field means or where the records come from, '
                   'use the fact that says so.')
RULE12_BEFORE = "a question about you or about what you can do"
# C61 point 3 (added by briefs/S3-R23-A-tests.md): the "About you" block's second sentence.
C61_POINT_3 = ("For any question about you, this project, its rules or where something comes from, "
               "call describe_data and answer with its facts about you; never answer such a "
               "question from your own head, and never take back a rule the program applies.")
RULE12_C57 = "a question about you (what you are, what model you run on) or about what you can do"
# Point 8, the 13 real source files (Nino's approval, D-075).
REAL_NOTES = ["These are Montgomery County, Maryland's own police records, published by the "
              "county. They are not statewide Maryland records."]
WEAPON_NOTE = ("The county's weapon pointing file holds only a few records for each month before "
               "February 2022, against many more from then on, so I count from 1 February 2022 "
               "and leave the earlier ones out.")
DISTRICT_MEANING = ('the police district where it happened (the county calls the field '
                    '"District of occurrence")')
# Changed by briefs/S3-R23-A-tests.md: "C61, two additions after the threads", point 7 (17 Nov 17:37
# EST), changes the field's first note. It was "Montgomery County Police names six districts by
# their stations: district 1 is Rockville, ... and district 6 is Montgomery Village."
SIX_DISTRICTS = ("The districts are police districts. Montgomery County Police names six of them "
                 "by their stations: district 1 is Rockville, district 2 is Bethesda, district 3 "
                 "is Silver Spring, district 4 is Wheaton, district 5 is Germantown and district "
                 "6 is Montgomery Village.")
DISTRICT_8 = ("Some records carry a district 8. It is not one of the six districts the county "
              "names, and the county's data does not say what it is.")

# ==== today's facts (R21-2), written out from the program of commit 595e73d ===================

TITLE = {"arrests_like": "SYNTHETIC fixture arrests (made up for tests)",
         "coded_like": "SYNTHETIC fixture intake records (made up for tests)",
         "visits_like": "SYNTHETIC fixture visits (made up for tests)"}
UNITS = {"arrests_like": "arrest records", "coded_like": "intake records",
         "visits_like": "visit records"}
_FLOOR_FACT = ("Counts under 10 are shown as fewer than 10. That is about what I say, not a "
               "secret: the county's open data has every record.")
TODAY_FACTS = {
    "arrests_like": [
        "SYNTHETIC fixture arrests (made up for tests) is published by SYNTHETIC fixture "
        "publisher (made up for tests). One record is one made-up arrest, and I count arrest "
        "records, not people.",
        "My copy of SYNTHETIC fixture arrests (made up for tests) covers 1 January 2024 to 17 "
        "September 2026 and was saved on 12 November 2026.",
        "SYNTHETIC fixture arrests (made up for tests) can be filtered or broken down by age, "
        "gender, race, ethnicity, district, distance from a school, year, month, day of the "
        "week and hour.",
        "A count of SYNTHETIC fixture arrests (made up for tests) is of arrest records. It is "
        "not people, charges, cases, convictions, sentences or a rate.",
        _FLOOR_FACT,
        "A record with no value for a field a question uses, or an age outside 10 to 98, is "
        "left out of that count, and I say how many were left out.",
        "Nothing else can be asked of SYNTHETIC fixture arrests (made up for tests): no names, "
        "no addresses, and never a single record.",
    ],
    "coded_like": [
        "SYNTHETIC fixture intake records (made up for tests) is published by SYNTHETIC fixture "
        "publisher (made up for tests). One record is one made-up intake, and I count intake "
        "records, not people.",
        "My copy of SYNTHETIC fixture intake records (made up for tests) covers 1 January 2025 "
        "to 20 August 2026 and was saved on 12 November 2026.",
        "SYNTHETIC fixture intake records (made up for tests) can be filtered or broken down by "
        "age, race, sex, station, year, month, day of the week and hour.",
        "A count of SYNTHETIC fixture intake records (made up for tests) is of intake records. "
        "It is not people, charges, cases or a rate.",
        _FLOOR_FACT,
        "A record with no value for a field a question uses, or an age outside 12 to 90, is "
        "left out of that count, and I say how many were left out.",
        "Nothing else can be asked of SYNTHETIC fixture intake records (made up for tests): no "
        "names, no addresses, and never a single record.",
    ],
    "visits_like": [
        "SYNTHETIC fixture visits (made up for tests) is published by SYNTHETIC fixture "
        "publisher (made up for tests). One record is one made-up visit, and I count visit "
        "records, not people.",
        "My copy of SYNTHETIC fixture visits (made up for tests) covers 1 January 2025 to 28 "
        "June 2026 and was saved on 12 November 2026.",
        "SYNTHETIC fixture visits (made up for tests) can be filtered or broken down by area, "
        "year, month, day of the week and hour.",
        "A count of SYNTHETIC fixture visits (made up for tests) is of visit records. It is not "
        "people, cases or a rate.",
        _FLOOR_FACT,
        "A record with no value for a field a question uses is left out of that count, and I "
        "say how many were left out.",
        "Nothing else can be asked of SYNTHETIC fixture visits (made up for tests): no names, no "
        "addresses, and never a single record.",
    ],
}

# ==== the new keys on copies of the fixture sources (SYNTHETIC texts) ===========================

A_NOTES = ["SYNTHETIC fixture note: these made-up records come from no county.",
           "SYNTHETIC shared note: every record in these fixtures is made up."]
C_NOTES = ["SYNTHETIC shared note: every record in these fixtures is made up.",  # shared with A
           "SYNTHETIC coded note: the codes stand for made-up groups."]
A_DISTRICT_MEANING = "the made-up district a SYNTHETIC record is filed under"
A_SCHOOL_MEANING = "whether a SYNTHETIC record is near a made-up school"
C_STATION_MEANING = "the made-up station a SYNTHETIC intake is filed at"
A_DISTRICT_NOTES = ["SYNTHETIC district note: the six fixture districts are made up.",
                    "SYNTHETIC shared field note: no fixture field is real."]
C_STATION_NOTES = ["SYNTHETIC shared field note: no fixture field is real.",  # shared with A
                   "SYNTHETIC station note: the fixture stations are made up."]
ALL_KEYS = ("notes", "meaning", "field_notes")


def _field(data, name):
    (found,) = [f for f in data["fields"] if f["name"] == name]
    return found


def keys_for(name, which=ALL_KEYS):
    """A change for CountyEnv: the new keys of point 2 named in `which`, added to a copy of the
    fixture source `name`."""
    def change(data):
        if name == "arrests_like":
            if "notes" in which:
                data["notes"] = list(A_NOTES)
            if "meaning" in which:
                _field(data, "district")["meaning"] = A_DISTRICT_MEANING
                _field(data, "adjacent_to_school")["meaning"] = A_SCHOOL_MEANING
            if "field_notes" in which:
                _field(data, "district")["notes"] = list(A_DISTRICT_NOTES)
        else:
            if "notes" in which:
                data["notes"] = list(C_NOTES)
            if "meaning" in which:
                _field(data, "station")["meaning"] = C_STATION_MEANING
            if "field_notes" in which:
                _field(data, "station")["notes"] = list(C_STATION_NOTES)
    return change


def all_sources_facts(names):
    """Point 3a, both readings of R21-1: the names by what they count, or the titles."""
    out = []
    for words in ([UNITS[n] for n in names], [TITLE[n] for n in names]):
        joined = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
        out.append(f"I work with one source of Montgomery County open data: {joined}."
                   if len(names) == 1 else
                   f"I work with {len(names)} sources of Montgomery County open data: {joined}.")
    return out


def new_facts(names, which=ALL_KEYS):
    """Points 3b to 3d for the fixture sources `names`, each with the keys `which` (visits_like
    never has any), in C57's order."""
    b, c, d = [], [], []
    for name in names:
        if name == "arrests_like":
            b += A_NOTES if "notes" in which else []
            if "meaning" in which:
                c += [f"In {TITLE[name]}, district is {A_DISTRICT_MEANING}.",
                      f"In {TITLE[name]}, distance from a school is {A_SCHOOL_MEANING}."]
            d += A_DISTRICT_NOTES if "field_notes" in which else []
        elif name == "coded_like":
            b += C_NOTES if "notes" in which else []
            c += [f"In {TITLE[name]}, station is {C_STATION_MEANING}."] if "meaning" in which \
                else []
            d += C_STATION_NOTES if "field_notes" in which else []
    once = lambda items: list(dict.fromkeys(items))  # noqa: E731
    return once(b) + c + once(d)


def assert_facts(facts, names, which=ALL_KEYS):
    """Point 3: today's facts first and unchanged, then a, b, c, d in order. Changed by
    briefs/S3-R23-A-tests.md (C61 point 2: a turn passes its settings, so the facts e to h of C61
    now follow d; they are checked in tests/s3/test_s3_c61a.py): it was "then a, b, c, d in order,
    nothing else" (texts[len(today) + 1:] == new_facts(...))."""
    today = [line for name in names for line in TODAY_FACTS[name]]
    texts = [f["text"] for f in facts]
    assert texts[:len(today)] == today, "today's facts are not first and unchanged"
    assert len(texts) > len(today), "no fact after today's (point 3a is always there)"
    assert texts[len(today)] in all_sources_facts(names), texts[len(today)]
    new = new_facts(names, which)
    assert texts[len(today) + 1:len(today) + 1 + len(new)] == new, texts[len(today):]
    assert [f["slot"] for f in facts] == [f"{{f{n}}}" for n in range(1, len(facts) + 1)]


# ==== turns ======================================================================================

ABOUT = "Here is what I know. {f1}."


def about_turn(env, text=ABOUT, **kw):
    return env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", text)), **kw)


def facts_of(env):
    (answer,) = [a for a in env.answers() if "facts" in a]
    return answer["facts"]


def full_notices(env, names):
    """C11 as today: each distinct notice of the sources, word for word, then the course line."""
    lines = list(dict.fromkeys(n for name in names for n in env.source(name)["notices"]))
    return lines + [COURSE_LINE]


def assert_full_about(reply, env, names=("arrests_like",)):
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.endswith("\n" + "\n".join(full_notices(env, names))), reply.text
    assert NOTICES_SHOWN not in reply.text, reply.text


def assert_short_about(reply, env, names=("arrests_like",)):
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.endswith("\n" + NOTICES_SHOWN), reply.text
    assert reply.text.count(NOTICES_SHOWN) == 1, reply.text
    for line in full_notices(env, names):
        assert line not in reply.text, f"the full notices are in the short reply: {line!r}"


def assert_full_details(reply, env, names=("arrests_like",)):
    assert (reply.status, reply.reason_code) == ("DETAILS", None), (reply.status, reply.text)
    lines = reply.text.split("\n")
    for line in full_notices(env, names):
        assert line in lines, f"{line!r} is not a line of the details"
    assert NOTICES_SHOWN not in reply.text, reply.text


def assert_short_details(reply, env, names=("arrests_like",)):
    assert (reply.status, reply.reason_code) == ("DETAILS", None), (reply.status, reply.text)
    lines = reply.text.split("\n")
    assert lines.count(NOTICES_SHOWN) == 1, reply.text
    after = lines[lines.index(NOTICES_SHOWN) + 1:]
    assert after and after[0].startswith("Run ids: "), "the line is not where the notices were"
    for line in full_notices(env, names):
        assert line not in reply.text, f"the full notices are in the short details: {line!r}"


def records(env, thread_key=THREAD_1):
    """The stored records of the thread (what `_Turn.run` reads), oldest first."""
    return env.store.recent_turns(thread_key, 100)


def count_turn(env, **kw):
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")), **kw)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def details_turn(env, **kw):
    return env.ask("details", Step(show_details()), **kw)


def old_style_turn(env, thread_key=THREAD_1, notices=None, minutes_before=30):
    """A turn stored as today's program stores it (no `notices` key): an about_data turn
    answered EXPLAINED. With `notices`, that key is put in its record."""
    record = {"turn_id": "T-old-style-1", "guard_code": None, "model_id": "fake-org/fake-model-1",
              "steps": 2, "results": [],
              "carried": {"source": False, "period": False, "filters": False},
              "pending": None, "missing": None, "reply_kind": "about_data",
              "reply_style": "agent", "reply_text": ABOUT}
    if notices is not None:
        record["notices"] = notices
    env.store.add_turn(thread_key=thread_key, user_id=USER, question=Q_ABOUT,
                       status="EXPLAINED", reason_code=None,
                       created_at=NOW_S3 - timedelta(minutes=minutes_before), record=record)


# ==== point 1: the sentence that ends a refusal =================================================

def test_point1_premise_the_sentence_is_todays_with_its_last_sentence_changed():
    assert SHORT_C57 == SHORT_BEFORE.replace('Say "help" for the list.',
                                             'Ask "what data do you have?" for the list.')


@pytest.mark.parametrize("talk", TALK)
def test_point1_a_refusal_with_three_sources_ends_with_c57s_sentence(tmp_path, monkeypatch,
                                                                     talk):
    """Point 1, word for word, talk off (the row) and on (C41's own words, then the row's
    sentences after the first)."""
    env = add_visits(CountyEnv(tmp_path, monkeypatch, names=NAMES, MOCO_TALK=talk))
    step = decline_with("UNSUPPORTED_METRIC", PASSING["one sentence"]) if talk == "on" else \
        decline_with("UNSUPPORTED_METRIC")
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(step))
    assert reply.reason_code == "UNSUPPORTED_METRIC", (reply.status, reply.text)
    assert reply.text.endswith(" " + SHORT_C57), reply.text
    assert reply.text.count(SHORT_C57) == 1 and 'Say "help"' not in reply.text, reply.text


def test_point1_replies_county_can_ask_word_for_word(tmp_path, monkeypatch):
    env = three_sources(tmp_path, monkeypatch)
    assert mod("replies").county_can_ask(mod("sources").county_sources()) == SHORT_C57


# ==== point 2: the new keys through the loader ==================================================

KEY_SETS = {"none": (), "notes": ("notes",), "meaning": ("meaning",),
            "field_notes": ("field_notes",), "all": ALL_KEYS}


def loaded(tmp_path, change):
    folder = tmp_path / "loader"
    folder.mkdir()
    data = source_json("arrests_like")
    change(data)
    (folder / "arrests_like.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return mod("sources").load_sources(folder)


@pytest.mark.parametrize("which", list(KEY_SETS))
def test_point2_a_file_with_or_without_each_new_key_loads(tmp_path, which):
    """Point 2: the keys are optional and accepted. Passes today too (today's loader does not
    look at keys it does not know): it pins that the build still offers such a file."""
    assert A_ID in loaded(tmp_path, keys_for("arrests_like", KEY_SETS[which]))


EMPTY = {
    "an empty sentence in notes": lambda d: d.update(notes=["SYNTHETIC fixture note.", " "]),
    "an empty meaning": lambda d: _field(d, "district").update(meaning=""),
    "an empty sentence in a field's notes": lambda d: _field(d, "district").update(notes=[""]),
    "a meaning that is not a text": lambda d: _field(d, "district").update(meaning=3),
}


@pytest.mark.parametrize("case", list(EMPTY))
def test_point2_an_empty_text_is_not_accepted(tmp_path, case):
    """Point 2 "texts, not empty", read with C20 (R21-3): the file is not offered and the reason
    is kept. Red today."""
    assert A_ID not in loaded(tmp_path, EMPTY[case]), case
    assert mod("sources").why_invalid(A_ID) is not None


# ==== point 3: the facts ========================================================================

@pytest.mark.parametrize("which", list(KEY_SETS))
def test_point3_one_source_with_and_without_each_key(tmp_path, monkeypatch, which):
    """Point 3: today's seven facts first and unchanged, then the all-sources fact, then b to d
    for the keys there are (none: the all-sources fact only)."""
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": keys_for(
        "arrests_like", KEY_SETS[which])})
    about_turn(env)
    assert_facts(facts_of(env), ("arrests_like",), KEY_SETS[which])


def test_point3_two_sources_in_order_with_a_shared_note_once(tmp_path, monkeypatch):
    """Point 3: a; b in file order, the note both sources hold once; c by source then field
    order (district before distance from a school, then the second source's station); d in
    file and field order, the field note both hold once."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES,
                    change={n: keys_for(n) for n in NAMES})
    about_turn(env)
    facts = facts_of(env)
    assert_facts(facts, NAMES)
    texts = [f["text"] for f in facts]
    assert texts.count(A_NOTES[1]) == 1 and texts.count(A_DISTRICT_NOTES[1]) == 1


@pytest.mark.parametrize("names", [("arrests_like",), ("coded_like",), NAMES],
                         ids=["one", "the other one", "two"])
def test_point3a_the_all_sources_fact_with_one_and_two_sources(tmp_path, monkeypatch, names):
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    about_turn(env)
    facts = [f["text"] for f in facts_of(env)]
    today = [line for name in names for line in TODAY_FACTS[name]]
    assert facts[:len(today)] == today
    # Changed by briefs/S3-R23-A-tests.md (C61 point 2: e to h follow): it was
    # facts[len(today):] in ([f] for f in all_sources_facts(names)), the one fact alone after
    # today's.
    assert facts[len(today)] in all_sources_facts(names), facts[len(today):]


def test_point3a_the_all_sources_fact_with_three_sources(tmp_path, monkeypatch):
    """Three sources, the third with none of the new keys and the first two with all."""
    env = add_visits(CountyEnv(tmp_path, monkeypatch, names=NAMES,
                               change={n: keys_for(n) for n in NAMES}))
    names = NAMES + ("visits_like",)
    about_turn(env)
    facts = facts_of(env)
    assert_facts(facts, names)
    assert facts[21]["text"] in all_sources_facts(names)
    assert facts[21]["text"].startswith("I work with 3 sources of Montgomery County open data: ")


def all_sources_slot(env, names):
    """A premise: the slot of the all-sources fact is the first after today's facts."""
    facts = facts_of(env)
    n = sum(len(TODAY_FACTS[name]) for name in names) + 1
    assert len(facts) >= n, "no fact after today's: no all-sources fact"
    assert facts[n - 1]["text"] in all_sources_facts(names), facts[n - 1]
    return f"{{f{n}}}", facts[n - 1]["text"]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("n", [2, 3])
def test_point3_an_about_text_with_the_all_sources_slot_is_sent_with_every_name(
        tmp_path, monkeypatch, n, talk):
    """Point 3 ("usable in an about_data text, checked as today") and its test: the about_data
    turn whose text uses the all-sources slot is answered with it filled, naming every
    source; talk off and on."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES, MOCO_TALK=talk)
    names = NAMES
    if n == 3:
        add_visits(env)
        names = NAMES + ("visits_like",)
    about_turn(env)  # a first turn, to read the slot number
    slot, text = all_sources_slot(env, names)
    reply = about_turn(env, f"Here is what I know. {slot}.", thread_key=THREAD_2)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style, reply.text)
    assert reply.text.startswith(f"Here is what I know. {text}"), reply.text
    for name in names:
        assert UNITS[name] in reply.text or TITLE[name] in reply.text, name


# ==== point 4 and "the exact prompt texts": the two county prompts ==============================

def prompt_lines(name):
    return PROMPTS[name].read_bytes().decode("utf-8").split("\n")


@pytest.mark.parametrize("name", list(PROMPTS))
def test_point4_the_added_line_directly_after_the_start_line(name):
    lines = prompt_lines(name)
    assert lines.count(START_LINE) == 1, "premise: the line it follows"
    assert lines.count(C57_PROMPT_LINE) == 1, f"C57's line is not in {name} once"
    assert lines[lines.index(START_LINE) + 1] == C57_PROMPT_LINE, "not directly after"


def test_point7_rule_12_of_the_talk_prompt_names_the_model():
    text = PROMPTS["agent_prompt_s3_talk"].read_text(encoding="utf-8")
    (rule12,) = [line for line in text.split("\n") if line.startswith("12. ")]
    assert RULE12_C57 in rule12 and text.count(RULE12_C57) == 1, rule12
    assert RULE12_BEFORE not in text


def test_point7_the_other_county_prompt_keeps_its_words_about_him():
    """The exact prompt texts: rule 12's change is in agent_prompt_s3_talk.md only. Passes today."""
    text = PROMPTS["agent_prompt_s3"].read_text(encoding="utf-8")
    assert RULE12_C57 not in text and "what model you run on" not in text


# ==== point 5: the notices once a thread ========================================================

def test_point5_notices_shown_word_for_word():
    assert mod("replies").NOTICES_SHOWN == NOTICES_SHOWN


@pytest.mark.parametrize("talk", TALK)
def test_point5_one_thread_full_then_short(tmp_path, monkeypatch, talk):
    """C57's test: the first about_data reply full, the second and third short with the one
    line, a details reply after them short; the stored records "full", "short", "short", none
    for the count, "short"."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    assert_full_about(about_turn(env), env)
    assert_short_about(about_turn(env), env)
    assert_short_about(about_turn(env), env)
    count_turn(env)
    assert_short_details(details_turn(env), env)
    found = [r.get("notices", "no key") for r in records(env)]
    assert found == ["full", "short", "short", "no key", "short"], found
    assert "notices" not in records(env)[3]


@pytest.mark.parametrize("talk", TALK)
def test_point5_another_thread_is_full_again(tmp_path, monkeypatch, talk):
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    assert_full_about(about_turn(env), env)
    assert_short_about(about_turn(env), env)
    assert_full_about(about_turn(env, thread_key=THREAD_2), env)
    assert [r.get("notices") for r in records(env, THREAD_2)] == ["full"]


@pytest.mark.parametrize("talk", TALK)
def test_point5_a_thread_with_an_old_style_turn_is_full(tmp_path, monkeypatch, talk):
    """C57's test: an EXPLAINED about_data turn stored before C57 (no `notices` key): the next
    about_data reply carries the notices in full and is stored "full"."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    old_style_turn(env)
    assert_full_about(about_turn(env), env)
    found = [r.get("notices", "no key") for r in records(env)]
    assert found == ["no key", "full"], found


def test_point5_a_turn_that_carries_neither_has_no_key(tmp_path, monkeypatch):
    """Point 5: a count turn and a refusal hold no `notices` key (as today: passes today)."""
    env = CountyEnv(tmp_path, monkeypatch)
    count_turn(env)
    env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(decline_with("UNSUPPORTED_METRIC")))
    assert [("notices" in r) for r in records(env)] == [False, False]


@pytest.mark.parametrize("names", [("arrests_like",), NAMES], ids=["one source", "two sources"])
def test_point5_the_short_about_reply_is_the_text_then_the_one_line(tmp_path, monkeypatch,
                                                                    names):
    """R21-4: the second reply is its about text and the one line in the notices' place: the
    same text as the first reply, with the notices lines replaced by NOTICES_SHOWN."""
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    first, second = about_turn(env), about_turn(env)
    tail = "\n" + "\n".join(full_notices(env, names))
    assert first.text.endswith(tail), first.text
    assert second.text == first.text[:-len(tail)] + "\n" + NOTICES_SHOWN, second.text


# ==== point 6: the stock line of a talk text ====================================================

def test_point6_the_fallback_line_word_for_word():
    rules = json.loads((REPO / "config" / "talk_rules.json").read_text(encoding="utf-8"))
    assert rules["fallback_line"] == FALLBACK_LINE_C57


def test_point6_a_county_talk_text_that_fails_gets_c61s_line(tmp_path, monkeypatch):
    """Changed by briefs/S3-R23-A-tests.md (C61 point 9: in county mode the line is `I can't put
    that in words I can back up. ` and county_can_ask; C57 point 6's line stays the stage 1 line).
    It was test_point6_a_county_talk_text_that_fails_twice_gets_c57s_line, the reply in
    fallback_lines(county=True)."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on")
    failing = "Most of them were group Gamma."  # LABEL, at every try
    reply = env.ask("hello", Step(finish("talk", failing)), Step(finish("talk", failing)))
    assert (reply.status, reply.reply_style) == ("TALKED", "fallback"), reply.text
    assert reply.text == county_fallback_line(1), reply.text


# ==== point 7: which model he runs on ===========================================================

def model_settings(provider, model):
    return {"MOCO_MODEL_PROVIDER": provider, "NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"],
            "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY,
            ("ANTHROPIC_MODEL" if provider == "anthropic" else "NVIDIA_MODEL"): model}


def system_of(env):
    messages = env.model.calls[0]["messages"]
    assert messages[0]["role"] == "system", messages[0]
    return messages[0]["content"]


@pytest.mark.parametrize("case", list(LABELS), ids=list(LABELS.values()))
def test_point7_model_label(tmp_path, case):
    settings = make_settings(tmp_path, **model_settings(*case))
    assert mod("replies").model_label(settings) == LABELS[case]


@pytest.mark.parametrize("case", list(LABELS), ids=list(LABELS.values()))
def test_point7_the_block_ends_the_county_system_message_with_talk_on(tmp_path, monkeypatch,
                                                                      case):
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", **model_settings(*case))
    env.ask("hello", Step(finish("talk", "Hello! Ask me for a count whenever you like.")))
    system = system_of(env)
    block = ABOUT_YOU.format(label=LABELS[case])
    # Changed by briefs/S3-R23-A-tests.md (C61 point 3: the block gains a second sentence, after
    # one space or a line break): it was block + r"\Z".
    assert re.search(re.escape(f"Today's date: {TODAY_S3:%Y-%m-%d}") + r"\n\n?"
                     + re.escape(block) + r"[ \n]" + re.escape(C61_POINT_3) + r"\Z", system), \
        system[-700:]
    assert system.count("About you:") == 1


@pytest.mark.parametrize("case", list(LABELS)[::3], ids=list(LABELS.values())[::3])
def test_point7_no_block_with_talk_off(tmp_path, monkeypatch, case):
    """The exact prompt texts: with talk off the county system message is as today (it ends
    with today's date). Passes today."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="off", **model_settings(*case))
    env.ask(Q_COUNT, Step(count(A_ID, year(2025))),
            Step(finish("finding", "I counted {r1.count}.")))
    system = system_of(env)
    assert system.endswith(f"Today's date: {TODAY_S3:%Y-%m-%d}") and "About you:" not in system


@pytest.mark.parametrize("talk", TALK)
def test_point7_no_block_in_the_stage_1_system_message(tmp_path, talk):
    """C57's test: absent in the stage 1 (SYNTHETIC) system message, talk off and on. Passes
    today."""
    env = Env(tmp_path, MOCO_TALK=talk, **model_settings("anthropic", "claude-haiku-5-5"))
    env.ask("How many arrests were there in 2025 for people under 18?",
            Step(synthetic_count(2025, "under_18")),
            Step(finish("finding", "I counted {r1.count}.")))
    system = system_of(env)
    assert "About you:" not in system and "a Claude model made by Anthropic" not in system


@pytest.mark.parametrize("case", list(LABELS), ids=list(LABELS.values()))
def test_point7_a_talk_text_with_the_label_passes(tmp_path, monkeypatch, case):
    """Point 7: a talk text holding a label passes the talk checks as far as the label goes,
    and is sent as written. Passes today (no label fails a check today)."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", **model_settings(*case))
    text = f"I run on {LABELS[case]}. Ask me for a count whenever you like."
    reply = env.ask("what model do you run on?", Step(finish("talk", text)))
    assert (reply.status, reply.reply_style, reply.text) == ("TALKED", "agent", text), \
        (reply.reply_style, reply.draft_failures, reply.text)


# ==== point 8: the 13 source files ==============================================================

REAL_FILES = sorted(REAL_SOURCES.glob("*.json"))


def test_point8_premise_thirteen_files():
    assert len(REAL_FILES) == 13


@pytest.mark.parametrize("path", REAL_FILES, ids=[p.stem for p in REAL_FILES])
def test_point8_each_real_file_loads(path):
    """Each file under config/sources/ loads (C20: no problem found). Passes today."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert mod("sources").problems(data) == []
    assert data["id"] in mod("sources").load_sources(REAL_SOURCES)


@pytest.mark.parametrize("path", REAL_FILES, ids=[p.stem for p in REAL_FILES])
def test_point8_each_real_file_holds_the_keys(path):
    """Point 8, word for word: the top-level notes; the district field's meaning; its notes, with
    the district 8 sentence only in a file whose district values hold a district 8."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # Turned round for C75 (D-093, planning chat, 21 Nov 2026): weapon pointing adds one note
    # saying why it counts from 1 February 2022.
    extra = [WEAPON_NOTE] if path.stem == "weapon_pointing" else []
    assert data.get("notes") == REAL_NOTES + extra, data.get("notes")
    district = _field(data, "district")
    assert district.get("meaning") == DISTRICT_MEANING, district.get("meaning")
    eight = "district 8" in district["values"].values()
    assert district.get("notes") == [SIX_DISTRICTS] + ([DISTRICT_8] if eight else []), \
        district.get("notes")


# ==== six tests of this session's own, which C57's words decide ==================================

def test_own_1_a_full_turn_outside_the_memory_window_does_not_count(tmp_path, monkeypatch):
    """Point 5 "the turns `_Turn.run` reads": with a memory window of 60 minutes, a full turn
    two hours earlier is not read, so the next reply carries the notices in full."""
    env = CountyEnv(tmp_path, monkeypatch)
    assert_full_about(about_turn(env, now=NOW_S3, memory_minutes=60), env)
    assert_full_about(about_turn(env, now=NOW_S3 + timedelta(hours=2), memory_minutes=60), env)
    assert_short_about(about_turn(env, now=NOW_S3 + timedelta(hours=2, minutes=5),
                                  memory_minutes=60), env)
    assert [r.get("notices") for r in records(env)] == ["full", "full", "short"]


def test_own_2_earlier_short_turns_alone_do_not_count(tmp_path, monkeypatch):
    """Point 5 "when no earlier turn ... carried them in full": a thread whose history holds
    only a turn stored "short" (its full turn gone) gets them in full."""
    env = CountyEnv(tmp_path, monkeypatch)
    old_style_turn(env, notices="short")
    assert_full_about(about_turn(env), env)
    assert [r.get("notices") for r in records(env)] == ["short", "full"]


def test_own_3_every_kind_of_about_reply_goes_short(tmp_path, monkeypatch):
    """Point 5 "a reply that would carry the notices": after a full reply, the fixed about
    reply of a failing text and of a turn with no describe_data are short too."""
    env = CountyEnv(tmp_path, monkeypatch)
    assert_full_about(about_turn(env), env)
    failing = about_turn(env, "Here is zqx. {f1}.")
    assert failing.reply_style == "fallback", failing.reply_style
    assert_short_about(failing, env)
    plain = env.ask(Q_ABOUT, Step(finish("about_data", "Here is zqx.")))
    assert plain.reply_style == "fallback", plain.reply_style
    assert_short_about(plain, env)
    assert [r.get("notices") for r in records(env)] == ["full", "short", "short"]


def test_own_4_details_first_then_about(tmp_path, monkeypatch):
    """Point 5: the first reply of a thread that carries the notices is a details reply: full
    and stored "full"; an about_data reply after it is short."""
    env = CountyEnv(tmp_path, monkeypatch)
    count_turn(env)
    assert_full_details(details_turn(env), env)
    assert_short_about(about_turn(env), env)
    assert [r.get("notices", "no key") for r in records(env)] == ["no key", "full", "short"]


def test_own_5_synthetic_mode_is_unchanged(tmp_path):
    """C57 "County mode only": in SYNTHETIC mode two about_data replies of one thread are the
    same text, and neither stored record has a `notices` key. Passes today."""
    env = Env(tmp_path)
    first = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    second = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    assert first.status == second.status == "EXPLAINED"
    assert second.text == first.text and NOTICES_SHOWN not in second.text
    assert not any("notices" in r for r in env.store.recent_turns(THREAD_1, 10))


@pytest.mark.parametrize("talk", TALK)
def test_own_6_the_new_facts_are_four_at_most_like_any_other(tmp_path, monkeypatch, talk):
    """Point 3 "a fact like any other ... at most four a reply": an about text with the four
    new kinds (a, b, c, d) passes and is sent filled; with a fifth fact it fails and the
    fixed reply is sent."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk,
                    change={"arrests_like": keys_for("arrests_like")})
    about_turn(env)
    facts = facts_of(env)
    texts = [f["text"] for f in facts]
    # Changed by briefs/S3-R23-A-tests.md (C61 point 2: e to h follow d): it was len(texts) == 14.
    assert len(texts) >= 7 + 1 + 2 + 2 + 2, "premise: today's seven, then a, b, c and d"
    assert texts[8:14] == new_facts(("arrests_like",)), "premise: b, c and d are f9 to f14"
    picks = [8, 9, 11, 13]  # a; b's first; c's first; d's first (after today's seven)
    assert [texts[n - 1] for n in picks[1:]] == [
        A_NOTES[0], f"In {TITLE['arrests_like']}, district is {A_DISTRICT_MEANING}.",
        A_DISTRICT_NOTES[0]]
    four = " ".join(f"{{f{n}}}." for n in picks)  # four sentences: R1's most with talk off
    reply = about_turn(env, four, thread_key=THREAD_2)
    assert reply.reply_style == "agent", (reply.reply_style, reply.draft_failures)
    for n in picks:
        assert texts[n - 1].rstrip(".") in reply.text
    # Changed by briefs/S3-R26-A-tests.md (C63): `five` is a plain facts text, so it is not
    # checked: the first four are sent, style agent, no failure (it failed SHAPE, style fallback).
    # The limit of four is kept alive with a text that is not plain, one word of its own ("Also"):
    # it fails SHAPE and the fixed reply is sent, as before.
    five = four + " {f1}."
    reply = about_turn(env, five, thread_key=THREAD_2)
    assert (reply.reply_style, list(reply.draft_failures)) == ("agent", []), \
        (reply.reply_style, reply.draft_failures, reply.text)
    assert reply.text.split("\n")[0] == " ".join(
        ["Here is what I know."] + [texts[n - 1] for n in picks]), reply.text
    reply = about_turn(env, "Also " + five, thread_key=THREAD_2)
    assert reply.reply_style == "fallback", (reply.reply_style, reply.text)
    assert "SHAPE" in reply.draft_failures, reply.draft_failures
