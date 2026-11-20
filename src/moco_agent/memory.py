"""Thread memory in one SQLite file (design P1, section 10; design P1A, A12).

A turn is stored with its thread key, user id, question, status, reason code and time, and
a small JSON record: the guard codes, the model id, the steps, the turn id, the results (id,
kind, year and age group or the compared ids, run id; never a value), what was kept, the
values a NEEDS_INPUT turn saved, the reply's kind and style, and the model's text when it
passed the checks (its slots unfilled, so it holds no number), or for a talk turn (MOCO_TALK
on) the text sent, which passed the talk check or is the fallback line. Never stored: a
token, a key, a person's name, a number from an answer, or a text that failed the checks.

A turn is found by its exact thread key only, so one thread never sees another's. Turns
live in the table agent_turns. The table `turns` of stage 2's first build (questions and
Slack user ids) is dropped with everything in it when a file that holds it is opened (R5).
"""
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import REPO

DEFAULT_DB = REPO / "var" / "agent.db"
REQUEST_CODES = ("UNSUPPORTED_FIELD", "UNSUPPORTED_METRIC", "REAL_DATA_NOT_AVAILABLE",
                 "OUT_OF_COVERAGE")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_key TEXT NOT NULL, user_id TEXT, question TEXT, status TEXT, reason_code TEXT,
    created_at TEXT NOT NULL, record TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS agent_turns_by_thread ON agent_turns (thread_key, id);
CREATE TABLE IF NOT EXISTS seen_events (event_id TEXT PRIMARY KEY, seen_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_requests (user_id TEXT NOT NULL, at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS user_requests_by_user ON user_requests (user_id, at);
CREATE TABLE IF NOT EXISTS model_calls (utc_date TEXT PRIMARY KEY, calls INTEGER NOT NULL);
"""
_TIME = "%Y-%m-%dT%H:%M:%S.%fZ"
GIVEN = "\x1fgiven"  # C65 point 4: added to a thread's key for what reset keeps


def _utc_text(moment):
    """A fixed-width UTC time, so the stored texts sort in time order."""
    if moment.tzinfo is None:  # ponytail: a naive time is taken to be UTC already
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime(_TIME)


def _from_text(text):
    return datetime.strptime(text, _TIME).replace(tzinfo=timezone.utc)


def _day_text(day):
    return (day.date() if isinstance(day, datetime) else day).isoformat()


class Store:
    def __init__(self, path=DEFAULT_DB):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Slack's handler runs events on worker threads: one connection, one lock.
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        old = self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'turns'").fetchall()
        if old:  # R5; VACUUM so the old rows leave the file, not just the table
            self._db.executescript("DROP TABLE turns; VACUUM;")

    def _run(self, sql, params=()):
        with self._lock:
            return self._db.execute(sql, params)

    def _all(self, sql, params=()):
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    def add_turn(self, *, thread_key, user_id, question, status, reason_code, created_at,
                 record):
        cursor = self._run(
            "INSERT INTO agent_turns (thread_key, user_id, question, status, reason_code, "
            "created_at, record) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (thread_key, user_id, question, status, reason_code, _utc_text(created_at),
             json.dumps(record)))
        return int(cursor.lastrowid)

    def recent_turns(self, thread_key, limit, since=None):
        """The newest `limit` turns of exactly this thread (only those made after `since`,
        when given), oldest first, each a dict: the stored columns plus the record's keys."""
        if limit <= 0:
            return []
        rows = self._all(
            "SELECT question, status, reason_code, created_at, record, user_id FROM agent_turns "
            "WHERE thread_key = ? AND created_at > ? ORDER BY id DESC LIMIT ?",
            (thread_key, "" if since is None else _utc_text(since), int(limit)))
        return [dict(json.loads(record), question=question, status=status,
                     reason_code=reason_code, created_at=_from_text(created_at),
                     user_id=user_id)
                for question, status, reason_code, created_at, record, user_id in reversed(rows)]

    def thread_has_turns(self, thread_key):
        return bool(self._all("SELECT 1 FROM agent_turns WHERE thread_key = ? LIMIT 1",
                              (thread_key,)))

    def refused_turns(self, days, now=None):
        """Turns refused with a request code (A15) in the last `days` days, newest first:
        [{"created_at", "reason_code", "question"}]. No user id."""
        now = now if now is not None else datetime.now(timezone.utc)
        rows = self._all(
            f"SELECT created_at, reason_code, question FROM agent_turns WHERE status = "
            f"'UNSUPPORTED' AND reason_code IN ({', '.join('?' * len(REQUEST_CODES))}) AND "
            f"created_at >= ? ORDER BY created_at DESC, id DESC",
            (*REQUEST_CODES, _utc_text(now - timedelta(days=days))))
        return [{"created_at": _from_text(at), "reason_code": code, "question": question}
                for at, code, question in rows]

    def reset_thread(self, thread_key, keep_given=False):
        """Delete this thread's turns; returns how many. C65 point 4: with `keep_given`, each
        ANSWERED turn that holds a count or a statistic leaves one stripped record behind
        (the time, the status, and of each count or statistic its kind, spec, days and, for
        a statistic, its name and options), under a key of its own."""
        if keep_given:
            rows = self._all("SELECT created_at, record FROM agent_turns "  # C65 point 10:
                             "WHERE thread_key = ? ORDER BY id",  # whatever the turn's ending
                             (thread_key,))
            for created_at, record in rows:
                try:
                    results = json.loads(record).get("results") or []
                except (TypeError, ValueError):
                    continue
                kept = [{k: r[k] for k in ("kind", "stat", "spec", "options", "days") if k in r}
                        for r in results if isinstance(r, dict)
                        and r.get("kind") in ("count", "analysis")
                        and isinstance(r.get("spec"), dict)]
                if kept:
                    self._run("INSERT INTO agent_turns (thread_key, user_id, question, status, "
                              "reason_code, created_at, record) VALUES (?, NULL, '', "
                              "'ANSWERED', NULL, ?, ?)",
                              (thread_key + GIVEN, created_at, json.dumps({"results": kept})))
        return self._run("DELETE FROM agent_turns WHERE thread_key = ?", (thread_key,)).rowcount

    def given_before_reset(self, thread_key, limit):
        """C65 point 4: the stripped records `reset` left of this thread, oldest first, for
        C21's check alone."""
        return self.recent_turns(thread_key + GIVEN, limit)

    def purge_older_than(self, days, now):
        """Delete turns older than `days` before `now`; returns how many. Old event ids and
        request times go too."""
        cutoff = _utc_text(now - timedelta(days=days))
        deleted = self._run("DELETE FROM agent_turns WHERE created_at < ?", (cutoff,)).rowcount
        self._run("DELETE FROM seen_events WHERE seen_at < ?", (cutoff,))
        self._run("DELETE FROM user_requests WHERE at < ?", (cutoff,))
        return deleted

    def seen_event(self, event_id):
        """True when this event id was already recorded; else records it and says False."""
        cursor = self._run("INSERT OR IGNORE INTO seen_events (event_id, seen_at) VALUES (?, ?)",
                           (str(event_id), _utc_text(datetime.now(timezone.utc))))
        return cursor.rowcount == 0

    def record_user_request(self, user_id, at):
        self._run("INSERT INTO user_requests (user_id, at) VALUES (?, ?)",
                  (user_id, _utc_text(at)))

    def user_requests_since(self, user_id, since):
        return self._all("SELECT COUNT(*) FROM user_requests WHERE user_id = ? AND at >= ?",
                         (user_id, _utc_text(since)))[0][0]

    def record_model_call(self, utc_date):
        self._run("INSERT INTO model_calls (utc_date, calls) VALUES (?, 1) "
                  "ON CONFLICT (utc_date) DO UPDATE SET calls = calls + 1",
                  (_day_text(utc_date),))

    def model_calls_on(self, utc_date):
        rows = self._all("SELECT calls FROM model_calls WHERE utc_date = ?",
                         (_day_text(utc_date),))
        return rows[0][0] if rows else 0

    def close(self):
        with self._lock:
            self._db.close()
