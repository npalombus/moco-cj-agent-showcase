# Part D: ready to run on a server (contract)

Written by the planning chat on 2026-11-12. Plan: `docs/PLAN-S4.md` ("Small build first").
Built by the planning chat (D-050, D-051); tests by a Claude Code tests session, because a
builder never grades its own work.

Why: on Railway the project folder is thrown away at every deploy. Only the storage
mounted at `/data` survives. Today his memory and his log are written inside the project
folder, so a redeploy would wipe them. And nothing refreshes the county copies unless a
person runs `fetch` by hand.

## D0. Nothing changes when the new settings are not set

With `MOCO_RUNS_DIR`, `MOCO_LOG_STDOUT` and `MOCO_REFRESH_HOURS` unset and
`MOCO_STATE_DIR` unset, every file is written where it is today and every existing test
passes untouched.

## D1. Everything that must survive follows `MOCO_STATE_DIR`

`MOCO_STATE_DIR` exists (default: the project's `var` folder). Today only the county copies
follow it. From Part D these do too:

- the memory file: `<state dir>/agent.db`, for `serve`, `agent-ask` and `requests`. A
  `--db` given on the command line still wins.
- the log file: `<state dir>/agent.log`, for `serve`.

The folder is made if it is missing, parents included. If it cannot be made or written,
the command stops before connecting to anything, with one line naming `MOCO_STATE_DIR`
and exit code as for any other settings error.

## D2. `MOCO_RUNS_DIR`

Where saved records go (each turn's folder with `turn.json`, each run's folder, charts,
and from Part S the statistics job folders). Default: the project's `runs` folder, as
today. Made if missing, parents included.

## D3. `MOCO_LOG_STDOUT`

`off` (the default) or `on`. Any other value is a ConfigError naming the key. With `on`,
every line written to `agent.log` is also written to standard output, the same text, one
line each, and nothing else changes: still ids, labels, codes and times, never a token, a
key, a question or a reply.

## D4. `python -m moco_agent refresh`

Fetches every county source whose file in `config/sources/` is valid (C20), one after the
other, in the order of their ids, with the same code `fetch` uses. One line per source on
standard output:

    <source id>: <rows> rows, copy of <day>, sha256:<first 12 characters>
    <source id>: FAILED (<what fetch would say>); the last good copy stays in use
    <source id>: FAILED (<what fetch would say>); there is no copy yet

A source that fails never stops the others, and its last good copy is left exactly as it
was. Exit code 0 when every source succeeded, otherwise the code `fetch` gives for a
failed fetch. Like `fetch`, it works whatever `MOCO_DATA` is set to.

After a source is fetched successfully, its copies beyond the newest three are deleted
(the whole dated folder), so the storage does not fill up. `fetch` deletes nothing, as
today. Nothing outside `<state dir>/copies/` is ever deleted.

## D5. `MOCO_REFRESH_HOURS`

A whole number from 0 to 168; 0 (the default) is off. Anything else is a ConfigError
naming the key. With a number above 0, and `MOCO_DATA=county`, `serve` keeps the copies
fresh by itself:

- once at start, and then every ten minutes, it looks at every valid source; a source
  with no copy, or whose newest copy was fetched more than that many hours ago, is **due**;
- each due source is fetched as D4 does it (pruning included);
- this runs beside the Slack connection and never blocks or stops it: a failure of any
  kind is caught and logged as one line (the source id and what failed) and tried again at
  the next look; a source that failed is not tried more than once an hour;
- a turn uses the newest copy there is when the turn starts (as today); a fetch that is
  under way does not change a turn that has started.

With `MOCO_DATA` not `county`, the setting is read and checked but nothing is fetched.

The two pieces a test can call without Slack or a clock of its own:
`moco_agent.refresh.due(sources, state_dir, now, hours)` gives the ids that are due, in
order, and `moco_agent.refresh.run_once(state_dir, now, hours, transport=None)` fetches
what is due and returns `{source id: "ok" or the failure's text}`.

## D6. The line `serve` prints at start

Today it says `data SYNTHETIC` whatever the mode. It must say `data SYNTHETIC` only in
SYNTHETIC mode and `data COUNTY (real county open data)` in county mode, and name the log
file where D1 puts it.

## D7. Files for the server (not tested by pytest)

`Dockerfile` and `.dockerignore` at the top of the project: Python 3.12 and R with the
four packages Part S names, the project's `src`, `config`, `data` and `analysis_r`
folders, no test, no `var`, no `runs`, no kit log, no secret; it starts
`python -m moco_agent serve`. The first real test of these two files is Railway's build.

## D8. What the tests must show

- D0: with the four settings unset, the memory file, the log file and the records are
  where they are today.
- D1: with `MOCO_STATE_DIR` set to a new folder two levels deep, `serve` (with the Slack
  stand-in), `agent-ask` and `requests` use `<state dir>/agent.db`; `serve` writes
  `<state dir>/agent.log`; nothing is written under the project's `var`; `--db` wins; a
  state folder that cannot be made stops the command before the model or Slack is touched.
- D2: with `MOCO_RUNS_DIR` set, a turn's `turn.json` and a count's run folder are under it
  and nothing is written under the project's `runs`.
- D3: `on` puts each log line on standard output too, the same text; `off` and unset put
  none; a bad value is a ConfigError naming the key; a log line still holds no question
  and no reply text.
- D4: with the fixture sources and a fake transport: every valid source fetched in id
  order; each of the three lines exactly; one failing source does not stop the next; the
  failed source's last copy is byte for byte what it was; the exit codes; an invalid
  source file is left out; four copies become three and the newest three stay; `fetch`
  prunes nothing.
- D5: `due` with no copy, a copy one minute younger than the limit, one minute older;
  `run_once` fetches only what is due; a failure is returned and logged and raises
  nothing; a source that failed is not tried again within the hour; 0, 168 and each bad
  value (`-1`, `169`, `1.5`, `x`, empty); with `MOCO_DATA` not `county` nothing is
  fetched; `serve` with the Slack stand-in starts the refresh and still answers a message
  while a slow fetch is under way.
- D6: the start line in each mode.
- No test touches the network, needs a real key, or sleeps for real time.

## D9. Answers to the tests session (2026-11-13)

The tests session listed its readings and its open points in `kit-log/raw/D-A-notes.txt`.
Its readings 1 to 16 stand as it took them. The planning chat's answers to its points:

- **A. An empty `MOCO_REFRESH_HOURS` is a ConfigError.** D8 says so and it stands, though
  every other key reads an empty value as unset. Reason: a variable made on the server and
  left empty would otherwise switch the refresh off without a word.
- **B. `--runs-dir` on the command line wins over `MOCO_RUNS_DIR`**, as `--db` wins over
  `MOCO_STATE_DIR`. The stage 1 `ask` command reads no settings at all and does not follow
  `MOCO_RUNS_DIR`. The statistics' job folders are inside the saved record, so they follow
  the records folder.
- **C. matplotlib's cache is not a record.** It goes where `MPLCONFIGDIR` says, and with
  that unset to `runs/.matplotlib` in the project, whatever the records folder is. The
  server image sets `MPLCONFIGDIR=/tmp/matplotlib`. "Nothing is written under the project's
  runs" means no record.
- **D. A refresh line writes its row count as `fetch` does**, with the thousands comma:
  `12,345 rows`.
- **E, F.** Agreed: the ten minutes inside `serve`, and "nothing is fetched later", cannot
  be tested without waiting. The hour is tested through `run_once`.
- **G. With `--db` given, the state folder is neither made nor checked** for the memory
  file: the path given is used as it is.
- **H.** The contract's wording wins over `PLAN-S4.md`.
- **I.** Agreed: on the server each log line shows its own time and Railway's. Left as it
  is.
- **The failure memory (its reading 13)** is kept in the process, per state folder: a restart forgets which
  source failed within the hour and tries it again.

## D10. Round 2 of Part D, from the fresh session's check (2026-11-13)

The check of the planning chat's build (`kit-log/raw/CHAT-BUILDS-check.txt`) gave Part D
FAIL for one sentence of D4, and named a gap in what protects pruning. Both are fixed
here; tests first (`briefs/GAPS-A-tests.md`), the build is the planning chat's.

1. **"A source that fails never stops the others" holds for a failure of ANY kind.** The
   first build caught only the failures `fetch` reports and those of saving the copy; a
   download cut off half way (`http.client.IncompleteRead`) stopped the whole `refresh`
   command with a traceback. Now, for the `refresh` command and inside `serve` alike: any
   other failure while fetching one source is that source's failure. Its line is
   `<id>: FAILED (unexpected error (<the error's type name>)); the last good copy stays in
   use` (or `; there is no copy yet`), the command goes on to the next source, and the exit
   code is 4. No traceback is printed. A failure while pruning after a good fetch does not
   make the fetch a failure: the copy is used and the line is the line of a good fetch.
2. **Pruning never leaves `<state dir>/copies/`.** A source's folder name is its id after
   the colon with every character other than letters, digits, `_`, `.` and `-` turned into
   `_`; a name made of dots only (`.`, `..`) is written with `_` for each dot, and an empty
   name is `_`. `prune` does nothing for a folder that is not directly inside
   `<state dir>/copies/`. All thirteen source files today give plain names; this is for a
   source file added later.

**What the round's tests must show:** the `refresh` command with a transport that raises
`http.client.IncompleteRead` for one source and answers for the other: the failed
source's line exactly, the other source fetched and its line printed, exit code 4, no
traceback on either stream, the last good copy of the failed source untouched and still
current; the same failure for the first source in id order and for the last; `run_once`
with the same failure gives the text `unexpected error (IncompleteRead)` for that source
and "ok" for the other; a failure while pruning (a stand-in that raises) leaves the good
fetch's line and exit code 0; the folder names for the ids `X:..`, `X:.`, `X:` and
`X:a.b`; `prune` for a source whose id is `X:..` deletes nothing in the state folder (a
file and a folder put there by the test are still there).
