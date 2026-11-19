"""Part S2: the Census Bureau's population figures for rates per resident (docs/S3S2-DESIGN.md
R1 and R8).

`fetch-census` downloads, for every year from config/census.json's first year that the Census
has published, the two tables (B01001, B03002) for Montgomery County from the American
Community Survey one-year estimates, and the Census's own labels of their lines. A year's
copy is kept only when every variable config/census.json lists is there, with a whole-number
estimate, a margin that is a whole number or one of the Census's "no margin" codes, and a
label that holds every word config/census.json expects; otherwise the year is refused, with
the variable named, and its last good copy stays in use. Copies live under
`<state dir>/census/<year>/<UTC time>/`, dated and fingerprinted like county copies, with a
small file `current` naming the copy in use.

The key (CENSUS_API_KEY) goes only into the request to the Census. It is never printed,
logged or saved: an error is reported by its kind, never by its text.
"""
import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from . import sources
from .counting import day_text

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config" / "census.json"
API = "https://api.census.gov/data"
KEEP = 3                 # copies kept per year after a good fetch (as Part D keeps county copies)
ONCE_EVERY = timedelta(hours=24)   # R8: Part D's refresh runs fetch-census once a day at most

log = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def settings(path=None):
    """config/census.json (the planning chat's)."""
    return json.loads(Path(CONFIG if path is None else path).read_text(encoding="utf-8"))


def variables(cfg):
    """Every Census variable a group adds up, once, in the file's order, with its words."""
    out = {}
    for groups in cfg["breakdowns"].values():
        for lines in groups.values():
            for v in lines:
                out.setdefault(v["variable"], v["label_has"])
    return out


def address(cfg, year):
    """The Census's address for one year of the survey (no key)."""
    return f"{API}/{year}/{cfg['survey']}"


def place_params(cfg):
    return {"for": f"county:{cfg['place']['county']}", "in": f"state:{cfg['place']['state']}"}


class _Refused(Exception):
    """A year whose answer cannot be kept. The message names the variable or the kind of
    failure; it never holds the key or the request."""


class _NotPublished(Exception):
    pass


def _status(answer):
    status = getattr(answer, "status_code", None)
    return getattr(answer, "status", None) if status is None else status


def _json(answer, what):
    if _status(answer) != 200:
        raise _Refused(f"the Census answered {what} with HTTP status {_status(answer)}")
    try:
        return json.loads(answer.text)
    except (TypeError, ValueError):
        raise _Refused(f"the Census's answer to {what} is not JSON (an error page?)") from None


def _whole(text):
    return isinstance(text, str) and text.isdigit()


def _fetch_year(cfg, year, key, get):
    """({table: [names, values]}, {variable: label}) for one year, checked; or _Refused /
    _NotPublished."""
    base, place = address(cfg, year), place_params(cfg)
    tables, labels = {}, {}
    for i, table in enumerate(cfg["tables"]):
        answer = get(base, params={"get": f"group({table})", **place, "key": key})
        if i == 0 and _status(answer) == 404:
            raise _NotPublished()
        data = _json(answer, f"table {table}")
        if not (isinstance(data, list) and len(data) == 2 and all(isinstance(x, list) for x in data)
                and len(data[0]) == len(data[1]) and data[0]):
            raise _Refused(f"the Census's answer for table {table} is not one line of figures")
        cells = dict(zip(data[0], data[1]))
        if (cells.get("state"), cells.get("county")) != (cfg["place"]["state"],
                                                         cfg["place"]["county"]):
            raise _Refused(f"the Census's answer for table {table} is not for "
                           f"{cfg['place']['name']}")
        tables[table] = data
        named = _json(get(f"{base}/groups/{table}.json"), f"the labels of table {table}")
        if not (isinstance(named, dict) and isinstance(named.get("variables"), dict)):
            raise _Refused(f"the Census's labels of table {table} are not a list of variables")
        labels.update({name: v.get("label") for name, v in named["variables"].items()
                       if isinstance(v, dict)})
    cells = {name: value for names, row in tables.values() for name, value in zip(names, row)}
    kept = {}
    for var, words in variables(cfg).items():
        est, moe, label = cells.get(var + "E"), cells.get(var + "M"), labels.get(var + "E")
        if not _whole(est):
            raise _Refused(f"{var} has no whole-number estimate")
        if not (_whole(moe) or moe in cfg["no_margin_codes"]):
            raise _Refused(f"{var} has a margin of error the agent cannot read")
        if not isinstance(label, str):
            raise _Refused(f"the Census gives no label for {var}")
        lacking = [w for w in words if w not in label]   # capitals count
        if lacking:
            raise _Refused(f'the label of {var} does not hold "{lacking[0]}" (the Census '
                           f'calls it "{label}")')
        kept[var] = label
    return tables, kept


def _root(state_dir, year):
    return Path(state_dir) / "census" / str(int(year))


def _save(state_dir, cfg, year, tables, labels, now):
    """The year's dated copy, made current last, in one step."""
    text = json.dumps({t: tables[t] for t in sorted(tables)}, ensure_ascii=False) + "\n"
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    root = _root(state_dir, year)
    stamp = f"{now:%Y%m%dT%H%M%SZ}"
    folder, n = root / stamp, 1
    while folder.exists():
        folder, n = root / f"{stamp}-{n}", n + 1
    folder.mkdir(parents=True)
    (folder / "tables.json").write_text(text, encoding="utf-8")
    (folder / "labels.json").write_text(json.dumps(labels, indent=1) + "\n", encoding="utf-8")
    record = {"year": year, "survey": cfg["survey"], "place": cfg["place"],
              "tables": sorted(tables), "address": address(cfg, year),
              "fetched_at": now.isoformat().replace("+00:00", "Z"), "sha256": sha}
    (folder / "copy.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    pointer = root / "current.tmp"
    pointer.write_text(folder.name + "\n", encoding="utf-8")
    os.replace(pointer, root / "current")
    return record


def _prune(state_dir, year, keep=KEEP):
    """The dated folders of one year beyond the newest `keep`; never the current one, never
    outside <state dir>/census/<year>/."""
    root = _root(state_dir, year)
    if root.resolve().parent != (Path(state_dir) / "census").resolve():
        return
    try:
        current = (root / "current").read_text(encoding="utf-8").strip()
        folders = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return
    for folder in folders[:-keep]:
        if folder.name != current:
            shutil.rmtree(folder, ignore_errors=True)


def fetch_all(state_dir, key, *, get=None, now=None, out=print, cfg=None):
    """R8: every year from the first year to last year (the Census publishes a year's one-year
    estimates late in the following year). One line per year. True when no year that the
    Census has published was refused."""
    cfg = cfg or settings()
    get = get or sources._get
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    good = True
    out(f"CENSUS: American Community Survey one-year estimates ({cfg['survey']}), "
        f"{cfg['place']['name']}, tables {' and '.join(cfg['tables'])}.")
    for year in range(int(cfg["first_year"]), now.year):
        had = latest(state_dir, year) is not None
        try:
            tables, labels = _fetch_year(cfg, year, key, get)
            record = _save(state_dir, cfg, year, tables, labels, now)
        except _NotPublished:
            out(f"{year}: not published by the Census yet.")
            continue
        except _Refused as e:
            reason = str(e)
        except OSError as e:  # a network error, a time-out, or the copy could not be written
            reason = f"the Census could not be reached or the copy not saved ({type(e).__name__})"
        except Exception as e:  # never the error's text: it could hold the request
            reason = f"unexpected error ({type(e).__name__})"
        else:
            try:
                _prune(state_dir, year)
            except Exception as e:
                log.warning("census: %s could not be pruned (%s)", year, type(e).__name__)
            out(f"{year}: copy of {day_text(datetime.fromisoformat(record['fetched_at'][:10]))}"
                f", sha256:{record['sha256'][:12]}")
            continue
        good = False
        out(f"{year}: REFUSED: {reason}; " + ("the last good copy stays in use." if had
                                              else "there is no copy of this year yet."))
    out(f"FOLDER: {Path(state_dir) / 'census'}")
    return good


def refresh_due(state_dir, key, now=None, out=print, get=None):
    """R8: Part D's refresh runs fetch-census too, at most once a day (the time of the last try
    is kept in <state dir>/census/last_try). None when it was not due; else fetch_all's answer."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    marker = Path(state_dir) / "census" / "last_try"
    try:
        last = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
        if now - last < ONCE_EVERY:
            return None
    except (OSError, ValueError):
        pass
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(now.isoformat() + "\n", encoding="utf-8")
    return fetch_all(state_dir, key, get=get, now=now, out=out)


# ---- the copy in use ---------------------------------------------------------------------------

def latest(state_dir, year, cfg=None):
    """The current copy of one year: {"year", "fetched_at", "sha256", "values": {variable:
    (estimate, margin or None)}}, or None when there is none (or it lacks a variable)."""
    cfg = cfg or settings()
    root = _root(state_dir, year)
    try:
        folder = root / (root / "current").read_text(encoding="utf-8").strip()
        record = json.loads((folder / "copy.json").read_text(encoding="utf-8"))
        tables = json.loads((folder / "tables.json").read_text(encoding="utf-8"))
        cells = {n: v for names, row in tables.values() for n, v in zip(names, row)}
        values = {}
        for var in variables(cfg):
            est, moe = cells[var + "E"], cells[var + "M"]
            values[var] = (int(est), None if moe in cfg["no_margin_codes"] else int(moe))
        return {"year": int(year), "fetched_at": record["fetched_at"],
                "sha256": record["sha256"], "values": values}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
