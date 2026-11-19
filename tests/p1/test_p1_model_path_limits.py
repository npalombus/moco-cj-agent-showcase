"""Limitations on the model path (docs/P1-DESIGN.md section 9, "Limitations on the model
path", as changed by docs/P1A-DESIGN.md A7 and A10; brief P1A-A step 3). First written by the
planning chat; rewritten for P1A.

An answer the model helped produce must not say that no AI model was used. Under P1A:
- the saved record (manifest.json) and report.md of a count the model chose carry the model
  sentence ("An AI model (<model id>) read the question and chose the analysis. Python ...")
  exactly once, and never "No AI model was used";
- the short reply lists no limitation at all (A7 gives its two lines, with no limits);
- a following "details" turn shows every limitation of the saved record, one per line after
  "- " (A10), the model sentence included, and not "No AI model was used";
- every other record a model turn saves (each count of a two-count compared turn, and a
  refused OUT_OF_COVERAGE count) never says "No AI model was used", and each ANSWERED one
  carries the model sentence exactly once;
- stage 1's `ask` and direct `execute_call` still say no model was used, also after a model
  turn in the same process (carried over).

Nothing here is accepted two ways. Not checked: the wording of the other limitations (P0
section 11, stage 1's own tests).
"""
import json

import pytest

from p1support import FAKE_MODEL_ID, ONE_COUNT_TEXT, Env, Step, check_reply, count, finish
from support import SKILL, SUPPORTED, ask, call, record

NO_MODEL = "No AI model was used"
MODEL_ROLE = "read the question and chose the analysis"


def model_answer(sid, tmp_path):
    """An ANSWERED turn on S1 or S2 (one count, a passing finish), and its saved record."""
    question, year, group = SUPPORTED[sid]
    env = Env(tmp_path)
    reply = env.answered(question, (year, group))
    check_reply(reply, env.model)
    (run_id,) = reply.run_ids
    run_dir = env.runs_dir / run_id
    manifest_text = (run_dir / "manifest.json").read_text(encoding="utf-8")
    return env, reply, json.loads(manifest_text), manifest_text, \
        (run_dir / "report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("sid", ["S1", "S2"])
def test_the_saved_record_and_report_carry_the_model_sentence_once(sid, tmp_path):
    _, _, manifest, manifest_text, report = model_answer(sid, tmp_path)
    (sentence,) = [s for s in manifest["limitations"] if MODEL_ROLE in s]
    assert FAKE_MODEL_ID in sentence and "Python" in sentence, sentence
    assert manifest_text.count(MODEL_ROLE) == 1, "the model sentence is not there exactly once"
    assert report.count(MODEL_ROLE) == 1, "report.md does not hold the model sentence once"
    assert sentence in report
    assert NO_MODEL not in manifest_text
    assert NO_MODEL not in report


@pytest.mark.parametrize("sid", ["S1", "S2"])
def test_the_short_reply_holds_no_limitation(sid, tmp_path):
    _, reply, manifest, _, _ = model_answer(sid, tmp_path)
    assert MODEL_ROLE not in reply.text
    assert NO_MODEL not in reply.text
    for sentence in manifest["limitations"]:
        assert sentence not in reply.text, f"a limitation is in the short reply: {sentence!r}"


@pytest.mark.parametrize("sid", ["S1", "S2"])
def test_details_shows_every_limitation_with_the_model_sentence(sid, tmp_path):
    env, _, manifest, _, _ = model_answer(sid, tmp_path)
    details = env.ask("details")
    check_reply(details, env.model)
    assert details.status == "DETAILS", (details.status, details.reason_code, details.text)
    lines = details.text.splitlines()
    for sentence in manifest["limitations"]:
        assert f"- {sentence}" in lines, f"limitation not shown by details: {sentence!r}"
    assert any(MODEL_ROLE in line for line in lines)
    assert NO_MODEL not in details.text


def test_every_record_of_a_model_turn_never_says_no_model_was_used(tmp_path):
    """P1 section 9: a record whose router is the model's must not hold the sentence. Two
    counts compared, then a count of 2019 (OUT_OF_COVERAGE, a refused record)."""
    env = Env(tmp_path)
    reply = env.answered("Compare 2024 and 2025 for people under 18.",
                         (2024, "under_18"), (2025, "under_18"), compared=True)
    check_reply(reply, env.model)
    refused = env.ask("How many arrests each month in 2019?", Step(count(2019, "all")),
                      Step(finish("finding", ONE_COUNT_TEXT)))
    check_reply(refused, env.model)
    assert (refused.status, refused.reason_code) == ("UNSUPPORTED", "OUT_OF_COVERAGE")
    run_dirs = sorted(p.parent for p in env.runs_dir.glob("*/manifest.json"))
    assert len(run_dirs) == 3, run_dirs
    statuses = []
    for run_dir in run_dirs:
        manifest_text = (run_dir / "manifest.json").read_text(encoding="utf-8")
        report = (run_dir / "report.md").read_text(encoding="utf-8")
        assert NO_MODEL not in manifest_text and NO_MODEL not in report, run_dir.name
        status = json.loads(manifest_text)["status"]
        statuses.append(status)
        if status == "ANSWERED":
            assert manifest_text.count(MODEL_ROLE) == 1, run_dir.name
            assert report.count(MODEL_ROLE) == 1, run_dir.name
    assert sorted(statuses) == ["ANSWERED", "ANSWERED", "UNSUPPORTED"], statuses


def test_stage_1_answers_still_say_no_model_was_used(tmp_path, runs_dir):
    """The rules path and a direct call use no model, and keep saying so, also after a
    model turn in the same process."""
    question, year, group = SUPPORTED["S1"]
    Env(tmp_path).answered(question, (year, group))
    for d in (record(ask(question, runs_dir)),
              record(call(SKILL, {"year": year, "age_group": group}, runs_dir))):
        assert any(NO_MODEL in sentence for sentence in d["limitations"]), d["limitations"]
        assert not any(MODEL_ROLE in sentence for sentence in d["limitations"]), \
            d["limitations"]
