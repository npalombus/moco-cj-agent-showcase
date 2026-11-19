# Stage 3, Part A: real county data, any count it can support (the contract)

Written by the planning chat on 2026-11-12. Plans: `docs/PLAN-S3.md` (approved, D-039) and
`docs/PLAN-S3-STATS.md` (approved, D-040). Replaces `docs/S3A-DESIGN-draft.md`. It ADDS to
the agent loop as built (`docs/P1A-DESIGN.md` with `docs/P1A-R2-DESIGN.md`); it changes
nothing in it. Stage 1 does not change at all.

Part A is counting only. Statistics, charts and R are Part S (`docs/S3S-DESIGN.md`, to
come). Automatic refresh is Part B.

## C0. The one structural decision: county mode is added beside synthetic mode

A new setting `MOCO_DATA` is `synthetic` (the default) or `county`.

- `synthetic`: everything behaves exactly as today. Every existing test stays as it is and
  must still pass. `count_arrests` and the made-up source are not touched.
- `county`: the model is offered `count`, `share`, `compare`, `describe_data`, `ask_user`,
  `show_details`, `decline`, `finish` (no `count_arrests`), the prompt is
  `config/agent_prompt_s3.md`, and only county sources can be counted.

Real and made-up data therefore never meet in one turn, by construction.

## C1. What must not break (adds to A0 and R0)

- Every number a person sees comes from Python, inside a whole phrase Python wrote.
- No reply, tool answer, log line, stored turn or `details` text ever holds a single
  record of a source, and no count from 1 to 9 is ever shown as a figure.
- Every county answer names its source and the date of the copy it used.
- Answers are computed from a saved copy, never from the live site while answering.
- Sources are never blended: no difference, share or comparison across two sources.

## C2. Words

**Source**: one approved dataset, described by one file. **Copy**: one dated download of a
source with a fingerprint. **Spec**: what to count: a source, a period, filters, and at
most two things to break it down by. **Group**: one line of a breakdown. **Left out**:
records that match the question but cannot be placed (no district recorded, age not
usable); always counted and said. **Hidden**: a count from 1 to 9, shown as `fewer than 10`.

## C3. Source files (registry version 3)

One file per source in `config/sources/<name>.json`. `config/registry.json` is not edited.
Nothing about a source lives in code. No session may edit a source file; the planning chat
writes them and each carries its approval record.

    {
      "id": "MOCO:police_arrests", "data_class": "COUNTY_OPEN_DATA",
      "title": "Montgomery County Police arrests",
      "publisher": "Montgomery County, Maryland (dataMontgomery)",
      "address": "https://data.montgomerycountymd.gov/resource/bep7-ghja.json",
      "page": "https://data.montgomerycountymd.gov/d/bep7-ghja",
      "unit": {"one": "arrest record", "many": "arrest records"},
      "is_not": ["people", "charges", "cases", "convictions", "sentences", "a rate"],
      "time_field": "event_date_time", "coverage_start": "2021-01-01", "floor": 10,
      "fields": [ ... ], "notices": [ ... ],
      "approved_by": "Nino", "approved_on": "2026-11-11", "approval_record": "D-039"
    }

A field is one of four kinds:

| Kind | In the file | Filter | Break down by |
| --- | --- | --- | --- |
| `age` | `usable: [10, 98]`, `bands: [[10,17],[18,24],[25,34],[35,44],[45,54],[55,98]]` | `{"field":"age","from":18,"to":21}`; either end may be missing | `age_band` only |
| `category` | `values`: each raw value mapped to a `label`; `wording`: `"in {labels}"` or `"recorded as {labels}"`; `dimension`: `"district"`; `person: true/false`; `sensitive: true/false` | `"is": label` or `"in": [labels]` | yes |
| `flag` | `yes_raw`, `no_raw`, `yes`: `"within 500 feet of a school"`, `no`: `"not within 500 feet of a school"`, `dimension` | `"is": true/false` | yes |
| `key` | nothing else | never | never; never shown |

Several raw values may map to one label (`"W"` and `"White"`). A raw value the file does
not list, or an empty one, puts the record in **left out** for any spec that uses that
field. An age outside `usable`, or not a whole number, does the same.

The time field allows the period (C5) and, as filters, `{"field":"weekday","in":[...]}`
and `{"field":"hour","from":22,"to":5}`; as breakdowns `year`, `month`, `weekday`, `hour`.

## C4. Copies

    sources.load_sources(folder=None) -> dict by id          # reads config/sources/*.json
    sources.fetch(source_id, *, state_dir, transport=None, now=None) -> Copy
    sources.latest(source_id, *, state_dir) -> Copy | None

- A copy is a folder `<state_dir>/copies/<source name>/<UTC time>/` (not in git) holding
  `rows.jsonl` (only the fields the source file lists) and `copy.json`: source id, time
  fetched, number of rows, newest record time, field list, sha256 of `rows.jsonl`.
- `fetch` downloads every row through `address`, in pages, ordered so that pages cannot
  overlap. It then checks: every listed field is present in the service's answer; the row
  count is not below the last good copy's by more than 2 in 100; the newest record is not
  older than the last good copy's. Only then is the copy made current (a small file
  `current` naming it). A failed check, a network error, or an answer that is not a list
  of rows (for example a redirect or an error page) leaves the last good copy in use and
  raises `FetchFailed` with the reason.
- The only address ever contacted is the source file's `address`. Tests use a fake
  transport; no test touches the network.
- New command `python -m moco_agent fetch <source id>`: runs `fetch` once, prints the
  copy's date, rows and fingerprint, or the reason it failed. New setting `MOCO_STATE_DIR`
  (default: the project's `var/`).
- With no current copy, a `count` on that source ends the turn with the fixed line
  `NO_COPY`. Nothing is fetched while answering.

## C5. The `count` tool

    count(source, period, filters, group_by)

- `source`: a source id. May be left out when exactly one county source has a copy;
  otherwise Python ends the turn asking which, with the fixed row `NEEDS_SOURCE` listing
  the titles.
- `period`: `{"year": 2025}`, `{"years": [2024, 2025]}`, `{"year": 2025, "months":
  {"from": 1, "to": 10}}`, or `{"from": "2025-03-01", "to": "2025-08-31"}`. Left out:
  filled from memory (C9), else Python asks, as A5 does for the year today.
- `filters`: a list, at most one per field.
- `group_by`: none, one or two of: a category or flag field, `age_band`, `year`, `month`,
  `weekday`, `hour`.

Python checks the whole spec against the source file before counting. A bad spec is a tool
error and the turn goes on:

| Error | When |
| --- | --- |
| `BAD_FIELD` | a field the source lacks, a `key` field, or a field used in a way its kind does not allow |
| `BAD_VALUE` | a label the file does not list; a range the wrong way round; a period that is not a real date range |
| `OUT_OF_COVERAGE` | a period wholly outside the copy; the error names what is covered |
| `NOT_ALLOWED` | an age filter narrower than two years that touches any age below 18; `age_band` with bands other than the file's |
| `TOO_FINE` | more than half of the groups that have any record would be hidden; the error names the breakdowns that would not be |
| `TOO_MANY` | more than two breakdowns, more than 400 groups, or a ninth `count` in the turn |
| `PARTIAL_YEAR` | see C7 |

A good spec makes a result and Python answers the model, with no value from the data:

    {"result_id": "r1", "read_as": "<the count phrase without its number>",
     "slots": ["{r1.count}", "{r1.groups}"]}

`{rN.groups}` is listed only for a one-way breakdown. `read_as` lets the model see how its
request was understood.

**The record.** Every count saves stage 1's kind of record: the spec, the copy's
fingerprint and date, the exact figures, the figures as shown, what was left out, the
limitations.

## C6. The phrases Python writes

Numbers have a comma from 1,000 up. A hidden value is written `fewer than 10`.

**The count phrase**, `{rN.count}`: `<total> <unit> <what> <period>`, parts separated by
one space, `<what>` possibly empty. Example: `212 arrest records of people aged 18 to 21,
recorded as female in district 3 in 2025`.

`<what>` is built from the filters in this fixed order:

1. Person fields (`age`, then each `category` with `person: true` in file order), written
   after `of people `; the first fragment follows directly, later ones are joined with
   `, `. Age fragments: `aged 18 to 21`; `aged 30 and over`; `under 18` (only `to`, written
   as one more than `to`); `aged 21` (both ends equal). Category fragments: the field's
   `wording` with its labels joined as `analysis.join_and` does.
2. Every other category in file order, by its `wording` (`in district 3 and district 4`).
3. Every flag in file order (`within 500 feet of a school`).
4. `weekday`: `on weekends` (exactly Saturday and Sunday), `on weekdays` (exactly Monday
   to Friday), else `on Monday and Friday`. `hour`: `between 10 pm and 5 am`.

`<period>`: `in 2025`; `in 2024 and 2025`; `from January to October 2025`; `from 1 March
2025 to 31 August 2025`. A period that reaches past the copy's newest record is cut to it
and written with ` (through 9 November 2026, the latest in this copy)` at its end.

**The groups phrase**, `{rN.groups}`: `by <dimension>, <top> had the most (<n>) and
<bottom> the fewest (<n>)`. Ties are written as the months sentence writes them (`district
3 and district 4 had the most (50 each)`). All equal: `by <dimension>, every group had the
same count (<n>)`. Groups are every value the file lists (or every period in the range),
including those with 0. Dimensions: the field's `dimension`, or `year`, `month`, `day of
the week`, `hour`, `age band`. Labels: the file's labels; `March 2025`; `Saturday`; `10
pm`; `ages 18 to 24`.

**The share phrase**, `{rN.share}`: `<p>% of the <whole's count phrase> were <part>`,
where `<part>` is the `<what>` of the filters the part adds (`of people under 18`; `in
district 3`). `<p>` is the nearest whole number; above 0 and below 0.5 it is written
`under 1`.

**The compare phrase**, `{rN.compare}`: as R1 writes it, where each result's label is the
part of its count phrase on which the compared specs differ (`2024`; `district 3`; `people
aged 18 to 21`). If any compared value is hidden, the phrase ends after the lowest value
and states no difference.

`replies.slot_phrases` gives these for county results. `{rN.groups}` and `{rN.share}`
follow R1's rules for a slot; `{rN.groups}` must come straight after its own `{rN.count}`
(the same rule as `{rN.months}`, for the same reason).

## C7. `share` and `compare`

- `share(part_id, whole_id)`: both from this turn and the same source; the part's spec
  must be the whole's spec plus one or more filters; neither value hidden; else a tool
  error (`BAD_SHARE`). Never called a rate.
- `compare(result_ids)`: single counts of the same source (`MIXED_SOURCES` otherwise).
- **A partial year.** When compared periods are whole years and one of them is the copy's
  last, unfinished year, `compare` answers `PARTIAL_YEAR` with the last finished month `M`,
  and the model counts both again with `"months": {"from": 1, "to": M}`. Python, not the
  model, decides `M`.

## C8. Privacy, in code (applied to every result before any slot is filled)

1. **The floor** is the source file's `floor`. A value from 1 to floor − 1 is hidden. 0 is
   shown as `0`. This covers totals, groups, left-out counts, tables and `details`.
2. **Totals stay exact** (D-034). Nothing is rounded and no second group is hidden. When
   any group is hidden Python adds: `Counts under 10 are not shown here; the county's open
   data has every record: <page>.`
3. **Never a row.** No tool returns records; `details` shows totals and tables only.
4. **Under 18**: `NOT_ALLOWED` as in C5.
5. No difference or share is computed from a hidden value.
6. The floor governs what the agent states. It is not a secrecy guarantee (a hidden group
   can be found by subtraction, and the county publishes every record). The fact sheet
   says so.

## C9. Memory and filling

A5's rule ("stated, else pending, else the last answer's") applies part by part: the
source, the period, and each filter by field. What was kept is said: `(I kept 2025 and
district 3 from earlier.)`. A new filter on a field replaces the old one; a `filters`
entry `{"field": "district", "clear": true}` removes it. A stored turn holds specs and
slot texts, never a value.

## C10. The reply

The model writes line 1 with slots, checked by R1's one check with the slots of C6 on
offer. The fixed rendering, used when the check fails, is `I counted <count phrase>.`
followed by ` <Groups phrase>.` when there is one, per result, then share and compare
phrases as sentences.

Python then adds, in this order:

1. the table of a breakdown: one line per group, `<label>: <n>`, at most 12 lines; a longer
   one or a two-way one is given in `details` only, with the line `The full table is in
   the details.`;
2. the kept note;
3. left out, when anything was: `(<n> had no <dimension> recorded and are not included.)`
   or, for age, `(<n> had no usable age and are not included.)`;
4. the hidden line of C8;
5. the sensitive line, when the spec filters or breaks down by a `sensitive` field: `These
   are counts of <unit many>, not rates, and they show no cause.`;
6. the source line. First answer of a thread: `Source: <title> (county open data), copy of
   <date>. A count is of <unit many>, not people. Want the details, or a different
   breakdown?` Later: `(County open data, copy of <date>.)`

No chart in Part A. Charts come with Part S.

## C11. About the data, details, help

- `describe_data` in county mode gives fact lines generated from the source files: for each
  source its title, what one record is, the period its copy covers, each field in plain
  words, what cannot be asked, the floor, and what is left out.
- `details` and `about_data` answers carry the source's `notices` word for word (the
  county's disclaimer), and the fixed line that the agent is a university course project
  and not a county service.
- `help` and the "what I can do" sentence are generated from the source files.

## C12. What the tests must show, and what they cannot

With two made-up fixture sources in `tests/s3/fixtures/` (one shaped like Police Arrests;
one with coded labels such as `W` and `3D`, a different unit and no flag), each with a
truth file the tests compute by plain counting, with no network and no real key:

- `MOCO_DATA=synthetic`: nothing changed (the existing suite, untouched, still passes);
- every row of C5's error table; a spec the file allows gives the truth file's figures;
- every phrase of C6 exactly, including each age fragment, two person filters, a tie, all
  equal, a period cut to the copy, `under 1`, and a hidden value in each place;
- the floor in every place a number can appear, with 0, 1, 9 and 10 each tested;
- totals exact; the hidden line exactly when a group is hidden; left out counted and said;
  the sensitive line exactly when C10 says;
- no age filter narrower than two years below 18, by any wording of the spec;
- no record and no hidden figure in any reply, tool answer, log line, stored turn or
  `details`;
- `share`, `compare`, `MIXED_SOURCES`, `PARTIAL_YEAR`;
- filling and keeping part by part, and `clear`;
- `fetch`: paging, each failed check, an error page, a redirect; a failed fetch leaves the
  last good copy in use; the fingerprint is in every record;
- R1's check accepts and refuses the new slots as it does the old ones.

Cannot show: that the real model builds good specs (the loop check in county mode, each
case three times); that the figures are right on the real data (the planning chat's
reference answers, kept outside the repo); that the county's site behaves (the live fetch).

## C13. Two repairs to R1's check, for both modes

Found by the planning chat's attack on the revision 2 build
(`kit-log/raw/P1A2-B-chat-check.txt`): 2 of 76 new trick texts got through.

1. **Only `and` may join two slots in one sentence.** When two slots stand in the same
   sentence, the text between them must be exactly ` and ` or `, and `. Anything else there
   fails `GLUE`. Why: `{r1.count} of the {r2.count}.` passed, and it reads as one count
   being a part of the other, which Python never checked. Slots in different sentences are
   not affected, so `I counted {r1.count}. {r1.months}. I also counted {r2.count}.` still
   passes.
2. **No private-use character.** Any character from U+E000 to U+F8FF in the model's text
   fails `CHARS`. Why: the build marks slots with U+E000 inside the check, so that one
   character slipped through when the model typed it.

The tests session adds tests for both. It may change a test in `tests/p1/` only where a
text that passes today breaks rule 1, and lists each such change in its notes.

## Round 2 additions (2026-11-12): C14 to C22

Written by the planning chat after its check of the Part A build
(`kit-log/raw/S3A-B-chat-check.txt`) and the tests session's notes
(`kit-log/raw/S3A-A-notes.txt`, points B and D). Where a rule here changes a phrase or a
line of C6 or C10, this section wins. They are tested and built together with Part S.

## C14. Fields the county wrote as free text (D-044)

Some sources hold a person field as text typed by hand (`BLK`, `BLACK`, `B`). A source
file may map those spellings to one label, exactly as C3 already allows, and then marks
the field `"interpreted": true` and gives it a `coverage`: one sentence, written by the
planning chat when the file was made, saying how many records carry a value that is used
and how many are left out. The file also carries, at the top level, an
`interpreted_line`: one sentence saying that the county recorded these fields as free
text and that the agent grouped the spellings. (Example: the source file for mental
health calls.)

Rules:

- A spec that filters or breaks down by an `interpreted` field gets the source's
  `interpreted_line` as a fixed line, placed after the sensitive line and before the
  source line (C10 gains a step 5a; S5 gains a step 6a). Once per reply, however many
  interpreted fields the spec uses.
- `about the data` (C11) lists interpreted fields under their own heading, `Grouped by
  the agent from free text:`, one line per field: `<dimension>: <coverage>`, then the
  `interpreted_line`.
- A field with `"interpreted": true` in a file that has no `interpreted_line`, or a
  field with `"interpreted": true` and no `coverage` text, makes the source file invalid
  (C3's loading error); the source is not offered.
- Nothing else changes: unlisted spellings still put a record in left out, the floor
  still applies, and an interpreted field that is `sensitive` gets both lines.

## C15. A breakdown that leaves records out says so in its count sentence

Found on the real data: "I counted 8,342 arrest records in 2025" for a breakdown by
district, when the year holds 8,394 and 52 have no district. Every figure was true and the
sentence still misled.

When records are left out because of a field the spec **breaks down by**, the count phrase
ends with what the counted records have: ` with a <dimension> recorded` for a category or
a flag, ` with a usable age` for `age_band`; two such fields are joined with `and`
(`with a district and a bureau recorded`). Example: `8,342 arrest records in 2025 with a
district recorded`. The total itself does not change, and the left-out line of C10 still
follows. Records left out because of a **filter** change nothing in the phrase (`208
arrest records of people aged 18 to 21 in district 3 in 2025` is already exact). `read_as`
does not carry the ending.

## C16. Hidden values are never ranked against each other

Found on the real data: two groups under 10 were written as tied (`fewer than 10 each`),
which says they are equal; two different hidden values would have been written as highest
and lowest, which says which is larger.

- **Groups phrase.** When no group is 0 and at least one group is hidden, the fewest side
  names **every** hidden group, in group order, with `(fewer than <floor> each)`; with one
  hidden group, `(fewer than <floor>)`. This is the wording whether their real values are
  equal or not. When a group is 0, the fewest side is the groups with 0, as today.
- **Compare phrase.** A hidden value is never called the highest. When no compared value is
  0, the lowest side names every hidden result, `(fewer than <floor> each)` or `(fewer
  than <floor>)` for one. When every compared value is hidden, the phrase is `the counts
  for <labels> were each fewer than <floor>`. When some are hidden and the rest are 0:
  `<hidden labels> each had fewer than <floor> and <zero labels> had 0` (`each` only for
  two or more). No difference is stated whenever a hidden value is in the phrase (C8.5).
- The table and `details` already show `fewer than <floor>` per group and do not change.

## C17. `year` with `month` in one breakdown

`group_by` holding both `year` and `month` is `BAD_FIELD` (`month` already names the year:
`March 2025`). It made a grid of every year against every month label.

## C18. The later source line names its source

C10's later line becomes `(<title>, county open data, copy of <date>.)`. The first-answer
line is unchanged.

## C19. Which result a line belongs to

When a reply holds more than one count result and at least one of them has a left-out
line or a hidden line, each left-out line starts with `For <read_as>: ` and loses its
brackets: `For arrest records in 2025: 52 had no district recorded and are not included.`
The hidden line stays one line for the whole reply.

## C20. A source file is checked when it is loaded

`sources.load_sources` checks every file's shape: the keys of C3, a known kind for every
field, a `floor` of at least 2, labels that are not empty, C14's two rules. A file that
fails is not offered; the others still are. The reason is logged once at start, shown by
`python -m moco_agent fetch <id>` (which ends with a code other than 0), and `about the
data` does not list the source. Nothing about the failure is given to the model.

## C21. Under 18, inside one turn (APPROVED by Nino, D-059, 2026-11-13; round 5)

The rule: no reply holds figures from which the number of records of ONE year of age
under 18 follows by adding and subtracting them. `count` refuses the request that would
make it so. (C8.4 is the simplest case of it: one figure that is itself one year.)

**The figures of a count, their ages and their kind.** A count gives its total and, with a
breakdown, one figure per group (per cell with two breakdowns). Whether a figure is shown
or hidden under the floor makes no difference here.

- The ages of the total: the count's age filter, cut to the usable ages; with no age
  filter, every usable age.
- A group of `age_band`: the band cut to the count's ages; a band with nothing left gives
  no figure.
- A group of a category or flag field: the count's ages; it is of the kind of a count that
  has that one label (that yes or no) as its filter on that field. If the count already
  filters that field, only the labels its filter allows give figures.
- The groups of `year`, `month`, `weekday` or `hour`: the count's ages; they are of one
  kind of their own, "the count's filters, by that breakdown".
- Two figures are of the same kind when they have the same source, the same days as their
  period (however the period is written: `{"year": 2025}` and 1 January to 31 December
  2025 are the same), and, after the lines above, the same filters on every field but
  the age.

**The check.** Before a count is made, Python takes the figures of the turn's counts so
far (those that were answered with a result) and of the new request, kind by kind. If,
within one kind, some of the figures added and subtracted (each taken any number of
times) cover exactly one year of age, and that year is under 18, the new request is
answered `NOT_ALLOWED`, field: the age field, `why`: `with this count, the figures of
this message would give one year of age under 18`. Nothing is counted or saved for it,
and it does not use up one of the turn's counts. The check comes after C5's own checks and
after the reuse of an identical count of the turn.

Refused, for example: under 17 after under 18 (the 17-year-olds); 11 and over after all
ages (the 10-year-olds); 14 to 15 after 10 to 16 and 10 to 13 (the 16-year-olds, from
three counts); 17 to 20 by `age_band`, on its own (the band 10 to 17, cut to 17);
Female aged 10 to 17 after 10 to 16 by sex. Allowed: under 18 and 18 to 24; under 18 and
under 16 (two years); 18 to 21 and 19 to 21 (the year is 18); the same ages in another
year or another district (another kind).

`compare` and `share` need no rule of their own: they only use counts of the turn.

**What this does not do.** Across turns nothing changes (C8.6): the same counts asked in
two messages are both answered. Figures of different kinds are not added together (the
two sexes summed, two periods summed), and Part S's analyses are not looked at. The floor
and this rule govern what the agent states in one reply; they are not a secrecy
guarantee, and the county publishes every record.

## C25. The period question when no source is known (round 5)

Found by the fresh check of C24 (`kit-log/raw/CHAT-BUILDS-check-2.txt`, PROOF GAP 2): the
model may itself call `ask_user` with missing `period`, and then no source is known to
C24, so the question listed every source (1,234 characters with thirteen).

When the model calls `ask_user` with missing `period`:

0. The first time in a turn, the turn does not end: the model gets the tool error
   `NO_PERIOD_QUESTION`, why: `Do not ask for the period. Call the tool again with the
   period left out: analyze uses every month; count asks the person itself.` (The live
   run: an analysis question ended in a source question.) Points 1 to 3 apply from the
   second time.

1. The source is the one the thread already has: the source of the turn that asked (its
   pending request), else the one source of the most recent earlier turn with counts
   (C9's rule for what is kept). If there is one and it has a copy, the question is C24's,
   naming that source only, and that source is kept with the question, so the answer
   "2024" is counted from it.
2. If no source is known that way and three or more sources are offered, Python asks for
   the source first, with C23's question (`Which source do you mean? I have <n>:
   <list>.`), exactly as if the model had asked with missing `source`. The period is
   asked afterwards, by C5's own rule, once the source is known.
3. With one or two sources offered, nothing changes: today's period question.

`ask_user` with missing `source` or `other` is unchanged.

## C26 to C28. Three things the live run of 13 November showed (round 5)

From the live check of 38 questions against the real model
(`kit-log/raw/S3-county-check-live-2026-11-13.txt`): three questions failed for reasons on
Python's side. What the model did each time is in that record.

**C26. A breakdown that can only have one group is dropped.** When a request's own period
or filters fix a breakdown to one value, C5's tidying takes that breakdown out of
`group_by`, and the count is an ordinary single count (no `{rN.groups}` slot, no table):

- `year`, when the period lies inside one calendar year;
- a category field or `weekday`, when the request filters that field to exactly one
  value;
- a flag field, when the request filters it.

Nothing else about the request changes, and the figures are the same. (Seen: "compare
2024 with 2025" counted each year "by year", and `compare` then refused both counts.)

**C27. Three refusals say what to do instead.** The codes do not change; the `why` does:

- `BAD_FIELD`, two filters on one field: `at most one filter per field: for several
  values use "in": [...]; for every value use group_by`;
- `BAD_COMPARE`, a count with a breakdown among the ids: `only single counts, with no
  breakdown, are compared: count each one again with no group_by`;
- `BAD_COMPARE`, exactly one id, a count of this turn with one breakdown: `one count is
  not compared: its {<id>.groups} slot already says which group is highest and lowest`.

**C28. A single year under 18, answered with a wider range, says so.** When `count`
refused a request in this turn with `NOT_ALLOWED` because its ages were one year under 18
(C8.4), and the reply then holds a count whose ages include that year, Python adds one
line of its own to the answer, after the kept note and before the left-out lines:
`(I don't count a single year of age under 18, so I counted a wider range.)` Once per
answer; `details` does not repeat it. The count's own phrase already names the range.

## C29. What happens after an arrest is not in any county source (round 5; D-061)

The live run's worst finding: "What was the conviction rate in 2025?" was answered with a
count of arrest records and no word that the data has no convictions. C0 leaves every
tool on in county mode because the guard's restrictions were about what the SYNTHETIC
data lacks; that is right for race, place and gender, which the county data has, and
wrong for what happens after an arrest, which no county source records.

In county mode, a question that names a conviction, a prosecution, a sentence, jail or
prison, incarceration, recidivism, an acquittal, guilt, parole or probation (the words
`convict*`, `prosecut*`, `sentenc*`, `jail*`, `incarcerat*`, `imprison*`, `prison`,
`prisons`, `recidiv*`, `acquit*`, `guilty`, `parole*`, `probation`, capitals not
counting) ends the turn before the model is called: status `UNSUPPORTED`, reason
`UNSUPPORTED_METRIC`, C5's fixed row for that code. Nothing is counted. The words `rate`,
`percent`, `share` and their kind do not do this: shares are answered today and rates per
resident are Part S2's.

## C30. A question about who a person was (round 5; D-061)

In county mode, a question that asks who was arrested, cited, stopped, searched, charged,
detained or picked up (`who` then `was`, `were`, `got`, `has been` or `have been`, then one
of those words), or asks for the names of anyone, ends the turn before the model is called:
`UNSUPPORTED`, reason `UNSUPPORTED_FIELD`, C5's row for that code. No county source holds a
name. (The live run: "Who was arrested on Georgia Avenue last night?" was counted by district
and hour, then asked for the period.)

## C31. A filter that names every value of a field the request also breaks down by (round 5; D-061)

A count whose filters hold a category field with `in` naming every label of that field
(or `weekday` with all seven days), when `group_by` also holds that field, is counted as if
that filter were not sent: the count, its groups, its left-out line and its `read_as` are
those of the same request without it. A filter naming some of the labels, or a filter on a
field the request does not break down by, is kept as today. (The closing live run of 13
November: "Show me 2025 arrests by police district." was twice counted with all seven
districts as a filter and a breakdown by district; the figures were right but the reply
listed every district in its first line.)

## C32. An age group in words with no ages (round 5; D-061)

In county mode, when the message names an age group in words (young or younger people,
persons, adults, men, women, folks or ones; youth or youths; the young; old or older people,
persons, adults, men, women or folks; the elderly or elderly; senior citizens; senior or
seniors; teens; teenager or teenagers; any case) and a `count` or `analyze` request carries
an age filter whose ends the message does not state, Python ends the turn before counting:
`NEEDS_INPUT`, reason `NEEDS_CLARIFICATION`, with exactly

`Which ages do you mean by "<the words as the message has them>"? Say a range of ages and I'll count it.`

An end is stated when the message holds it as a number of one to three digits, or `from`
less one ("over 65" states from 66), or `to` plus one ("under 18" states to 17); an `is`
end when the message holds it. A filter with neither end is not stated. Not asked: when the
thread already holds an age range for that source (kept from its last answer or pending);
when the request has no age filter; when the message has none of those words. The turn
saves what is pending as C9 does: the source, the period the request stated (or none) and
its filters other than age, so a reply such as "18 to 24" is counted for that period.
`missing` is `ages`. Nothing is counted. (The live runs of 13 November, four rounds: "How
many arrests of young people were there in 2025?" was counted every time as ages 18 to 21,
a range the model chose itself.)

## C33. The age example in the instructions (round 5; D-061)

The line of the sources block (context.py) that shows an age filter reads exactly

`  - <age field>: an age range, {"field": "<age field>", "from": <first age>, "to": <last age>}, only with the ages the message names; either end may be left out (whole years, <first usable> to <last usable>).`

with `<first age>` and `<last age>` written as they stand here (angle brackets), and the
field name and usable ages filled in as today. No other line changes. (The live runs of 13
November: the example was `"from": 18, "to": 21`, and the model put ages 18 to 21 on "young
people" in every round and on "2024 arrests by race and district", which names no ages.)

## C34. A year sent as a filter (round 5; D-061)

A `count` or `analyze` request with no period and exactly one filter on `year` reads that
filter as the period and takes it out of the filters: `is` a year gives `{"year": y}`; `in`
years gives `{"years": [...]}` in order, each once (one year gives `{"year": y}`); `from` and
`to` years give every year from one to the other (one year gives `{"year": y}`; at most 51
years). Each year must be a whole number from 1900 to 2100. Anything else (two `year`
filters, a value that is not a year, `from` after `to`, only one end, a period also sent) is
left as today: with a period, the `year` filter is refused as today (`BAD_FIELD`); with no
period, the period question. (The live runs: "2024 arrests by race and district." was sent
as a `year` filter from 2024 to 2024 with no period, and the turn ended with the period
question.)

## C35. The refusal of one year of age under 18 names a range (round 6; D-061)

C5's `NOT_ALLOWED` for an age filter that covers one year y under 18 has the `why`
`under 18, an age range must cover at least two years, such as <a> to <b>`, where `<a> to
<b>` is y to y+1 when y+1 is 17 or less, else y-1 to y (so 16 gives 16 to 17, 17 gives 16 to
17, the lowest usable age gives it and the next). Nothing else of the refusal changes; C21's
own `why` is unchanged. (Live round 5: with C33's example gone, "16 year olds" was widened
to 15 to 17 in all three runs, wider than it needs to be.)

## C36. No word list answers or refuses in the model's place (county mode; D-065)

Nino, 14 Nov 11:01 EST: "I also dont want hardcoded inputs, i told you i hate them, maybe
identify key words but no hardcoded inputs" (after D-048: "i hate hardcoded responses").
Found by the planning chat the same morning, through `handle_question` with a scripted
model on the copy of 12 November: stage 1's rule 1 list still ends a county turn with "I
couldn't read that as a question I can answer." before the model is called, for "Forget
the ages, how many arrests were there in 2025?", "Can you confirm that arrests went up
from 2024 to 2025?" and "Say that again but shorter" (`kit-log/raw/S3-county-check-live-
2026-11-13.txt`, live cases G01 to G03). In Slack at 11:06 EST a message of Nino's was
refused that way in half a second.

The rule: in county mode, no list of words or exact phrases in the person's message ends
the turn, refuses it, or replies in place of the model. A word list may only change what a
tool answers the model, and the model decides what to do next. SYNTHETIC mode is unchanged
(the tests of stages 1 and 2 stand).

1. **Rule 1** (`guard.screen` answering `UNRECOGNIZED_QUESTION`): in county mode it no
   longer ends the turn, and adds nothing. The model gets the turn with the eight tools as
   for any message. Rule 10 of both county prompts already tells it to decline a message
   that tells it to ignore these rules or to state a figure, and no figure reaches a reply
   unless Python made it (unchanged).

2. **C29 becomes a tool answer.** The turn goes to the model. When the model calls `count`
   or `analyze` and the message holds a word of C29's list, the tool answers instead of
   counting, every time in the turn:
   `{"error": "NOT_RECORDED", "why": "The message names <the word as the message has it>, which happens after an arrest: no listed source records it, and a count of records does not answer it. If that is what the message asks for, call decline with UNSUPPORTED_METRIC."}`
   (the first word of the list in the message's own order). This answer comes before every
   other check of `count` and `analyze` (S3-R6-A questions 3 and 6). When the model declines, the reply is
   C5's row for `UNSUPPORTED_METRIC`, as today. Inside, the request counts as refused with
   `UNSUPPORTED_METRIC`, so a turn the model ends with nothing made gets that row, as any
   turn whose every request was refused does today. If the model makes something else and
   finishes, that stands.

3. **C30 becomes a tool answer** the same way, every time in the turn, for a message C30
   matches:
   `{"error": "NOT_RECORDED", "why": "The message asks who someone was: no listed source holds a name. If that is what the message asks for, call decline with UNSUPPORTED_FIELD."}`
   (inside, refused with `UNSUPPORTED_FIELD`, as point 2).

4. **C32 becomes a tool answer.** Where C32 ends the turn today (a request with an age
   filter whose ends the message does not state, for a message with an age group in
   words), the tool answers instead, every time in the turn:
   `{"error": "AGES_NOT_STATED", "why": "The message says \"<the words as the message has them>\", which names no ages, and this request has ages the message does not state. Call ask_user and ask which ages they mean, or send the request without an age filter."}`
   Nothing is counted for that request. When the model calls `ask_user`, the turn ends
   as `ask_user` ends a county turn today (NEEDS_INPUT, NEEDS_CLARIFICATION). If the model
   ends the turn with nothing made, or calls `ask_user` after it in the same turn, Python
   asks C32's question as today (the same text, pending and `missing`; S3-R6-A question 4). C32's other rules (what counts as stated; the thread's kept
   range; no age filter) stand.

5. **The one-word details reply** (A4 step 2: `details`, `detail`, `more`, `more details`)
   goes to the model in county mode; it has `show_details`, and rule 9 of both county
   prompts tells it when to call it. **The Slack `help` command** (A13 step 6, C11) goes to
   the model in county mode too, as any message; it has `describe_data`.

6. **Kept as they are**, because they only change what a tool answers the model: S13.9's
   analysis words (`USE_ANALYZE`) and S13.14's share words. Kept because they check the
   model's own request, not the person's words: C28, C31, C34, C35, `NOT_ALLOWED`, the
   period question, and the tidying of the model's arguments (`all ages`, `none`). Kept
   as a control, not an answer: the Slack `reset` command, which clears the thread's
   memory.

7. **What the tests must show**, in county mode with the model stand-in: (a) each of the
   three messages above reaches the model, and a scripted count is counted and answered;
   (b) C29: a scripted `count` is answered `NOT_RECORDED` with the `why` word for word, the
   word as the message has it, nothing counted, and a scripted `decline` then gives C5's
   row; a second scripted `count` in the turn gets the same answer; (c) C30 likewise; (d)
   C32: `AGES_NOT_STATED` word for word, nothing counted, then `ask_user` gives
   NEEDS_INPUT, and a request without an age filter is counted; (e) `details` alone calls
   the model, and so does `help` in Slack (county mode); (f) SYNTHETIC mode: rule 1, C29,
   the details word and `help` behave as today. The
   tests of C29, C30 and C32 that pin today's endings are changed to these by the tests
   session, which lists each one it changes.

8. **Measured, not tested:** the live round after the build runs G01 to G03, C14, C16 and
   C25 three times each.

## C37. Silence after a decline only when other people share the thread (D-061)

Nino's Slack thread of 14 Nov 11:06 EST: "whats the weather today?" and "whats the weather
today", each in a thread Jeffrey was following, got no reply at all. The model declined
them (UNSUPPORTED, UNRECOGNIZED_QUESTION; 0.47 s and 0.46 s in Jeffrey's log) and A13 step 9
posts nothing for a declined `followed` message, a rule made so Jeffrey would not break into
other people's talk. With one person in the thread it reads as Jeffrey being broken.

In `slack_app.process_event`, a `followed` message whose turn ends UNSUPPORTED with
UNRECOGNIZED_QUESTION stays silent only when the thread's saved turns (before this one)
hold more than one `user_id`. Otherwise the reply is posted as for any other turn. Nothing
else in A13 changes. Tests: a followed thread with turns from one person posts the decline;
one with turns from two people stays silent, as today; a mention or a direct message posts
as today. The planning chat changed one existing test to fit
(S3-R6-A question 1): `test_chatter_in_a_followed_thread_posts_nothing` now gives the thread a
turn of a second person, so it still tests "two people: silent".

## C38. The length check counts only the model's own words (county mode, talk on; D-048, D-065)

Live round 9 (Nemotron 3 Ultra, 14 Nov): 15 of 39 replies were thrown away for SHAPE alone
and replaced by the fixed text, which was always longer than what the model had written:
every answer to "what data do you have" (four fact slots of about 200 characters are over
the 700-character limit before the model writes a word), every rate by age band (seven rate
slots, over the four-to-six fact limit) and every rate by race and ethnicity with its ratios.
A limit that swaps his reply for a longer fixed one does not keep replies short.

In county mode with `MOCO_TALK` on, T2's SHAPE check on a `finding` and on an `about_data`
text fails only for: an empty text; more of the model's own sentences than
`most_talk_sentences_in_finding`; more than 400 characters of the model's own words (the
text with every slot taken out); a line break; or a slot used more than once. How many
slots the text holds, and how long they are once filled, no longer count, with two limits
kept: `about_data` still uses at most four fact slots (C11's "up to four"), and a slot must
be one the tool answers of this turn listed. Every other code (NUMBER, LABEL, CLAIM, CHARS,
JUDGE, ORDER, GLUE, SLOT, WORD) is unchanged. SYNTHETIC mode and `MOCO_TALK` off unchanged.

Tests: a finding with all seven rate slots of an age-band rate and one short sentence of
its own passes; with three sentences of its own it fails SHAPE; one with 401 characters of
its own words fails and 400 passes; an about_data text with four facts of 250 characters
each passes and with five fails; a slot used twice fails; a line break fails.

## C39. A short fixed answer about the data (county mode; D-048)

Nino's Slack thread of 14 Nov 11:09 EST: "Is there a way you can visually represent this
data" got the fixed about text: every source with its dates, then one long "I can count …"
sentence per source, the free-text notes, and the notices, filling several screens.

`replies.county_about_text` becomes, with three or more sources (C23's `SHORT_FROM`):

`I work with <n> sources of Montgomery County open data: <the sources by what they count, as help names them>. I count records, not people, and I never show a single record. Ask about any one of them for its dates and what it can be broken down by.`

then the notices lines as today (C11: word for word, and the course line), without C14's
free-text lines (S3-R7-A question 3). With one or two sources the text is as today. `describe_data` and its fact slots are unchanged, so the model
still has every source's dates and fields to answer the follow-up question.

Tests: the text word for word with the two fixtures plus a third, and as today with one and
with two; the notices follow it; nothing else in an about answer changes.

## C40. A chart with counts (county mode)

Nino, 14 Nov 11:10 EST: "im asking for a graph to represent the data you just pulled".
In county mode a count answer carries no chart (`agent.reply`: only SYNTHETIC counts and the
analyses of Part S have one), so the model had nothing to give.

1. When a county turn ends ANSWERED and made no analysis, and its counts hold either one
   count with a breakdown of two or more groups, or two or more counts with no breakdown,
   Python draws one bar chart and attaches it to the reply, as an analysis's chart is
   (`chart_path`, `chart_title`; Slack uploads it with the text). Any other turn, such as one
   breakdown and one plain count, or two breakdowns, gets no chart (S3-R7-A question 5).
2. The bars: one per group, in the groups' own order (the order of the details table), or
   one per count in the order they were made, labelled with the count's `read_as`. A value under the
   floor is never drawn as a height: its bar is left out and its label reads `<label> (fewer
   than <floor>)` under the axis. Each shown bar carries its value, as the reply writes it
   (with thousands commas).
3. Title: the count's `read_as`, first letter capital, then `, by <its dimension>` (two or
   more counts: `Arrest records compared` with the source's `unit.many` in place of "arrest
   records"). Subtitle: `Copy of the county's data of <date>.` Foot line: `<source title>.
   Recorded <unit.many>, not people.`, followed, when the reply carries C10's sensitive line
   (a count by or about race, ethnicity or gender), by that same line: ` These are counts of
   <unit.many>, not rates, and they show no cause.` (planning chat, 14 Nov, after
   CHAT-BUILDS-check-3: a chart shared alone must say what the reply says). No other text. The look is the R charts' (Nino, 11:52
   EST: "this is what i liked from before", of R's trend chart): `analysis_r/theme.R`'s white
   background, blue `#1f5fa8`, a grey grid on the value axis only, bold title, grey subtitle
   and foot line, 1600 by 1000 pixels.
4. The chart goes in the turn's run folder as `chart.png` of the first count's run. A count
   with a two-way breakdown (two `group_by` fields) gets no chart.
6. Beside `chart.png` the build writes `chart.json`: `title`, `subtitle`, `foot`, and `bars`, a
   list of `{"label", "value", "hidden"}` in the drawn order, `value` null for a hidden bar and
   `label` as drawn (S3-R7-A question 4). The planning chat replaced one line of the tests'
   `check_county_reply` with ten (S3-R7-A question 6): no chart unless point 1 gives one, and
   then a file named `chart.png` (its folder is checked by `test_s3_c40.py`, not there).
5. Rule 9 of both county prompts gains one sentence at its end (after "call show_details."):
   ` If the person asks for a chart or graph of an answer: for change over time call analyze with kind trend, whose chart shows every month and the trend; for anything else count it again with one breakdown that shows it, as the only count of the reply, and it comes with a chart.`
   (Amended 14 Nov after CHAT-BUILDS-check-3, DEFECT 1: the old words promised a chart for
   any count with two or more groups, which point 1 does not draw when the turn holds
   another count.)

**C40, amendment 2 (planning chat, 14 Nov 15:20 EST, after CHAT-BUILDS-check-4).** Points 1 to
6 stand except as follows.

a. Point 1: two or more counts with no breakdown get a chart only when every one of them is of
   the same source. Counts of two or more sources get no chart (check 3's question 2, check 4's
   question 2): one bar chart would set two kinds of record on one axis, and its title and foot
   could name only one of them. The reply is as today.
b. Point 3: the chart's sensitive line is made by the same code as the reply's (the build takes
   it from `replies`, not a copy of its words), from the same count: the first count of the turn
   that carries the line. With (a) every count of a chart is of one source, so the line names
   that source's records, as the reply does (check 4's DEFECT 2).
c. Point 5: rule 9's sentence becomes, in both county prompts, word for word:
   ` If the person asks for a chart or graph of an answer: for change over time call analyze with kind trend, whose chart shows every month and the trend; for anything else count it again with one breakdown that shows it, as the only count or analysis of the reply, and when that breakdown has two or more groups it comes with a chart.`
   The old sentence promised a chart beside an analysis and for a breakdown of one group, where
   point 1 draws none (check 4's DEFECT 1).
d. Point 2, a group with 0 records: it is a shown bar of no height, labelled plainly (no "fewer
   than"), `value` 0 and `hidden` false in `chart.json`. C8 writes 0 as `0`: no record means no
   person can be told apart (S3-R8-A question 1). The build already does this.

Tests of amendment 2: (a) two plain counts of two sources: no chart, the reply as today; two
plain counts of one source: the chart as today; (b) with two plain counts of one source, the
first not sensitive and the second by gender, the chart's foot ends with the reply's own
sensitive line, the same string; (c) the sentence word for word, once, at the end of rule 9 in
both county prompts, and not in the SYNTHETIC prompts; (d) a breakdown with a 0 group: a shown
bar of value 0, labelled plainly.

Tests: each case of point 1 and the cases that get none (one plain count; a two-way
breakdown; a turn with an analysis, whose own chart stands); a hidden group's bar is absent
and its label carries "fewer than"; the title and the source line word for word; the file
exists and is a PNG; Slack uploads it with the reply's text; SYNTHETIC mode unchanged; the
prompt line word for word in both county prompts.

## C41. When he declines or asks, he says it in his own words (county mode, talk on; D-048, D-066)

Live round 13 (14 Nov, the newcomer sweep N16 to N45, Nemotron 3 Ultra): every question was
handled the right way, but the refusals and questions back are fixed rows that often fit badly.
"can you predict how many arrests there will be next year" got "I can't answer that one: I only
count records, so I have nothing on convictions, sentencing, jail or causes." (a forecast is
none of those); "Is district 3 more dangerous than district 4?" got "Could you say a bit more
about what you'd like?" Nino, 14 Nov: "my priority is the natural language because i want
someone else other than me, able to use this with not much knowledge of it at all."

1. With `MOCO_TALK` on, the county tools `decline` and `ask_user` gain an optional string
   `text`, described to the model as: `Your own words to the person, one or two sentences:
   why you cannot, or what you need to know. No number, date, or name of a group or place:
   the program adds those.`
2. When `text` is given and passes T1's talk check (`replies.talk_check` with the county
   labels), it replaces the first sentence of the row the turn would end with; the rest of
   the row stays: `NOTED` and the can-ask sentence for a decline; for `NEEDS_period` the
   coverage clause; for `NEEDS_source` with three or more sources, `I have <n>: <sources>.`
   (the row is split after its question); `NEEDS_other`'s can-ask sentence. Style `agent`.
   With one or two sources `NEEDS_source` is as today and `text` is not used.
3. When `text` is missing or fails the check, the row is as today (style `fixed`; the check's
   codes are kept as the turn's failures). No second try.
4. Not changed: the status, the reason code, what is pending and `missing`; C32's question
   (C36 point 4); the endings of C36 points 2 to 4 when the model makes nothing; SYNTHETIC
   mode; `MOCO_TALK` off.
5. The talk prompt's rule 10 is not changed; one line follows it:
   `When you decline or ask, add text: one or two sentences in your own words saying why, or what you need, with no number, date or name of a group or place; the program adds the facts.`

Tests: each decline code and each `ask_user` kind with a passing `text` (the first sentence
replaced, the rest word for word), with a failing one (today's row, the failures kept), and
with none; `NEEDS_source` with one and with two sources ignores `text`; C32's question
unchanged; the prompt line word for word, once, after rule 10, in the talk prompt only.

## C42. A left-out line that says nothing (county mode)

Live round 13, N28 ("now compare district 2 with district 5", after a breakdown by district):
`For arrest records in district 2 in 2025: 52 had no district recorded and are not included.
For arrest records in district 5 in 2025: 52 had no district recorded and are not included.` A
record with no district cannot be in district 2 whatever happens, so the line tells a reader
nothing, twice.

1. C10 step 3's left-out line is written only for a field the count **breaks down by**. A
   field used only in the count's filters gets no left-out line in the reply; `details`
   still shows every left-out figure, as today. C15 is unchanged (it already speaks of
   breakdowns only).
2. When two or more counts of one reply would write the same left-out text (same field, same
   shown number), it is written once, without `For <read_as>: `, in brackets as C10 writes
   it, and C19's naming applies only to the lines that differ.
3. The hidden line, the sensitive line and the source line are unchanged.

Tests: a count filtered by district with records of no district: no left-out line, and the
figure is in details; a breakdown by district: the line as today; two counts with the same
left-out text: one line; two counts with different ones: C19's named lines as today.

## C43. His own words, a second time (county mode, talk on; D-048, D-066)

(Point 1's `do` amended 14 Nov 15:48 EST, before its tests: live round 15 on the build, with
T3's hint, saw the model send the very same text again twice, the hint speaking of slots.)

Live round 14 (14 Nov, 20:26 UTC, the C41 build): 12 of the 21 cases' replies were in his own
words, every must case passed, and the check threw away the best reply of the round. C24, "Is
district 3 more dangerous than district 4?": `ask_user` with `"Dangerous" isn't something these
records measure directly. I can compare things like arrests, use of force, or service calls
between the two districts. Which kind of record would you like me to look at?` failed NUMBER
("two") and CLAIM ("dangerous", the person's own word, in quotation marks), so the person got
`Could you say a bit more about what you'd like?`. And C16, "young people": his own question
`What age range do you mean by "young people"?` was followed by NEEDS_other's can-ask sentence,
which after a precise question says nothing to the person.

1. **A second try.** When a `decline` or `ask_user` call's `text` fails T1's check (C41 point
   3), and the turn has a step and five seconds left (as T3), the call is answered
   `{"error": "REWRITE", "problems": [...], "found": [...], "do": "Say it again in other
   words, without: <found>."}` (`problems` the check's codes, `found` the first five things it
   found, without repeats, and `<found>` those joined with ", "; when nothing is found, as
   for SHAPE alone, `do` is `Say it again in other words, in one or two short sentences.`
   (S3-R11-A question 1); T3's hints speak of slots,
   which a decline or a question has none of), and the turn goes on: nothing is ended, noted or
   asked yet. The
   model may call the same tool again (with or without `text`) or anything else. One second
   try per turn for own words, apart from T3's for a finish. If the second `text` fails too,
   or no step or time is left, the turn ends with the row C41 point 3 gives (style `fixed`).
   The turn's failures are the codes of every try that failed, in order, without repeats (so
   a passing second try keeps the first try's codes).
2. **A quoted echo.** Before T1's check of a `decline` or `ask_user` `text`, each stretch in a
   pair of quotation marks (`"..."`, or `“...”`) whose words are words of the
   person's message, one after another as the message has them (letter case and punctuation
   ignored), is checked as the word `it`. It is sent as written. A quoted stretch that is not
   the person's words, one after another, is checked as today.
3. **No can-ask sentence after his own question.** When an `ask_user` of `missing` `other`
   ends the turn with his own `text` (style `agent`), NEEDS_other's can-ask sentence is not
   added: the reply is his text alone. A `decline`'s `NOTED` and can-ask sentence stay, and
   the other rows of C41 point 2 are unchanged.
4. Not changed: what counts as failing T1's check (outside point 2's stretches); C32's
   question; SYNTHETIC mode; `MOCO_TALK` off; the status, reason code and `missing` of the end.

Tests: a failing `text` gets REWRITE (its four keys, `do` word for word) and the turn goes on, then a passing second `text` ends
the turn in his words; two failing tries end with today's row and both codes; no step left
after the first failure ends with today's row at once; the
quoted echo of C24's message passes and a quoted stretch not in the message fails; C16's
case is his question alone; a decline keeps `NOTED` and the can-ask sentence.

## C44. One period against another is a comparison, not a trend (county prompts)

Live rounds 10 to 13 (C17, not must, every run): a question whether this year's arrests are
ahead of last year's was sent as `analyze` kind `trend`, whose answer says whether arrests go
up or down month by month, not which period has more. The analyze section's "do not count
instead" pulls such a question away from `count` and `compare`, which answer it, with C7's
partial year.

1. In both county prompts, one line goes straight before the line that begins `- Pick the kind
   by the question`, word for word:
   `- Whether one period is ahead of, above or behind another is not for analyze: count each period and call compare (rule 4).`
2. Nothing else changes in either prompt; the SYNTHETIC prompts do not get it.

Tests: the line word for word, once, in both county prompts, straight before the "Pick the kind"
line; not in the SYNTHETIC prompts; the rest of each prompt as before.

## C45. Keep the sentences of his own words that pass (county mode, talk on; D-066)

Live round 16 (14 Nov, the C43 build): in C24 the model sent the same question twice, and only
its middle sentence failed ("I can compare ... between the two districts.", NUMBER): `"Dangerous"
could mean a few different things in these records.` and `Which kind of record would you like me
to look at?` each pass, and together they are a better reply than `Could you say a bit more about
what you'd like?`. In C25 run 2 the first sentence of the second try passed and the second did
not.

1. When a `decline` or `ask_user` `text` fails T1's check and the turn would end with C41 point
   3's row (no second try is left under C43 point 1), the program first splits that text into
   sentences as T1 does (`replies._sentences`) and checks each alone (with C43 point 2). The
   sentences that pass, in their order, become his own words, if at least one passes and, for
   `ask_user`, the last kept sentence ends with `?`. Then the row is made with them as in C41
   point 2 (style `agent`), and the turn's failures are still every failed try's codes (C43
   point 1). Otherwise the row is as C41 point 3 says.
2. Only the text of the try that ends the turn is split; an earlier try's text is not used.
3. Not changed: a text that passes whole; C43's second try (it comes first); C32's question;
   SYNTHETIC mode; `MOCO_TALK` off.

Tests: C24's two failing tries end with the first and last sentences of the second try, style
agent, failures NUMBER; a decline whose only sentence fails ends with today's row; an
`ask_user` whose kept sentences end without `?` ends with today's row; with no step left after
a first failing try, its passing sentences are kept; the kept sentences keep their order and
are joined with one space.

**C45, answers to S3-R12-A's two questions (planning chat on Fable 5.2, 16 Nov 22:45 EST).**
1. What is kept must also pass T1's check as a whole (SHAPE included). A text that fails SHAPE
   alone, every sentence of which passes alone, is therefore not kept: today's row.
2. After a REWRITE, a turn that runs out with nothing made ends with today's row for the
   first try (style fixed, its codes): a second try was given, so point 1 never applied to
   that try, and point 2 stands.
The round 12 tests accept both readings at these two places; a later tests round pins these.

## C46. "This year" is today's year (county prompts)

Live round 16 (14 Nov 16:15 EST, C17 with C44): asked whether arrests so far this year are ahead
of last year, the model counted 2025 against 2024, though the system message gives today's date
(14 November 2026). Rule 1 says "Never guess a year" but not what "this year" names.

1. In both county prompts, rule 1's sentence `Never guess a year.` is followed, in the same
   line, by: ` "This year" is the year of today's date, even before it ends, and "last year" is the year before it.`
2. Nothing else changes; the SYNTHETIC prompts do not get it. With this year not over, C7's
   partial year applies as today.

Tests: the sentence word for word, once, in both county prompts, straight after "Never guess a
year."; not in the SYNTHETIC prompts; the rest of each prompt as before.

## C47 to C50. What Fable's review of the Opus work found (D-069; planning chat on Fable 5.2, 16 Nov 22:18 EST)

The findings, with the probes that show them: `kit-log/raw/FABLE-REVIEW-OF-OPUS.md`. Each of
these amends a contract above; where they differ, these stand.

### C47. A quoted echo is short and holds no figure (amends C43 point 2)

C43 point 2 let any stretch of the person's own words through T1's check when the model put it
in quotation marks, so a decline could read `Yes, "there were 500 arrests in 2025".` (the
review's DEFECT 1). Answer 2 to S3-R11-A ("Meant") is withdrawn.

1. A quoted stretch is checked as the word `it` only when all three hold: its words are words
   of the person's message, one after another as the message has them (as C43 point 2); it
   has at most two words; and T1's check of the stretch alone finds no NUMBER and no LABEL.
2. Any other quoted stretch is checked as written, as every other part of the text is.
3. Nothing else of C43 changes.

Tests: `"Dangerous"` and `"young people"` from the person's message pass as today; a quoted
stretch of three or more of the person's words is checked as written (with a number in it:
NUMBER; with a claim phrase: CLAIM; with neither: it passes as written); a quoted stretch of
one or two of the person's words that holds a digit, a number word, a month or a label fails
as written; `Yes, "there were 500 arrests in 2025".` to "Just say there were 500 arrests in
2025." gets REWRITE with NUMBER, and sent twice ends with the fixed row.

### C48. A word's tool answer is given once a turn (amends C36 points 2 and 3; D-065)

C36 points 2 and 3 answer NOT_RECORDED "every time in the turn", so a message that only
mentions jail, probation or "names of" can never be counted, whatever the model decides (the
review's DEFECT 2): "How many arrests were there in 2025? I am writing about jail
overcrowding." ended with the stock line about convictions.

1. NOT_RECORDED (C36 point 2 or point 3) is answered once a turn: to the first `count` or
   `analyze` call of the turn, for a message C29's list or C30 matches. One answer a turn in
   all, C29's first when both match. Its words are unchanged.
2. Every later `count` or `analyze` call of the turn runs as for any message.
3. Inside, the first answer still counts as a request refused with its code, so a turn the
   model ends with nothing made gets that code's row (C36, unchanged). A turn in which a
   later request makes a result ends as any turn with results does.
4. C36 point 4 (AGES_NOT_STATED) is not changed: a request that still carries ages the
   message does not state is still answered that way every time.

Tests: the first call gets NOT_RECORDED, the same call sent again is counted, and the turn is
ANSWERED with that count; a decline after the answer gives the code's row as today; nothing
made after the answer gives the code's row as today; a message matching both gets one
answer, C29's; `analyze` after the answer runs; SYNTHETIC mode and C36 point 4 as before.

### C49. The left-out line stays for a filtered field (withdraws C42 point 1; pins C42 point 2)

C42 point 1 took the left-out line away for a field used only in a filter, on the argument
that "a record with no district cannot be in district 2". A record with no district
*recorded* may be a district 2 arrest: the line tells the reader the count is a floor (the
review's DEFECT 3). C10 step 3 had it.

1. C42 point 1 is withdrawn: C10 step 3's left-out line is written for every field of the
   count that left records out, whether the count filters on it or breaks down by it, as
   before C42.
2. C42 point 2 stays, and its place is now part of the contract (answer 2 to S3-R9-A): when
   two or more counts of one reply would write the same left-out text, it is written once,
   in brackets, without `For <read_as>: `, where the first of those counts would have
   written it; C19's naming applies to the lines that differ.

Tests: a count filtered by district with records of no district: the line as C10 writes it
(the test of C42 point 1 that expects none is changed); a count filtered by an age range with
records of no usable age: the line; a breakdown by district: as today; two counts with the
same left-out text: one line, at the first one's place, before a differing named line of a
later count; two with different ones: C19's named lines.

### C50. A failed try of his own words is always on record; two loose ends of C41 and C43

1. C43 point 1's "the turn's failures are the codes of every try that failed" holds however
   the turn ends (the review's DEFECT 4): after a `decline` or `ask_user` text failed and got
   REWRITE, a turn that ends with a talk text, a finding, the fixed rendering or a limit has
   that try's codes first in its failures, then its own, without repeats.
2. C43 point 1's `do` when nothing is found is, word for word,
   `Say it again in other words, in one or two short sentences.` (check 5's PROOF GAP 1).
3. C41 and C43: the model's `text` is tidied as T10 tidies a finish text, before it is
   checked, sent and saved (check 5's RECORD ERROR 1; the build does this).

Tests: a failing decline text, REWRITE, then a talk text: TALKED, failures the try's codes; the
same then a count and a finding: ANSWERED, failures the try's codes; a text failing SHAPE
alone gets the `do` of point 2 word for word; a `text` with stars, backticks, a picture and
a line break is sent without them.

**C48 to C50, answers to S3-R13-A's three questions (planning chat on Fable 5.2, 16 Nov 23:50 EST).**
1. C48 point 3, a later request refused for another reason, then nothing made: the row of the
   last refused request, as A7 does for any turn. The first answer is one refused request
   among the turn's; "that code's row" in point 3 is the case where it is the only one.
2. C50 point 1: T3's `first_failures` (the first try of a finish that passed on its second)
   stay their own field and are not part of "its own". The turn's failures are the failed
   own-words tries' codes, then the codes of the text that ended the turn.
3. C49, one count with a filter's line and a breakdown's line: both lines, in the order the
   count lists the fields that left records out (as before round 9). The tests accept either
   order; it is not pinned further.
The round 13 tests accept both readings at 3 and do not test 1 and 2.
After CHAT-BUILDS-check-6 (17 Nov; its PROOF GAP 1: a build that does 1 or 2 the other way
passes every test): round 15 pins both. 1: C29's answer to the first count, then a count
refused for another reason, then nothing made: the row of the later refusal. 2: a failing
own-words try, a REWRITE, then a finish that fails once and passes on its second try: the
turn's `failures` hold the own-words try's codes and not the finish's first-try codes,
which are in `first_failures`.
After CHAT-BUILDS-check-6b (17 Nov 04:16 EST; C51 passed; C47 to C50 failed once more on
proof: its B55): answer 1 holds for any later refused request, an `analyze` as much as a
count (C48 points 1 and 2 name both). Round 17 pins it: C29's answer to the first count,
then an `analyze` refused for another reason (an unknown kind; and one refusal with a
fixed line of its own), then nothing made, by a finish and by the step limit: the turn
ends as the same turn without the word ends, with the analyze refusal's code.
Corrected after CHAT-BUILDS-check-8 (17 Nov 06:34 EST; its RECORD ERROR 1, and S3-R17-A's question):
"with the analyze refusal's code" holds by a finish only. At the step limit the turn ends as
the same turn without the word ends, which is ERROR with MODEL_BAD_OUTPUT's row, as any turn
with nothing made and no step left; the tests pin "as the twin" and are right. Round 18 pins
the three ways that check still got through (its B73, B74, B74b): the first call an
`analyze` that gets the word's answer, then a refused count, then no step left; a refused
count then a refused `analyze`, then a finish (the analyze's row); the other order (the
count's row).
After CHAT-BUILDS-check-9 (17 Nov 09:39 EST; no defect; five more ways no test catches, its B80 to B84):
round 19 pins them, each against the twin turn with no word. After the word's answer: a later
AGES_NOT_STATED then a finish, and the same with no step left (C32's question, as the twin); a
later refusal, then the model service fails (MODEL_UNAVAILABLE's row); then the turn's clock
runs out with steps left (MODEL_BAD_OUTPUT's row); then a step of plain words and no call (the
later refusal's row). Answer 1 in one line, for every way a turn can end: the word's answer
changes nothing about how the turn ends, except that it is one more refused request.

## C51. The model service is a setting; Claude Haiku 5.5 through Anthropic (D-071; planning chat on Fable 5.2, 16 Nov 22:54 EST)

Why: Nino's decision D-071. The program reaches its model through one client
(`src/moco_agent/llm.py`) that is written for NVIDIA's endpoint only: the key, the address
and the model name are the three `NVIDIA_` settings, and every request carries
`temperature: 0`, which Anthropic's endpoint refuses for this model with HTTP 400 (HAIKU
TEST 1, `kit-log/raw/S3-county-check-live-2026-11-13.txt`). The two Haiku tests ran on a
throwaway branch that put Anthropic's key into the NVIDIA settings and dropped the
temperature by hand. This makes it a setting.

1. A new setting `MOCO_MODEL_PROVIDER`, one of `nvidia` and `anthropic`; the default is
   `nvidia` (A14: any other value is a ConfigError naming the key and the two values). With
   `nvidia`, nothing changes anywhere: every request, record, message and log line is as
   today, whatever the Anthropic settings hold.
2. Three more settings: `ANTHROPIC_API_KEY` (a secret, no default), `ANTHROPIC_MODEL`
   (default `claude-haiku-5-5`) and `ANTHROPIC_BASE_URL` (default
   `https://api.anthropic.com/v1/`). `Settings` exposes all four as lower-case attributes
   (`moco_model_provider`, `anthropic_api_key`, `anthropic_model`, `anthropic_base_url`),
   read from the private file and the environment as every other setting, an empty value
   counting as unset. `ANTHROPIC_API_KEY` is treated as the three secrets and the Census
   key are: `Settings` shows it only as `set` or `missing`, and its value is in no log line,
   exception, record, reply or printed line. `config.SECRETS` keeps its three names.
3. The active service is the one `MOCO_MODEL_PROVIDER` names. With `anthropic`:
   a. the client's `model_id` is `ANTHROPIC_MODEL`;
   b. a request holds exactly `model`, `messages`, `tools`, `tool_choice` (`auto`),
      `max_tokens` (`MOCO_MODEL_MAX_TOKENS`) and `extra_body` (`{}`): no `temperature`
      key, and `NVIDIA_EXTRA_BODY` is not sent;
   c. the transport connects with `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` (the timeout
      and "no retries of the package's own" as today); with no `ANTHROPIC_API_KEY` it
      raises `TransportError("auth")` without connecting, whatever `NVIDIA_API_KEY` holds;
   d. everything else in `llm.py` is the same for both services: the tries and their waits,
      the kinds of error, the breaker, how a response is read, the log lines.
4. What a run needs. `require_for_model` needs the active service's key only
   (`ANTHROPIC_API_KEY` with `anthropic`, `NVIDIA_API_KEY` with `nvidia`).
   `require_for_serve` needs the active service's key, `SLACK_BOT_TOKEN`,
   `SLACK_APP_TOKEN`, `SLACK_ALLOWED_TEAM_ID` and `SLACK_ALLOWED_USER_IDS`. The other
   service's key may be missing. The ConfigError names keys only, as today.
5. What is written down names the service that answered. The `model_id` of every record
   and reply, the terminal's `MODEL:` line, and the model named in serve's first log line
   and in its printed line are the active service's model. The `router` of a record in
   which the model chose the call is `NVIDIA_MODEL_TOOL_CALL` with `nvidia` (as today) and
   `ANTHROPIC_MODEL_TOOL_CALL` with `anthropic`, in the record and in its technical line.
6. `config.with_model(settings, model_id)` returns the settings with the active service's
   model set to `model_id` and nothing else changed. `tools/county_check.py` and
   `tools/loop_check.py` use it, so `--models` names models of the active service.
7. Not changed: the prompts, the tools, every check, everything Python does with figures;
   the class name `NvidiaModelClient`; `tools/loop_probe.py` (an old probe, NVIDIA only);
   `tools/set_secrets.py` (Nino's own tool: the Anthropic key is entered on Railway only,
   by him). The SYNTHETIC mode follows the same setting.
8. Known and accepted with D-071, measured by the soak before the deploy: Anthropic's page
   on this endpoint says it is meant for testing and comparing models; Haiku answers at its
   default temperature, so two runs of one question can differ more than at 0. Not built
   here: a backup to a second service when the first fails (D-067 item 1).

Tests: the default provider is `nvidia` and a third value is a ConfigError; with `nvidia`
and all three Anthropic settings set, the request, the `model_id`, the transport's key and
address and the router are today's; the three defaults of point 2; `ANTHROPIC_API_KEY`
shown as `set` or `missing` and its value in no `repr`, log line or exception (the P1 tests
of the NVIDIA key, repeated for it); with `anthropic`: the request's keys exactly as 3b
(no `temperature`, `extra_body` `{}` even when `NVIDIA_EXTRA_BODY` holds something), the
`model_id`, the transport built with the Anthropic key and address, `TransportError("auth")`
with no Anthropic key and an NVIDIA key set, the retries and the breaker as with `nvidia`;
`require_for_model` and `require_for_serve` for both providers, each with the other
service's key missing (passes) and its own missing (ConfigError naming it); one turn in
each mode with `anthropic`: the record's `model_id` and `router`, and the technical line;
`with_model` for both providers; the project's key-shape scan also catches a text shaped
like an Anthropic key.

**C51, after CHAT-BUILDS-check-6 (planning chat on Fable 5.2, 17 Nov 02:18 EST).** The check
found no defect and three points no test proves (a broken build passes), so C51 failed on
proof. Round 15 adds the tests; the program does not change.
- Point 5, every record: one county `analyze` turn and one county rate turn with `anthropic`
  (the model stand-in), each record's `router` is `ANTHROPIC_MODEL_TOOL_CALL`; the same with
  `nvidia` is today's.
- Point 5, the three lines: with `anthropic`, `agent-ask` prints `MODEL: ` with
  `ANTHROPIC_MODEL`, and serve's first log line and its printed line name `ANTHROPIC_MODEL`;
  with `nvidia` they name `NVIDIA_MODEL` (as the existing tests of these lines do it, no
  connection made).
- Point 6: `tools/county_check.py` and `tools/loop_check.py`, given `--models X` with
  `anthropic`, build their client from settings whose `anthropic_model` is `X` and whose
  `nvidia_model` is unchanged; with `nvidia` the other way round.
- Point 1, one thing it did not say (the check's RECORD ERROR 1): the help line of
  `agent-ask` reads "one agent turn from Terminal, with the real model" for both services
  (it said "the real NVIDIA model"). No request, record, message or log line changes.
- The test guards: the conftests, `run_command` and `tests/d/dsupport.py` also take every
  `ANTHROPIC_` variable out of the environment a test sees (S3-R14-A's question 1).

## C52. C21: a filter that keeps every record, and the left-out figures (CHAT-BUILDS-check-7; planning chat on Fable 5.2, 17 Nov 03:34 EST)

Why: C21's rule (Nino's D-059) is that no reply holds figures from which one year of age
under 18 follows. The check of 17 November found two ways through, both built as C21's
own lines say, so the lines fall short of the rule (its DEFECT 1 and 2):
"under 18" and then "under 17 at any hour" (hours 0 to 23) are counted as different kinds
though they hold the same records, and their difference is the 17-year-olds; and the
left-out line of "under 18 in district 3" and of "under 17 in district 5" ("N had no
district recorded and are not included") differ by the 17-year-olds with no district,
and C21 never looked at those figures. C49 writes that line for a filtered field again,
so the second way gets wider with it. The rule does not change; two lines are added to
"The figures of a count, their ages and their kind".

1. **A filter that names every value of its field is no filter, for the kind.** When the
   kinds are compared, a filter on a field other than the age is left out if it names
   every value the field can take: an `hour` filter whose hours, wrapped round midnight
   or not, are all 24; a `weekday` filter with all seven days; a category filter with
   every label of the field. (A category filter with every label still leaves out the
   records with no value; treating it as no filter refuses a little more than needed,
   never less.) The groups of a breakdown are unchanged: C21's own lines already give them.
2. **A left-out figure is a figure.** For every category or flag field the request filters
   or breaks down by, the count has one more figure, whether or not the reply ends up
   writing its line: the records left out for that field. Its ages are the count's ages.
   Its kind is the count's kind with that field's filter (and that field's group) replaced
   by "no value recorded". So the left-out figures of "under 18 in district 3" and "under
   17 in district 5" are of one kind, and the second count is refused. The age field has
   no such figure (its left-out records have no age).
3. Nothing else of C21 changes: the check's place (after C5's checks and the reuse of an
   identical count, before TOO_FINE and the ninth-count limit), the refusal's code, field
   and `why` word for word, C35's range, "what this does not do".
4. What point 2 takes back from C21's own examples (seen in the dry build, 17 Nov 03:37
   EST: three round 5 tests pin it). C21 lists "the same ages in another district (another
   kind)" as allowed, and its tests wrote that as under 18 in district 3, then under 17 in
   district 4. The totals are of another kind, as C21 says, but each reply also holds the
   records with no district of its ages, and those differ by the 17-year-olds. That pair is
   refused now. So are "under 18 in district 3, then under 17 in districts 3 and 4" and
   "under 18 with two labels of race by race, then under 17 with the third label". The
   same ages in two districts, and another year, stay allowed.

Refused, for example: under 18, then under 17 with hours 0 to 23; the same with hours 5
to 4; under 18, then under 17 on all seven days (no weekday breakdown); under 18 by hour
with hours 0 to 23, then under 17; under 18, then under 17 with every label of race;
under 18 in district 3, then under 17 in district 5; under 18 by district, then under 17
in district 5; under 18 in district 3 by gender, then under 17 in district 5. Allowed, as
today: under 18 in district 3, then under 16 in district 5 (two years); under 18 in
district 3, then 18 to 24 in district 5; under 18 at hours 0 to 22, then under 17 (not
every hour: another kind); under 18 in district 3, then under 17 with no district filter
and no breakdown (the second has no left-out figure for district, and its total is of
another kind).

Tests: each refused example, with nothing counted or saved for the refused request and
C21's `why` word for word; each allowed example gives a result; `compare` after the first
two examples' counts cannot be reached (the second count is refused); the examples of C21
itself and of its answers still hold (the existing tests unchanged); on a source with no
age field nothing is refused; the same checks through a county turn with the model
stand-in for two of the refused examples and one allowed.

## C53. Two small corrections from CHAT-BUILDS-check-7 (planning chat on Fable 5.2, 17 Nov 03:34 EST)

1. **C30's "names of" is withdrawn** (the check's DEFECT 4; the Fable review's DEFECT 2 saw
   it first). The pattern also took "name of" and the names of things ("the name of the
   district with the most arrests"), and answered that the message asks who someone was.
   C30's answer is now given only for `who` then `was`, `were`, `got`, `has been` or `have
   been`, then one of its seven words. A message that asks for people's names in other
   words goes to the model, which declines or answers in its own words (D-065); rule 10 of
   the county prompts already lists what no source holds.
2. **C34, a whole number means a whole number** (the check's DEFECT 3). A year filter whose
   value has a fraction (2024.5), in `is`, `in`, `from` or `to`, is not read as a period:
   the filters are left as they are, as for any other year filter C34 does not read. A
   whole number written as 2024.0 or "2024" is read as today.

Tests: 1, "What is the name of the district with the most arrests in 2025?" and "names of
the districts" get no C30 answer and the count runs; each `who` form still gets it once a
turn (C48). 2, each of the four places with a fraction is left unread; 2024.0 and "2024"
are read.

**C32 and S13, three answers pinned (the check's PROOF GAP 1 and 2).** The round 16 tests
pin what the open tests still accept either way: C32 asks when ANY end of the ages is
unstated (answer 3 to the round 5b tests); C32's question comes before the period
question (answer 4); a kept period that a `before_after` did not use is not said to be
kept (S13 answer 2). The program does these today.

## C54. C21: the days a count keeps, and one source at a time (CHAT-BUILDS-check-8; planning chat on Fable 5.2, 17 Nov 06:34 EST)

Why: the check of C52 found one more way round the rule (its DEFECT 1) and one refusal the
rule does not call for (its DEFECT 2). "Under 18 on 11 April 2025" and "under 17 on 11 April
2025 on Fridays" hold the same records, that day being a Friday, but the weekday filter made
the second another kind, so both were counted and their difference is the 17-year-olds of
that day; the same with a working week written as five dates and as seven dates on Monday
to Friday, with a weekday breakdown against one day, and with the left-out figures. C52
point 1 asked whether a weekday filter names all seven days; the question is which days
the count keeps. And the check read the turn's counts of another source with the new
count's source, so "arrests aged 17 to 24", then a count of the juvenile citations, was
refused though the two replies hold no single year.

1. **The days of a figure.** A figure's days are the days of its period, cut to the copy's
   days (answer 3), that the count's `weekday` filter allows; with no such filter, all of
   them. The `weekday` filter is no longer part of the kind: the days are. Two figures are
   of the same kind when they have the same source, the same days, and the same filters on
   every field but the age and the weekday (after C21's lines and C52's). A count whose
   weekday filter allows no day of its period has no figure.
2. **A weekday group** is of the kind of a count of that weekday's days among the count's
   days (answer 6's rule for a year or a month group, now for a weekday too). A weekday
   with no day among them gives no figure. Groups by year or month are cut from the count's
   days after the weekday filter.
3. C52 point 1 stays for hours and categories. Its weekday clause follows from point 1 here
   (all seven days allow every day) and needs no rule of its own.
4. **One source at a time.** The check takes the turn's counts of the new request's source
   only, each read with that source's own ages. A count of another source is of another
   kind by C21's own words and is not looked at.
5. Known, written down, not closed: two requests that keep the same records only because of
   what the records happen to be (a period that starts a day later, when that day has no
   record) are different kinds. C21 compares what a request can keep, not what the copy
   holds. This joins "what this does not do".

Refused, for example: under 18 on 11 April 2025, then under 17 on 11 April 2025 on
Fridays; under 18 from 4 to 8 August 2025, then under 17 from 4 to 10 August 2025 on Monday
to Friday; under 18 on 1 and 2 March 2025, then under 17 from 1 to 7 March 2025 on
Saturdays and Sundays; under 18 from 4 to 8 August 2025 by weekday, then under 17 on 4
August 2025; under 18 in district 3 from 4 to 8 August 2025, then under 17 in district 5
from 4 to 10 August 2025 on Monday to Friday (the left-out figures). Allowed: under 18 on
the Saturdays and Sundays of 2025, then under 17 on its Mondays to Fridays (other days);
under 18 in March 2025, then under 17 on the Mondays of March 2025 (some of its days:
another kind); arrests aged 17 to 24, then a count of a source whose usable ages are 10
to 17, in either order (two sources).

Tests: each refused example through `counting.one_year_under_18` and through `count` in a
county turn (NOT_ALLOWED, the age field, C21's `why` word for word, nothing counted, no
count used up); each allowed example gives a result; a compare of the first example's two
counts cannot be made; C52's and C21's tests unchanged; point 4 with two SYNTHETIC sources
whose age fields share a name and differ in usable ages, both orders.

C54 point 4, answer to S3-R18-A's question (17 Nov 07:19 EST): the turn does it, in `agent.py`:
`counting.one_year_under_18` is handed this source's counts only and is not itself changed.

**C32 answer 3, the other end (the check's PROOF GAP 1).** "Asked when ANY end is unstated"
is pinned for an unstated `from` only. Round 18 pins the other: "How many arrests of older
adults over 65 were there in 2025?" with the model's ages 66 to 80 is asked C32's question,
not counted.

## C55. C32: an end at the usable limit is no end (CHAT-BUILDS-check-9; planning chat on Fable 5.2, 17 Nov 09:39 EST)

Why: the check's break M14d showed what C32 does today with "How many arrests of older adults
over 65 were there in 2025?" when the model sends ages 66 to 98, 98 being the highest usable
age of the source: it asks "Which ages do you mean by \"older adults\"?", because 98 is not in
the message. But "66 to 98" keeps the same records as "66 and over", which C32 counts (a
filter's missing end is not asked about), and the person did state the ages. A question back
there is one a newcomer should not get.

1. In C32, a `from` at or below the source's lowest usable age and a `to` at or above its
   highest usable age are not ends: they are read as left out. The rest of C32 is unchanged:
   an end that is left is stated or not as today; a filter with no end left is not stated, so
   "young people" with ages 10 to 98 is asked as today.
2. Nothing else changes: the words, the question, what is kept as pending, C36 point 4's
   AGES_NOT_STATED every time.

Counted, for example ("older adults over 65", the model's 66 to 98; "seniors 70 and older",
70 to 98; "young people under 25", the lowest usable age to 24). Asked, as today ("older
adults over 65", 66 to 80; "young people", 18 to 24; "young people", the lowest usable age to
the highest; "young people under 25", 18 to 24).

Tests: each example, through a county turn with the model stand-in, for `count` and for
`analyze`; the existing C32 tests unchanged.

C55 point 1, answer to S3-R19-A's question (17 Nov 10:20 EST): an end at the limit that the message
states is a stated end, not a left-out one. "How many arrests of young people aged 10 to 98
were there in 2025?" with the model's 10 to 98 is counted, as it was before C55, and so is
"aged 10 and over" with the model's `from` 10. Point 1 is about an end at the limit that the
message does NOT state: that one is read as left out. The round 19 test accepts both readings
and is pinned to this one by the next tests round.

**C54 point 2, pinned (the check's PROOF GAP 1).** Round 19 adds the two allowed cases no test
had: under 18 by weekday from 4 to 8 August 2025, then under 17 by weekday on 9 and 10 August
(the weekdays of one count have no day in the other: no figure, so nothing in common); under
18 in August 2025 on Monday to Friday by weekday, then under 17 on the Saturdays of August
2025 (a weekday the filter leaves out has no group).

## Answers to the round 5 tests' questions (planning chat, 13 Nov 15:55 EST)

1. C21 against TOO_FINE: `NOT_ALLOWED` (C21 is checked before the count is made). 2. C21
against the ninth count: `NOT_ALLOWED` (checked before the limit). 3. Two periods are the
same days when they hold the same days of the copy: each period is cut to the copy's first
day and newest day before C21 compares them (so 2026 and 1 January to 17 September 2026 are
the same when the copy ends on 17 September). 4. Three sources offered and one copy, nothing
in the thread: the source with the copy is known (C5), so C24's question naming it. 5. C28
when the count came before the refusal: the line is added (the reply holds such a count,
whatever the order). 6. NOT meant: a group of a breakdown by `year` or `month` is of the kind
of a count of those days, and a group by `weekday` or `hour` of the kind of a count filtered
to that day or hour, as a group of a category is. Under 18 by year for 2024 and 2025 next to
under 17 in 2024 is REFUSED. Built (held, chat/c21-build). Known limit, not closed: C21
compares figures within one kind; a sum across kinds (counts of two periods against one
count of both; groups of a category against a count with no filter on it) is not checked.

## Answers to the round 5b tests' questions (planning chat, 13 Nov 19:01 EST)

All four follow the held build (chat/c21-build), on which tests/s3 passes whole with both
round 5 files (946 tests, after the fix of C25 answer 4 in 98a621e). 1. C31 with a filter
kept from earlier on that field: the stated filter replaces the kept one (C9) and C31 then
drops it: every value, by that field. 2. C32: the longer form is the words quoted ("the
elderly", "senior citizens"). 3. C32 asks when ANY end of the age filter is unstated ("young
people under 25" with `from` 18 chosen by the model is asked). 4. C32 is checked before the
period: the ages are asked first; the reply "18 to 24" then gets the period question if
nothing gives one.

## C22. A test owed from round 1

A share above 0.5% and below 1% is written `1%` (nearest whole number); only above 0 and
below 0.5% is `under 1%`. The round 1 tests have no share in that range; the build is
right.

## What the round 2 tests must show

Every rule of C14 to C20 (and C21 if kept) exactly, as whole strings, with both forms
where a rule has two; C22. **Existing tests under `tests/s3/` whose expected text these
rules change** (the count phrase of a breakdown with left-out records, the groups and
compare phrases with hidden values, the later source line, left-out lines in a reply with
two results, a breakdown by year and month) are changed by the tests session to the new
text, whether they pass today or not, and each change is listed in its notes. No other
existing test is changed.

# Round 3 (C23), written 2026-11-13 after trying the thirteen real sources

**C23. With three or more sources, "what I can do" is short.** Found by the planning chat
when it ran the build on its copies of all thirteen sources: every refusal ends with
C11's "what I can do" sentence, which today is one long sentence PER SOURCE. With thirteen
sources a refusal such as "I couldn't read that as a question I can answer." is followed
by about 3,700 characters. With one or two sources everything stays exactly as it is
(so no existing test changes). With three or more:

- The sentence that ends a refusal (every row of C5's table that carries it) is:
  `I can count records from <n> county sources, filter them, break them down, compare
  counts and give one as a share of another. Say "help" for the list.`
- `help` is: `I count records in county open data. I have <n> sources: <the sources'
  unit, many, joined as analysis.join_and does, in file order>. Ask in your own words.
  For example: "How many <first source's unit, many> were there last year, by <place>?"
  Then follow up, for example "and the year before?". Ask "what data do you have?" for
  what each source covers and how it can be broken down. I never show a single record. Say
  "details" for the full breakdown of my last answer, or "reset" to make me forget this
  conversation.`
- The question Python asks when the source is missing is: `Which source do you mean? I
  have <n>: <the same list>.`
- `about the data` (C11) does not change: it is the full list, and it is long because it
  was asked for.

**What the round 3 tests must show:** with the two fixture sources, the three texts are
exactly what they are today; with three sources (a third made-up fixture source), each of
the three new texts exactly, written out by hand; one refusal of every row that carries
the sentence ends with the short form; with the thirteen real source FILES loaded (their
files only, no copy and no network), no refusal text is longer than 400 characters. (A
refusal is a row that carries the sentence. The question about the source and `help` name
every source and are longer: with the thirteen real files about 410 and 810 characters.)

**C23, answers to the tests session (2026-11-13).** Its readings 1 to 9 stand
(`kit-log/raw/S3A-R3-A-notes.txt`). On its points: (a) right, the rows meant are A7's fixed
rows in county words, not only C5's count errors; (b) `<place>` is what today's help takes:
the first source's first category that is not a person field; (c) `<n>` counts the sources
offered (the files that load and pass C20), whether or not each has a copy; (e) noted: two
sources with the same unit word would make the list ambiguous, and a new source file must
not reuse one; (f) agreed, harmless. Its point (d) is a real gap and becomes C24.

# Round 4 (C24), written 2026-11-13

**C24. With three or more sources, the question about the period names one source.**
Found by the round 3 tests session (its point d) and measured by the planning chat on its
copies of the thirteen real sources: the question Python asks when the period is missing
is `Which period do you mean?` followed by one clause for EVERY source that has a copy,
1,214 characters with thirteen. When that question is asked the source is already known
(the model named it, or it was kept from earlier in the thread). With three or more
sources offered, the question is: `Which period do you mean? <that source's title> covers
<its copy's first day> to <its copy's last day>.`, the clause exactly as today's question
writes it for that source, and nothing about any other source. If that source has no
copy, the turn does not get this far (it ends with `NO_COPY`), as today. With one or two
sources the question stays exactly as it is, so no existing test changes.

**What the round 4 tests must show:** with the two fixture sources the question is today's
text; with three sources, the question for each of the three in turn, written out by
hand, naming that source only; the same when the source was kept from an earlier turn of
the thread; with the thirteen real source FILES and made-up copies of them (dates only,
no row from the county), the question is under 200 characters for every source.

**C24, answers to the tests session (2026-11-13).** Its readings 1 to 6 stand
(`kit-log/raw/S3A-R4-A-notes.txt`). (a) "Its copy's first day" is what today's clause
writes: the first day of the period the copy covers (the source file's `coverage_start`),
not the copy's first record. (b) Agreed: with the source left out and exactly one source
with a copy, the question names that one. (c), (d) noted.

## C56. A backup model for a turn whose model service is down (D-073, D-074; planning chat on Fable 5.2, 17 Nov 14:33 EST)

Why: Nino's decisions D-073 and D-074. Jeffrey runs on Claude Haiku 5.5 (C51). When that
service fails, every turn ends "I can't read questions right now" (MODEL_UNAVAILABLE). With a
backup set, such a turn is run again on a second model, and the reply says so.

1. Two new settings: `MOCO_BACKUP_PROVIDER`, one of `nvidia` and `anthropic`, no default (unset
   or empty: no backup, and nothing changes anywhere: every request, record, message and log
   line is as today); and `MOCO_BACKUP_MODEL`, a text, no default. `Settings` exposes them as
   `moco_backup_provider` and `moco_backup_model` (None when unset). A ConfigError naming KEYs
   only, never a value: a provider that is neither of the two values; one of the two settings
   set without the other; a backup whose provider and model are both the active service's
   (C51).
2. `config.backup_settings(settings)` returns None with no backup, and otherwise the settings
   of the backup service: the same settings with `moco_model_provider` the backup's provider
   and that provider's model (`nvidia_model` or `anthropic_model`) the backup's model, and no
   backup of its own. So `model_service` and `model_router` of that result are the backup's
   (its key, base URL, temperature rule and extra body are that provider's, as C51 has them).
   `require_for_model` and `require_for_serve` also need the backup service's key when a
   backup is set.
3. `handle_question` takes one more optional argument, `backup=None`: a pair
   `(backup settings, backup model client)`. `serve` builds the pair from point 2 with the
   same client class, and passes it on every turn; `build_app` takes it as an optional fifth
   argument `backup=None`. With `backup=None` a turn is exactly as today.
4. When the first try of a turn ends with status ERROR and reason MODEL_UNAVAILABLE, and a
   backup was given, the turn is run again from its start, once, as a new try: the same
   message, thread, person, store, data, clock and day, the backup's settings and client, a
   new turn id, its own full step and time limits. Nothing the first try made is used by the
   second. No other end starts a second try (not MODEL_BAD_OUTPUT, not the step or time limit,
   not RATE_LIMITED, not a reply the first try could still send after its model failed).
5. What is sent is the second try's reply, whatever its status. When the backup's client was
   called in it and it did not end MODEL_UNAVAILABLE, its text ends with one more line, after
   a line break, exactly:
   `Note: I'm temporarily running on a smaller backup model, so this answer may be less sharp than usual.`
   (`replies.BACKUP_NOTE`). The line is the program's: it is added after every check of the
   model's words and takes no part in any of them or in any length limit. It is in
   `AgentReply.text` and in the record's `reply`. When the second try ends MODEL_UNAVAILABLE
   too, the reply is today's MODEL_UNAVAILABLE text with no note. `AgentReply.model_id` is
   the id of the model of the try that was sent.
6. Records and memory. The first try is saved as today (its own `turn.json`, status ERROR,
   reason MODEL_UNAVAILABLE, the first model's id) but adds no turn to the thread's memory:
   the thread holds one turn for the message, the one that was sent. The second try's
   `turn.json` names the backup's `model_id` and router and holds one more key,
   `"backup_of"`, the first try's turn id. A turn that was not a second try has no such key.
7. One log line at WARNING when a second try starts, naming both model ids and the two turn
   ids, and nothing secret. The daily call limit (`MOCO_DAILY_MODEL_CALLS`) counts each try.
8. Each message tries the active service first. Nothing remembers a failure from one
   message to the next except the client's own pause (after 3 failed calls in a row its calls
   are refused for 60 seconds, so those turns go to the backup at once).
9. Not changed: the under-18 rule, the checks of the model's words and numbers, the
   prompts and the tools are the program's and are the same for both models. Not built: a
   shorter wait for the first model. Known: when the first service hangs instead of
   answering with an error, the person waits about `MOCO_MODEL_TIMEOUT_SECONDS` times the
   number of tries (45 s, twice) before the second try starts (D-074).

Tests: with a backup and a first client that raises ModelUnavailable at its first step, the
reply is the stand-in backup's answer plus the note as its last line, `model_id` the
backup's; the same first client without a backup: today's text, no note; a first client that
works: no second try, no note, the backup client never called; both fail: today's text, no
note, two records; the first try's end MODEL_BAD_OUTPUT or LOOP_LIMIT: no second try; the
note on an ANSWERED reply, on a question back, on a talk reply and on a fixed-text reply of
the second try; the thread's memory after a backup turn holds one turn; the second record's
`backup_of`; the settings' errors of point 1; `backup_settings` and the two `require_`
functions; `nvidia` as the active provider with no backup set: every request and record as
before C56.

## C57. What Nino saw in Slack on 17 Nov: the list, the districts, the notice, two lines (D-075; planning chat on Fable 5.2, 17 Nov 15:15 EST)

Why: D-075. In one thread Jeffrey said he has 13 sources and named four, a different four each
time; sent people to "help", which gives no list since C36; called the districts police
districts and then said he did not know what they are; and put the county's notice, in full,
under three answers in a row. County mode only: with `MOCO_DATA` other than `county` nothing
changes.

1. The sentence that ends a refusal (`replies.county_can_ask`, three or more sources): its
   last sentence is now `Ask "what data do you have?" for the list.` in place of
   `Say "help" for the list.` Nothing else of it changes.
2. New keys in a source file, all optional (a file without them is as today):
   - at the top level, `"notes"`: a list of complete sentences about the source as a whole;
   - in a field, `"meaning"`: a phrase that completes "<dimension> is ..."; and `"notes"`: a
     list of complete sentences about the field.
   The loader accepts them (texts, not empty) and refuses any other new key as today.
3. `replies.county_facts` gives every fact it gives today, in today's order (so today's slot
   numbers stay), and after them, in this order:
   a. one fact naming every source: `I work with <n> sources of Montgomery County open data:
      <names>.` with the names as `county_about_text` joins them today (with one source:
      `I work with one source of Montgomery County open data: <name>.`);
   b. each distinct sentence of the sources' `notes`, in file order, once;
   c. for each source in file order and each of its fields with a `meaning`, in field order:
      `In <title>, <dimension> is <meaning>.`;
   d. each distinct sentence of the fields' `notes`, in file and field order, once.
   Each is a fact like any other: a slot of describe_data, usable in an about_data text,
   checked as today, at most four a reply.
4. The two county prompts (`config/agent_prompt_s3.md`, `config/agent_prompt_s3_talk.md`) say,
   under "How to write about the data", in one added line each: for a question about which
   sources or what data there is, use the fact that names every source; for what a field
   means, the fact that says so.
5. The notices once a thread (amends C11's "`details` and `about_data` answers carry the
   source's `notices` word for word"). A reply that would carry the notices carries them in
   full when no earlier turn of the thread's history (the turns `_Turn.run` reads) carried
   them in full; such a turn's stored record holds `"notices": "full"`. Otherwise the reply
   carries, in their place, exactly this one line (`replies.NOTICES_SHOWN`):
   `The county's data notice and the course-project note shown earlier in this thread still apply.`
   and its stored record holds `"notices": "short"`. A turn that carries neither has no such
   key. A thread whose earlier turns were stored before C57 shows the full notices once more.
6. `config/talk_rules.json`, `fallback_line`:
   `I can't answer that without running a count. Tell me what to count and for which period, and I'll show you the numbers.`
7. The county system message ends with one more block, after today's date (with talk on only:
   see "C57, the exact prompt texts" below):
   `About you: you run on <label>. If someone asks what model or company is behind you, say so plainly, as talk.`
   `<label>` is `replies.model_label(settings)`, from the active service (C51; in a second try
   of C56, the backup's): provider `anthropic` with "claude" in the model id: `a Claude model
   made by Anthropic`; `anthropic` otherwise: `a model served by Anthropic`; provider `nvidia`
   with "nemotron" in the model id: `a Nemotron model made by NVIDIA`; `nvidia` otherwise:
   `a model served by NVIDIA`. A talk text that holds one of these four labels passes the talk
   checks as far as the label goes. Rule 12 of the talk prompt and the like in the other
   prompt name "what model you run on" among the questions about him.
8. The 13 source files (`config/sources/*.json`), Nino's approval D-075:
   - top-level `notes`: `["These are Montgomery County, Maryland's own police records,
     published by the county. They are not statewide Maryland records."]`;
   - the `district` field: `"meaning": "the police district where it happened (the county
     calls the field \"District of occurrence\")"`, and `notes`: `"Montgomery County Police
     names six districts by their stations: district 1 is Rockville, district 2 is Bethesda,
     district 3 is Silver Spring, district 4 is Wheaton, district 5 is Germantown and
     district 6 is Montgomery Village."`; and, only in the files whose `district` values hold
     a district 8: `"Some records carry a district 8. It is not one of the six districts the
     county names, and the county's data does not say what it is."`
   The planning chat makes these edits with the build; no session edits these files.

Tests: point 1's sentence, word for word; a fixture source with and without each new key
through the loader and through `county_facts` (today's facts first and unchanged; a to d
after them, in order; a note shared by two sources once); the all-sources fact with one, two
and three or more sources; an about_data turn whose text uses the all-sources slot is sent
with every name; point 5 in one thread: the first about_data reply full, the second and
third short with the one line, a `details` reply after them short, another thread full again,
a thread with an old-style EXPLAINED turn (no `notices` key) full; the record's key; point 6
word for word; point 7: the block in the county system message for the four labels, absent
in the stage 1 system message, and a talk text with each label passing the checks; the
prompts' added lines.

## C58. C7: a compared month that the copy cuts short (live Soak 2, C17 run 3; planning chat on Fable 5.2, 17 Nov 15:23 EST)

Why: C7 answers PARTIAL_YEAR when whole years are compared and one is the copy's unfinished
year. In Soak 2 (`kit-log/raw/S3-county-check-live-2026-11-13.txt`) the model named the months
itself, January to November for 2025 and 2026, with a copy that ended on 14 November 2026: a
whole November stood against half of one, and the compare went through. A user sees "this
year is behind" for a reason that is only the calendar.

1. In `compare`, after today's checks and C7's: when every chosen count's period is a year
   with months (`{"year": Y, "months": {"from": A, "to": B}}`), all with the same A and B, in
   at least two different years, one of them the year of the copy's newest day, B the month
   of that day, and that day not the last day of its month: the tool answers
   `{"error": "PARTIAL_YEAR", "year": <that year>, "months": {"from": A, "to": B - 1},
   "why": "count both years again with these months"}`; when B - 1 is below A: no `months`,
   and `"why": "no month of that period is finished in this copy"`.
2. Nothing else changes: whole years are C7's as today; periods whose months differ, or that
   do not hold the copy's newest month, or a copy that reaches the last day of that month,
   are compared as today.

Tests: the Soak 2 case on a fixture copy that ends mid-month (PARTIAL_YEAR with months to the
month before); the same with a copy that ends on the month's last day (compared); months
that end before the copy's newest month (compared); three years with the same months; A
equal to B in the unfinished month (the second answer); whole years as before C58.

**C57, the exact prompt texts (planning chat, 17 Nov 15:37 EST; `tests/s3s2/test_s2_r13.py` pins every
other character of the two county prompts by a hash, so a tests session needs them word for
word).**
- Point 4, in both county prompts, a new line directly after the line that begins
  `- Start with "Here is what I know."`:
  `- For a question about which sources or what data there is, use the fact that names every source. For what a field means or where the records come from, use the fact that says so.`
- Point 7, in `config/agent_prompt_s3_talk.md` only, rule 12: `a question about you or about
  what you can do` becomes `a question about you (what you are, what model you run on) or
  about what you can do`. The "About you" block of point 7 is added to the county system
  message only when talk is on (`MOCO_TALK` on); with talk off the system message is as
  today.

## C59. The timing answer names the busiest day too (live rounds, N07; planning chat on Fable 5.2, 17 Nov 15:37 EST)

Why: "whats the busiest day of the week for arrests" is answered, in every live round, with
the busiest hour ("Saturday at 2 am"). S13 point 9 sends such a question to `analyze`
(`busiest` is one of its words), `timing` is the kind, and its one sentence names an hour
only. The person asked for a day.

1. `statwords.timing_phrase` puts the days first: `the busiest day of the week was <day>
   (<n>) and the quietest <day> (<n>); ` and then today's text unchanged (`the busiest hour
   was ...`). A day's figure is the sum of its 24 cells, the true values, shown as any figure
   is (`shown`: under the floor, `fewer than <floor>`). Ties are joined with `and` and the
   figure is followed by ` each`, as for the hours. Days are named as the hours' days are.
2. Nothing else changes: one slot (`{a1.timing}`), the table in details, the checks.

Tests: a table with one busiest and one quietest day; ties at the top; ties at the bottom; a
day whose total is under the floor; the days' figures against the sum of the cells; today's
hour text, unchanged, after the semicolon; a county turn whose finding uses `{a1.timing}`.

## C60. Two sentences in the county prompts, tried live (planning chat on Fable 5.2, 17 Nov 15:37 EST)

Why: N30 ("how many arrests in 2024 and 2025, and ...") got one total for the two years in
Haiku round 3, and N35 ("the past five years") ran the trend twice in one of three runs of
Soak 2. With these two sentences, on build-test (deployment 9e9e37e6, Haiku 5.5, 17 Nov,
three runs each): N30 gave each year its own figure in 3 of 3, N35 ran one trend in 3 of 3,
and C01, C06, C17, S01, S07, N01, N04 passed as before. A third sentence, for the busiest
day, changed nothing in 3 of 3 and is not added (C59 answers it).

In both county prompts, word for word:
1. Rule 3, after `never make one count per group yourself.`, one more sentence:
   `When the message asks for a figure for two or more years it names ("how many in 2024 and 2025"), make one count over those years with group_by year, so each year gets its own figure.`
2. Under "How to use analyze", after `with no period the program uses every month it has.`,
   one more sentence:
   `"The past five years" or "the last three years" names one: from the same month that many years back; call analyze once for it, never twice.`

Tests: each sentence is in each prompt once, in its place; the hash tests of the prompts take
C57's line and rule 12 change and C60's two sentences out before they compare.

**C56, answers to S3-R20-A's two questions (planning chat, 17 Nov 16:33 EST; to be copied into
`briefs/QUESTIONS.md` when no tests session runs).** 1. "Router" in point 6 means the second
try's run records (`manifest.json`), where C51 has it; `turn.json` gets no `router` key. 2. A
second try whose model fails after it made a count ends ANSWERED with the fixed rendering, as
a first try does today; that is not an end MODEL_UNAVAILABLE, so the note is added: the reply
that is sent holds the backup's count. The build does both.

## C61. Context and memory: what he knows about himself, what he said, the thread-wide rule, the clean-up (D-076; planning chat on Fable 5.2, 17 Nov 16:33 EST)

Why: D-076 and `kit-log/raw/THREADS-2026-11-17.txt`. In 96 messages Jeffrey disowned the
under-18 rule, could not say whether he is a county service, forgot the Census, asked where a
figure he had just given came from, and two plain messages gave the 17-year-olds by
subtraction. Three causes: nothing he reads is about himself; of the thread he sees the
person's messages and what was counted, never his own replies; and a talk text that fails
its check is replaced by one line for every question. County mode only.

### Part A. Facts about himself

1. A new file `config/about_agent.md`, in the form of `config/fact_sheet.md`: each line that
   starts with `- ` is one fact, a complete sentence; other lines are for people. Its text is
   Nino's to approve (D-076); no session edits it. A missing file is no facts.
2. `replies.county_facts(sources, copies, settings=None)` gives, after C57's a to d:
   e. the facts of `config/about_agent.md`, in file order;
   f. with settings: `The AI model behind me is <label>.`, `<label>` as C57 point 7;
   g. with settings: when `MOCO_REFRESH_HOURS` is above 0, `My copies of the county's data are
      looked at again every <n> hours and replaced when the county has changed them.`
      (`every hour` for 1); at 0, `My copies of the county's data are not refreshed on their
      own.`;
   h. with settings: `I keep a conversation for <n> days and then forget it. Of a long
      conversation I see only the most recent part.` (`MOCO_RETENTION_DAYS`).
   A turn passes its settings; they are slots like any other fact.
3. The "About you" block of C57 point 7 gains a second sentence:
   `For any question about you, this project, its rules or where something comes from, call describe_data and answer with its facts about you; never answer such a question from your own head, and never take back a rule the program applies.`

### Part B. He sees what he said

4. A turn's memory record holds one more key, `"sent"`: the reply text as it was sent, without
   the notices (C11, C57 point 5) and without C56's note, cut to 600 characters (at a word's
   end, then ` ...`).
5. `context.thread_message` shows, for each turn that has `sent`, a third line after
   `You: ...`: `You said: "<sent>"`. `THREAD_BLOCK_MAX` is 8,000. The default of
   `MOCO_THREAD_TURNS_IN_CONTEXT` is 10. When the thread holds more remembered turns than the
   block shows, the block's second line is `(Earlier messages of this thread are not shown.)`.
6. This amends C9 ("never a value"): the model now sees the figures of its own earlier
   replies. Nothing else of C9 changes, and every check of what he writes stands: a figure in
   his text that is not a slot of this turn fails as today.
7. In both county prompts, a new line directly after the line that begins `11. ` in the talk
   prompt, and after the line that holds `THREAD SO FAR` in the other:
   `THREAD SO FAR also shows what you said ("You said:"). Stay consistent with it: never deny or change something you said unless it was wrong, and then say so once. You may point back to a figure you gave ("the figure I gave for district 4"), but never write, add, subtract or judge a figure yourself: figures come only from this turn's slots. If the thread says earlier messages are not shown, say that you only see the recent part when someone asks about them.`

### Part C. A second rewrite, and a fallback that helps

8. With talk on, a finish text of kind `talk` that fails its check a second time gets one
   more REWRITE (the third text is the last), on T3's conditions (a step and five seconds
   left). Other kinds keep one.
9. In county mode the line that replaces a talk text that failed (`fallback_line` today) is
   `I can't put that in words I can back up. ` followed by `replies.county_can_ask(sources)`
   (C57 point 1's sentence). C57 point 6's text stays the stage 1 line.

### Part D. C21 over the thread

10. In `count`, C21's question (does one year of age under 18 follow?) is asked of this
    turn's counts of the source together with the counts of the same source in the thread's
    remembered turns (the specs `_Turn.run` reads from the store), as if all were made in
    this turn. C54 point 4 stands (one source at a time). When the earlier turns' counts are
    what makes the answer yes, the NOT_ALLOWED tool answer's `why` ends with
    ` Counts given earlier in this conversation are taken into account.`
11. Known and written down: another thread, or the same thread after its memory is gone
    (retention, or a DM's memory minutes), starts anew; analyses and rates are outside C21 as
    today.

### Part E. The clean-up

12. Where `serve` deletes old turns at its start (`purge_older_than`), it also removes, under
    the records folder, every folder whose newest file is older than `MOCO_RETENTION_DAYS`
    days, and logs how many. Nothing outside the records folder is touched; a folder that
    cannot be removed is logged and left.
13. The log file: when `agent.log` is larger than 5,000,000 bytes at the start of `serve`, it
    is renamed `agent.log.1` (replacing an older one) before logging starts.
14. With the data refresh on, the two clean-ups of 12 (turns and records) run again once a
    day beside it; a failure is logged and never stops `serve`.

Tests: A: a fixture `about_agent.md` through `county_facts` (order a to h, with and without
settings, the refresh sentence at 0, 1 and 6 hours), an about_data turn that uses one of its
slots, the block's second sentence. B: `sent` in the record (notices and the note taken out,
the cut), the third line, the not-shown line with more turns than shown, the two defaults, a
talk text that repeats a figure from `You said:` still fails NUMBER. C: three failing talk
texts (two REWRITEs, then the fallback), the third passing, a `finding` keeps one, the
county fallback's text. D: the two messages of thread P05 in one thread (the second
NOT_ALLOWED with the added sentence); the same two in two threads (both answered); two
sources (both answered); the earlier turn outside the remembered turns (answered). E: old
and new record folders, a folder that cannot be removed, the log at 4,999,999 and 5,000,001
bytes, the daily run.

**C61, four corrections before its tests (planning chat, 17 Nov 16:59 EST; round 23 had not started).**
1. Point 2: the facts e to h are given only with settings (a turn passes its own); without
   settings `county_facts` gives what C57 has it give. The file's path is the module constant
   `replies.ABOUT_AGENT` (`config/about_agent.md`), so a test can point it at its own file.
2. Point 7: the line goes into `config/agent_prompt_s3_talk.md` only (the other county prompt
   has no thread rule), directly after the line that begins `11. `.
3. Point 4: `sent` is kept in county mode only; point 5's not-shown line too. `THREAD_BLOCK_MAX`
   and the default of `MOCO_THREAD_TURNS_IN_CONTEXT` are the program's, in both modes.
4. Point 10: the remembered turns that count are those that ended ANSWERED (their figures
   were sent).
Also, the answer to S3-R21-A's question 5: `tests/s3/test_s3_c39.py::
test_three_sources_describe_data_still_covers_every_source` is to compare the facts of
before C57 only (the first seven of each of the first two sources); round 23 changes it.
The answers to its questions 1 to 4: 1. the file has one line, so SYNTHETIC mode gets C57's
line too; 2. the sources by what they count (C39's join); 3. as today: other keys are not
looked at; 4. hidden totals are never ranked: both days are named, `fewer than <floor> each`.

**C61, two additions after the threads of the C56 to C60 build (planning chat, 17 Nov 17:17 EST; round 23
had not started; build-test deployment 1507955d, 96 messages read).** Seen there: "what are the
police districts in montgomery county" got the list of sources, because his about_data text
failed GLUE and the fixed about text took its place; and "which district is Bethesda in?" was
declined although a fact now says it.
5. Point 9b (Part C): when an about_data text fails its check, the reply is not the fixed
   about text when the failed text named facts: it is `Here is what I know.` followed by the
   facts it named (at most four, in its order, each once), each as its own sentence, then the
   notices as point 5 of C57 has them. Style `fallback`, the failures on record as today.
   With no fact named it is the fixed about text as today.
   (`replies.facts_rendering(text, facts)`.)
6. Point 7's line ends with one more sentence:
   `Before you decline, or say that you do not know something about the data or about yourself, call describe_data and read its facts: decline only when no fact answers the question.`
7. C57 point 8's sentence about the six districts (17 Nov 17:37 EST; seen in the threads of the C61
   build, deployment 35c37424: asked "are these police districts or county council
   districts?" he still said the records cannot tell). The field's first note now reads:
   `The districts are police districts. Montgomery County Police names six of them by their stations: district 1 is Rockville, district 2 is Bethesda, district 3 is Silver Spring, district 4 is Wheaton, district 5 is Germantown and district 6 is Montgomery Village.`
   (The county police site: the county "is divided into six police districts"; D-075.) Round
   23 changes round 21's pin of the old sentence.

## C62. Four things the threads showed after C61 (D-078; planning chat on Fable 5.2, 17 Nov 21:05 EST)

Why: `kit-log/raw/THREADS-2026-11-17.txt`, the rounds after the C61 build. County mode only.

1. **The maker's name.** With talk on, a finish text of kind `talk` that holds one of the
   words `Anthropic`, `Claude`, `NVIDIA`, `Nemotron` (whole words, capitals not counting)
   anywhere but inside the label of the turn's own model (`replies.model_label(settings)`,
   word for word) fails the talk check with the code `MAKER`, after the codes of today's
   check; `found` holds the words. It is a failure like any other: REWRITE, then C61's
   fallback. `config/talk_rules.json`, `rewrite_hints`, gains
   `"MAKER": "Say what you run on only in the exact words of the About you line, and say nothing else about who built you: the facts of describe_data say that."`
   Other names (ChatGPT, OpenAI) are not looked at.
2. **The refusal that is about earlier figures.** When C61 point 10's added sentence was
   given in a turn (the thread's earlier counts are what made the count NOT_ALLOWED) and the
   turn ends UNSUPPORTED with reason NOT_ALLOWED and the fixed text, that text's first
   sentence is
   `With the figures already given in this conversation, that count would give one single year of age under 18, so I don't give it.`
   in place of `I don't count a single year of age under 18; I can count ranges of two years or more.`
   Nothing else of the reply changes.
3. **Two sentences at the end of C61 point 7's line** (`config/agent_prompt_s3_talk.md`), after
   `decline only when no fact answers the question.`:
   `When someone asks which of several figures you gave is the highest or lowest, or what the difference is, do not point back: count them again in one count with a breakdown, or count each and call compare, and let the slots say it. When someone asks what you answered earlier, make the same count again and give it.`
4. **A DEFECT: the wrong kind of ending after describe_data.** A `finish` of kind `finding` in a
   turn that called describe_data, made no result and had no count error is an about_data
   finish: it goes through `county_about` with its text, as kind `about_data` does (so C61
   point 9b applies when it named facts). Today it ends UNSUPPORTED,
   UNRECOGNIZED_QUESTION, "I couldn't read that as a question I can answer." (3 of 10 runs
   of "what are the police districts in montgomery county" on 17 Nov; the steps are in the
   deploy log of build-test deployment 8f306228).

Tests: 1: a talk text with each of the four words outside the label fails MAKER and is not
sent; inside the exact label it passes; the backup's turn has the backup's label; ChatGPT
passes; kind `finding` and `about_data` texts are not checked for it; the hint. 2: thread
P14's "17 to 18, then 18" and P05's "under 18, then 10 to 16" end with the new sentence; a
single age asked outright keeps the old one. 3: the two sentences, word for word, once,
in place; the prompt hash tests take them out. 4: describe_data, then finish kind `finding`
with a text that names facts (9b's reply), with a passing text (sent, kind about_data), and
with a text that names none and fails (the fixed about text); with a result or a count error
in the turn, kind `finding` is as today.

**C62, a fifth point (17 Nov 21:06 EST; `kit-log/raw/CHAT-BUILDS-check-11.txt`: C56, C57-C60, C61 A-C and
C61 E pass; C61 D fails with one DEFECT; round 24 had not started).**
5. **CHAT-BUILDS-check-11's DEFECT 1: an earlier count keeps the days of its own copy.** C61
   point 10 read the thread's earlier counts with this message's copy. When the copy changes
   between two messages (the refresh), an earlier period that the old copy cut short is read
   as reaching the new copy's last day: one year of age under 18 can follow in one thread
   (the check's probe P19), and a harmless count can be refused (P20). So:
   a. a remembered count holds one more key, `"days"`: the first and the last day its copy
      covered when it was counted, as two ISO dates (what `counting.coverage(source, copy)`
      gave in that turn);
   b. in C61 point 10's check each earlier count is read with its own `days` (C21 answer 3:
      a period is cut to the days of the copy it was counted from), this turn's counts with
      this turn's copy; a remembered count with no `days` (stored before C62) is read with
      this turn's copy, as today;
   c. `counting.one_year_under_18(source, specs, copy=None, days=None)`: `days`, when given,
      is a list as long as `specs`, each entry `None` (use the copy) or a pair of dates.
   The check's PROOF GAP 1 gets its test in the same round: an earlier count of another
   source is never read into this source's check (its probes P18 and P18b).

**C62, answers to S3-R24-A's three questions (planning chat on Fable 5.2, 17 Nov 22:11 EST; also in
`briefs/QUESTIONS.md`).** 1. Round 25 changes the two tests
(`tests/s3/test_s3_c61b.py::test_b7_the_line_directly_after_rule_11_of_the_talk_prompt` and
`test_b7_the_line_is_sent_with_talk_on`) to C62's line: C61's line, one space, C62 point 3's two
sentences, and nothing else. 2. Point 5c: a pair is two `datetime.date`; an entry of two ISO
date texts (the memory record's form, 5a) is taken too and means the same. 3. Point 1: every
text sent as talk is checked for MAKER, a plain text read as talk included (T1, T13), as C61
point 8 was read (R23-C2); round 25 pins it.

**C62, one more answer, after CHAT-BUILDS-check-12 (planning chat on Fable 5.2, 17 Nov 23:42 EST; its "two
readings", reading 2, probe Q03).** Point 1, "inside the label ... word for word": the label is
the label too when its first letter is a capital, as at the start of a sentence (`A Claude model
made by Anthropic runs me.` passes). Nothing else of it may differ: any other capital, or a word
missing, and its maker's words count as outside the label. Round 27 pins it; the build is made
with C63's. The check's reading 1 (a remembered count with no `days` is read with this message's
copy) stands as point 5b has it: it reaches only threads stored before C62 went live (17 Nov
23:31 EST), for the 30 days they are kept.

## C63. An about answer that is only facts is written by the program (D-080; planning chat on Fable 5.2, 17 Nov 22:58 EST)

Why: `kit-log/raw/THREADS-2026-11-17.txt`, "THE C62 BUILD IN THREADS" and "WHAT THE MODEL WRITES WHEN AN
ABOUT ANSWER FALLS BACK". The model chooses the right facts and writes them with no full stops
between (`Here is what I know. {f93} {f94}`), so the check fails it (GLUE), the rewrite fails
again, and C61 point 9b's rendering is sent: three model calls for what one decides (24 of 142
messages, 9 to 18 seconds each against about 8). And a text that passes can leave out a fact's
full stop or repeat the opening (thread P05, replies 2, 7 and 8). County mode only: with
`MOCO_DATA` other than `county` nothing changes.

1. **A plain facts text.** A finish text that reaches `county_about` (kind `about_data`, or C62
   point 4's `finding`) in a turn that called describe_data, with `MOCO_REPLY_STYLE` not
   `fixed`, is a plain facts text when (a) it names at least one fact slot, (b) every slot it
   names is one describe_data offered in this turn, and (c) with its slots and every
   `Here is what I know` (capitals not counting) taken out, no letter and no digit is left.
   Spaces, line breaks, full stops, commas and other marks between the slots do not count.
2. **What is sent for it.** `Here is what I know.` and then the facts it named, each once, at
   most the first four, in its order, each as its own sentence ending with a full stop; then
   the notices as C57 point 5 has them (the words of `replies.facts_rendering`). The text is
   not checked: no failure is recorded, no REWRITE is given, with talk on or off. The end is
   EXPLAINED, kind `about_data`, style `agent`; the draft on record is the model's text; the
   memory's `sent` is what was sent.
3. **Every other text is as today.** A text with words of its own, a slot that was not
   offered, or no slot goes through today's check; when it fails, the REWRITE and C61 point
   9b's reply are as today. A turn that did not call describe_data, and `MOCO_REPLY_STYLE`
   `fixed`, get the fixed about text as today. No prompt changes.

(`replies.plain_facts(text, facts)`: the rendering, or None when the text is not plain.)

Tests: the three forms seen live (`Here is what I know. {f1} {f2}`; the slots on lines of
their own; `Here is what I know. {f1}` with no full stop) are sent as the rendering, style
`agent`, no failures, one finish and no REWRITE, talk off and on; the opening twice is sent
once; the opening left out is put in; five slots give the first four; a slot twice is given
once; a text with a word of its own, with a slot that was not offered, or with a digit
outside the slots is checked as today (and 9b's reply stands for one that fails and names
facts); `{f1}. {f2}.` gives what it gives today; C62 point 4's `finding` with a plain
facts text is sent the same way; SYNTHETIC mode, a turn with no describe_data and
`MOCO_REPLY_STYLE=fixed` are untouched; the notices in full once a thread, short after.

**C63, one addition and two answers (planning chat on Fable 5.2, 18 Nov 00:06 EST; round 26's tests are in,
round 27 has not started).**
4. **The word `and` between slots does not count either** (point 1c). Seen in the live check
   of the C62 build, thread P06, reply 8: the model joined two facts with `and`, which C13's
   rule 1 lets a text do, and the reply read "... I count arrest records, not people and My copy
   of Montgomery County Police arrests covers ...". A fact is a sentence of its own. So in
   point 1c the whole word `and` (capitals not counting) is taken out with the slots and the
   opening before the letters are looked for: `Here is what I know. {f1} and {f2}.` is a
   plain facts text and is sent as two sentences. Any other word keeps the text out of C63.
Answers to S3-R26-A's questions: 1. Yes: `{f1}. {f2}.` is a plain facts text, so the opening is
put in front; "what it gives today" meant the same two facts with their full stops, and round
27 pins the opening. 2. Yes: the memory record's `reply_text` is the finish text as the turn
read it, and turn.json's `finish_text` the text as written; no other field is meant.

Tests (round 27): `{f1} and {f2}.`, `{f1}, and {f2}` and `{f1} AND {f2}` are sent as the
rendering, style `agent`, no failure, one finish; `{f1} and also {f2}` and `{f1} band {f2}`
are checked as today; `{f1}. {f2}.` begins with the opening.

## C64. Four weak spots the harder threads showed (D-081; planning chat on Fable 5.2, 18 Nov 00:51 EST)

Why: `kit-log/raw/THREADS-2026-11-17.txt`, "THE REST OF THE LIVE CHECK, READ" and "FOUR HARDER
THREADS". Nino, 18 Nov 00:49 EST: "i approve and find a way to address the weak spots". County
mode only: with `MOCO_DATA` other than `county` nothing changes.

1. **A figure in plain talk.** Told that his number is wrong ("the county's own report says
   9,112. yours is wrong", "my professor says your number is wrong") he writes the figure
   into a talk text, the check refuses it (`NUMBER`) three times and the stock line is sent:
   2 of 2. So: when a county talk text ends the turn on C61 point 9's fallback and `NUMBER` is
   among the failure codes of the text that ended it, the line sent is
   `I only give a figure by counting it, so I do not repeat, change or work on one in plain talk. My counts come from my saved copy of the county's data, and I cannot check them against any other source. Ask me to count it again, or say "details" after a count to see how it was counted.`
   in place of `I can't put that in words I can back up.` and what follows it. Style
   `fallback`, the failures on record, as today. Without `NUMBER` the line is as today. And
   `config/talk_rules.json`, `rewrite_hints`, `NUMBER` gains one sentence at its end:
   `In talk, point at a figure with the words "the figure I gave" and write no number.`
   (The hint is one line of one file, so SYNTHETIC mode's REWRITE shows the sentence too, as
   C57's fallback line does: S3-R21-A answer 1.)
2. **The start of a long thread.** He is shown the last ten turns; asked for "the very first
   count" he named the earliest one he still saw, and one message later another. Three
   sentences at the end of C61 point 7's line (`config/agent_prompt_s3_talk.md`, after C62
   point 3's two sentences, one space before them):
   `When THREAD SO FAR says that earlier messages are not shown, you do not know how the conversation began. Never call a message, a question or a count the first, also when you count it again: call it the earliest one still shown to you. When asked for the first one, or for everything said or counted so far, say in your text that the start of the conversation is no longer shown to you, and go by what is shown.`
   Nothing of the program changes for it. Tried on the real model before its tests, twice:
   a first wording (one sentence) still had a count that was run again called "the first"
   (1 of 5); with this wording nothing was called the first in 8 replies, 4 of them said that
   the start is not shown and 4 were the program's rendering of the count with no such claim
   (`kit-log/raw/THREADS-2026-11-17.txt`, the two trials of the C64 build).
3. **A count that was not made is said.** Asked for a share or a comparison of which one
   count is refused, the reply showed the count that was made and nothing about the other.
   So: when a turn ends ANSWERED and, in it,
   a. a count was refused by C21's check of the message and the thread (the NOT_ALLOWED answer
      whose `why` begins `with this count, the figures of this message would give`), the
      reply holds the line
      `(One count asked for here is not given: with the other figures it would give one single year of age under 18.)`
   b. a count was refused with TOO_MANY (C8's eight counts), the line
      `(I make at most 8 counts in one message, so not everything asked for is here. Ask for the rest in a new message.)`
      with the program's own number;
   c. a compare was refused with MIXED_SOURCES, the line
      `(Counts of different sources are never compared with each other.)`
   Each line once, in this order, directly after the kept line and the widened line (C10's
   order), in every style (`fixed`, `fallback`, `agent`). They are part of the reply: the
   memory's `sent` and turn.json hold them. A turn that does not end ANSWERED is as today
   (the code's own row says it).
4. **Who to write to.** "who do I complain to about you?" got who he is. `config/about_agent.md`
   becomes version 2 with a ninth fact:
   `Questions or complaints about me go to the owner of this project, who set me up in this Slack workspace. I have no address to give.`
   Nino has not read these words yet (he is away on 18 Nov until about 16:00): they say
   nothing that the eight facts he approved do not imply, and he may reword them.

Tests: 1: a talk text that fails `NUMBER` at each try ends on the new line, with `NUMBER` and
another code too; a text that fails only `LABEL` or only `MAKER` ends on today's line; the
hint; SYNTHETIC mode's fallback line untouched. 2: the three sentences, word for word, once,
in place, in that prompt only; the prompt hash tests take them out. 3: thread P16's "under 18,
then the share aged 10 to 16" (line a, style fallback and agent); nine counts in one message
(line b); a compare of two sources' counts with a count made (line c); two of them in one
turn, in order, each once; a turn with none of the three has no such line; a turn that
ends UNSUPPORTED has none; `sent` holds the line; C21's own single-age refusal that the
program widens keeps only the widened line. 4: nine facts from the file, the ninth offered by
describe_data with the others; the tests' own fixture of the file is theirs.

## C65. Two ways round the under-18 rule, closed (D-082; planning chat on Fable 5.2, 18 Nov 01:47 EST)

Why: `kit-log/raw/THREADS-2026-11-18.txt`, threads P20 and P21 on the real model (the program
that is live). One thread gave the arrest records of people under 18 in 2025 and, three ways,
the same for ages 10 to 16: (a) a trend of ages 10 to 16, whose table shows each year's count;
(b) two counts, January to June and July to December; (c) two counts, recorded as male and
recorded as female. Each time the difference is the 17-year-olds of 2025. C21 looks at the
figures of one kind (the same days, the same other filters) and at counts only: C21 answer 6
and C61 point 11 named these two limits. Jeffrey says "in one answer or across a
conversation", so they are closed. A safeguard only: nothing that was refused is now given.
County mode only.

1. **Every part of the records, not one kind.** C21's question stays: do the figures of this
   message and of the thread's ANSWERED turns (C61 point 10, each with the days of its own
   copy, C62 point 5), for one source, added and subtracted, give a number for records that
   are all of ONE year of age under 18? What changes is what may be added. A figure counts
   the records of its days, of its values of each field it names, and of its ages (a kind
   and a band, as `counting.age_figures` gives them). Two figures of different kinds can now
   be added or subtracted where their records fit together: the halves of a year make the
   year; the values of a category or a flag, with the records that have no value recorded,
   make all records; the hours of a day make the day. The check is exact: it refuses when,
   and only when, some sum of the figures leaves records of one single year under 18 and
   nothing else, for all records or for any part of them. A count that is only one step of
   such a sum is still given (under 18 in 2025, then ages 10 to 16 from January to June);
   the count that would complete it is refused (then July to December). What C21 refused it
   still refuses.
   A constraint or a field the check cannot read (none exists today) is held against every
   value, and the check then errs on the side of refusing.
2. **What a statistic shows is a figure too.** A statistic (`analyze`, any kind, and a rate)
   shows a table, sums and parts of its records. For this check it stands for a figure of
   EACH part of the records of its days, whatever its other filters, with the ages of each
   of its bands: the band of its own age filter (every usable age when it has none); the
   band of any age filter among its options; the source's own age bands when it is broken
   down by age band; under 18, and 18 and over, when it uses the made-up `under_18`.
   a. A statistic is refused, before anything is computed, when its figures with those of the
      message and the thread would give one year of age under 18: the tool answer is
      NOT_ALLOWED with C21's `why` (and C61 point 10's sentence when the thread's earlier
      figures are the cause), and the turn ends as it does for a count that C21 refuses
      (C62 point 2's sentence, C64 point 3a's line).
   b. A count is checked against the statistics of the message and of the thread's ANSWERED
      turns as it is against their counts.
   c. A remembered statistic holds `"days"` as a remembered count does (C62 point 5a); one
      with none is read with this message's copy.
3. **The reply texts are C21's, C62's and C64's. No prompt changes.**
   `counting.one_year_under_18(source, specs, copy=None, days=None, shown=())`: `shown` is the
   statistics' figures, from `counting.shown_figures(source, spec, options, start, newest)`.
4. **`reset` forgets the conversation, not which counts were given** (added 18 Nov 02:10 EST, found by
   reading the code: not tried in Slack). Today `reset` deletes the thread's turns, and with
   them everything C61 point 10 reads: under 18, then `reset`, then ages 10 to 16, gives the
   17-year-olds in one Slack thread. So, in county mode, `reset` keeps for each of the
   thread's ANSWERED turns that hold a count or a statistic one stripped record: the time,
   the status, and of each count or statistic its kind, spec, days and, for a statistic,
   its name and options. No question, no reply text (`sent`), no `read_as`, no user id, no
   run id, nothing else. The stripped records are read by C21's check alone
   (`Store.given_before_reset(thread_key, limit)`): the model is never shown them, and a
   follow-up, `details`, the kept filters, C57's notices and "who was in the thread" (C37)
   do not see them: for all of those the thread is empty after `reset`, as today. They are
   deleted when they are older than the retention days, as turns are; a second `reset` keeps
   them and adds the newer ones. The reply to `reset` in county mode becomes
   `Done. I've cleared what I remembered of this conversation. I keep only a list of which counts I gave here, with no figures and no words of yours, so that my rule about single years of age under 18 still holds.`
   With `MOCO_DATA` other than `county`, `reset` and its reply are as today.
5. **The check reads the whole thread** (added with point 4). C21's check reads every
   remembered turn of the thread, up to the newest 5,000, and the stripped records of point
   4. In a top-level direct message the model is shown only the last
   `MOCO_DM_MEMORY_MINUTES` minutes; the check reads the turns before them too: under 18, and
   ages 10 to 16 an hour and a minute later in the same direct message, is refused. What
   the model is shown and what the check holds against are two things.
   This takes back C61 point 11's limit "a direct message's memory minutes": the old test
   `tests/s3/test_s3_c61d.py::test_d_the_earlier_turn_outside_the_remembered_turns_is_answered`
   turns round (the second message is now refused), and round 29 changes it.

Tests: 1: the three ways of threads P20 and P21 each end with the last step refused (the
second half-year; the second of two genders, with the no-value figure; the count after the
trend, and the trend after the count); each first step is answered; the pairs C21 refuses
today are refused as today; counts that cannot be combined are both answered (under 18 in
one year and ages 10 to 16 in another; ages 10 to 16 of one district and then under 18 with
no district filter);
four quarters; the hours in two ranges; a copy that changes between the messages (the days of
each figure's own copy); another source's figures are never read in. 2: for each kind of
statistic and for a rate, an age filter of 10 to 16 after an answered under-18 count of
days it shares is refused before R runs; the same statistic for days the count does not
share is given; a statistic with no age filter after under 18 is given; under 18, then 17
and over, after a trend of every age is refused; a rate by age band after ages 10 to 16 is
refused; a part of ages 10 to 16 of a whole under 18 is refused on its own; the memory
record holds a statistic's `days`. Speed: thirty figures of ten turns are decided in under
two seconds. 4: under 18, `reset`, ages 10 to 16: refused with C62 point 2's sentence; the
stripped records hold only what point 4 names (no question, no `sent`, no user id); after
`reset` the model's thread block is empty, `details` finds no answer, no filter is kept, the
notices are shown in full again; two resets; the stripped records go with the retention
days; the reply's words; SYNTHETIC mode as today. 5: a top-level direct message, a count 61
minutes after another: the model is not shown the first, the check refuses the second.

**C65, answers to S3-R29-A's five questions (planning chat on Fable 5.2, 18 Nov 08:04 EST; also in
`briefs/QUESTIONS.md`).** 1. The pair "under 18 of one district, then ages 10 to 16 of another"
is refused, as C52 point 4 has it: C65's Tests were wrong to list it among the pairs that are
both answered, and "what C21 refused it still refuses" governs. Pairs that truly cannot be
combined are two years, or one district and then no district filter. 2. Yes: C52 point 1
stands inside the check. The figures are `counting.age_figures`' figures, so where they hold
a little more than the count keeps, the check refuses a little more, never less. "Exact"
means exact over those figures. 3. The wide reading: any sum, each figure any number of
times with either sign, that is not zero and lies in one year of age under 18. 4. Yes: one
flat list, each statistic's figures as `shown_figures` returns them. 5. The period cut to the
copy's days, as a count's: wider than S2's window of full months, so it errs on the side of
refusing.


**C65, two more points (18 Nov 09:29 EST; `kit-log/raw/CHAT-BUILDS-check-14.txt`: C64 passes; C65 fails with two
DEFECTS and no proof gap; both are ways to one year of age under 18 that the build left open).**
6. **Check 14's DEFECT 2: the check's figures are what a count really shows.** `counting.tally`
   leaves a record out of a count's total and groups when it has no value in ANY category or
   flag field the request filters or breaks down by, and counts it on the left-out line of
   each such field; a filter on a field where the record has no value is not asked of it.
   C65's sums need exactly that. So `counting.age_figures` gives:
   a. a category filter that names every label as the filter it is: the records with one of
      those labels. C52 point 1's reading (such a filter "is no filter") is taken back, and
      with it C65 answer 2: under C65's sums it could hide a year. What C52 point 1 refused
      is still refused: those labels and the count's no-value figure make every record.
   b. no figure for the total of a count that is broken down by a category or a flag it does
      not filter: that total holds only the records with a value there, and is the sum of
      its groups.
   c. the left-out figure of a field as: no value recorded for that field; each of the
      count's OTHER category and flag filters read as "one of these values, or none
      recorded"; its hour filter, its days and its ages as they are.
   d. Two things stay on the side of refusing, because the records in the way are few and
      the sum would in practice be the year's figure. A count with no age filter also holds
      the records with no usable age: the check reads it as the count of the usable ages.
      And the check says yes when a sum leaves one year of age under 18 either exactly, on
      the figures of a to c, or once the records that have no value recorded in more than
      one of the fields the figures name are taken not to exist
      (`counting._parts(source, figures, one_gap=True)`).
   So the check never refuses less than the figures allow. Of round 29's cases one turns
   round, towards refusing (named under Tests).
7. **Check 14's DEFECT 1: a rate's age bands are the Census's.** For a rate (`analyze`, kind
   `rate`) broken down by age band, point 2's figures have the bands of
   `config/census.json` (`records`, `age_band`: 10 to 17, 18 to 24, 25 to 34, 35 to 44, 45 to
   54, 55 to 64, 65 and over), each cut to the source's usable ages and to the rate's own
   ages, in place of the source's own bands. `counting.shown_bands(source, spec, options=None,
   age_bands=None)` and `counting.shown_figures(source, spec, options=None, start=None,
   newest=None, age_bands=None)`: `age_bands` is that list, each (first, last) with last
   None for "and over". The program passes it for a rate of this message, for a remembered
   rate of the thread and for one kept through `reset` (`"stat": "rate"`), and for no other
   statistic.

Tests: 6: check 14's two turns (18 and over by gender and race; then 17 and over, one gender,
every label of race, two years, by year): the second is refused; with the first turn a year
earlier both are answered; C52 point 1's pairs (round 16) are refused as before. An oracle of
the tests' own that builds every figure of a count from `counting.tally` run on one record at
a time (every combination of an age inside and outside the usable ages, each of two
categories and a flag with and without a value, two days) and decides by its own exact
arithmetic: with the records of no usable age left out, "yes" exactly, or "yes" once the
records with no value in more than one field are left out too. It agrees with
`counting.one_year_under_18` on at least 2,000 seeded sets of one to four counts, and the
function never says no where the oracle with every record says yes (the planning chat's own,
6,000 sets: no difference; main's function differs from it). Round 29's case "three fields,
the last in another district (does not fit)" turns round under d: it is now refused (the
three counts' no-district figures differ by one year once a record with neither a district
nor a race is taken not to exist). 7: a rate by
age band, then ages 17 to 64 of its year: refused, and in the other order; then 18 to 64
instead: answered; a rate by gender, then 17 to 64: answered; the same for a remembered rate
of an earlier turn and for one before a `reset`; `shown_bands` with `age_bands` of a source
whose usable ages end at 17.

**C65 point 6, answer to S3-R30-A's question 1 (planning chat on Fable 5.2, 18 Nov 10:55 EST; also in
`briefs/QUESTIONS.md` once no tests session runs).** The tests' reading is right and the
example under Tests was wrong: "with the first turn a year earlier" read literally (18 and
over by gender and race in 2024; then 17 and over, one gender, every label of race, 2024
and 2025, by year) gives the 17-year-olds of 2024 and is refused. The pair meant was the one
that shares no day (the first turn's year, then two other years by year): both answered.

**C65, points 8 and 9 (18 Nov 10:22 EST; found by the planning chat while round 30 ran, by reading what
check 14 said it had not checked and by timing the check on long conversations).**
8. **The age chart's bars are figures.** A distribution draws a chart of the ages in two-year
   steps from an even age (`analysis_r/theme.R`, `draw_ages`: 10 and 11, 12 and 13, 14 and 15,
   16 and 17, 18 and 19, and so on), one row of bars for each of its groups. For the check a
   distribution therefore also stands for a figure of each of those steps, cut to its own
   ages: `counting.shown_bands(..., steps=True)` and `shown_figures(..., steps=True)`. The
   program passes `steps` for a distribution of this message, for a remembered one and for
   one kept through `reset` (`"stat": "distribution"`), and for no other statistic. So a
   distribution whose own ages cut a step down to one year under 18 (ages 10 to 16; 15 to
   17; 17 to 30) is refused on its own before anything is computed, with C21's `why` and no
   word of earlier figures; and after a distribution the count that would give one year with
   its bars is refused (the ages of everyone, then ages 10 to 16). A bar's height is read off
   a scale and a bar under the floor is left blank: the check takes every bar as an exact
   figure, which errs on the side of refusing.
   Named and left open, because closing it changes how a statistic is worked out (Nino's;
   `docs/PROPOSALS-2026-11-18.md`, item 10): the median and the quartiles themselves. R's
   method (type 7) can land between two ages ("16.5"); when it does, the number of records
   at or below the lower age follows exactly.
9. **A big conversation is decided slice by slice.** The work of the exact check grows with
   the product of everything the thread's figures cut the records by. A thorough
   conversation about one year (breakdowns by district, gender, month, race and hour) took
   main's check 3.4 seconds for six counts, and with a trend before them more than 3 GB of
   memory (the planning chat's measurement, 18 Nov): the program that is live would have
   stopped answering. So `counting._one_year_somewhere` decides in one piece only while
   rows × rows × columns of its table is at most `counting.WORK_EXACT` (10,000,000). Beyond
   that it takes the dimension with the most entries (the stretches of days, or the values
   of one field) and decides each entry's slice on its own, every figure taken as known for
   the slice alone, and says yes when any slice says yes; a slice is cut again while it is
   too big. Slices that hold the same figures in the same way are decided once. This never
   turns a yes into a no: a sum that leaves one year of age leaves it in some slice. It can
   turn a no into a yes for a count that is one step of a sum across the dimension that was
   sliced; that count is then refused one step early. Two things are exact at every size:
   figures of adults only are left out of a slice in which no figure reaches across the
   eighteenth birthday, and figures that are the same in a slice count once.

Tests: 8: a distribution on its own: of every age, of under 18, of ages 16 to 17: given; of
ages 10 to 16, 15 to 17 and 17 to 30: refused before R runs, C21's `why` without C61 point
10's sentence; the ages of everyone, then ages 10 to 16: refused with C62 point 2's
sentence, and under 18 instead: given; then ages 17 to 18: given, and 19 and over after
them: refused; a distribution remembered from an earlier turn and one from before a `reset`;
a source whose usable ages end at 17; no other statistic is given the steps. Round 29's three
cases with a distribution of ages 10 to 16 turn round (it is now refused on its own, also for
days the count does not share). 9: with `WORK_EXACT` set to 0, and to 20,000, the function
never says no where it says yes with the bound out of reach (at least 1,000 seeded sets of
the tests' own, and round 30's oracle: never no where reading (ii) or (iii) is yes); the
examples of points 1 to 8 give the same answers as before with the bound as it is; a thread
of 22 counts of one year with every breakdown the fixtures allow, alone, after a trend, and
after a trend, a rate by age band and two distributions: each decided in under two seconds
and under 300 MB at its peak; one sliced case where a first step is refused early, written
down as what point 9 allows.

**C65, point 10 (18 Nov 15:31 EST; from check 15's probes T09, T10 and X1, read in its record while it was still
being written; held on the branch `chat/c65-p10`, not on main).**
10. **A figure that "details" can show is held too.** `details` shows the most recent earlier
    turn of the thread that has results, whatever that turn's ending. A turn can make a count
    or a statistic and still end as a question (the model then asks for a period): its reply
    holds no figure, but "details" after it shows the count's total or the statistic's table,
    and C61 point 10 has the check read only the thread's ANSWERED turns. So: under 18 made in
    a turn that ends as a question, "details", then ages 10 to 16: one year of age from one
    thread. C61 point 10's word "ANSWERED" is taken back: the check reads the counts and
    statistics of every remembered turn of the thread, whatever its status, and `reset` keeps
    the stripped record (C65 point 4) of every turn that holds one. This turns two old tests
    round: `tests/s3/test_s3_c61d.py::test_own_d5_only_turns_that_ended_answered_count` and
    `tests/s3/test_s3_c65.py::test_p2_a_statistic_of_a_turn_that_did_not_end_answered_is_not_read`.

Tests: 10: check 15's T09 and T10 through county turns (a count made, the turn ends as a
question, "details" shows its total, the completing count is refused with C62 point 2's
sentence), in both orders; its X1 (a trend made, the turn ends as a question, then under 18 of
one of its years: refused); the same without "details" in between: refused too (the figure
could still be shown); a turn that ended as a question and made nothing: nothing held; `reset`
after such a turn keeps its stripped record, and the completing count after `reset` is refused.

## C66. Three small wordings from the live check of 18 November (D-081; planning chat on Fable 5.2, 18 Nov 09:29 EST)

Why: `kit-log/raw/THREADS-2026-11-18.txt`, runs 4 and 5, and two short trials on the real
model. County mode only. Wording only: nothing he may count changes and no check gets looser.

1. **"I've noted it as a request." once.** In `replies.county_text`, when the turn's own text
   (`lead`) takes the place of a row's first sentence and already holds the words
   `noted it as a request` (capitals not counting; a curly apostrophe read as a straight
   one), the row's own `I've noted it as a request.` is left out. Nothing else of the row
   changes. (Thread P21 A07 ended with the sentence twice.)
2. **A refusal under the age rule is a rule, not a lack in the records.**
   `config/agent_prompt_s3_talk.md`, the line that begins `When you decline or ask, add text:`,
   gains at its end, after `the program adds the facts.`:
   `When a tool answered NOT_ALLOWED, the reason is a rule of this project: say that it is a rule, and never say that the records or the data cannot do it. When THREAD SO FAR says that a count was refused under that rule and someone asks why, call describe_data and answer with its fact about the rule: never call it your mistake, and never offer to count it after all.`
   (Thread P05 A01: "The records cannot count a single young age on its own". The other
   county prompt has no such line and is not changed.)
3. **The thread shows that the rule refused a count.** A county turn in which a count or a
   statistic was refused with NOT_ALLOWED (a single year asked outright, C21's check or
   C65's) stores one more key in its memory record, `"age_rule": true`, whatever its ending
   (asked back, declined under another code, answered with a count held back, refused).
   `context.what_was_done` adds for such a turn, after what he did and before ` and said:`,
   ` (a count was refused under the rule about single years of age under 18)`. A turn
   without the key reads as today. The stripped records kept through `reset` (C65 point 4) do
   not hold the key. (Trial 1: "how many 16 year olds were arrested in 2025?" was asked
   back with only "Would a range that includes that age work for you?", his reason having
   failed a check; to "why not?" he then said "That was my mistake ... I could have counted
   it straight away" and offered to count the single age. The program would have refused
   it; the sentence was false.)

Tests: 1: a decline whose text ends with the sentence (straight and curly apostrophe, capitals)
under each of the three codes whose row has it: once in the reply; a text without it: the
row's sentence as today; NEEDS_other and a row without the sentence: unchanged. 2: the two
sentences word for word, once, in place; the turn is sent them with talk on and not with
talk off; the prompt hash tests take them out. 3: a single year asked outright that ends as a
question back, a count refused by C21's check beside one that is made, a statistic refused
by C65's, and a plain refusal: each stores the key and the next turn's thread block holds the
words once for that turn; a turn with no refused count, a refused count of another kind
(TOO_FINE) and a SYNTHETIC-mode turn do not; after `reset` nothing of it is shown and the
stripped records hold no such key.

**C66 point 3, answer to S3-R30-A's question 2 (planning chat on Fable 5.2, 18 Nov 10:55 EST).** Yes: a
turn whose count was refused with NOT_ALLOWED because the model sent age bands of its own
("age bands are the source's own") stores the key and gets the note too. Its reply is the
age rule's sentence like any other NOT_ALLOWED, and bands of one's own are refused because
they could cut the ages into single years. The key is stored for every NOT_ALLOWED of a
county turn, whatever its `why`.

## C67. A trend asked after a count of one year (D-082; planning chat on Fable 5.2, 18 Nov 11:34 EST)

Why: `kit-log/raw/THREADS-2026-11-18.txt`, runs 7 and 8. In one thread, "how many arrests were
there in 2024, by district?" and then "are arrests going up or down since 2021?" ends "That
needs at least 24 full months of records, and this selection has fewer" (8 of 9 times for
three wordings, on the real model). The prompt tells the model to leave a statistic's period
out unless the message names one, "with no period the program uses every month it has"; the
program instead keeps the period of the thread's last answer (one year), and a trend of one
year is too short. It is the demo's fifth line. County mode only. This adds to S13 point 1 of
`docs/S3S-DESIGN.md` ("a period that IS pending or kept is used as today"): it is still used,
unless the statistic cannot be run on it.

1. **A statistic whose kept period is too short is run on every month.** In `analyze` (every
   kind but `rate`), when the request's period was not stated in this message but taken from
   the thread (the pending question's or the last answer's: `"period" in carried`) and the
   statistic then fails with TOO_LITTLE (whatever its rule), it is run again on every month
   of the copy (`coverage_start` to the copy's newest day), as S13.3 does for a
   before-and-after whose sides are too short. The kept period is then not kept and not
   named as kept (S13 answer 2); the reply names the months used, as every statistic's
   does. If the statistic fails on every month too, that second failure is the answer.
2. A period the message itself states is never widened (S13.3's own case apart).
3. C65's check is made on the request as it is run: once with the kept period, and again
   with every month before anything is computed.

Tests: a count of one year, then a trend with no period: answered over every month, the
reply names the months, no "(I kept ...)" line for the period, the next follow-up does not
keep the year from the widened statistic's turn; the same with each kind that can fail
TOO_LITTLE on one year (trend, trend_compare, shares, before_after with its date inside the
year); a trend whose message states the one year: TOO_LITTLE as today; a statistic that is
long enough on the kept period: run on the kept period as today; a selection too small on
every month too: the second failure's sentence; a rate is as today; after an answered
under-18 count of one year, a trend of ages 10 to 16 with the kept year: refused by C65's
check (NOT_ALLOWED), nothing computed.

**C65 point 8, answer to S3-R31-A's question (18 Nov 14:20 EST).** A distribution refused on its own ends
with the NOT_ALLOWED row as built ("I don't count a single year of age under 18; I can count
ranges of two years or more."). The sentence is true but reads oddly for a range such as 10
to 16, where the single year is the chart's last bar. Words of its own are left for a later
contract; the tests stay.

## C68. A breakdown lists only the groups its filters keep (D-085; planning chat on Opus 5.5, 18 Nov 17:09 EST)

Why: Nino in Slack, 18 Nov about 16:55 EST, after the 16:40 deploy. "How many arrests were there in
2024, by district?", then "Can you provide the earlier information without districts 7-8?": the model
counted districts 1 to 6 by district, rightly, but the reply listed "district 8: 0" and said "district 8
the fewest (0)"; "i said no district 8", "again, why is district 8 there?" and "i asked to exclude
district 8" got the same table three more times. C6 lists every group of a breakdown "including those
that will hold 0", also those the request's own filter leaves out. The model sees the reply only after
it is sent, so it could not change the table. County and SYNTHETIC mode alike.

1. In `counting.tally`, the groups of each breakdown are those of `counting.group_labels` that a
   filter of the request on the same field keeps (`counting.kept_labels`): a category or a weekday,
   the labels in its "in"; a flag, its one value; the hour, the hours of its range; the age band,
   the source's bands that meet the age filter's range. With no filter on the field, every group, as
   C6 has it (a district with no records in the period is still listed with 0).
2. Everything that reads the groups follows: the reply's lines, "the most" and "the fewest", the chart,
   details, the TOO_FINE test (which counts only groups that hold records, so it does not change).
3. When only one group is left and it is not hidden, the groups phrase is `by <dimension>, all of
   them were in <label>` ("by age band, all of them were in ages 10 to 17"), not "every group had
   the same count".
4. Nothing else changes. C21's and C65's check already read only the kept values
   (`counting.age_figures`), so the under-18 rule is not changed by this.

Tests (not written: D-085 took this change live without a tests session; for the next builder): the
thread above; a filter of one label, of several, of a weekday set, an hour range that crosses midnight,
a flag, an age range with a breakdown by age band (under 18 by age band: one band, no five empty ones);
no filter: every group with zeros as today; two breakdowns, one filtered.

## C69. After `reset`, Jeffrey still follows the thread (D-086; planning chat on Opus 5.5, 18 Nov 18:16 EST)

Why: Nino in Slack, 18 Nov 18:06 EST: after `reset`, two replies without a mention got no answer (the
deploy log shows no event after the reset). A13 step 1 answers a thread reply without a mention only
when the thread has turns, and `reset` deletes them.
1. In county mode, a thread whose `reset` kept stripped records (C65 point 4: the thread had counts or
   statistics) is followed as before: `slack_app._kind_of` also reads `thread_key + memory.GIVEN`.
2. A thread that is reset with no count or statistic in it, and every SYNTHETIC-mode thread, is not
   followed after `reset`, as today: a mention starts it again.
Tests (not written, D-086; for the next builder): reset after a count, then a reply without a mention:
answered, with an empty thread block; reset with no count: not followed; SYNTHETIC mode: as today.

## C70. A new question starts fresh; a recount replaces the first answer (D-087; planning chat on Opus 5.5, 18 Nov 18:53 EST)

Why: Nino in Slack, 18 Nov 18:00 to 18:07 EST. After questions about people under 18, "how old are
the people arrested in 2025?" kept "under 18" (C9), and the model, reading `read_as`, asked again with
the age filter cleared: the reply held both results and two charts. "Over the past five years, are
arrests going up or down?" did the same with "without district 8".
1. **A new question starts fresh.** In a request's filters, `{"field": "all", "clear": true}` keeps no
   filter from the pending question or the last answer (C9's "else the last answer's" is skipped for
   every field). `config/agent_prompt_s3_talk.md`, rule 11, after `"Everyone", "overall" or "all
   districts" removes that filter: send it with "clear": true.`, gains:
   ` A message that asks a new question of its own, and does not change just one thing in your last answer, starts fresh: add {"field": "all", "clear": true} to its filters, so that nothing is kept from earlier.`
   The other county prompt is not changed.
2. **A recount without kept filters replaces the first.** When a count, an analysis or a rate of a
   turn asks again what an earlier result of the same turn asked (the same kind, source, period and
   breakdown; for a statistic the same kind and options), with only filters missing that the earlier
   one had kept from the thread, the new result takes the earlier one's place and id: the reply,
   the chart, the memory record and `details` hold the new one only, and the dropped filters are no
   longer named in "(I kept ... from earlier.)". Not when a share or a comparison of the turn reads
   the earlier one. The under-18 check is made before, as for every count, and the replaced result
   was never shown.
Tests (not written, D-087; for the next builder): point 1: a kept age, then a request with "all": no
filter kept, no "(I kept" line; a follow-up without it keeps as today; the sentence in place; the
prompt hash tests take it out (`s3support.without_c70`). Point 2: a kept filter, then the same count
without it in one turn: one result, one table, no "(I kept" for it; with a share of the first:
both kept; a different period or breakdown: both kept.
