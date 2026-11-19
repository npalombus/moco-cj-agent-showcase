"""D3 (docs/D-DESIGN.md): MOCO_LOG_STDOUT is `off` (the default) or `on`; any other value is
a ConfigError naming the key. With `on`, every line written to agent.log is also written to
standard output, the same text, one line each, and nothing else changes: still ids, labels,
codes and times, never a token, a key, a question or a reply.

D8: `on` puts each log line on standard output too, the same text; `off` and unset put none
(unset: test_d_off.py); a bad value is a ConfigError naming the key; a log line still holds
no question and no reply text.

Readings (kit-log/raw/D-A-notes.txt): the value is read back as settings.moco_log_stdout,
like every other key. "Nothing else changes" is checked as: with `on`, standard output holds
the start line and the lines of agent.log, in the same order, and nothing more. The values
are matched exactly (`ON` is another value). serve runs against a copy of the program with
the Slack stand-in and one message; the log stays in the copy's var/ (MOCO_STATE_DIR unset),
so D1 does not come into these tests.
"""
import pytest

from dsupport import (SETTINGS_EXIT, SYNTHETIC_Q, SYNTHETIC_STEPS, Sandbox, files_under,
                      log_lines, message, project_folders, serve_env, start_line, start_lines)
from p1support import assert_no_secret, make_settings, mod


# ---- the setting ---------------------------------------------------------------------------------

def test_on_is_read(tmp_path):
    assert make_settings(tmp_path, MOCO_LOG_STDOUT="on").moco_log_stdout == "on"


@pytest.mark.parametrize("value", [None, "off"], ids=["unset", "off"])
def test_off_and_unset_read_as_off(tmp_path, value):
    values = {} if value is None else {"MOCO_LOG_STDOUT": value}
    assert make_settings(tmp_path, **values).moco_log_stdout == "off"


@pytest.mark.parametrize("value", ["yes", "true", "ON", "1"])
def test_a_bad_value_is_a_config_error_naming_the_key(tmp_path, value):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        make_settings(tmp_path, MOCO_LOG_STDOUT=value)
    assert "MOCO_LOG_STDOUT" in str(caught.value)


# ---- serve -----------------------------------------------------------------------------------------

def serve(box, value):
    env = serve_env() if value is None else serve_env(MOCO_LOG_STDOUT=value)
    result = box.run("serve", env=env, steps=SYNTHETIC_STEPS, events=[message(SYNTHETIC_Q)])
    assert result.code == 0, result.explain()
    assert result.report["answered"] == [True], result.explain()
    logged = [line for line in log_lines(box.var / "agent.log") if line.strip()]
    assert any("label=answered" in line for line in logged), "premise: the event was logged"
    return result, logged


def test_on_puts_every_log_line_on_standard_output_too(tmp_path):
    """With `on`: standard output is the start line and every line of agent.log, the same
    text, in the same order, nothing else. The real project's var/ and runs/ are listed
    before and after."""
    before = project_folders()
    box = Sandbox(tmp_path)
    result, logged = serve(box, "on")
    assert start_lines(result) == [start_line("SYNTHETIC", box.var / "agent.log")]
    others = [line for line in result.lines if line not in start_lines(result)]
    assert others == logged, (f"standard output is not the log's lines:\n--- stdout ---\n"
                              f"{result.stdout}\n--- agent.log ---\n" + "\n".join(logged))
    assert project_folders() == before, "the real project's var/ or runs/ changed"


def test_off_puts_no_log_line_on_standard_output_and_on_does(tmp_path):
    """`off` written out: no line of agent.log on standard output, only the start line. The
    same serve with `on` puts them there."""
    off_box, on_box = Sandbox(tmp_path / "off"), Sandbox(tmp_path / "on")
    off, off_logged = serve(off_box, "off")
    assert not set(off_logged) & set(off.lines), "a log line is on standard output"
    assert off.lines == start_lines(off), off.explain()
    on, on_logged = serve(on_box, "on")
    assert set(on_logged) <= set(on.lines), on.explain()


def test_a_log_line_on_standard_output_holds_no_question_no_reply_and_no_secret(tmp_path):
    """With `on`, the log lines on standard output (and in agent.log) hold neither the
    question nor the reply's text, nor any part of a made-up secret."""
    box = Sandbox(tmp_path)
    result, logged = serve(box, "on")
    assert set(logged) <= set(result.lines), "premise: the log lines are on standard output"
    replies = [p["text"] for p in result.posts] + [u["initial_comment"]
                                                   for u in result.report["uploads"]]
    first_lines = [text.splitlines()[0] for text in replies
                   if text and text not in ("None", "One moment.")]
    assert first_lines, "premise: the message got a reply"
    for text in (result.stdout, "\n".join(logged)):
        assert SYNTHETIC_Q not in text and "recorded each month" not in text
        for line in first_lines:
            assert line not in text, "a reply's text is in the log"
        assert_no_secret(text)


def test_a_bad_value_stops_serve_before_slack(tmp_path):
    """serve with MOCO_LOG_STDOUT=yes stops with exit code 4 naming the key, before the
    model or Slack, writing nothing in the project's var."""
    box = Sandbox(tmp_path)
    result = box.run("serve", env=serve_env(MOCO_LOG_STDOUT="yes"), steps=SYNTHETIC_STEPS,
                     events=[message(SYNTHETIC_Q)])
    assert result.code == SETTINGS_EXIT, result.explain()
    assert "MOCO_LOG_STDOUT" in result.stdout + result.stderr, result.explain()
    assert result.report["apps"] == 0 and result.report["model_clients"] == 0
    assert files_under(box.var) == []
