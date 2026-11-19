"""Point 9: bad input straight into execute_call, standing in for a model that sends wrong
arguments (design sections 4, 5 and 8). Every call must return a result, never raise."""
import copy

import pytest

from support import (DATA_CSV, ROUTER_DIRECT, SKILL, call, check_answered, check_refused,
                     snapshot_of)

# The brief asks for an unknown name; the tests session added near misses and None:
# only the exact approved name is approved.
UNKNOWN_SKILLS = ["conviction_rate", "", "Arrest_Count_Trend", " arrest_count_trend",
                  "arrest_count_trend@0.1.0", None]

BAD_ARGUMENTS = {
    "year_as_text": {"year": "2025", "age_group": "18_25"},
    "year_as_float": {"year": 2025.0, "age_group": "18_25"},
    "year_as_True": {"year": True, "age_group": "18_25"},
    "year_missing": {"age_group": "18_25"},
    "age_group_not_in_list": {"year": 2025, "age_group": "18_to_25"},
    "extra_argument": {"year": 2025, "age_group": "18_25", "county": "Montgomery"},
    "arguments_not_a_dict": None,  # added by the tests session
}


@pytest.mark.parametrize("skill", UNKNOWN_SKILLS, ids=[repr(s) for s in UNKNOWN_SKILLS])
def test_unknown_skill_is_an_error(skill, runs_dir):
    check_refused(call(skill, {"year": 2025, "age_group": "18_25"}, runs_dir), runs_dir,
                  question="", router=ROUTER_DIRECT, status="ERROR", code="UNKNOWN_SKILL")


@pytest.mark.parametrize("arguments", BAD_ARGUMENTS.values(), ids=BAD_ARGUMENTS)
def test_bad_arguments_are_an_error(arguments, runs_dir):
    as_sent = copy.deepcopy(arguments)
    d = check_refused(call(SKILL, arguments, runs_dir), runs_dir, question="",
                      router=ROUTER_DIRECT, status="ERROR", code="INVALID_ARGUMENTS")
    assert d["skill"] == SKILL
    assert d["arguments"] == as_sent  # "the arguments as received"


def test_valid_call_for_2019_is_out_of_coverage(runs_dir):
    d = check_refused(call(SKILL, {"year": 2019, "age_group": "18_25"}, runs_dir), runs_dir,
                      question="", router=ROUTER_DIRECT, status="UNSUPPORTED",
                      code="OUT_OF_COVERAGE")
    assert d["skill"] == SKILL
    assert d["arguments"] == {"year": 2019, "age_group": "18_25"}
    assert d["snapshot_id"] == snapshot_of(DATA_CSV)  # the file was read to find no rows


def test_valid_call_for_2025_18_25_matches_truth(runs_dir):
    check_answered(call(SKILL, {"year": 2025, "age_group": "18_25"}, runs_dir), runs_dir,
                   question="", router=ROUTER_DIRECT, year=2025, age_group="18_25")


@pytest.mark.parametrize("arguments", [{"year": 2024}, {"year": 2024, "age_group": None}],
                         ids=["age_group_left_out", "age_group_None"])
def test_valid_call_for_all_ages_matches_truth(arguments, runs_dir):
    """Added by the tests session: age_group is optional and defaults to None (all ages)."""
    question = "Monthly arrests in 2024 (direct call)"
    check_answered(call(SKILL, arguments, runs_dir, question=question), runs_dir,
                   question=question, router=ROUTER_DIRECT, year=2024, age_group=None)
