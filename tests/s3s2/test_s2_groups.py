"""R9, point 1: every group of R3 and R4 (docs/S3S2-DESIGN.md): which records count, which
Census variables are added up, and the residents figure with its margin by the formula for a
sum (R5).

- race_ethnicity (R3, D-055): Hispanic (any race) is ethnicity Hispanic with any race,
  recorded or not; Black, White and Asian are that race with ethnicity not Hispanic; every
  other record is left out. Census: B03002_012, _004, _003, _006.
- gender (R4): female and male, against B01001's two totals (_026, _002).
- age_band (R4, D-056): 10 to 17, 18 to 24, 25 to 34, 35 to 44, 45 to 54, 55 to 64, 65 and
  over, each the sum of B01001's age lines for both sexes; no usable age: left out.
- none: every record over all residents (B01001_001, which has no margin).

The variables of each group are worked out by the tests from the Census's own line labels
(tests/s3s2/fixtures/census.json, made by make_fixtures.py) and compared with the planning
chat's config/census.json, which the program reads. The tests without program code pass
today; the ones that run a rate start R and fail until Part S2 is built.

R10 points 3 and 6: the reply's table holds each shown group's records, residents figure (added
up over the years) and margin, whole numbers with thousands commas; `details` holds, for each
year asked and each shown group, that year's residents figure with its margin (READING: a
group of several Census lines, an age band, has the sum and the sum formula's margin; written
with or without commas, whole or with decimals).
"""
import json
import math
from pathlib import Path

import pytest

import s2support as T
from s2agent import MF, MAIN, RATES, S2Env, ask_rate, details_of, lines_of

REPO = Path(__file__).resolve().parents[2]


def _real_config():
    return json.loads((REPO / "config" / "census.json").read_text(encoding="utf-8"))


def _variables(cfg, by, group):
    return sorted(v["variable"] for v in cfg["breakdowns"][by][group])


def test_the_programs_config_adds_up_the_variables_the_tests_expect():
    """No program code: for every group, config/census.json adds up exactly the variables the
    tests work out from the Census labels, and its record rules are R3's and R4's."""
    real, mine = _real_config(), T.config()
    assert set(real["breakdowns"]) == set(mine["breakdowns"]) == {
        "none", "gender", "age_band", "race_ethnicity"}
    for by in mine["breakdowns"]:
        assert list(real["breakdowns"][by]) == list(mine["breakdowns"][by]), by
        for group in mine["breakdowns"][by]:
            assert _variables(real, by, group) == _variables(mine, by, group), (by, group)
    assert real["records"] == mine["records"]
    assert real["survey"] == "acs/acs1" and real["first_year"] == 2021
    assert (real["place"]["state"], real["place"]["county"]) == ("24", "031")
    assert set(real["tables"]) == {"B01001", "B03002"}
    assert real["margin_z"] == 1.645 and real["margin_level"] == 0.9
    assert "-555555555" in real["no_margin_codes"]


def test_the_groups_by_hand():
    """No program code: the groups of R3 and R4 and their variables, written out by hand."""
    cfg = T.config()["breakdowns"]
    assert list(cfg["race_ethnicity"]) == ["Hispanic (any race)", "Black, not Hispanic",
                                           "White, not Hispanic", "Asian, not Hispanic"]
    assert {g: _variables(T.config(), "race_ethnicity", g) for g in cfg["race_ethnicity"]} == {
        "Hispanic (any race)": ["B03002_012"], "Black, not Hispanic": ["B03002_004"],
        "White, not Hispanic": ["B03002_003"], "Asian, not Hispanic": ["B03002_006"]}
    assert {g: _variables(T.config(), "gender", g) for g in cfg["gender"]} == {
        "female": ["B01001_026"], "male": ["B01001_002"]}
    assert _variables(T.config(), "none", "all residents") == ["B01001_001"]
    bands = {g: _variables(T.config(), "age_band", g) for g in cfg["age_band"]}
    assert bands == {
        "10 to 17": ["B01001_005", "B01001_006", "B01001_029", "B01001_030"],
        "18 to 24": ["B01001_007", "B01001_008", "B01001_009", "B01001_010", "B01001_031",
                     "B01001_032", "B01001_033", "B01001_034"],
        "25 to 34": ["B01001_011", "B01001_012", "B01001_035", "B01001_036"],
        "35 to 44": ["B01001_013", "B01001_014", "B01001_037", "B01001_038"],
        "45 to 54": ["B01001_015", "B01001_016", "B01001_039", "B01001_040"],
        "55 to 64": ["B01001_017", "B01001_018", "B01001_019", "B01001_041", "B01001_042",
                     "B01001_043"],
        "65 and over": ["B01001_020", "B01001_021", "B01001_022", "B01001_023", "B01001_024",
                        "B01001_025", "B01001_044", "B01001_045", "B01001_046", "B01001_047",
                        "B01001_048", "B01001_049"]}
    # R4: no band below 18 narrower than eight years
    assert 17 - 10 + 1 == 8


def test_the_fixture_labels_hold_every_word_the_config_expects():
    """No program code: with the fixture's labels, every variable config/census.json lists
    passes its own label check in every year (so a refused year in the tests is one the test
    broke on purpose)."""
    real = _real_config()
    for year in T.YEARS:
        labels = {}
        for table in MF.TABLES:
            labels.update(T.census_file(year, table, labels=True)["variables"])
        for by, groups in real["breakdowns"].items():
            for group, variables in groups.items():
                for v in variables:
                    label = labels[v["variable"] + "E"]["label"]
                    for word in v["label_has"]:
                        assert word in label, (year, v["variable"], word, label)


def test_the_hispanic_label_words_are_in_no_not_hispanic_label():
    """No program code: R10 point 8. The words config/census.json now expects in the label of
    Hispanic (any race), `Total:!!Hispanic or Latino`, are in B03002_012's label and in no
    "Not Hispanic or Latino" label (every one of which held the old words). They are still in
    the labels of the Hispanic lines by race, B03002_013 to _021: briefs/QUESTIONS.md, Brief
    S3S2-A2."""
    real = _real_config()["breakdowns"]["race_ethnicity"]["Hispanic (any race)"]
    assert [(v["variable"], v["label_has"]) for v in real] == [
        ("B03002_012", ["Total:!!Hispanic or Latino"])], real
    labels = T.census_file(2025, "B03002", labels=True)["variables"]
    holding = sorted(name[:-1] for name, v in labels.items() if name.endswith("E")
                     and "Total:!!Hispanic or Latino" in v["label"])
    assert holding == [f"B03002_{n:03d}" for n in range(12, 22)], holding
    assert not any("Not Hispanic" in labels[n + "E"]["label"] for n in holding)


def test_the_fixture_tables_have_the_census_shape():
    """No program code: a first line of names, one line of values, every value a string or
    null, estimates E and margins M, each total with the "no margin" code, the place."""
    for year in T.YEARS:
        for table in MF.TABLES:
            data = T.census_file(year, table)
            assert "SYNTHETIC" in data["note"]
            names, row = data["answer"]
            assert len(names) == len(row) and names[-4:] == ["GEO_ID", "NAME", "state",
                                                               "county"]
            assert all(v is None or isinstance(v, str) for v in row)
            cell = dict(zip(names, row))
            assert cell[f"{table}_001M"] == "-555555555" and cell[f"{table}_001MA"] == "*****"
            assert (cell["state"], cell["county"]) == ("24", "031")
            assert data["answer"] == MF.group_answer(table, year)
            assert "SYNTHETIC" in T.census_file(year, table, labels=True)["note"]
        b01, b03 = T.census_values(year, "B01001"), T.census_values(year, "B03002")
        assert b01["B01001_001"][0] == b01["B01001_002"][0] + b01["B01001_026"][0]
        assert b01["B01001_002"][0] == sum(b01[f"B01001_{n:03d}"][0] for n in range(3, 26))
        assert b03["B03002_001"][0] == b01["B01001_001"][0]
        assert b03["B03002_001"][0] == b03["B03002_002"][0] + b03["B03002_012"][0]


RACE_CASES = [  # (race raw, ethnicity raw; None: not recorded) -> group
    (("White", "HISPANIC"), "Hispanic (any race)"),
    (("Unknown", "HISPANIC"), "Hispanic (any race)"),
    ((None, "HISPANIC"), "Hispanic (any race)"),
    (("Asian", "HISPANIC"), "Hispanic (any race)"),
    (("Black/African American", "HISPANIC"), "Hispanic (any race)"),
    (("Black/African American", "NON-HISPANIC"), "Black, not Hispanic"),
    (("White", "NON-HISPANIC"), "White, not Hispanic"),
    (("Asian", "NON-HISPANIC"), "Asian, not Hispanic"),
    (("Unknown", "NON-HISPANIC"), None),
    (("American Indian/ALSK Natv", "NON-HISPANIC"), None),
    (("Hawaiian/Pacific Islander", "NON-HISPANIC"), None),
    (("Black/African American", None), None),
    ((None, "NON-HISPANIC"), None),
    ((None, None), None),
]


def test_which_records_count_by_hand():
    """No program code: R3's and R4's rules on one record at a time, written out by hand."""
    src = T.source_json(RATES)
    for (race, eth), want in RACE_CASES:
        row = {k: v for k, v in (("race", race), ("ethnicity", eth)) if v is not None}
        assert T.group_of(row, "race_ethnicity", src) == want, (race, eth)
    main = T.source_json(MAIN)
    for raw, want in (("Female", "female"), ("Male", "male"), ("Unknown", None), (None, None)):
        row = {} if raw is None else {"gender": raw}
        assert T.group_of(row, "gender", main) == want, raw
    for raw, want in (("10", "10 to 17"), ("17", "10 to 17"), ("18", "18 to 24"),
                      ("34", "25 to 34"), ("35", "35 to 44"), ("54", "45 to 54"),
                      ("64", "55 to 64"), ("65", "65 and over"), ("98", "65 and over"),
                      ("9", None), ("7", None), ("99", None), ("120", None), ("25.5", None),
                      (None, None)):
        row = {} if raw is None else {"age": raw}
        assert T.group_of(row, "age_band", main) == want, raw
    assert T.group_of({}, None, main) == "all residents"


def test_the_record_counts_of_the_fixtures():
    """No program code: the counts the fixture was made with, counted again."""
    for year, groups in MF.RECORDS.items():
        if year > 2025:
            continue
        counts, left = T.record_counts(RATES, "race_ethnicity", (year,))
        assert dict(counts) == groups and left == 30, year
    counts, left = T.record_counts(MAIN, "gender", (2025,))
    assert dict(counts) == {"female": 601, "male": 1421} and left == 18
    counts, left = T.record_counts(MAIN, "age_band", (2025,))
    assert dict(counts) == {"10 to 17": 188, "18 to 24": 369, "25 to 34": 731,
                            "35 to 44": 423, "45 to 54": 187, "55 to 64": 72,
                            "65 and over": 30} and left == 40
    assert T.record_counts(MAIN, None, (2025,)) == ({"all residents": 2040}, 0)


def test_the_residents_by_the_formula_for_a_sum():
    """No program code: R5's formula for a sum, written out by hand."""
    assert T.residents("age_band", "10 to 17", (2025,)) == (110000, 2500.0)
    # 2024: 34,800 (1,700) + 20,800 (1,000) + 33,800 (1,300) + 19,800 (1,300) = 109,200
    est, moe = T.residents("age_band", "10 to 17", (2024, 2025))
    assert est == 110000 + 109200
    assert math.isclose(moe, math.sqrt(2500 ** 2 + 1700 ** 2 + 1000 ** 2 + 1300 ** 2
                                       + 1300 ** 2)) and round(moe) == 3677
    assert T.residents("gender", "female", (2025,)) == (541000, 13000.0)
    assert T.residents("gender", "male", (2024,)) == (516000 - 23 * 200, 13000.0)
    assert T.residents("race_ethnicity", "Hispanic (any race)", (2025,)) == (200000, 4000.0)
    assert T.residents(None, "all residents", (2025,)) == (1057000, None)
    assert T.residents(None, "all residents", (2024, 2025)) == (1057000 + 1047800, None)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["re_2025", "gender_2025", "age_5y", "all_2025", "re_2024_25"])
def test_every_group_its_records_and_its_residents(tmp_path, monkeypatch, name):
    """With the program: each shown group's table line (its records over its residents, the
    rate right only if the right records are counted over the right residents), and in
    `details` each year's residents figure with its margin."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],), MOCO_REPLY_STYLE="fixed")
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    lines = lines_of(reply.text)
    for group in t["shown"]:
        assert T.table_line(t, group) in lines, (T.table_line(t, group), reply.text)
    details = details_of(env).text
    assert ("B03002" if t["by"] == "race_ethnicity" else "B01001") in details, details
    for year in t["years"]:
        for group in t["shown"]:
            est, moe = T.residents(t["by"], group, (year,))
            assert T.written(details, est, whole=True), (year, group, est, details)
            if moe is not None:
                assert T.written(details, moe, whole=True), (year, group, moe, details)
