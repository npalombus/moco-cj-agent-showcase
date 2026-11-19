# analysis_r/trend_compare.R: model T with a group: two trends compared (docs/S3S-DESIGN.md S3 and S6).
# Started by Python as `Rscript analysis_r/trend_compare.R <job folder>`. Reads job.json and
# input.csv from the job folder and writes chart.png, then result.json, into it. Reads
# nothing else and contacts no network.
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE),
                                                        value = TRUE)[1])))
source(file.path(here, "theme.R"))
source(file.path(here, "common.R"))
dir <- commandArgs(TRUE)[1]
job <- read_job(dir)
tab <- read_input(dir)
m <- model_trend_compare(tab, job)
draw_series(m, job, dir, panels = c(job_chr(job$labels$a), job_chr(job$labels$b)))
finish(dir, m$result, job)
