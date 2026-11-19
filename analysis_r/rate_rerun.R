# ---- rate_rerun.R: the body of the rate script anyone can run (docs/S3S2-DESIGN.md R8) -------
# Python puts above this: the notes, `data_url`, `census_url` and `job` (the years, the groups
# with their Census variables and the rules that put a record in a group), then
# rate_common.R. This part downloads the county's records once and each Census table once a
# year, counts and adds up as the agent did, and prints the rates. It saves nothing.

rows <- jsonlite::fromJSON(data_url, simplifyVector = TRUE)
if (!is.data.frame(rows)) rows <- data.frame()
column <- function(name) {
  if (name %in% names(rows)) as.character(rows[[name]]) else rep(NA_character_, nrow(rows))
}
label_of <- function(name) {
  map <- unlist(job$fields[[name]]$values)
  raw <- column(name)
  ifelse(!is.na(raw) & raw %in% names(map), unname(map[raw]), NA_character_)
}

# The year of each record, and the group it counts in (none: left out).
years <- job_num(job$years)
year <- suppressWarnings(as.integer(substr(column(job_chr(job$time_field)), 1, 4)))
inside <- !is.na(year) & year %in% years
keys <- vapply(job$groups, function(g) job_chr(g$key), character(1))
group <- rep(NA_character_, nrow(rows))
by <- if (is.null(job$by)) "" else job_chr(job$by)
if (by == "") {
  group[] <- keys[1]
} else if (by == "age_band") {
  raw <- column(job_chr(job$age_field))
  usable <- job_num(job$usable)
  a <- suppressWarnings(as.integer(raw))
  ok <- !is.na(raw) & grepl("^[0-9]+$", raw) & !is.na(a) & a >= usable[1] & a <= usable[2]
  for (g in job$groups) {
    band <- job_num(g$ages)
    top <- if (length(band) < 2) Inf else band[2]
    group[is.na(group) & ok & a >= band[1] & a <= top] <- job_chr(g$key)
  }
} else {
  for (g in job$groups) {
    hit <- rep(TRUE, nrow(rows))
    for (name in names(g$rule)) {
      v <- label_of(name)
      hit <- hit & !is.na(v) & v == job_chr(g$rule[[name]])
    }
    group[is.na(group) & hit] <- job_chr(g$key)
  }
}
records <- vapply(keys, function(k) sum(inside & !is.na(group) & group == k), numeric(1))
left_out <- sum(inside & is.na(group))

# Each Census table once a year: a first line of names, one line of values.
cells <- list()
for (y in years) {
  for (table in job_chr(job$tables)) {
    answer <- jsonlite::fromJSON(census_url(y, table), simplifyVector = TRUE)
    cells[[as.character(y)]] <- c(cells[[as.character(y)]],
                                  stats::setNames(as.character(answer[2, ]), answer[1, ]))
  }
}

# R10 point 4: a group with fewer than min_records records is not shown and not computed.
shown <- which(records >= job_num(job$min_records))
if (!length(shown)) stop("too little data for a rate: no group has enough records")
census <- do.call(rbind, lapply(seq_along(shown), function(k) {
  g <- job$groups[[shown[k]]]
  do.call(rbind, lapply(years, function(y) {
    cs <- cells[[as.character(y)]]
    do.call(rbind, lapply(job_chr(g$variables), function(v) {
      m <- cs[[paste0(v, "M")]]
      data.frame(k = k, year = y, estimate = as.numeric(cs[[paste0(v, "E")]]),
                 margin = if (is.na(m) || m %in% job_chr(job$no_margin)) NA_real_
                          else as.numeric(m))
    }))
  }))
}))
groups <- data.frame(k = seq_along(shown), records = records[shown])
labels <- vapply(job$groups[shown], function(g) job_chr(g$label), character(1))
residents <- vapply(seq_along(shown), function(k) sum(census$estimate[census$k == k]), numeric(1))
reference <- NULL
if (by != "") {
  wanted <- if (is.null(job$reference)) "" else tolower(trimws(job_chr(job$reference)))
  reference <- if (wanted %in% tolower(labels)) which(tolower(labels) == wanted)[1] else
    which.max(residents)
}
m <- rate_model(census, groups, reference, job_num(job$per), job_num(job$z))

cat(sprintf("%s\n", job_chr(job$read_as)))
for (g in m$groups) {
  cat(sprintf("%s: %d records, %.0f residents, %.1f per 10,000%s\n", labels[g$k], g$records,
              g$residents, g$rate,
              if (is.na(g$margin)) " (the Census gives no margin of error)" else
                sprintf(" (margin of error %.1f)", g$margin)))
}
cat(sprintf("%d records of these years are in no group shown.\n",
            as.integer(left_out + sum(records[-shown]))))
cat("\n")
for (g in m$groups) {
  name <- if (by == "") "rate" else paste0("rate.", g$k)
  cat(name, format(g$rate, digits = 15), format(g$rate - g$margin, digits = 15),
      format(g$rate + g$margin, digits = 15), "\n")
}
for (x in m$ratios) {
  cat(paste0("ratio.", x$k), format(x$ratio, digits = 15), format(x$low, digits = 15),
      format(x$high, digits = 15), "\n")
}
