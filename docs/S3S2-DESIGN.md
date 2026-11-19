# Stage 3, Part S2: rates per resident (contract)

Written by the planning chat on 2026-11-12. The approved statistics plan
(`docs/PLAN-S3-STATS.md`, D-040) lists "arrests per 10,000 residents, by group" with Census
population. This file says exactly what that means. Its four definitions were decided by
Nino the same evening (D-055, D-056, D-057). It ADDS to Part S (`docs/S3S-DESIGN.md`):
where this file is silent, Part S and Part A stand. Nothing is built yet.

## R0. What a rate here is, and is not

`<records> per 10,000 residents` = the records counted in a calendar year, divided by the
Census estimate of how many residents of that kind lived in the county that year, times
10,000. It is NOT the share of residents who were arrested: one person can be arrested
several times, and people arrested in the county do not all live in it. Every answer with
a rate carries that sentence, written by Python.

## R1. Where the population comes from

The Census Bureau's American Community Survey, one-year estimates, Montgomery County,
Maryland, for each year from 2021 to the newest year published. Nino fetched fifteen tables
with his own key on 2026-11-12 (three tables for each of 2021 to 2025). The agent keeps its
own dated copies, as it does for county sources, and names the table and year in `details`.

- Sex by age: table B01001.
- Hispanic or Latino origin by race: table B03002. **Not fetched yet** (see R3).
- Fetched but not used for rates: B02001 (race alone) and B03003 (Hispanic origin alone).

Every figure in those tables is an estimate from a survey and has a margin of error. The
range of a rate takes it into account (R5).

## R2. Which sources and years

Only a source whose file says `"rates": true`. To start with: Police Arrests only. Whole
calendar years only, each one a full year in the copy and a year the Census has published.
A rate for 2026 is refused until the 2026 estimates exist (late 2027). County-wide only:
police districts are not Census areas, so a rate by district is refused, with that reason.

## R3. The groups (DECIDE 1: **approved by Nino, D-055, 2026-11-12 23:32 EST**)

What the real data shows (the chat's own count of its copy of 12 November 2026, year 2025):
of the arrest records with race White, 6 in 10 are also recorded as Hispanic. In the
Census, people say their own race, and many Hispanic residents do not choose "White" (they
choose "some other race" or more than one). So dividing "White" arrest records by the
Census's "White" residents would divide a large group of records by a much smaller group
of people, and the rate for White would come out far too high. A rate by plain race would
be wrong, not just rough.

PROPOSED: for race and ethnicity there is ONE breakdown, `race_ethnicity`, with groups
that mean the same thing on both sides:

| Group | Arrest records | Census B03002 |
| --- | --- | --- |
| Hispanic (any race) | ethnicity Hispanic | Hispanic or Latino |
| Black, not Hispanic | race Black or African American, ethnicity not Hispanic | Not Hispanic: Black alone |
| White, not Hispanic | race White, ethnicity not Hispanic | Not Hispanic: White alone |
| Asian, not Hispanic | race Asian, ethnicity not Hispanic | Not Hispanic: Asian alone |

Every other record (race unknown, and the two groups with fewer than 10 records a year) is
left out and counted in the used line. A rate by `race` alone or by `ethnicity` alone is
refused, with one sentence saying why and offering `race_ethnicity`. This needs one more
Census table (B03002), five small files: the program fetches them itself with the key
Nino has saved (a `fetch-census` command, and the refresh of Part D), so he downloads
nothing by hand.

Still true after this, and said in a fixed line: the police record what an officer writes
down; the Census records what people say about themselves. The two do not match person
for person.

## R4. The other breakdowns (DECIDE 2: **the age bands approved by Nino, D-056**)

- `gender`: female and male, against B01001's two totals.
- `age_band`: 10 to 17, 18 to 24, 25 to 34, 35 to 44, 45 to 54, 55 to 64, 65 and over,
  against B01001's age groups added up for both sexes. No band below 18 is narrower than
  eight years (Part A's rule for under 18 stands). Records with no usable age are left out.
- none: all records over all residents.
- Two breakdowns at once (for example gender within age band) are refused in this round.

## R5. The numbers and their margins (DECIDE 3: **decided by Nino, D-057: "exactly how the census states it"**)

The uncertainty of a rate is stated the way the Census Bureau states its own: an estimate
and a margin of error at the 90 percent level, worked out with the Bureau's own published
formulas and nothing else. The count of records is taken as exact. (This replaces the
chat's first proposal of 95% ranges that also allowed for chance in the count.)

- The residents figure is shown as the Census gives it: the estimate and its margin of
  error. Where the Census publishes no margin for a figure (a total it fixes to its own
  population estimates), the answer says so and gives none.
- A group that adds up several Census lines (an age band over both sexes): the estimates
  are added, and the margin of error of the sum is the square root of the sum of the
  squared margins (the Bureau's formula for a sum).
- The rate per 10,000, one decimal, with its margin: `rate x (margin of residents /
  residents)`, which is the Bureau's formula for a ratio when the top number is exact.
- Several years together: records added up over residents added up, the margin by the
  formula for a sum.
- The **rate ratio** of each group against a reference group, two decimals: by default
  the group with the most residents; the question may name another. Its margin by the
  Bureau's formula for a ratio of two estimates. "Clear" means the ratio's 90 percent
  range (ratio minus and plus its margin) does not include 1.
- R computes all of it (the rule of S0). Python recomputes it in the tests.
- `TOO_LITTLE`: a group with under 100 records in the years asked for.
- A fixed sentence says what the margin is and is not: it comes from the Census's survey
  alone, at the Census's 90 percent level; it says nothing about chance in the number of
  arrests from year to year.

The Bureau's formulas, as published: margins of error are at the 90 percent level;
standard error = margin / 1.645; for a ratio A/B whose top is not part of its bottom,
SE(A/B) = (1/B) x sqrt(SE(A)^2 + (A/B)^2 x SE(B)^2). Sources (read 2026-11-12):
https://www.census.gov/content/dam/Census/library/publications/2018/acs/acs_general_handbook_2018_ch08.pdf
and
https://www2.census.gov/programs-surveys/acs/tech_docs/statistical_testing/2025_Instructions_for_Stat_Testing_ACS.pdf

## R6. What Python writes

- `{aN.rate}`: `there were about <r> <unit many> per 10,000 residents <what> in <years>
  (margin of error ±<m>)`.
- `{aN.ratio.<k>}`, clear: `the rate for <group> was about <x> times the rate for <reference>
  (margin of error ±<m>)`; not clear: `the rates for <group> and <reference> were not
  clearly different (ratio <x>, margin of error ±<m>)`.
- Fixed lines, in this order after the table: the sentence of R0; for `race_ethnicity` the
  officer-and-Census sentence of R3; the association line and the sensitive line as in Part
  S; then the source line, which now names two sources: the county's and the Census
  Bureau's, each with its copy's date.
- Chart: one dot per group with its range, the reference group marked.

## R7. Refused, with the reason (DECIDE 4: **approved by Nino, D-056: every refusal states its reason**)

A rate by district or any other place; by a field that has no Census counterpart; for a
source that is not marked for rates; for a year the Census has not published; for part of
a year; for a filter the Census cannot match (for example "arrests near a school per
resident"). Each gets one fixed sentence that says no AND why, for example: `I can't give a
rate by police district, because the Census does not count residents by district. I can
give the count by district, or a rate for the whole county.`

## R8. Settings, files, commands

- `analyze` gains the kind `rate`, with `options`: `"by"`: one of `race_ethnicity`,
  `gender`, `age_band`, or left out; `"reference"`: a group label, optional. The period
  must be whole calendar years. Results, slots, the two-call limit and the errors are Part
  S's; `BAD_OPTIONS` covers every refusal of R7 and each carries its fixed sentence.
- `config/census.json` (the planning chat writes it): the survey (ACS one-year), the place
  (state 24, county 031), the two tables, and for every group the Census variables that
  are added up, each with words its official label must contain (for example `Male` and
  `10 to 14 years`).
- `python -m moco_agent fetch-census`: for each year from 2021 on that the Census has
  published, fetch the two tables and the Census's own list of variable labels, with
  `CENSUS_API_KEY` (never printed, logged or saved). A year's copy is kept only if every
  variable's label holds the words `config/census.json` expects; otherwise that year is
  refused, with the variable named, and the last good copy stays. Copies live under
  `<state dir>/census/<year>/`, dated and fingerprinted like county copies. Part D's
  refresh runs this too, once a day at most.
- With no Census copy for a year asked for: the rate is refused with one sentence saying
  the Census figures for that year are not there yet.
- R script `analysis_r/rate.R`; the script in `details` (S7) downloads both the county
  data and the Census tables from their public addresses. The Census address in it holds
  no key: the reader is told in one comment line to add their own.

## R9. What the tests must show

With made-up Census tables in the Census's own shape (a fake service; no real figure, no
key) and Part S's fixture source marked for rates:

- every group of R3 and R4: which records count, which Census variables are added up, and
  the residents figure with its margin by the formula for a sum;
- the rate and its margin, the ratio and its margin, each against the tests' own
  arithmetic written out from R5's formulas, to the decimals shown; several years
  together; a figure the Census publishes with no margin;
- every phrase of R6 exactly, clear and not clear; the fixed lines and their order; the
  source line naming both sources; the floor (a group under 10 records is never shown,
  and `TOO_LITTLE` under 100);
- every refusal of R7, each with its reason in the sentence; `race` alone and `ethnicity`
  alone refused with the offer of `race_ethnicity`;
- `fetch-census`: the request it makes; a label that does not match refuses the year and
  keeps the last good copy; a failed or error answer; the key is in no file, log line,
  printed line, saved record or script;
- no rate, margin, residents figure or count in any tool answer, log line or stored turn;
- the chart exists, has the stated size and is not blank;
- with no `rate` call, nothing a user or a test can see changes.

## What Nino decided

1. The `race_ethnicity` groups of R3; plain `race` and plain `ethnicity` rates are refused
   (D-055).
2. The age bands of R4 (D-056).
3. The margins of R5: "exactly how the census states it" (D-057).
4. The refusals of R7, each stating its reason (D-056).

## R10. Exact words and open points settled (2026-11-13, after the tests and their check)

The tests session asked nine things (`briefs/QUESTIONS.md`, Brief S3S2-A) and the automatic
check failed the tests in four places because the contract gave no words to hold a build
to (`kit-log/raw/S3S2-A-autocheck.txt`). This section gives them. Where it and R0 to R9
differ, this section wins. Nothing here changes a definition Nino decided (D-055, D-056,
D-057): it is wording, layout and what is shown.

**1. Groups, their words, their order.** In the table, in the `reference` option and in
the line of what is not shown, a group is written by its label; in a phrase by its
"residents" form:

| Breakdown | Label (table order) | In the rate phrase, after `per 10,000` | In a ratio phrase |
| --- | --- | --- | --- |
| `race_ethnicity` | `Hispanic (any race)`; `Black, not Hispanic`; `White, not Hispanic`; `Asian, not Hispanic` | `residents counted as <label>` | `<label>` |
| `gender` | `female`; `male` | `<label> residents` | `<label> residents` |
| `age_band` | `aged 10 to 17`; `aged 18 to 24`; `aged 25 to 34`; `aged 35 to 44`; `aged 45 to 54`; `aged 55 to 64`; `aged 65 and over` | `residents <label>` | `residents <label>` |
| none | (one line, `All residents`) | `residents` | (no ratio) |

`<years>` is `2025` for one year, `2024 and 2025` for two, `2021 to 2025` for more (the
years of a rate are always one unbroken run of whole years).

**2. Slots and line 1.** With no breakdown the one slot is `{aN.rate}`. With a breakdown:
`{aN.rate.<k>}` for each group SHOWN, k counting the shown groups in table order from 1,
and `{aN.ratio.<k>}` for each shown group other than the reference, with that group's k.
R1's limits do not change: the model's own text may use four sentences and chooses which
slots to put in them; the table carries every group. The fixed rendering writes every rate
phrase, then every ratio phrase, each as its own sentence.

- `{aN.rate...}`: `there were about <r> <unit many> per 10,000 <residents form> in <years>
  (margin of error ±<m>)`. Where the Census gives the residents figure no margin (the
  county total), the bracket is `(the Census gives no margin of error for this figure)`.
- `{aN.ratio.<k>}`: as R6 writes it, with the ratio forms of the table above.
- The reference is the shown group with the most residents over the years asked, unless
  `reference` names another shown group by its label (capitals do not count).

**3. The table.** One line per shown group, in table order: `<label>: <n> records,
<residents> residents (margin of error ±<m>), <r> per 10,000`. With no breakdown: `All
residents: <n> records, <residents> residents (the Census gives no margin of error for
this figure), <r> per 10,000`. For several years the records and the residents are each
added up over the years, and the margin is the sum formula's. Residents and their margins
are whole numbers with thousands commas.

**4. Too few records, and the floor.** A group with fewer than 100 records in the years
asked is NOT SHOWN: it has no phrase, no slot, no table line, no dot on the chart and no
line in `details`, and neither its count, its residents figure nor its rate is written
anywhere (a rate and a residents figure together would give a hidden count back). It is
named in one line straight after the table: `Not shown, with fewer than 100 records:
<labels joined by "; ">.` Its records are part of the used line: `; <k> not included: in a
group with fewer than 100 records`, where `<k>` follows the floor like every count (`fewer
than 10`). If no group has 100 records (or, with no breakdown, the selection has fewer
than 100) the rate is refused with the code `TOO_LITTLE` and the line `There is too little
data for a rate: it needs at least 100 records in a group, and none here has that many.`
With one group shown there is no ratio.

**5. The lines after the table, in this order.** The not-shown line (if any). The used
line, Part S's form: `(<n> records over <m> months` then one `; <k> not included: <reason>`
part per reason `.)`, where `<n>` counts the records of the shown groups, `<m>` is twelve
for each year, and the reasons are, in this order: for `race_ethnicity` `no race and
ethnicity that the Census counts`; for `gender` `no gender recorded`; for `age_band` `no
usable age`; then `in a group with fewer than 100 records`. Then:

- R0's sentence: `This is not the share of residents who were arrested: one person can be
  arrested several times, and people arrested in the county do not all live in it.`
- R5's sentence, only when a margin of error is shown somewhere in the reply: `The margin
  of error comes from the Census's survey alone, at the Census's 90 percent level; it says
  nothing about chance in the number of arrests from year to year.`
- for `race_ethnicity`, R3's sentence: `The police record what an officer writes down; the
  Census records what people say about themselves. The two do not match person for
  person.`
- the association line of Part S exactly as it is with no sensitive field: `These are
  patterns in recorded <unit many>: what goes with what, not what causes what.` A rate
  answer never carries S11 2f's line or C10's sensitive line: both say "not rates".
- the source line. First answer: `Source: <title> (county open data), copy of <date>;
  Census Bureau, American Community Survey one-year estimates, copy of <date>. A count is
  of <unit many>, not people. Want the details and the R script?` Later answers: `(<title>,
  county open data, copy of <date>; Census Bureau, American Community Survey one-year
  estimates, copy of <date>.)` The Census date is the day its newest copy among the years
  asked was fetched.

**6. `details`.** Names the Census table (`B03002` for `race_ethnicity`, `B01001`
otherwise) and, for each year asked and each shown group, that year's residents figure
with its margin as the Census gives it; the county's notices word for word; the model
sentence; the script. Nothing of a group that is not shown but its label.

**7. The refusals, word for word.** Each is the error `BAD_OPTIONS` (but for
`TOO_LITTLE`, point 4), carries its sentence to the model and ends the turn with it; R is
not started. `<dimension>` is the field's word in the source file.

| When | The sentence |
| --- | --- |
| `by` is the district field | `I can't give a rate by police district, because the Census does not count residents by district. I can give the count by district, or a rate for the whole county.` |
| a filter on the district field | `I can't give a rate inside one police district, because the Census does not count residents by district. I can give the count for that district, or a rate for the whole county.` |
| `by` is `race` | `I can't give a rate by race alone, because many Hispanic residents do not choose a race such as White in the Census while the police record one for them, so the two counts would not be of the same people. I can give a rate by race and ethnicity together.` |
| `by` is `ethnicity` | `I can't give a rate by ethnicity alone, because the groups have to mean the same in the police records and in the Census, and this agent matches them by race and ethnicity together. I can give a rate by race and ethnicity together; its first group is Hispanic (any race).` |
| `by` is any other field of the source | `I can't give a rate by <dimension>, because the Census does not count residents by <dimension>. I can give the count by <dimension>, or a rate by gender, by age band, or by race and ethnicity.` |
| `by` is a list, or `by` is given together with any filter on gender, age, race or ethnicity | `I can't give a rate broken down two ways at once: this version matches the Census one breakdown at a time. Ask for one of: by gender, by age band, or by race and ethnicity.` |
| any other filter (not the district) | `I can't give a rate for a filtered selection (<the filters as C6 writes them>), because the Census has no count of residents to match it. I can give the count, or a rate for all <unit many> by gender, by age band, or by race and ethnicity.` |
| the source's file does not say `"rates": true` | `I can't give a rate for <source title>, because no count of residents has been matched to that source. I can give counts from it.` |
| the period is not whole calendar years | `I can't give a rate for part of a year, because the Census counts residents for whole calendar years only. Ask for one or more whole years.` |
| a year asked has no Census copy (not published yet, or not fetched) | `I can't give a rate for <the years without a copy, written as <years> is>, because I have no Census figures for <that year or those years> yet. The Census publishes a year's estimates late in the following year.` (`that year` for one, `those years` for more.) |
| `reference` is not the label of a shown group | `I can't compare with "<the reference as given>", because it is not one of the groups shown for that breakdown: <labels of the shown groups joined by "; ">.` |

When several apply, the first in this order decides: source not marked; part of a year; a
year with no Census copy; `by` district; a filter on the district; `by` race; `by`
ethnicity; `by` another field; two breakdowns; another filter; then (after counting) too
few records; the reference.

**8. `config/census.json`.** The tests session's note is right: the words expected in the
label of `Hispanic (any race)` were `Hispanic or Latino`, which every "Not Hispanic or
Latino" label also holds. They are now `Total:!!Hispanic or Latino`, as the Census writes
that line (`Estimate!!Total:!!Hispanic or Latino:`, read from the Census's own variable
list for 2023 on 2026-11-13: https://api.census.gov/data/2023/acs/acs1/variables/B03002_012E.json).

**9. What the tests must show beyond R9.** Every sentence of point 7 word for word, and
the order of point 7 for two pairs that both apply; the phrases, table lines and lines of
points 2 to 5 exactly, for each breakdown; a group under 100 records, and one under 10:
named only in the not-shown line, its count, residents figure and rate in no line of the
reply and nowhere in `details`, its records in the used line by the floor; `TOO_LITTLE`
with its line; the no-margin bracket and no R5 sentence for the county total; the plain
association line and neither "not rates" line on a `gender` and a `race_ethnicity` answer;
in the log, no rate at any precision, no margin and no residents figure written as a whole
number or with decimals; that `fetch-census` made copies before "nothing changes without
a rate call" is compared; the made-up key nowhere under the test's home folder either.

## R11. The second tests session's six questions, answered (2026-11-13, planning chat)

`briefs/QUESTIONS.md`, Brief S3S2-A2. Where this section and R10 differ, this section wins.

1. **A not-shown group's records in the used line.** Allowed, as the tests read it: the used
   line's `<k>` is written, by the floor like every count (`fewer than 10`). A group of 10 to
   99 records is not a secret (the floor is 10); it is not shown because a rate from it
   would be too unsteady. The count appears nowhere else.
2. **The label check of point 8.** Stays as it is. The codes in `config/census.json` were
   checked by hand against the Census's live labels on 13 November; a wrong code is a
   change to that file, which only the planning chat makes. Accepted as a known limit.
3. **A `reference` written as the config's group name** (`25 to 34`, `all residents`): refused
   with point 7's unknown-reference sentence. Only R10 point 1's labels are names a person
   uses. No test is required for it.
4. **A whole year the copy covers only in part** (2026 on a copy that ends in October):
   point 7's "part of a year" sentence, because point 7's order puts it first. A test may
   go on accepting either.
5. **A margin that rounds to nothing.** A rate's margin that is under 0.05 is written
   `under ±0.1`; a ratio's margin under 0.005 is written `under ±0.01`. So the bracket reads
   `(margin of error under ±0.1)`. Every other margin as R10 writes it. The tests were
   corrected to this by the planning chat (`s2support.margin_words` and one literal in
   `test_s2_phrases_lines.py`); record: `kit-log/raw/S3S2-chat-test-fix.txt`. The real
   data needs this: for gender over 2021 to 2025 the rate margins and the ratio margin
   round to nothing (`kit-log/raw/S3S2-chat-reference.txt`).
6. **The smaller readings** (a table line starts with the label as written; the Census
   copy's date in the county's form; C6's `<what>`; `details` figures with or without
   commas; TOO_LITTLE ends the turn as Part S's does; replies compared line by line; slots
   as a set; R1 with five slot sentences refused): all stand as the tests took them.

## R12. After the build: the build session's three questions (2026-11-13 22:38 EST, planning chat)

The build (a2511ea) passes every test; the planning chat ran them again in its own workspace
(tests/s3s2, tests/s3, tests/t 1,434 passed; tests/p1, tests/d and the top level 1,527 passed,
2 failed that cannot fail as root) and found its real 2025 figures equal, to the last digit
shown, to `kit-log/raw/S3S2-chat-reference.txt` (all residents; by gender; all seven age bands
with their margins and ratios).

1. YES, and more. Both county prompts' rule 10 drops "rates per resident" from
   UNSUPPORTED_METRIC: it reads `UNSUPPORTED_METRIC: convictions, prosecution, sentencing,
   forecasts or causes.` C5's fixed row for `UNSUPPORTED_METRIC` drops "rates" for the same
   reason: `I can't answer that one: I only count records, so I have nothing on convictions,
   sentencing, jail or causes.` (then the rest of the row as today). Nothing else changes.
   Built by the planning chat after a tests session pins both (one literal in
   `tests/s3/test_s3_round5b.py` holds the old row and is changed by that session).
2. Kept as built: a rate with no period is asked for its period, as a count is.
3. DECIDED (D-063, Nino, 23:56 EST: "A"): kept as built. (It is how a figure's uncertainty is read:) the Census gives no margin for
   the county's Hispanic (any race) total (`-555555555`, a figure it fixes to its population
   estimates). The build reads that as no survey uncertainty (a standard error of 0), so a
   ratio with Hispanic on one side takes its margin from the other side alone. The planning
   chat recommends keeping it: it is the Census's meaning of that code. The other reading:
   such a ratio carries no margin and no "clear" wording.

## R13. A rate question that names no breakdown (2026-11-14 10:58 EST, planning chat)

Found by live round 7 (`kit-log/raw/S3-county-check-live-2026-11-13.txt`, LIVE ROUND 7
(RATES)), the first live round with the Census key on build-test. A DEFECT IN THE PROMPT:
"How many arrests per 10,000 residents were there in 2025?" names no breakdown, yet in all
three runs the model sent `{"by": "race_ethnicity"}`. The rates block lists the race and
ethnicity option first and "no options for all records" last. A plain rate question answered
with a breakdown by race and ethnicity nobody asked for must not happen. A second, smaller
finding: in 11 of 12 rate runs the reply fell to the fixed text because the model wrote its
own lead-in with "per 10,000 residents in 2025" (NUMBER); the figures were right, the wording
was not his.

The fix is in the prompt only. The program gains no word list (Nino asked on 14 Nov whether
the program reacts to fixed words; this round adds none).

1. In both county prompts (`config/agent_prompt_s3.md`, `config/agent_prompt_s3_talk.md`),
   three changes to the rate block, word for word, and nothing else in either file:

   (a) the options line becomes:

   `- options: leave options out when the message names no breakdown: that is the rate for all residents. Send "by" only for a breakdown the message itself names: {"by": "race_ethnicity"} when it names race or ethnicity, {"by": "gender"} when it names gender, men or women, {"by": "age_band"} when it names ages or age groups. Put a district or any other narrowing in filters as for count, and "by district" as {"by": "district"}: the program refuses what the Census cannot match and says why. Add "reference": "<the group's label>" only when the message names the group to compare with.`

   (b) the slots line gains one sentence at its end, so it reads:

   `- The slots: with no breakdown {a1.rate}; with one, {a1.rate.1}, {a1.rate.2} and so on, one per group shown, and {a1.ratio.2} and so on, each comparing that group with the reference group. Use only the slots the tool answer lists, each in its own sentence, at most four. Each slot already says "per 10,000 residents" and the year: write no number, unit or year of your own, not even in a lead-in.`

   (c) the two example lines become:

   `A finding with a rate might read: I found that {a1.rate}.`
   `A finding with rates by group might read: I found that {a1.rate.1}. {a1.rate.2}. {a1.ratio.2}.`

2. R12 (d)'s test, which holds today's block, is changed by the tests session to the new
   block. Nothing in `src/` changes. The fixed text still shows every group when the model's
   reply cannot be used (a breakdown by age band has seven), as today.

3. Measured, not tested: the live round after the build repeats R01 to R04 three times. R01
   must call the rate with no options in at least 2 of 3 runs.

## R14. R13's slots line corrected (14 Nov, after CHAT-BUILDS-check-3)

The check found (RECORD ERROR 1) that R13 1(b)'s new sentence says "Each slot already says 'per
10,000 residents' and the year", which the ratio slots do not, and (NOTE) that "at most four" is
stricter than C38 now allows. In both county prompts the slots line becomes, word for word:

`- The slots: with no breakdown {a1.rate}; with one, {a1.rate.1}, {a1.rate.2} and so on, one per group shown, and {a1.ratio.2} and so on, each comparing that group with the reference group. Use only the slots the tool answer lists, each in its own sentence. The rate slots already say "per 10,000 residents" and the year: write no number, unit or year of your own, not even in a lead-in.`

Nothing else in the rate block changes. Tests: R13's tests of the slots line and of the whole
block change to this line; (e) still holds the rest of each prompt unchanged.
