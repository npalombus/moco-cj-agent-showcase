"""Round 2 of Part D: docs/D-DESIGN.md D10, every point of "What the round's tests must show".
Brief briefs/GAPS-A-tests.md. Why: kit-log/raw/CHAT-BUILDS-check.txt (DEFECT 1, PROOF GAPS 1
and 3).

D10 point 1: "A source that fails never stops the others" holds for a failure of ANY kind,
for the `refresh` command and inside `serve` alike. Any other failure while fetching one
source is that source's failure; its line is
    <id>: FAILED (unexpected error (<the error's type name>)); the last good copy stays in use
(or `; there is no copy yet`); the command goes on to the next source; exit code 4; no
traceback. A failure while pruning after a good fetch does not make the fetch a failure: the
copy is used and the line is the line of a good fetch.
D10 point 2: pruning never leaves <state dir>/copies/. A source's folder name is its id after
the colon with every character other than letters, digits, `_`, `.` and `-` turned into `_`;
a name of dots only is written with `_` for each dot; an empty name is `_`.

How: as the Part D tests do it (tests/d/test_d_refresh_command.py, kit-log/raw/D-A-notes.txt).
The `refresh` command runs in a subprocess against a copy of the program in pytest's
temporary folder (dsupport.Sandbox), with the stand-ins of tests/d/standin.py, so nothing it
does can reach the project's var/ or runs/ (the s3 guard, loaded by tests/d/conftest.py,
checks both after every test, and the first test lists them before and after too). The two
stand-ins this round needs and standin.py does not have (a county service whose download is
cut off half way, and a `prune` that raises) are put in place by a few lines this file
writes into pytest's temporary folder (WRAPPER): they import standin.py, add the one
stand-in, and run standin.py's own main(), unchanged. run_once, fetch and prune are called
in this process with a `now` of the test's own, as tests/d/test_d_refresh_serve.py does.
All data is SYNTHETIC (the fixture sources of tests/s3).

Readings (each also in kit-log/raw/GAPS-A-notes.txt):
1. "A transport that raises http.client.IncompleteRead for one source": every request to
   that source's address raises it from inside the fake service, as the fake service's
   "network" failure raises ConnectionError (the `fetch` code is the program's own).
2. "The last good copy untouched and still current": every file under the source's copies
   folder is byte for byte what it was, and its `current` file names the same folder.
3. "No traceback on either stream": neither standard output nor standard error holds
   "Traceback", and the command raised nothing (the stand-in runner's report has no error).
4. "A failure while pruning (a stand-in that raises)": moco_agent.refresh.prune, the
   function D10 names, is replaced by one that notes the call and raises; tried with an
   OSError (PermissionError, what deleting a folder gives) and with an error of another
   kind (RuntimeError). A premise checks that the stand-in was called.
5. "The folder names for the ids": where the real `fetch` puts the copies of a source with
   that id (the one folder directly under <state dir>/copies/, holding `current` and the
   dated copy), and that `latest` finds the copy there. No function name is assumed.
6. `prune` is called as today: moco_agent.refresh.prune(source_id, state_dir).
7. "`prune` for X:.. deletes nothing in the state folder (a file and a folder put there by
   the test)": the state folder is laid out so that today's prune, pointed at the state
   folder itself (X:..) or at copies/ (X:. and X:), would delete a folder there: each holds
   a `current` file and more than three folders. The whole tree must be left as it was.
   X:. and X: are tried too (point 2 covers them; D10 names them among the folder names).
8. Beyond the list, from point 1 ("inside serve alike"): run_once with a failure while
   pruning gives "ok".
"""
import http.client
from datetime import datetime, timezone
from pathlib import Path

import pytest

import dsupport
from dsupport import (A_ID, A_NAME, A_ROWS, C_ID, C_NAME, C_ROWS, FAIL_EXIT, Sandbox, Services,
                      address_for, copy_names, make_copies, project_folders, service,
                      source_file, tree_bytes, write_files)
from p1support import mod
from s3support import (FakeService, copies_root, current_folder, current_text, fixture_rows,
                       source_json, use_sources)
from test_d_refresh_command import assert_lines, days_ago, ok

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)
CUT = "unexpected error (IncompleteRead)"          # D10 point 1, written out by hand
LAST_GOOD = "the last good copy stays in use"       # D4
NO_COPY = "there is no copy yet"                    # D4
A_ADDRESS, C_ADDRESS = source_json(A_NAME)["address"], source_json(C_NAME)["address"]
CUT_MODE = "cut_off"   # the fake service's failure this file adds (WRAPPER)

WRAPPER = '''"""Written by tests/d/test_d_round2.py into pytest's temporary folder. It adds one
stand-in to those of tests/d/standin.py and then runs standin.py's own main(), unchanged."""
import builtins
import http.client
from pathlib import Path

import s3support
import standin

PRUNE_ERROR = @PRUNE_ERROR@
PRUNE_CALLS = Path(@PRUNE_CALLS@)
_failure = s3support.FakeService._failure


def failure(self, mode, url):
    """The fake county service, with one more failure: a download cut off half way."""
    if mode == "@CUT_MODE@":
        raise http.client.IncompleteRead(b'[{"id": "FIXTURE-SYNTHETIC', 4096)
    return _failure(self, mode, url)


s3support.FakeService._failure = failure

if PRUNE_ERROR:
    import moco_agent.refresh as refresh

    def prune(*args, **kwargs):
        """A stand-in for prune that fails."""
        with PRUNE_CALLS.open("a", encoding="utf-8") as calls:
            calls.write("prune called\\n")
        raise getattr(builtins, PRUNE_ERROR)("SYNTHETIC stand-in: pruning failed")

    standin.replace_everywhere(refresh, "prune", prune)

standin.main()
'''


def refresh(box, monkeypatch, state, services, prune_error=None):
    """`python -m moco_agent refresh` against the sandbox, through WRAPPER."""
    calls = box.tmp / "prune-calls.txt"
    wrapper = box.tmp / "standin_round2.py"
    wrapper.write_text(WRAPPER.replace("@PRUNE_ERROR@", repr(prune_error))
                       .replace("@PRUNE_CALLS@", repr(str(calls)))
                       .replace("@CUT_MODE@", CUT_MODE), encoding="utf-8")
    monkeypatch.setattr(dsupport, "STANDIN", wrapper)
    return box.run("refresh", env={"MOCO_STATE_DIR": state}, services=services)


def prune_calls(box):
    path = box.tmp / "prune-calls.txt"
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def assert_no_traceback(result):
    assert "Traceback" not in result.stdout and "Traceback" not in result.stderr, \
        result.explain()
    assert result.report["error"] is None, result.explain()


# ==== point 1: the refresh command and a download cut off half way ============================

@pytest.mark.parametrize("had_copy", [True, False], ids=["with_a_copy", "no_copy_yet"])
@pytest.mark.parametrize("failing", ["first", "last"])
def test_a_download_cut_off_half_way_does_not_stop_the_refresh(tmp_path, monkeypatch, failing,
                                                                had_copy):
    """D10 point 1. One source's service raises http.client.IncompleteRead, the other
    answers. In id order FIXTURE:arrests_like is first and FIXTURE:coded_like is last; each
    is the failing one in turn. The failing source's line is exactly D10's, the other source
    is fetched and its line printed, the exit code is 4, no traceback on either stream; the
    failing source's last good copy is byte for byte what it was and still current (or it
    still has none). The real project's var/ and runs/ are listed before and after."""
    before = project_folders()
    box, state = Sandbox(tmp_path), tmp_path / "state"
    bad, good = (A_NAME, C_NAME) if failing == "first" else (C_NAME, A_NAME)
    bad_id = A_ID if bad == A_NAME else C_ID
    if had_copy:
        make_copies(monkeypatch, box.sources_dir, state, bad, days_ago(2))
        kept, current = tree_bytes(copies_root(state, bad)), current_text(state, bad)
    result = refresh(box, monkeypatch, state, [service(bad, fail=CUT_MODE), service(good)])
    assert_no_traceback(result)
    assert result.code == FAIL_EXIT, result.explain()
    failed = f"{bad_id}: FAILED ({CUT}); {LAST_GOOD if had_copy else NO_COPY}"
    good_line = ok(C_ID, C_ROWS, state, C_NAME) if good == C_NAME else \
        ok(A_ID, A_ROWS, state, A_NAME)
    assert_lines(result, *((failed, good_line) if failing == "first" else (good_line, failed)))
    assert service(good)["address"] in result.report["requests"], result.report["requests"]
    assert len(copy_names(state, good)) == 1
    if had_copy:
        assert tree_bytes(copies_root(state, bad)) == kept, "the last good copy changed"
        assert current_text(state, bad) == current, "the last good copy is no longer current"
    else:
        assert copy_names(state, bad) == []
    assert project_folders() == before, "the real project's var/ or runs/ changed"


# ==== point 1: run_once and the same failure ==================================================

def lone_source(tag):
    """The arrests fixture under an id and an address of its own (FIXTURE:<tag>), so that no
    other test makes the same id fail (the failure memory of D5)."""
    return source_file(A_NAME, sid=f"FIXTURE:{tag}", address=address_for(tag))


def cut_off(*args, **kwargs):
    raise http.client.IncompleteRead(b'[{"id": "FIXTURE-SYNTHETIC', 4096)


@pytest.mark.parametrize("failing", ["first", "last"])
def test_run_once_gives_unexpected_error_for_a_download_cut_off(tmp_path, monkeypatch, failing):
    """D10: run_once with the same failure gives the text `unexpected error (IncompleteRead)`
    for that source and "ok" for the other. The failing source is first in id order
    (FIXTURE:a_d10_cut, before FIXTURE:coded_like) or last (FIXTURE:z_d10_cut)."""
    lone = lone_source("a_d10_cut" if failing == "first" else "z_d10_cut")
    folder = write_files(tmp_path / "sources", {"lone.json": lone,
                                                "coded_like.json": source_file(C_NAME)})
    use_sources(monkeypatch, folder)
    services = Services({lone["address"]: cut_off,
                         C_ADDRESS: FakeService(fixture_rows(C_NAME), address=C_ADDRESS)})
    answer = mod("refresh").run_once(tmp_path / "state", NOW, 24, transport=services)
    assert answer == {lone["id"]: CUT, C_ID: "ok"}, answer
    assert lone["address"] in services.asked and C_ADDRESS in services.asked, services.asked


# ==== point 1: a failure while pruning =========================================================

@pytest.mark.parametrize("error", ["PermissionError", "RuntimeError"])
def test_a_failure_while_pruning_leaves_the_good_fetch(tmp_path, monkeypatch, error):
    """D10 point 1: prune is replaced by a stand-in that raises. The arrests source has three
    copies, so a fourth would be pruned. Both fetches are good: both lines are the lines of
    a good fetch, the exit code is 0, no traceback, and the new copy is current."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, days_ago(2, 3, 4))
    old = copy_names(state, A_NAME)
    result = refresh(box, monkeypatch, state, [service(A_NAME), service(C_NAME)],
                     prune_error=error)
    assert prune_calls(box), "premise: the stand-in for prune was not called"
    assert_no_traceback(result)
    assert result.code == 0, result.explain()
    assert_lines(result, ok(A_ID, A_ROWS, state, A_NAME), ok(C_ID, C_ROWS, state, C_NAME))
    assert current_folder(state, A_NAME).name not in old, "the new copy is not current"
    assert current_folder(state, C_NAME) is not None


@pytest.mark.parametrize("error", [PermissionError, RuntimeError], ids=lambda e: e.__name__)
def test_run_once_with_a_failure_while_pruning_gives_ok(tmp_path, monkeypatch, error):
    """D10 point 1, "inside serve alike" (beyond the list of what the tests must show):
    run_once with a prune that raises answers "ok" for both sources, and both copies are
    current."""
    folder = write_files(tmp_path / "sources", {"arrests_like.json": source_file(A_NAME),
                                                "coded_like.json": source_file(C_NAME)})
    use_sources(monkeypatch, folder)
    calls = []

    def prune(*args, **kwargs):
        calls.append(args)
        raise error("SYNTHETIC stand-in: pruning failed")

    monkeypatch.setattr(mod("refresh"), "prune", prune)
    services = Services({A_ADDRESS: FakeService(fixture_rows(A_NAME), address=A_ADDRESS),
                         C_ADDRESS: FakeService(fixture_rows(C_NAME), address=C_ADDRESS)})
    state = tmp_path / "state"
    answer = mod("refresh").run_once(state, NOW, 24, transport=services)
    assert calls, "premise: the stand-in for prune was not called"
    assert answer == {A_ID: "ok", C_ID: "ok"}, answer
    assert current_folder(state, A_NAME) is not None
    assert current_folder(state, C_NAME) is not None


# ==== point 2: folder names, and prune stays inside copies/ ==================================

FOLDER_NAMES = [("X:..", "__"), ("X:.", "_"), ("X:", "_"), ("X:a.b", "a.b")]   # D10, by hand


@pytest.mark.parametrize("sid, name", FOLDER_NAMES, ids=[s for s, _ in FOLDER_NAMES])
def test_the_folder_name_of_a_source(tmp_path, monkeypatch, sid, name):
    """D10 point 2: the copies of a source with this id go to <state dir>/copies/<name>/,
    the one folder there, with its `current` file and the dated copy; the state folder holds
    nothing else; latest() finds the copy."""
    tag = "d10-" + name.replace(".", "dot").replace("_", "under")
    folder = write_files(tmp_path / "sources",
                         {"x.json": source_file(A_NAME, sid=sid, address=address_for(tag))})
    state = tmp_path / "state"
    make_copies(monkeypatch, folder, state, A_NAME, [NOW], sid=sid, address=address_for(tag))
    in_state = sorted(p.name for p in state.iterdir())
    assert in_state == ["copies"], f"the state folder holds {in_state}"
    copies = state / "copies"
    in_copies = sorted(p.name for p in copies.iterdir())
    assert in_copies == [name], f"copies/ holds {in_copies}, not only {name!r}"
    root = copies / name
    current = (root / "current").read_text(encoding="utf-8").strip()
    dated = [p for p in root.iterdir() if p.is_dir()]
    assert [p.name for p in dated] == [current], (current, dated)
    found = mod("sources").latest(sid, state_dir=state)
    assert found is not None and Path(found.folder).parent == root, found


TRAP = {
    # The state folder: a `current` file and four folders.
    "agent.db": b"SYNTHETIC stand-in memory file\n",
    "agent.log": b"SYNTHETIC stand-in log line\n",
    "current": b"zz_kept\n",
    "keep/keep.txt": b"SYNTHETIC: keep me\n",
    "more/more.txt": b"SYNTHETIC: keep me too\n",
    "zz_kept/kept.txt": b"SYNTHETIC: the folder `current` names\n",
    # copies/: a `current` file and four folders (other sources' copies).
    "copies/current": b"zz_kept\n",
    "copies/aa_other/current": b"20261101T000000Z\n",
    "copies/aa_other/20261101T000000Z/rows.jsonl": b'{"data_class": "SYNTHETIC"}\n',
    "copies/bb_other/rows.txt": b"SYNTHETIC\n",
    "copies/cc_other/rows.txt": b"SYNTHETIC\n",
    "copies/zz_kept/rows.txt": b"SYNTHETIC\n",
}


def folders_under(folder):
    return sorted(str(p.relative_to(folder)) for p in Path(folder).rglob("*") if p.is_dir())


@pytest.mark.parametrize("sid", ["X:..", "X:.", "X:"])
def test_prune_never_leaves_the_copies_folder(tmp_path, sid):
    """D10 point 2: `prune` for a source whose id is X:.. (and X:. and X:) deletes nothing in
    the state folder: every file and folder the test put there is still there, byte for
    byte. The layout is one where today's prune, pointed at the state folder (X:..) or at
    copies/ (X:. and X:), would delete a folder (copies/ itself, or aa_other/)."""
    state = tmp_path / "state"
    for rel, data in TRAP.items():
        path = state / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    files, folders = tree_bytes(state), folders_under(state)
    mod("refresh").prune(sid, state)
    assert folders_under(state) == folders, "prune deleted a folder outside its own"
    assert tree_bytes(state) == files, "prune changed a file outside its own folder"
