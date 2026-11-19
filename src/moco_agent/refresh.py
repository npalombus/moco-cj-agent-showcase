"""Part D (docs/D-DESIGN.md D4, D5): keeping the county copies fresh.

`refresh_all` fetches every valid source once (the `refresh` command). `due` and `run_once`
are what `serve` runs every ten minutes when MOCO_REFRESH_HOURS is above 0. A failure never
stops the next source and never touches a source's last good copy. After a good fetch only
the newest three copies of that source are kept; nothing outside <state dir>/copies/ is
ever deleted.
"""
import logging
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import sources

log = logging.getLogger(__name__)
KEEP = 3              # copies kept per source after a good fetch
LOOK_SECONDS = 600    # how often serve looks for due sources
RETRY_SECONDS = 3600  # a source that failed is not tried again sooner than this
_FAILED_AT = {}       # source id -> when it last failed


def _fetched(copy):
    return datetime.fromisoformat(copy.fetched_at.replace("Z", "+00:00"))


def due(source_ids, state_dir, now, hours):
    """The ids, in order, with no copy or whose newest copy was fetched more than `hours`
    hours before `now`."""
    out = []
    for sid in sorted(source_ids):
        copy = sources.latest(sid, state_dir=state_dir)
        if copy is None or now - _fetched(copy) > timedelta(hours=hours):
            out.append(sid)
    return out


def prune(source_id, state_dir, keep=KEEP):
    """Delete the dated folders of this source beyond the newest `keep`. The current copy is
    never deleted."""
    copies = Path(state_dir) / "copies"
    root = copies / sources.name_of(source_id)
    if root.resolve().parent != copies.resolve():  # D10: never outside copies/
        return
    try:
        current = (root / "current").read_text(encoding="utf-8").strip()
        folders = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return
    for folder in folders[:-keep] if keep else folders:
        if folder.name != current:
            shutil.rmtree(folder, ignore_errors=True)


def fetch_one(source_id, state_dir, transport=None, now=None):
    """Fetch one source and prune. Returns (copy, None) or (None, the failure's text).
    Raises nothing (D4, D10): a failure of any kind is this source's failure only."""
    try:
        copy = sources.fetch(source_id, state_dir=Path(state_dir), transport=transport, now=now)
    except sources.FetchFailed as e:
        return None, str(e)
    except OSError as e:
        return None, f"the copy could not be saved ({type(e).__name__})"
    except Exception as e:
        return None, f"unexpected error ({type(e).__name__})"
    try:
        prune(source_id, state_dir)
    except Exception as e:  # the copy is good; old folders stay for the next fetch
        log.warning("refresh: %s could not be pruned (%s)", source_id, type(e).__name__)
    return copy, None


def refresh_all(state_dir, transport=None, now=None, out=print):
    """D4: every valid source, in id order, one line each. True when all succeeded."""
    from .counting import day_text
    good = True
    for sid in sorted(sources.load_sources()):
        had = sources.latest(sid, state_dir=state_dir) is not None
        copy, failure = fetch_one(sid, state_dir, transport, now)
        if copy is not None:
            out(f"{sid}: {copy.rows:,} rows, copy of {day_text(copy.day)}, "
                f"sha256:{copy.sha256[:12]}")
        else:
            good = False
            out(f"{sid}: FAILED ({failure}); " + ("the last good copy stays in use" if had
                                                  else "there is no copy yet"))
    return good


def run_once(state_dir, now, hours, transport=None):
    """D5: fetch what is due. Returns {source id: "ok" or the failure's text}. Raises
    nothing; a source that failed less than an hour ago is left for a later look."""
    done = {}
    try:
        ids = due(sources.load_sources(), state_dir, now, hours)
    except Exception as e:  # never stops serve
        log.warning("refresh: could not look for due sources (%s)", type(e).__name__)
        return done
    for sid in ids:
        failed_at = _FAILED_AT.get((str(state_dir), sid))
        if failed_at is not None and (now - failed_at).total_seconds() < RETRY_SECONDS:
            continue
        try:
            copy, failure = fetch_one(sid, state_dir, transport, now)
        except Exception as e:
            copy, failure = None, f"unexpected error ({type(e).__name__})"
        if copy is not None:
            _FAILED_AT.pop((str(state_dir), sid), None)
            done[sid] = "ok"
            log.info("refresh: %s ok rows=%d sha256=%s", sid, copy.rows, copy.sha256[:12])
        else:
            _FAILED_AT[(str(state_dir), sid)] = now
            done[sid] = failure
            log.warning("refresh: %s failed: %s", sid, failure)
    return done


def start(settings, transport=None, clock=None, wait=None):
    """D5: with MOCO_DATA=county and MOCO_REFRESH_HOURS above 0, look once now and then
    every ten minutes, beside the Slack connection. Returns the thread, or None when off.
    `wait(seconds)` returns True to stop (tests); by default it waits on an event."""
    hours = getattr(settings, "moco_refresh_hours", 0)
    if hours <= 0 or getattr(settings, "moco_data", "synthetic") != "county":
        return None
    stop = threading.Event()
    clock = clock or (lambda: datetime.now(timezone.utc))
    wait = wait or stop.wait

    last = [clock()]  # S3A C61 point 14: the clean-ups again once a day, beside the refresh

    def loop():
        while True:
            if clock() - last[0] >= timedelta(days=1):
                last[0] = clock()
                try:
                    from . import cleanup
                    cleanup.daily(settings, clock())
                except Exception as e:  # never stops serve
                    log.warning("clean-up: the daily run failed (%s)", type(e).__name__)
            run_once(settings.moco_state_dir, clock(), hours, transport)
            key = getattr(settings, "census_api_key", None)
            if key:  # S2 R8: the Census copies too, at most once a day
                try:
                    from . import census
                    census.refresh_due(settings.moco_state_dir, key, clock(), out=log.info)
                except Exception as e:  # never stops serve
                    log.warning("refresh: the Census copies failed (%s)", type(e).__name__)
            if wait(LOOK_SECONDS):
                return

    thread = threading.Thread(target=loop, name="moco-refresh", daemon=True)
    thread.stop = stop
    thread.start()
    return thread
