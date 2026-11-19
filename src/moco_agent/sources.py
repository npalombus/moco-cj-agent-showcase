"""County sources and their saved copies (design S3A, C3 and C4).

A source is one approved dataset, described by one file in config/sources/ (the planning
chat's; nothing about a source lives in code). A copy is one dated download of a source:
`<state_dir>/copies/<source name>/<UTC time>/` with rows.jsonl (only the fields the source
file lists, and its time field) and copy.json; a small file `current` names the copy in use.
Answers are counted from the current copy, never from the live site. The only address ever
contacted is the source file's `address`.
"""
import hashlib
import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = REPO / "config" / "sources"
COUNTY = "COUNTY_OPEN_DATA"
PAGE_SIZE = 5000
TIMEOUT_SECONDS = 60


class FetchFailed(Exception):
    """A fetch that did not make a new current copy. The message is the reason; it never
    holds a record."""


@dataclass(frozen=True)
class Copy:
    source_id: str
    folder: str
    fetched_at: str     # UTC, ISO 8601
    rows: int
    newest: str         # the newest record's time, as the service writes it
    fields: tuple
    sha256: str         # of rows.jsonl: the copy's fingerprint

    @property
    def day(self):
        """The date the copy was made (UTC)."""
        return date.fromisoformat(self.fetched_at[:10])

    @property
    def newest_day(self):
        return date.fromisoformat(self.newest[:10])


_TOP_KEYS = ("id", "data_class", "title", "publisher", "address", "page", "unit", "is_not",
             "time_field", "coverage_start", "floor", "fields")
_FIELD_KEYS = {"key": (), "age": ("usable", "bands"),
               "category": ("dimension", "wording", "values"),
               "flag": ("dimension", "yes_raw", "no_raw", "yes", "no")}
INVALID = {}       # file name -> {"id": the file's id or None, "reasons": [...]}: the last load
_LOGGED = set()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _sentences(value):
    """C57 point 2: a list of texts, none empty (an empty list holds none, and is fine)."""
    return isinstance(value, list) and all(_text(v) for v in value)


def problems(data):
    """C20: what is wrong with a source file's shape, as plain reasons; [] when it is fit to
    offer. C14: an interpreted field needs its coverage text and the file its line."""
    if not isinstance(data, dict):
        return ["the file is not one object"]
    found = [f"{key} is missing" for key in _TOP_KEYS if key not in data]
    for key in ("id", "data_class", "title", "address", "page", "time_field"):
        if key in data and not _text(data[key]):
            found.append(f"{key} is empty")
    unit = data.get("unit")
    if "unit" in data and not (isinstance(unit, dict) and _text(unit.get("one"))
                               and _text(unit.get("many"))):
        found.append("unit needs the words for one and for many")
    floor = data.get("floor")
    if "floor" in data and not (isinstance(floor, int) and not isinstance(floor, bool)
                                and floor >= 2):
        found.append("floor must be a whole number of at least 2")
    if "notes" in data and not _sentences(data["notes"]):  # S3A C57 point 2
        found.append("notes must be a list of sentences")
    fields = data.get("fields")
    if "fields" in data and not isinstance(fields, list):
        found.append("fields is not a list")
        fields = []
    interpreted = False
    for f in fields or []:
        name = f.get("name") if isinstance(f, dict) else None
        if not _text(name):
            found.append("a field has no name")
            continue
        kind = f.get("kind")
        if kind not in _FIELD_KEYS:
            found.append(f"field {name} has an unknown kind")
            continue
        found += [f"field {name} lacks {key}" for key in _FIELD_KEYS[kind] if key not in f]
        if "meaning" in f and not _text(f["meaning"]):  # S3A C57 point 2
            found.append(f"field {name} has an empty meaning")
        if "notes" in f and not _sentences(f["notes"]):
            found.append(f"field {name}: notes must be a list of sentences")
        if kind in ("category", "flag") and "dimension" in f and not _text(f["dimension"]):
            found.append(f"field {name} has an empty dimension")
        if kind == "category" and "values" in f:
            values = f["values"]
            labels = [v.get("label") if isinstance(v, dict) else v for v in values.values()] \
                if isinstance(values, dict) else None
            if not labels:
                found.append(f"field {name} lists no values")
            elif not all(_text(label) for label in labels):
                found.append(f"field {name} has an empty label")
        if kind == "flag" and not all(_text(f.get(k)) for k in ("yes", "no") if k in f):
            found.append(f"field {name} has an empty label")
        if f.get("interpreted"):
            interpreted = True
            if not _text(f.get("coverage")):
                found.append(f"field {name} is interpreted and has no coverage text")
    if interpreted and not _text(data.get("interpreted_line")):
        found.append("the file has an interpreted field and no interpreted_line")
    return found


def load_sources(folder=None):
    """Every config/sources/*.json (or the folder given) that is fit to offer, as {id: the
    file's dict}. C20: a file that cannot be read or fails `problems` is left out, the
    others still load; the reason is kept in INVALID and logged once."""
    folder = Path(DEFAULT_SOURCES if folder is None else folder)
    out = {}
    INVALID.clear()
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reasons = problems(data)
        except (OSError, ValueError) as e:
            data, reasons = None, [f"the file cannot be read ({type(e).__name__})"]
        if reasons:
            source_id = data.get("id") if isinstance(data, dict) else None
            INVALID[path.name] = {"id": source_id if isinstance(source_id, str) else None,
                                  "reasons": reasons}
            if str(path) not in _LOGGED:
                _LOGGED.add(str(path))
                logging.getLogger(__name__).warning(
                    "source file %s is not offered: %s", path.name, "; ".join(reasons))
            continue
        out[data["id"]] = data
    return out


def why_invalid(source_id):
    """After a load: the reasons the file with this id (or this file name) is not offered,
    else None."""
    for name, entry in INVALID.items():
        if source_id in (entry["id"], name, name[:-len(".json")]):
            return name, entry["reasons"]
    return None


def county_sources():
    """The sources county mode may count (C0): data class COUNTY_OPEN_DATA."""
    return {sid: s for sid, s in load_sources().items() if s.get("data_class") == COUNTY}


def name_of(source_id):
    """The folder name of a source's copies: its id after the colon."""
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(source_id).split(":", 1)[-1])
    # D10: a name of dots only (".", "..") would point at a folder above; never give one
    return name if name.strip(".") else "_" * max(1, len(name))


def _root(source_id, state_dir):
    return Path(state_dir) / "copies" / name_of(source_id)


def kept_fields(source):
    """The fields a copy keeps: every listed field, then the time field."""
    names = [f["name"] for f in source["fields"]]
    return names + ([source["time_field"]] if source["time_field"] not in names else [])


# ---- fetch ------------------------------------------------------------------------------------

def fetch(source_id, *, state_dir, transport=None, now=None):
    """Download every row of the source through its `address`, in pages ordered on the
    service's unique row id (so pages cannot overlap), check it against the last good copy,
    and only then make it current. Anything else raises FetchFailed and leaves the last
    good copy in use."""
    source = load_sources().get(source_id)
    if source is None:
        raise FetchFailed(f"no approved source file has the id {source_id}")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    get = transport or _get
    keep = kept_fields(source)
    rows = []
    while True:
        params = {"$select": ",".join(keep), "$order": ":id", "$limit": PAGE_SIZE,
                  "$offset": len(rows)}
        try:
            answer = get(source["address"], params=params)
        except OSError as e:  # a network error or a time-out
            raise FetchFailed(f"the service could not be reached ({type(e).__name__})") from None
        page = _rows_of(answer)
        rows += page
        if len(page) < PAGE_SIZE:
            break

    present = {key for row in rows for key in row}
    missing = [name for name in keep if name not in present]
    if missing:
        raise FetchFailed(f"the service's answer lacks the listed field(s) {', '.join(missing)}")
    time_field = source["time_field"]
    times = [row[time_field] for row in rows if isinstance(row.get(time_field), str)]
    newest = max(times) if times else ""
    last = latest(source_id, state_dir=state_dir)
    if last is not None:
        if (last.rows - len(rows)) * 100 > 2 * last.rows:
            raise FetchFailed(f"the service gave {len(rows):,} rows, more than 2 in 100 fewer "
                              f"than the last good copy's {last.rows:,}")
        if newest < last.newest:
            raise FetchFailed(f"the newest record ({newest[:10]}) is older than the last good "
                              f"copy's ({last.newest[:10]})")

    text = "".join(json.dumps({k: row[k] for k in keep if k in row}, ensure_ascii=False,
                              sort_keys=True) + "\n" for row in rows)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    root = _root(source_id, state_dir)
    stamp = f"{now:%Y%m%dT%H%M%SZ}"
    folder, n = root / stamp, 1
    while folder.exists():
        folder, n = root / f"{stamp}-{n}", n + 1
    folder.mkdir(parents=True)
    (folder / "rows.jsonl").write_text(text, encoding="utf-8")
    record = {"source_id": source_id, "fetched_at": now.isoformat().replace("+00:00", "Z"),
              "rows": len(rows), "newest": newest, "fields": keep, "sha256": sha,
              "address": source["address"]}
    (folder / "copy.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    pointer = root / "current.tmp"
    pointer.write_text(folder.name + "\n", encoding="utf-8")
    os.replace(pointer, root / "current")  # made current last, in one step
    return latest(source_id, state_dir=state_dir)


def _rows_of(answer):
    """The page of rows in a service's answer, or FetchFailed: an error status, a redirect,
    an error page or an error object is not a list of rows."""
    status = getattr(answer, "status_code", None)
    status = getattr(answer, "status", None) if status is None else status
    if status != 200:
        raise FetchFailed(f"the service answered with HTTP status {status}, not a list of rows")
    try:
        page = json.loads(answer.text)
    except (TypeError, ValueError):
        raise FetchFailed("the service's answer is not JSON (an error page?)") from None
    if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
        raise FetchFailed("the service's answer is not a list of rows")
    return page


class _Answer:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # a redirect is an answer that is not a list of rows (C4)


def _ssl_context():
    try:
        import truststore  # the system's certificates, as the model client uses
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def _get(url, params=None):
    """The real transport: one GET of `url` with `params`, no redirects followed."""
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    request = urllib.request.Request(full, headers={"Accept": "application/json",
                                                    "User-Agent": "moco-cj-agent/0.1"})
    opener = urllib.request.build_opener(_NoRedirect,
                                         urllib.request.HTTPSHandler(context=_ssl_context()))
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return _Answer(response.status, response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _Answer(e.code, "")


# ---- the current copy -------------------------------------------------------------------------

def latest(source_id, *, state_dir):
    """The current copy of the source, or None when there is none."""
    root = _root(source_id, state_dir)
    try:
        folder = root / (root / "current").read_text(encoding="utf-8").strip()
        data = json.loads((folder / "copy.json").read_text(encoding="utf-8"))
        return Copy(source_id=data["source_id"], folder=str(folder),
                    fetched_at=data["fetched_at"], rows=int(data["rows"]),
                    newest=data["newest"], fields=tuple(data["fields"]),
                    sha256=data["sha256"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def copy_rows(copy):
    """The rows of a copy, as a tuple of dicts (read once per copy)."""
    return _read_rows(copy.folder, copy.sha256)


@lru_cache(maxsize=4)
def _read_rows(folder, sha):  # ponytail: the sha keys the cache; a few copies at most
    lines = (Path(folder) / "rows.jsonl").read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines if line.strip())
