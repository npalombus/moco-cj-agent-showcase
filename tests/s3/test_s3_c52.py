"""Stage 3 Part A, C52 of docs/S3A-DESIGN.md: C21 (under 18, inside one turn) with a filter that
keeps every record, and with the left-out figures. Brief: briefs/S3-R16-A-tests.md. Tests only;
the planning chat builds C52. The findings it answers are DEFECT 1 and 2 of
kit-log/raw/CHAT-BUILDS-check-7.txt (its step 4 probes P01 to P05, P23 and P24 are here by name).
All data is SYNTHETIC: the fixtures of tests/s3, and rows made for one test in that test's own
copy (ids FIXTURE-R16-...); no real figure is quoted.

C52 point 1: a filter on a field other than the age that names every value its field can take
(every hour, wrapped round midnight or not; all seven days; every label of a category) is no
filter for C21's kinds. Point 2: for every category or flag field a request filters or breaks
down by, the count has one more figure, the records left out for that field: the count's ages,
of the count's kind with that field set to "no value recorded". Point 3: nothing else of C21
changes. Point 4: three of C21's own allowed examples (tests/s3/test_s3_round5.py) are refused
now; that file moves them to its refused cases.

What each test shows:
- refused: `counting.one_year_under_18` on the checked specs is True (and False on the counts
  before the last); through `count` in a county turn with the model stand-in, the last request
  is answered NOT_ALLOWED with the age field and C21's `why` word for word, the counts before it
  are answered, nothing is counted or saved for it, and the turn is ANSWERED;
- the refused count uses up none of the turn's eight counts (eight more are answered, a ninth
  is TOO_MANY), for every refused example;
- allowed: `one_year_under_18` is False, every count is answered, the totals are plain
  counting's;
- C52's own examples, the check's probes P01 to P05, P23 (with rows that make the left-out
  figures differ) and P24 (the compare cannot be made), fourteen more refused of this file's own
  and eight more allowed (among them a filter naming all labels but one, hours 1 to 23, six
  weekdays, and a left-out figure of a field only one of the two counts uses);
- point 3: C52's refusal comes before TOO_FINE and before the ninth-count limit;
- a source with no age field: nothing is refused.

READINGS (also in kit-log/raw/S3-R16-A-notes.txt):
- R16-1. "A filter that names every value of its field": for a category, every label the source
  file lists, in any order and any case (C5 reads labels that way). A flag filter names one
  value only, so point 1 never applies to it.
- R16-2. Point 2's figure is one per field per count (as the reply has one left-out line per
  field per count), with the count's ages and the total's kind, whatever other breakdown the
  count has: a count by race and age band has one left-out figure for race, of the count's ages,
  not one per band. Point 2 holds "whether or not the reply ends up writing its line", so a
  left-out figure of 0 is still a figure (P05 and the race cases).
- R16-3. "The examples of C21 itself still hold": C21's example "under 18 by district, then under
  17 in district 5" (C52's refused list) is refused today already, by C21's own group line (the
  group district 5 is of the kind of a count in district 5), so that test passes today; the
  others of C52's refused list fail today.
- R16-4. "No count used up": as tests/s3/test_s3_round5.py shows it, eight counts are answered
  after the refusal and a ninth is TOO_MANY. The counts added for it are of ages 18 and over, so
  none of them is refused or too fine.
"""
import pytest

from p1support import Step, finish, mod
from s3support import (SCHOOL, CountyEnv, age, compare, figures, fixture_rows, hours, in_, is_,
                       made_rows, truth, weekdays, year)
from test_s3_round5 import (A, AGE_FIELD, C, IDS, U16, U17, U18, V_ID, Y25, add_visits,
                            assert_counted, assert_not_allowed, assert_result, call_of, checked,
                            one_turn, spec)

Q_COMPARE = "Compare those two counts."
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DISTRICTS = [f"district {n}" for n in range(1, 7)]
D3, D4, D5 = (is_("district", f"district {n}") for n in (3, 4, 5))
CODED_U18, CODED_U17 = age(None, 17, "age_years"), age(None, 16, "age_years")


# ---- rows made for one test (the test's own copy of the fixture; the shared files unchanged) ----

def _r16_rows(*groups):
    """SYNTHETIC rows over arrests_like's base row (s3support.made_rows; the anchor row it adds
    is left out, so the fixture's own newest record stays the copy's newest)."""
    made = made_rows(A, *groups, prefix="FIXTURE-R16-")
    return [r for r in made if not r["id"].endswith("ANCHOR")]


def at(hour):
    return f"2025-03-04T{hour:02d}:00:00.000"


EXTRA = {
    # P23 as the check made it: 2025, no district recorded, 14 aged 17 and 11 aged 15
    "no district": _r16_rows((14, {"age": "17", "district": None}),
                             (11, {"age": "15", "district": None})),
    # ten aged 15 at every hour of 2025, so a count of under 18 by hour is not too fine
    "every hour": _r16_rows(*[(10, {"age": "15", "event_date_time": at(h)}) for h in range(24)]),
    # ten aged 15 in each of districts 1 to 5, so under 18 by district in 2025 is not too fine
    "by district": _r16_rows(*[(10, {"age": "15", "district": str(d)}) for d in range(1, 6)]),
    # ten women and ten men aged 15 in district 3, so under 18 there by gender is not too fine
    "district 3 by gender": _r16_rows((10, {"age": "15", "district": "3", "gender": "Female"}),
                                      (10, {"age": "15", "district": "3", "gender": "Male"})),
}


def rows_of(extra):
    return fixture_rows(A) + EXTRA[extra] if extra else None


def env_with(tmp_path, monkeypatch, specs, extra=None):
    names = tuple(n for n in (A, C) if any(s["name"] == n for s in specs)) or (A,)
    return CountyEnv(tmp_path, monkeypatch, names=names,
                     rows={A: rows_of(extra)} if extra else None)


def checked_specs(env, specs):
    """The specs as C5 checks and tidies them (counting.check_spec), each with its source's
    copy, as the turn hands them to C21."""
    loaded, out = mod("sources").load_sources(), []
    for s in specs:
        sid = IDS[s["name"]]
        copy = mod("sources").latest(sid, state_dir=env.state_dir)
        out.append(mod("counting").check_spec(
            loaded[sid], copy, {"period": s["period"], "filters": s["filters"],
                                "group_by": s["group_by"]}))
    return loaded[sid], copy, out


def one_year(env, specs):
    source, copy, done = checked_specs(env, specs)
    return mod("counting").one_year_under_18(source, done, copy)


def total(s, extra=None):
    return truth(s["name"], s["period"], s["filters"], rows=rows_of(extra))["total"]


# ---- refused ------------------------------------------------------------------------------------
# Each case: (the counts of one turn, in order; the rows made for it, or None). Every count but
# the last is answered; the last is refused. arrests_like and 2025 unless said.

ALL_HOURS, ALL_DAYS = hours(0, 23), weekdays(*DAYS)
ALL_RACES = in_("race", "group Alpha", "group Beta", "group Gamma")

REFUSED = {
    # C52's own examples
    "C52, P01: under 18, then under 17 with hours 0 to 23":
        ([spec(Y25, [U18]), spec(Y25, [U17, ALL_HOURS])], None),
    "C52, P02: under 18, then under 17 with hours 5 to 4 (round midnight)":
        ([spec(Y25, [U18]), spec(Y25, [U17, hours(5, 4)])], None),
    "C52, P03: under 18, then under 17 on all seven days (no weekday breakdown)":
        ([spec(Y25, [U18]), spec(Y25, [U17, ALL_DAYS])], None),
    "C52, P04: under 18 by hour with hours 0 to 23, then under 17":
        ([spec(Y25, [U18, ALL_HOURS], ["hour"]), spec(Y25, [U17])], "every hour"),
    "C52, P05: under 18, then under 17 with every label of race":
        ([spec(Y25, [U18]), spec(Y25, [U17, ALL_RACES])], None),
    "C52, P23: under 18 in district 3, then under 17 in district 5 (left-out figures differ)":
        ([spec(Y25, [U18, D3]), spec(Y25, [U17, D5])], "no district"),
    "C52: under 18 in district 3, then under 17 in district 5 (the fixture as it is)":
        ([spec(Y25, [U18, D3]), spec(Y25, [U17, D5])], None),
    "C52: under 18 by district, then under 17 in district 5 (R16-3: refused today too)":
        ([spec(Y25, [U18], ["district"]), spec(Y25, [U17, D5])], "by district"),
    "C52: under 18 in district 3 by gender, then under 17 in district 5":
        ([spec(Y25, [U18, D3], ["gender"]), spec(Y25, [U17, D5])], "district 3 by gender"),
    # this file's own
    "every hour written another way: hours 22 to 21":
        ([spec(Y25, [U18]), spec(Y25, [U17, hours(22, 21)])], None),
    "every label of gender":
        ([spec(Y25, [U18]), spec(Y25, [U17, in_("gender", "female", "male")])], None),
    "every label of race, in another order and case":
        ([spec(Y25, [U18]), spec(Y25, [U17, in_("race", "GROUP GAMMA", "group alpha",
                                                  "Group Beta")])], None),
    "every label of district, the narrower count first":
        ([spec(Y25, [U17, in_("district", *DISTRICTS)]), spec(Y25, [U18])], None),
    "every hour and all seven days on one count":
        ([spec(Y25, [U18]), spec(Y25, [U17, ALL_HOURS, ALL_DAYS])], None),
    "an every-value filter on each side, of two fields: every hour, then all seven days":
        ([spec(Y25, [U18, ALL_HOURS]), spec(Y25, [U17, ALL_DAYS])], None),
    "both points: under 18 in district 3 at every hour, then under 17 in district 5":
        ([spec(Y25, [U18, D3, ALL_HOURS]), spec(Y25, [U17, D5])], None),
    "left-out: under 18 in district 3, then under 17 in districts 4 and 5":
        ([spec(Y25, [U18, D3]), spec(Y25, [U17, in_("district", "district 4", "district 5")])],
         None),
    "left-out of race (0 recorded none): group Alpha, then group Beta":
        ([spec(Y25, [U18, is_("race", "group Alpha")]), spec(Y25, [U17, is_("race", "group Beta")])],
         None),
    "left-out of a flag: within 500 feet of a school, then not within":
        ([spec(Y25, [U18, is_(SCHOOL, True)]), spec(Y25, [U17, is_(SCHOOL, False)])], None),
    "left-out, the year at the bottom: 11 and over in district 3, then all ages in district 4":
        ([spec(Y25, [age(11), D3]), spec(Y25, [D4])], None),
    "left-out of three counts in districts 1, 2 and 3: under 18, under 16, then 10 to 16":
        ([spec(Y25, [U18, is_("district", "district 1")]),
          spec(Y25, [U16, is_("district", "district 2")]), spec(Y25, [age(10, 16), D3])], None),
    "left-out of a breakdown: under 18 by district, then under 17 in districts 1 and 2":
        ([spec(Y25, [U18], ["district"]),
          spec(Y25, [U17, in_("district", "district 1", "district 2")])], "by district"),
    "coded_like, left-out of station: under 18 at station 1, then under 17 at station 2":
        ([spec(Y25, [CODED_U18, is_("station", "station 1")], name=C),
          spec(Y25, [CODED_U17, is_("station", "station 2")], name=C)], None),
}


@pytest.mark.parametrize("case", list(REFUSED))
def test_c52_refused(tmp_path, monkeypatch, case):
    specs, extra = REFUSED[case]
    env = env_with(tmp_path, monkeypatch, specs, extra)
    assert not one_year(env, specs[:-1]), "premise: the counts before the last are allowed"
    assert one_year(env, specs), "counting.one_year_under_18 must be True"
    reply, answers = one_turn(env, specs, answered=len(specs) - 1)
    for i, answer in enumerate(answers[:-1], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[-1], AGE_FIELD[specs[-1]["name"]])
    assert_counted(env, reply, len(specs) - 1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    checked(reply)


FILLERS = ([spec(Y25, [age(18), is_("district", d)]) for d in DISTRICTS]
           + [spec(year(2024), [age(18)]), spec(year(2026), [age(18)]), spec(Y25, [age(18)])])


@pytest.mark.parametrize("case", list(REFUSED))
def test_c52_the_refused_count_uses_up_none_of_the_turns_counts(tmp_path, monkeypatch, case):
    """R16-4: after the refusal, counts are answered up to eight; the next is TOO_MANY."""
    specs, extra = REFUSED[case]
    made = specs[:-1]
    if specs[-1]["name"] == C:
        fillers = [spec(year(2025), [age(18, None, "age_years"), is_("station", f"station {n}")],
                        name=C) for n in (1, 2, 3)] + \
                  [spec(year(2026), [age(18, None, "age_years"), is_("station", f"station {n}")],
                        name=C) for n in (1, 2, 3)] + \
                  [spec(Y25, [age(18, None, "age_years")], name=C),
                   spec(year(2026), [age(18, None, "age_years")], name=C)]
    else:
        fillers = list(FILLERS)
    fillers = fillers[:8 - len(made) + 1]
    env = env_with(tmp_path, monkeypatch, specs, extra)
    reply, answers = one_turn(env, made + [specs[-1]] + fillers, answered=1)
    for i, answer in enumerate(answers[:len(made)], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[len(made)], AGE_FIELD[specs[-1]["name"]])
    for i, answer in enumerate(answers[len(made) + 1:-1], len(made) + 1):
        assert_result(answer, f"r{i}")
    assert answers[-1].get("error") == "TOO_MANY", answers[-1]
    assert_counted(env, reply, 8)


def test_c52_p23_the_left_out_figures_differ_by_the_17_year_olds_with_no_district():
    """P23's premise, by plain counting (no program code): on the test's own copy, the records
    of no district under 18 and under 17 differ by the 17-year-olds of no district (14), and
    both would be shown (10 or more)."""
    rows = rows_of("no district")
    first = truth(A, Y25, [U18, D3], rows=rows)["left_out"]["district"]
    second = truth(A, Y25, [U17, D5], rows=rows)["left_out"]["district"]
    seventeen = sum(1 for r in rows if r.get("age") == "17" and "district" not in r
                    and r["event_date_time"].startswith("2025"))
    assert first - second == seventeen == 14
    assert min(first, second) >= 10


def test_c52_p24_the_compare_cannot_be_made(tmp_path, monkeypatch):
    """P24: P01's two counts, then compare: the second count is refused, so it has no result and
    the compare is not made; no difference (the 17-year-olds) is written."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, second = spec(Y25, [U18]), spec(Y25, [U17, ALL_HOURS])
    seventeen = total(first) - total(second)
    assert seventeen == 3, "premise: three records aged 17 in 2025"
    reply = env.ask(Q_COMPARE, Step(call_of(first), call_of(second)), Step(compare("r1", "r2")),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_result(env.model.answer(0, 0), "r1")
    assert_not_allowed(env.model.answer(0, 1))
    assert env.model.answer(1).get("error") == "BAD_COMPARE", env.model.answer(1)
    assert "difference" not in reply.text and seventeen not in figures(reply.text), reply.text
    assert [r["kind"] for r in reply.results] == ["count"]


def test_c52_p01_two_counts_in_two_steps(tmp_path, monkeypatch):
    """The check is over the turn's counts so far, whatever step they came in."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(call_of(spec(Y25, [U18]))),
                    Step(call_of(spec(Y25, [U17, ALL_HOURS]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_result(env.model.answer(0), "r1")
    assert_not_allowed(env.model.answer(1))
    assert_counted(env, reply, 1)


# ---- point 3: the check's place is C21's ----------------------------------------------------------

def test_c52_point_3_before_too_fine(tmp_path, monkeypatch):
    """Under 17 at every hour by district (too fine on the fixture) after under 18:
    NOT_ALLOWED, not TOO_FINE (C21 answer 1)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [spec(Y25, [U18]), spec(Y25, [U17, ALL_HOURS], ["district"])],
                              answered=1)
    assert_not_allowed(answers[1])
    assert_counted(env, reply, 1)


def test_c52_point_3_before_the_ninth_count_limit(tmp_path, monkeypatch):
    """Eight counts made; a ninth that C52 refuses: NOT_ALLOWED, not TOO_MANY (C21 answer 2)."""
    eight = [spec(Y25, [U18])] + FILLERS[:7]
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, eight + [spec(Y25, [U17, ALL_DAYS])], answered=1)
    for i, answer in enumerate(answers[:8], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[8])
    assert_counted(env, reply, 8)


# ---- allowed ----------------------------------------------------------------------------------------

ALLOWED = {
    # C52's own examples
    "C52: under 18 in district 3, then under 16 in district 5 (two years)":
        ([spec(Y25, [U18, D3]), spec(Y25, [U16, D5])], "no district"),
    "C52: under 18 in district 3, then 18 to 24 in district 5":
        ([spec(Y25, [U18, D3]), spec(Y25, [age(18, 24), D5])], "no district"),
    "C52: under 18 at hours 0 to 22, then under 17 (not every hour)":
        ([spec(Y25, [U18, hours(0, 22)]), spec(Y25, [U17])], None),
    "C52: under 18 in district 3, then under 17 with no district filter and no breakdown":
        ([spec(Y25, [U18, D3]), spec(Y25, [U17])], "no district"),
    # this file's own
    "a filter naming all labels but one: under 18, then under 17 in districts 1 to 5":
        ([spec(Y25, [U18]), spec(Y25, [U17, in_("district", *DISTRICTS[:5])])], None),
    "hours 1 to 23: under 18, then under 17 at hours 1 to 23":
        ([spec(Y25, [U18]), spec(Y25, [U17, hours(1, 23)])], None),
    "hours 5 to 3, round midnight (23 hours)":
        ([spec(Y25, [U18]), spec(Y25, [U17, hours(5, 3)])], None),
    "six weekdays: under 18, then under 17 from Monday to Saturday":
        ([spec(Y25, [U18]), spec(Y25, [U17, weekdays(*DAYS[:6])])], None),
    "a field only one count uses: under 18 in district 3, then under 17 recorded as female":
        ([spec(Y25, [U18, D3]), spec(Y25, [U17, is_("gender", "female")])], "no district"),
    "every label of race, the same ages on both sides":
        ([spec(Y25, [U18]), spec(Y25, [U18, ALL_RACES])], None),
    "every hour, in another year":
        ([spec(Y25, [U18]), spec(year(2024), [U17, ALL_HOURS])], None),
    "left-out figures of the same ages: under 18 in district 3, then in districts 4 and 5":
        ([spec(Y25, [U18, D3]), spec(Y25, [U18, in_("district", "district 4", "district 5")])],
         "no district"),
}


@pytest.mark.parametrize("case", list(ALLOWED))
def test_c52_allowed(tmp_path, monkeypatch, case):
    specs, extra = ALLOWED[case]
    env = env_with(tmp_path, monkeypatch, specs, extra)
    assert not one_year(env, specs), "counting.one_year_under_18 must be False"
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert [r["total"] for r in reply.results if r["kind"] == "count"] == \
        [total(s, extra) for s in specs]
    checked(reply)


def test_c52_a_source_with_no_age_field_refuses_nothing(tmp_path, monkeypatch):
    """visits_like (tests/s3/fixtures/round3) has no age field: every-value filters and left-out
    figures change nothing; every count is answered."""
    env = add_visits(CountyEnv(tmp_path, monkeypatch))
    areas = in_("area", "area North", "area South")
    specs = [spec(Y25, [is_("area", "area North")], name="visits_like"),
             spec(Y25, [is_("area", "area South")], name="visits_like"),
             spec(Y25, [areas], name="visits_like"),
             spec(Y25, [ALL_HOURS], name="visits_like"),
             spec(Y25, [ALL_DAYS], name="visits_like"),
             spec(Y25, [], name="visits_like")]
    loaded = mod("sources").load_sources()
    copy = mod("sources").latest(V_ID, state_dir=env.state_dir)
    done = [mod("counting").check_spec(loaded[V_ID], copy, {"period": s["period"],
                                                           "filters": s["filters"],
                                                           "group_by": s["group_by"]})
            for s in specs]
    assert not mod("counting").one_year_under_18(loaded[V_ID], done, copy)
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))


def test_premises_of_this_file():
    """Plain counting (no program code): the breakdowns made above are not too fine on the rows
    they use, and the rows made here are SYNTHETIC, of 2025, and new ids."""
    for s, extra in ((spec(Y25, [U18, ALL_HOURS], ["hour"]), "every hour"),
                     (spec(Y25, [U18], ["district"]), "by district"),
                     (spec(Y25, [U18, D3], ["gender"]), "district 3 by gender")):
        values = list(truth(A, s["period"], s["filters"], s["group_by"],
                            rows=rows_of(extra))["groups"].values())
        assert not [n for n in values if 1 <= n <= 9], (s, values)
    ids = {r["id"] for r in fixture_rows(A)}
    for rows in EXTRA.values():
        assert all(r["data_class"] == "SYNTHETIC" and r["id"] not in ids
                   and r["event_date_time"].startswith("2025") for r in rows)
