"""Brief S3-R20-A: C56 of docs/S3A-DESIGN.md (D-073, D-074), a backup model for a turn whose model
service is down. Tests only; the planning chat builds C56 (D-050). No model service is reached:
the model clients are stand-ins (p1support.FakeModel, which raises ModelUnavailable at its first
step or answers by script), or NvidiaModelClient over a fake transport that sends nothing; every
key is made up (p1support's FAKE_SECRETS and FAKE_ANTHROPIC_KEY); all data is SYNTHETIC (stage 1's
SYNTHETIC data file, and the SYNTHETIC fixtures of tests/s3 in county mode). No real figure.

The setup follows D-074: the active service is `anthropic` (in Claude's place, a test model name)
and the backup is `nvidia` with a model of its own (in Lightning's place), so the backup's model
differs from both NVIDIA_MODEL and ANTHROPIC_MODEL and every model id and router says which try
wrote it.

C56's points and its "Tests":
- point 1 and 2: `config` directly (the two settings, their errors, backup_settings, the two
  require_ functions);
- point 3: build_app and handle_question take `backup`; leaving it out changes nothing;
- points 4 to 8 and every example of "Tests": turns through handle_question in county mode and in
  stage 1's mode, talk off and on where the point is about the reply text;
- the six (and more) of the brief's own, marked OWN below.

READINGS (also in kit-log/raw/S3-R20-A-notes.txt):
- R20-1. The note is joined to the reply by exactly one line break ("one more line, after a line
  break"), and is the text's last line: text == <the second try's own text> + "\n" + NOTE.
- R20-2. "The second try's own text" is what the same message gets as a turn of its own, with no
  backup, on the backup's settings and a stand-in that plays the backup's script, in a fresh
  agent with the same thread so far (the twin). Point 4 runs the second try "from its start" with
  nothing the first made, so its reply before the note is the twin's.
- R20-3. "The backup's client was called" means its step was called at least once.
- R20-4. Point 1's ConfigErrors are raised by load_settings, as A14's and C51's are.
- R20-5. "One of the two settings set without the other": the message names at least one of
  the two keys (which one is not said); it holds no value given.
- R20-6. Point 6's router: turn.json holds no router today (the run records do: C51's tests read
  it there). The second try's run records name the backup's router; turn.json may hold a
  `router` key or not, and if it does it is the backup's (briefs/QUESTIONS.md, S3-R20-A q. 1).
- R20-7. A second try that ends RATE_LIMITED (the daily limit reached by the first try) calls no
  model: its reply is sent, with no note; its model_id is not checked (None or the backup's).
- R20-8. The backup's own second try that ends with its model failing after a count was made is
  ANSWERED with the fixed rendering, not "ended MODEL_UNAVAILABLE"; whether it gets the note is
  open (QUESTIONS.md, S3-R20-A q. 2): both accepted.
- R20-9. The first try's record is the turn.json under runs/ other than the reply's own.
"""
import dataclasses
import inspect
import json
import logging
import os
import sys
from datetime import timedelta, timezone
from pathlib import Path

import pytest

import p1support as p1
from p1support import (FAKE_ANTHROPIC_KEY, FAKE_SECRETS, NOW, ONE_COUNT_TEXT, TEAM, THREAD_1,
                       TODAY, TURN_ID, USER, USER2, Env, FakeModel, Step, assert_fixed,
                       assert_no_anthropic_key, assert_no_secret, decline, describe, finish,
                       make_settings, manifests, mod)
from s3support import (A_ID, NOW_S3, Q_COUNT, TODAY_S3, CountyEnv, count, county_settings,
                       guard_free, year)
from support import DATA_CSV, SUPPORTED
from test_p1_llm import FakeSleep, FakeTransport, response

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import HELLO_TEXT  # noqa: E402

DESIGN = TESTS.parent / "docs" / "S3A-DESIGN.md"

# C56 point 5, word for word from the contract (not from the program).
NOTE = ("Note: I'm temporarily running on a smaller backup model, so this answer may be less "
        "sharp than usual.")

A_MODEL = "test-org/active-model-r20"    # ANTHROPIC_MODEL: the active service's model
N_MODEL = "test-org/nvidia-model-r20"    # NVIDIA_MODEL as set: not the backup's
B_MODEL = "test-org/backup-model-r20"    # MOCO_BACKUP_MODEL
A_URL = "https://anthropic.example.invalid/v1/"
N_URL = "https://nvidia.example.invalid/v1"
NVIDIA_KEY = FAKE_SECRETS["NVIDIA_API_KEY"]
SERVICES = {"MOCO_MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY,
            "ANTHROPIC_MODEL": A_MODEL, "ANTHROPIC_BASE_URL": A_URL,
            "NVIDIA_API_KEY": NVIDIA_KEY, "NVIDIA_MODEL": N_MODEL, "NVIDIA_BASE_URL": N_URL}
BACKUP = {"MOCO_BACKUP_PROVIDER": "nvidia", "MOCO_BACKUP_MODEL": B_MODEL}
ROUTERS = {"nvidia": "NVIDIA_MODEL_TOOL_CALL", "anthropic": "ANTHROPIC_MODEL_TOOL_CALL"}
OWN_KEY = {"nvidia": "NVIDIA_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
KEY_VALUES = {"NVIDIA_API_KEY": NVIDIA_KEY, "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY}
OTHER = {"nvidia": "anthropic", "anthropic": "nvidia"}
PROVIDERS = ["nvidia", "anthropic"]
SLACK_VALUES = {"SLACK_BOT_TOKEN": FAKE_SECRETS["SLACK_BOT_TOKEN"],
                "SLACK_APP_TOKEN": FAKE_SECRETS["SLACK_APP_TOKEN"],
                "SLACK_ALLOWED_TEAM_ID": TEAM, "SLACK_ALLOWED_USER_IDS": f"{USER},{USER2}"}
NVIDIA_REQUEST_KEYS = {"model", "messages", "tools", "tool_choice", "temperature", "max_tokens",
                       "extra_body"}  # C51 3b and today's request with `nvidia`

MODES = ["stage1", "county"]
TALK = ["off", "on"]
S1 = SUPPORTED["S1"][0]  # 2025, ages 18 to 25; no guard rule matches it
HELLO = "Hello there!"
Q_NO_PERIOD = "Can you count the arrests for me?"
TALK_FAILING = "I can look at two years for you."  # a talk text that fails NUMBER (T3's tests)
# Six sentences, 657 characters: it passes T1's check alone (at most 6 sentences and 700
# characters); with the note counted it would be 7 sentences and more than 700 characters.
SIX = ("Hello again, and thank you for writing to me today with a question about what I can do "
       "for you here. I am a helper that counts what is written down in the county's open data, "
       "and I can tell you plainly what I find there. You can ask me in plain words, the way you "
       "would ask a person sitting next to you at a desk in the same office. If something you ask "
       "is not clear to me, I will ask you a short question back before I count anything at all. "
       "When I answer, I will also tell you where the figures come from, so you can go and look "
       "at them yourself later. Whenever you are ready, just write your question here and I will "
       "get started on it right away for you.")

# The backup's scripts, by mode and by the kind of reply its second try ends with.
COUNTY_FINISH = "I counted {r1.count}."
SCRIPTS = {
    ("stage1", "answered"): (S1, [Step(p1.count(2025, "18_25")),
                                  Step(finish("finding", ONE_COUNT_TEXT))]),
    ("stage1", "asked"): (S1, [Step(p1.count(None, "18_25"))]),
    ("stage1", "fixed"): (S1, [Step(decline("UNSUPPORTED_METRIC"))]),
    ("stage1", "talk"): (HELLO, [Step(finish("talk", HELLO_TEXT))]),
    ("county", "answered"): (Q_COUNT, [Step(count(A_ID, year(2025))),
                                       Step(finish("finding", COUNTY_FINISH))]),
    ("county", "asked"): (Q_NO_PERIOD, [Step(count(A_ID))]),
    ("county", "fixed"): (Q_COUNT, [Step(decline("UNSUPPORTED_METRIC"))]),
    ("county", "talk"): (HELLO, [Step(finish("talk", HELLO_TEXT))]),
}
STATUS = {"answered": "ANSWERED", "asked": "NEEDS_INPUT", "fixed": "UNSUPPORTED",
          "talk": "TALKED"}
CASES = [(mode, talk, kind) for mode in MODES for talk in TALK
         for kind in ("answered", "asked", "fixed", "talk") if kind != "talk" or talk == "on"]
OMIT = object()  # handle_question is called without a `backup` argument


@pytest.fixture(autouse=True)
def _no_real_anthropic_variable(monkeypatch):
    """Take every ANTHROPIC_ variable out of the process environment for the test (not read, not
    shown), as tests/s3/test_s3_c51.py does; the conftest already hides MOCO_ ones."""
    for key in list(os.environ):
        if key.startswith("ANTHROPIC_"):
            monkeypatch.delenv(key)


# ---- one agent, its backup, and the stand-ins -----------------------------------------------

def unavailable():
    return mod("llm").ModelUnavailable("SYNTHETIC: the model service is down for this test")


def down(model_id=A_MODEL, **kw):
    """A model client that raises ModelUnavailable at its first step (and every step after)."""
    return FakeModel(error=unavailable(), model_id=model_id, **kw)


def standin(*steps, model_id=B_MODEL, **kw):
    """A model client that answers by script."""
    return FakeModel(*steps, model_id=model_id, **kw)


class Flaky:
    """A model client that raises ModelUnavailable at the calls numbered in `down` (0: its first)
    and plays its steps, in order, at the others (the last one repeats)."""

    def __init__(self, *steps, down=(0,), model_id=A_MODEL):
        self.model_id, self.steps, self.down = model_id, list(steps), set(down)
        self.calls, self.played = [], 0

    def step(self, messages, tools):
        llm = mod("llm")
        index = len(self.calls)
        self.calls.append({"messages": messages, "tools": tools})
        if index in self.down:
            raise unavailable()
        scripted = self.steps[min(self.played, len(self.steps) - 1)]
        self.played += 1
        return llm.ModelStep(tool_calls=[llm.ToolCall(
            id=f"flaky_{index}_{i}", name=name, arguments_json=json.dumps(arguments))
            for i, (name, arguments) in enumerate(scripted.calls)], text=scripted.text)


class World:
    """One agent in `folder`: county mode on the SYNTHETIC fixtures, or stage 1's SYNTHETIC mode.
    Its settings are SERVICES (+ BACKUP when `backup_set`) + `values`; `backup_settings` are the
    backup's (point 2, built here by hand: the same values with the backup's provider and model,
    and no backup of its own)."""

    def __init__(self, folder, monkeypatch, mode, *, backup_set=True, **values):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        first = {**SERVICES, **(BACKUP if backup_set else {}), **values}
        second = {**SERVICES, **{k: v for k, v in values.items()
                                 if not k.startswith("MOCO_BACKUP_")},
                  "MOCO_MODEL_PROVIDER": "nvidia", "NVIDIA_MODEL": B_MODEL}
        if mode == "county":
            self.env = CountyEnv(folder, monkeypatch, **first)
            self.backup_settings = county_settings(folder, self.env.state_dir, **second)
            self.now0, self.today, self.data_path = NOW_S3, TODAY_S3, None
        else:
            self.env = Env(folder, **first)
            self.backup_settings = make_settings(folder, **second)
            self.now0, self.today, self.data_path = NOW, TODAY, DATA_CSV
        self.turns = 0

    @property
    def clock(self):
        return self.env.clock

    @property
    def store(self):
        return self.env.store

    @property
    def runs_dir(self):
        return self.env.runs_dir

    def ask(self, question, first, backup=OMIT, *, settings=None, thread_key=THREAD_1,
            now=None):
        """One message through handle_question. `backup`: OMIT (no argument), None, a model
        client (given as the pair with backup_settings) or a pair as it is."""
        if now is None:
            now = self.now0 + timedelta(minutes=self.turns)
        self.turns += 1
        kw = dict(thread_key=thread_key, user_id=USER,
                  settings=settings if settings is not None else self.env.settings,
                  registry=self.env.registry, model_client=first, store=self.env.store,
                  runs_dir=self.env.runs_dir, today=self.today, now=now, clock=self.env.clock)
        if self.data_path is not None:
            kw["data_path"] = self.data_path
        if backup is not OMIT:
            kw["backup"] = backup if backup is None or isinstance(backup, tuple) \
                else (self.backup_settings, backup)
        return mod("agent").handle_question(question, **kw)

    def turn_records(self):
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(Path(self.runs_dir).glob("*/turn.json"))]

    def records_of(self, reply):
        """(the reply's own turn.json, every other turn.json)."""
        records = self.turn_records()
        own = [r for r in records if r["turn_id"] == reply.turn_id]
        assert len(own) == 1, [r["turn_id"] for r in records]
        return own[0], [r for r in records if r["turn_id"] != reply.turn_id]

    def memory(self, thread_key=THREAD_1):
        return self.store.recent_turns(thread_key, 100)

    def calls_today(self):
        return self.store.model_calls_on(self.now0.astimezone(timezone.utc).date())


def twin(tmp_path, monkeypatch, mode, question, steps, *, name="twin", before=(), **values):
    """R20-2: the second try's reply without the note. The same message as a turn of its own in
    a fresh agent, on the backup's settings with a stand-in playing `steps`, no backup given.
    `before`: (question, steps) of earlier turns of the thread, run the same way first."""
    w = World(tmp_path / name, monkeypatch, mode, **values)
    for q, s in before:
        w.ask(q, standin(*s, model_id=A_MODEL, clock=w.clock))
    model = standin(*steps, clock=w.clock)
    return w.ask(question, model, settings=w.backup_settings), model


def as_today(tmp_path, monkeypatch, mode, question, make_first, *, name="today", **values):
    """The same message with the same first client and no backup argument (today's turn)."""
    w = World(tmp_path / name, monkeypatch, mode, **values)
    model = make_first(w)
    return w.ask(question, model), model, w


def plain(reply):
    return (reply.status, reply.reason_code, reply.text)


def names_model(run, model):
    """A run record names `model`: county's record by its `model_id` (C5), stage 1's by its
    technical line (`Model: <model id>.`, C51's tests)."""
    return run.get("model_id") == model if "model_id" in run \
        else f"Model: {model}." in run["technical_summary"]


# ==== the note, as the contract writes it ======================================================

def test_premise_the_note_is_c56_point_5s_line_word_for_word():
    assert f"`{NOTE}`" in DESIGN.read_text(encoding="utf-8")


def test_replies_backup_note_is_the_line():
    assert mod("replies").BACKUP_NOTE == NOTE


# ==== point 1: the two settings =================================================================

def settings_of(tmp_path, file_text="", **values):
    return make_settings(tmp_path, file_text, **values)


def test_no_backup_by_default(tmp_path):
    settings = settings_of(tmp_path, **SERVICES)
    assert settings.moco_backup_provider is None and settings.moco_backup_model is None


def test_empty_backup_settings_count_as_unset(tmp_path):
    settings = settings_of(tmp_path, **SERVICES, MOCO_BACKUP_PROVIDER="", MOCO_BACKUP_MODEL="")
    assert settings.moco_backup_provider is None and settings.moco_backup_model is None


@pytest.mark.parametrize("where", ["file", "environment"])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_each_backup_provider_loads(tmp_path, provider, where):
    values = {"MOCO_BACKUP_PROVIDER": provider, "MOCO_BACKUP_MODEL": B_MODEL}
    if where == "file":
        settings = settings_of(tmp_path, "".join(f"{k}={v}\n" for k, v in values.items()),
                               **SERVICES)
    else:
        settings = settings_of(tmp_path, **SERVICES, **values)
    assert (settings.moco_backup_provider, settings.moco_backup_model) == (provider, B_MODEL)


def load_error(tmp_path, **values):
    """R20-4: load_settings raises a ConfigError; it holds no secret and no model given."""
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        settings_of(tmp_path, **values)
    message = str(caught.value)
    assert_no_secret(message)
    assert_no_anthropic_key(message)
    for model in (A_MODEL, N_MODEL, B_MODEL):
        assert model not in message, "a value appears in the message"
    return message


@pytest.mark.parametrize("value", ["openai", "claude", "nemotron", "lightning"])
def test_a_backup_provider_that_is_neither_value_is_a_config_error(tmp_path, value):
    message = load_error(tmp_path, **SERVICES, MOCO_BACKUP_PROVIDER=value,
                         MOCO_BACKUP_MODEL=B_MODEL)
    assert "MOCO_BACKUP_PROVIDER" in message
    assert value not in message


@pytest.mark.parametrize("given", [{"MOCO_BACKUP_PROVIDER": "nvidia"},
                                   {"MOCO_BACKUP_PROVIDER": "anthropic"},
                                   {"MOCO_BACKUP_MODEL": B_MODEL},
                                   {"MOCO_BACKUP_PROVIDER": "nvidia", "MOCO_BACKUP_MODEL": ""},
                                   {"MOCO_BACKUP_PROVIDER": "", "MOCO_BACKUP_MODEL": B_MODEL}],
                         ids=["nvidia-alone", "anthropic-alone", "model-alone",
                              "model-empty", "provider-empty"])
def test_one_backup_setting_without_the_other_is_a_config_error(tmp_path, given):
    message = load_error(tmp_path, **SERVICES, **given)
    assert "MOCO_BACKUP_PROVIDER" in message or "MOCO_BACKUP_MODEL" in message  # R20-5


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_backup_that_is_the_active_services_own_model_is_a_config_error(tmp_path, provider):
    model = {"nvidia": N_MODEL, "anthropic": A_MODEL}[provider]
    message = load_error(tmp_path, **{**SERVICES, "MOCO_MODEL_PROVIDER": provider},
                         MOCO_BACKUP_PROVIDER=provider, MOCO_BACKUP_MODEL=model)
    assert "MOCO_BACKUP_PROVIDER" in message or "MOCO_BACKUP_MODEL" in message


def test_a_backup_that_is_the_active_services_default_model_is_a_config_error(tmp_path):
    """The active service's model at its default (NVIDIA_MODEL unset), read from the program's
    own active service, not copied here."""
    config = mod("config")
    plain_settings = settings_of(tmp_path, NVIDIA_API_KEY=NVIDIA_KEY)
    model = config.model_service(plain_settings).model
    with pytest.raises(config.ConfigError) as caught:
        settings_of(tmp_path, NVIDIA_API_KEY=NVIDIA_KEY, MOCO_BACKUP_PROVIDER="nvidia",
                    MOCO_BACKUP_MODEL=model)
    assert model not in str(caught.value)
    assert_no_secret(str(caught.value))


@pytest.mark.parametrize("active,backup", [("nvidia", ("nvidia", B_MODEL)),
                                           ("anthropic", ("anthropic", B_MODEL)),
                                           ("anthropic", ("nvidia", A_MODEL)),
                                           ("nvidia", ("anthropic", N_MODEL))],
                         ids=["same-provider-other-model-nvidia",
                              "same-provider-other-model-anthropic",
                              "other-provider-same-model-text-1",
                              "other-provider-same-model-text-2"])
def test_a_backup_is_refused_only_when_both_provider_and_model_are_the_active_services(
        tmp_path, active, backup):
    settings = settings_of(tmp_path, **{**SERVICES, "MOCO_MODEL_PROVIDER": active},
                           MOCO_BACKUP_PROVIDER=backup[0], MOCO_BACKUP_MODEL=backup[1])
    assert (settings.moco_backup_provider, settings.moco_backup_model) == backup


# ==== point 2: backup_settings and the two require_ functions ===================================

def test_backup_settings_is_none_with_no_backup(tmp_path):
    config = mod("config")
    assert config.backup_settings(settings_of(tmp_path, **SERVICES)) is None
    assert config.backup_settings(settings_of(tmp_path, **SERVICES, MOCO_BACKUP_PROVIDER="",
                                              MOCO_BACKUP_MODEL="")) is None


@pytest.mark.parametrize("active,backup", [("anthropic", "nvidia"), ("nvidia", "anthropic"),
                                           ("nvidia", "nvidia"), ("anthropic", "anthropic")])
def test_backup_settings_are_the_same_settings_on_the_backups_service(tmp_path, active, backup):
    config = mod("config")
    settings = settings_of(tmp_path, **{**SERVICES, "MOCO_MODEL_PROVIDER": active},
                           NVIDIA_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}',
                           MOCO_BACKUP_PROVIDER=backup, MOCO_BACKUP_MODEL=B_MODEL)
    before = dataclasses.asdict(settings)
    made = config.backup_settings(settings)
    assert type(made) is type(settings)
    after = dataclasses.asdict(made)
    assert after["moco_model_provider"] == backup
    assert after[f"{backup}_model"] == B_MODEL
    assert after[f"{OTHER[backup]}_model"] == before[f"{OTHER[backup]}_model"]
    assert after["moco_backup_provider"] is None and after["moco_backup_model"] is None
    changed = {k for k in before if before[k] != after[k]}
    assert changed <= {"moco_model_provider", f"{backup}_model", "moco_backup_provider",
                       "moco_backup_model"}, sorted(changed)
    assert dataclasses.asdict(settings) == before, "the settings given were changed"
    assert config.backup_settings(made) is None, "the backup has a backup of its own"


@pytest.mark.parametrize("backup", PROVIDERS)
def test_the_backup_service_is_that_providers_as_c51_has_it(tmp_path, backup):
    config = mod("config")
    settings = settings_of(tmp_path, **{**SERVICES, "MOCO_MODEL_PROVIDER": OTHER[backup]},
                           NVIDIA_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}',
                           MOCO_BACKUP_PROVIDER=backup, MOCO_BACKUP_MODEL=B_MODEL)
    service = config.model_service(config.backup_settings(settings))
    assert (service.provider, service.model, service.key_name) == (backup, B_MODEL,
                                                                    OWN_KEY[backup])
    assert service.base_url == {"nvidia": N_URL, "anthropic": A_URL}[backup]
    if service.api_key != KEY_VALUES[OWN_KEY[backup]]:
        raise AssertionError("the backup service does not hold its own provider's key")
    expected = {"nvidia": (0, {"chat_template_kwargs": {"enable_thinking": False}}),
                "anthropic": (None, {})}[backup]
    assert (service.temperature, service.extra_body) == expected
    assert config.model_router(config.backup_settings(settings)) == ROUTERS[backup]


@pytest.mark.parametrize("backup", PROVIDERS)
def test_a_client_built_on_the_backup_settings_asks_the_backups_model_by_its_rules(tmp_path,
                                                                                   backup):
    config = mod("config")
    settings = settings_of(tmp_path, **{**SERVICES, "MOCO_MODEL_PROVIDER": OTHER[backup]},
                           NVIDIA_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}',
                           MOCO_BACKUP_PROVIDER=backup, MOCO_BACKUP_MODEL=B_MODEL)
    transport = FakeTransport(response(("decline", '{"reason_code": "UNSUPPORTED_METRIC"}')))
    client = mod("llm").NvidiaModelClient(config.backup_settings(settings), transport=transport,
                                          sleep=FakeSleep(), clock=p1.FakeClock())
    client.step([{"role": "user", "content": "SYNTHETIC test"}], [])
    (request,) = transport.requests
    assert client.model_id == request["model"] == B_MODEL
    if backup == "nvidia":
        assert request["temperature"] == 0
        assert request["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    else:
        assert "temperature" not in request and request["extra_body"] == {}


def config_error(call, settings):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        call(settings)
    message = str(caught.value)
    assert_no_secret(message)
    assert_no_anthropic_key(message)
    return message


REQUIRES = ["require_for_model", "require_for_serve"]


@pytest.mark.parametrize("function", REQUIRES)
@pytest.mark.parametrize("missing", ["NVIDIA_API_KEY", "ANTHROPIC_API_KEY"])
def test_with_a_backup_each_require_needs_both_services_keys(tmp_path, function, missing):
    """Active anthropic, backup nvidia: the backup's key is needed too."""
    keys = {k: v for k, v in KEY_VALUES.items() if k != missing}
    settings = settings_of(tmp_path, MOCO_MODEL_PROVIDER="anthropic", **BACKUP, **keys,
                           **SLACK_VALUES)
    message = config_error(getattr(mod("config"), function), settings)
    assert missing in message
    assert set(KEY_VALUES).difference({missing}).pop() not in message


@pytest.mark.parametrize("function", REQUIRES)
def test_with_a_backup_and_both_keys_each_require_passes(tmp_path, function):
    settings = settings_of(tmp_path, **SERVICES, **BACKUP, **SLACK_VALUES)
    assert getattr(mod("config"), function)(settings) is None


@pytest.mark.parametrize("function", REQUIRES)
def test_a_backup_on_the_active_provider_needs_no_other_key(tmp_path, function):
    settings = settings_of(tmp_path, MOCO_MODEL_PROVIDER="nvidia", NVIDIA_API_KEY=NVIDIA_KEY,
                           NVIDIA_MODEL=N_MODEL, MOCO_BACKUP_PROVIDER="nvidia",
                           MOCO_BACKUP_MODEL=B_MODEL, **SLACK_VALUES)
    assert getattr(mod("config"), function)(settings) is None


@pytest.mark.parametrize("function", REQUIRES)
@pytest.mark.parametrize("provider", PROVIDERS)
def test_with_no_backup_the_other_services_key_may_still_be_missing(tmp_path, function, provider):
    """Pins today (C51 point 4): with no backup set, nothing more is needed."""
    own = OWN_KEY[provider]
    settings = settings_of(tmp_path, MOCO_MODEL_PROVIDER=provider, **{own: KEY_VALUES[own]},
                           **SLACK_VALUES)
    assert getattr(mod("config"), function)(settings) is None


# ==== point 3: handle_question and build_app take `backup`; leaving it out changes nothing =====

def test_handle_question_takes_backup_with_default_none():
    parameter = inspect.signature(mod("agent").handle_question).parameters.get("backup")
    assert parameter is not None and parameter.default is None


def test_build_app_takes_backup_as_an_optional_fifth_argument():
    parameters = list(inspect.signature(mod("slack_app").build_app).parameters.values())
    assert len(parameters) >= 5 and parameters[4].name == "backup"
    assert parameters[4].default is None


class FakeBolt:
    """Stands in for slack_bolt.App: keeps the handlers; connects nothing."""

    def __init__(self, *args, **kwargs):
        self.client, self.handlers = object(), {}

    def event(self, name):
        def register(function):
            self.handlers[name] = function
            return function
        return register


def wired_agent(monkeypatch, *arguments, **keywords):
    """build_app with Slack replaced; returns (the agent function it hands process_event, the
    keyword arguments of every handle_question call it makes)."""
    import slack_bolt
    monkeypatch.setattr(slack_bolt, "App", FakeBolt)
    slack_app, agent = mod("slack_app"), mod("agent")
    handed, asked = [], []
    monkeypatch.setattr(slack_app, "process_event", lambda event, **kw: handed.append(kw["agent"]))
    monkeypatch.setattr(agent, "handle_question", lambda question, **kw: asked.append(kw))
    app = slack_app.build_app(*arguments, **keywords)
    app.handlers["message"]({"team_id": TEAM, "event_id": "EvTEST000020"}, {"type": "message"})
    assert len(handed) == 1
    return handed[0], asked


@pytest.mark.parametrize("how", ["fifth", "keyword"])
def test_build_app_passes_the_pair_to_handle_question_on_every_turn(tmp_path, monkeypatch, how):
    w = World(tmp_path, monkeypatch, "stage1")
    pair = (w.backup_settings, standin())
    base = (w.env.settings, w.env.registry, w.store, down())
    agent, asked = (wired_agent(monkeypatch, *base, pair) if how == "fifth"
                    else wired_agent(monkeypatch, *base, backup=pair))
    agent("SYNTHETIC question one", THREAD_1, USER)
    agent("SYNTHETIC question two", THREAD_1, USER)
    assert len(asked) == 2 and all(kw.get("backup") is pair for kw in asked)


def test_build_app_without_backup_hands_handle_question_none(tmp_path, monkeypatch):
    """Pins today: build_app with four arguments; handle_question gets no backup."""
    w = World(tmp_path, monkeypatch, "stage1")
    agent, asked = wired_agent(monkeypatch, w.env.settings, w.env.registry, w.store, down())
    agent("SYNTHETIC question", THREAD_1, USER)
    assert len(asked) == 1 and asked[0].get("backup") is None


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("first_works", [True, False], ids=["first-works", "first-down"])
def test_backup_none_is_the_same_turn_as_no_backup_argument(tmp_path, monkeypatch, mode,
                                                            first_works):
    kind = "answered"
    question, steps = SCRIPTS[mode, kind]

    def first_of(w):
        return standin(*steps, model_id=A_MODEL, clock=w.clock) if first_works else down()
    today, today_model, tw = as_today(tmp_path, monkeypatch, mode, question, first_of)
    w = World(tmp_path / "none", monkeypatch, mode)
    model = first_of(w)
    reply = w.ask(question, model, None)
    assert plain(reply) == plain(today)
    assert (reply.model_id, reply.reply_style, reply.steps) == (today.model_id,
                                                                today.reply_style, today.steps)
    assert model.calls == today_model.calls
    own, others = w.records_of(reply)
    today_own, _ = tw.records_of(today)
    assert others == [] and "backup_of" not in own
    assert sorted(own) == sorted(today_own)
    assert len(w.memory()) == len(tw.memory()) == 1


# ==== point 1 and "Tests": nvidia active, no backup set: every request and record as before C56 ===

STAGE1_RESPONSES = [response(("count_arrests", '{"year": 2025, "age_group": "18_25"}')),
                    response(("finish", json.dumps({"kind": "finding", "text": ONE_COUNT_TEXT})))]
COUNTY_RESPONSES = [response(("count", json.dumps({"source": A_ID, "period": {"year": 2025}}))),
                    response(("finish", json.dumps({"kind": "finding", "text": COUNTY_FINISH})))]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("mode", MODES)
def test_pin_nvidia_with_no_backup_set_every_request_and_record_as_today(tmp_path, monkeypatch,
                                                                        caplog, mode, talk):
    """Pins today: passes before C56 and must after. The real client over a fake transport."""
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    w = World(tmp_path, monkeypatch, mode, backup_set=False, MOCO_MODEL_PROVIDER="nvidia",
              MOCO_TALK=talk)
    transport = FakeTransport(*(STAGE1_RESPONSES if mode == "stage1" else COUNTY_RESPONSES))
    client = mod("llm").NvidiaModelClient(w.env.settings, transport=transport, sleep=FakeSleep(),
                                          clock=w.clock)
    question = S1 if mode == "stage1" else Q_COUNT
    reply = w.ask(question, client)
    assert reply.status == "ANSWERED", plain(reply)
    assert len(transport.requests) == 2
    for request in transport.requests:
        assert set(request) == NVIDIA_REQUEST_KEYS
        assert (request["model"], request["temperature"]) == (N_MODEL, 0)
    assert reply.model_id == N_MODEL and NOTE not in reply.text
    own, others = w.records_of(reply)
    assert others == [] and own["model_id"] == N_MODEL and own["reply"] == reply.text
    assert not [k for k in own if "backup" in k.lower()]
    assert not [k for k in reply.to_dict() if "backup" in k.lower()]
    runs = manifests(w.runs_dir)
    assert runs and all(m["router"] == ROUTERS["nvidia"] and names_model(m, N_MODEL) for m in runs)
    assert len(w.memory()) == 1
    assert not [r for r in caplog.records if "backup" in r.getMessage().lower()]


@pytest.mark.parametrize("mode", MODES)
def test_pin_with_no_backup_a_failed_model_ends_as_today(tmp_path, monkeypatch, mode):
    """Pins today: the first client down, no backup set or given: today's text, one record (no
    backup_of), one turn in memory."""
    w = World(tmp_path, monkeypatch, mode, backup_set=False)
    first = down(clock=w.clock)
    reply = w.ask(SCRIPTS[mode, "answered"][0], first)
    assert (reply.status, reply.reason_code) == ("ERROR", "MODEL_UNAVAILABLE")
    assert_fixed(reply.text, "MODEL_UNAVAILABLE")
    assert reply.model_id == A_MODEL and len(first.calls) == 1
    own, others = w.records_of(reply)
    assert others == [] and "backup_of" not in own
    assert [t["turn_id"] for t in w.memory()] == [reply.turn_id]


# ==== points 4 and 5: the second try and the note ==============================================

@pytest.mark.parametrize("mode,talk,kind", CASES)
def test_the_second_try_is_sent_with_the_note_as_its_last_line(tmp_path, monkeypatch, mode, talk,
                                                               kind):
    """C56 Tests: the backup's answer plus the note on an ANSWERED reply, a question back, a talk
    reply and a fixed-text reply of the second try; model_id the backup's."""
    question, steps = SCRIPTS[mode, kind]
    expected, twin_model = twin(tmp_path, monkeypatch, mode, question, steps, MOCO_TALK=talk)
    assert expected.status == STATUS[kind], plain(expected)  # premise: the script ends so
    assert twin_model.calls and NOTE not in expected.text
    w = World(tmp_path, monkeypatch, mode, MOCO_TALK=talk)
    first, backup = down(clock=w.clock), standin(*steps, clock=w.clock)
    reply = w.ask(question, first, backup)
    assert reply.text == expected.text + "\n" + NOTE  # R20-1, R20-2
    assert reply.text.count(NOTE) == 1
    assert (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style) == (
        expected.status, expected.reason_code, expected.reply_kind, expected.reply_style)
    assert reply.model_id == B_MODEL and reply.model_called is True
    assert len(first.calls) == 1 and len(backup.calls) == len(twin_model.calls)
    own, _ = w.records_of(reply)
    assert own["reply"] == reply.text


@pytest.mark.parametrize("mode", MODES)
def test_without_a_backup_the_same_first_client_gives_todays_text_and_no_note(tmp_path,
                                                                              monkeypatch, mode):
    """C56 Tests: the same first client without a backup (none given; the backup set in the
    settings changes nothing without the argument): today's text, no note."""
    w = World(tmp_path, monkeypatch, mode)
    first = down(clock=w.clock)
    reply = w.ask(SCRIPTS[mode, "answered"][0], first)
    assert (reply.status, reply.reason_code) == ("ERROR", "MODEL_UNAVAILABLE")
    assert_fixed(reply.text, "MODEL_UNAVAILABLE")
    assert NOTE not in reply.text and reply.model_id == A_MODEL
    own, others = w.records_of(reply)
    assert others == [] and "backup_of" not in own


@pytest.mark.parametrize("mode", MODES)
def test_a_first_client_that_works_makes_no_second_try(tmp_path, monkeypatch, mode, caplog):
    """C56 Tests: no second try, no note, the backup client never called."""
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    question, steps = SCRIPTS[mode, "answered"]
    today, _, _ = as_today(tmp_path, monkeypatch, mode, question,
                           lambda tw: standin(*steps, model_id=A_MODEL, clock=tw.clock))
    w = World(tmp_path, monkeypatch, mode)
    backup = standin(*steps, clock=w.clock)
    reply = w.ask(question, standin(*steps, model_id=A_MODEL, clock=w.clock), backup)
    assert backup.calls == []
    assert plain(reply) == plain(today) and reply.status == "ANSWERED"
    assert NOTE not in reply.text and reply.model_id == A_MODEL
    own, others = w.records_of(reply)
    assert others == [] and "backup_of" not in own
    assert not [r for r in caplog.records if B_MODEL in r.getMessage()]


@pytest.mark.parametrize("mode", MODES)
def test_both_fail_todays_text_no_note_two_records(tmp_path, monkeypatch, mode):
    """C56 Tests: both fail: today's text, no note, two records; the reply's model_id is the
    backup's (the try that was sent); the thread holds one turn."""
    question = SCRIPTS[mode, "answered"][0]
    today, _, _ = as_today(tmp_path, monkeypatch, mode, question, lambda tw: down())
    w = World(tmp_path, monkeypatch, mode)
    first, backup = down(clock=w.clock), down(model_id=B_MODEL, clock=w.clock)
    reply = w.ask(question, first, backup)
    assert plain(reply) == plain(today) == ("ERROR", "MODEL_UNAVAILABLE", today.text)
    assert_fixed(reply.text, "MODEL_UNAVAILABLE")
    assert NOTE not in reply.text
    assert len(first.calls) == 1 and len(backup.calls) == 1
    assert reply.model_id == B_MODEL
    own, others = w.records_of(reply)
    assert len(others) == 1
    assert own["backup_of"] == others[0]["turn_id"]
    assert (own["model_id"], own["status"], own["reason_code"]) == (B_MODEL, "ERROR",
                                                                     "MODEL_UNAVAILABLE")
    assert [t["turn_id"] for t in w.memory()] == [reply.turn_id]


# Point 4: no other end starts a second try.
NO_SECOND = {
    # id: (the first client, from (world, steps); MOCO_ settings)
    "MODEL_BAD_OUTPUT at the step limit": (lambda w, s: standin(Step(), model_id=A_MODEL,
                                                                clock=w.clock), {}),
    "LOOP_LIMIT with a result": (lambda w, s: standin(s[0], Step(), model_id=A_MODEL,
                                                      clock=w.clock), {}),
    "the time limit": (lambda w, s: standin(Step(), model_id=A_MODEL, clock=w.clock,
                                            seconds=50.0), {}),
    # OWN: the brief's first example
    "the first client fails at its second step after a count was made": (
        lambda w, s: standin(s[0], model_id=A_MODEL, clock=w.clock, error=unavailable(),
                             fail_at=1), {}),
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("end", list(NO_SECOND))
@pytest.mark.parametrize("mode", MODES)
def test_no_other_end_starts_a_second_try(tmp_path, monkeypatch, mode, end, talk, caplog):
    """C56 Tests: the first try's end MODEL_BAD_OUTPUT or LOOP_LIMIT: no second try; also the time
    limit and (OWN) a model that fails after a count was made (the fixed rendering is a reply the
    first try can still send). The reply is today's; the backup never called; no note."""
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    make, values = NO_SECOND[end]
    question, steps = SCRIPTS[mode, "answered"]
    today, _, _ = as_today(tmp_path, monkeypatch, mode, question, lambda tw: make(tw, steps),
                           MOCO_TALK=talk, **values)
    assert (today.status, today.reason_code) != ("ERROR", "MODEL_UNAVAILABLE"), plain(today)
    w = World(tmp_path, monkeypatch, mode, MOCO_TALK=talk, **values)
    backup = standin(*steps, clock=w.clock)
    reply = w.ask(question, make(w, steps), backup)
    assert backup.calls == []
    assert plain(reply) == plain(today) and NOTE not in reply.text
    assert reply.model_id == A_MODEL
    own, others = w.records_of(reply)
    assert others == [] and "backup_of" not in own
    assert not [r for r in caplog.records if B_MODEL in r.getMessage()]


class Broken:
    """A model client whose step fails with an error that is not ModelUnavailable."""
    model_id = A_MODEL

    def __init__(self):
        self.calls = []

    def step(self, messages, tools):
        self.calls.append(messages)
        raise RuntimeError("SYNTHETIC: a client broken in another way")


@pytest.mark.parametrize("mode", MODES)
def test_own_a_first_client_broken_another_way_ends_model_bad_output_with_no_second_try(
        tmp_path, monkeypatch, mode):
    """OWN (point 4, "not MODEL_BAD_OUTPUT"): handle_question's last guard ends the turn
    MODEL_BAD_OUTPUT as today; the backup is never called."""
    question, steps = SCRIPTS[mode, "answered"]
    today, _, _ = as_today(tmp_path, monkeypatch, mode, question, lambda tw: Broken())
    w = World(tmp_path, monkeypatch, mode)
    backup = standin(*steps, clock=w.clock)
    reply = w.ask(question, Broken(), backup)
    assert (reply.status, reply.reason_code) == ("ERROR", "MODEL_BAD_OUTPUT")
    assert plain(reply) == plain(today) and backup.calls == [] and NOTE not in reply.text


@pytest.mark.parametrize("mode", MODES)
def test_own_a_first_try_ended_rate_limited_starts_no_second_try(tmp_path, monkeypatch, mode,
                                                                caplog):
    """OWN (point 4, "not RATE_LIMITED"): the day's limit is reached by an earlier message; the
    next message ends RATE_LIMITED, neither client is called, and no second try starts (a second
    try would end RATE_LIMITED too, so its warning line is what would show it)."""
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode, MOCO_DAILY_MODEL_CALLS=1)
    w.ask(question, standin(*steps, model_id=A_MODEL, clock=w.clock), standin(clock=w.clock))
    first, backup = down(clock=w.clock), standin(*steps, clock=w.clock)
    reply = w.ask(question, first, backup)
    assert (reply.status, reply.reason_code) == ("ERROR", "RATE_LIMITED")
    assert_fixed(reply.text, "RATE_LIMITED")
    assert first.calls == [] and backup.calls == [] and NOTE not in reply.text
    assert not [r for r in caplog.records if B_MODEL in r.getMessage()]


# ==== point 6: records and memory ===============================================================

@pytest.mark.parametrize("mode", MODES)
def test_the_two_records_of_a_backup_turn(tmp_path, monkeypatch, mode):
    """C56 Tests: the second record's backup_of. OWN: the first try's turn id is not the second's;
    the first record has no backup_of; it is saved as today (status, reason, model id, text)."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    reply = w.ask(question, down(clock=w.clock), standin(*steps, clock=w.clock))
    own, others = w.records_of(reply)
    (first,) = others
    assert first["turn_id"] != own["turn_id"]
    assert TURN_ID.fullmatch(first["turn_id"]) and TURN_ID.fullmatch(own["turn_id"])
    assert (first["status"], first["reason_code"], first["model_id"]) == (
        "ERROR", "MODEL_UNAVAILABLE", A_MODEL)
    assert_fixed(first["reply"], "MODEL_UNAVAILABLE")
    assert "backup_of" not in first
    assert own["backup_of"] == first["turn_id"]
    assert own["model_id"] == B_MODEL and own["status"] == reply.status == "ANSWERED"
    if "router" in own:  # R20-6
        assert own["router"] == ROUTERS["nvidia"]


@pytest.mark.parametrize("mode", MODES)
def test_the_second_trys_run_records_name_the_backups_model_and_router(tmp_path, monkeypatch,
                                                                       mode):
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    reply = w.ask(question, down(clock=w.clock), standin(*steps, clock=w.clock))
    runs = manifests(w.runs_dir)
    assert len(runs) == 1 and runs[0]["run_id"] in reply.run_ids
    assert runs[0]["router"] == ROUTERS["nvidia"] and names_model(runs[0], B_MODEL)
    if mode == "stage1":
        assert f"Router: {ROUTERS['nvidia']}." in runs[0]["technical_summary"]
    saved = "\n".join(p.read_text(encoding="utf-8") for p in w.runs_dir.rglob("manifest.json"))
    assert ROUTERS["anthropic"] not in saved and A_MODEL not in saved


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("mode", MODES)
def test_the_threads_memory_after_a_backup_turn_holds_one_turn(tmp_path, monkeypatch, mode, talk):
    """C56 Tests: one turn for the message, the one that was sent."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode, MOCO_TALK=talk)
    reply = w.ask(question, down(clock=w.clock), standin(*steps, clock=w.clock))
    (stored,) = w.memory()
    assert (stored["turn_id"], stored["status"], stored["model_id"]) == (reply.turn_id,
                                                                         reply.status, B_MODEL)
    assert stored["user_id"] == USER


@pytest.mark.parametrize("mode", MODES)
def test_own_the_second_try_starts_from_the_start_with_nothing_the_first_made(tmp_path,
                                                                              monkeypatch, mode):
    """OWN (point 4): the first try described the data, then its model failed; the backup's first
    request is the first try's first request (same message, thread, day; no tool answer of the
    first try); the thread so far has the earlier turn and not the failed try; afterwards the
    thread holds the earlier turn and the one sent."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    earlier = w.ask(question, standin(*steps, model_id=A_MODEL, clock=w.clock))
    assert earlier.status == "ANSWERED"
    first = standin(Step(describe()), model_id=A_MODEL, clock=w.clock, error=unavailable(),
                    fail_at=1)
    backup = standin(*steps, clock=w.clock)
    reply = w.ask(question, first, backup)
    assert len(first.calls) == 2 and backup.calls
    assert backup.calls[0]["messages"] == first.calls[0]["messages"]
    assert backup.calls[0]["tools"] == first.calls[0]["tools"]
    assert [t["turn_id"] for t in w.memory()] == [earlier.turn_id, reply.turn_id]
    assert reply.text.endswith("\n" + NOTE)


@pytest.mark.parametrize("mode", MODES)
def test_own_the_second_try_has_its_own_full_step_and_time_limits(tmp_path, monkeypatch, mode):
    """OWN (point 4): two steps at most and 90 seconds a turn; the first try spends 80 seconds and
    a step and fails; the backup needs both steps and 40 seconds and still finishes by its own
    words (no limit's fixed rendering)."""
    question, steps = SCRIPTS[mode, "answered"]
    values = {"MOCO_MAX_STEPS": 2, "MOCO_TURN_SECONDS": 90}
    expected, _ = twin(tmp_path, monkeypatch, mode, question, steps, **values)
    assert (expected.status, expected.reply_style) == ("ANSWERED", "agent"), plain(expected)
    w = World(tmp_path, monkeypatch, mode, **values)
    first = down(clock=w.clock, seconds=80.0)
    backup = standin(*steps, clock=w.clock, seconds=20.0)
    reply = w.ask(question, first, backup)
    assert len(backup.calls) == 2
    assert (reply.status, reply.reply_style, reply.draft_failures) == ("ANSWERED", "agent", [])
    assert reply.text == expected.text + "\n" + NOTE


# ==== point 5: the note is the program's line, outside every check and limit ====================

@pytest.mark.parametrize("mode", MODES)
def test_own_the_note_takes_no_part_in_the_talk_check_or_its_limits(tmp_path, monkeypatch, mode):
    """OWN: a talk text of six sentences and 657 characters passes alone; with the note it would
    be seven sentences and over 700 characters, and the note has a judgement word."""
    steps = [Step(finish("talk", SIX))]
    expected, _ = twin(tmp_path, monkeypatch, mode, HELLO, steps, MOCO_TALK="on")
    assert (expected.status, expected.reply_style, expected.text) == ("TALKED", "agent", SIX)
    w = World(tmp_path, monkeypatch, mode, MOCO_TALK="on")
    reply = w.ask(HELLO, down(clock=w.clock), standin(*steps, clock=w.clock))
    assert (reply.status, reply.reply_style, reply.draft_failures) == ("TALKED", "agent", [])
    assert reply.text == SIX + "\n" + NOTE


@pytest.mark.parametrize("mode", MODES)
def test_own_the_note_appears_once_after_a_rewrite_in_the_second_try(tmp_path, monkeypatch, mode):
    """OWN: the backup's first talk text fails (REWRITE), its second passes: one note, once."""
    steps = [Step(finish("talk", TALK_FAILING)), Step(finish("talk", HELLO_TEXT))]
    expected, twin_model = twin(tmp_path, monkeypatch, mode, HELLO, steps, MOCO_TALK="on")
    assert len(twin_model.calls) == 2 and expected.text == HELLO_TEXT, plain(expected)
    w = World(tmp_path, monkeypatch, mode, MOCO_TALK="on")
    reply = w.ask(HELLO, down(clock=w.clock), standin(*steps, clock=w.clock))
    assert reply.text == HELLO_TEXT + "\n" + NOTE and reply.text.count(NOTE) == 1


@pytest.mark.parametrize("mode", MODES)
def test_the_backups_model_fails_after_a_count_is_open_both_readings(tmp_path, monkeypatch, mode):
    """R20-8 (QUESTIONS.md, S3-R20-A q. 2): the second try's model fails after a count; the reply
    is the fixed rendering the backup's turn sends alone, with the note or without it."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    backup = standin(steps[0], clock=w.clock, error=unavailable(), fail_at=1)
    tw = World(tmp_path / "twin2", monkeypatch, mode)
    alone = tw.ask(question, standin(steps[0], clock=tw.clock, error=unavailable(), fail_at=1),
                   settings=tw.backup_settings)
    assert alone.status == "ANSWERED", plain(alone)
    reply = w.ask(question, down(clock=w.clock), backup)
    assert reply.text in (alone.text, alone.text + "\n" + NOTE)
    assert reply.status == "ANSWERED" and reply.model_id == B_MODEL


# ==== point 7: the log line, and the daily limit ===============================================

@pytest.mark.parametrize("mode", MODES)
def test_one_warning_line_names_both_models_and_both_turns_and_nothing_secret(tmp_path,
                                                                             monkeypatch, caplog,
                                                                             mode):
    """Point 7; OWN: no secret is in any log line of a backup turn."""
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    reply = w.ask(question, down(clock=w.clock), standin(*steps, clock=w.clock))
    _, (first,) = w.records_of(reply)
    lines = [r for r in caplog.records if B_MODEL in r.getMessage()]
    assert len(lines) == 1, [r.getMessage() for r in lines]
    assert lines[0].levelno == logging.WARNING
    message = lines[0].getMessage()
    for name in (A_MODEL, B_MODEL, first["turn_id"], reply.turn_id):
        assert name in message, name
    shown = "\n".join(r.getMessage() for r in caplog.records) + "\n" + caplog.text
    assert_no_secret(shown)
    assert_no_anthropic_key(shown)


@pytest.mark.parametrize("mode", MODES)
def test_own_the_daily_limit_counts_both_tries(tmp_path, monkeypatch, mode):
    """OWN (point 7): with no limit set, one backup turn counts two calls; with a limit of 2, the
    next message is RATE_LIMITED and neither client is called."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    w.ask(question, down(clock=w.clock), standin(*steps, clock=w.clock))
    assert w.calls_today() == 2
    w2 = World(tmp_path / "limit", monkeypatch, mode, MOCO_DAILY_MODEL_CALLS=2)
    w2.ask(question, down(clock=w2.clock), standin(*steps, clock=w2.clock))
    first, backup = standin(*steps, model_id=A_MODEL, clock=w2.clock), standin(clock=w2.clock)
    reply = w2.ask(question, first, backup)
    assert (reply.status, reply.reason_code) == ("ERROR", "RATE_LIMITED")
    assert first.calls == [] and backup.calls == []


@pytest.mark.parametrize("mode", MODES)
def test_own_a_second_try_over_the_daily_limit_is_sent_rate_limited_with_no_note(tmp_path,
                                                                                 monkeypatch,
                                                                                 mode):
    """OWN (R20-7): a limit of 1: the first try spends it; the second try ends RATE_LIMITED, its
    reply is sent, the backup is never called, no note; the thread holds that one turn."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode, MOCO_DAILY_MODEL_CALLS=1)
    first, backup = down(clock=w.clock), standin(*steps, clock=w.clock)
    reply = w.ask(question, first, backup)
    assert (reply.status, reply.reason_code) == ("ERROR", "RATE_LIMITED")
    assert_fixed(reply.text, "RATE_LIMITED")
    assert len(first.calls) == 1 and backup.calls == [] and NOTE not in reply.text
    (stored,) = w.memory()
    assert (stored["status"], stored["reason_code"]) == ("ERROR", "RATE_LIMITED")


# ==== point 8: each message tries the active service first =====================================

@pytest.mark.parametrize("mode", MODES)
def test_own_each_message_tries_the_active_service_first(tmp_path, monkeypatch, mode):
    """OWN: message 1 goes to the backup; message 2, with the same two clients, is answered by
    the first (nothing remembers the failure), with no note."""
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    first = Flaky(*steps, down=(0,))
    backup = standin(*steps, clock=w.clock)
    one = w.ask(question, first, backup)
    assert one.text.endswith("\n" + NOTE) and one.model_id == B_MODEL
    used = len(backup.calls)
    two = w.ask(question, first, backup, thread_key=p1.THREAD_2)
    assert len(backup.calls) == used, "the backup was called for the second message"
    assert two.model_id == A_MODEL and NOTE not in two.text and two.status == "ANSWERED"


@pytest.mark.parametrize("mode", MODES)
def test_own_while_the_first_clients_pause_lasts_turns_go_to_the_backup_at_once(tmp_path,
                                                                                monkeypatch,
                                                                                mode):
    """OWN (point 8): the real client over a transport that always fails (2 tries a call): three
    messages open its pause; the fourth reaches no transport and goes to the backup; after 61
    seconds the fifth tries the first service again."""
    w = World(tmp_path, monkeypatch, mode)
    transport = FakeTransport("server")
    first = mod("llm").NvidiaModelClient(w.env.settings, transport=transport, sleep=FakeSleep(),
                                         clock=w.clock)
    assert first.model_id == A_MODEL
    backup = standin(Step(decline("UNSUPPORTED_METRIC")), clock=w.clock)
    question = SCRIPTS[mode, "fixed"][0]
    for n in range(3):
        reply = w.ask(question, first, backup, thread_key=f"{THREAD_1}-{n}")
        assert reply.text.endswith("\n" + NOTE)
    assert len(transport.requests) == 6 and len(backup.calls) == 3
    reply = w.ask(question, first, backup, thread_key=f"{THREAD_1}-3")
    assert len(transport.requests) == 6 and len(backup.calls) == 4
    assert reply.text.endswith("\n" + NOTE) and reply.model_id == B_MODEL
    w.clock.now += 61
    w.ask(question, first, backup, thread_key=f"{THREAD_1}-4")
    assert len(transport.requests) > 6


# ==== point 2 and 3 together: the pair as serve builds it =======================================

@pytest.mark.parametrize("mode", MODES)
def test_a_pair_built_with_backup_settings_runs_the_second_try_on_the_backup(tmp_path,
                                                                             monkeypatch, mode):
    question, steps = SCRIPTS[mode, "answered"]
    w = World(tmp_path, monkeypatch, mode)
    pair = (mod("config").backup_settings(w.env.settings), standin(*steps, clock=w.clock))
    reply = w.ask(question, down(clock=w.clock), pair)
    assert reply.text.endswith("\n" + NOTE) and reply.model_id == B_MODEL
    (run,) = manifests(w.runs_dir)
    assert run["router"] == ROUTERS["nvidia"]


def test_premise_the_questions_pass_the_guard():
    for question in {q for q, _ in SCRIPTS.values()}:
        guard_free(question)
