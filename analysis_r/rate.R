# analysis_r/rate.R: rates per resident (docs/S3S2-DESIGN.md R5, R6). Started by Python as
# `Rscript analysis_r/rate.R <job folder>`. Reads job.json (the shown groups, their records,
# the reference) and input.csv (each group's Census estimates and margins by year and
# variable) from the job folder; writes chart.png, then result.json, into it. Reads nothing
# else and contacts no network.
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE),
                                                        value = TRUE)[1])))
source(file.path(here, "theme.R"))
source(file.path(here, "common.R"))
source(file.path(here, "rate_common.R"))
dir <- commandArgs(TRUE)[1]
job <- read_job(dir)
tab <- read_input(dir)

census <- data.frame(k = as.integer(tab$k), year = as.integer(tab$year),
                     estimate = as.numeric(tab$estimate),
                     margin = suppressWarnings(as.numeric(tab$margin)))
groups <- data.frame(k = vapply(job$groups, function(g) job_num(g$k), numeric(1)),
                     records = vapply(job$groups, function(g) job_num(g$records), numeric(1)))
reference <- if (is.null(job$reference)) NULL else job_num(job$reference)
m <- rate_model(census, groups, reference, job_num(job$per), job_num(job$z))

# R6: one dot per group with its range (the Census's 90 percent margin), the reference marked.
labels <- vapply(job$groups, function(g) {
  l <- job_chr(g$label)
  if (isTRUE(g$reference)) paste(l, "(reference)") else l
}, character(1))
d <- data.frame(label = factor(labels, levels = rev(labels)),
                rate = vapply(m$groups, function(g) g$rate, numeric(1)),
                lo = vapply(m$groups, function(g) g$rate - g$margin, numeric(1)),
                hi = vapply(m$groups, function(g) g$rate + g$margin, numeric(1)),
                ref = vapply(job$groups, function(g) isTRUE(g$reference), logical(1)))
p <- ggplot(d, aes(y = label)) +
  geom_segment(aes(x = lo, xend = hi, yend = label), colour = BLUE, linewidth = 1.6,
               na.rm = TRUE) +
  geom_point(aes(x = rate), colour = BLUE, fill = ifelse(d$ref, "white", BLUE), shape = 21,
             size = 5, stroke = 1.6) +
  expand_limits(x = 0) +
  theme_moco("x") +
  labs(title = wrap(job_chr(job$chart$title), 95), subtitle = job_chr(job$chart$subtitle),
       caption = wrap(job_chr(job$chart$foot), 160), x = job_chr(job$chart$axis), y = NULL)
save_chart(p, dir)

write_result(dir, list(kind = "rate", model = "rates per 10,000 residents with the Census's margins",
                       groups = m$groups, ratios = m$ratios, reference = job$reference))
