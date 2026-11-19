# Stage 2, the agent loop, revision 2: design (the contract)

Written by the planning chat on 2026-11-11. Plan: `docs/PLAN-P1A-R2.md`, approved by Nino
on 2026-11-11 (decisions D-035 and D-036). This file changes `docs/P1A-DESIGN.md`. Where
the two differ, this file wins; what it does not name stays as P1A says. Stage 1 does not
change at all.

Why: the planning chat's check of the build (`kit-log/raw/P1A-B-chat-check.txt`, part C)
found that A7's checks let false statements through. The model could not type a number,
but it could put a number beside the wrong year, add "per day", or state a comparison the
wrong way round. A list of banned words cannot be complete. So the rule is turned around.

## R0. What must not break (adds to A0)

- A number never reaches a person without the words that say what it counts. Python
  writes every fact as one whole phrase.
- In a finding or an answer about the data, the model's own words come only from an
  approved list of plain words (`config/reply_words.json`).

## R1. Facts are whole phrases (replaces "Slots" and the `finding` and `about_data` parts of A7)

**Fact slots.** The old value and label slots (`{r1.total}`, `{r1.year}`, `{r3.top_label}`
and the rest) no longer exist. There are three kinds of fact slot, and Python writes what
each fills with:

- `{rN.count}` of a count result: `<total> arrest records <age phrase> in <year>`, where
  `<age phrase>` is `across all ages` or `for ` + the registry wording, and a total of 1
  gives `1 arrest record`. Example: `400 arrest records for ages 18 to 25 in 2025`.
- `{rN.months}` of a count result: the months sentence of `render_fixed` without its final
  full stop. Example: `April was the busiest month (56) and June the quietest (9)`. When
  every month is equal: `every month had the same count (<n>)`.
- `{rN.compare}` of a compare result: the compare sentence of `render_fixed` without its
  final full stop and with its first label as the registry writes it (not capitalised).
  Example: `2025 had the highest count (303) and 2024 the lowest (249), a difference of
  54`. When `all_equal`: `the counts were the same (<n>) for <labels>`.
- `{fN}` of a fact line (R2): that line as the fact sheet has it, without its final full
  stop when it has one.

Numbers are written as before (a comma from 1,000 up). When a slot is the first thing in
the text, or the first thing after a sentence end, `fill` gives its phrase a capital first
letter; elsewhere the phrase is used as written above.

    replies.slot_phrases(result, registry) -> dict    {"count": ..., "months": ...} or {"compare": ...}
    replies.fill(text, results, registry, facts=None) -> str
    replies.check_finding(text, results, words) -> list[str]     failure codes, [] = pass
    replies.check_about(text, facts, words) -> list[str]
    replies.load_words(path=None) -> the allowed words of config/reply_words.json, lower case
    replies.check_background(text, rules) and replies.load_rules: unchanged (R7)

`results` is `AgentReply.results`, unchanged in what it holds. `facts` is
`replies.load_facts()`: fact line N (counted from 1) is `{fN}`.

**The one check for `finding` and `about_data`.** A sentence ends at `.`, `!` or `?`
followed by white space or the end of the text. The text fails for:

- `SLOT`: a `{...}` that is not a fact slot this turn offers; or no fact slot at all; or
  the same slot twice; or a `{rN.months}` that does not come straight after its own
  count: the slot before it in the text must be `{rN.count}` of the same result. (The
  months phrase names no year and no age group, so on its own it would break R0. Added by
  the planning chat on 2026-11-11, after the tests session's note.) A finding offers the
  `count` and `months` slots of this turn's count results and the `compare` slot of its
  compare results. An `about_data` text offers `{f1}` to `{fN}` only.
- `GLUE`: a slot that does not stand on its own. The character before a slot must be the
  start of the text or a space. The character after it must be the end of the text, a
  space, or one of `. , ; : ! ?`. Between two slots there must be a sentence end or at
  least one word.
- `CHARS`: outside the slots, any character that is not an ASCII letter, a space, an
  apostrophe (`'` or `’`), or one of `. , ; : ! ? ( ) - – —`. So no digit, no `%`, no
  other script, no markup, no quotation mark, no line break.
- `WORD`: outside the slots, a word that is not in the allowed list. A word is a run of
  ASCII letters and apostrophes; a hyphen separates two words; letter case is ignored and
  `’` counts as `'`.
- `SHAPE`: empty; more than four sentences; more than 600 characters once filled; for
  `about_data`, more than four fact slots.

Nothing else is checked for these two kinds: the old codes `NUMBER`, `MONTH`, `AGE`,
`UNIT`, `COMPARE`, `MEASURE`, `CLAIM` and `FINDING` are gone for them, because a word that
is not on the list fails as `WORD` and a digit fails as `CHARS`.

**`finish` with `kind` = `finding`.** As A7: it needs a result; pass gives
`fill(text, ...)` as line 1 with style `agent`; fail gives `render_fixed` with style
`fallback` and the codes in `draft_failures`; `MOCO_REPLY_STYLE` at `fixed` never uses the
text. `render_fixed`, the kept note, line 2 and every fixed row are unchanged.

**`finish` with `kind` = `about_data`.** As A7 (with results it is a finding; without
`describe_data` this turn, or on a failed check, the fixed ABOUT text with style
`fallback`). On a pass the reply is `fill(text, [], registry, facts)`, and DATA_TAG is
added when the filled text lacks the word `SYNTHETIC`. Status `EXPLAINED`.

## R2. What the tools tell the model (changes A3)

- `count_arrests`, answered: `{"result_id": "r1", "year": 2025, "age_group": "under_18",
  "slots": ["{r1.count}", "{r1.months}"]}`. The key `fields` is gone.
- `compare`: `{"result_id": "r3", "slots": ["{r3.compare}"]}`.
- `describe_data`: `{"facts": [{"slot": "{f1}", "text": "<fact line 1>"}, ...]}`.

Still no value from the data in any tool result.

## R3. `show_details` in a turn that has results (changes A3 and A10)

When the model calls `show_details` and this turn already has a result, Python reads it as
"send the answer": the turn is `ANSWERED` with the fixed rendering and the failure code
`DETAILS_THIS_TURN`. With no result in this turn, A10 applies as before.

## R4. A restricted turn never counts (changes A5)

When the guard restricted the turn and the model calls `ask_user` with `year`, Python does
not count, whatever memory holds. The turn ends `UNSUPPORTED` with the restricted code and
that code's fixed row.

## R5. The old table goes (changes A12)

When a database file is opened and holds the table `turns` of stage 2's first build, that
table is dropped with everything in it. Opening such a file still must not fail.

## R6. The turn record (adds to A9)

Each step in `turn.json` also holds `text`: what the model wrote in that step, exactly as
given, or `null`. When a check fails, the record also holds `check_details`: the words and
characters that failed. Neither is ever logged or stored in the database, and neither
appears in a reply.

## R7. What stays as it is, on purpose

- `background` and `check_background` with `config/reply_rules.json`: unchanged, and
  `MOCO_BACKGROUND` stays `off` by default. Its lists of banned words have the weakness
  this revision removes elsewhere, which is one more reason it stays off.
- A4's reading of a step with text and no tool call. A broken model's garbage therefore
  still ends as `UNSUPPORTED` / `UNRECOGNIZED_QUESTION`.
- The guard, filling and asking (but R4), comparing, `details`, memory (but R5), Slack,
  the settings, the commands, the fixed wording.

## R8. What the model is given (changes A11)

The agent prompt is `config/agent_prompt_v2.md` (the planning chat's starting text, which
the build session may reword and must log). `config/agent_prompt_v1.md` stays in the repo
unused. The thread block's `and said: "<text>"` shows the stored text with its slots
unfilled, as before.

## R9. What the tests must show, and what they cannot

Must show, with stand-ins as before:

- each fact slot fills with exactly the phrase R1 gives, with numbers from the truth file,
  including a tie in the months, every month equal, a comparison, `all_equal`, a total of
  1, and the capital letter at the start of the text and after a sentence end;
- a passing finding and a passing `about_data` text, end to end;
- each failure code of R1, with at least two texts that fail with exactly that code;
- the planning chat's 49 trick sentences rewritten for the new slots where a rewrite
  exists, plus these, all failing: a digit, a number word, a month name, an age word,
  `per day`, `roughly`, `over`, `not`, `people`, a place name, an offense, a direction
  word, a judgement word, a second language, a slot glued to a letter, to a sign and to
  another slot, an old slot such as `{r1.total}`, a slot of another turn, `{f1}` in a
  finding and `{r1.count}` in an `about_data` text;
- when a finding fails, the fixed rendering is sent and nothing the model wrote is in the
  reply;
- a word list file with a word added lets that word pass (the list is read, not copied);
- R2's tool results, R3, R4, R5 and R6;
- everything of P1A that this file does not change still holds, and stage 1's 142 tests
  are untouched and passing.

Cannot show: whether the real model writes replies that pass (the live loop check, which
counts `agent` style against `fallback`), whether the list of allowed words is wide enough
to read naturally (Nino and the planning chat read the loop check's replies), and whether
two true facts placed side by side could still mislead by what is left out.
