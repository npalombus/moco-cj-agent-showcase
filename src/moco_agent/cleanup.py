"""S3A C61 Part E: what would otherwise pile up on the storage. The saved records of old
turns and runs go after the retention days, as the thread memory does; the log starts anew
when it has grown large."""
import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path

log = logging.getLogger(__name__)
LOG_MAX_BYTES = 5_000_000


def purge_records(folder, days, now):
    """Remove every folder directly under `folder` whose newest file is older than `days`
    days before `now`; returns how many. A folder that cannot be removed is logged and left."""
    folder, cutoff, removed = Path(folder), (now - timedelta(days=days)).timestamp(), 0
    if not folder.exists():
        return 0
    if not folder.is_dir():
        raise NotADirectoryError(str(folder.name))
    for entry in sorted(folder.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        try:
            times = [f.stat().st_mtime for f in entry.rglob("*") if f.is_file()]
            if max(times or [entry.stat().st_mtime]) >= cutoff:
                continue
            shutil.rmtree(entry)
            removed += 1
        except OSError as e:
            log.warning("clean-up: %s could not be removed (%s)", entry.name, type(e).__name__)
    return removed


def daily(settings, now):
    """C61 point 14: the two clean-ups again, with a connection of its own: old turns, then
    old record folders. Returns (turns, folders); raises when one of them cannot be done."""
    from .config import DEFAULT_STATE_DIR, runs_dir_of, state_file
    from .core import DEFAULT_RUNS
    from .memory import Store
    days = settings.moco_retention_days
    own = Store(state_file(settings, "agent.db", Path(DEFAULT_STATE_DIR) / "agent.db"))
    try:
        turns = own.purge_older_than(days, now)
    finally:
        own.close()
    folders = purge_records(runs_dir_of(settings, DEFAULT_RUNS), days, now)
    log.info("clean-up: %d old turns and %d old record folders removed", turns, folders)
    return turns, folders


def roll_log(path):
    """Before logging starts: a log above LOG_MAX_BYTES becomes `<name>.1` (replacing an
    older one). True when it was rolled."""
    path = Path(path)
    try:
        if path.is_file() and path.stat().st_size > LOG_MAX_BYTES:
            os.replace(path, path.with_name(path.name + ".1"))
            return True
    except OSError:
        pass
    return False
