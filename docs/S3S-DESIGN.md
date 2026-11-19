# Stage 3, Part S: statistics, charts and R (the contract)

Written by the planning chat on 2026-11-12. Plan: `docs/PLAN-S3-STATS.md` (approved, D-040).
It ADDS to Part A (`docs/S3A-DESIGN.md`) and applies in county mode only. Where this file
is silent, Part A and the agent loop stand. Rates per resident (Census) are not in this
file; they follow as Part S2 once this part is checked.

## S0. What must not break (adds to C1)

- Every estimate a person sees was computed by R from a saved copy, placed by Python inside
  a whole phrase Python wrote, and can be recomputed by anyone from the script in `details`.
- The model chooses an analysis from a fixed menu and fills in options. It never writes R,
  never sees an estimate, and never types one.
- No answer says or implies cause. The fixed association line is on every statistical
  answer.
- An analysis with too little data is refused, with the reason, instead of being run.
- Nothing below the floor is shown, in a table or on a chart.

## S1. The `analyze` tool

    analyze(kind, source, period, filters, options)

`source`, `period` and `filters` are exactly Part A's (C5), checked the same way, with the
same errors and the same filling from memory (C9). `kind` and its `options`:

| `kind` | `options` | Model |
| --- | --- | --- |
| `trend` | none | T |
| `trend_compare` | `"versus": [filters]`: a second filter list; the two must differ in exactly one field | T with a group |
| `before_after` | `"date": "YYYY-MM-01"` | T with a step |
| `yes_no` | `"outcome": {a flag field, or a category field with one label, or "under_18", "weekend", "night"}`, `"factors": [1 to 6 of the same kinds]`, `"controls": [0 to 3 of: category fields, "year"]` | L |
| `shares` | `"part": [filters]`: one or more filters added to the spec | S |
| `timing` | none | counts only |
| `distribution` | `"by": a category or flag field`, optional | age summary |

At most two `analyze` calls in a turn. A good call makes a result `aN`; Python answers the
model with no value: `{"result_id": "a1", "read_as": "<what was analysed, in words>",
"slots": [...]}`.

New tool errors:

| Error | When |
| --- | --- |
| `BAD_OPTIONS` | options missing, unknown, or not allowed for the kind or the source |
| `TOO_LITTLE` | T: fewer than 24 full months, or under 100 records in all. L: fewer than 100 yes cases or 100 no cases, or fewer than 10 of the rarer outcome per estimated coefficient. S: a year with under 100 records in the base. `distribution`: a group under 30 usable ages. The error says which |
| `TOO_FINE` | a chart or table of the result would have more than half its points hidden |
| `ENGINE_MISSING` | `Rscript` or a needed R package is not there |
| `ENGINE_FAILED` | R ended with an error, ran over 60 seconds, did not converge, or gave an answer that is not in S3's shape |

`ENGINE_MISSING` and `ENGINE_FAILED` end the turn with a fixed line and are logged with
the R message (never shown to the user, never given to the model).

## S2. The window, and what R is given

- Count models use **full months only**, from the later of the source's `coverage_start`
  and the period's start, to the last full month in the copy **minus
  `drop_newest_months`** (a setting in `config/analysis.json`, 1 to start with: the newest
  months may still be filling in at the county; not yet measured). The answer's period
  phrase names the months actually used.
- Python filters the copy by the spec, then writes a job folder with `job.json` (kind,
  options, labels, the window) and the input table: for T and S a table of counts by
  month (and group), for L one line per record holding only 0/1 and category columns for
  the outcome, factors and controls (no id, no time, nothing else), for `timing` a
  weekday-by-hour table, for `distribution` ages with the group column.
- Python starts `Rscript analysis_r/<kind>.R <job folder>` as a process with a list of
  arguments (no shell), 60 seconds at most. R writes `result.json` and `chart.png` into
  the job folder. R never contacts the network and reads nothing but the job folder.
- The job folder is kept with the saved record (not in git, never sent anywhere).

## S3. The models, fixed

**T, trend.** Negative binomial regression of the monthly count, log link, exposure the
number of days in the month, on time in years and month of year (11 indicators):
`MASS::glm.nb(n ~ t + factor(month) + offset(log(days)))`. If it does not converge or the
spread estimate is not above zero: Poisson with the same terms and robust standard errors
(`sandwich::vcovHC(type = "HC1")`), and the result says which was used. `trend_compare`
adds a group indicator and its product with time; `before_after` adds an indicator for
months from the date on and time since the date (0 before it); the date must leave at
least 12 full months on each side.

**L, yes or no.** Logistic regression of the outcome on the factors and controls:
`glm(family = binomial)`. Category factors are indicator-coded against the most common
label.

**S, shares.** The share of the base that matches `part`, per calendar year in the window,
with a Wilson 95% range; and a logistic regression of "matches part" on year as a number.

**Intervals** are 95% Wald intervals on the model's own scale (estimate plus or minus
1.959964 standard errors), turned into percentages or odds ratios at the ends. "Clear"
means the interval does not include no change (0% for T, an odds ratio of 1 for L and S).

**Fit note (T).** R also returns the total of the last six months used, divided by what
the model expected for them. Outside 0.90 to 1.10 the answer carries the fit line (S5).

`result.json` holds, for every estimate: its name, the estimate, both ends of the
interval, the p-value, and for the whole result: the model used, the months or records
used, what was left out, and the fit ratio.

## S4. The phrases Python writes

Percentages have one decimal, odds ratios two, with the sign written out (`-3.2%`).
`<what>` and labels are Part A's phrases (C6). Months are written `January 2021`.

- `{aN.trend}`, clear: `<unit many> <what> <rose|fell> by about <p>% a year from <first
  month> to <last month> (95% range <lo>% to <hi>%)`. Not clear: `<unit many> <what> showed
  no clear change from <first month> to <last month> (about <p>% a year, 95% range <lo>% to
  <hi>%)`.
- `{aN.difference}` (`trend_compare`), clear: `the yearly change <b label> was about <p>
  points <higher|lower> than <a label> (95% range <lo> to <hi>)`. Not clear: `there was no
  clear difference in yearly change between <a label> and <b label> (about <p> points, 95%
  range <lo> to <hi>)`. Each group's own trend is in the table.
- `{aN.step}` (`before_after`): `from <date month> on, the monthly level was about <p>%
  <higher|lower> than the earlier trend pointed to (95% range <lo>% to <hi>%)`, or `there
  was no clear step in <date month> (about <p>%, 95% range <lo>% to <hi>%)`. `{aN.bend}`:
  `the yearly change after <date month> was about <p> points <higher|lower> than before
  (95% range <lo> to <hi>)`, or the no-clear form.
- `{aN.odds.<k>}` (`yes_no`, one per factor label, numbered in table order), clear:
  `<factor label> went with <higher|lower> odds of <outcome label> (odds ratio <or>, 95%
  range <lo> to <hi>)`. Not clear: `<factor label> showed no clear link with <outcome
  label> (odds ratio <or>, 95% range <lo> to <hi>)`. `{aN.held}`: `holding <controls>
  fixed`, or `with nothing else held fixed`.
- `{aN.share}` (`shares`): `the share <part> went from <p1>% in <first year> to <p2>% in
  <last year>`; `{aN.sharetrend}`: `a clear <rise|fall> over the years` or `no clear change
  over the years`.
- `{aN.timing}`: `the busiest hour was <weekday> at <hour> (<n>) and the quietest <weekday>
  at <hour> (<n>)`.
- `{aN.ages}`: `the median age was <m> (the middle half were <q1> to <q3>)`; with `by`,
  one per group, each starting `for <label>, `.

R1's check applies to a statistical finding with these slots on offer. `{aN.held}` must
come in the same sentence as, or the sentence after, an odds slot of the same result.
The fixed rendering is each phrase as its own sentence, capitalised.

## S5. What Python adds to the reply, in this order

1. the table (as C10: at most 12 lines, else in `details`): for T the yearly totals and the
   estimate; for L one line per factor label with odds ratio and range; for S one line per
   year; for `distribution` one line per group;
2. the fit line, when S3 says: `The last six months were about <q>% <below|above> the
   trend line, so a straight line describes the recent period poorly.`;
3. for `before_after`: `Other things changed over the same months. This shows timing, not
   cause.`;
4. what was used and left out: `(<n> records over <m> months; <k> not included: <reason>.)`;
5. the association line, always: `These are patterns in recorded <unit many>: what goes
   with what, not what causes what.`;
6. the sensitive line (C10), when a sensitive field is a filter, factor, control or group;
7. the source line (C10), ending for a first answer `Want the details and the R script?`

The chart is attached to the same message.

## S6. Charts (ggplot2, drawn by R)

One chart per result, PNG, 1600 by 1000 pixels, one fixed theme in `analysis_r/theme.R`
(white background, grey grid on the value axis only, one blue for the data, grey for
context, no legend when there is one series).

| Kind | Chart |
| --- | --- |
| `trend`, `before_after` | monthly counts as a thin grey line; the fitted values as a blue line with the 95% band; for `before_after` a dashed line at the date |
| `trend_compare` | the two groups in two panels side by side, same value axis |
| `yes_no` | odds ratios as points with their ranges, log scale, a line at 1, factors in table order |
| `shares` | the yearly share as points with ranges, joined by a line |
| `timing` | weekday by hour as a heat map in one hue |
| `distribution` | histogram of ages in two-year steps; with `by`, one panel per group |

Every chart carries a title (`read_as`), a subtitle (the months used, the copy's date) and
a foot line (the source title and "recorded <unit many>, not people; patterns, not
causes"). **The floor on charts:** a monthly series with any month from 1 to 9 is drawn by
quarter; if a quarter is still hidden, `TOO_FINE`. A histogram bar or heat map cell from
1 to 9 is drawn as empty and the foot line says so.

## S7. `details` and the script anyone can run

`details` after a statistical answer shows the full table, the model in one plain
sentence, the months and records used and left out, the copy's date and fingerprint, the
county's notices, and **a script**: one R file that downloads the same public dataset from
the county's address, applies the same filters and window, fits the same model and prints
the same estimates. It holds no record of the data. It says at its top that the county
may have corrected records since the copy's date, so the last digit can differ. It is
attached to the message as a file.

The address appears exactly once in the script, on a line of its own:
`data_url <- "<the full address, with its query>"`. Everything else the script needs it
works out itself. (A reader with a saved file, or a test, can point that one line at a
local file.) The script uses only base R, `jsonlite` and, where the model needs it, `MASS`
and `sandwich`. It ends by printing one line per estimate in the form
`<name> <estimate> <low> <high>` with full precision, after the readable table.

## S8. Settings, files, commands

- `analysis_r/` at the top of the project: one script per kind, `theme.R`, `common.R`.
- `config/analysis.json`: `drop_newest_months`, the thresholds of S1, the fit band.
- `MOCO_RSCRIPT` (default `Rscript`). `python -m moco_agent check-engine` prints the R
  version and whether each package loads.
- `statsmodels` and `scipy` are test-only requirements (`requirements-dev.txt`); the
  running agent does not need them.

## S9. What the tests must show, and what they cannot

With Part A's fixtures, grown so that each analysis has enough data and one case each
that has too little, and with R really running (the Mac has R 4.6.2 with MASS, ggplot2,
jsonlite and sandwich):

- for every kind, R's estimates equal the tests' own recomputation in Python
  (statsmodels), written in the tests without importing the program: estimates within
  0.01 of a percentage point or 0.001 of an odds ratio; interval ends within 0.10 of a
  percentage point for T and 0.005 of an odds ratio for L and S (R and statsmodels differ
  by a few hundredths in the width of a negative binomial interval; measured 2026-11-11,
  `kit-log/raw/S3S-R-vs-Python-2026-11-11.txt`);
- every phrase of S4 exactly, in its clear and not-clear form, with both directions;
- every row of S1's error table; each threshold at its edge;
- the Poisson fallback when the negative binomial cannot be fitted;
- the fit line exactly when the ratio is outside the band;
- every fixed line of S5 exactly when it applies, in order;
- each chart file exists, has the stated size, and is not blank; the floor on charts;
- the script of S7 is produced, holds no data row, and (with a fake transport standing in
  for the county) prints the same estimates;
- no estimate, row or hidden figure in any tool answer, log line or stored turn;
- R is started without a shell and with a time limit; an R error never reaches the user;
- Part A's tests and the existing suite are untouched and pass.

Cannot show: that the real model picks the right analysis (the loop check in county mode);
that the estimates are right on the real data (the planning chat's reference answers,
outside the repo: 14 questions); that a chart reads well (Nino and the chat look at them);
that R behaves the same on the server (stage 4's first test).

## S10. Answers to the tests session's thirteen questions (added 2026-11-12, 22:10 EST)

The tests session (`briefs/QUESTIONS.md`, brief S3S-A) found thirteen places where this
file did not say enough. These are the answers; they are part of the contract. Where the
tests accept two readings at one place, build the reading given here. The numbers are the
questions' own.

1. **Signs.** After a direction word (`rose by about`, `fell by about`, `higher`, `lower`,
   `points higher`, `points lower`, `below`, `above`) the number is its size, with no sign:
   `fell by about 7.1% a year`. Everywhere else (the not-clear forms and every range) a
   value below zero is written with `-`, a value above zero with `+`, and zero as `0.0`:
   `(about +0.4% a year, 95% range -1.2% to +2.0%)`. Odds ratios never carry a sign.
2. **The three made-up factors.** `under_18`: a usable age below 18; records with no usable
   age are left out and counted in the used line. `weekend`: Saturday or Sunday. `night`:
   the hour is 22, 23 or 0 to 5 (10 p.m. to 5:59 a.m.). As a factor label they are written
   `being under 18`, `a weekend day` and `night hours (10 p.m. to 6 a.m.)`; as an outcome
   label `being under 18`, `falling on a weekend` and `falling at night (10 p.m. to
   6 a.m.)`. The night hours are the planning chat's choice and Nino is told of them.
3. **Per coefficient** does not count the intercept: every indicator column of a factor or
   a control counts as one.
4. **`year` as a control of L** is a category: indicators against the most common year.
   (In S the year is a number, as S3 says.)
5. **The used line.** `<reason>` is Part A's own wording for records left out (C10, C15),
   for example `no district recorded` or `no usable age`. Nothing left out:
   `(<n> records over <m> months.)`. Several reasons: one `; <k> not included: <reason>`
   part for each, in the order the fields appear in the source file. A `<k>` from 1 to 9 is
   written `fewer than 10`.
6. **The floor on charts.** S1's rule is the rule; the sentence in S6 "if a quarter is
   still hidden, `TOO_FINE`" is withdrawn. A monthly series with any month from 1 to 9 is
   drawn by quarter; a quarter from 1 to 9 is drawn as a gap and the foot line says so;
   `TOO_FINE` only when more than half of the quarters would be gaps. The same for the heat
   map and the histogram: more than half of the cells or bars that are not 0. One more
   case: `shares` with a year whose `part` count is from 1 to 9 is `TOO_FINE`, because the
   share would give the count away.
7. **`trend_compare`'s labels.** In the clear form `<a label>` and `<b label>` are the
   `<what>` fragments of the one filter that differs: `the yearly change in district 3 was
   about 2.1 points higher than in district 4`. In the not-clear form they are C6's compare
   labels: `between district 3 and district 4`.
8. **`distribution` with `by`:** one slot `{aN.ages}` that holds every group's phrase, in
   table order, joined by `; `.
9. **The tables.** `trend` and `before_after`: one line per calendar year of the window,
   `<year>: <n>`. `trend_compare`: one line per group, `<compare label>: about <p>% a year
   (95% range <lo>% to <hi>%)`. `yes_no`: `<factor label>: odds ratio <or> (95% range <lo>
   to <hi>)`. `shares`: `<year>: <p>% (95% range <lo>% to <hi>%)`. `distribution`:
   `<label>: median <m>, middle half <q1> to <q3>`. A count from 1 to 9 is written `fewer
   than 10`, as everywhere.
10. **Fixed lines.** `ENGINE_MISSING`: `I can't run statistics here right now: the
    statistics engine is not installed. Counts still work.` `ENGINE_FAILED`: `The
    statistics run failed, so there is no result to show. Counts still work, and the
    failure is logged.` `TOO_FINE`: `That selection is too small to chart without showing
    counts under 10. Try a wider period or fewer filters.` `TOO_LITTLE`, one line per rule:
    `That needs at least 24 full months of records, and this selection has fewer.` /
    `That needs at least 100 records in all, and this selection has fewer.` / `That needs
    at least 100 records with the outcome and 100 without, and this selection has fewer.` /
    `That needs at least 10 records of the rarer outcome for each thing compared, and this
    selection has fewer.` / `That needs at least 100 records in every year, and one year
    here has fewer.` / `That needs at least 30 usable ages in every group, and one group
    here has fewer.` / `That needs at least 12 full months on each side of the date, and
    this selection has fewer.` The numbers in these lines are read from
    `config/analysis.json`. The model is told the error and which rule, never how many
    records there were.
11. **`{aN.bend}`, not clear:** `there was no clear change in the yearly trend after <date
    month> (about <p> points, 95% range <lo> to <hi>)`.
12. **`before_after` with under 12 full months on a side** is `TOO_LITTLE`. A date that is
    not the first of a month, or lies outside the window, is `BAD_OPTIONS`.
13. **`trend_compare`:** each of the two groups needs 100 records. **The window:** every
    kind uses S2's full-month window with the newest month dropped, so every statistical
    answer of a source rests on the same months and the used line can name them.

What the tests do not pin down because of these questions (each a proof gap until a test
is added): the phrases of `night`, `under_18` and `weekend`; the `year` control; a single
hidden quarter; the join in 8; the table lines of 9 beyond `<year>: <n>`; the exact texts
of 10 and 11. The planning chat's check of the build reads these by hand.

### S10, continued: five more answers (added 2026-11-12, 23:00 EST, after the automatic check)

The automatic check of the tests (`kit-log/raw/S3S-A-autocheck.txt`) found five more places
that were not said. They are part of the contract.

14. **`details` after a `timing` answer** shows the table as seven lines, Monday first:
    `<weekday>: ` and then the 24 hourly counts from midnight on, joined by ` | `. A count
    from 1 to 9 is written `fewer than 10`, as everywhere.
15. **`result.json` says how a series was drawn:** for `trend`, `trend_compare` and
    `before_after` it holds `"chart_points": "month"` or `"quarter"` (S6: by quarter when
    any month is from 1 to 9).
16. **A record left out for two reasons is counted once,** under the first of its missing
    fields in the order of the source file, so the parts of the used line add up to the
    records left out. For `trend_compare`, `<n>` is the records of both groups together,
    and a record that is in neither group because the field that makes the groups has no
    value is counted once.
17. **"More than half" (answer 6) is counted over the whole chart,** not per panel. And
    `TOO_LITTLE` is checked before `TOO_FINE`.
18. **A share is a level, not a change:** it never takes a `+` (`16.3%`).

Two wording faults the automatic check and the tests session named are NOT changed in this
round, because every phrase test is written against them; they go to a wording round after
the build: the odds phrase reads badly with some labels ("... went with higher odds of
within 500 feet of a school"), and "points" in the `trend_compare` and bend phrases is in
fact a ratio of the two yearly changes, not a difference in percentage points.

## S11. Wording round (round 2 of Part S; applies AFTER the first build is checked)

Written by the planning chat on 2026-11-13. The first build follows S4 as written, and its
tests are written against S4. This section changes three phrases of S4 and the three
labels of S10 answer 2. It changes no number, no model, no threshold and no rule about what
is shown. (Items 2f, 2g and 2i were added on 2026-11-13 after the planning chat's check of
the first build; the R side found by the same check is S12, a separate round.) Tests first (`briefs/S3S-R2-A-tests.md`), then the planning chat builds it (D-050:
the phrases are plain Python).

Why: the tests session (its note C11) and the first automatic check (its "unclear" point
5) each found a sentence that says something slightly different from what was computed.

**1. The odds phrase.** S4's `<factor label> went with <higher|lower> odds of <outcome
label>` gives "with a weapon recorded went with higher odds of within 500 feet of a
school". New, with both sides written as Part A's `<what>` fragments (C6), the same words a
count uses:

- `{aN.odds.<k>}`, clear: `<unit many> <factor what> had <higher|lower> odds of being
  <outcome what> (odds ratio <or>, 95% range <lo> to <hi>)`. Example: `arrest records with
  a weapon recorded had higher odds of being within 500 feet of a school (odds ratio 1.52,
  95% range 1.21 to 1.91)`.
- Not clear: `<unit many> <factor what> showed no clear difference in the odds of being
  <outcome what> (odds ratio <or>, 95% range <lo> to <hi>)`.
- `<factor what>` and `<outcome what>` are what C6 writes for a filter on that one field
  and label: `with a weapon recorded`; `of people recorded as female`; `in district 3`.
  The three made-up ones are written as C6 writes the matching filter: `under_18` as
  `of people under 18`; `weekend` as `on weekends`; `night` as C6 writes an hour filter
  from 10 pm to 5 am. (This replaces the labels of S10 answer 2. What the three MEAN does
  not change: D-053.)
- The `yes_no` table line (S10 answer 9) becomes `<factor what>: odds ratio <or> (95%
  range <lo> to <hi>)`.

**2. "Points" was the wrong word.** The number in `{aN.difference}` and `{aN.bend}` is a
ratio of two yearly changes, written as a percentage; it is not a difference in percentage
points (two groups growing 5% and 7.1% a year give 2.0, not 2.1). New:

- `{aN.difference}`, clear: `the yearly trend <b what> was about <p>% <above|below> the
  yearly trend <a what> (the ratio of the two yearly changes; 95% range <lo>% to <hi>%)`.
  Not clear: `there was no clear difference in yearly trend between <a label> and <b
  label> (the ratio of the two yearly changes was about <p>%, 95% range <lo>% to <hi>%)`.
  `<a what>`, `<b what>` and the labels are as S10 answer 7 says.
- `{aN.bend}`, clear: `after <date month> the yearly trend was about <p>% <above|below>
  the yearly trend before (the ratio of the two yearly changes; 95% range <lo>% to
  <hi>%)`. Not clear: `there was no clear change in the yearly trend after <date month>
  (the ratio of the two yearly changes was about <p>%, 95% range <lo>% to <hi>%)`.
- Signs as S10 answer 1: after `above` or `below` the size with no sign; in the not-clear
  forms and in every range, `+` or `-`.
- The `trend_compare` table line (S10 answer 9) does not change: each group's own yearly
  change is a plain percentage.

**2b. The hidden line.** The first build does not add C8.2's line (`Counts under 10 are
not shown here; the county's open data has every record: <address>.`) to a statistical
reply (its reading b: S5 did not name it). It belongs there: a statistical reply whose
phrase or table holds `fewer than 10` carries that line, straight after the table and
before the fit line.

**2c. A year that is not whole says so.** Seen in the build's first real answers: the
yearly table of a trend ending in September 2026 has a line `2026: 5,994`, which reads
like a full year. A year the window covers only in part is written with its months:
`2026 (January to September): 5,994`; a first year that starts late the same way.

**2d. `{aN.held}` in the fixed rendering.** The fixed rendering writes every phrase as its
own sentence, which gives `With nothing else held fixed.` standing alone. In the fixed
rendering `{aN.held}` is joined to the last odds sentence of its result with `, `:
`... (odds ratio 1.52, 95% range 1.21 to 1.91), with nothing else held fixed.`

**2f. One line about cause, not two.** Seen in the first real answers: a statistical reply
on a sensitive field ends with both `These are patterns in recorded arrest records: what
goes with what, not what causes what.` and C8.3's `These are counts of arrest records, not
rates, and they show no cause.` When both apply, one line replaces the two: `These are
patterns in recorded <unit many>, not rates: what goes with what, not what causes what.`
A statistical reply with no sensitive field keeps the association line as it is.

**2g. The partial year in a share.** 2c also holds for `shares`: the table line of a
year the window covers in part is `2026 (January to September): 14.8% (95% range 14.0% to
15.8%)`, and `{aN.share}` writes that end as `in January to September 2026` (`the share
of people under 18 went from 7.1% in 2021 to 14.8% in January to September 2026`).

**2i. Room for every factor.** R1 allows a reply four sentences and 600 characters, so the
first build's answer with four factors fell back to the fixed rendering (its note F4). For
a reply that fills k `{aN.odds.<n>}` slots, R1's limits are the larger of 4 and k + 2
sentences, and the larger of 600 and 200 k + 200 characters. Nothing else of R1 changes.

**3. What the wording round's tests must show:** each new phrase exactly, clear and not
clear, both directions, for a flag, a category label and each of the three made-up
factors, as factor and as outcome; the two table lines; that every estimate, range and
clear-or-not verdict is the same as before the round for every case of the truth helper;
the hidden line on the timing case (its quietest cell is hidden) and not on a case with
nothing hidden; a partial last year and a partial first year in the yearly table, and a
whole year unchanged; the fixed rendering of a yes_no answer with and without controls; the single line of 2f
on a sensitive field and the unchanged association line without one; the partial last year
in the shares table and in `{aN.share}`; a reply with four odds slots and one with six
passing R1 where five sentences were refused before, and a reply with one odds slot still
held to four sentences and 600 characters; that no other phrase or fixed line of Part S
changed.

## S12. The R side found by the check of the first build (round 3 of Part S)

Written by the planning chat on 2026-11-13 from its own check of the first build
(`kit-log/raw/S3S-B-chat-check.txt`). These change R (`analysis_r/`), so a Claude Code
session builds them, tests first. Item 1 changes a number and WAITS FOR NINO'S YES; nothing
of item 1 is built or tested before `docs/DECISIONS.md` records it. Items 2 to 4 change
only how a chart is drawn and titled.

**1. (waits for his yes) `trend_compare`: the difference must follow from the two lines
shown.** Today the reply shows each group's own yearly change (each fitted alone) and a
difference taken from a third model that fits both groups with the same month-of-year
pattern. The three numbers do not agree with each other. On the real copy of 12 November
2026: people under 18 +21.3% a year, people aged 18 and over +5.1% a year, and a stated
difference of -12.4%, where the two lines shown give 1.051 / 1.213 = -13.4%. A reader who
checks the arithmetic finds the reply wrong. Proposed: the difference is computed from the
two fits that are shown. On the model's scale it is b(B) minus b(A), with standard error
the square root of se(A) squared plus se(B) squared (the two groups share no record: the first
build already refuses two groups that overlap, its reading E9, and this makes that a rule), then the 95% Wald interval as S3. On the same copy this gives -13.4%
(95% range -17.1% to -9.5%) in place of -12.4% (-15.9% to -8.6%), and for district 3
against district 4 -0.2% (-3.3% to +3.0%) in place of -0.1% (-3.3% to +3.2%); no verdict
of clear or not clear changes in either. The third model is dropped: the fit ratio is the
two groups' last six months together over what their two own fits expected, and the
result names the model of each group (they can differ if one falls back to Poisson).

**2. A chart says what its lines are.** The foot line of `trend`, `trend_compare` and
`before_after` charts gains, before the source: `Grey: recorded each month. Blue: the
model's line and its 95% range.` (by quarter: `Grey: recorded each quarter, as an average
per month.`).

**3. `trend_compare`: each panel its own value axis.** S6 said "same value axis". With
groups of very different size (people under 18 against 18 and over) the smaller group's
trend is pressed flat and cannot be read, and the question is about the trends. Each panel
gets its own value axis, starting at 0, and the foot line gains `The two panels have
different scales.`

**4. Titles.** `read_as` (the chart's title and the line the model is given) for `shares`
becomes `the yearly share of <unit many> that were <part what>, from <first month> to
<last month>` (was: "the yearly share of people under 18 of arrest records"); for `yes_no`
`the odds of <unit many> being <outcome what>, for those <factor what 1>, ... and <factor
what k>, <held>, from <first month> to <last month>`, with the `<what>` fragments of S11
item 1 (was: "the odds of within 500 feet of a school in arrest records, by being under 18
and female"). A partial year on the `shares` chart's axis is labelled `2026 (Jan to Sep)`.
(`read_as` is written by Python; the chart only prints it. The axis label is R.)

**4b. R is started with a short environment.** Today the R process gets the agent's whole
environment, which on the server holds the keys. R gets only `PATH`, `HOME`, `LANG`,
`LC_ALL`, `TZ`, `TMPDIR` and any variable whose name starts with `R_`. Nothing R does today
reads a key; this keeps a later change to an R file from being able to.

**4c. A before-and-after at the edge of S3 never ends `ENGINE_FAILED`.** (Added 13 Nov
18:23 EST under D-061, from the second full live run.) A `before_after` over exactly 24
months with the date in the middle (12 full months on each side, S3's least) stopped R in
`term_estimate` -> `wald`: "no finite estimate for step". Reproduced by the planning chat
without the model on the copy of police arrests of 12 November 2026, for 2024 and 2025 with
1 January 2025 and for 2023 and 2024 with 1 January 2024 (`kit-log/raw/S12-chat-repro-before-
after.py` and `.txt`). Required: every selection S3 lets through to R either gives finite
estimates for every term the reply names, or is refused before R as `TOO_LITTLE` with a
`why` that says why in plain words. The R session finds the cause (the model's terms at 24
points, or the minimum itself) and says which fix it chose; if the fix changes S3's minimum
(how many months a side), that is a change of an analytical rule and waits for Nino's yes
(written into `briefs/QUESTIONS.md`; the round goes on with the refusal). No other estimate
changes.

**4c DECIDED (D-064, 14 Nov 2026):** S3's least for a before-and-after is 12 full months on each side and more than 12 on one side (25 months in all), as built (rule `step_apart`). Nino chose this over asking for more months.

**5. What round 3's tests must show:** for item 1, once approved: the difference, its
range and verdict from the two own fits for every `trend_compare` case of the truth
helper, to the tolerance of S9; that (1 + b's change) / (1 + a's change) - 1 equals the
stated difference to one decimal for each case; the fit ratio from the two own fits; the
R cross-check rerun. For items 2 to 4: the foot line texts in the chart's data (the tests
read the plot's labels from `result.json`, which gains `"chart_labels": {"title",
"subtitle", "foot", "axis"}`, not from the picture); the panels' scales recorded as
`"chart_scales": "own"` for `trend_compare`; the two `read_as` forms for a flag, a
category label and each made-up factor; the partial-year axis label. For 4b: with a
made-up variable named like a key set in the agent's environment, a stand-in for Rscript
that writes its environment to the job folder shows that variable absent and `PATH`
present.

## S11, answers to the wording round's tests session (2026-11-13)

Its readings 1 to 7 stand (`kit-log/raw/S3S-R2-A-notes.txt`). On its points:

1. C8.2's line ends with the source's `<page>`, as C8.2 writes it. "Address" in 2b was
   loose wording.
2. A sensitive field as the outcome of `yes_no` counts as a sensitive field in the reply
   (the first build's reading h), so 2f's single line applies.
3. Noted: "had higher odds of being of people under 18" and "of being on weekends" read
   stiffly. They are right and they are what S11 says; a later round may give outcomes
   their own form.
4. A year with one month in the window is written `2026 (January)`, and in a share
   `in January 2026`.
5. A partial FIRST year in `{aN.share}` takes the same form as a partial last one:
   `from 12.0% in March to December 2021 to ...`.
6. The used line does not bring the hidden line, as the left-out lines of a count do not:
   it already says what is not included.
7. With `MOCO_TALK` on, a finding with k odds slots may have the larger of 4 and k + 2
   fact sentences and the larger of 700 and 200 k + 200 characters; the limit on talk
   sentences does not change. With two results in one reply, k counts the odds slots of
   both.
8. Right: `read_as` and the model sentence of `details` still use S10's labels until S12
   item 4.
9. Noted: the helper `stat_reply_re` still builds the old ending; the round 3 tests
   session may change it.

## S11, answer to the proof-gap tests session (S3S-R2b-A, 2026-11-13)

Its question: does `details` carry C8.2's hidden line when its table hides a count? No:
`details` keeps S7's contents, and its limits already say `Counts under 10 are never shown,
in a table or on a chart.` and its data line ends with the page. No change; the test that
accepts either reading may keep accepting the limits line only.

## S12, answers to the round 3 tests session (S3S-R3-A; planning chat, 14 Nov 00:34 EST)

1. By quarter the blue sentence still follows: `Grey: recorded each quarter, as an average per
   month. Blue: the model's line and its 95% range.`
2. The filters stay in `read_as`, where the old forms had them: `the yearly share of arrest
   records in district 3 that were ...`, `the odds of arrest records in district 3 being ...`.
3. After item 1, the model sentence of `details` for `trend_compare` says each group's own
   line is fitted on its own and names each group's model, then that the difference is the
   ratio of the two yearly changes. Not built in round 3 (no test); a later wording round.
4. No: this round moves `read_as` only; the yes_no model sentence of `details` keeps S10's
   labels until a later wording round.

## S13. An analysis with no period, and choosing the kind (round 4 of Part S; D-061)

From the live check of 13 November (`kit-log/raw/S3-county-check-live-2026-11-13.txt`):
the prompts tell the model to leave the period out when the message names none, and for
`analyze` Python then asked "Which period do you mean?" (five questions of twelve). A
question such as "is the trend in district 3 different from district 4?" has no period by
nature.

1. `analyze` with no period stated, none pending from a turn that asked, and none kept
   from the thread's last answer uses the whole of the copy: the source's first day to
   the copy's newest day (S2's window rule then takes the full months, as today). Python
   does not ask for the period, and the period is not said to be "kept". A period that IS
   pending or kept is used as today. `count` does not change: with no period it asks.
2. The two county prompts replace the line "Give source, period and filters exactly as for
   count, ..." with these two lines, word for word:
   - `- Give source and filters exactly as for count. Leave the period out unless the
     message names one: with no period the program uses every month it has. Never put the
     date of a before_after question in the period. The program uses full months only and
     names them.`
   - `- Pick the kind by the question, and do not count instead: "has the share of X
     changed", "is the share of X going up" is shares with options {"part": [the filters
     of X]} and no other filter; "which days or hours are busiest", "at what times" is
     timing; "how old", "how do the ages compare between groups" is distribution with
     {"by": "<field>"}; "did it change from <month> on" is before_after; "is the trend
     for A different from B" is trend_compare with A in filters and B in versus, never
     both in filters.`
   Whether these lines work is not something a test with a stand-in model can show: the
   live check is their test.
3. The shapes the model sends by mistake are read as what they mean, before C9's filling:
   - option keys (`versus`, `date`, `outcome`, `factors`, `controls`, `part`, `by`) sent
     beside `options` instead of inside it, when `options` is missing or empty, are taken
     as the options;
   - `options`, or one option's value, sent as JSON text (a string that starts with `[` or
     `{`) is read as that JSON; text that is not JSON is left as it is (and refused as
     today);
   - a period with only `from` or only `to` is no period (point 1 then applies).
   Seen in the rerun: yes_no with its options at the top level as JSON text, six times; a
   before_after whose period was `{"from": <the date>}`.
4. A `before_after` whose stated (or kept) period leaves fewer than 12 full months on a side
   of the date is run on the whole copy instead, as if no period had been given; the reply
   names the months used, as always. Any other TOO_LITTLE is unchanged.
5. Two refusals say what to do, word for word (the codes do not change):
   - `trend_compare` refused because two filters name one field: `trend_compare: one group in
     filters and the other in options.versus, one filter each, for example filters
     [{"field": "district", "is": "district 3"}] and options {"versus": [{"field":
     "district", "is": "district 4"}]}`;
   - `shares` whose part filters a field the filters already limit: `shares: the part must
     not filter a field that filters already limit. For "the share of X among all records"
     send filters [] and options {"part": [the filters of X]}`.
6. The kind line of point 2 begins, before "has the share of X changed": `"is it rising",
   "going up or down", "increasing" is trend, with the filters of the group the question
   names; `.
7. A factor given as a bare label (`"female"`) is read as `{"field": <field>, "is": <label>}`
   when exactly one category field of the source has that label (capitals not counting);
   otherwise refused as today.
8. `trend_compare` whose versus names the same group as its filters: BAD_OPTIONS `versus is
   the same group as filters: for the trend of one group use kind trend`.
9. A `count` with no period stated, none pending and none kept, in a turn whose question
   holds words of an analysis (rise, going up or down, increase, decrease, trend, over the
   years, over time, change, share, proportion, percentage, what time(s), which days or
   hours, busiest, times of the day or week, how old, ages, what goes with, odds, more
   likely; whole words, capitals not counting) is answered, once a turn, with the tool
   error `USE_ANALYZE`, why: `This question is about change over time, a share, the times of
   the week, ages or what goes with what: use analyze, with the period left out (it uses
   every month). Pick its kind as the instructions say.` Nothing is counted; the error is
   not one of the turn's count errors. A second such count in the turn asks for the
   period as today.
10. `compare` or `share` naming an analysis's id: BAD_COMPARE / BAD_SHARE, why: `compare and
    share take counts only; an analysis's own slots already say what it found: call finish
    with them`.
11. Two more hints, word for word: distribution's `by` that is not a category or yes-or-no
    field: `"by" names the field of the groups whose ages are compared, such as "gender" (a
    category or yes-or-no field); leave it out for everyone`; a distribution with two
    filters on one field: `distribution: to compare the ages of groups send options {"by":
    "<field>"}, for example {"by": "gender"}, and no filter on that field`.
12. The kind line of point 2 is replaced by the one now in both county prompts (shares
    first, then trend, timing, distribution with the field of the groups, before_after,
    trend_compare, and yes_no "with X as the outcome and every factor the question names in
    one call"). The prompts are the text of record.
13. A `before_after` with no `options.date` whose period is `{"from": <day>}` or `{"date": <day>}`
    takes that day's month as `options.date` (the first of the month) and has no period.
14. A `trend` asked in a turn whose question holds a share word (share, shares, proportion,
    proportions, percentage, percentages, percent; whole words, capitals not counting) is
    answered, once a turn, with the tool error `USE_SHARES`, why: `This question asks about a
    share: use kind shares, with filters for the whole (none for all records) and options
    {"part": [the filters of the group]}, for example options {"part": [{"field": "age", "to":
    17}]}.` Nothing runs. The second such trend in the turn runs as today.


## S13, answers to the round 4 tests session (S3S-R4-A; planning chat, 13 Nov 18:47 EST)

Its 111 tests and the two changed ones pass on the held build (chat/c21-build f711fee): with
the rest of tests/s3s, 352 of 352. On its six points:

1. The kind line's text of record is the line beginning `- Pick the kind by the question, and
   do not count instead.` in `config/agent_prompt_s3.md` and `config/agent_prompt_s3_talk.md`
   on the held branch (the same in both). It holds point 6's trend clause word for word; the
   kinds come in point 12's order (shares first). A later tests round may pin it whole.
2. A kept period that a before_after does not use is NOT said to be kept: no kept note for
   it (built in f711fee, found by this question).
3. Yes: the period of an analysis run on the whole copy is the last answer's period (C9), so a
   following `count` with no period is counted over it, with the kept note naming it.
4. Refused, as today: the 24-month rule is checked first and is "another TOO_LITTLE"; only the
   sides rule widens.
5. The word lists are the regular expressions `ANALYSIS_WORDS` and `SHARE_WORDS` in
   `src/moco_agent/agent.py` (whole words, any case): "going up" and "going down", "which
   days" and "which hours", "times of the day" and "times of the week" each count alone;
   "rise", "rises", "rising", "increase..." and "decrease..." in any form, "change", "changed",
   "changes", "changing" all count. Tests may pin those forms.
6. The codes do not change: `by` that is not such a field stays BAD_OPTIONS; two filters on
   one field stay BAD_FIELD.

## S14. A shares analysis over one year (planning chat, 14 Nov 12:00 EST; D-061)

Live round 10 (Nemotron 3 Ultra, all 48 cases, 14 Nov): C07 run 2, "What share of arrests in
2025 were of women?", was sent as `analyze` kind `shares` with the period `{"year": 2025}` and
ended ENGINE_FAILED: R stopped in `model_shares` -> `wald("sharetrend", coef(fit)["year"] ...)`,
because with one year the year term has no estimate. The reply was the fixed engine-failed
line; no wrong figure was shown. `_s_table` checks `min_base_year` but not the number of years.

Required: a `shares` selection whose months fall in fewer than two calendar years is refused
before R as `TOO_LITTLE`, rule `years`, with exactly

`That follows a share across years, so it needs at least two years of records. For one year, I can count the whole and the part and give the share.`

Nothing else changes; the model may still call `count` and `share` in the same turn. Tests:
a shares analysis over one year is refused with that line and R is not started; over two
years it runs as today; the line word for word.

**S14, the order (planning chat, 14 Nov 15:20 EST; check 3's question 1).** The years check
comes first: a selection of one year is refused with S14's line even when its base is also
under `min_base_year` or a part is hidden, because with one year there is nothing to follow.
The build already does this. Test: one year whose base is under `min_base_year` gets S14's
line, and R is not started.
