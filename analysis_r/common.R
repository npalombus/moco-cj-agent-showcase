# common.R: the models of docs/S3S-DESIGN.md S3, used by every analysis_r/<kind>.R and pasted
# whole into the script anyone can run (S7). Base R with jsonlite, MASS and sandwich, each
# called by its package name; nothing here attaches a package or draws a chart.
#
# A model reads only the table Python wrote into the job folder (input.csv), or the same
# table the standalone script builds: monthly counts, one 0/1 line per record, a weekday by
# hour table, or ages. Never an id or a time.

job_num <- function(x) as.numeric(unlist(x))
job_chr <- function(x) as.character(unlist(x))

read_job <- function(dir) jsonlite::fromJSON(file.path(dir, "job.json"), simplifyVector = FALSE)

read_input <- function(dir) {
  utils::read.csv(file.path(dir, "input.csv"), colClasses = "character", check.names = FALSE)
}

write_result <- function(dir, result) {
  jsonlite::write_json(result, file.path(dir, "result.json"), auto_unbox = TRUE, digits = NA,
                       pretty = TRUE, null = "null", na = "null")
}

month_days <- function(y, m) {
  y <- as.integer(y)
  m <- as.integer(m)
  first <- as.Date(sprintf("%04d-%02d-01", y, m))
  after <- as.Date(sprintf("%04d-%02d-01", y + (m == 12L), m %% 12L + 1L))
  as.numeric(after - first)
}

# A 95% Wald interval on the model's scale, turned into a percentage or an odds ratio at the
# ends (S3). "Clear": the interval leaves out no change.
wald <- function(name, b, se, scale, z) {
  if (!is.finite(b) || !is.finite(se) || se <= 0) stop("no finite estimate for ", name)
  shown <- if (scale == "percent") function(x) 100 * (exp(x) - 1) else exp
  lo <- b - z * se
  hi <- b + z * se
  list(name = name, estimate = shown(b), low = shown(lo), high = shown(hi),
       p = 2 * stats::pnorm(-abs(b / se)), coef = b, se = se, scale = scale,
       clear = (lo > 0 || hi < 0))
}

term_estimate <- function(m, term, name, scale, z) {
  b <- unname(stats::coef(m$fit)[term])
  wald(name, b, sqrt(unname(m$V[term, term])), scale, z)
}

# ---- T: counts by month -----------------------------------------------------------------

count_frame <- function(tab, job) {
  df <- data.frame(year = as.integer(tab$year), month = as.integer(tab$month),
                   days = as.numeric(tab$days), n = as.numeric(tab$n))
  if (!is.null(tab$group)) df$g <- as.integer(tab$group)
  origin <- job_num(job$window$first_year)
  df$t <- (df$year - origin) + (df$month - 1) / 12
  df$moy <- factor(df$month)
  df
}

# S3: negative binomial, log link, the days in the month as exposure; if it does not
# converge, warns, or the spread is not above zero, Poisson with the same terms and HC1
# standard errors.
fit_counts <- function(df, rhs) {
  f <- stats::as.formula(paste("n ~", rhs, "+ offset(log(days))"))
  said <- character(0)
  nb <- withCallingHandlers(
    tryCatch(MASS::glm.nb(f, data = df), error = function(e) {
      said <<- c(said, conditionMessage(e))
      NULL
    }),
    warning = function(w) {
      said <<- c(said, conditionMessage(w))
      invokeRestart("muffleWarning")
    })
  ok <- !is.null(nb) && isTRUE(nb$converged) && is.null(nb$th.warn) &&
    is.finite(nb$theta) && nb$theta > 0 && length(said) == 0
  if (ok) return(list(fit = nb, V = stats::vcov(nb), model = "negative binomial"))
  fit <- stats::glm(f, family = stats::poisson(), data = df)
  if (!isTRUE(fit$converged)) stop("neither count model converged")
  list(fit = fit, V = sandwich::vcovHC(fit, type = "HC1"), model = "Poisson")
}

# S3's fit note: the last six months used, counted over what the model expected for them.
last_six <- function(df) {
  ym <- df$year * 12 + df$month
  ym %in% sort(unique(ym), decreasing = TRUE)[1:6]
}

fit_ratio <- function(df, fit) {
  last <- last_six(df)
  sum(df$n[last]) / sum(stats::fitted(fit)[last])
}

model_trend <- function(tab, job) {
  z <- job_num(job$z)
  df <- count_frame(tab, job)
  m <- fit_counts(df, "t + moy")
  list(model = m, frame = df, result = list(
    kind = "trend", model = m$model,
    estimates = list(term_estimate(m, "t", "trend", "percent", z)),
    months = nrow(df), records = sum(df$n), fit_ratio = fit_ratio(df, m$fit)))
}

# S12 item 1 (D-058): no third model. Each group is fitted alone, as its table line shows;
# the difference is b(B) - b(A) on the model's scale with standard error the root of the two
# squared (the groups share no record: Python refuses two that overlap), then S3's Wald
# interval. The fit ratio is the two groups' last six months together over what their own
# fits expected. Each group names its own model (one may fall back to Poisson).
model_trend_compare <- function(tab, job) {
  z <- job_num(job$z)
  df <- count_frame(tab, job)
  frames <- lapply(0:1, function(k) df[df$g == k, ])
  fits <- lapply(frames, function(f) fit_counts(f, "t + moy"))
  own <- lapply(1:2, function(k) {
    e <- term_estimate(fits[[k]], "t", c("trend_a", "trend_b")[k], "percent", z)
    e$model <- fits[[k]]$model
    e
  })
  difference <- wald("difference", own[[2]]$coef - own[[1]]$coef,
                     sqrt(own[[1]]$se^2 + own[[2]]$se^2), "percent", z)
  seen <- sum(vapply(frames, function(f) sum(f$n[last_six(f)]), numeric(1)))
  expected <- sum(vapply(1:2, function(k) sum(stats::fitted(fits[[k]]$fit)[last_six(frames[[k]])]),
                         numeric(1)))
  models <- unique(c(fits[[1]]$model, fits[[2]]$model))
  list(models = fits, frame = df, result = list(
    kind = "trend_compare", model = paste(models, collapse = " and "),
    estimates = list(difference), own = own,
    months = length(unique(df$year * 12 + df$month)), records = sum(df$n),
    fit_ratio = seen / expected))
}

model_before_after <- function(tab, job) {
  z <- job_num(job$z)
  df <- count_frame(tab, job)
  dy <- job_num(job$date$year)
  dm <- job_num(job$date$month)
  t0 <- (dy - job_num(job$window$first_year)) + (dm - 1) / 12
  df$post <- as.integer(df$year * 12 + df$month >= dy * 12 + dm)
  df$since <- ifelse(df$post == 1, df$t - t0, 0)
  m <- fit_counts(df, "t + moy + post + since")
  list(model = m, frame = df, result = list(
    kind = "before_after", model = m$model,
    estimates = list(term_estimate(m, "post", "step", "percent", z),
                     term_estimate(m, "since", "bend", "percent", z)),
    months = nrow(df), records = sum(df$n), fit_ratio = fit_ratio(df, m$fit)))
}

# ---- L: yes or no ---------------------------------------------------------------------------

# Factors are 0/1 columns factor1..k; each control is a column of labels, indicator-coded
# against its most common label (ties: the first in the source file's order).
model_yes_no <- function(tab, job) {
  z <- job_num(job$z)
  k <- length(job$factors)
  df <- data.frame(outcome = as.integer(tab$outcome))
  for (i in seq_len(k)) df[[paste0("factor", i)]] <- as.integer(tab[[paste0("factor", i)]])
  references <- list()
  for (ctl in job$controls) {
    column <- job_chr(ctl$column)
    levels <- job_chr(ctl$levels)
    x <- as.character(tab[[column]])
    present <- levels[levels %in% x]
    counts <- vapply(present, function(l) sum(x == l), numeric(1))
    ref <- present[which.max(counts)]
    df[[column]] <- stats::relevel(factor(x, levels = present), ref = ref)
    references[[job_chr(ctl$dimension)]] <- ref
  }
  terms <- c(paste0("factor", seq_len(k)),
             vapply(job$controls, function(ctl) job_chr(ctl$column), character(1)))
  fit <- stats::glm(stats::as.formula(paste("outcome ~", paste(terms, collapse = " + "))),
                    family = stats::binomial(), data = df)
  if (!isTRUE(fit$converged)) stop("the logistic regression did not converge")
  V <- stats::vcov(fit)
  estimates <- lapply(seq_len(k), function(i) {
    term <- paste0("factor", i)
    wald(paste0("odds", i), unname(stats::coef(fit)[term]), sqrt(V[term, term]), "odds", z)
  })
  list(fit = fit, result = list(
    kind = "yes_no", model = "logistic regression", estimates = estimates,
    records = nrow(df), yes = sum(df$outcome), references = references))
}

# ---- S: shares --------------------------------------------------------------------------------

wilson <- function(k, n, z) {
  p <- k / n
  d <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / d
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / d
  c(100 * (centre - half), 100 * (centre + half))
}

# The base and the part by month; the logistic regression of "matches part" on the year as
# a number is fitted on the monthly table (the same estimate as one line per record).
model_shares <- function(tab, job) {
  z <- job_num(job$z)
  df <- data.frame(year = as.integer(tab$year), base = as.numeric(tab$base),
                   part = as.numeric(tab$part))
  df <- df[df$base > 0, ]
  fit <- stats::glm(cbind(part, base - part) ~ year, family = stats::binomial(), data = df)
  if (!isTRUE(fit$converged)) stop("the logistic regression did not converge")
  V <- stats::vcov(fit)
  years <- lapply(sort(unique(df$year)), function(y) {
    n <- sum(df$base[df$year == y])
    k <- sum(df$part[df$year == y])
    w <- wilson(k, n, z)
    list(year = y, share = 100 * k / n, low = w[1], high = w[2])
  })
  list(fit = fit, result = list(
    kind = "shares", model = "logistic regression on the year",
    estimates = list(wald("sharetrend", unname(stats::coef(fit)["year"]),
                          sqrt(V["year", "year"]), "odds", z)),
    years = years, records = sum(df$base)))
}

# ---- counts only and the age summary ---------------------------------------------------------

model_timing <- function(tab, job) {
  list(result = list(kind = "timing", model = "counts by weekday and hour",
                     estimates = list(), records = sum(as.numeric(tab$n))))
}

model_distribution <- function(tab, job) {
  ages <- as.numeric(tab$age)
  labels <- job_chr(job$groups)
  group <- if (length(labels)) as.character(tab$group) else rep("", length(ages))
  if (!length(labels)) labels <- ""
  groups <- lapply(labels, function(l) {
    a <- ages[group == l]
    q <- stats::quantile(a, c(0.25, 0.5, 0.75), names = FALSE, type = 7)
    list(label = l, n = length(a), median = q[2], q1 = q[1], q3 = q[3])
  })
  list(result = list(kind = "distribution", model = "median and quartiles of the ages",
                     estimates = list(), groups = groups, records = length(ages)))
}

run_model <- function(tab, job) {
  switch(job_chr(job$kind),
         trend = model_trend(tab, job), trend_compare = model_trend_compare(tab, job),
         before_after = model_before_after(tab, job), yes_no = model_yes_no(tab, job),
         shares = model_shares(tab, job), timing = model_timing(tab, job),
         distribution = model_distribution(tab, job),
         stop("unknown kind"))
}
