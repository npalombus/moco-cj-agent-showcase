"""Brief S3-R14-A: C51 point 5 of docs/S3A-DESIGN.md (D-071) in county mode. Tests only; the
planning chat builds C51. One county turn (MOCO_DATA=county, the SYNTHETIC fixture
arrests_like) with the model stand-in (p1support.FakeModel) in each provider, every setting of
both services given (made-up keys, test model names and addresses): the saved record's model_id
and router, and the turn record's model_id. No model service is reached; all data is SYNTHETIC.

READINGS (also in tests/p1/test_p1_c51.py and kit-log/raw/S3-R14-A-notes.txt):
- C51-3. The router follows MOCO_MODEL_PROVIDER, not the client (A14: a model client is anything
  with .model_id and .step); the stand-in's model_id is the active service's model.
- A county count's record (runs/<run id>/manifest.json) holds `router` and `model_id` and no
  technical line, so only those two are checked there; turn.json holds `model_id`.
- The conftest does not hide ANTHROPIC_ variables of the real environment; these tests take them
  out of the process environment for their own run (none is read or shown).
"""
import json
import os

import pytest

from p1support import (FAKE_ANTHROPIC_KEY, FAKE_SECRETS, FakeModel, Step,
                       assert_no_anthropic_key, assert_no_secret, finish, saved_text)
from s3support import (A_ID, Q_COUNT, CountyEnv, check_county_reply, count, run_records,
                       turn_json, year)

N_MODEL = "test-org/nvidia-model-zz"
A_MODEL = "test-org/anthropic-model-zz"
SETTINGS = {"NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"], "NVIDIA_MODEL": N_MODEL,
            "NVIDIA_BASE_URL": "https://nvidia.example.invalid/v1",
            "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY, "ANTHROPIC_MODEL": A_MODEL,
            "ANTHROPIC_BASE_URL": "https://anthropic.example.invalid/v1/"}
ROUTERS = {"nvidia": "NVIDIA_MODEL_TOOL_CALL", "anthropic": "ANTHROPIC_MODEL_TOOL_CALL"}
MODELS = {"nvidia": N_MODEL, "anthropic": A_MODEL}
OTHER = {"nvidia": "anthropic", "anthropic": "nvidia"}


@pytest.fixture(autouse=True)
def _no_real_anthropic_variable(monkeypatch):
    for key in list(os.environ):
        if key.startswith("ANTHROPIC_"):
            monkeypatch.delenv(key)


def county_turn(tmp_path, monkeypatch, provider):
    env = CountyEnv(tmp_path, monkeypatch, MOCO_MODEL_PROVIDER=provider, **SETTINGS)
    model = FakeModel(Step(count(A_ID, year(2025))), Step(finish("finding", "I counted {r1.count}.")),
                      clock=env.clock, model_id=MODELS[provider])
    reply = env.ask(Q_COUNT, model=model)
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return env, reply


@pytest.mark.parametrize("provider", ["nvidia", "anthropic"])
def test_a_county_turn_records_the_active_services_model_id_and_router(tmp_path, monkeypatch,
                                                                        provider):
    env, reply = county_turn(tmp_path, monkeypatch, provider)
    (record,) = run_records(reply, env.runs_dir)
    assert (record["router"], record["model_id"]) == (ROUTERS[provider], MODELS[provider])
    assert turn_json(reply, env.runs_dir)["model_id"] == MODELS[provider]
    assert reply.model_id == MODELS[provider]


@pytest.mark.parametrize("provider", ["nvidia", "anthropic"])
def test_a_county_turn_names_nothing_of_the_other_service(tmp_path, monkeypatch, provider):
    env, reply = county_turn(tmp_path, monkeypatch, provider)
    other = OTHER[provider]
    saved = saved_text(env.runs_dir) + reply.text + json.dumps(reply.to_dict(), default=str)
    for name in (ROUTERS[other], MODELS[other]):
        assert name not in saved, name


def test_a_county_turn_with_anthropic_saves_and_replies_no_key(tmp_path, monkeypatch):
    env, reply = county_turn(tmp_path, monkeypatch, "anthropic")
    shown = saved_text(env.runs_dir) + reply.text + json.dumps(reply.to_dict(), default=str)
    assert_no_anthropic_key(shown)
    assert_no_secret(shown)
