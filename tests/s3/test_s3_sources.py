"""Source files and the fixtures: docs/S3A-DESIGN.md C3 (source files) and C4's
`load_sources`, and the premises every other stage 3 test stands on (brief S3A-A steps 3
and 4).

What this file covers
- sources.load_sources(folder=None) -> dict by id: the default folder is config/sources
  (it holds MOCO:police_arrests); a folder given is read; every *.json file in it is one
  source, keyed by its id, carrying what its file says; a changed file is read as changed.
- "Nothing about a source lives in code" (C3): a source file with another unit, wording and
  dimension changes what a county answer says, word for word.
- The fixtures themselves (these pass today, and must keep passing): they are SYNTHETIC
  and plainly made up (ids start FIXTURE-, addresses on the reserved .invalid domain, titles
  and notices say SYNTHETIC); each source file has C3's shape; make_fixtures.py makes the
  same rows again from its seed; the truth (s3support.truth, plain counting) gives every
  value that make_fixtures.py designed; the questions the tests use pass stage 1's guard.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- What load_sources gives for each id is not named beyond "dict by id": each value is
  checked only to carry its file's title, unit and floor somewhere (p1support
  reachable_values), as a dict or an object.

Not checked here: fetch and copies (test_s3_fetch.py), counting (test_s3_count_spec.py).
"""
import calendar
import json
import random
import re
from datetime import date
from pathlib import Path

import pytest

from p1support import Step, finish, mod, reachable_values
from s3support import (A_ID, C_ID, FIXTURE_ROWS, FIXTURE_SOURCES, NAMES, Q_ABOUT, Q_BREAKDOWN,
                       Q_COMPARE, Q_COUNT, Q_FOLLOW, Q_SHARE, REAL_SOURCES, SCHOOL, CountyEnv,
                       assert_reply, count, fixture_rows, guard_free, hidden_line, in_, is_,
                       left_out_line, row_id, shown, source_json, source_re, table_lines,
                       truth, write_sources, year, years)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def load_make_fixtures():
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_fixtures_for_test",
                                                  FIXTURES / "make_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def carries(value, *expected):
    found = {v for v in reachable_values(value) if isinstance(v, (str, int))}
    missing = [e for e in expected if e not in found]
    assert not missing, f"not carried: {missing}"


# ---- load_sources (C4) ---------------------------------------------------------------------

def test_load_sources_reads_config_sources_by_default():
    """C4: load_sources(folder=None) reads config/sources/*.json, a dict by id."""
    loaded = mod("sources").load_sources()
    ids = {json.loads(p.read_text(encoding="utf-8"))["id"] for p in REAL_SOURCES.glob("*.json")}
    assert "MOCO:police_arrests" in ids
    assert set(loaded) == ids
    real = json.loads((REAL_SOURCES / "police_arrests.json").read_text(encoding="utf-8"))
    carries(loaded["MOCO:police_arrests"], real["title"], real["unit"]["many"], real["floor"])


def test_load_sources_reads_the_folder_it_is_given():
    """C4: a folder given is read: both fixtures, by id, each carrying its file."""
    loaded = mod("sources").load_sources(FIXTURE_SOURCES)
    assert set(loaded) == {A_ID, C_ID}
    for name in NAMES:
        data = source_json(name)
        carries(loaded[data["id"]], data["title"], data["unit"]["many"], data["page"],
                data["address"], data["time_field"])


def test_load_sources_reads_a_changed_file_as_changed(tmp_path):
    """C3: nothing about a source lives in code: a changed title and floor are read."""
    def change(data):
        data["title"] = "SYNTHETIC fixture zebra title"
        data["floor"] = 7
    folder = write_sources(tmp_path / "sources", ["arrests_like"], {"arrests_like": change})
    loaded = mod("sources").load_sources(folder)
    assert set(loaded) == {A_ID}
    carries(loaded[A_ID], "SYNTHETIC fixture zebra title", 7)


def test_a_source_file_with_its_own_unit_and_wording_is_answered_in_its_words(tmp_path,
                                                                               monkeypatch):
    """C3 "Nothing about a source lives in code": the unit, a category's wording and its
    dimension come from the file. A copy of arrests_like says "zebra records" and "inside
    {labels}" and calls the district a "zone"; the answer uses those words (C6, C10)."""
    def change(data):
        data["unit"] = {"one": "zebra record", "many": "zebra records"}
        for f in data["fields"]:
            if f["name"] == "district":
                f["wording"] = "inside {labels}"
                f["dimension"] = "zone"
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": change})
    spec = (year(2025), [is_(SCHOOL, True)], ["district"])
    t = truth("arrests_like", *spec)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, *spec)),
                    Step(finish("finding", "I counted {r1.count}.")))
    src = env.source("arrests_like")
    line1 = (f"I counted {shown(t['total'])} zebra records within 500 feet of a school in "
             f"2025 with a zone recorded.")
    assert_reply(reply.text, line1, table=table_lines(t["groups"]),
                 left_out=[left_out_line(t["left_out"]["district"], "zone")],
                 hidden=hidden_line(src["page"]), source=source_re("arrests_like", src=src))
    assert "arrest records" not in reply.text


def test_a_category_filter_uses_the_files_wording(tmp_path, monkeypatch):
    """C3 and C6: a category fragment is the field's `wording` with its labels."""
    def change(data):
        for f in data["fields"]:
            if f["name"] == "district":
                f["wording"] = "inside {labels}"
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": change})
    spec = (years(2024, 2025), [in_("district", "district 3", "district 4")])
    t = truth("arrests_like", *spec)
    reply = env.ask(Q_COUNT, Step(count(A_ID, *spec)),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.text.startswith(
        f"I counted {shown(t['total'])} arrest records inside district 3 and district 4 in 2024 "
        f"and 2025.")


# ---- the fixtures are SYNTHETIC and plainly made up (brief step 3) -------------------------

@pytest.mark.parametrize("name", NAMES)
def test_every_fixture_row_is_plainly_made_up(name):
    rows = fixture_rows(name)
    assert rows and all(row_id(r).startswith("FIXTURE-") for r in rows)
    assert len({row_id(r) for r in rows}) == len(rows)
    assert all(r.get("data_class") == "SYNTHETIC" for r in rows)
    note = json.loads((FIXTURE_ROWS / f"{name}.json").read_text(encoding="utf-8"))["note"]
    assert "SYNTHETIC" in note


@pytest.mark.parametrize("name", NAMES)
def test_every_fixture_source_says_synthetic_and_points_nowhere_real(name):
    data = source_json(name)
    assert data["id"].startswith("FIXTURE:")
    assert "SYNTHETIC" in data["title"] and "SYNTHETIC" in data["publisher"]
    assert all("SYNTHETIC" in notice for notice in data["notices"])
    for key in ("address", "page"):
        assert re.fullmatch(r"https://fixture\.invalid/\S+", data[key]), data[key]
    assert "montgomery" not in json.dumps(data).lower()


@pytest.mark.parametrize("name", NAMES)
def test_each_fixture_source_has_the_shape_of_c3(name):
    """C3: one file per source; the keys of the example; each field one of four kinds, each
    kind with its own keys."""
    data = source_json(name)
    for key in ("id", "data_class", "title", "publisher", "address", "page", "unit", "is_not",
                "time_field", "coverage_start", "floor", "fields", "notices", "approved_by",
                "approved_on", "approval_record"):
        assert key in data, key
    assert data["data_class"] == "COUNTY_OPEN_DATA"
    assert set(data["unit"]) == {"one", "many"}
    date.fromisoformat(data["coverage_start"])
    assert data["floor"] == 10
    kinds = [f["kind"] for f in data["fields"]]
    assert set(kinds) <= {"age", "category", "flag", "key"} and kinds.count("key") == 1
    for f in data["fields"]:
        if f["kind"] == "age":
            low, high = f["usable"]
            assert f["bands"][0][0] == low and f["bands"][-1][1] == high
        if f["kind"] == "category":
            assert {"values", "wording", "dimension", "person", "sensitive"} <= set(f)
            assert "{labels}" in f["wording"]
        if f["kind"] == "flag":
            assert {"yes_raw", "no_raw", "yes", "no", "dimension"} <= set(f)


def test_the_two_fixtures_differ_as_the_brief_asks():
    """Brief step 3: the second has coded labels (two raw spellings, one label), a
    different unit, no flag and a floor of 10."""
    a, c = source_json("arrests_like"), source_json("coded_like")
    assert a["unit"] != c["unit"] and c["floor"] == 10
    assert not [f for f in c["fields"] if f["kind"] == "flag"]
    assert [f for f in a["fields"] if f["kind"] == "flag"]
    shared = [f for f in c["fields"] if f["kind"] == "category"
              and len(set(f["values"].values())) < len(f["values"])]
    assert len(shared) == 2  # race_code (W, White) and station (3D, 3rd; 2D, 2nd)
    person = [f["name"] for f in a["fields"] if f.get("person")]
    assert person == ["gender", "race", "ethnicity"]


def test_make_fixtures_makes_the_same_rows_again():
    """Brief step 3: built by a small script with a fixed seed: the same rows again."""
    module = load_make_fixtures()
    rng = random.Random(module.SEED)
    assert module.arrests_rows(rng) == fixture_rows("arrests_like")
    assert module.coded_rows(rng) == fixture_rows("coded_like")
    assert module.ARRESTS_LIKE == source_json("arrests_like")
    assert module.CODED_LIKE == source_json("coded_like")


# ---- the truth gives what make_fixtures.py designed (brief step 4) -------------------------

def test_the_truth_gives_the_designed_values_of_arrests_like():
    """s3support.truth (plain counting) agrees with make_fixtures.DESIGNED, which the script
    checked with counting of its own."""
    d = load_make_fixtures().DESIGNED["arrests_like"]
    t = truth("arrests_like", year(2025), [is_(SCHOOL, True)], ["district"])
    assert dict(t["groups"]) == d["2025 school by district"]
    assert t["left_out"] == {SCHOOL: 0, "district": d["2025 school no district"]}
    assert t["total"] == sum(d["2025 school by district"].values())
    for y in (2024, 2025, 2026):
        assert truth("arrests_like", year(y))["total"] == d["per_year"][y]
        t = truth("arrests_like", year(y), [], ["district"])
        assert t["left_out"]["district"] == d["no district"][y]
        assert truth("arrests_like", year(y), [], ["age_band"])["left_out"]["age"] == \
            d["unusable ages"][y]
    assert dict(truth("arrests_like", year(2024), [], ["district"])["groups"]) == \
        d["2024 by district"]
    assert dict(truth("arrests_like", year(2026), [], ["district"])["groups"]) == \
        d["2026 by district"]
    assert dict(truth("arrests_like", year(2026), [], ["gender"])["groups"]) == \
        d["2026 by gender"]
    assert dict(truth("arrests_like", year(2026), [], ["race"])["groups"]) == d["2026 by race"]
    assert dict(truth("arrests_like", year(2026), [], ["ethnicity"])["groups"]) == \
        d["2026 by ethnicity"]
    from s3support import age
    assert truth("arrests_like", year(2025), [age(None, 17)])["total"] == d["2025 under 18"]
    weekdays = truth("arrests_like", year(2025), [], ["weekday"])["groups"]
    assert dict(weekdays) == d["2025 by weekday"]
    hours = truth("arrests_like", year(2025), [], ["hour"])["groups"]
    assert hours[22] == d["2025 by hour"]["most_n"] and hours[5] == 0
    months = truth("arrests_like", year(2025), [], ["month"])["groups"]
    assert months["July 2025"] == 30 and months["February 2025"] == 12


def test_the_truth_gives_the_designed_values_of_coded_like():
    d = load_make_fixtures().DESIGNED["coded_like"]
    for y in (2025, 2026):
        assert truth("coded_like", year(y))["total"] == d["per_year"][y]
        assert truth("coded_like", year(y), [], ["station"])["left_out"]["station"] == \
            d["no station"][y]
    assert truth("coded_like", year(2025), [is_("station", "station 3")])["total"] == \
        sum(d["2025 station 3 raw"].values())
    assert truth("coded_like", year(2025), [is_("race_code", "group W")])["total"] == \
        sum(d["2025 group W raw"].values())


def test_no_row_is_at_5_am_and_the_newest_rows_are_alone():
    """Premises other tests use: no row at 5 am (so the hour 5 reads the same whether
    "to 5" takes it in or not), and each copy's newest record is one row on its own day."""
    for name, field_name, newest in (("arrests_like", "event_date_time", "2026-09-17"),
                                     ("coded_like", "booked_at", "2026-08-20")):
        times = [r[field_name] for r in fixture_rows(name)]
        assert not [t for t in times if t[11:13] == "05"]
        assert max(times)[:10] == newest and sum(t[:10] == newest for t in times) == 1


def test_the_questions_the_tests_use_pass_the_guard():
    """A premise: stage 1's guard neither refuses nor restricts them (A2), so whatever the
    build does with the guard in county mode, the county tools are offered."""
    for question in (Q_COUNT, Q_BREAKDOWN, Q_FOLLOW, Q_SHARE, Q_COMPARE, Q_ABOUT):
        guard_free(question)


def test_the_months_and_weekdays_are_english():
    """A premise for the labels the tests write (C6: `March 2025`, `Saturday`)."""
    assert calendar.month_name[3] == "March" and calendar.day_name[5] == "Saturday"
