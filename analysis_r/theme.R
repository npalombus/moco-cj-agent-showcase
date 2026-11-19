# theme.R: the one look of every chart (docs/S3S-DESIGN.md S6) and the charts themselves.
# White background, a grey grid on the value axis only, one blue for the data, grey for
# context, no legend for one series. PNG, 1600 by 1000 pixels. A count from 1 to the floor
# less one is never drawn: a series is then drawn by quarter and a quarter, a heat map cell
# or a histogram bar from 1 to 9 is left empty, and the foot line says so.

local({  # S1 ENGINE_MISSING: Python reads this mark
  missing <- Filter(function(p) !requireNamespace(p, quietly = TRUE),
                    c("MASS", "ggplot2", "jsonlite", "sandwich"))
  if (length(missing)) {
    message("MOCO-MISSING-PACKAGE: ", paste(missing, collapse = ", "))
    quit(save = "no", status = 3)
  }
})
suppressPackageStartupMessages(library(ggplot2))

BLUE <- "#1f5fa8"
GREY <- "grey55"
LIGHT <- "#dde8f5"
WEEKDAYS <- c("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

theme_moco <- function(value_axis = "y") {
  base <- theme_minimal(base_size = 18) + theme(
    plot.background = element_rect(fill = "white", colour = NA),
    panel.background = element_rect(fill = "white", colour = NA),
    panel.grid.minor = element_blank(), panel.grid.major = element_blank(),
    legend.position = "none",
    plot.title = element_text(face = "bold", size = 21),
    plot.subtitle = element_text(colour = "grey30", margin = margin(b = 12)),
    plot.caption = element_text(hjust = 0, colour = "grey30", size = 13,
                                margin = margin(t = 14)),
    plot.title.position = "plot", plot.caption.position = "plot",
    strip.text = element_text(face = "bold", size = 16),
    plot.margin = margin(24, 34, 20, 24))
  grid <- element_line(colour = "grey88")
  if (value_axis == "y") base <- base + theme(panel.grid.major.y = grid)
  if (value_axis == "x") base <- base + theme(panel.grid.major.x = grid)
  base
}

wrap <- function(text, width) paste(strwrap(text, width), collapse = "\n")

cap <- function(text) paste0(toupper(substr(text, 1, 1)), substr(text, 2, nchar(text)))

# What the chart says in words, kept for result.json (S12 item 5: "chart_labels", and
# "chart_scales" for trend_compare): the tests read these, not the picture.
drawn <- new.env()

# Title: what was analysed (read_as); subtitle: the months used and the copy's date; foot
# line: what the lines are (`lines`, S12 items 2 and 3), the source and what the records
# are, and what is left empty. `ticks`: tick labels written in words (shares' years, the
# factors of yes_no), kept with the axis titles.
chart_labels <- function(job, x = NULL, y = NULL, empty = NULL, lines = NULL, ticks = NULL) {
  w <- job$window
  title <- cap(job_chr(job$read_as))
  subtitle <- sprintf("%s to %s (%d months). Copy of the county's data of %s.",
                      job_chr(w$first), job_chr(w$last), as.integer(job_num(w$months)),
                      job_chr(job$copy_date))
  foot <- paste(c(lines, sprintf("%s. Recorded %s, not people; patterns, not causes.",
                                 job_chr(job$source_title), job_chr(job$unit_many)), empty),
                collapse = " ")
  drawn$labels <- list(title = title, subtitle = subtitle, foot = foot,
                       axis = Filter(Negate(is.null), list(x = x, y = y, ticks = ticks)))
  labs(title = wrap(title, 95), subtitle = subtitle, caption = wrap(foot, 160), x = x, y = y)
}

save_chart <- function(p, dir) {
  ggsave(file.path(dir, "chart.png"), p, width = 16, height = 10, units = "in", dpi = 100,
         bg = "white")
}

hidden <- function(n, floor) n >= 1 & n < floor

# ---- T: monthly counts, the fitted values and their 95% band --------------------------------

# By month, or by quarter (three months from the window's first) when any month is from 1
# to 9 (S6, S10 answer 15). A quarter's band comes from the sum of its fitted values (delta
# method on the log scale). Values are per month: a quarter is the average of its months.
# trend_compare: each panel from its own group's fit (S12 item 1, m$models).
series_frame <- function(m, df, job) {
  z <- job_num(job$z)
  floor <- job_num(job$floor)
  by_quarter <- job_chr(job$chart_points) == "quarter"
  panels <- if (is.null(df$g)) list(list(k = 0L, rows = seq_len(nrow(df)), model = m$model)) else
    lapply(0:1, function(k) list(k = k, rows = which(df$g == k), model = m$models[[k + 1]]))
  out <- list()
  for (pn in panels) {
    d <- df[pn$rows, ]
    X <- stats::model.matrix(pn$model$fit)
    V <- pn$model$V
    mu <- as.numeric(stats::fitted(pn$model$fit))
    idx <- order(d$year * 12 + d$month)
    parts <- if (by_quarter) split(idx, ceiling(seq_along(idx) / 3)) else as.list(idx)
    for (rows in parts) {
      size <- length(rows)
      total <- sum(d$n[rows])
      expected <- sum(mu[rows])
      grad <- colSums(mu[rows] * X[rows, , drop = FALSE])
      se <- sqrt(as.numeric(t(grad) %*% V %*% grad)) / expected
      mid <- rows[ceiling(size / 2)]
      out[[length(out) + 1]] <- data.frame(
        panel = pn$k, date = as.Date(sprintf("%04d-%02d-15", d$year[mid], d$month[mid])),
        n = if (hidden(total, floor)) NA_real_ else total / size, fit = expected / size,
        lo = expected * exp(-z * se) / size, hi = expected * exp(z * se) / size)
    }
  }
  do.call(rbind, out)
}

draw_series <- function(m, job, dir, panels = NULL, date_line = NULL) {
  sf <- series_frame(m, m$frame, job)
  by_quarter <- job_chr(job$chart_points) == "quarter"
  many <- job_chr(job$unit_many)
  ylab <- if (by_quarter) paste(cap(many), "per month (each quarter's average)") else
    paste(cap(many), "per month")
  empty <- if (any(is.na(sf$n))) sprintf("Quarters with fewer than %d records are left as gaps.",
                                         as.integer(job_num(job$floor))) else NULL
  # S12 item 2: what the lines are, before the source; item 3: two panels, two scales
  lines <- c(if (by_quarter) "Grey: recorded each quarter, as an average per month." else
               "Grey: recorded each month.",
             "Blue: the model's line and its 95% range.",
             if (!is.null(panels)) "The two panels have different scales.")
  if (!is.null(panels)) sf$label <- factor(panels[sf$panel + 1], levels = panels)
  p <- ggplot(sf, aes(x = date)) +
    geom_ribbon(aes(ymin = lo, ymax = hi), fill = BLUE, alpha = 0.18) +
    geom_line(aes(y = n), colour = GREY, linewidth = 0.6, na.rm = TRUE) +
    geom_line(aes(y = fit), colour = BLUE, linewidth = 1.3) +
    expand_limits(y = 0) +
    scale_x_date(date_breaks = "1 year", date_labels = "%Y") +
    theme_moco("y") + chart_labels(job, y = ylab, empty = empty, lines = lines)
  if (by_quarter) p <- p + geom_point(aes(y = n), colour = GREY, size = 1.6, na.rm = TRUE)
  if (!is.null(date_line)) {
    p <- p + geom_vline(xintercept = date_line, linetype = "dashed", colour = "grey25",
                        linewidth = 0.8)
  }
  if (!is.null(panels)) {  # S12 item 3: each panel its own value axis, from 0
    p <- p + facet_wrap(~label, nrow = 1, scales = "free_y")
    drawn$scales <- "own"
  }
  save_chart(p, dir)
}

# ---- L: odds ratios ------------------------------------------------------------------------

draw_odds <- function(m, job, dir) {
  labels <- vapply(job_chr(job$factors), function(x) wrap(x, 34), character(1))
  est <- m$result$estimates
  d <- data.frame(label = factor(labels, levels = rev(labels)),
                  or = vapply(est, function(e) e$estimate, numeric(1)),
                  lo = vapply(est, function(e) e$low, numeric(1)),
                  hi = vapply(est, function(e) e$high, numeric(1)))
  p <- ggplot(d, aes(y = label)) +
    geom_vline(xintercept = 1, colour = "grey40", linewidth = 0.8) +
    geom_segment(aes(x = lo, xend = hi, yend = label), colour = BLUE, linewidth = 1.4) +
    geom_point(aes(x = or), colour = BLUE, size = 4.5) +
    scale_x_log10() +
    theme_moco("x") +
    chart_labels(job, x = sprintf("Odds ratio of %s, log scale (1 is no difference)",
                                  job_chr(job$outcome)), y = NULL, ticks = job_chr(job$factors))
  save_chart(p, dir)
}

# ---- S: the yearly share ---------------------------------------------------------------------

# S12 item 4: a year the window covers in part is labelled with its months, `2026 (Jan to
# Sep)` (`2026 (Jan)` for one month); a whole year is the bare year. The window's months are
# job.json's data.months.
year_axis <- function(job, years) {
  ym <- vapply(job$data$months, job_num, numeric(2))
  vapply(years, function(y) {
    have <- ym[2, ym[1, ] == y]
    a <- min(have)
    b <- max(have)
    if (a == 1 && b == 12) as.character(y) else if (a == b) sprintf("%d (%s)", y, month.abb[a])
    else sprintf("%d (%s to %s)", y, month.abb[a], month.abb[b])
  }, character(1))
}

draw_shares <- function(m, job, dir) {
  ys <- m$result$years
  d <- data.frame(year = vapply(ys, function(v) v$year, numeric(1)),
                  share = vapply(ys, function(v) v$share, numeric(1)),
                  lo = vapply(ys, function(v) v$low, numeric(1)),
                  hi = vapply(ys, function(v) v$high, numeric(1)))
  years <- year_axis(job, d$year)
  p <- ggplot(d, aes(x = year, y = share)) +
    geom_line(colour = BLUE, linewidth = 1) +
    geom_linerange(aes(ymin = lo, ymax = hi), colour = BLUE, linewidth = 1.2) +
    geom_point(colour = BLUE, size = 4) +
    scale_x_continuous(breaks = d$year, labels = years) +
    expand_limits(y = 0) +
    theme_moco("y") +
    chart_labels(job, y = sprintf("Share %s (%%), with its 95%% range", job_chr(job$part)),
                 ticks = years)
  save_chart(p, dir)
}

# ---- timing: weekday by hour ------------------------------------------------------------------

draw_timing <- function(tab, job, dir) {
  floor <- job_num(job$floor)
  d <- data.frame(weekday = as.integer(tab$weekday), hour = as.integer(tab$hour),
                  n = as.numeric(tab$n))
  d$shown <- ifelse(hidden(d$n, floor), NA_real_, d$n)
  d$day <- factor(WEEKDAYS[d$weekday + 1], levels = rev(WEEKDAYS))
  hours <- c("midnight", "3 am", "6 am", "9 am", "noon", "3 pm", "6 pm", "9 pm")
  empty <- if (any(is.na(d$shown))) sprintf("Cells with fewer than %d records are left blank.",
                                            as.integer(floor)) else NULL
  p <- ggplot(d, aes(x = hour, y = day, fill = shown)) +
    geom_tile(colour = "white", linewidth = 0.8) +
    scale_fill_gradient(low = LIGHT, high = BLUE, na.value = "white",
                        name = cap(job_chr(job$unit_many))) +
    scale_x_continuous(breaks = seq(0, 21, 3), labels = hours, expand = c(0, 0)) +
    scale_y_discrete(expand = c(0, 0)) +
    theme_moco("none") + theme(legend.position = "right") +
    chart_labels(job, x = "Hour of the day", y = NULL, empty = empty)
  save_chart(p, dir)
}

# ---- distribution: ages in two-year steps -------------------------------------------------------

draw_ages <- function(tab, job, dir) {
  floor <- job_num(job$floor)
  usable <- job_num(job$usable)
  first <- usable[1] - usable[1] %% 2
  last <- usable[2] - usable[2] %% 2
  bins <- seq(first, last, by = 2)
  ages <- as.numeric(tab$age)
  labels <- job_chr(job$groups)
  group <- if (length(labels)) as.character(tab$group) else rep("", length(ages))
  if (!length(labels)) labels <- ""
  d <- do.call(rbind, lapply(labels, function(l) {
    a <- ages[group == l]
    n <- vapply(bins, function(b) sum(a >= b & a < b + 2), numeric(1))
    data.frame(label = l, bin = bins, n = ifelse(hidden(n, floor), NA_real_, n))
  }))
  d$label <- factor(d$label, levels = labels)
  empty <- if (any(is.na(d$n))) sprintf("Bars with fewer than %d records are left blank.",
                                        as.integer(floor)) else NULL
  p <- ggplot(d, aes(x = bin + 1, y = n)) +
    geom_col(width = 1.8, fill = BLUE, na.rm = TRUE) +
    coord_cartesian(xlim = c(first, last + 2)) +
    scale_x_continuous(breaks = seq(10 * ceiling(first / 10), last + 2, 10)) +
    theme_moco("y") +
    chart_labels(job, x = "Age (two-year steps)", y = cap(job_chr(job$unit_many)),
                 empty = empty)
  if (length(job$groups)) p <- p + facet_wrap(~label, nrow = 1)
  save_chart(p, dir)
}

# The result, with how a series was drawn (S10 answer 15) and the chart's words and scales
# (S12 item 5), written last: result.json is there only when the chart is.
finish <- function(dir, result, job) {
  if (!is.null(job$chart_points)) result$chart_points <- job_chr(job$chart_points)
  result$chart_labels <- drawn$labels
  if (!is.null(drawn$scales)) result$chart_scales <- drawn$scales
  write_result(dir, result)
}
