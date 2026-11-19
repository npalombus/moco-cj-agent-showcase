"""The Slack service (design P1, section 11; design P1A, A13).

The agent connects out to Slack in Socket Mode, so it needs no public address. All the
logic is in process_event, which tests call with fakes; build_app and serve only wire it
to Slack. The log (var/agent.log) holds ids, labels, codes and times: never a token, a key,
the question or the reply.
"""
import logging
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import replies
from .memory import GIVEN  # S3A C69
from .core import REPO

log = logging.getLogger(__name__)

VAR = REPO / "var"
LABELS = {"ANSWERED": "answered", "EXPLAINED": "explained", "DETAILS": "details",
          "UNSUPPORTED": "refused", "NEEDS_INPUT": "needs_input", "ERROR": "error",
          "TALKED": "talked"}  # T4, MOCO_TALK on
_MENTION = re.compile(r"<@[^>]*>")


def start_thread_timer(seconds, function):
    timer = threading.Timer(seconds, function)
    timer.daemon = True
    timer.start()
    return timer


def _kind_of(event, store, team_id):
    """A13 step 1: "mention", "direct" or "followed", or None for an event to ignore."""
    text = event.get("text")
    if (event.get("bot_id") or event.get("subtype") or not event.get("user")
            or not isinstance(text, str) or not text.strip()
            or not event.get("channel") or not event.get("ts")):
        return None
    if event.get("type") == "app_mention":
        return "mention"
    if event.get("type") != "message":
        return None
    if event.get("channel_type") == "im":
        return "direct"
    key = f"{team_id}:{event.get('channel')}:{event.get('thread_ts')}"
    if (event.get("channel_type") in ("channel", "group") and event.get("thread_ts")
            and "<@" not in text
            and (store.thread_has_turns(key)  # S3A C69: and after `reset` in county mode
                 or store.thread_has_turns(key + GIVEN))):
        return "followed"
    return None


def process_event(event, *, team_id, event_id, settings, store, agent, slack, now=None,
                  start_timer=None):
    """One Slack event, in the steps of A13. Returns what it did, as a label."""
    started = time.monotonic()
    now = now if now is not None else datetime.now(timezone.utc)
    start_timer = start_timer if start_timer is not None else start_thread_timer
    kind = _kind_of(event, store, team_id) if isinstance(event, dict) else None
    if kind is None:
        return "ignored"  # 1. post nothing, store nothing, log nothing
    channel, user = event["channel"], event["user"]
    top_level_dm = kind == "direct" and not event.get("thread_ts")
    # 4. Where it belongs (worked out here, so every post goes to the same place).
    thread_ts = None if top_level_dm else (event.get("thread_ts") or event["ts"])
    thread_key = f"{team_id}:{channel}:{'dm' if top_level_dm else thread_ts}"
    outcome = {"label": "error", "reply": None}
    try:
        label = _steps(event, kind, channel, user, thread_ts, thread_key, top_level_dm,
                       outcome, team_id=team_id, event_id=event_id, settings=settings,
                       store=store, agent=agent, slack=slack, now=now,
                       start_timer=start_timer)
        if label is None:
            return "ignored"  # a followed message from someone not approved: in silence
        outcome["label"] = label
    except Exception:
        # 10. A fixed line with a reference; the traceback goes to the log only.
        ref = uuid.uuid4().hex[:8]
        log.error("event %s failed (ref %s):\n%s", event_id, ref, traceback.format_exc())
        try:
            slack.post_message(channel, thread_ts, replies.ERROR_LINE.format(ref=ref))
        except Exception:
            log.error("event %s: the error line could not be posted either (ref %s)",
                      event_id, ref)
        outcome["label"] = "error"
    reply = outcome["reply"]
    log.info("event=%s user=%s label=%s status=%s reason=%s kind=%s style=%s steps=%s "
             "failures=%s turn=%s runs=%s model=%s seconds=%.2f", event_id, user,
             outcome["label"], getattr(reply, "status", None),
             getattr(reply, "reason_code", None), getattr(reply, "reply_kind", None),
             getattr(reply, "reply_style", None), getattr(reply, "steps", None),
             ",".join(getattr(reply, "draft_failures", None) or []) or None,
             getattr(reply, "turn_id", None), ",".join(getattr(reply, "run_ids", None) or [])
             or None, getattr(reply, "model_id", None), time.monotonic() - started)
    return outcome["label"]


def _steps(event, kind, channel, user, thread_ts, thread_key, top_level_dm, outcome, *,
           team_id, event_id, settings, store, agent, slack, now, start_timer):
    # 2. Duplicate delivery, by event id or by the message itself.
    if (event_id and store.seen_event(event_id)) or \
            store.seen_event(f"msg:{channel}:{event['ts']}"):
        return "duplicate"
    # 3. Authorize: the one workspace, an approved person, an allowed channel (or a DM).
    allowed = (bool(settings.slack_allowed_team_id)
               and team_id == settings.slack_allowed_team_id
               and user in (settings.slack_allowed_user_ids or ())
               and (not settings.slack_allowed_channel_ids or kind == "direct"
                    or channel in settings.slack_allowed_channel_ids))
    if not allowed:
        if kind == "followed":
            return None
        slack.post_message(channel, thread_ts, replies.NOT_AUTHORIZED)
        return "unauthorized"
    # 5. Clean the text; 6. commands.
    question = _MENTION.sub("", event["text"]).strip()
    if question.lower() == "help" and \
            getattr(settings, "moco_data", "synthetic") != "county":  # C36: county asks the model
        if getattr(settings, "moco_data", "synthetic") == "county":  # S3A C11
            from .sources import county_sources
            slack.post_message(channel, thread_ts, replies.county_help(county_sources()))
        else:
            slack.post_message(channel, thread_ts, replies.HELP)
        return "help"
    if question.lower() == "reset":
        if getattr(settings, "moco_data", "synthetic") == "county":  # S3A C65 point 4
            store.reset_thread(thread_key, keep_given=True)
            slack.post_message(channel, thread_ts, replies.RESET_DONE_COUNTY)
        else:
            store.reset_thread(thread_key)
            slack.post_message(channel, thread_ts, replies.RESET_DONE)
        return "reset"
    # 7. Per-person limit: N requests inside 60 seconds are handled, the next is refused.
    if store.user_requests_since(user, now - timedelta(seconds=60)) >= \
            settings.moco_user_requests_per_minute:
        slack.post_message(channel, thread_ts, replies.WAIT)
        return "rate_limited"
    store.record_user_request(user, now)
    # C37: who had a turn in this thread before this message
    people_before = {t.get("user_id") for t in store.recent_turns(thread_key, 500)}
    # 8. "One moment." only if the agent has not answered in time, and never after it.
    lock, state = threading.Lock(), {"done": False}

    def one_moment():
        with lock:
            if not state["done"]:
                state["done"] = True
                slack.post_message(channel, thread_ts, replies.ONE_MOMENT)

    timer = None
    if settings.moco_ack_after_seconds <= 0:
        one_moment()
    else:
        timer = start_timer(settings.moco_ack_after_seconds, one_moment)
    try:
        reply = agent(question, thread_key, user,
                      memory_minutes=settings.moco_dm_memory_minutes if top_level_dm else None)
    finally:
        with lock:
            state["done"] = True
        if timer is not None:
            timer.cancel()
    outcome["reply"] = reply
    # 9. Post once.
    if kind == "followed" and (reply.status, reply.reason_code) == \
            ("UNSUPPORTED", "UNRECOGNIZED_QUESTION") and len(people_before) > 1:
        return "quiet"  # C37: silent only when other people share the thread
    # S3S: an analysis's chart goes with its answer, the R script with details (S5, S7)
    files = ([reply.chart_path] if reply.chart_path else []) + \
        list(getattr(reply, "attachments", None) or [])
    if files:
        try:
            slack.upload_file(channel, thread_ts, str(files[0]),
                              reply.chart_title if reply.chart_path else Path(files[0]).name,
                              reply.text)
        except Exception as e:
            log.warning("event %s: the chart upload failed (%s); posting the text instead",
                        event_id, type(e).__name__)
            slack.post_message(channel, thread_ts, reply.text)
        for path in files[1:]:
            try:
                slack.upload_file(channel, thread_ts, str(path), Path(path).name, None)
            except Exception as e:
                log.warning("event %s: a file upload failed (%s)", event_id, type(e).__name__)
    else:
        slack.post_message(channel, thread_ts, reply.text)
    return LABELS.get(reply.status, "error")


class SlackPoster:
    """post_message and upload_file on Slack's own web client."""

    def __init__(self, client):
        self._client = client

    def post_message(self, channel, thread_ts, text):
        extra = {} if thread_ts is None else {"thread_ts": thread_ts}
        self._client.chat_postMessage(channel=channel, text=text, **extra)

    def upload_file(self, channel, thread_ts, path, title, comment):
        extra = {} if thread_ts is None else {"thread_ts": thread_ts}
        self._client.files_upload_v2(channel=channel, file=str(path), filename=Path(path).name,
                                     title=title, initial_comment=comment, **extra)


def build_app(settings, registry, store, model_client, backup=None):
    from slack_bolt import App

    from .agent import handle_question

    app = App(token=settings.slack_bot_token)
    slack = SlackPoster(app.client)

    def agent(question, thread_key, user_id, memory_minutes=None):
        return handle_question(question, thread_key=thread_key, user_id=user_id,
                               settings=settings, registry=registry,
                               model_client=model_client, store=store,
                               memory_minutes=memory_minutes, backup=backup)

    def on_event(body, event):
        process_event(event, team_id=body.get("team_id"), event_id=body.get("event_id"),
                      settings=settings, store=store, agent=agent, slack=slack)

    app.event("app_mention")(on_event)
    app.event("message")(on_event)  # every message event; process_event keeps what A13 says
    return app


def serve(settings=None):
    """Blocks. Fails closed: with any required setting missing, nothing starts."""
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    from . import refresh
    from .config import (backup_settings, ensure_folder, load_settings, model_service,
                         require_for_serve, state_file)
    from .llm import NvidiaModelClient
    from .memory import Store
    from .registry import load_registry

    settings = settings if settings is not None else load_settings()
    require_for_serve(settings)
    registry = load_registry()
    # Part D D1: the log and the memory follow MOCO_STATE_DIR (today's folder by default).
    log_file = state_file(settings, "agent.log", VAR / "agent.log")
    db_file = state_file(settings, "agent.db", VAR / "agent.db")
    if log_file == VAR / "agent.log":
        VAR.mkdir(exist_ok=True)
    else:
        ensure_folder(log_file.parent, "MOCO_STATE_DIR")
    from . import cleanup
    from .agent import DEFAULT_RUNS
    from .config import runs_dir_of
    cleanup.roll_log(log_file)  # S3A C61 point 13
    line = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(line)
    package_log = logging.getLogger("moco_agent")
    package_log.addHandler(handler)
    if settings.moco_log_stdout == "on":  # D3: the same lines on the screen too
        screen = logging.StreamHandler(sys.stdout)
        screen.setFormatter(line)
        package_log.addHandler(screen)
    package_log.setLevel(logging.INFO)

    store = Store(db_file)
    purged = store.purge_older_than(settings.moco_retention_days, datetime.now(timezone.utc))
    log.info("serve starting: model=%s retention_days=%d purged_turns=%d",
             model_service(settings).model, settings.moco_retention_days, purged)
    try:  # S3A C61 point 12
        log.info("clean-up: %d old record folders removed", cleanup.purge_records(
            runs_dir_of(settings, DEFAULT_RUNS), settings.moco_retention_days,
            datetime.now(timezone.utc)))
    except OSError as e:
        log.warning("clean-up: the records folder could not be cleaned (%s)", type(e).__name__)
    second = backup_settings(settings)  # S3A C56 point 3
    backup = None if second is None else (second, NvidiaModelClient(second))
    if backup is not None:
        log.info("backup model: %s", model_service(second).model)
    app = build_app(settings, registry, store, NvidiaModelClient(settings), backup)
    refresh.start(settings)  # D5: off unless MOCO_REFRESH_HOURS is above 0 in county mode
    data = "COUNTY (real county open data)" if settings.moco_data == "county" else "SYNTHETIC"
    print(f"The agent is connecting to Slack (model {model_service(settings).model}, data {data}). "
          f"Log: {log_file}. Stop it with Ctrl+C.", flush=True)
    try:
        SocketModeHandler(app, settings.slack_app_token).start()
    finally:
        store.close()
