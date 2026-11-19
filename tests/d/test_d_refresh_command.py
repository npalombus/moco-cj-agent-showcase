"""D4 (docs/D-DESIGN.md): `python -m moco_agent refresh` fetches every county source whose
file in config/sources/ is valid (C20), one after the other, in the order of their ids, with
the same code `fetch` uses, and prints one line per source:

    <source id>: <rows> rows, copy of <day>, sha256:<first 12 characters>
    <source id>: FAILED (<what fetch would say>); the last good copy stays in use
    <source id>: FAILED (<what fetch would say>); there is no copy yet

A failing source never stops the others and its last good copy is left exactly as it was.
Exit 0 when every source succeeded, else the code `fetch` gives for a failed fetch (4). It
works whatever MOCO_DATA is. After a successful fetch the source's copies beyond the newest
three are deleted (the whole dated folder); `fetch` deletes nothing; nothing outside
<state dir>/copies/ is ever deleted.

D8: with the fixture sources and a fake transport: every valid source fetched in id order;
each of the three lines exactly; one failing source does not stop the next; the failed
source's last copy is byte for byte what it was; the exit codes; an invalid source file is
left out; four copies become three and the newest three stay; `fetch` prunes nothing.

How: the command runs against a copy of the program whose config/sources/ holds the two
fixture files, named so that file order is not id order (dsupport.fixture_files); the fake
county service (s3support.FakeService) answers in the subprocess (tests/d/standin.py). The
copies a test needs beforehand are made in this process by the real sources.fetch, days
before the real clock. The reason in a FAILED line is written out by hand from what today's
fetch says for that failure (it raises FetchFailed with it; `fetch` prints it).

Readings (kit-log/raw/D-A-notes.txt): standard output holds the source lines and nothing else;
"<what fetch would say>" is the reason FetchFailed carries; the day is accepted in the three
forms the stage 3 tests accept.
"""
import re
from datetime import timedelta

import pytest

from dsupport import (A_ID, A_NAME, A_ROWS, C_ID, C_NAME, C_ROWS, FAIL_EXIT, Sandbox,
                      address_for, copy_names, files_under, fixture_files, make_copies,
                      ok_line_re, project_folders, service, source_file, tree_bytes, utc_now)
from s3support import copies_root, current_folder

REDIRECT = "the service answered with HTTP status 302, not a list of rows"
ERROR_PAGE = "the service's answer is not JSON (an error page?)"
NETWORK = "the service could not be reached (ConnectionError)"
BROKEN_ID = "FIXTURE:broken_like"


def refresh(box, state, services, **env):
    return box.run("refresh", env=dict({"MOCO_STATE_DIR": state}, **env), services=services)


def both_ok():
    return [service(A_NAME), service(C_NAME)]


def days_ago(*days):
    """Times the given numbers of days before the real clock, oldest first."""
    now = utc_now()
    return [now - timedelta(days=d) for d in sorted(days, reverse=True)]


def assert_lines(result, *expected):
    """Standard output is exactly these lines; each is a string or a compiled regex."""
    assert len(result.lines) == len(expected), result.explain()
    for line, want in zip(result.lines, expected):
        if isinstance(want, re.Pattern):
            assert want.fullmatch(line), f"{line!r}\ndoes not match\n{want.pattern}"
        else:
            assert line == want, f"{line!r}\n!=\n{want!r}"


def ok(sid, rows, state, name):
    return re.compile(ok_line_re(sid, rows, state, name))


def test_every_valid_source_is_fetched_in_id_order_with_one_line_each(tmp_path):
    """Two sources, no copy before: both fetched, the arrests one (first by id, second by
    file name) entirely before the coded one; one line each, exactly; exit 0. Nothing in
    the project's var or runs; the real project's var/ and runs/ are listed before and
    after."""
    before = project_folders()
    box, state = Sandbox(tmp_path), tmp_path / "state"
    result = refresh(box, state, both_ok())
    assert result.code == 0, result.explain()
    assert_lines(result, ok(A_ID, A_ROWS, state, A_NAME), ok(C_ID, C_ROWS, state, C_NAME))
    asked = result.report["requests"]
    a_address, c_address = service(A_NAME)["address"], service(C_NAME)["address"]
    assert set(asked) == {a_address, c_address}, asked
    last_a = max(i for i, address in enumerate(asked) if address == a_address)
    assert last_a < asked.index(c_address), f"not one after the other in id order: {asked}"
    assert files_under(box.var) == [] and files_under(box.runs) == []
    assert project_folders() == before, "the real project's var/ or runs/ changed"


@pytest.mark.parametrize("failing", ["arrests_first", "coded_last"])
def test_a_failing_source_does_not_stop_the_others(tmp_path, failing):
    """One source fails and has no copy yet: its line says so with fetch's reason, the other
    is still fetched, and the exit code is 4."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    if failing == "arrests_first":
        result = refresh(box, state, [service(A_NAME, fail="redirect"), service(C_NAME)])
        assert result.code == FAIL_EXIT, result.explain()
        assert_lines(result, f"{A_ID}: FAILED ({REDIRECT}); there is no copy yet",
                     ok(C_ID, C_ROWS, state, C_NAME))
        assert copy_names(state, A_NAME) == [] and len(copy_names(state, C_NAME)) == 1
    else:
        result = refresh(box, state, [service(A_NAME), service(C_NAME, fail="error_page")])
        assert result.code == FAIL_EXIT, result.explain()
        assert_lines(result, ok(A_ID, A_ROWS, state, A_NAME),
                     f"{C_ID}: FAILED ({ERROR_PAGE}); there is no copy yet")
        assert len(copy_names(state, A_NAME)) == 1 and copy_names(state, C_NAME) == []


def test_a_failed_source_keeps_its_last_good_copy_byte_for_byte(tmp_path, monkeypatch):
    """A source with a copy fails (the network): its line says the last good copy stays in
    use, and every file of its copies is byte for byte what it was; the next source is
    fetched; exit 4."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, days_ago(2))
    kept = tree_bytes(copies_root(state, A_NAME))
    result = refresh(box, state, [service(A_NAME, fail="network"), service(C_NAME)])
    assert result.code == FAIL_EXIT, result.explain()
    assert_lines(result, f"{A_ID}: FAILED ({NETWORK}); the last good copy stays in use",
                 ok(C_ID, C_ROWS, state, C_NAME))
    assert tree_bytes(copies_root(state, A_NAME)) == kept, "the last good copy changed"


def test_an_invalid_source_file_is_left_out(tmp_path):
    """A third source file that fails its check (no title) gets no line and no request,
    although its service would answer; the valid two are fetched; exit 0."""
    broken = source_file(A_NAME, sid=BROKEN_ID, address=address_for("broken-like"),
                         drop=("title",))
    box = Sandbox(tmp_path, sources=fixture_files(**{"b_broken.json": broken}))
    state = tmp_path / "state"
    result = refresh(box, state, both_ok() + [service(A_NAME, address=address_for("broken-like"))])
    assert result.code == 0, result.explain()
    assert_lines(result, ok(A_ID, A_ROWS, state, A_NAME), ok(C_ID, C_ROWS, state, C_NAME))
    assert address_for("broken-like") not in result.report["requests"]
    assert not copies_root(state, "broken_like").exists()


@pytest.mark.parametrize("before", [1, 3, 4])
def test_copies_beyond_the_newest_three_are_deleted(tmp_path, monkeypatch, before):
    """After a successful fetch the source keeps its newest three copies: 1 + 1 = 2 stay,
    3 + 1 (four) become three, 4 + 1 become three. The new copy is current; each copy
    deleted is gone as a whole folder; the newest older copies stay."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, days_ago(*range(1, before + 1)))
    old = copy_names(state, A_NAME)
    assert len(old) == before
    result = refresh(box, state, both_ok())
    assert result.code == 0, result.explain()
    now = copy_names(state, A_NAME)
    new = [name for name in now if name not in old]
    assert len(new) == 1, (old, now)
    assert now == old[-(min(before + 1, 3) - 1):] + new, (old, now)
    assert current_folder(state, A_NAME).name == new[0]
    for gone in old[:max(0, before - 2)]:
        assert not (copies_root(state, A_NAME) / gone).exists(), f"{gone} is still there"


def test_a_failed_source_is_not_pruned(tmp_path, monkeypatch):
    """A source with four copies that fails keeps all four, byte for byte."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, days_ago(1, 2, 3, 4))
    kept = tree_bytes(copies_root(state, A_NAME))
    result = refresh(box, state, [service(A_NAME, fail="redirect"), service(C_NAME)])
    assert result.code == FAIL_EXIT, result.explain()
    assert result.lines[0] == f"{A_ID}: FAILED ({REDIRECT}); the last good copy stays in use"
    assert tree_bytes(copies_root(state, A_NAME)) == kept


def test_nothing_outside_the_copies_folder_is_deleted(tmp_path, monkeypatch):
    """Pruning four copies to three leaves every file outside <state dir>/copies/ as it
    was: the memory file, the log file and a folder of the state dir's own."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, days_ago(1, 2, 3))
    (state / "agent.db").write_bytes(b"SYNTHETIC stand-in memory file\n")
    (state / "agent.log").write_text("SYNTHETIC stand-in log line\n", encoding="utf-8")
    (state / "keep").mkdir()
    (state / "keep" / "keep.txt").write_text("SYNTHETIC: keep me\n", encoding="utf-8")
    outside = {path: data for path, data in tree_bytes(state).items()
               if not path.startswith("copies")}
    result = refresh(box, state, both_ok())
    assert result.code == 0, result.explain()
    assert len(copy_names(state, A_NAME)) == 3, "premise: a copy was pruned"
    assert {path: data for path, data in tree_bytes(state).items()
            if not path.startswith("copies")} == outside


def test_fetch_prunes_nothing(tmp_path, monkeypatch):
    """After refresh has kept three copies, `fetch` adds a fourth and deletes nothing."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, days_ago(1, 2, 3))
    first = refresh(box, state, both_ok())
    assert first.code == 0, first.explain()
    three = copy_names(state, A_NAME)
    assert len(three) == 3
    fetched = box.run("fetch", A_ID, env={"MOCO_STATE_DIR": state}, services=both_ok())
    assert fetched.code == 0, fetched.explain()
    now = copy_names(state, A_NAME)
    assert len(now) == 4 and now[:3] == three, (three, now)


@pytest.mark.parametrize("data", ["synthetic", "county"])
def test_refresh_works_whatever_moco_data_is(tmp_path, data):
    box, state = Sandbox(tmp_path), tmp_path / "state"
    result = refresh(box, state, both_ok(), MOCO_DATA=data)
    assert result.code == 0, result.explain()
    assert_lines(result, ok(A_ID, A_ROWS, state, A_NAME), ok(C_ID, C_ROWS, state, C_NAME))
