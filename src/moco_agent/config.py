"""Settings and secrets (design P1, section 4; design P1A, A14).

The secrets live in one private file outside the repo, ~/.config/moco-cj-agent/.env, or the
file named by MOCO_ENV_FILE. Only this module reads it, at run time. A value in the process
environment wins over the file. No secret's value is ever shown: str() and repr() say "set"
or "missing", and a ConfigError names the KEY, never a value.
"""
import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_ENV_FILE = "~/.config/moco-cj-agent/.env"
# S3A C4: copies of county sources live under the state folder (not in git).
DEFAULT_STATE_DIR = str(Path(__file__).resolve().parents[2] / "var")
# Part D D2: the saved records. The default is today's folder.
DEFAULT_RUNS_DIR = str(Path(__file__).resolve().parents[2] / "runs")

SECRETS = ("NVIDIA_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN")
# Part S2 R8: the Census key, for `fetch-census` only (serve does not need it), never shown.
CENSUS_KEY = "CENSUS_API_KEY"
# S3A C51: the key of the second model service, shown and required as a secret is. It is
# not in SECRETS, because a run needs only the active service's key.
ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
TEXT = {"NVIDIA_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
        "NVIDIA_BASE_URL": "https://integrate.api.nvidia.com/v1",
        "ANTHROPIC_MODEL": "claude-haiku-5-5",  # S3A C51
        "ANTHROPIC_BASE_URL": "https://api.anthropic.com/v1/",
        "SLACK_ALLOWED_TEAM_ID": None, "MOCO_STATE_DIR": DEFAULT_STATE_DIR,
        "MOCO_RUNS_DIR": DEFAULT_RUNS_DIR,
        "MOCO_RSCRIPT": "Rscript"}  # S3S S8: the Rscript that runs analysis_r/
LISTS = ("SLACK_ALLOWED_USER_IDS", "SLACK_ALLOWED_CHANNEL_IDS")
NUMBERS = {"MOCO_MAX_QUESTION_CHARS": 500, "MOCO_USER_REQUESTS_PER_MINUTE": 6,
           "MOCO_DAILY_MODEL_CALLS": 0, "MOCO_MODEL_TIMEOUT_SECONDS": 45,
           "MOCO_MODEL_MAX_RETRIES": 1, "MOCO_MODEL_MAX_TOKENS": 2048,
           "MOCO_THREAD_TURNS_IN_CONTEXT": 10, "MOCO_RETENTION_DAYS": 30,
           "MOCO_MAX_STEPS": 6, "MOCO_TURN_SECONDS": 90, "MOCO_DM_MEMORY_MINUTES": 60,
           "MOCO_ACK_AFTER_SECONDS": 3, "MOCO_REFRESH_HOURS": 0}  # Part D D5
MOST = {"MOCO_REFRESH_HOURS": 168}
# A14: a value outside its list is a ConfigError; the first value is the default.
CHOICES = {"MOCO_REPLY_STYLE": ("agent", "fixed"), "MOCO_BACKGROUND": ("off", "on"),
           "MOCO_DATA": ("synthetic", "county"),  # S3A C0
           "MOCO_TALK": ("off", "on"),  # T0
           "MOCO_LOG_STDOUT": ("off", "on"),  # Part D D3
           "MOCO_MODEL_PROVIDER": ("nvidia", "anthropic")}  # S3A C51
# S3A C56: the backup model service, both unset (no backup) or both set.
BACKUP_KEYS = ("MOCO_BACKUP_PROVIDER", "MOCO_BACKUP_MODEL")
KEYS = (*SECRETS, *TEXT, "NVIDIA_EXTRA_BODY", *LISTS, *NUMBERS, *CHOICES, CENSUS_KEY,
        ANTHROPIC_KEY, *BACKUP_KEYS)
# S3A C51: per service, the router a record names when the model chose the call.
MODEL_ROUTERS = {"nvidia": "NVIDIA_MODEL_TOOL_CALL", "anthropic": "ANTHROPIC_MODEL_TOOL_CALL"}


class ConfigError(Exception):
    """A setting is missing or malformed. The message names KEYs only, never a value."""


@dataclass(frozen=True, repr=False)
class Settings:
    nvidia_api_key: str | None
    slack_bot_token: str | None
    slack_app_token: str | None
    nvidia_model: str
    nvidia_base_url: str
    slack_allowed_team_id: str | None
    nvidia_extra_body: dict
    slack_allowed_user_ids: tuple
    slack_allowed_channel_ids: tuple
    moco_max_question_chars: int
    moco_user_requests_per_minute: int
    moco_daily_model_calls: int
    moco_model_timeout_seconds: int
    moco_model_max_retries: int
    moco_model_max_tokens: int
    moco_thread_turns_in_context: int
    moco_retention_days: int
    moco_max_steps: int
    moco_turn_seconds: int
    moco_dm_memory_minutes: int
    moco_ack_after_seconds: int
    moco_reply_style: str
    moco_background: str
    moco_state_dir: str
    moco_data: str
    moco_talk: str = "off"  # T0
    moco_runs_dir: str = DEFAULT_RUNS_DIR  # Part D
    moco_refresh_hours: int = 0
    moco_log_stdout: str = "off"
    moco_rscript: str = "Rscript"  # S3S S8
    census_api_key: str | None = None  # S3S2 R8
    anthropic_api_key: str | None = None  # S3A C51
    anthropic_model: str = "claude-haiku-5-5"
    anthropic_base_url: str = "https://api.anthropic.com/v1/"
    moco_model_provider: str = "nvidia"
    moco_backup_provider: str | None = None  # S3A C56
    moco_backup_model: str | None = None

    def __repr__(self):
        def shown(key):
            value = getattr(self, key.lower())
            if key in (*SECRETS, CENSUS_KEY, ANTHROPIC_KEY):
                return "set" if value else "missing"
            return repr(value)
        return f"Settings({', '.join(f'{key.lower()}={shown(key)}' for key in KEYS)})"

    __str__ = __repr__


def load_settings(env_file=None, environ=None):
    """Read the private file (a missing file is not an error), then let the environment
    override it. Raises ConfigError for a number that is not whole or an NVIDIA_EXTRA_BODY
    that is not a JSON object."""
    environ = os.environ if environ is None else environ
    if env_file is None:
        env_file = environ.get("MOCO_ENV_FILE") or DEFAULT_ENV_FILE
    values = _read_file(Path(env_file).expanduser())
    values.update({key: environ[key] for key in KEYS if key in environ})
    # ponytail: an empty value counts as unset everywhere (a blank line in the file, or
    # KEY="" in the environment), so a blank secret is "missing", never "set".
    blank = {key for key, value in values.items() if value == ""}
    values = {key: value for key, value in values.items() if value != ""}

    fields = {key.lower(): values.get(key) for key in SECRETS}
    fields.update({key.lower(): values.get(key, default) for key, default in TEXT.items()})
    fields.update({key.lower(): _ids(values.get(key, "")) for key in LISTS})
    for key, default in NUMBERS.items():
        text = values.get(key)
        if key in MOST and key in blank:  # Part D D5, D8: the one key where empty is not unset
            raise ConfigError(f"{key} must be a whole number from 0 to {MOST[key]}")
        if text is not None and not re.fullmatch(r"\s*[0-9]+\s*", text):
            raise ConfigError(f"{key} must be a whole number of 0 or more")
        if text is not None and key in MOST and int(text) > MOST[key]:
            raise ConfigError(f"{key} must be a whole number from 0 to {MOST[key]}")
        fields[key.lower()] = default if text is None else int(text)
    for key, allowed in CHOICES.items():
        value = values.get(key, allowed[0])
        if value not in allowed:
            raise ConfigError(f"{key} must be one of: {', '.join(allowed)}")
        fields[key.lower()] = value
    fields["nvidia_extra_body"] = _extra_body(values.get("NVIDIA_EXTRA_BODY"))
    fields["census_api_key"] = values.get(CENSUS_KEY)
    fields["anthropic_api_key"] = values.get(ANTHROPIC_KEY)
    provider, model = (values.get(key) for key in BACKUP_KEYS)  # S3A C56 point 1
    if provider is not None and provider not in CHOICES["MOCO_MODEL_PROVIDER"]:
        raise ConfigError(f"{BACKUP_KEYS[0]} must be one of: "
                          f"{', '.join(CHOICES['MOCO_MODEL_PROVIDER'])}")
    if (provider is None) != (model is None):
        raise ConfigError(f"{BACKUP_KEYS[0]} and {BACKUP_KEYS[1]} must be set together, or "
                          f"neither")
    fields["moco_backup_provider"], fields["moco_backup_model"] = provider, model
    settings = Settings(**fields)
    active = model_service(settings)
    if provider is not None and (provider, model) == (active.provider, active.model):
        raise ConfigError(f"{BACKUP_KEYS[0]} and {BACKUP_KEYS[1]} name the active model "
                          f"service's own model: a backup must be another model")
    return settings


@dataclass(frozen=True, repr=False)
class ModelService:
    """S3A C51: what the model client needs from the active service. Never shown."""
    provider: str
    key_name: str
    api_key: str | None
    base_url: str
    model: str
    extra_body: dict
    temperature: int | None  # None: the request carries no temperature
    router: str

    def __repr__(self):
        return f"ModelService(provider={self.provider!r}, model={self.model!r})"

    __str__ = __repr__


def model_service(settings):
    """The service MOCO_MODEL_PROVIDER names (nvidia when the settings do not say)."""
    if getattr(settings, "moco_model_provider", "nvidia") == "anthropic":
        return ModelService("anthropic", ANTHROPIC_KEY, getattr(settings, "anthropic_api_key", None),
                            settings.anthropic_base_url, settings.anthropic_model, {}, None,
                            MODEL_ROUTERS["anthropic"])
    return ModelService("nvidia", "NVIDIA_API_KEY", getattr(settings, "nvidia_api_key", None),
                        getattr(settings, "nvidia_base_url", TEXT["NVIDIA_BASE_URL"]),
                        settings.nvidia_model,
                        dict(getattr(settings, "nvidia_extra_body", None) or {}), 0,
                        MODEL_ROUTERS["nvidia"])


def model_router(settings):
    """The router a record names when the active service's model chose the call."""
    return MODEL_ROUTERS[getattr(settings, "moco_model_provider", "nvidia")]


def with_model(settings, model_id):
    """The settings with the active service's model set to model_id, nothing else changed."""
    field = "anthropic_model" if model_service(settings).provider == "anthropic" else "nvidia_model"
    return replace(settings, **{field: model_id})


def backup_settings(settings):
    """S3A C56 point 2: None with no backup; else the settings of the backup service: the
    same settings with the backup's provider active and its model as that provider's
    model, and no backup of its own."""
    provider = getattr(settings, "moco_backup_provider", None)
    model = getattr(settings, "moco_backup_model", None)
    if not provider or not model:
        return None
    field = "anthropic_model" if provider == "anthropic" else "nvidia_model"
    return replace(settings, moco_model_provider=provider, moco_backup_provider=None,
                   moco_backup_model=None, **{field: model})


def _model_keys(settings):
    """The active service's key and, with a backup set, the backup service's (C56)."""
    keys = [model_service(settings).key_name]
    backup = backup_settings(settings)
    if backup is not None and model_service(backup).key_name not in keys:
        keys.append(model_service(backup).key_name)
    return keys


def state_file(settings, name, today):
    """Part D D1: where a file of the state folder lives. With MOCO_STATE_DIR at its
    default this is `today` (the path used before Part D), so nothing moves."""
    folder = getattr(settings, "moco_state_dir", DEFAULT_STATE_DIR)
    return Path(today) if folder == DEFAULT_STATE_DIR else Path(folder).expanduser() / name


def runs_dir_of(settings, today):
    """Part D D2: the records folder; `today` when MOCO_RUNS_DIR is at its default."""
    folder = getattr(settings, "moco_runs_dir", DEFAULT_RUNS_DIR)
    return Path(today) if folder == DEFAULT_RUNS_DIR else Path(folder).expanduser()


def ensure_folder(path, key):
    """Make the folder (parents included) and check it can be written, or raise a
    ConfigError naming the KEY."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        probe = Path(path) / ".moco-write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        raise ConfigError(f"{key}: the folder could not be made or written "
                          f"({type(e).__name__})") from None


def require(settings, *keys):
    """Fail closed: raise ConfigError naming every KEY in `keys` that has no value."""
    missing = [key for key in keys if not getattr(settings, key.lower())]
    if missing:
        raise ConfigError(
            f"Missing setting{'s' if len(missing) > 1 else ''}: {', '.join(missing)}. Add "
            f"{'them' if len(missing) > 1 else 'it'} to the private settings file "
            f"({DEFAULT_ENV_FILE}, or the file named by MOCO_ENV_FILE); see README.md.")


def require_for_model(settings):
    require(settings, *_model_keys(settings))  # S3A C51, C56: the services' keys


def require_for_serve(settings):
    require(settings, *_model_keys(settings), "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN",
            "SLACK_ALLOWED_TEAM_ID", "SLACK_ALLOWED_USER_IDS")


def _read_file(path):
    """KEY=VALUE lines. Blank lines and lines starting with # are skipped; one pair of
    matching quotes around a value is removed; nothing else is interpreted."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as e:  # unreadable: say so by its kind, never by its contents
        raise ConfigError(f"the private settings file could not be read "
                          f"({type(e).__name__})") from None
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _ids(text):
    return tuple(part.strip() for part in text.split(",") if part.strip())


def _extra_body(text):
    if text is None:
        return {}
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if not isinstance(value, dict):
        raise ConfigError("NVIDIA_EXTRA_BODY must be a JSON object, for example "
                          '{"chat_template_kwargs": {"enable_thinking": false}}')
    return value
