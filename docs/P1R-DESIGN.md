# Stage 2, round 2: design changes (the contract for this round)

> **On hold since 2026-11-10 (decision D-028).** Round 2 was re-scoped into the agent loop: see
> `docs/PLAN-P1A.md`. Parts of this file are reused there; this file is not a contract to build to.

Written by the planning chat on 2026-11-10, after the first live run in Slack
(`kit-log/raw/P1-live-slack-check.txt`). This file changes `docs/P1-DESIGN.md`. Where the
two differ, this file wins. Everything it does not name stays as P1 says.

Stage 1 does not change at all: `docs/P0-DESIGN.md`, the `ask` command, its 142 tests, and
the saved record (`manifest.json`, `report.md`, `chart.png`) with its full label and every
limitation.

## Why this round

1. Nino, 2026-11-10: the replies are "super techical and dense"; they should be "concise and
   natural and then follow up for further explanation, adjustment".
2. Nino: having to mention the agent on every message inside a thread is awkward.
3. DEFECT 1 of the live run: a follow-up one minute after a 2025 answer was asked "which
   year?", and the next message got the wrong age group. The memory held the right turns;
   the model did not use them.
4. Nino: "better memory retrieval".

## R0. What must not break

- The model decides what is being asked. Python decides whether that is allowed, counts,
  and supplies every number. With the default reply style Python also writes every word,
  and no text the model writes is ever shown. The one exception is R9, a switch that is
  off by default: there the model words one sentence, without ever seeing or typing a
  number, and Python checks it before it is sent.
- Every answer with a number, every list of what can be asked, and every chart says
  `SYNTHETIC`.
- The saved record keeps its full formal wording. The short reply is a view of it.
- No secret is printed, logged or committed. The log never holds question text.

## R1. The model reports only what the latest message says

The model stops doing the remembering. It reports what the LATEST message states, and
Python fills the rest from the thread (R2).

The tools (this replaces the tool list of P1 section 7):

1. `arrest_count_trend`: the latest message asks for a count or trend of arrest records.
   Both arguments are required and both may be null.
   - `year`: a whole number, or `null` when the latest message names no year. A relative
     year ("last year", "this year") counts as named: the model gives the number, from
     today's date.
   - `age_group`: one of the four codes; or `"all"` when the latest message says all ages
     (everyone, overall, in total); or `null` when the latest message says nothing about
     age.
2. `decline`: unchanged (`reason_code`, the four listed codes).
3. `ask_clarification`: `missing` is `age_group` or `other`. The model is told never to ask
   for the year: it leaves `year` null. If it asks for the year anyway, R2 handles it.
4. `show_details` (new, no arguments): the latest message asks for more about the previous
   answer (the details, the monthly numbers, the limits, how it was worked out), or says
   yes to the agent's offer of details.

The thread context block of P1 section 7 stays (same header, same caps), so the model can
tell a follow-up from an unrelated message. Its outcome wordings become: `ANSWERED
year=<y> age_group=<code or null (all ages)> (details were offered)`, `CLARIFICATION ASKED
<missing>`, `DETAILS SHOWN`, `REFUSED <code>`.

The prompt is a new file, `config/system_prompt_v2.md`, written by the planning chat as a
starting text. The build session may reword it under the rules of brief P1-B (log every
change; no check question as an example). `context.DEFAULT_PROMPT` points to it.
`system_prompt_v1.md` stays in the repo, unused, for the record.

## R2. Python fills the gaps from memory

**Tidying** (replaces P1's tidying; only for a call that came from the model). A missing
key counts as not stated.

- `year`: a string of exactly four digits becomes that integer; a float with no fraction
  becomes that integer; `null`, `""`, `"null"`, `"none"` (any letter case) mean not stated.
- `age_group`: `null`, `""`, `"null"`, `"none"`, `"unspecified"` (any case) mean not
  stated; `"all"`, `"all_ages"`, `"all ages"`, `"everyone"`, `"overall"`, `"total"` (any
  case) mean all ages. Anything else is passed on unchanged and meets stage 1's strict
  check.

**What memory offers**, for one thread key at the moment of the question:

- `base`: the year and age group of the most recent `ANSWERED` turn of this thread.
- `pending`: only when the most recent turn of this thread is `NEEDS_INPUT`: the values that
  turn saved (below).

For a direct-message conversation (R5) only turns newer than `MOCO_DM_MEMORY_MINUTES` count,
for the context block, `base`, `pending` and "first answer" (R4). A thread has no time limit.

**Filling**, one value at a time:

- year: stated, else `pending`, else `base`, else Python asks: `NEEDS_INPUT` /
  `NEEDS_CLARIFICATION` with `missing` = `year`.
- age group: stated (a code, or all ages), else `pending`, else `base`, else all ages.

A value that came from `pending` or `base` is "kept". The reply says so (R4), and
`AgentReply.carried` records it: `{"year": bool, "age_group": bool}`. All ages reached
because nothing was stated and nothing was remembered is not "kept".

Then `execute_call("arrest_count_trend", {"year": <year>, "age_group": <code or None>},
question=..., model_id=...)` exactly as now. Its strict check and its codes are unchanged.

**When Python asks.** A `NEEDS_INPUT` turn saves what is known so far in the turn's
`arguments`: `{"year": <int or null>, "age_group": <code, "all" or null>}`. The next turn
reads it as `pending`. No change to the database tables.

**Python never asks for what the thread already holds.** If the model calls
`ask_clarification` with `missing` = `year`, Python treats it as `arrest_count_trend` with
no year stated and with the age group that stage 1's own fixed wordings find in the latest
message (`router.read_age_group(text)`, new: the one age group whose fixed wording appears
in the text, `"all"` for "all ages", else `None`; two different groups give `None`). Then
it fills as above. So the live run's "and for people under 18?" after a 2025 answer gives
2025, people under 18, whichever way the model answers.

`ask_clarification` with `age_group` or `other` (or any unlisted value, which counts as
`other`): `NEEDS_INPUT`, saving `{"year": null, "age_group": null}`.

## R3. `details`

A short reply needs a way to the full record. Two ways in:

- Python, no model call: the cleaned text is exactly `details`, `detail`, `more` or `more
  details` (any letter case, a final `?`, `.` or `!` ignored). Checked in
  `handle_question` after the size check and before the guard.
- The model calls `show_details`.

Either way Python finds the most recent `ANSWERED` turn of this thread key (no time limit),
reads `runs/<run id>/manifest.json`, and writes:

    Here are the details of my last answer.
    Read as: arrest records per month in <year>, <age wording or "all ages">.
    By month: Jan <n>, Feb <n>, Mar <n>, Apr <n>, May <n>, Jun <n>, Jul <n>, Aug <n>, Sep <n>, Oct <n>, Nov <n>, Dec <n>. Total <total>.
    Data: <dataset id>, SYNTHETIC (made-up) test data, not real Montgomery County figures.
    Limits:
    - <each limitation of the saved record, one per line>
    Run id: <run id>

Status `DETAILS` (new), no reason code, no chart. No `ANSWERED` turn in the thread:
`UNSUPPORTED` / `NO_PREVIOUS_ANSWER`, text `There's no answer in this conversation to give
details on yet.` The saved record missing or unreadable: `ERROR` / `RECORD_NOT_FOUND`, text
`I can't find the saved record for that answer, so I can't show its details.` The turn is
saved like any other. Every number in the details comes from the saved record.

## R4. The replies (replaces "The reply text" of P1 section 9)

Python writes all of it from the fixed wording below and the computed record. Numbers of
1,000 or more have a comma. `<years>` is built from the registry's coverage: one year
`2024`; two `2024 or 2025`; more `2024 to 2027`. `<groups>` is the registry's four wordings
joined: `people under 18, ages 18 to 25, ages 26 to 40, or ages 41 and over`.

    CAN_ASK  = I can count arrest records per month for <years>, for all ages or one group (<groups>).
    DATA_TAG = It's SYNTHETIC (made-up) test data.

**`ANSWERED`**, two lines:

Line 1: `In <year> there were <total> arrest records <age phrase>.` then, when something was
kept, ` (I kept <kept> from earlier.)` then a space and the months sentence.

- `<age phrase>`: `across all ages`, or `for ` + the registry wording (`for people under
  18`, `for ages 18 to 25`).
- `<kept>`: the year; or the age wording; or `<year> and <age wording>`.
- Months sentence: `<High> was the busiest month (<n>) and <Low> the quietest (<n>).` When
  several months tie, they are listed in calendar order (`A and B`, or `A, B and C`), the
  verb is `were`, `month` becomes `months` for the busiest, and the number is followed by
  ` each`: `April was the busiest month (50) and January and August the quietest (8
  each).` When every month has the same count: `Every month had the same count (<n>).`

Line 2: for the first `ANSWERED` turn of the thread, `This is SYNTHETIC (made-up) test data,
not real Montgomery County figures. Want the details, or a different year or age group?`
For later ones, `(SYNTHETIC test data, not real county figures.)`

Examples, from the truth file's numbers:

    In 2025 there were 400 arrest records for ages 18 to 25. April was the busiest month (56) and June the quietest (9).
    This is SYNTHETIC (made-up) test data, not real Montgomery County figures. Want the details, or a different year or age group?

    In 2025 there were 303 arrest records for people under 18. (I kept 2025 from earlier.) April was the busiest month (50) and January and August the quietest (8 each).
    (SYNTHETIC test data, not real county figures.)

`AgentReply.chart_title` (new) is `Arrest records per month, <year>, <age wording or "all
ages"> (SYNTHETIC test data)`. The chart image itself is unchanged.

**Everything else.** A refusal is its own sentence, then a space, `CAN_ASK`, and `DATA_TAG`
unless the sentence already says `SYNTHETIC`.

| Code | Text |
| --- | --- |
| `REAL_DATA_NOT_AVAILABLE` | `I don't have real figures yet: only SYNTHETIC (made-up) test data is loaded.` + CAN_ASK |
| `UNSUPPORTED_METRIC` | `I can't answer that one: I only count arrest records, so I have nothing on convictions, sentencing, jail, rates, comparisons or causes.` + CAN_ASK + DATA_TAG |
| `UNSUPPORTED_FIELD` | `I can't break it down that way: the data has only the month and the age group.` + CAN_ASK + DATA_TAG |
| `UNRECOGNIZED_QUESTION` (guard, model, empty question, or no tool call) | `I couldn't read that as a question I can answer.` + CAN_ASK + DATA_TAG |
| `OUT_OF_COVERAGE` | `I have no data for <year>.` + CAN_ASK + DATA_TAG |
| `INVALID_ARGUMENTS` | `I couldn't make sense of the year or age group, so nothing was counted.` + CAN_ASK + DATA_TAG |
| `INPUT_TOO_LONG` | `That's longer than I can read (the limit is <limit> characters). Could you ask it more briefly?` |
| `NEEDS_CLARIFICATION`, year | `Which year do you mean, <years>?` |
| `NEEDS_CLARIFICATION`, age_group | `Which age group do you mean: <groups>, or all ages?` |
| `NEEDS_CLARIFICATION`, other | `Could you say a bit more about what you'd like?` + CAN_ASK + DATA_TAG |
| `MODEL_UNAVAILABLE` | `I can't read questions right now, so nothing was counted. Please try again in a few minutes.` |
| `MODEL_BAD_OUTPUT` | `I got muddled reading that, so nothing was counted. Could you ask it again, maybe in other words?` |
| `RATE_LIMITED` | `I've reached today's limit on questions, so nothing was counted. Please try again tomorrow.` |
| `DATA_CLASS_MISMATCH`, `DATA_UNREADABLE` | `There's a problem with my data file, so nothing was counted. Whoever runs this agent needs to look at it.` |

Unless the status is `ANSWERED` or `DETAILS`, the text holds no count from the data. No
reply ever holds text or a number that came from the model. A year or an age group named in
a reply has passed the strict check or comes from the registry.

`agent-ask` prints the same text. Its exit code for `DETAILS` is 0.

## R5. Slack

**Slack app settings (Nino changes these; no session does).** Add the bot scopes
`channels:history` and `groups:history`, and the bot events `message.channels` and
`message.groups`, then reinstall the app to the workspace. With them Slack sends the agent
every message in the channels it has been added to. The agent drops every message that is
not for it (step 1) without storing it, logging it or sending it to the model.

    slack_app.process_event(event, *, team_id, event_id, settings, store, agent, slack,
                            now=None, start_timer=None) -> str

- `agent(question, thread_key, user_id, memory_minutes=None) -> AgentReply`.
- `slack.post_message(channel, thread_ts, text)`; `thread_ts` of `None` posts at the top
  level. `slack.upload_file(channel, thread_ts, path, title, comment)`.
- New labels: `details`, `quiet`.
- New store method: `thread_has_turns(thread_key) -> bool`.

The steps (this replaces the list of P1 section 11):

1. **Ignore** (post nothing, store nothing, log nothing): an event with `bot_id`, any
   `subtype`, no `user` or no text; and any event that is not one of these three kinds:
   - **mention**: an `app_mention`;
   - **direct**: a `message` whose `channel_type` is `im`;
   - **followed**: a `message` whose `channel_type` is `channel` or `group`, that has a
     `thread_ts`, whose text holds no `<@` mention at all, and whose thread the agent
     already has turns for (`store.thread_has_turns`). A message that mentions the agent
     arrives as a mention; one that mentions someone else is not for the agent.
2. **Duplicate.** `store.seen_event(event_id)` is true, or the same message was already
   handled (`store.seen_event("msg:<channel>:<ts>")`): post nothing. This also covers a
   message that was answered as followed and then edited to add a mention.
3. **Authorize**, as in P1. One difference: a followed message from someone not approved
   is ignored in silence (label `ignored`), not answered with the fixed line.
4. **Where it belongs.**
   - In a channel, or in a direct message that has a `thread_ts`: the root is `thread_ts`
     when present, else `ts`; the key is `<team>:<channel>:<root>`; every post goes to
     that thread. No time limit on memory.
   - A top-level direct message: the key is `<team>:<channel>:dm`; posts go to the top
     level of the conversation (`thread_ts` `None`); the agent is called with
     `memory_minutes` = `MOCO_DM_MEMORY_MINUTES`.
5. **Clean the text**, as in P1.
6. **Commands.** `help` and `reset`, as in P1, with the wording below. (`details` is the
   agent's, R3.)
7. **Per-person limit**, as in P1.
8. **Late acknowledgement.** The line `One moment.` is posted only if the agent has not
   answered `MOCO_ACK_AFTER_SECONDS` after it was called, and never after the reply.
   `start_timer(seconds, function)` returns something with `cancel()`; the default uses
   `threading.Timer`. With the setting at 0 the line is posted at once, before the agent
   is called.
9. **Run the agent and post once.**
   - A followed message whose reply is `UNSUPPORTED` / `UNRECOGNIZED_QUESTION`: post
     nothing; label `quiet`. Without a mention the agent speaks only when it has an
     answer, a question or a specific refusal.
   - A reply with a chart: one `upload_file` with `title` = `reply.chart_title` and
     `comment` = `reply.text`. If the upload raises, post the text with `post_message`
     and write the failure to the log.
   - Otherwise one `post_message` with `reply.text`.
   - Label: `answered`, `refused`, `needs_input`, `details`, `error`, or `quiet`.
10. **If anything raises**, as in P1, with the wording below.

Fixed lines (replace P1's):

    NOT_AUTHORIZED  Sorry, I only answer approved people in this workspace.
    WAIT            That's a lot of questions in one minute. Give me a minute, then ask again.
    RESET_DONE      Done. I've cleared what I remembered of this conversation.
    ERROR_LINE      Something went wrong on my side, so nothing was counted. (ref <8 characters>)
    HELP            I count arrest records per month in SYNTHETIC (made-up) test data. Ask in your own words, for example "How many arrests were there each month in 2025 for ages 18 to 25?" Then follow up with things like "and under 18?" or "what about 2024?". Say "details" for the full breakdown of my last answer, or "reset" to make me forget this conversation.

The log line gains `kind=` (`mention`, `direct` or `followed`). Still no question text.

## R6. Settings

Two new optional numbers: `MOCO_DM_MEMORY_MINUTES` (default 60) and
`MOCO_ACK_AFTER_SECONDS` (default 3). The planning chat adds them to `tools/set_secrets.py`.

## R7. The live model check (changes P1 section 13)

    python tools/model_check.py --models ID1,ID2 [--cases FILE] [--repeat N]
    python tools/model_check.py --list-models

- Default cases file: `config/model_check_cases_v2.json` (planning chat's). A case's
  `accept` entries name the tool and, for `arrest_count_trend`, the STATED year and age
  group after tidying (`null`, a number; `null`, `"all"`, a code). Memory filling is
  Python's and is covered by the tests, not by this check.
- `--repeat N` (default 3): each case is sent N times and passes only if all N pass. The
  line shows `3/3`, or the first failing call.
- A refused request shows its HTTP status, for example `client (HTTP 404)`. The model
  client's log line does too. Each case starts with a closed breaker, so one bad model id
  cannot hide the other cases.
- `--list-models` prints the model ids the key can use, one per line, and nothing else.
- Gate for this round: `nvidia/nemotron-3.5-lightning-30b-a3b` with thinking off passes
  every `must` case 3 of 3. If it does not, the build session rewords the prompt (at most
  four full runs) and reports the result; the decision is Nino's.

## R9. Model-drafted answers: a switch, off by default

Added on 2026-11-10 after Nino asked to test letting the model write replies ("im sure if we
set strict guidelines, rigorous tests too"). The fixed sentences of R4 stay the default and
are the fallback. This section adds a second way to write line 1 of an `ANSWERED` reply.

New setting `MOCO_REPLY_STYLE`: `fixed` (default) or `drafted`. Any other value is a
`ConfigError`.

**What may be drafted.** Only line 1 of an `ANSWERED` reply (the finding). Line 2, the "kept"
note, `details`, every refusal, every question back and every error stay Python's fixed
wording in both styles. An off-topic or unclear message is where a model writing freely
would start answering the off-topic thing, and no check can tell; so those are never
drafted.

**The model never types a number.** When the style is `drafted` and the analysis answered,
Python makes one more model call, `model_client.write(messages) -> str` (no tools; same
timeout, retries, breaker and `extra_body` as `choose`; `max_tokens` 200). The messages
are the writer prompt (`config/writer_prompt_v1.md`, the planning chat's starting text; the
build session may reword it and logs every change) and the user's latest question, marked
as data. The model is given NO value from the data. It writes one to three sentences using
slots, which Python fills afterwards:

    {year}  {total}  {age}  {busiest}  {busiest_count}  {quietest}  {quietest_count}

`{age}` is the registry wording or `all ages`. `{busiest}` and `{quietest}` are the month
names as in R4 (`April`, or `January and August`); the prompt tells the model whether each
is one month or several.

**The check** (`agent.check_draft(draft, rules) -> list of failure codes`, empty when it
passes). The rules file is `config/draft_rules.json`, the planning chat's; no session
edits it. A draft fails when any of these holds:

- `SLOTS`: a `{...}` that is not one of the seven; a slot used more than once; `{year}`,
  `{total}` or `{age}` missing.
- `DIGIT`: any digit, any `%`, a number word from the rules file (two, three, ... twelve,
  twenty, ... hundred, thousand, million, dozen, half, twice, double, triple), or a month
  name. Numbers and months come only from slots.
- `UNIT`: the word `records` is missing.
- `BANNED`: a banned word or phrase from the rules file, matched as whole words in any
  letter case. The list covers causes (because, due to, caused, led to, why), change over
  time (rose, fell, increased, decreased, surged, spiked, dropped, grew, trend), judgement
  (significant, dramatic, alarming, worrying, sharp, only, just, merely, a lot), other
  measures (rate, percent, average, per day), things the count is not (people arrested,
  individuals, offenders, crimes, crime, charges, cases, convictions, jail), claims of
  reality (real, actual, official, Montgomery), and advice or prediction (should, must,
  recommend, expect, predict, forecast).
- `PAIR`: `{busiest_count}` in a sentence without `{busiest}`, or `{quietest_count}`
  without `{quietest}`; or, in a sentence, the nearest of the words busiest, highest, most,
  peak, top / quietest, lowest, fewest, least to a month slot is of the other kind.
- `SHAPE`: empty; more than three sentences; more than 350 characters once filled; a line
  break; or any of `<`, `>`, `@`, `http`, a backtick, `*`, `_`, `#`.

**Outcome.** A draft that passes is filled and becomes line 1; the "kept" note and line 2
are added as in R4. A draft that fails, a `write` that raises `ModelUnavailable`, and the
case where every month has the same count all give the fixed line 1 instead: the answer is
never lost. `AgentReply.reply_style` (new) is `fixed`, `drafted` or `fallback`, and
`AgentReply.draft_failures` (new) lists the failure codes. The log line gains `style=` and
the codes. The draft text itself is never logged or stored.

**The trial** (`tools/draft_trial.py --repeat N`, default 3). For each case in
`config/draft_trial_cases.json` (the planning chat's: a question and the situation it was
asked in) it makes the real `write` call N times and prints the raw draft, the failure
codes or `PASS`, and the filled text, then totals. Saved under `kit-log/raw/` by whoever
runs it. This is the evidence Nino and the planning chat read before the switch is turned
on. It is not a pass or fail gate for the build.

**What the check cannot catch.** A sentence made only of allowed words and slots can still
read oddly or imply something the data does not say. The banned list and the trial reduce
that; they do not remove it. That is the risk the switch carries, and why it is off by
default.

## R10. Conversation about the data and the agent (awaiting Nino's approval)

Added on 2026-11-10 after Nino's point: "what if someone wants a specific dataset or
explanation or requesting something that may be deemed as off topic but actually important
and necessary to the topic itself ... theres no way we can have a library for every
possible question jeffrey will recieve".

There are three kinds of message, and only the first needs an approved analysis:

1. A request for a count: the analysis (R1, R2). Python supplies every number.
2. A question ABOUT the data or the agent: what data there is, what a term means, where the
   data comes from, what the limits are, why something cannot be answered, what the agent
   can do, how an answer was worked out. This section.
3. Everything else: a plain refusal that says what the agent can do (R4), and the request
   is kept (below).

**The tool.** A fifth tool for the model, `explain`, with one argument `topic`: `data`,
`definitions`, `limits`, `capabilities`, `method` or `other`. The model calls it for a
message of the second kind. An unlisted `topic` counts as `other`. The guard still runs
first, so a message that contains a guarded request gets the guard's refusal.

**The fact sheet.** `config/fact_sheet.md`, written by the planning chat from the registry,
the limitations and the designs, and approved by Nino: it is everything the agent may say
about itself and its data. No session edits it. It contains no count from the data.

**Two styles**, by a new setting `MOCO_CONVERSATION`: `off` (default) or `on`.

- `off`: the reply to `explain` is fixed text built by Python from the registry: what the
  data is (made-up test data, the dataset id, the years covered), what is counted (arrest
  records per month, for all ages or one group) and what it is not (the registry's
  `is_not` list), ending with CAN_ASK.
- `on`: one `model_client.write` call with the explainer prompt
  (`config/explainer_prompt_v1.md`), the fact sheet, the thread context block and the
  latest question marked as data. No computed value is given to the model. It is told to
  answer in at most four sentences, only from the fact sheet, and to say so plainly when
  the fact sheet does not cover the question. Python then checks the text
  (`agent.check_explanation(text, fact_sheet, rules)`), and sends it only if it passes:
  - `NUMBER`: every number in the text also appears in the fact sheet (the years covered
    and the ages in the group names); no `%`; no number word from the rules file; no month
    name.
  - `BANNED`: a phrase from the rules file's list for explanations: findings (rose, fell,
    increased, decreased, surged, spiked, more arrests, fewer arrests, most arrests, the
    data shows, suggests that, indicates that, proves), claims of reality (real figures
    show, actual figures), and advice or prediction (should, must, recommend, predict,
    forecast, expect).
  - `SHAPE`: empty; more than four sentences; more than 600 characters; a line break; or
    any of `<`, `>`, `@`, `http`, a backtick, `*`, `_`, `#`.
  If the text lacks the word `SYNTHETIC`, Python adds DATA_TAG. A text that fails, or a
  `write` that fails, gives the `off` text instead.

Status `EXPLAINED` (new), label `explained`, no chart, exit code 0 for `agent-ask`. The
turn is saved; its outcome in the thread context is `EXPLAINED`. `AgentReply.reply_style`
and `draft_failures` (R9) are set the same way. The log line carries the style and the
codes, never the text.

**Requests are kept, not lost.** Every turn is already stored with its question and
outcome. A new command lists what the agent was asked and could not do:

    python -m moco_agent requests [--days N]

It prints, newest first, the time, the reason code and the question of each turn refused
with `UNSUPPORTED_FIELD`, `UNSUPPORTED_METRIC`, `REAL_DATA_NOT_AVAILABLE` or
`OUT_OF_COVERAGE`, with a count per code. No user id is printed. The refusal texts for the
first three of those codes (R4) gain a final sentence: `I've noted it as a request.` This
is how unanswerable questions become the list of what to add next. Adding a data source or
an analysis still needs Nino's approval.

**The trial.** `tools/draft_trial.py` covers explanations too: its cases file marks each
case `answer` or `explain`.

**What the check cannot catch.** Whether an explanation is true. The check keeps numbers
and findings out; the fact sheet and the prompt keep the model to approved facts; nothing
in code can confirm that a sentence means what the fact sheet says. An explanation holds
no statistic, so a mistake here misstates a definition or a limit, not a figure. That is
the risk this switch carries, and why it is off until Nino has read the trial.

## R8. What the tests must show, and what they cannot

Must show: every rule of R1 to R6 with stand-ins, including the live run's own sequence
(a 2025 answer for ages 18 to 25; "and for people under 18?" answered for 2025 and people
under 18 both when the stand-in model leaves the year null and when it asks for the year;
"all ages" overriding memory; a refusal between two follow-ups not breaking the chain; a
fresh thread asking which year and then using the reply); the exact wording of R4 and R5
with numbers from the truth file; `details` from a saved record; a followed message
handled without a mention, ignored outside the agent's threads, silent on chatter, and not
answered twice after an edit; a direct-message conversation remembered inside the window
and fresh outside it; one post per answer; the late acknowledgement posted only when slow
and never after the reply; with `MOCO_REPLY_STYLE` at `drafted`, a stand-in draft that passes is
filled with the truth file's numbers, and a stand-in draft failing each rule of R9 in turn
(a typed digit, a month name, a banned word, a wrong pairing, a missing slot) falls back to
the fixed line, as does a `write` that fails; with the default style `write` is never
called; `explain` giving the fixed text when `MOCO_CONVERSATION` is `off`, a passing
stand-in explanation sent when it is `on`, and one failing each rule of R10 replaced by the
fixed text; the `requests` command listing refused questions without user ids; stage 1's 142 tests untouched and passing.

Cannot show: that the real model fills its two arguments well (the live check), and that
Slack delivers the new events as described (the live Slack check with Nino). Nor whether
the real model's drafts read well: the trial of R9, read by Nino and the planning chat.
