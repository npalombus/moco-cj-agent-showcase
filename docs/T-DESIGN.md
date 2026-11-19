# Part T: Jeffrey talks (contract)

Written by the planning chat on 2026-11-12, after the live Slack retest of stage 2. Decided
by Nino the same day (D-048, D-049): "it should be someone you can talk to ... i can have a
meaningful, natural conversation wiht him", and "i hate hardcoded responses".

What the retest showed: the counts were right and follow-ups without an @ worked, but
`hello` was answered with "Which age group do you mean", `How are you doing today` with "I
couldn't read that as a question I can answer", `thanks` with the stock description of the
data, and `can you answer more concisely` with the same sentence again. In 3 of 5 answers
the program replaced his sentence with its own.

What does not change: Python makes every figure and writes every fact as a whole phrase;
the model never sees a value; the floor; the guard that runs before the model; the data
tag on every reply that holds a fact; who may use him; rate limits; memory and `details`.

## T0. One setting, and nothing changes when it is off

`MOCO_TALK`: `off` (the default) or `on`. Any other value is a ConfigError naming the key.
With `off`, everything behaves exactly as it does today in both data modes, and every
existing test passes untouched. Everything below applies only with `on`.

With `on` the prompt file is `config/agent_prompt_talk.md` (SYNTHETIC data) or
`config/agent_prompt_s3_talk.md` (county data, with the sources listed after it as today).
The rules file is `config/talk_rules.json`. The planning chat writes all three; the build
session may change the two prompt files only as T9 says.

## T1. A new way to end a turn: `talk`

`finish` takes a fourth kind, `talk`, with the model's own text. It is for a message that
is not a request for a count and not a question about the data: a greeting, a thanks,
small talk, a question about him, a remark about his last answer.

- In a turn that has results, a `finish` of any kind is a finding, as today.
- The text is checked by the **talk check**. It fails with these codes:
  - `NUMBER`: a digit, `%`, a word of `number_words` or `month_names`
    (`config/reply_rules.json`);
  - `LABEL`: in county mode, any label of any category or flag field of any loaded source
    (whole words, any letter case); in SYNTHETIC mode, any age wording of the registry;
  - `CLAIM`: a phrase of `claim_phrases`;
  - `CHARS`: a character that is not a letter, a space or one of `allowed_marks`; a brace;
    a private-use character (C13); anything of `markup` in `reply_rules.json`;
  - `SHAPE`: empty, more than `most_talk_sentences_in_talk` sentences, more than
    `most_chars_talk` characters, or a line break.
- A text that passes is sent as it is: one plain message, no chart, no data tag, no second
  line, no "kept" note. Status `TALKED`, kind `talk`, style `agent`.
- No whitelist of words applies to talk. That is the point.

## T2. A finding may hold sentences of his own

With `on`, the check of a `finding` (and of `about_data`) works sentence by sentence.

- A **fact sentence** holds at least one slot. Everything of R1 and C13 applies to it as
  today: only the allowed words, the joining rule, the characters, the slot rules.
- A **talk sentence** holds no slot. The talk check's `NUMBER`, `LABEL`, `CLAIM` and
  `CHARS` apply to it, and `JUDGE`: no word or phrase of `judgement_words`. The whitelist
  does not.
- For the whole text: `SLOT` as today (at least one slot, none twice, each one offered, a
  months or groups slot straight after its own count slot); `ORDER`: no talk sentence
  between the sentence of `{rN.count}` and the sentence of `{rN.months}` or `{rN.groups}`
  of the same result; `SHAPE`: at most 4 fact sentences, at most
  `most_talk_sentences_in_finding` talk sentences, at most `most_chars_finding` characters
  once filled, one line.
- What Python adds after line 1 (the kept note, the tables, the fixed lines, the data tag
  or source line) is unchanged.

Example that passes: `Here you go. I counted {r1.count}. {r1.months}. Want it compared
with another year?` Examples that fail: `I counted {r1.count}. That is a lot.` (`JUDGE`);
`I counted {r1.count}. It went up because of summer.` (`CLAIM`); `I counted {r1.count}.
Twice last year.` (`NUMBER`).

## T3. One second try

The first time in a turn that a `finish` text fails its check, and the turn has at least
one step and five seconds left, the turn does not end. `finish` answers

    {"error": "REWRITE", "problems": [codes], "found": [...], "do": "<hint>"}

`found` is at most five of the offending words, phrases or characters, taken from the
model's own text, in lower case. `do` is the `rewrite_hints` line of the first code. The
model may call `finish` once more. If that text passes, the reply's style is `agent`. If
it fails too, or there is no step or time left, the turn ends as today: with results, the
fixed rendering (style `fallback`); for `about_data`, the fixed text; for `background`,
the fixed refusal; for `talk`, the `fallback_line` of `config/talk_rules.json` (status
`TALKED`, style `fallback`). The saved turn keeps the codes of both tries
(`first_failures`, `failures`). Nothing but the model's own words is given back to it.

## T4. Records, log, memory

A talk turn is saved in the thread like any other turn, with the user's message and the
text he sent, and is shown to the model in later turns of that thread within the usual
limit. It has no run, is skipped by `details` and by the filling of year, group, source,
period and filters, and is not written to the request log. The log line's label is
`talked`.

## T5. Slack

`help`, `reset`, `details`, the thread rules and the "One moment." line are unchanged. A
talk reply is never preceded or followed by another message of his.

## T6. Background, with his reasoning made explicit (D-049)

Still governed by `MOCO_BACKGROUND`, and all of today's checks stay (no number, hedged,
no advice, nothing stated as certain). Nino's condition for turning it on: "it should be
on only if he makes his reasoning explicit". So with `MOCO_TALK` on, a background text
must also pass `REASON`: it holds at least one phrase of `reason_phrases` (why the
possibility is plausible) and at least one phrase of `check_phrases` (what records would
be needed to check it), both in `config/talk_rules.json`. A text that offers a possibility
with no reasoning, or with no way to check it, fails. A failed background text gets T3's
second try, and after a second failure the fixed refusal as today. The fixed words Python
puts before and after a background text are unchanged.

## T7. What the tests must show

- `MOCO_TALK` unset or `off`: the tools offered, the prompt file, every check and every
  reply are as today (the existing tests are this proof; add three that say so directly).
- The talk check: one passing text and one failing text for every code; the labels of a
  county fixture source; a private-use character; the limits at their edges.
- T2: fact and talk sentences mixed, each example above, each code, `ORDER`, the limits at
  their edges; that a whitelist miss in a talk sentence passes and in a fact sentence
  still fails `WORD`; `about_data` the same way.
- T3: a failing first text gets `REWRITE` with the right codes, `found` and hint; a passing
  second text is sent with style `agent`; a failing second text falls back, for each of
  the four kinds; no second try without a step or without five seconds; never a third;
  `found` holds nothing that was not in the model's text.
- T1 end to end with the stand-in model, in both data modes: status, kind, style, the text
  sent as it is, one message, no data tag, no chart; a finish in a turn with results is a
  finding.
- T4: the saved turn, the context of the next turn, `details` and filling skip it, the log
  label, nothing in the request log.
- No figure can reach a reply through talk: digits, number words, months, labels.
- T6: a background text with reasoning and a way to check passes; one without the
  reasoning fails `REASON`; one without the way to check fails `REASON`; the second try;
  with `MOCO_TALK` off the background check is exactly as today.

## T8. What the tests cannot show

That he sounds natural. That is T9 and Nino's own try in Slack.

## T9. The live check (build session)

`tools/loop_check.py` gains `--talk`: it sets `MOCO_TALK=on` for the run and understands
two more keys in a case's `expect`: `no_digits` (the reply text holds no digit) and
`styles` (the styles that pass). Run it on `config/loop_check_cases_talk.json`, 3 runs a
case, with `--background`, on `nvidia/nemotron-3.5-lightning-30b-a3b` with thinking off, and then the existing
`config/loop_check_cases.json` with `--talk` as well, so it is known what talk does to the
counting cases. Save both outputs.

Aim, not a gate: every must case passes in at least 2 of 3 runs, and at least 8 in 10 talk
replies are in his own words (style `agent`). To get there the build session may change
`config/agent_prompt_talk.md` and `config/agent_prompt_s3_talk.md`, and nothing else in
`config/`: every change is listed in `kit-log/raw/T-B-prompt-changes.txt` with the reason,
no loop check question is used as an example, and no rule about figures, groups, places,
judgement or advice is weakened. At most four prompt rounds.

# Round 2 (T10 to T15), written 2026-11-12 after the first live run

Why: in the one full live run (`kit-log/raw/T-B-talk-run1.txt`) 22 of 39 talk replies fell
back to the stock line. All 22 failed `CHARS` (line breaks, dashes, the non-breaking
hyphen), 16 of them were plain text with no tool call and so got no second try, and a
self-introduction of five sentences was replaced by "I'd rather not say something I can't
back up". None of those 22 held a wrong figure. Round 2 stops the program from throwing
away a reply for how it is laid out. It weakens nothing about figures: `NUMBER`, `LABEL`,
`CLAIM`, `JUDGE`, `REASON` and everything of R1 in a fact sentence stay exactly as they are.
Everything below applies only with `MOCO_TALK` on.

## T10. A finish text is tidied before it is checked

Every finish text of every kind, and a plain-text reply read as one, is tidied first. The
tidied text is what is checked, what is sent and what is saved as the reply. The step log
keeps what the model wrote, exactly, as today (R6). Tidying, in this order:

1. U+2010 and U+2011 (hyphen, non-breaking hyphen) become `-`. U+00A0, U+2007, U+2009 and
   U+202F (the no-break and thin spaces) become a plain space.
2. These are removed: `*`, the backtick, U+FE0F, U+200D, and every character whose Unicode
   category is `So` or whose code point is U+1F3FB to U+1F3FF (pictures and emoji).
3. Every run of white space (spaces, tabs, line breaks, U+2028, U+2029) becomes one plain
   space, and the ends are trimmed.

So a line break can no longer fail `SHAPE` in a talk text or a finding ("a line break" in
T1 and "one line" in T2 cannot occur after tidying). A text that is empty after tidying
fails `SHAPE` as an empty text does. A private-use character is not removed and still
fails `CHARS` (C13). A digit written as a picture is removed with the other pictures; a
digit left behind by one (the `1` of a keycap) still fails `NUMBER`.

## T11. More marks in a talk sentence

`allowed_marks` of `config/talk_rules.json` (version 2) gains `"`, U+201C, U+201D, U+2013
(en dash), U+2014 (em dash) and U+2026 (ellipsis). They apply to a talk text and to a talk
sentence of a finding. A fact sentence keeps R1's characters.

## T12. Longer talk

`most_talk_sentences_in_talk` is 6 (was 4) and `most_chars_talk` is 700 (was 500). The two
limits for a finding do not change.

## T13. A plain-text reply gets its second try too

Today (T3, the build's reading 7) a model step with text and no tool call is read as a
finish, checked, and ended with no second try. From round 2 it gets one, on T3's
conditions (the first failing finish text of the turn, a step and five seconds left).
There is no `finish` call to answer, so the turn goes on with these two messages added
after the ones the model has seen:

    {"role": "assistant", "content": <the model's text, exactly as it wrote it>}
    {"role": "user", "content": "PROGRAM NOTE (not from the person). Your reply was not sent. " + <the REWRITE object of T3, as JSON>}

The model's next step is its second try, whether it calls `finish` or writes plain text
again. Everything else of T3 holds: never a third try, the same fallbacks, both tries'
codes saved. This applies to plain text read as `talk`, as a finding and as `about_data`.

## T14. A talk text that is only too long is cut, not replaced

When the text that ends a `talk` turn (after the second try, or with none left) fails
`SHAPE` and no other code, and is not empty, he sends its leading sentences instead of the
fallback line: as many whole sentences from the start as fit within both limits of T12,
joined by one space. If the first sentence alone is over `most_chars_talk`, the fallback
line as today. The reply is status `TALKED`, kind `talk`, style `agent`; the saved turn
keeps `failures` (`["SHAPE"]`) and gets `"cut": true`. Nothing is cut in a finding, an
`about_data` text or a background text.

## T15. What the round 2 tests must show

- T10: each of the three steps alone and together, for a talk text and for a finding; the
  text sent and saved is the tidied one and the step log is the model's own; a text of
  only removed characters is empty; a private-use character still fails; a keycap digit
  still fails `NUMBER`; with `MOCO_TALK` off nothing is tidied.
- T11: each new mark passes in a talk text and in a talk sentence of a finding, and still
  fails `CHARS` in a fact sentence.
- T12: the edges at 6 and 7 sentences and at 700 and 701 characters.
- T13: the two added messages, exactly; a passing second try as a `finish` call and as
  plain text; a failing second try falls back; no second try without a step or without
  five seconds; never a third; for talk, a finding and `about_data`.
- T14: seven short sentences are cut to six; a text over 700 characters is cut at a
  sentence end; one sentence over 700 characters gets the fallback line; `SHAPE` with any
  other code is not cut; `"cut": true` is saved; nothing is cut in a finding.
- No figure through talk still holds after tidying: digits, number words, months, labels.

## T16. Answers to the round 2 tests session (2026-11-13)

The tests session listed its readings in `kit-log/raw/T2-A-notes.txt`. The planning chat's
answers, so the check of the build has one text to hold it to. Its readings 3 to 9 and 14
stand as it took them.

1. **The dashes in a fact sentence (its reading 1): the tests session is right and T15's
   line was wrong.** R1 already allows the en dash and the em dash in a fact sentence, and
   round 2 changes nothing of R1 there. In a fact sentence the straight and curly
   quotation marks and the ellipsis fail `CHARS`; the two dashes pass, as before.
2. **`finish_text` (its reading 2)** stays exactly what the model gave `finish` (A9), not
   tidied. The reply, and the turn stored for later, hold the tidied text.
3. **`found` (its point 10)** is taken from the tidied text, because that is the text the
   check reads. An item can therefore differ from the model's own characters by white
   space.
4. **No step or time left after a REWRITE (its point 11):** the turn ends as the first
   try would have, and T14 applies to it: a first try that failed only `SHAPE` is cut and
   sent.
5. **A tool call after the note (its point 12):** the model's next `finish` or plain text
   is its second try, whatever it calls in between, within the turn's steps and time.
6. **`draft_failures` of a cut turn (its point 13)** is `["SHAPE"]`, the same as the saved
   turn's `failures`.
7. **`no_digits` in the live check (T9)**, from the fresh session's check of the build
   (`kit-log/raw/CHAT-BUILDS-check.txt`, DEFECT 2): T9 said "the reply text holds no
   digit". That was wrong for a fixed refusal, which names the years it covers. `no_digits`
   is checked on a talk reply (status `TALKED`) only, which is what `tools/loop_check.py`
   does since round 2. A wrong kind of reply is still caught by `kind`.
8. **"Every run of white space" in T10 (the same check, PROOF GAP 2)** means every
   character Python's `\s` matches, not only the five T10 names: also the vertical tab, the
   form feed, U+0085, U+2002 to U+200A, U+3000 and U+001C to U+001F. Each becomes one
   space. Tested in the gaps round (`briefs/GAPS-A-tests.md`).
