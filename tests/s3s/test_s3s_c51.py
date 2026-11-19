"""Brief S3-R15-A: C51 point 5 of docs/S3A-DESIGN.md (D-071) for an analysis's record ("C51, after
CHAT-BUILDS-check-6": its PROOF GAP 2, break B40d). Tests only; the program does not change.

One county `analyze` turn (Part S, a trend on the SYNTHETIC fixture of tests/s3s) and one county
rate turn (Part S2, kind `rate`, on the SYNTHETIC fixtures of tests/s3s2, the Census copies made
by `fetch-census` against the fake Census service) with the model stand-in
(p1support.FakeModel), MOCO_MODEL_PROVIDER `anthropic` and then `nvidia`, every setting of both
services given: a made-up ANTHROPIC_API_KEY built from pieces (p1support.FAKE_ANTHROPIC_KEY,
shaped like no real key), test model names, addresses that do not exist. The stand-in's
model_id is the active service's model. No model service and no site is reached (the conftest
blocks every socket; the Census is s2agent.FakeCensus behind urllib). R really runs (needs_r).
All data is SYNTHETIC.

READINGS (also in kit-log/raw/S3-R15-A-notes.txt):
- "Each saved record" is the analysis's runs/<run id>/manifest.json (S2; the run id is the
  result's in reply.results, since reply.run_ids lists counts only): its `router` and
  `model_id`. turn.json's model_id is checked too.
"""
import json
import sys
from pathlib import Path

import pytest

from p1support import FAKE_ANTHROPIC_KEY, FAKE_SECRETS, FakeModel, Step, finish
from s3sagent import QUESTION, StatsEnv, analyze_case, slot_text
from s3support import turn_json
import s3ssupport as T

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "s3s2") not in sys.path:
    sys.path.insert(0, str(TESTS / "s3s2"))

import s2support as T2  # noqa: E402
from s2agent import Q_RATE, S2Env, rate_call  # noqa: E402

N_MODEL = "test-org/nvidia-model-r15"
A_MODEL = "test-org/anthropic-model-r15"
SETTINGS = {"NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"], "NVIDIA_MODEL": N_MODEL,
            "NVIDIA_BASE_URL": "https://nvidia.example.invalid/v1",
            "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY, "ANTHROPIC_MODEL": A_MODEL,
            "ANTHROPIC_BASE_URL": "https://anthropic.example.invalid/v1/"}
ROUTERS = {"nvidia": "NVIDIA_MODEL_TOOL_CALL", "anthropic": "ANTHROPIC_MODEL_TOOL_CALL"}
MODELS = {"nvidia": N_MODEL, "anthropic": A_MODEL}
TREND = "trend_all"
RATE = "all_2025"


def analysis_record(reply, runs_dir):
    """The one analysis of the turn and its saved record (manifest.json)."""
    (result,) = [r for r in reply.results if r.get("kind") == "analysis"]
    path = Path(runs_dir) / result["run_id"] / "manifest.json"
    assert path.is_file(), f"no record at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_records(env, reply, provider):
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    record = analysis_record(reply, env.runs_dir)
    assert (record["router"], record["model_id"]) == (ROUTERS[provider], MODELS[provider]), \
        (record["router"], record["model_id"])
    assert turn_json(reply, env.runs_dir)["model_id"] == MODELS[provider]
    assert reply.model_id == MODELS[provider]


@pytest.mark.needs_r
@pytest.mark.parametrize("provider", ["anthropic", "nvidia"])
def test_an_analyze_turns_record_names_the_active_services_router(tmp_path, monkeypatch, provider):
    env = StatsEnv(tmp_path, monkeypatch, MOCO_MODEL_PROVIDER=provider, **SETTINGS)
    model = FakeModel(Step(analyze_case(TREND)), Step(finish("finding", slot_text(TREND))),
                      clock=env.clock, model_id=MODELS[provider])
    reply = env.ask(QUESTION[T.case(TREND)["kind"]], model=model)
    assert_records(env, reply, provider)


@pytest.mark.needs_r
@pytest.mark.parametrize("provider", ["anthropic", "nvidia"])
def test_a_rate_turns_record_names_the_active_services_router(tmp_path, monkeypatch, provider):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)  # as tests/s3s2/conftest.py does
    env = S2Env(tmp_path, monkeypatch, names=(T2.CASES[RATE][0],), MOCO_MODEL_PROVIDER=provider,
                **SETTINGS)
    model = FakeModel(Step(rate_call(T2.analyze_arguments(RATE))),
                      Step(finish("finding", "I found that.")), clock=env.clock,
                      model_id=MODELS[provider])
    reply = env.ask(Q_RATE, model=model)
    assert_records(env, reply, provider)
    assert analysis_record(reply, env.runs_dir)["kind"] == "rate"
