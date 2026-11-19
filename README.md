# moco-cj-agent: the Montgomery County criminal justice data agent

A Slack agent ("Jeffrey") that answers plain-English questions about arrest records in
Montgomery County, Maryland. Built for the course SPA-375 (American University, fall 2026).
You ask in Slack or in Terminal; the agent counts arrest records, compares and breaks them
down, runs a fixed menu of statistics in R, gives rates per 10,000 residents from the Census,
explains what the data is and lacks, or says plainly why it cannot answer.

The design rule that runs through everything: **the language model never counts or writes a
figure.** The model only chooses which tool to call and with what options. Python counts the
records, checks every option against the data's own fields, writes every number into the
reply, and checks the model's words before anything is sent. A reply that fails a check is
replaced by Python's own wording.

![Jeffrey in a Slack thread: arrests by district with a chart, a follow-up that leaves one district out, a five-year trend computed in R, and a question about one single age that he turns into an age range](docs/demo.gif)

*A real Slack thread on 18 November 2026, county mode, Montgomery County's open data. The waiting time is sped up.*

It runs in one of two modes, set by `MOCO_DATA`:

- **synthetic** (the default): the data in `data/synthetic/` is made up for testing. It
  describes no real person or event and says nothing about Montgomery County. Every answer
  with a number, every list of what can be asked, and every chart says SYNTHETIC.
- **county**: real Montgomery County open data (Police Arrests), counted from a saved,
  dated copy that the agent downloads itself. Every answer names its source and the date of
  the copy. The two kinds of data never meet in one answer.

## Try it in five minutes (no keys, no network)

You need Python 3.12.

    git clone <this repository> moco-cj-agent && cd moco-cj-agent
    python3.12 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install -e .
    .venv/bin/python -m moco_agent ask "How many arrests were recorded each month in 2025 for ages 18 to 25?"

That runs the first stage's fixed rules on the SYNTHETIC data, with no model. It saves the
answer, a table and a chart under `runs/`.

## What you need for the full agent

| For | You need | Setting |
|---|---|---|
| The agent's reasoning | An Anthropic API key (or an NVIDIA API key) | `ANTHROPIC_API_KEY` |
| Slack | A Slack workspace where you can install apps | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` |
| Statistics and charts in county mode | R 4.2 or newer with the packages MASS, ggplot2, jsonlite and sandwich | `MOCO_RSCRIPT` if `Rscript` is not on your PATH |
| Rates per resident (optional) | A free US Census Bureau API key | `CENSUS_API_KEY` |
| County data | Nothing: it is public, and the agent downloads it | `MOCO_DATA=county` |

## Set up

1. **Install** as in "Try it" above. For the tests, also `.venv/bin/pip install -r requirements-dev.txt`.
2. **Settings.** Copy `.env.example` to `~/.config/moco-cj-agent/.env` (or anywhere, and
   set `MOCO_ENV_FILE` to that path) and fill in your own values. The file lives outside the
   project folder so it can never be committed. The program reads it at run time and never
   prints a key; a value in the shell's environment wins over the file.
3. **Slack app.** At https://api.slack.com/apps choose "Create New App", "From an app
   manifest", and paste `slack-manifest.yaml`. Install it to your workspace and copy the
   "Bot User OAuth Token" into `SLACK_BOT_TOKEN`. Under "Basic Information", create an
   app-level token with the scope `connections:write` and copy it into `SLACK_APP_TOKEN`.
   Then run `.venv/bin/python -m moco_agent whoami`: it prints your workspace id (for
   `SLACK_ALLOWED_TEAM_ID`). Put the member ids of the people allowed to use the agent in
   `SLACK_ALLOWED_USER_IDS` (in Slack: a profile, the three dots, "Copy member ID").
4. **County data** (optional): set `MOCO_DATA=county`, then
   `.venv/bin/python -m moco_agent refresh` downloads every county source once. With
   `MOCO_REFRESH_HOURS=24` the running agent refreshes it daily by itself.

## Run it

- In Terminal, one question with the real model:
  `.venv/bin/python -m moco_agent agent-ask "Compare 2024 and 2025 for people under 18."`
  (`--thread KEY` lets you try a follow-up in the same conversation.)
- In Slack: `.venv/bin/python -m moco_agent serve`. It connects out to Slack in Socket Mode
  (no public address needed) and runs until Ctrl+C. Mention the agent in a channel or send
  it a direct message; in a thread where it has answered, it follows replies without a
  mention. `help` shows what can be asked, `details` the full breakdown of the last answer,
  `reset` clears the conversation's memory.

## Deploy (Docker, for example on Railway)

The `Dockerfile` builds Python 3.12 with R and the four R packages, and runs `serve`. Mount a
volume at `/data`: memory, the log, the county copies and the saved records live there and
survive a redeploy. Set the same settings as in `.env.example` as the service's environment
variables (the container has no settings file of its own). Socket Mode needs no public URL or port.

## How it was built

In stages, each with a written contract in `docs/` (`P0-DESIGN.md` stage 1, `P1-DESIGN.md`
and `P1A-DESIGN.md` stage 2, `S3A-DESIGN.md`, `S3S-DESIGN.md` and `S3S2-DESIGN.md` stage 3,
`T-DESIGN.md` conversation, `D-DESIGN.md` deployment); where they differ, a later one wins.
Tests were written against each contract; the suite has over 6,000 tests and uses stand-ins
for the model and Slack, so it needs no key and no network. References in the contracts and
in code comments to `kit-log/`, `briefs/` and decision numbers (D-0xx) point to working
records of the private build repository that are not part of this public copy.

## How the agent works, in steps

1. **Size.** An empty question, or one longer than `MOCO_MAX_QUESTION_CHARS`, gets a fixed
   reply. No model is called.
2. **Details.** Exactly `details`, `detail`, `more` or `more details` shows the full
   breakdown of the last answer in the conversation, from its saved records. No model.
3. **The guard.** Stage 1's own rules screen the question. An instruction to ignore the
   rules or to state a figure is refused with no model call. A question about real
   figures, a measure other than a count (convictions, rates, jail ...) or a field the
   data lacks (race, place, offense ...) still goes to the model, so it can explain, but
   the counting tools are switched off for that message.
4. **The loop.** The model works in steps. At each step it calls tools and Python
   answers each call. It is given the agent prompt (`config/agent_prompt_v2.md`), the
   data's description from `config/registry.json`, today's date, the earlier turns of the
   same conversation (in Python's words, with no number from the data), the latest
   message, and this turn's steps so far. A turn has at most 6 steps, 8 counts, 12 tool
   calls and 90 seconds.
5. **Remember.** The turn is stored in `var/agent.db`; a turn that called the model also
   saves `runs/<turn id>/turn.json` (A9 of the design).

The tools the model is offered:

| Tool | What Python does |
| --- | --- |
| `count_arrests(year, age_group)` | Counts one year, for all ages or one age group, through stage 1's `execute_call`, which saves the full record (`manifest.json`, `report.md`, `chart.png`). The model gets back a result id (`r1`, `r2`, ...) and two fact slots, `{r1.count}` and `{r1.months}`, never a value. |
| `compare(result_ids, field)` | Compares two to eight counts of this turn: highest, lowest, and the difference. No rate, no percentage. |
| `describe_data()` | Returns the approved fact sheet, `config/fact_sheet.md`, one fact slot (`{f1}`, `{f2}`, ...) per line. |
| `ask_user(missing)` | Ends the turn with a question Python writes. |
| `show_details()` | Ends the turn with the details of the last answer. Called after counting in the same turn, it sends this turn's answer instead (Python's own sentence). |
| `decline(reason_code)` | Ends the turn with a fixed refusal. |
| `finish(kind, text)` | Ends the turn with the model's reply, checked first (below). |

When the latest message leaves out the year or the age group, the model passes null and
**Python fills it** from the conversation: from a question the agent just asked, else from
the last answer (when that answer had one year, or one age group). The reply then says what
was kept, for example `(I kept 2025 from earlier.)`. With no year anywhere, the agent asks
which year; it never guesses one.

## How replies are written and checked

The model never sees a count and never types one. **Python writes every fact as one whole
phrase**, so a number never stands apart from what it counts. The model writes a few plain
words around **fact slots**, and Python fills each slot:

- `{r1.count}`: `400 arrest records for ages 18 to 25 in 2025`
- `{r1.months}`: `April was the busiest month (56) and June the quietest (9)`; it may only
  come straight after its own count slot, since it names no year or age group
- `{r3.compare}`: `2025 had the highest count (303) and 2024 the lowest (249), a difference
  of 54`
- `{f1}`, `{f2}`, ...: a line of the fact sheet, for a reply about the data itself

Before anything is sent, Python checks the text (`src/moco_agent/replies.py`). Outside the
slots, every word must be on the list of plain words in `config/reply_words.json` (the
planning chat's), and only letters, spaces, apostrophes and ordinary punctuation are allowed:
no digit, no other script, no markup, no quotation mark, no line break. Each slot must be
one this turn offers, used once, and must stand on its own (a space before it, a space or
punctuation after it, words or a sentence end between two slots). At most four sentences
and 600 characters once filled. A text that fails is not used: Python writes the reply
itself from the results (the "fallback" style) and records which checks failed. Every
answer ends with a SYNTHETIC line.

A question about the data itself is answered from the fact sheet's slots only (at most four),
under the same check; general background on criminal justice data is off unless
`MOCO_BACKGROUND=on`, and keeps its older checks with `config/reply_rules.json`.
Every other reply (refusals, questions back, errors) is fixed wording.

## Talk (`MOCO_TALK`)

With `MOCO_TALK=off` (the default) everything above holds exactly. With `MOCO_TALK=on`
(docs/T-DESIGN.md) the agent uses `config/agent_prompt_talk.md` (or
`config/agent_prompt_s3_talk.md` in county mode) and may answer a greeting, a thanks or small
talk in its own words. Such a reply is checked by `config/talk_rules.json`: no digit, number
word or month, no group or place label, no claim about the figures, only letters and plain
punctuation, at most four sentences and 500 characters on one line. A finding may then hold
up to two sentences of its own beside the slot sentences, which keep every rule above; those
sentences get the same check and may not judge the figures. A text that fails is sent back to
the model once with what failed; if the second text fails too, Python's own wording is sent.
With `MOCO_BACKGROUND=on` as well, a background text must also say why the possibility is
plausible and what records would check it. A talk reply is one plain message with no data
tag, is kept in the thread's memory, and is skipped by `details` and by the filling of year,
group, source, period and filters.

## What people asked for that the data lacks

    .venv/bin/python -m moco_agent requests [--days 30] [--db var/agent.db]

Lists, newest first, the questions refused because the data lacks a field, a measure, real
figures or a year, then a count per reason. No user id is shown.

## Ask with the stage 1 rules (no model, no network)

    .venv/bin/python -m moco_agent ask "How many arrests were recorded each month in 2025 for ages 18 to 25?"

Exit codes: 0 answered, 3 refused, 4 error. It reads only fixed wordings ("under 18",
"juvenile(s)", "18 to 25", "18-25", "young adults", "26 to 40", "26-40", "41 and over",
"41+", "over 40") and refuses anything it cannot read word for word. `--data PATH` uses
another data file.

## County mode (real county data)

Set `MOCO_DATA=county` (in the private file, or before a command). Then:

1. **Fetch a copy** of a source, once and whenever you want fresh data:

       MOCO_DATA=county .venv/bin/python -m moco_agent fetch MOCO:police_arrests

   It downloads every row from the county's open data service (the only address it
   contacts is the one in the source file), checks it, and prints the copy's date, its
   number of rows and its fingerprint. A copy that fails a check (a listed field missing,
   more than 2 in 100 fewer rows than the last good copy, an older newest record, an error
   page or a redirect) is not used: the last good copy stays in use and the command says
   why. Copies live in `var/copies/<source>/<time>/` and are not saved in git.
2. **Ask** in Terminal (`agent-ask`) or in Slack, as before. The agent can count any period
   the copy covers, filter by age range, gender, race, ethnicity, district, distance from a
   school, bureau, day of the week and hour, break a count down by one or two of those (or
   by age band, year, month, day or hour), compare counts and give one count as a share of
   another. Nothing is fetched while answering; with no copy it says so.

What the sources are and what may be asked of them lives in `config/sources/` (one file per
source, written by the planning chat); nothing about a source is written in the code. The
agent never shows a single record. A count from 1 to 9 is shown as "fewer than 10"; when a
group of a table is hidden that way, the answer points to the county's own page, which has
every record. Totals stay exact. An
answer says how many records it left out (no district recorded, no usable age), adds "These
are counts of arrest records, not rates, and they show no cause." when it uses race,
ethnicity or gender, and ends with the source and the copy's date. "details" gives the full
tables, the county's notice word for word, and the line that this is a course project and not
a county service.

## Statistics with R (county mode)

In county mode the agent can also run one of seven analyses on a source's copy, chosen by the
model from a fixed menu with its options filled in (`analyze`): **trend** (is it rising or
falling, adjusted for the season), **trend_compare** (do two groups change differently),
**before_after** (did the level or the trend change from a date), **yes_no** (what goes with
a yes-or-no outcome, holding other things fixed), **shares** (a part's share, year by year),
**timing** (weekday by hour) and **distribution** (ages). At most two in one message.

- R does the statistics and draws the chart; Python counts the records into one small table
  for R, checks what R sends back, and writes every word of the answer. The model never sees
  an estimate. The scripts are in `analysis_r/` (one per kind, `common.R` for the models,
  `theme.R` for the look of the charts).
- Models use full months only, and leave out the copy's newest full month, which may still be
  filling in at the county. An analysis with too little data is refused with the reason (for
  example fewer than 24 months for a trend), and so is one whose chart would show a count
  under 10. These numbers are in `config/analysis.json`. A before-and-after with exactly 12
  months on each side of the date is refused too: with so few months a step at the date
  cannot be told apart from the yearly trend.
- A trend comparison fits each group on its own; the stated difference is worked out from
  those two fits, so it agrees with the two yearly changes in the table. Its chart gives each
  group its own panel and scale. Each trend chart's foot line says what the grey and blue
  lines are.
- R is started with a short environment (`PATH`, `HOME`, `LANG`, `LC_ALL`, `TZ`, `TMPDIR` and
  variables starting `R_`), so no key of the agent's ever reaches it.
- Every statistical answer says how many records it used and left out, and ends with "These
  are patterns in recorded arrest records: what goes with what, not what causes what." A
  before-and-after answer also says it shows timing, not cause. The chart comes with the
  answer. "details" adds the full table, the model in one sentence, and an R script anyone
  can run: it downloads the same public data from the county, applies the same filters and
  months, fits the same model and prints the same estimates.
- R 4 with the packages MASS, ggplot2, jsonlite and sandwich must be installed. Check with:

      .venv/bin/python -m moco_agent check-engine

  It prints the R version and whether each package loads. Without R, a statistical question
  is answered "I can't run statistics here right now ... Counts still work."

## Rates per resident (county mode)

The agent can give arrest records per 10,000 residents (`analyze` with kind `rate`), using the
Census Bureau's American Community Survey one-year estimates for Montgomery County as the
residents. The definitions are in `docs/S3S2-DESIGN.md`; the Census tables, groups and the words
each Census label must hold are in `config/census.json` (the planning chat's).

1. **Fetch the Census copies**, once, and again when the Census publishes a new year (late each
   year):

       MOCO_DATA=county .venv/bin/python -m moco_agent fetch-census

   For each year from 2021 to last year it downloads tables B01001 (sex by age) and B03002
   (Hispanic or Latino origin by race) for the county and the Census's own labels of their
   lines, with `CENSUS_API_KEY` from the private file. A year is kept only if every line the
   agent adds up is there and its label holds the words `config/census.json` expects;
   otherwise that year is refused, with the line named, and its last good copy stays in use.
   A year the Census has not published yet is said so and skipped. Copies live in
   `var/census/<year>/<time>/`, dated and fingerprinted, and are not saved in git. With
   `CENSUS_API_KEY` set, `refresh` (and the refresh inside `serve`) does this too, at most
   once a day.
2. **Ask** for a rate, for whole calendar years (one year, or several in a row): for all
   records, or by one of gender, age band (10 to 17, 18 to 24, 25 to 34, 35 to 44, 45 to 54,
   55 to 64, 65 and over) and race and ethnicity together (Hispanic of any race; Black, White
   and Asian, not Hispanic). Only a source whose file says `"rates": true` can be used (to
   start with, Police arrests).

What the answer holds: each group's rate with its margin of error, and how many times the
reference group's rate it is (the group with the most residents, unless the question names
another), with that ratio's margin; a table of records, residents and rate per group; how many
records were used and left out; and fixed lines: a rate is not the share of residents arrested;
the margin comes from the Census's survey alone, at its 90 percent level; for race and
ethnicity, that the police and the Census record these differently; the source line names the
county's copy and the Census's. A group with fewer than 100 records in the years asked is not
shown (only its name is). R works out the rates, the margins (the Census Bureau's own formulas)
and the ratios, and draws the chart (one dot per group with its range). "details" names the
Census table, gives each year's residents with their margins, and attaches an R script that
downloads the county's records and the Census tables (the Census address in it has no key: the
reader adds their own) and prints the same rates.

Refused, each with one sentence that says why: a rate by police district or inside one; by race
alone or by ethnicity alone (offered: race and ethnicity together); by any other field; two
breakdowns at once; a filtered selection; a source not marked for rates; part of a year; a year
with no Census copy (2026 until the Census publishes it, late in 2027); a reference group that
is not shown; and too little data (no group with 100 records).

## Run the tests

    .venv/bin/python -m pytest -v

The tests use stand-ins for the model and for Slack: they use no network, no real key and
no real `var/` or `runs/` folder. They cannot show how the real model behaves. The tests of
the statistics (`tests/s3s/`) start the real R and need `statsmodels` and `scipy`
(`requirements-dev.txt`) to work out the right answers themselves.

## The live loop check (uses the real NVIDIA model)

    .venv/bin/python tools/loop_check.py --models nvidia/nemotron-3.5-lightning-30b-a3b --repeat 3
    .venv/bin/python tools/loop_check.py --models nvidia/nemotron-3.5-lightning-30b-a3b --repeat 3 --background

It runs every case of `config/loop_check_cases.json` through the real agent and the real
model, each in a fresh memory seeded with the case's earlier turns, and prints PASS or FAIL
per run, the reply as sent, and totals: must cases passed, replies in the agent's own
words against fallback, the failed checks seen, and seconds per turn. `--background` runs
the background cases with `MOCO_BACKGROUND` on (the other cases run either way). `--talk`
runs with `MOCO_TALK` on, for example on `config/loop_check_cases_talk.json`; it also prints
the checks the first text failed (`first=`) and counts talk replies by style. Each run's
memory and records are kept under `runs/loop-check/`.

## Where the output goes

Each count gets its own folder, `runs/<run id>/`, holding `manifest.json` (the full record:
status, numbers, the data file's fingerprint, which router or model chose the call),
`report.md` (the answer, limitations and the monthly table) and `chart.png` (only when
answered). In county mode a count's folder holds `manifest.json` only: the spec, the copy's
fingerprint and date, the exact figures and the figures as shown, what was left out and the
limitations. An analysis's folder holds `manifest.json` (the record, with every estimate),
`script.R` (the script "details" sends) and `job/`: what R was given (`job.json`,
`input.csv`: counts by month, 0/1 lines, a weekday-by-hour table or ages, never a record's id
or time) and what it made (`result.json`, `chart.png`). Each turn that called the model saves `runs/<turn id>/turn.json`: the question,
every step with what the model wrote in it (exactly, or null), every tool call and
Python's answer, the results, the model's reply text as given, the checks that failed and
the words and characters that failed them, and the reply sent. A reply text that failed the
checks is kept there and nowhere else. `runs/` and `var/` are not saved in git.

Memory lives in `var/agent.db`. A file from stage 2's first build still holds its old
`turns` table (questions and Slack user ids); opening the file deletes that table.

## License

MIT; see `LICENSE`. The county data the agent downloads is Montgomery County's, under the county's own terms.
