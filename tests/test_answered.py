"""Points 2, 3, 4 and 7: the five agreed supported questions S1-S5 (design section 10)."""
import pytest

from support import (ROUTER_RULES, SUPPORTED, api, ask, check_answered_fields, check_chart,
                     check_numbers, check_saved, check_words, record)


def test_public_interface_exists():
    """Section 5: from moco_agent import answer_question, execute_call, AnalysisResult."""
    module = api()
    assert callable(module.answer_question)
    assert callable(module.execute_call)
    assert isinstance(module.AnalysisResult, type)


@pytest.mark.parametrize("sid", SUPPORTED)
def test_supported_question_gets_the_right_numbers(sid, runs_dir):
    """Point 2: ANSWERED, the listed arguments, all 12 months and the total match the truth file."""
    question, year, age_group = SUPPORTED[sid]
    d = record(ask(question, runs_dir))
    assert d["status"] == "ANSWERED", (d["reason_code"], d["user_facing_summary"])
    listed = {"year": year, "age_group": age_group}
    # With no age wording, age_group may be filled in as None or left out (both mean all ages).
    assert d["arguments"] == listed or (age_group is None and d["arguments"] == {"year": year})
    check_numbers(d, year, age_group)  # all 12 months and the total, from the truth file


@pytest.mark.parametrize("sid", SUPPORTED)
def test_supported_question_record_is_complete(sid, runs_dir):
    """Point 3: every section 6 field; SYNTHETIC; no source URL; the rules router; JSON-safe."""
    question, year, age_group = SUPPORTED[sid]
    d = record(ask(question, runs_dir))  # every field present; to_dict() goes through json.dumps
    assert d["data_class"] == "SYNTHETIC"
    assert d["source_urls"] == []
    assert d["router"] == ROUTER_RULES
    check_answered_fields(d, question=question, router=ROUTER_RULES, year=year, age_group=age_group)


@pytest.mark.parametrize("sid", SUPPORTED)
def test_supported_question_is_saved(sid, runs_dir):
    """Point 4: manifest.json equals to_dict(); report.md; a real chart.png; labeled title."""
    question, _, _ = SUPPORTED[sid]
    d = record(ask(question, runs_dir))
    assert d["status"] == "ANSWERED", (d["reason_code"], d["user_facing_summary"])
    run_dir = check_saved(d, runs_dir)
    check_chart(d, run_dir)


@pytest.mark.parametrize("sid", SUPPORTED)
def test_supported_question_words(sid, runs_dir):
    """Point 7: both summaries say SYNTHETIC; the total in digits; three or more limitations."""
    question, _, _ = SUPPORTED[sid]
    d = record(ask(question, runs_dir))
    assert d["status"] == "ANSWERED", (d["reason_code"], d["user_facing_summary"])
    check_words(d)
