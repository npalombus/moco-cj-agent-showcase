"""The engine: docs/S3S-DESIGN.md S1 (ENGINE_MISSING, ENGINE_FAILED: they end the turn with a
fixed line and are logged with the R message, never shown to the user, never given to the
model), S2 (`Rscript analysis_r/<kind>.R <job folder>` as a process with a list of arguments,
no shell, 60 seconds at most), S8 (MOCO_RSCRIPT, default `Rscript`; `python -m moco_agent
check-engine` prints the R version and whether each package loads), S9 ("R is started without
a shell and with a time limit; an R error never reaches the user").

How a start is seen: subprocess.run and subprocess.Popen are wrapped (they call through to
the real ones) and every start is recorded with its arguments, `shell` and the time limit
given to run, communicate or wait. The overrun uses a stand-in that sleeps and a patched
limit: the wrapper records the 60 seconds asked for and passes 1 second instead.

Stand-ins for Rscript are small /bin/sh scripts in tmp_path, named by MOCO_RSCRIPT (given
both as a setting and in the environment, since the build may read either). A stand-in hands
every call that is not an analysis script (`*.R`) to the real Rscript, so a build that checks
R or its packages first still finds them; only the analysis itself fails.

READINGS: the turn ends with status ERROR and reason_code the error's name; the fixed line's
words are not given (QUESTIONS.md, 10), so the tests check it is the same for every cause of
one code and holds nothing of R's message. A missing R package (the other half of
ENGINE_MISSING) is not tested: how the build finds it is not said. What check-engine does
when R is missing is not said either.
"""
import json
import logging
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest

import s3ssupport as T
from p1support import Step, finish, mod
from s3sagent import (MAIN, Q_TREND, StatsEnv, analyze_case, answered, ask_case, job_folders,
                      slot_text)

MARK = "zqx-R-ERROR-MARKER-7"


class Starts:
    """Every process start of the turn: {"via", "args", "shell", "timeout"}."""

    def __init__(self, monkeypatch, limit=None):
        self.calls = []
        real_run, real_popen = subprocess.run, subprocess.Popen
        starts = self

        def run(*args, **kwargs):
            entry = {"via": "run", "args": args[0] if args else kwargs.get("args"),
                     "shell": kwargs.get("shell", False), "timeout": kwargs.get("timeout")}
            starts.calls.append(entry)
            if limit is not None and kwargs.get("timeout") is not None:
                kwargs["timeout"] = limit
            return real_run(*args, **kwargs)

        class Popen(real_popen):
            def __init__(self, *args, **kwargs):
                self._entry = {"via": "Popen", "args": args[0] if args else kwargs.get("args"),
                               "shell": kwargs.get("shell", False), "timeout": None}
                starts.calls.append(self._entry)
                super().__init__(*args, **kwargs)

            def communicate(self, input=None, timeout=None):
                if timeout is not None:
                    self._entry["timeout"] = self._entry["timeout"] or timeout
                    if limit is not None:
                        timeout = limit
                return super().communicate(input, timeout)

            def wait(self, timeout=None):
                if timeout is not None:
                    self._entry["timeout"] = self._entry["timeout"] or timeout
                    if limit is not None:
                        timeout = limit
                return super().wait(timeout)

        monkeypatch.setattr(subprocess, "run", run)
        monkeypatch.setattr(subprocess, "Popen", Popen)

    def analyses(self):
        def words(args):
            return [args] if isinstance(args, (str, bytes)) else [str(a) for a in args or []]
        return [c for c in self.calls if any("analysis_r" in w for w in words(c["args"]))]


def _png(path):
    raw = b"\x00\xff\xff\xff"
    body = (T.PNG_SIGNATURE + _chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00")
            + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b""))
    path.write_bytes(body)
    return path


def _chunk(kind, data):
    return (len(data).to_bytes(4, "big") + kind + data
            + zlib.crc32(kind + data).to_bytes(4, "big"))


def stand_in(tmp_path, on_analysis):
    """An executable stand-in for Rscript: an analysis script (`*.R`) runs `on_analysis`
    (sh; $last is the job folder); anything else goes to the real Rscript."""
    real = shutil.which("Rscript") or "Rscript"
    path = tmp_path / "bin" / "Rscript"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"""#!/bin/sh
last=""
for a in "$@"; do last="$a"; done
case "$1" in
  *.R) {on_analysis} ;;
  *) exec "{real}" "$@" ;;
esac
""", encoding="utf-8")
    path.chmod(0o755)
    return path


def engine_env(tmp_path, monkeypatch, rscript):
    monkeypatch.setenv("MOCO_RSCRIPT", str(rscript))
    return StatsEnv(tmp_path, monkeypatch, MOCO_RSCRIPT=str(rscript))


def _turn_json(env, reply):
    path = Path(env.runs_dir) / str(reply.turn_id) / "turn.json"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def check_engine_end(env, reply, code, marker=MARK):
    """The turn ended with the fixed line of `code`; nothing of R's message reached the
    reply, the model, memory or turn.json; the model was not called again."""
    assert (reply.status, reply.reason_code) == ("ERROR", code), \
        (reply.status, reply.reason_code, reply.text)
    assert marker not in reply.text
    assert len(env.model.calls) == 1, "the turn ends at the analyze call"
    for call in env.model.calls:
        assert marker not in json.dumps(call["messages"])
    assert marker not in json.dumps(env.stored_turns(), default=str)
    assert marker not in _turn_json(env, reply)
    assert "Error in" not in reply.text and "Traceback" not in reply.text
    return reply.text


@pytest.mark.needs_r
def test_r_is_started_with_a_list_of_arguments_and_a_60_second_limit(tmp_path, monkeypatch):
    starts = Starts(monkeypatch)
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "trend_all"))
    found = starts.analyses()
    assert found, f"no start of analysis_r/... was seen: {starts.calls}"
    for c in found:
        assert isinstance(c["args"], (list, tuple)), f"a shell string: {c['args']!r}"
        assert not c["shell"], c
    args = [str(a) for a in found[0]["args"]]
    assert Path(args[0]).name == "Rscript", args
    assert args[1].replace("\\", "/").endswith("analysis_r/trend.R"), args
    assert len(args) == 3 and (Path(args[2]) / "job.json").is_file(), args
    assert Path(args[2]) in job_folders(env)
    assert any(c["timeout"] == 60 for c in found), [c["timeout"] for c in found]


@pytest.mark.needs_r
def test_moco_rscript_names_the_rscript_used(tmp_path, monkeypatch):
    """S8: MOCO_RSCRIPT is the Rscript started (here a stand-in that passes through)."""
    rscript = tmp_path / "bin" / "Rscript"
    rscript.parent.mkdir()
    real = shutil.which("Rscript")
    rscript.write_text(f'#!/bin/sh\nexec "{real}" "$@"\n', encoding="utf-8")
    rscript.chmod(0o755)
    starts = Starts(monkeypatch)
    env = engine_env(tmp_path, monkeypatch, rscript)
    answered(ask_case(env, "timing"))
    assert str(starts.analyses()[0]["args"][0]) == str(rscript)


def test_engine_missing_when_moco_rscript_points_nowhere(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    env = engine_env(tmp_path, monkeypatch, tmp_path / "no-such-folder" / "Rscript")
    reply = ask_case(env, "trend_all")
    check_engine_end(env, reply, "ENGINE_MISSING")
    other = engine_env(tmp_path / "again", monkeypatch, tmp_path / "nowhere" / "Rscript")
    assert ask_case(other, "timing").text == reply.text, "a fixed line"


@pytest.mark.needs_r
def test_engine_failed_for_an_r_error(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    rscript = stand_in(tmp_path, f'echo "Error in glm.nb(f): {MARK}" >&2; exit 1')
    env = engine_env(tmp_path, monkeypatch, rscript)
    reply = ask_case(env, "trend_all")
    check_engine_end(env, reply, "ENGINE_FAILED")
    assert any(MARK in r.getMessage() for r in caplog.records), \
        "S1: ENGINE_FAILED is logged with the R message"


@pytest.mark.needs_r
def test_engine_failed_for_an_overrun(tmp_path, monkeypatch, caplog):
    """S2's 60 seconds, patched to 1 second: a stand-in that sleeps 5 seconds is stopped."""
    caplog.set_level(logging.DEBUG)
    rscript = stand_in(tmp_path, "exec sleep 5")
    starts = Starts(monkeypatch, limit=1)
    env = engine_env(tmp_path, monkeypatch, rscript)
    reply = ask_case(env, "trend_all")
    check_engine_end(env, reply, "ENGINE_FAILED")
    assert any(c["timeout"] == 60 for c in starts.analyses()), starts.calls
    assert any(r.name.startswith("moco_agent") for r in caplog.records), "the overrun is logged"


@pytest.mark.needs_r
def test_engine_failed_for_a_result_in_the_wrong_shape(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    png = _png(tmp_path / "small.png")
    rscript = stand_in(tmp_path, f"""echo '{{"nonsense": "{MARK}"}}' > "$last/result.json"; """
                                 f"""cp "{png}" "$last/chart.png"; exit 0""")
    env = engine_env(tmp_path, monkeypatch, rscript)
    reply = ask_case(env, "trend_all")
    check_engine_end(env, reply, "ENGINE_FAILED")


@pytest.mark.needs_r
def test_engine_failed_is_one_fixed_line_for_every_cause(tmp_path, monkeypatch):
    texts = []
    for i, body in enumerate([f'echo "{MARK}" >&2; exit 2', "exec sleep 5",
                              f"""echo '[1, 2, 3]' > "$last/result.json"; exit 0"""]):
        folder = tmp_path / f"case{i}"
        folder.mkdir()
        if i == 1:
            Starts(monkeypatch, limit=1)
        env = engine_env(folder, monkeypatch, stand_in(folder, body))
        reply = ask_case(env, "timing")
        texts.append(check_engine_end(env, reply, "ENGINE_FAILED"))
    assert len(set(texts)) == 1, texts


@pytest.mark.needs_r
def test_check_engine_prints_the_r_version_and_each_package(capsys):
    code = mod("__main__").main(["check-engine"])
    out = capsys.readouterr()
    text = out.out + out.err
    assert code == 0, text
    assert "R version 4." in text, text
    for package in ("MASS", "ggplot2", "jsonlite", "sandwich"):
        assert package in text, (package, text)


def test_the_stand_in_passes_other_calls_to_r(tmp_path):
    """No program code: the stand-in's own behaviour (an analysis fails; anything else is
    handed to R when R is there)."""
    rscript = stand_in(tmp_path, f'echo "{MARK}" >&2; exit 1')
    done = subprocess.run([str(rscript), "x.R", str(tmp_path)], capture_output=True, text=True,
                          timeout=30)
    assert done.returncode == 1 and MARK in done.stderr
    assert T.png_header(_png(tmp_path / "p.png"))[:2] == (1, 1)
    assert slot_text("trend_all") == "{a1.trend}." and analyze_case("trend_all")[0] == "analyze"
    assert MAIN == "stats_like" and Q_TREND and Step and finish
