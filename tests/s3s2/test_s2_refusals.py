"""R10 point 7 (docs/S3S2-DESIGN.md; R2, R3, R4, R7, R8; D-055, D-056): every refusal, its
sentence word for word, written out by hand in s2support (REFUSE, refuse_*, TOO_LITTLE_LINE).

Each is the error BAD_OPTIONS (TOO_LITTLE for too few records, point 4), carries its sentence
to the model (in the tool answer the model is given) and ends the turn with it (the reply holds
it; the turn is not ANSWERED); R is not started (no job folder); no value in the refusal.
When several apply, the first in point 7's order decides (test_the_order_of_point_7). None of
these tests starts R.

READINGS (briefs/QUESTIONS.md, Brief S3S2-A2):
- `<the filters as C6 writes them>` is C6's `<what>` of the filters (`within 500 feet of a
  school`; `of people recorded as female`; `on shift A`).
- A rate for 2026 on a copy that ends in October 2026: the year is not whole in the copy (R2)
  and has no Census copy; point 7 puts part of a year first, but the period asked IS a whole
  calendar year. Either of the two sentences, word for word, is accepted.
"""
import json
import re

import pytest

import s2support as T
from p1support import Step, finish
from s2agent import (MAIN, RATES, TITLE, FakeCensus, Q_RATE, S2Env, ask_rate, rate_call)
from s3sagent import job_folders

SCHOOL = {"field": "adjacent_to_school", "is": True}
FEMALE = {"field": "gender", "in": ["female"]}
DISTRICT_3 = {"field": "district", "in": ["district 3"]}
HALF_YEAR = {"year": 2025, "months": {"from": 1, "to": 6}}
RE_LABELS = T.LABELS["race_ethnicity"]


def _env(tmp_path, monkeypatch, name=RATES, **kw):
    return S2Env(tmp_path, monkeypatch, names=(name,), **kw)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _refused(env, reply, sentence, code="BAD_OPTIONS"):
    answer = env.model.answer(0)
    assert "result_id" not in answer, f"the rate was run: {answer}"
    assert answer.get("error") == code, answer
    assert reply.reason_code == code, (reply.status, reply.reason_code, reply.text)
    assert reply.status != "ANSWERED", (reply.status, reply.text)
    assert job_folders(env) == [], "R10 point 7: R is not started for a refused rate"
    assert not re.search(r"\d+\.\d", reply.text), f"a value in a refusal: {reply.text}"
    sentences = sentence if isinstance(sentence, tuple) else (sentence,)
    assert any(s in reply.text for s in sentences), (
        f"R10 point 7: the sentence, word for word:\n  want {sentences[0]}\n  got  {reply.text}")
    assert any(s in text for s in sentences for text in _strings(answer)), (
        f"R10 point 7: the error the model is given carries the sentence: {answer}")
    return answer


def _args(name, **change):
    args = T.analyze_arguments(name)
    for key, value in change.items():
        if key == "options":
            args["options"] = value
        else:
            args[key] = value
    return args


def _few_rows(per_group=None, total=None):
    """rates_like with 2025 cut down: at most `per_group` records in each group of R3, or at
    most `total` records in all (the other years as they are)."""
    src = T.source_json(RATES)
    kept, seen = [], {}
    for row in T.fixture_rows(RATES):
        if row["event_date_time"].startswith("2025"):
            key = T.group_of(row, "race_ethnicity", src) if per_group else "all"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > (per_group or total):
                continue
        kept.append(row)
    return {RATES: kept}


# (id, source, census years or None for the fixture's, args, sentence)
CASES = [
    ("by district", RATES, None, _args("re_2025", options={"by": "district"}),
     T.REFUSE["by_district"]),
    ("inside one district", RATES, None, _args("all_re_2025", filters=[DISTRICT_3]),
     T.REFUSE["in_district"]),
    ("by race", RATES, None, _args("re_2025", options={"by": "race"}), T.REFUSE["race"]),
    ("by ethnicity", RATES, None, _args("re_2025", options={"by": "ethnicity"}),
     T.REFUSE["ethnicity"]),
    ("by shift", MAIN, None, _args("gender_2025", options={"by": "shift"}),
     T.refuse_field("shift")),
    ("by school", MAIN, None, _args("gender_2025", options={"by": "adjacent_to_school"}),
     T.refuse_field("distance from a school")),
    ("by weapon", MAIN, None, _args("gender_2025", options={"by": "weapon"}),
     T.refuse_field("weapon")),
    ("by a list", MAIN, None, _args("age_5y", options={"by": ["gender", "age_band"]}),
     T.REFUSE["two_ways"]),
    ("by age band, gender filter", MAIN, None, _args("age_5y", filters=[FEMALE]),
     T.REFUSE["two_ways"]),
    ("by race_ethnicity, age filter", RATES, None,
     _args("re_2025", filters=[{"field": "age", "from": 18, "to": 24}]), T.REFUSE["two_ways"]),
    ("school filter", RATES, None, _args("all_re_2025", filters=[SCHOOL]),
     T.refuse_filtered("within 500 feet of a school")),
    ("gender filter, no by", MAIN, None, _args("all_2025", filters=[FEMALE]),
     T.refuse_filtered("of people recorded as female")),
    ("shift filter", MAIN, None, _args("all_2025", filters=[{"field": "shift", "in": ["shift A"]}]),
     T.refuse_filtered("on shift A")),
    ("from and to", RATES, None, _args("re_2025", period={"from": "2025-01-01", "to": "2025-06-30"}),
     T.REFUSE["part_year"]),
    ("months", RATES, None, _args("re_2025", period=HALF_YEAR), T.REFUSE["part_year"]),
    ("2025 not fetched", RATES, (2021, 2022, 2023, 2024), _args("re_2025"),
     T.refuse_no_copy([2025])),
    ("no Census copy at all", RATES, (), _args("re_2025"), T.refuse_no_copy([2025])),
    ("2024 and 2025 not fetched", RATES, (2021, 2022, 2023), _args("re_2024_25"),
     T.refuse_no_copy([2024, 2025])),
    ("2026", RATES, None, _args("re_2025", period={"year": 2026}),
     (T.REFUSE["part_year"], T.refuse_no_copy([2026]))),
    ("unknown reference", RATES, None,
     _args("re_2025", options={"by": "race_ethnicity", "reference": "district 3"}),
     T.refuse_reference("district 3", RE_LABELS)),
]


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_each_refusal_word_for_word(tmp_path, monkeypatch, case):
    _, name, years, args, sentence = case
    census = True if years is None else (FakeCensus(years=years) if years else False)
    env = _env(tmp_path, monkeypatch, name, census=census)
    _refused(env, ask_rate(env, arguments=args), sentence)


def test_a_source_not_marked_for_rates(tmp_path, monkeypatch):
    """R2: only a source whose file says "rates": true (here Part S's source, unmarked)."""
    env = _env(tmp_path, monkeypatch, MAIN, mark=())
    _refused(env, ask_rate(env, "gender_2025"), T.refuse_not_marked(TITLE[MAIN]))


@pytest.mark.parametrize("reference", ["Asian, not Hispanic", "asian, NOT hispanic"])
def test_a_reference_that_is_not_shown(tmp_path, monkeypatch, reference):
    """Point 4 and 7: in 2022 Asian, not Hispanic has 60 records, so it is not shown and cannot
    be the reference; the sentence names the reference as given and the shown groups."""
    env = _env(tmp_path, monkeypatch)
    reply = ask_rate(env, arguments=_args("re_2022", options={"by": "race_ethnicity",
                                                              "reference": reference}))
    _refused(env, reply, T.refuse_reference(reference, RE_LABELS[:3]))


@pytest.mark.parametrize("name,rows", [("re_2025", _few_rows(per_group=99)),
                                       ("all_re_2025", _few_rows(total=99))])
def test_too_little(tmp_path, monkeypatch, name, rows):
    """Point 4: no group with 100 records (or, with no breakdown, fewer than 100 in all):
    TOO_LITTLE with its line."""
    env = _env(tmp_path, monkeypatch, rows=rows)
    _refused(env, ask_rate(env, name), T.TOO_LITTLE_LINE, code="TOO_LITTLE")


# Point 7's order: (id, source, marked, census years or None, rows, args, the sentence that
# decides). Each pair below has two refusals that both apply; the first in the order wins.
ORDER = [
    ("not marked, part of a year", MAIN, False, None, None,
     _args("gender_2025", period=HALF_YEAR), T.refuse_not_marked(TITLE[MAIN])),
    ("part of a year, no Census copy", RATES, True, (2021, 2022, 2023, 2024), None,
     _args("re_2025", period=HALF_YEAR), T.REFUSE["part_year"]),
    ("no Census copy, by district", RATES, True, (2021, 2022, 2023, 2024), None,
     _args("re_2025", options={"by": "district"}), T.refuse_no_copy([2025])),
    ("by district, a district filter", RATES, True, None, None,
     _args("re_2025", options={"by": "district"}, filters=[DISTRICT_3]), T.REFUSE["by_district"]),
    ("by district, another filter", RATES, True, None, None,
     _args("re_2025", options={"by": "district"}, filters=[SCHOOL]), T.REFUSE["by_district"]),
    ("a district filter, by race", RATES, True, None, None,
     _args("re_2025", options={"by": "race"}, filters=[DISTRICT_3]), T.REFUSE["in_district"]),
    ("by race, a gender filter", RATES, True, None, None,
     _args("re_2025", options={"by": "race"}, filters=[FEMALE]), T.REFUSE["race"]),
    ("by ethnicity, another filter", RATES, True, None, None,
     _args("re_2025", options={"by": "ethnicity"}, filters=[SCHOOL]), T.REFUSE["ethnicity"]),
    ("by shift, a gender filter", MAIN, True, None, None,
     _args("gender_2025", options={"by": "shift"}, filters=[FEMALE]), T.refuse_field("shift")),
    ("two breakdowns, another filter", MAIN, True, None, None,
     _args("age_5y", filters=[FEMALE, SCHOOL]), T.REFUSE["two_ways"]),
    ("too few records, an unknown reference", RATES, True, None, _few_rows(per_group=99),
     _args("re_2025", options={"by": "race_ethnicity", "reference": "district 3"}),
     T.TOO_LITTLE_LINE),
]


@pytest.mark.parametrize("case", ORDER, ids=[c[0] for c in ORDER])
def test_the_order_of_point_7(tmp_path, monkeypatch, case):
    _, name, marked, years, rows, args, sentence = case
    env = _env(tmp_path, monkeypatch, name, mark=None if marked else (), rows=rows,
               census=True if years is None else FakeCensus(years=years))
    code = "TOO_LITTLE" if sentence == T.TOO_LITTLE_LINE else "BAD_OPTIONS"
    _refused(env, ask_rate(env, arguments=args), sentence, code=code)


def test_the_model_is_told_no_value(tmp_path, monkeypatch):
    """The error the model gets for a refused rate names no figure from the data."""
    env = _env(tmp_path, monkeypatch)
    reply = env.ask(Q_RATE, Step(rate_call(_args("re_2025", options={"by": "district"}))),
                    Step(finish("finding", "I found that.")))
    answer = _refused(env, reply, T.REFUSE["by_district"])
    text = json.dumps(answer)
    for n in ("600", "900", "400", "150", "200,000", "200000"):
        assert not re.search(rf"(?<![\d,]){re.escape(n)}(?![\d,])", text), (n, text)
