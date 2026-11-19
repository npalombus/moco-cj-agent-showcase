"""Brief S3-R14-A: C51 of docs/S3A-DESIGN.md (D-071), the model service is a setting. Tests only;
the planning chat builds C51. No test reaches a model service: every key is made up (p1support's
FAKE_SECRETS and FAKE_ANTHROPIC_KEY, built from pieces and shaped like no real key), every model
request goes to a fake transport (test_p1_llm.FakeTransport) or to a recorder put in the place of
`openai.OpenAI`, which sends nothing, and the conftest blocks every socket. All data is SYNTHETIC.

What is tested, as C51 lists it under "Tests":
- point 1: the default provider is `nvidia`; a third value is a ConfigError naming the key and
  the two values; with `nvidia` and all three Anthropic settings set, the request, the model_id,
  the key and address the transport connects with, and the router are today's;
- point 2: the three defaults; an empty value counts as unset; ANTHROPIC_API_KEY shown as `set`
  or `missing`, its value in no repr or str; config.SECRETS keeps its three names;
- point 3, with `anthropic`: the request's keys exactly as 3b; the model_id; the transport's key
  and address; TransportError("auth") with no Anthropic key and an NVIDIA key set, nothing
  connected; tries, waits and the breaker as test_p1_llm shows them for `nvidia` (a few cases);
  the Anthropic key in no exception, log line or step;
- point 4: require_for_model and require_for_serve for both providers;
- point 5 in SYNTHETIC mode: one turn in each provider with a model stand-in;
- point 6: config.with_model for both providers.
The county turn of point 5 is tests/s3/test_s3_c51.py; the key-shape scan is
tests/p1/test_p1_no_secrets.py.

READINGS (also in kit-log/raw/S3-R14-A-notes.txt):
- C51-1. "The transport": the default transport, used when NvidiaModelClient gets none; it is
  llm.OpenAITransport today and C51 3d keeps the rest of llm.py as it is. The tests that need it
  build the client with no transport (the recorder sees what it connects with); the auth test
  also calls llm.OpenAITransport itself. The recorder is put at `openai.OpenAI` and, should the
  build import the name into llm, at `llm.OpenAI` too.
- C51-2. The timeout "as today": float(MOCO_MODEL_TIMEOUT_SECONDS), compared as a number; "no
  retries of the package's own": max_retries=0.
- C51-3. Point 5's router follows MOCO_MODEL_PROVIDER, not the client: A14 makes a model client
  anything with .model_id and .step, and the brief asks for a turn "with anthropic and a model
  stand-in". The stand-in's model_id is the active service's model (ANTHROPIC_MODEL with
  `anthropic`), so the record's model_id is the same whether the build reads it from the client
  (as today) or from the settings.
- C51-4. "The record" of a SYNTHETIC turn: each run's manifest.json (stage 1's record, which holds
  `router` and the technical line `technical_summary`), its report.md (which repeats both), and the
  turn's turn.json (which holds `model_id`). "The technical line" holds `Router: <router>.` and,
  for an answered count, `Model: <model_id>.`, as today. The turn has a count the data does not
  cover, so a refused run's record is checked too: the model chose that call as well.
- C51-5. An unset secret may read as None or "" (as test_p1_settings accepts). "Shown as set or
  missing": repr and str name `anthropic_api_key` followed by `=` or `:` and the word.
- C51-6. "Nothing else changed" (point 6): every field of the Settings dataclass but the one
  model; the settings given are not changed, and a client built from the result has that model.
- The conftest hides NVIDIA_, SLACK_, MOCO_ and OPENAI_ variables of the real environment, not
  ANTHROPIC_ ones; these tests take every ANTHROPIC_ variable out of the process environment for
  their own run (none is read or shown), so a build that also read os.environ sees none.

Not tested, because neither C51's list of tests nor the brief names them: the terminal's MODEL:
line, serve's first log line and printed line (point 5); tools/county_check.py and
tools/loop_check.py using with_model (point 6).
"""
import copy
import dataclasses
import json
import logging
import os
import re
from types import SimpleNamespace

import openai
import pytest

from p1support import (FAKE_ANTHROPIC_KEY, FAKE_SECRETS, ONE_COUNT_TEXT, TEAM, USER, USER2, Env,
                       FakeClock, FakeModel, Step, assert_no_anthropic_key, assert_no_secret, count,
                       finish, make_settings, manifests, mod, saved_text, turn_record)
from support import SUPPORTED
from test_p1_llm import (ARGS, GOOD, MESSAGES, NO_ID, TOOLS, FakeSleep, FakeTransport, _all_text,
                         _logged, calls_of, response, step, unavailable)

NVIDIA_KEY = FAKE_SECRETS["NVIDIA_API_KEY"]
N_MODEL = "test-org/nvidia-model-zz"
N_URL = "https://nvidia.example.invalid/v1"
A_MODEL = "test-org/anthropic-model-zz"
A_URL = "https://anthropic.example.invalid/v1/"
ALL_ANTHROPIC = {"ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY, "ANTHROPIC_MODEL": A_MODEL,
                 "ANTHROPIC_BASE_URL": A_URL}
EXTRA = '{"chat_template_kwargs": {"enable_thinking": false}}'
EXTRA_DICT = {"chat_template_kwargs": {"enable_thinking": False}}

# Point 2's defaults.
A_DEFAULT_MODEL = "claude-haiku-5-5"
A_DEFAULT_URL = "https://api.anthropic.com/v1/"

ROUTERS = {"nvidia": "NVIDIA_MODEL_TOOL_CALL", "anthropic": "ANTHROPIC_MODEL_TOOL_CALL"}
MODELS = {"nvidia": N_MODEL, "anthropic": A_MODEL}
OWN_KEY = {"nvidia": "NVIDIA_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
KEY_VALUES = {"NVIDIA_API_KEY": NVIDIA_KEY, "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY}
OTHER = {"nvidia": "anthropic", "anthropic": "nvidia"}
PROVIDERS = ["nvidia", "anthropic"]

# 3b: exactly these with `anthropic`; today's request adds `temperature`.
ANTHROPIC_REQUEST_KEYS = {"model", "messages", "tools", "tool_choice", "max_tokens", "extra_body"}
NVIDIA_REQUEST_KEYS = ANTHROPIC_REQUEST_KEYS | {"temperature"}

SLACK_VALUES = {"SLACK_BOT_TOKEN": FAKE_SECRETS["SLACK_BOT_TOKEN"],
                "SLACK_APP_TOKEN": FAKE_SECRETS["SLACK_APP_TOKEN"],
                "SLACK_ALLOWED_TEAM_ID": TEAM, "SLACK_ALLOWED_USER_IDS": f"{USER},{USER2}"}
SERVE_OTHER_KEYS = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ALLOWED_TEAM_ID",
                    "SLACK_ALLOWED_USER_IDS"]
THIRD_VALUES = ["openai", "claude", "haiku", "none"]

Q_COUNT = SUPPORTED["S1"][0]  # 2025, ages 18 to 25; no guard rule matches it


@pytest.fixture(autouse=True)
def _no_real_anthropic_variable(monkeypatch):
    """Take every ANTHROPIC_ variable out of the process environment for the test (not read,
    not shown): the conftest hides only NVIDIA_, SLACK_, MOCO_ and OPENAI_ ones."""
    for key in list(os.environ):
        if key.startswith("ANTHROPIC_"):
            monkeypatch.delenv(key)


def settings_of(tmp_path, provider=None, file_text="", **values):
    if provider is not None:
        values["MOCO_MODEL_PROVIDER"] = provider
    return make_settings(tmp_path, file_text, **values)


def everything(tmp_path, provider, **values):
    """Both services fully set (made-up keys, test models and addresses); then `values`."""
    base = dict(NVIDIA_API_KEY=NVIDIA_KEY, NVIDIA_MODEL=N_MODEL, NVIDIA_BASE_URL=N_URL,
                **ALL_ANTHROPIC)
    base.update(values)
    return settings_of(tmp_path, provider, **base)


def client_of(settings, transport=None, *, sleep=None, clock=None):
    """NvidiaModelClient (the class name stays, point 7); with transport None, the default."""
    kw = {} if transport is None else {"transport": transport}
    return mod("llm").NvidiaModelClient(settings, sleep=sleep if sleep is not None else FakeSleep(),
                                        clock=clock if clock is not None else FakeClock(), **kw)


class OpenAIRecorder:
    """Stands in for openai.OpenAI. Records the arguments each client was built with and every
    request; sends nothing; answers GOOD."""

    def __init__(self, monkeypatch):
        recorder = self
        self.built = []
        self.requests = []

        class FakeOpenAI:
            def __init__(self, *args, **kwargs):
                recorder.built.append((args, kwargs))
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

            def _create(self, *args, **kwargs):
                recorder.requests.append((args, copy.deepcopy(kwargs)))
                return SimpleNamespace(model_dump=lambda: copy.deepcopy(GOOD))

        monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
        monkeypatch.setattr(mod("llm"), "OpenAI", FakeOpenAI, raising=False)

    def connected_with(self):
        """(key, address, timeout, max_retries) of the one client built. (Plain raises: what
        was recorded holds a key and is never shown.)"""
        if len(self.built) != 1:
            raise AssertionError(f"{len(self.built)} clients built, not 1")
        args, kwargs = self.built[0]
        if args:
            raise AssertionError("openai.OpenAI was given positional arguments")
        return (kwargs.get("api_key"), kwargs.get("base_url"), kwargs.get("timeout"),
                kwargs.get("max_retries"))

    def nothing_connected(self):
        return not self.built and not self.requests


def check_key(value, wanted, message):
    """A key compared without showing either value (a plain raise, which pytest does not
    rewrite; its frame, which would show the arguments, is hidden from tracebacks)."""
    __tracebackhide__ = True
    if value != wanted:
        raise AssertionError(message)


# ---- point 1: the setting ---------------------------------------------------------------------

def test_the_default_provider_is_nvidia(tmp_path):
    assert settings_of(tmp_path).moco_model_provider == "nvidia"


@pytest.mark.parametrize("where", ["environ", "file"])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_each_provider_loads(provider, where, tmp_path):
    if where == "environ":
        settings = settings_of(tmp_path, provider)
    else:
        settings = settings_of(tmp_path, file_text=f"MOCO_MODEL_PROVIDER={provider}\n")
    assert settings.moco_model_provider == provider


@pytest.mark.parametrize("where", ["environ", "file"])
@pytest.mark.parametrize("value", THIRD_VALUES)
def test_a_third_value_is_a_config_error_naming_the_key_and_the_two_values(value, where,
                                                                             tmp_path):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        if where == "environ":
            settings_of(tmp_path, value)
        else:
            settings_of(tmp_path, file_text=f"MOCO_MODEL_PROVIDER={value}\n")
    message = str(caught.value)
    for word in ("MOCO_MODEL_PROVIDER", "nvidia", "anthropic"):
        assert word in message, (word, message)


@pytest.mark.parametrize("where", ["environ", "file"])
def test_an_empty_provider_counts_as_unset(where, tmp_path):
    if where == "environ":
        settings = settings_of(tmp_path, "")
    else:
        settings = settings_of(tmp_path, file_text="MOCO_MODEL_PROVIDER=\n")
    assert settings.moco_model_provider == "nvidia"


def test_with_nvidia_and_every_anthropic_setting_the_model_id_is_nvidias(tmp_path):
    model = client_of(everything(tmp_path, "nvidia"), FakeTransport(GOOD))
    assert model.model_id == N_MODEL


@pytest.mark.parametrize("extra", [None, EXTRA], ids=["no_extra_body", "extra_body"])
def test_with_nvidia_and_every_anthropic_setting_the_request_is_todays(extra, tmp_path):
    values = {} if extra is None else {"NVIDIA_EXTRA_BODY": extra}
    transport = FakeTransport(GOOD)
    step(client_of(everything(tmp_path, "nvidia", MOCO_MODEL_MAX_TOKENS="77", **values),
                   transport))
    (request,) = transport.requests
    assert set(request) == NVIDIA_REQUEST_KEYS, sorted(request)
    assert (request["model"], request["tool_choice"], request["temperature"],
            request["max_tokens"]) == (N_MODEL, "auto", 0, 77)
    assert (request["messages"], request["tools"]) == (MESSAGES, TOOLS)
    assert request["extra_body"] == ({} if extra is None else EXTRA_DICT)


def test_with_nvidia_and_every_anthropic_setting_the_transport_connects_as_today(tmp_path,
                                                                                 monkeypatch):
    recorder = OpenAIRecorder(monkeypatch)
    result = step(client_of(everything(tmp_path, "nvidia", NVIDIA_EXTRA_BODY=EXTRA)))
    assert calls_of(result) == [("count_arrests", ARGS)]
    key, url, timeout, retries = recorder.connected_with()
    check_key(key, NVIDIA_KEY, "not the NVIDIA key")
    assert (url, timeout, retries) == (N_URL, 45, 0)
    (args, sent), = recorder.requests
    assert args == () and set(sent) == NVIDIA_REQUEST_KEYS, sorted(sent)
    assert (sent["model"], sent["temperature"], sent["extra_body"]) == (N_MODEL, 0, EXTRA_DICT)


def test_with_nvidia_and_no_nvidia_key_the_transport_raises_auth_whatever_anthropic_holds(
        tmp_path, monkeypatch):
    llm = mod("llm")
    recorder = OpenAIRecorder(monkeypatch)
    settings = settings_of(tmp_path, "nvidia", **ALL_ANTHROPIC)
    with pytest.raises(llm.TransportError) as caught:
        llm.OpenAITransport(settings)(copy.deepcopy(request_of_today()))
    assert caught.value.kind == "auth"
    assert recorder.nothing_connected(), "a client was built or a request made"


def request_of_today():
    return {"model": N_MODEL, "messages": MESSAGES, "tools": TOOLS, "tool_choice": "auto",
            "max_tokens": 77, "extra_body": {}}


# ---- point 2: the three Anthropic settings ---------------------------------------------------

def test_config_secrets_keeps_its_three_names():
    assert mod("config").SECRETS == ("NVIDIA_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN")


def test_the_three_defaults(tmp_path):
    settings = settings_of(tmp_path)
    assert settings.anthropic_api_key in (None, "")
    assert settings.anthropic_model == A_DEFAULT_MODEL
    assert settings.anthropic_base_url == A_DEFAULT_URL


@pytest.mark.parametrize("provider", [None, "anthropic"], ids=["default_provider", "anthropic"])
def test_the_three_defaults_with_either_provider(provider, tmp_path):
    settings = settings_of(tmp_path, provider)
    assert (settings.anthropic_model, settings.anthropic_base_url) == (A_DEFAULT_MODEL,
                                                                       A_DEFAULT_URL)


@pytest.mark.parametrize("where", ["environ", "file"])
def test_the_anthropic_settings_are_read_as_every_other_setting(where, tmp_path):
    if where == "environ":
        settings = settings_of(tmp_path, **ALL_ANTHROPIC)
    else:
        settings = settings_of(tmp_path, file_text="".join(f"{k}={v}\n"
                                                           for k, v in ALL_ANTHROPIC.items()))
    check_key(settings.anthropic_api_key, FAKE_ANTHROPIC_KEY, "the key was not loaded")
    assert (settings.anthropic_model, settings.anthropic_base_url) == (A_MODEL, A_URL)


def test_the_environment_wins_over_the_file_for_the_anthropic_settings(tmp_path):
    settings = settings_of(tmp_path, file_text="ANTHROPIC_MODEL=file-org/file-model\n"
                                               "ANTHROPIC_BASE_URL=https://file.invalid/v1/\n"
                                               "MOCO_MODEL_PROVIDER=nvidia\n",
                           ANTHROPIC_MODEL=A_MODEL, ANTHROPIC_BASE_URL=A_URL,
                           MOCO_MODEL_PROVIDER="anthropic")
    assert (settings.anthropic_model, settings.anthropic_base_url,
            settings.moco_model_provider) == (A_MODEL, A_URL, "anthropic")


@pytest.mark.parametrize("where", ["environ", "file"])
def test_an_empty_anthropic_value_counts_as_unset(where, tmp_path):
    keys = ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL")
    if where == "environ":
        settings = settings_of(tmp_path, **{key: "" for key in keys})
    else:
        settings = settings_of(tmp_path, file_text="".join(f"{key}=\n" for key in keys))
    assert settings.anthropic_api_key in (None, "")
    assert (settings.anthropic_model, settings.anthropic_base_url) == (A_DEFAULT_MODEL,
                                                                       A_DEFAULT_URL)
    for text in (str(settings), repr(settings)):
        assert shown_as(text, "missing"), "an empty key does not show as missing"


def shown_as(text, word):
    return re.search(r"anthropic_api_key['\"]?\s*[=:]\s*['\"]?" + word + r"\b", text,
                     re.IGNORECASE) is not None


@pytest.mark.parametrize("where", ["environ", "file"])
def test_the_anthropic_key_shows_as_set_and_its_value_nowhere(where, tmp_path):
    values = dict(FAKE_SECRETS, **ALL_ANTHROPIC)
    if where == "environ":
        settings = settings_of(tmp_path, "anthropic", **values)
    else:
        settings = settings_of(tmp_path, file_text="".join(f"{k}={v}\n" for k, v in values.items()))
    check_key(settings.anthropic_api_key, FAKE_ANTHROPIC_KEY, "the key was not loaded")
    for text in (str(settings), repr(settings), f"{settings}"):
        assert_no_anthropic_key(text)
        assert_no_secret(text)
        assert shown_as(text, "set"), "the Anthropic key does not show as set"


def test_the_anthropic_key_shows_as_missing(tmp_path):
    settings = settings_of(tmp_path, "anthropic", NVIDIA_API_KEY=NVIDIA_KEY)
    for text in (str(settings), repr(settings)):
        assert shown_as(text, "missing"), "the Anthropic key does not show as missing"
        assert_no_secret(text)


# ---- point 3: with anthropic ---------------------------------------------------------------

def test_with_anthropic_the_model_id_is_anthropic_model(tmp_path):
    assert client_of(everything(tmp_path, "anthropic"), FakeTransport(GOOD)).model_id == A_MODEL


def test_with_anthropic_and_no_anthropic_model_the_model_id_is_the_default(tmp_path):
    settings = settings_of(tmp_path, "anthropic", ANTHROPIC_API_KEY=FAKE_ANTHROPIC_KEY,
                           NVIDIA_MODEL=N_MODEL)
    assert client_of(settings, FakeTransport(GOOD)).model_id == A_DEFAULT_MODEL


@pytest.mark.parametrize("extra", [None, EXTRA], ids=["no_extra_body", "nvidia_extra_body_set"])
def test_with_anthropic_the_request_holds_exactly_3bs_keys(extra, tmp_path):
    values = {} if extra is None else {"NVIDIA_EXTRA_BODY": extra}
    transport = FakeTransport(GOOD)
    step(client_of(everything(tmp_path, "anthropic", MOCO_MODEL_MAX_TOKENS="77", **values),
                   transport))
    (request,) = transport.requests
    assert set(request) == ANTHROPIC_REQUEST_KEYS, sorted(request)
    assert "temperature" not in request
    assert (request["model"], request["tool_choice"], request["max_tokens"],
            request["extra_body"]) == (A_MODEL, "auto", 77, {})
    assert (request["messages"], request["tools"]) == (MESSAGES, TOOLS)


def test_with_anthropic_max_tokens_is_moco_model_max_tokens_by_default(tmp_path):
    transport = FakeTransport(GOOD)
    step(client_of(everything(tmp_path, "anthropic"), transport))
    assert transport.requests[0]["max_tokens"] == 2048


@pytest.mark.parametrize("set_url", [True, False], ids=["anthropic_base_url", "default_url"])
def test_with_anthropic_the_transport_connects_with_the_anthropic_key_and_address(
        set_url, tmp_path, monkeypatch):
    recorder = OpenAIRecorder(monkeypatch)
    values = {} if set_url else {"ANTHROPIC_BASE_URL": ""}
    settings = everything(tmp_path, "anthropic", NVIDIA_EXTRA_BODY=EXTRA,
                          MOCO_MODEL_TIMEOUT_SECONDS="33", **values)
    result = step(client_of(settings))
    assert calls_of(result) == [("count_arrests", ARGS)]
    key, url, timeout, retries = recorder.connected_with()
    check_key(key, FAKE_ANTHROPIC_KEY, "not the Anthropic key")
    assert (url, timeout, retries) == ((A_URL if set_url else A_DEFAULT_URL), 33, 0)
    (args, sent), = recorder.requests
    assert args == () and set(sent) == ANTHROPIC_REQUEST_KEYS, sorted(sent)
    assert (sent["model"], sent["extra_body"]) == (A_MODEL, {})


def test_with_anthropic_and_no_anthropic_key_the_transport_raises_auth_and_connects_nothing(
        tmp_path, monkeypatch):
    """3c: whatever NVIDIA_API_KEY holds (here: a key)."""
    llm = mod("llm")
    recorder = OpenAIRecorder(monkeypatch)
    settings = settings_of(tmp_path, "anthropic", NVIDIA_API_KEY=NVIDIA_KEY,
                           ANTHROPIC_MODEL=A_MODEL, ANTHROPIC_BASE_URL=A_URL)
    with pytest.raises(llm.TransportError) as caught:
        llm.OpenAITransport(settings)(copy.deepcopy(request_of_today()))
    assert caught.value.kind == "auth"
    assert recorder.nothing_connected(), "a client was built or a request made"


def test_with_anthropic_and_no_anthropic_key_the_client_fails_at_once_as_auth(tmp_path,
                                                                              monkeypatch,
                                                                              caplog):
    """The default transport through the client: auth is not retried (no wait, with one retry
    allowed), the log line says auth, nothing is connected."""
    caplog.set_level(logging.DEBUG)
    recorder = OpenAIRecorder(monkeypatch)
    sleep = FakeSleep()
    settings = settings_of(tmp_path, "anthropic", NVIDIA_API_KEY=NVIDIA_KEY,
                           ANTHROPIC_MODEL=A_MODEL)
    unavailable(client_of(settings, sleep=sleep))
    assert sleep.waits == []
    assert "auth" in caplog.text
    assert recorder.nothing_connected(), "a client was built or a request made"
    assert_no_secret(_logged(caplog))


# Tries, waits and the breaker as test_p1_llm shows them for nvidia (a few cases).

@pytest.mark.parametrize("kind", ["timeout", "server"])
def test_with_anthropic_a_retried_error_makes_2_tries_waiting_1(kind, tmp_path):
    transport, sleep = FakeTransport(kind), FakeSleep()
    unavailable(client_of(everything(tmp_path, "anthropic"), transport, sleep=sleep))
    assert len(transport.requests) == 2 and sleep.waits == [1]


def test_with_anthropic_three_retries_wait_1_then_2_then_4(tmp_path):
    transport, sleep = FakeTransport("rate_limit"), FakeSleep()
    unavailable(client_of(everything(tmp_path, "anthropic", MOCO_MODEL_MAX_RETRIES="3"),
                          transport, sleep=sleep))
    assert len(transport.requests) == 4 and sleep.waits == [1, 2, 4]


def test_with_anthropic_a_retry_that_works_returns_the_step(tmp_path):
    transport, sleep = FakeTransport("network", GOOD), FakeSleep()
    result = step(client_of(everything(tmp_path, "anthropic"), transport, sleep=sleep))
    assert calls_of(result) == [("count_arrests", ARGS)]
    assert len(transport.requests) == 2 and sleep.waits == [1]


@pytest.mark.parametrize("kind, status", [("auth", 401), ("client", 400)])
def test_with_anthropic_auth_and_client_errors_are_not_retried_and_log_their_status(
        kind, status, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    transport, sleep = FakeTransport((kind, status)), FakeSleep()
    unavailable(client_of(everything(tmp_path, "anthropic", MOCO_MODEL_MAX_RETRIES="3"),
                          transport, sleep=sleep))
    assert len(transport.requests) == 1 and sleep.waits == []
    assert f"{kind} (HTTP {status})" in caplog.text


def test_with_anthropic_the_breaker_opens_after_3_failed_calls_and_closes_after_60_seconds(
        tmp_path):
    clock, sleep = FakeClock(), FakeSleep()
    transport = FakeTransport("server", "server", "server", GOOD)
    model = client_of(everything(tmp_path, "anthropic", MOCO_MODEL_MAX_RETRIES="0"), transport,
                      sleep=sleep, clock=clock)
    for _ in range(3):
        unavailable(model)
    unavailable(model)  # open: at once, without the transport
    clock.now += 59
    unavailable(model)
    assert len(transport.requests) == 3
    clock.now += 2  # 61 seconds after it opened
    assert calls_of(step(model)) == [("count_arrests", ARGS)]
    assert len(transport.requests) == 4 and sleep.waits == []


def test_with_anthropic_an_unreadable_response_raises_model_unavailable(tmp_path):
    unavailable(client_of(everything(tmp_path, "anthropic", MOCO_MODEL_MAX_RETRIES="0"),
                          FakeTransport({"choices": []})))


# The Anthropic key in no exception and no log line: test_p1_llm's two tests of the NVIDIA key.

@pytest.mark.parametrize("outcome", ["timeout", "rate_limit", "server", "network", "auth",
                                     "client", "unreadable"])
def test_the_anthropic_key_appears_in_no_exception_and_no_log_line(outcome, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    transport = FakeTransport({} if outcome == "unreadable" else outcome)
    model = client_of(everything(tmp_path, "anthropic", MOCO_MODEL_MAX_RETRIES="1"), transport)
    errors = [unavailable(model) for _ in range(4)]  # the 4th comes from the open breaker
    for error in errors:
        assert_no_anthropic_key(_all_text(error))
        assert_no_secret(_all_text(error))
    assert_no_anthropic_key(_logged(caplog))
    assert_no_secret(_logged(caplog))
    assert_no_anthropic_key(repr(model) + str(model))


def test_the_anthropic_key_appears_in_no_step_and_no_log_line(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    result = step(client_of(everything(tmp_path, "anthropic"), FakeTransport(response(
        ("count_arrests", ARGS), ("describe_data", "{}", NO_ID), content="some words"))))
    shown = repr(result) + str(result) + json.dumps(
        [[c.id, c.name, c.arguments_json] for c in result.tool_calls] + [result.text])
    assert_no_anthropic_key(shown)
    assert_no_anthropic_key(_logged(caplog))


def test_the_anthropic_key_appears_in_no_log_line_through_the_default_transport(tmp_path,
                                                                                monkeypatch,
                                                                                caplog):
    caplog.set_level(logging.DEBUG)
    OpenAIRecorder(monkeypatch)
    model = client_of(everything(tmp_path, "anthropic"))
    result = step(model)
    assert_no_anthropic_key(_logged(caplog) + repr(result) + repr(model) + str(model))


# ---- point 4: what a run needs ------------------------------------------------------------

def config_error(call, settings):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        call(settings)
    message = str(caught.value)
    assert_no_secret(message)
    assert_no_anthropic_key(message)
    for value in (TEAM, USER, USER2):
        assert value not in message, "a value appears in the message"
    return message


@pytest.mark.parametrize("provider", PROVIDERS)
def test_require_for_model_own_key_missing_names_it_and_not_the_other(provider, tmp_path):
    other_key = OWN_KEY[OTHER[provider]]
    settings = settings_of(tmp_path, provider, **{other_key: KEY_VALUES[other_key]})
    message = config_error(mod("config").require_for_model, settings)
    assert OWN_KEY[provider] in message
    assert other_key not in message


@pytest.mark.parametrize("provider", PROVIDERS)
def test_require_for_model_passes_with_the_other_services_key_missing(provider, tmp_path):
    own = OWN_KEY[provider]
    settings = settings_of(tmp_path, provider, **{own: KEY_VALUES[own]})
    assert mod("config").require_for_model(settings) is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_require_for_serve_own_key_missing_names_it_and_not_the_other(provider, tmp_path):
    other_key = OWN_KEY[OTHER[provider]]
    settings = settings_of(tmp_path, provider, **SLACK_VALUES,
                           **{other_key: KEY_VALUES[other_key]})
    message = config_error(mod("config").require_for_serve, settings)
    assert OWN_KEY[provider] in message
    assert other_key not in message
    for key in SERVE_OTHER_KEYS:
        assert key not in message, key


@pytest.mark.parametrize("provider", PROVIDERS)
def test_require_for_serve_passes_with_the_other_services_key_missing(provider, tmp_path):
    own = OWN_KEY[provider]
    settings = settings_of(tmp_path, provider, **SLACK_VALUES, **{own: KEY_VALUES[own]})
    assert mod("config").require_for_serve(settings) is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_require_for_serve_with_nothing_set_names_every_needed_key_and_not_the_other(provider,
                                                                                     tmp_path):
    message = config_error(mod("config").require_for_serve, settings_of(tmp_path, provider))
    for key in [OWN_KEY[provider]] + SERVE_OTHER_KEYS:
        assert key in message, key
    assert OWN_KEY[OTHER[provider]] not in message


@pytest.mark.parametrize("key", SERVE_OTHER_KEYS)
def test_require_for_serve_with_anthropic_still_names_a_missing_slack_setting(key, tmp_path):
    values = {k: v for k, v in SLACK_VALUES.items() if k != key}
    settings = settings_of(tmp_path, "anthropic", ANTHROPIC_API_KEY=FAKE_ANTHROPIC_KEY, **values)
    message = config_error(mod("config").require_for_serve, settings)
    assert key in message
    assert "NVIDIA_API_KEY" not in message and "ANTHROPIC_API_KEY" not in message


# ---- point 5: a SYNTHETIC turn names the service that answered ------------------------------

def model_turn(tmp_path, provider):
    """One turn with every setting of both services: a count the data does not cover (a refused
    run), a count of 2025 ages 18 to 25, and a finish that passes. The stand-in's model_id is the
    active service's model (C51-3)."""
    env = Env(tmp_path, MOCO_MODEL_PROVIDER=provider, NVIDIA_API_KEY=NVIDIA_KEY,
              NVIDIA_MODEL=N_MODEL, NVIDIA_BASE_URL=N_URL, **ALL_ANTHROPIC)
    model = FakeModel(Step(count(2019, "all"), count(2025, "18_25")),
                      Step(finish("finding", ONE_COUNT_TEXT)), clock=env.clock,
                      model_id=MODELS[provider])
    reply = env.ask(Q_COUNT, model=model)
    assert (reply.status, reply.reply_style) == ("ANSWERED", "agent"), (reply.status,
                                                                        reply.reason_code,
                                                                        reply.text)
    return env, reply


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_synthetic_turn_records_the_active_services_model_id(provider, tmp_path):
    env, reply = model_turn(tmp_path, provider)
    assert reply.model_id == MODELS[provider]
    assert turn_record(reply, env.runs_dir)["model_id"] == MODELS[provider]
    (answered,) = [m for m in manifests(env.runs_dir) if m["status"] == "ANSWERED"]
    assert f"Model: {MODELS[provider]}." in answered["technical_summary"], \
        answered["technical_summary"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_synthetic_turn_records_the_active_services_router_and_technical_line(provider,
                                                                                tmp_path):
    env, reply = model_turn(tmp_path, provider)
    router = ROUTERS[provider]
    records = manifests(env.runs_dir)
    assert {m["status"] for m in records} == {"ANSWERED", "UNSUPPORTED"}, \
        [m["status"] for m in records]
    for record in records:
        assert record["router"] == router, (record["status"], record["router"])
        assert f"Router: {router}." in record["technical_summary"], record["technical_summary"]
        report = (env.runs_dir / record["run_id"] / "report.md").read_text(encoding="utf-8")
        assert f"- Router: {router}" in report


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_synthetic_turn_names_nothing_of_the_other_service(provider, tmp_path):
    env, reply = model_turn(tmp_path, provider)
    other = OTHER[provider]
    saved = saved_text(env.runs_dir) + reply.text + json.dumps(reply.to_dict(), default=str)
    for name in (ROUTERS[other], MODELS[other]):
        assert name not in saved, name


def test_a_synthetic_turn_with_anthropic_saves_and_replies_no_key(tmp_path):
    env, reply = model_turn(tmp_path, "anthropic")
    shown = saved_text(env.runs_dir) + reply.text + json.dumps(reply.to_dict(), default=str)
    assert_no_anthropic_key(shown)
    assert_no_secret(shown)


# ---- point 6: config.with_model --------------------------------------------------------------

CHOSEN = "test-org/chosen-model-zz"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_with_model_changes_the_active_services_model_and_nothing_else(provider, tmp_path):
    settings = everything(tmp_path, provider)
    changed = mod("config").with_model(settings, CHOSEN)
    attribute = f"{provider}_model"
    assert type(changed) is type(settings)
    assert getattr(changed, attribute) == CHOSEN
    before, after = dataclasses.asdict(settings), dataclasses.asdict(changed)
    assert sorted(k for k in before if before[k] != after[k]) == [attribute]
    assert getattr(settings, attribute) == MODELS[provider], "the settings given were changed"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_client_built_from_with_model_has_that_model(provider, tmp_path):
    changed = mod("config").with_model(everything(tmp_path, provider), CHOSEN)
    transport = FakeTransport(GOOD)
    model = client_of(changed, transport)
    step(model)
    assert model.model_id == transport.requests[0]["model"] == CHOSEN
