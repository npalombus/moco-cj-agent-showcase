# rate_common.R: the arithmetic of rates per resident (docs/S3S2-DESIGN.md R5), used by
# analysis_r/rate.R and pasted whole into the script anyone can run. Base R only; it draws
# nothing and reads nothing.
#
# `census`: one line per group, year and Census variable: k (the group), year, estimate and
# margin (NA where the Census gives no margin). `groups`: k and records, in table order.
# `reference`: the k of the reference group, or NULL (no ratio). The Census Bureau's formulas,
# at its 90 percent level (z = 1.645):
# - a sum of estimates: its margin is the square root of the sum of the squared margins;
# - a rate per 10,000 whose top (the records) is exact: its margin is rate x (margin of the
#   residents / residents);
# - a ratio A / B of two estimates: SE(A/B) = (1 / B) x sqrt(SE(A)^2 + (A/B)^2 x SE(B)^2),
#   with SE = margin / z, and its margin z x SE(A/B). "Clear": ratio minus and plus its margin
#   leaves out 1. (A rate the Census gives no margin for counts as exact here: SE 0.)

sum_margin <- function(m) if (any(is.na(m))) NA_real_ else sqrt(sum(m^2))

rate_model <- function(census, groups, reference, per, z) {
  out <- lapply(seq_len(nrow(groups)), function(i) {
    k <- groups$k[i]
    mine <- census[census$k == k, ]
    residents <- sum(mine$estimate)
    rm <- sum_margin(mine$margin)
    rate <- groups$records[i] / residents * per
    years <- lapply(sort(unique(mine$year)), function(y) {
      one <- mine[mine$year == y, ]
      list(year = y, residents = sum(one$estimate), residents_margin = sum_margin(one$margin))
    })
    list(k = k, records = groups$records[i], residents = residents, residents_margin = rm,
         rate = rate, margin = if (is.na(rm)) NA_real_ else rate * rm / residents,
         years = years)
  })
  ratios <- list()
  if (!is.null(reference)) {
    ref <- out[[which(groups$k == reference)]]
    se_of <- function(g) if (is.na(g$margin)) 0 else g$margin / z
    for (g in out) {
      if (g$k == reference) next
      x <- g$rate / ref$rate
      se <- (1 / ref$rate) * sqrt(se_of(g)^2 + x^2 * se_of(ref)^2)
      m <- z * se
      ratios[[length(ratios) + 1]] <- list(k = g$k, ratio = x, margin = m, low = x - m,
                                           high = x + m, clear = !(x - m <= 1 && 1 <= x + m))
    }
  }
  list(groups = out, ratios = ratios)
}
