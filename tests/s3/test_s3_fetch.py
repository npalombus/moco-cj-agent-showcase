"""Copies: docs/S3A-DESIGN.md C4 (fetch, latest, the copy on disk, the checks, the `fetch`
command, NO_COPY) with C1's "Answers are computed from a saved copy" and C12's fetch
bullet ("paging, each failed check, an error page, a redirect; a failed fetch leaves the
last good copy in use; the fingerprint is in every record").

What this file covers
- fetch makes `<state_dir>/copies/<source name>/<UTC time>/` holding rows.jsonl (every row
  once, only the fields the source file lists) and copy.json (source id, time fetched,
  number of rows, newest record time, field list, sha256 of rows.jsonl), and a `current`
  file naming it; latest() gives it, and None before any copy.
- Paging: through the source's `address` only, in pages that cannot overlap (the fake
  service gives rows in a different order on every request unless they are ordered on a
  unique field, so overlapping pages lose rows), at least three pages when the service
  holds more than two pages of rows.
- Each failed check (a listed field missing; rows down by more than 2 in 100; the newest
  record older), a network error, a time-out, a redirect, an error page, an error object
  and an error status, on the first request or on a later page: FetchFailed with a reason,
  and the last good copy stays current. The edges: 2 in 100 fewer rows and the same newest
  record pass.
- A count is made from the current copy and touches no service; after a failed fetch it
  still uses the last good copy; its record holds the copy's sha256 and date.
- With no current copy a count ends the turn with NO_COPY and nothing is fetched.
- `python -m moco_agent fetch <source id>` (run in-process through __main__.main, with
  the fake service put in place of the network): prints the copy's date, its rows and its
  fingerprint; on a failure, the reason and a non-zero exit, with no traceback.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- The time field is kept in rows.jsonl although `fields` does not list it: the source file
  names it (`time_field`), and nothing could be counted by period without it.
- A field the service leaves out of a row (its value empty) may be missing, null or "" in
  rows.jsonl.
- copy.json's key names are not given: its values are looked for among its leaves. The
  folder's <UTC time> is checked by its digits (it starts 202611121500 for 15:00 UTC).
- The Copy object's attributes are not given: it is checked only to carry the sha256.
- "Every listed field is present in the service's answer" is read as: each listed field
  appears in at least one row (the service leaves a key out of a row when it is empty).
- NO_COPY is the turn's reason code (C4 calls it a fixed line, as A7's table names each
  fixed line by its code); its status is not given and not checked, beyond not ANSWERED.
- The fetch command's exit code on success is 0 and on a failure is not 0 (not given).
"""
import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from p1support import Step, deep_leaves, finish, has_leaf, mod, reachable_values
from s3support import (A_ID, COPY_DATE_RE, COPY_NOW, FAILURES, FIXTURE_SOURCES, Q_COUNT,
                       CountyEnv, FakeService, bulk_rows, check_county_reply, copy_folders,
                       count, current_folder, current_text, fixture_rows, read_copy_json,
                       read_copy_rows, row_id, rows_file_sha256, run_records, service_for,
                       source_id, source_json, use_sources, year)

LATER = COPY_NOW + timedelta(hours=1)


def sources_in_place(monkeypatch):
    """fetch and latest find the fixture source files through load_sources()."""
    use_sources(monkeypatch, FIXTURE_SOURCES)


def fetch(name, state_dir, service, now=COPY_NOW):
    return mod("sources").fetch(source_id(name), state_dir=Path(state_dir), transport=service,
                                now=now)


def latest(name, state_dir):
    return mod("sources").latest(source_id(name), state_dir=Path(state_dir))


def listed(name):
    src = source_json(name)
    return {f["name"] for f in src["fields"]} | {src["time_field"]}


def carries_sha(copy, sha):
    assert copy is not None
    found = {v.lower() for v in reachable_values(copy) if isinstance(v, str)}
    assert sha in found, "the Copy does not carry the sha256 of its rows.jsonl"


def replace_fetch(monkeypatch, replacement):
    """Put `replacement` in place of sources.fetch in every moco_agent module that holds it
    (so `from .sources import fetch` is covered too). Returns the real fetch."""
    real = mod("sources").fetch
    for name, module in list(sys.modules.items()):
        if (name == "moco_agent" or name.startswith("moco_agent.")) and \
                getattr(module, "fetch", None) is real:
            monkeypatch.setattr(module, "fetch", replacement)
    return real


def bulk_service(name="arrests_like", year=2026, **kw):
    """A service that makes 2 x (the first $limit) + 7 rows: at least three pages."""
    return FakeService(None, address=source_json(name)["address"],
                       make_rows=lambda n: bulk_rows(name, n, year=year), **kw)


# ---- the copy on disk ----------------------------------------------------------------------

def test_a_copy_is_a_folder_named_by_its_utc_time_and_made_current(tmp_path, monkeypatch):
    """C4: a folder <state_dir>/copies/<source name>/<UTC time>/ holding rows.jsonl and
    copy.json; a small file `current` names it."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, service_for("arrests_like"))
    (folder,) = copy_folders(tmp_path, "arrests_like")
    assert folder.parent == tmp_path / "copies" / "arrests_like"
    digits = "".join(ch for ch in folder.name if ch.isdigit())
    assert digits.startswith("202611121500"), f"not named by its UTC time: {folder.name}"
    assert (folder / "rows.jsonl").is_file() and (folder / "copy.json").is_file()
    assert current_folder(tmp_path, "arrests_like") == folder


@pytest.mark.parametrize("name", ["arrests_like", "coded_like"])
def test_rows_jsonl_holds_every_row_once_with_only_the_listed_fields(tmp_path, monkeypatch,
                                                                     name):
    """C4: rows.jsonl holds only the fields the source file lists: the field `data_class`
    every fixture row carries is dropped; every row is there once, with its values."""
    sources_in_place(monkeypatch)
    fetch(name, tmp_path, service_for(name))
    copied = read_copy_rows(current_folder(tmp_path, name))
    served = {row_id(r): r for r in fixture_rows(name)}
    assert len(copied) == len(served)
    assert sorted(row_id(r) for r in copied) == sorted(served)
    keep = listed(name)
    for row in copied:
        assert set(row) <= keep, f"fields not listed in the source file: {set(row) - keep}"
        original = served[row_id(row)]
        for key in keep:
            if key in original:
                assert row.get(key) == original[key], (row_id(row), key)
            else:
                assert row.get(key) in (None, ""), (row_id(row), key)


def test_copy_json_holds_what_c4_lists(tmp_path, monkeypatch):
    """C4: copy.json holds the source id, the time fetched, the number of rows, the newest
    record time, the field list and the sha256 of rows.jsonl."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, service_for("arrests_like"))
    folder = current_folder(tmp_path, "arrests_like")
    record = read_copy_json(folder)
    strings = [v for v in deep_leaves(record) if isinstance(v, str)]
    assert has_leaf(record, A_ID)
    assert has_leaf(record, 600), "the number of rows"
    assert has_leaf(record, rows_file_sha256(folder)), "the sha256 of rows.jsonl"
    assert any("2026-09-17" in s for s in strings), "the newest record time"
    assert any("2026-11-12" in s for s in strings), "the time fetched"
    for name in listed("arrests_like") - {"event_date_time"}:
        assert has_leaf(record, name), f"the field list lacks {name}"


def test_latest_is_none_before_any_copy_and_the_current_copy_after(tmp_path, monkeypatch):
    """C4: latest(source_id, state_dir) -> Copy | None."""
    sources_in_place(monkeypatch)
    assert latest("arrests_like", tmp_path) is None
    made = fetch("arrests_like", tmp_path, service_for("arrests_like"))
    sha = rows_file_sha256(current_folder(tmp_path, "arrests_like"))
    carries_sha(made, sha)
    carries_sha(latest("arrests_like", tmp_path), sha)
    assert latest("coded_like", tmp_path) is None


def test_a_newer_good_copy_becomes_current(tmp_path, monkeypatch):
    """C4: each fetch that passes its checks is made current; the older copy stays on disk."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, service_for("arrests_like"))
    first = current_folder(tmp_path, "arrests_like")
    newer = dict(fixture_rows("arrests_like")[0], id="FIXTURE-A-9001",
                 event_date_time="2026-09-18T10:00:00.000")
    fetch("arrests_like", tmp_path, service_for("arrests_like",
                                                 fixture_rows("arrests_like") + [newer]),
          now=LATER)
    second = current_folder(tmp_path, "arrests_like")
    assert second != first and len(copy_folders(tmp_path, "arrests_like")) == 2
    assert len(read_copy_rows(second)) == 601
    carries_sha(latest("arrests_like", tmp_path), rows_file_sha256(second))


# ---- paging (C4: in pages, ordered so that pages cannot overlap) ----------------------------

def test_every_row_comes_once_over_three_or_more_pages(tmp_path, monkeypatch):
    """C4: fetch downloads every row through `address`, in pages, ordered so that pages
    cannot overlap. The service holds more than two pages of rows (whatever page size the
    build asks for), and many rows share their exact time, so pages ordered on the time
    field alone would overlap and lose rows."""
    sources_in_place(monkeypatch)
    service = bulk_service()
    fetch("arrests_like", tmp_path, service)
    copied = read_copy_rows(current_folder(tmp_path, "arrests_like"))
    assert len(service.rows) >= 2007
    assert len(copied) == len(service.rows)
    assert sorted(row_id(r) for r in copied) == sorted(row_id(r) for r in service.rows)
    assert len(service.requests) >= 3, f"{len(service.requests)} requests for three pages"


def test_only_the_source_files_address_is_contacted(tmp_path, monkeypatch):
    """C4: the only address ever contacted is the source file's `address`."""
    sources_in_place(monkeypatch)
    for name in ("arrests_like", "coded_like"):
        service = service_for(name)
        fetch(name, tmp_path, service)
        assert service.requests
        assert {r["base"] for r in service.requests} == {source_json(name)["address"]}
        assert {r["method"] for r in service.requests} == {"GET"}


# ---- the checks: a failed fetch leaves the last good copy in use ----------------------------

def without_field(rows, key):
    return [{k: v for k, v in r.items() if k != key} for r in rows]


def without_newest(rows):
    newest = max(r["event_date_time"] for r in rows)
    return [r for r in rows if r["event_date_time"] != newest]


def fewer(rows, n):
    """`rows` less n rows that are not the newest record."""
    newest = max(r["event_date_time"] for r in rows)
    out, dropped = [], 0
    for r in rows:
        if dropped < n and r["event_date_time"] != newest:
            dropped += 1
            continue
        out.append(r)
    return out


BAD_ROWS = {
    "a listed field missing": lambda rows: without_field(rows, "gender"),
    "13 rows fewer in 600 (more than 2 in 100)": lambda rows: fewer(rows, 13),
    "the newest record older": without_newest,
}


def assert_last_good_copy_in_use(state_dir, folder, sha):
    assert current_folder(state_dir, "arrests_like") == folder, "`current` moved"
    assert rows_file_sha256(folder) == sha
    carries_sha(latest("arrests_like", state_dir), sha)


@pytest.mark.parametrize("case", list(BAD_ROWS))
def test_a_failed_check_raises_fetch_failed_and_keeps_the_last_good_copy(tmp_path,
                                                                         monkeypatch, case):
    """C4: a listed field missing, the row count down by more than 2 in 100, or the newest
    record older than the last good copy's: FetchFailed with the reason; `current` still
    names the last good copy."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, service_for("arrests_like"))
    good = current_folder(tmp_path, "arrests_like")
    sha = rows_file_sha256(good)
    sources = mod("sources")
    with pytest.raises(sources.FetchFailed) as caught:
        fetch("arrests_like", tmp_path,
              service_for("arrests_like", BAD_ROWS[case](fixture_rows("arrests_like"))),
              now=LATER)
    assert str(caught.value).strip(), "FetchFailed carries no reason"
    assert "FIXTURE-" not in str(caught.value)
    assert_last_good_copy_in_use(tmp_path, good, sha)


@pytest.mark.parametrize("mode", FAILURES)
def test_a_bad_answer_raises_fetch_failed_and_keeps_the_last_good_copy(tmp_path, monkeypatch,
                                                                       mode):
    """C4: a network error, or an answer that is not a list of rows (a redirect, an error
    page, an error status, an error object), leaves the last good copy in use and raises
    FetchFailed with the reason."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, service_for("arrests_like"))
    good = current_folder(tmp_path, "arrests_like")
    sha = rows_file_sha256(good)
    sources = mod("sources")
    with pytest.raises(sources.FetchFailed) as caught:
        fetch("arrests_like", tmp_path, service_for("arrests_like", fail={"all": mode}),
              now=LATER)
    assert str(caught.value).strip(), "FetchFailed carries no reason"
    assert_last_good_copy_in_use(tmp_path, good, sha)


@pytest.mark.parametrize("mode", ["error_page", "redirect", "network"])
def test_a_failure_on_a_later_page_keeps_the_last_good_copy(tmp_path, monkeypatch, mode):
    """C4: a failure on the second page (after a good first page) is a failed fetch too;
    nothing of it is made current."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, bulk_service())
    good = current_folder(tmp_path, "arrests_like")
    sha = rows_file_sha256(good)
    sources = mod("sources")
    service = bulk_service(fail={1: mode})
    with pytest.raises(sources.FetchFailed):
        fetch("arrests_like", tmp_path, service, now=LATER)
    assert len(service.requests) >= 2
    assert_last_good_copy_in_use(tmp_path, good, sha)


@pytest.mark.parametrize("mode", ["network", "error_page"])
def test_a_first_fetch_that_fails_leaves_no_copy(tmp_path, monkeypatch, mode):
    """C4: with no good copy before, a failed fetch makes none current."""
    sources_in_place(monkeypatch)
    sources = mod("sources")
    with pytest.raises(sources.FetchFailed):
        fetch("arrests_like", tmp_path, service_for("arrests_like", fail={"all": mode}))
    assert current_text(tmp_path, "arrests_like") is None
    assert latest("arrests_like", tmp_path) is None


def test_the_edges_of_the_checks_pass(tmp_path, monkeypatch):
    """C4 at its edges: 12 rows fewer in 600 is exactly 2 in 100 (not more), and the same
    newest record is not older: both copies are made current."""
    sources_in_place(monkeypatch)
    fetch("arrests_like", tmp_path, service_for("arrests_like"))
    rows = fewer(fixture_rows("arrests_like"), 12)
    assert len(rows) == 588
    fetch("arrests_like", tmp_path, service_for("arrests_like", rows), now=LATER)
    folder = current_folder(tmp_path, "arrests_like")
    assert len(read_copy_rows(folder)) == 588
    fetch("arrests_like", tmp_path, service_for("arrests_like", rows),
          now=LATER + timedelta(hours=1))
    assert current_folder(tmp_path, "arrests_like") != folder
    assert len(copy_folders(tmp_path, "arrests_like")) == 3


# ---- answers come from the saved copy (C1, C4) ---------------------------------------------

def one_count(env, spec=(year(2025),)):
    return env.ask(Q_COUNT, Step(count(A_ID, *spec)),
                   Step(finish("finding", "I counted {r1.count}.")))


def test_a_count_touches_no_service_while_answering(tmp_path, monkeypatch):
    """C1 and C4: answers are computed from a saved copy; nothing is fetched while
    answering (no request reaches the service, and sources.fetch is not called)."""
    env = CountyEnv(tmp_path, monkeypatch)
    service = env.services["arrests_like"]
    before = len(service.requests)
    calls = []
    real = replace_fetch(monkeypatch, lambda *a, **k: calls.append(a) or real(*a, **k))
    reply = one_count(env)
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith("I counted 240 arrest records in 2025.")
    assert len(service.requests) == before and calls == []


def test_after_a_failed_fetch_a_count_uses_the_last_good_copy(tmp_path, monkeypatch):
    """C4 and C12: a failed fetch leaves the last good copy in use: the count is the first
    copy's (240 in 2025), and its record holds the first copy's sha256."""
    env = CountyEnv(tmp_path, monkeypatch)
    sha = rows_file_sha256(current_folder(env.state_dir, "arrests_like"))
    sources = mod("sources")
    with pytest.raises(sources.FetchFailed):
        env.fetch("arrests_like", rows=fewer(fixture_rows("arrests_like"), 100), now=LATER)
    reply = one_count(env)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith("I counted 240 arrest records in 2025.")
    (record,) = run_records(reply, env.runs_dir)
    assert has_leaf(record, sha)


def test_the_fingerprint_and_date_of_the_copy_are_in_every_record(tmp_path, monkeypatch):
    """C5 "The record": every count saves the copy's fingerprint and date; C12: the
    fingerprint is in every record. Two counts of two sources, two records."""
    env = CountyEnv(tmp_path, monkeypatch, names=("arrests_like", "coded_like"))
    shas = {name: rows_file_sha256(current_folder(env.state_dir, name))
            for name in ("arrests_like", "coded_like")}
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025)), count("FIXTURE:coded_like", year(2025))),
                    Step(finish("finding", "I counted {r1.count}. I also counted {r2.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    records = run_records(reply, env.runs_dir)
    assert len(records) == 2
    for record, name in zip(records, ("arrests_like", "coded_like")):
        assert has_leaf(record, shas[name]), f"the record of {name} lacks its copy's sha256"
        other = shas["coded_like" if name == "arrests_like" else "arrests_like"]
        assert not has_leaf(record, other)
        strings = [v for v in deep_leaves(record) if isinstance(v, str)]
        assert any("2026-11-12" in s or "12 November 2026" in s for s in strings), \
            "the record lacks the copy's date"


# ---- NO_COPY (C4) ------------------------------------------------------------------------------

def test_with_no_current_copy_a_count_ends_the_turn_with_no_copy(tmp_path, monkeypatch):
    """C4: with no current copy, a count on that source ends the turn with the fixed line
    NO_COPY. Nothing is fetched while answering; nothing is counted."""
    env = CountyEnv(tmp_path, monkeypatch, copies=())
    calls = []
    replace_fetch(monkeypatch, lambda *a, **k: calls.append(a))
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    check_county_reply(reply)
    assert reply.reason_code == "NO_COPY", (reply.status, reply.reason_code, reply.text)
    assert reply.status != "ANSWERED"
    assert reply.run_ids == [] and calls == []
    assert "240" not in reply.text
    assert current_text(env.state_dir, "arrests_like") is None


# ---- the fetch command (C4) -------------------------------------------------------------------

def run_fetch_command(tmp_path, monkeypatch, capsys, service):
    """__main__.main(["fetch", <id>]) with MOCO_STATE_DIR in tmp_path, the fixture sources,
    and the fake service given to every call of sources.fetch."""
    state = Path(tmp_path) / "state"
    monkeypatch.setenv("MOCO_STATE_DIR", str(state))
    sources_in_place(monkeypatch)
    main = mod("__main__")
    real = mod("sources").fetch

    def with_fake_transport(source, *, state_dir, transport=None, now=None):
        return real(source, state_dir=state_dir, transport=service, now=now or COPY_NOW)

    replace_fetch(monkeypatch, with_fake_transport)
    try:
        code = main.main(["fetch", A_ID])
    except SystemExit as stop:
        code = stop.code
    out = capsys.readouterr()
    return (0 if code is None else code), out.out + out.err, state


def test_the_fetch_command_prints_the_date_rows_and_fingerprint(tmp_path, monkeypatch,
                                                                capsys):
    """C4: `python -m moco_agent fetch <source id>` runs fetch once and prints the copy's
    date, rows and fingerprint; the copy is made under MOCO_STATE_DIR."""
    code, text, state = run_fetch_command(tmp_path, monkeypatch, capsys,
                                          service_for("arrests_like"))
    assert code == 0, text
    folder = current_folder(state, "arrests_like")
    assert folder is not None, "no copy under MOCO_STATE_DIR"
    sha = rows_file_sha256(folder)
    assert re.search(COPY_DATE_RE, text), f"no copy date: {text!r}"
    assert re.search(r"(?<![0-9,])600(?![0-9])", text), f"no row count: {text!r}"
    assert sha[:8] in text.lower(), f"no fingerprint: {text!r}"
    assert "FIXTURE-" not in text


def test_the_fetch_command_prints_the_reason_it_failed(tmp_path, monkeypatch, capsys):
    """C4: on a failure the command prints the reason it failed (no traceback), and makes
    no copy current."""
    code, text, state = run_fetch_command(tmp_path, monkeypatch, capsys,
                                          service_for("arrests_like", fail={"all": "redirect"}))
    assert code != 0, text
    assert text.strip() and "Traceback" not in text, text
    assert current_text(state, "arrests_like") is None
