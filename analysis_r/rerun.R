# ---- rerun.R: the body of the script anyone can run (docs/S3S-DESIGN.md S7) -----------------
# Python puts above this: the notes, `data_url` and `job` (the source's fields as the agent
# reads them, the filters, the months, the options), then common.R. This part downloads the
# records once, builds the same table the agent gave R, fits the same model with common.R and
# prints the estimates. It saves nothing.

rows <- jsonlite::fromJSON(data_url, simplifyVector = TRUE)
if (!is.data.frame(rows)) rows <- data.frame()
d <- job$data
column <- function(name) {
  if (name %in% names(rows)) as.character(rows[[name]]) else rep(NA_character_, nrow(rows))
}

# The time of each record: the day and the hour, as the service writes them.
when <- column(job_chr(d$time_field))
day <- as.Date(substr(when, 1, 10), format = "%Y-%m-%d")
hour <- suppressWarnings(as.integer(substr(when, 12, 13)))
inside <- !is.na(day) & !is.na(hour) & day >= as.Date(job_chr(d$first_day)) &
  day <= as.Date(job_chr(d$last_day))
wday <- (as.POSIXlt(day)$wday + 6L) %% 7L          # Monday is 0
year <- as.integer(format(day, "%Y"))
month <- as.integer(format(day, "%m"))
WEEKDAY_NAMES <- c("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Each field the analysis uses: its value as the agent reads it, and whether the record has
# one it can use (a listed raw value; a whole-number age inside the usable range).
fields <- list()
value <- list()
usable <- list()
for (f in d$fields) {
  name <- job_chr(f$name)
  raw <- column(name)
  if (f$kind == "age") {
    a <- suppressWarnings(as.integer(raw))
    ok <- !is.na(raw) & grepl("^[0-9]+$", raw) & !is.na(a) &
      a >= job_num(f$usable)[1] & a <= job_num(f$usable)[2]
    v <- ifelse(ok, a, NA)
  } else if (f$kind == "category") {
    map <- unlist(f$values)
    ok <- !is.na(raw) & raw %in% names(map)
    v <- ifelse(ok, unname(map[raw]), NA)
  } else {
    ok <- !is.na(raw) & raw %in% c(job_chr(f$yes_raw), job_chr(f$no_raw))
    v <- ifelse(ok, raw == job_chr(f$yes_raw), NA)
  }
  fields[[name]] <- f
  value[[name]] <- v
  usable[[name]] <- ok
}

matches <- function(flt) {
  name <- job_chr(flt$field)
  if (name == "weekday") return(WEEKDAY_NAMES[wday + 1] %in% job_chr(flt[["in"]]))
  if (name == "hour") {
    lo <- job_num(flt$from)
    hi <- job_num(flt$to)
    return(if (lo <= hi) hour >= lo & hour <= hi else hour >= lo | hour <= hi)
  }
  v <- value[[name]]
  kind <- fields[[name]]$kind
  if (kind == "age") {
    out <- rep(TRUE, length(v))
    if (!is.null(flt$from)) out <- out & v >= job_num(flt$from)
    if (!is.null(flt$to)) out <- out & v <= job_num(flt$to)
    return(out %in% TRUE)
  }
  if (kind == "flag") return(v %in% isTRUE(flt$is))
  v %in% job_chr(flt[["in"]])
}

# A record is in a group when it matches every filter on a field it has a value for; it is
# then counted, or left out (once, under its first missing field in the source file's order)
# when a field the analysis uses has no usable value.
gap <- rep(FALSE, nrow(rows))
first_gap <- rep(NA_character_, nrow(rows))
for (name in rev(names(usable))) {
  first_gap[!usable[[name]]] <- name
  gap <- gap | !usable[[name]]
}
in_group <- function(filters) {
  ok <- inside
  for (flt in filters) {
    name <- job_chr(flt$field)
    has <- if (name %in% names(usable)) usable[[name]] else rep(TRUE, nrow(rows))
    ok <- ok & (!has | matches(flt))
  }
  ok
}
member <- lapply(d$groups, in_group)
anywhere <- Reduce(`|`, member)
left <- table(factor(first_gap[anywhere & gap], levels = names(usable)))
kept <- lapply(member, function(m) m & !gap)

months <- do.call(rbind, lapply(d$months, function(ym) data.frame(year = ym[[1]], month = ym[[2]])))
months$days <- month_days(months$year, months$month)
by_month <- function(sel) {
  vapply(seq_len(nrow(months)), function(i) {
    sum(sel & year == months$year[i] & month == months$month[i])
  }, numeric(1))
}

item_value <- function(item) {
  if (item$type == "made") {
    name <- job_chr(item$name)
    if (name == "under_18") return(as.integer(value[[job_chr(d$age_field)]] < 18))
    if (name == "weekend") return(as.integer(wday >= 5))
    return(as.integer(hour %in% c(22, 23, 0:5)))
  }
  v <- value[[job_chr(item$field)]]
  if (item$type == "flag") return(as.integer(v %in% isTRUE(item$is)))
  as.integer(v %in% job_chr(item$label))
}

kind <- job_chr(job$kind)
sel <- kept[[1]]
if (kind %in% c("trend", "before_after")) {
  tab <- data.frame(year = months$year, month = months$month, days = months$days,
                    n = by_month(sel))
} else if (kind == "trend_compare") {
  tab <- rbind(data.frame(months, group = 0, n = by_month(kept[[1]])),
               data.frame(months, group = 1, n = by_month(kept[[2]])))
} else if (kind == "shares") {
  part <- Reduce(`&`, lapply(d$part, matches), sel)
  tab <- data.frame(year = months$year, month = months$month, base = by_month(sel),
                    part = by_month(part))
} else if (kind == "yes_no") {
  tab <- data.frame(outcome = item_value(d$outcome)[sel])
  for (i in seq_along(d$factors)) tab[[paste0("factor", i)]] <- item_value(d$factors[[i]])[sel]
  for (ctl in d$controls) {
    x <- if (job_chr(ctl$field) == "year") as.character(year) else value[[job_chr(ctl$field)]]
    tab[[job_chr(ctl$column)]] <- x[sel]
  }
} else if (kind == "timing") {
  grid <- expand.grid(hour = 0:23, weekday = 0:6)
  grid$n <- mapply(function(w, h) sum(sel & wday == w & hour == h), grid$weekday, grid$hour)
  tab <- grid[, c("weekday", "hour", "n")]
} else {
  tab <- data.frame(age = value[[job_chr(d$age_field)]][sel])
  if (!is.null(d$by)) {
    v <- value[[job_chr(d$by$field)]][sel]
    if (d$by$kind == "flag") v <- ifelse(v, job_chr(d$by$yes), job_chr(d$by$no))
    tab$group <- v
  }
}

m <- run_model(tab, job)
res <- m$result

# ---- what it prints: a readable summary, then one line per estimate ------------------------
floor <- job_num(job$floor)
shown <- function(n) ifelse(n >= 1 & n < floor, paste("fewer than", floor),
                            format(n, big.mark = ",", trim = TRUE))
cat("Rerun of:", job_chr(job$read_as), "\n")
cat(sprintf("%s records over %d months (%s to %s).\n", shown(sum(vapply(kept, sum, numeric(1)))),
            nrow(months), job_chr(job$window$first), job_chr(job$window$last)))
for (name in names(left)) if (left[[name]] > 0) {
  cat(sprintf("Not included, no usable %s: %s\n", name, shown(left[[name]])))
}
cat("Model:", res$model, "\n")
if (kind == "timing") {
  for (w in 0:6) cat(WEEKDAY_NAMES[w + 1], ": ",
                     paste(shown(tab$n[tab$weekday == w][order(tab$hour[tab$weekday == w])]),
                           collapse = " | "), "\n", sep = "")
}
if (kind == "distribution") {
  for (g in res$groups) cat(sprintf("%s median %s, middle half %s to %s (%s ages)\n",
                                    if (nzchar(g$label)) g$label else "all", g$median, g$q1,
                                    g$q3, shown(g$n)))
}
if (kind == "shares") {
  for (y in res$years) cat(sprintf("%d: %.1f%% (95%% range %.1f%% to %.1f%%)\n", as.integer(y$year),
                                   y$share, y$low, y$high))
}
if (length(res$estimates)) {
  cat("Estimates (", if (res$estimates[[1]]$scale == "percent") "percent" else "odds ratio",
      ", 95% range):\n", sep = "")
  number <- function(x) format(x, digits = 15, scientific = FALSE, trim = TRUE)
  for (e in res$estimates) cat(e$name, number(e$estimate), number(e$low), number(e$high), "\n")
}
