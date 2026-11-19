"""Point 1: settings and secrets (design P1, section 4; P1A, A14; brief P1A-A point 10).

Every test passes an environ dict, and an env file in tmp_path. Secret values are made up.
Not tested, because section 4 does not say: whitespace around a KEY or a VALUE, an empty
value (KEY=), a line with no "=", and what load_settings reads when `environ` is left out.
Not tested on purpose: the default file ~/.config/moco-cj-agent/.env. The tests point HOME
into a temporary folder, but a build that found the home folder some other way would then
read the real secrets file, which no test may touch.
Accepted both ways: an unset secret or workspace id may read as None or as "" (section 4
says "none" and "simply unset"); the allowed user ids may read as () or None; MOCO_BACKGROUND
may be held as "off"/"on" or as False/True (kit-log/raw/P1A-A-notes.txt); MOCO_REPLY_STYLE
may be held as a str subclass (a str Enum), since A14 does not fix a choice's type.

P1A (A14) changes five defaults and adds six settings: four whole numbers (MOCO_MAX_STEPS,
MOCO_TURN_SECONDS, MOCO_DM_MEMORY_MINUTES, MOCO_ACK_AFTER_SECONDS, where 0 is allowed for
the last) and two choices (MOCO_REPLY_STYLE: agent or fixed; MOCO_BACKGROUND: off or on). A
value outside a choice's list raises ConfigError naming the KEY. Not tested, because A14
does not say: the letter case of a choice ("ON", "Fixed").
"""
import re

import pytest

from p1support import FAKE_SECRETS, TEAM, USER, USER2, assert_no_secret, make_settings, mod

UNSET_TEXT = ["nvidia_api_key", "slack_bot_token", "slack_app_token", "slack_allowed_team_id"]
DEFAULTS = {  # P1 section 4's table with A14's new defaults, as Settings attributes
    "nvidia_model": "nvidia/nemotron-3-ultra-550b-a55b",  # (the four above: see test_unset)
    "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
    "nvidia_extra_body": {},
    "slack_allowed_channel_ids": (),
    "moco_max_question_chars": 500,
    "moco_user_requests_per_minute": 6,
    "moco_daily_model_calls": 0,
    "moco_model_timeout_seconds": 45,
    "moco_model_max_retries": 1,
    "moco_model_max_tokens": 2048,
    "moco_thread_turns_in_context": 10,  # C61 point 5 (brief S3-R23-A); it was 6
    "moco_retention_days": 30,
    "moco_max_steps": 6,
    "moco_turn_seconds": 90,
    "moco_dm_memory_minutes": 60,
    "moco_ack_after_seconds": 3,
    "moco_reply_style": "agent",
}
NUMBER_KEYS = ["MOCO_MAX_QUESTION_CHARS", "MOCO_USER_REQUESTS_PER_MINUTE",
               "MOCO_DAILY_MODEL_CALLS", "MOCO_MODEL_TIMEOUT_SECONDS",
               "MOCO_MODEL_MAX_RETRIES", "MOCO_MODEL_MAX_TOKENS",
               "MOCO_THREAD_TURNS_IN_CONTEXT", "MOCO_RETENTION_DAYS",
               "MOCO_MAX_STEPS", "MOCO_TURN_SECONDS", "MOCO_DM_MEMORY_MINUTES",
               "MOCO_ACK_AFTER_SECONDS"]
CHOICES = {"MOCO_REPLY_STYLE": ("agent", "fixed"), "MOCO_BACKGROUND": ("off", "on")}  # A14
NOT_LISTED = {"MOCO_REPLY_STYLE": ["fallback", "agents", "free", "on"],
              "MOCO_BACKGROUND": ["yes", "true", "enabled", "agent"]}
SERVE_KEYS = ["NVIDIA_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ALLOWED_TEAM_ID",
              "SLACK_ALLOWED_USER_IDS"]
SERVE_VALUES = dict(FAKE_SECRETS, SLACK_ALLOWED_TEAM_ID=TEAM,
                    SLACK_ALLOWED_USER_IDS=f"{USER},{USER2}")
# Every value given in SERVE_VALUES, for "the message never contains a value".
ALL_VALUES = list(FAKE_SECRETS.values()) + [TEAM, USER, USER2]


def test_file_is_read_as_key_value_lines(tmp_path):
    settings = make_settings(tmp_path, "NVIDIA_MODEL=file-org/file-model\n"
                                       "MOCO_MAX_QUESTION_CHARS=250\n"
                                       "NVIDIA_API_KEY=" + FAKE_SECRETS["NVIDIA_API_KEY"] + "\n")
    assert settings.nvidia_model == "file-org/file-model"
    assert settings.moco_max_question_chars == 250
    assert settings.nvidia_api_key == FAKE_SECRETS["NVIDIA_API_KEY"]


def test_comments_and_blank_lines_are_skipped(tmp_path):
    settings = make_settings(tmp_path, "# NVIDIA_MODEL=commented-org/commented-model\n"
                                       "\n"
                                       "NVIDIA_MODEL=kept-org/kept-model\n"
                                       "\n"
                                       "# a last comment\n")
    assert settings.nvidia_model == "kept-org/kept-model"


@pytest.mark.parametrize("written, read", [
    ('"quoted-org/model"', "quoted-org/model"),
    ("'single-org/model'", "single-org/model"),
    ('""twice-org/model""', '"twice-org/model"'),     # one pair only
    ('"mismatched-org/model\'', '"mismatched-org/model\''),  # not a matching pair
    ('in"side-org/model', 'in"side-org/model'),        # not around the value
], ids=["double", "single", "two_pairs", "mismatched", "inside"])
def test_one_pair_of_matching_quotes_is_removed(written, read, tmp_path):
    settings = make_settings(tmp_path, f"NVIDIA_MODEL={written}\n")
    assert settings.nvidia_model == read


def test_nothing_else_is_interpreted(tmp_path):
    """An "=" or "#" inside a value, and a "$NAME", are kept as written."""
    settings = make_settings(tmp_path, "NVIDIA_BASE_URL=https://example.invalid/v1?a=b#c\n"
                                       "NVIDIA_MODEL=$HOME/model\n")
    assert settings.nvidia_base_url == "https://example.invalid/v1?a=b#c"
    assert settings.nvidia_model == "$HOME/model"


def test_environment_wins_over_the_file(tmp_path):
    settings = make_settings(tmp_path, "NVIDIA_MODEL=file-org/file-model\n"
                                       "MOCO_MAX_QUESTION_CHARS=250\n",
                             NVIDIA_MODEL="env-org/env-model", MOCO_MAX_QUESTION_CHARS="300")
    assert settings.nvidia_model == "env-org/env-model"
    assert settings.moco_max_question_chars == 300


def test_a_missing_file_is_not_an_error(tmp_path):
    absent = tmp_path / "no-such-file.env"
    settings = mod("config").load_settings(env_file=absent,
                                           environ={"MOCO_ENV_FILE": str(absent)})
    assert settings.nvidia_api_key in (None, "")
    for attribute, value in DEFAULTS.items():
        assert getattr(settings, attribute) == value, attribute
    assert is_background(settings.moco_background, "off")


def test_the_file_named_by_moco_env_file_is_read(tmp_path, monkeypatch):
    """Section 4: the secrets file is the path in MOCO_ENV_FILE. With env_file left out,
    load_settings reads that file. MOCO_ENV_FILE is set both in `environ` and in the process
    environment, so this holds whichever of the two the build reads it from."""
    chosen = tmp_path / "chosen.env"
    chosen.write_text("NVIDIA_MODEL=chosen-org/chosen-model\n", encoding="utf-8")
    monkeypatch.setenv("MOCO_ENV_FILE", str(chosen))
    settings = mod("config").load_settings(environ={"MOCO_ENV_FILE": str(chosen)})
    assert settings.nvidia_model == "chosen-org/chosen-model"


@pytest.mark.parametrize("attribute", UNSET_TEXT)
def test_unset(attribute, tmp_path):
    assert getattr(make_settings(tmp_path), attribute) in (None, "")


@pytest.mark.parametrize("attribute", DEFAULTS)
def test_default(attribute, tmp_path):
    value = getattr(make_settings(tmp_path), attribute)
    assert value == DEFAULTS[attribute]
    if isinstance(DEFAULTS[attribute], str):  # a str subclass is fine: a choice may be a str Enum
        assert isinstance(value, str), type(value)
    else:  # P1 section 4 fixes ints, a tuple and a dict
        assert type(value) is type(DEFAULTS[attribute]), type(value)


def is_background(value, word):
    """MOCO_BACKGROUND held as its word or as a bool (both accepted, see the docstring)."""
    return value == word or value is (word == "on")


def test_default_background_is_off(tmp_path):
    """A14: MOCO_BACKGROUND is off by default."""
    assert is_background(make_settings(tmp_path).moco_background, "off")


def test_default_allowed_user_ids(tmp_path):
    """Default "none", and the attribute is "a tuple of strings": an empty tuple and None
    both honestly mean none, so both are accepted."""
    assert make_settings(tmp_path).slack_allowed_user_ids in ((), None)


@pytest.mark.parametrize("key, attribute", [
    ("SLACK_ALLOWED_USER_IDS", "slack_allowed_user_ids"),
    ("SLACK_ALLOWED_CHANNEL_IDS", "slack_allowed_channel_ids"),
])
def test_lists_become_tuples_of_strings(key, attribute, tmp_path):
    settings = make_settings(tmp_path, **{key: "XTEST0001,XTEST0002,XTEST0003"})
    assert getattr(settings, attribute) == ("XTEST0001", "XTEST0002", "XTEST0003")
    assert type(getattr(settings, attribute)) is tuple
    one = make_settings(tmp_path, **{key: "XTEST0001"})
    assert getattr(one, attribute) == ("XTEST0001",)


@pytest.mark.parametrize("key", NUMBER_KEYS)
def test_numbers_become_ints(key, tmp_path):
    from_environ = getattr(make_settings(tmp_path, **{key: "7"}), key.lower())
    from_file = getattr(make_settings(tmp_path, f"{key}=8\n"), key.lower())
    assert (from_environ, from_file) == (7, 8)
    assert type(from_environ) is int and type(from_file) is int


def test_ack_after_seconds_may_be_zero(tmp_path):
    """A13 step 8 and A14: at 0 the late acknowledgement is posted at once."""
    assert make_settings(tmp_path, MOCO_ACK_AFTER_SECONDS="0").moco_ack_after_seconds == 0
    assert make_settings(tmp_path, "MOCO_ACK_AFTER_SECONDS=0\n").moco_ack_after_seconds == 0


@pytest.mark.parametrize("where", ["environ", "file"])
@pytest.mark.parametrize("key, value", [(k, v) for k, values in CHOICES.items() for v in values])
def test_each_listed_choice_loads(key, value, where, tmp_path):
    if where == "environ":
        settings = make_settings(tmp_path, **{key: value})
    else:
        settings = make_settings(tmp_path, f"{key}={value}\n")
    held = getattr(settings, key.lower())
    if key == "MOCO_BACKGROUND":
        assert is_background(held, value), held
    else:
        assert held == value


@pytest.mark.parametrize("where", ["environ", "file"])
@pytest.mark.parametrize("key, bad", [(k, b) for k, bads in NOT_LISTED.items() for b in bads])
def test_a_choice_outside_the_list_raises_naming_the_key(key, bad, where, tmp_path):
    """A14: a value outside the listed ones is a ConfigError naming the KEY."""
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        if where == "environ":
            make_settings(tmp_path, **{key: bad})
        else:
            make_settings(tmp_path, f"{key}={bad}\n")
    assert key in str(caught.value)


def test_extra_body_becomes_a_dict(tmp_path):
    text = '{"chat_template_kwargs": {"enable_thinking": false}}'
    assert make_settings(tmp_path, NVIDIA_EXTRA_BODY=text).nvidia_extra_body == \
        {"chat_template_kwargs": {"enable_thinking": False}}
    assert make_settings(tmp_path, f"NVIDIA_EXTRA_BODY={text}\n").nvidia_extra_body == \
        {"chat_template_kwargs": {"enable_thinking": False}}


@pytest.mark.parametrize("bad", ["twelve", "1.5"])
@pytest.mark.parametrize("key", NUMBER_KEYS)
def test_a_number_that_is_not_whole_raises_naming_the_key(key, bad, tmp_path):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        make_settings(tmp_path, **{key: bad})
    assert key in str(caught.value)


@pytest.mark.parametrize("bad", ["not json", "[1, 2]", '"text"', "42", "null"])
def test_extra_body_that_is_not_a_json_object_raises_naming_the_key(bad, tmp_path):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        make_settings(tmp_path, NVIDIA_EXTRA_BODY=bad)
    assert "NVIDIA_EXTRA_BODY" in str(caught.value)


@pytest.mark.parametrize("where", ["environ", "file"])
def test_str_and_repr_never_show_a_secret(where, tmp_path):
    if where == "environ":
        settings = make_settings(tmp_path, **FAKE_SECRETS)
    else:
        settings = make_settings(tmp_path, "".join(f"{k}={v}\n" for k, v in FAKE_SECRETS.items()))
    assert settings.nvidia_api_key == FAKE_SECRETS["NVIDIA_API_KEY"]  # really loaded
    for text in (str(settings), repr(settings), f"{settings}"):
        assert_no_secret(text)
        assert re.search(r"\bset\b", text.lower()), text  # each secret shows as "set"


def test_str_and_repr_say_missing_for_missing_secrets(tmp_path):
    settings = make_settings(tmp_path)
    for text in (str(settings), repr(settings)):
        assert re.search(r"\bmissing\b", text.lower()), text


def test_require_for_model_names_the_missing_key_without_values(tmp_path):
    config = mod("config")
    settings = make_settings(tmp_path, SLACK_BOT_TOKEN=FAKE_SECRETS["SLACK_BOT_TOKEN"],
                             SLACK_APP_TOKEN=FAKE_SECRETS["SLACK_APP_TOKEN"])
    with pytest.raises(config.ConfigError) as caught:
        config.require_for_model(settings)
    assert "NVIDIA_API_KEY" in str(caught.value)
    assert_no_secret(str(caught.value))


def test_require_for_model_passes_with_the_key(tmp_path):
    config = mod("config")
    settings = make_settings(tmp_path, NVIDIA_API_KEY=FAKE_SECRETS["NVIDIA_API_KEY"])
    assert config.require_for_model(settings) is None


def test_require_for_serve_names_every_missing_key(tmp_path):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        config.require_for_serve(make_settings(tmp_path))
    for key in SERVE_KEYS:
        assert key in str(caught.value), key


@pytest.mark.parametrize("key", SERVE_KEYS)
def test_require_for_serve_names_a_missing_key_and_shows_no_value(key, tmp_path):
    config = mod("config")
    values = {k: v for k, v in SERVE_VALUES.items() if k != key}
    with pytest.raises(config.ConfigError) as caught:
        config.require_for_serve(make_settings(tmp_path, **values))
    message = str(caught.value)
    assert key in message
    assert_no_secret(message)
    for value in ALL_VALUES:
        assert value not in message, "a value appears in the message"


def test_require_for_serve_needs_at_least_one_allowed_user(tmp_path):
    config = mod("config")
    settings = make_settings(tmp_path, **dict(SERVE_VALUES, SLACK_ALLOWED_USER_IDS=""))
    with pytest.raises(config.ConfigError) as caught:
        config.require_for_serve(settings)
    assert "SLACK_ALLOWED_USER_IDS" in str(caught.value)
    assert_no_secret(str(caught.value))


def test_require_for_serve_passes_with_everything_and_no_channel_list(tmp_path):
    config = mod("config")
    assert config.require_for_serve(make_settings(tmp_path, **SERVE_VALUES)) is None
