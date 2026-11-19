# analysis_r/before_after.R: model T with a step and a bend at a date (docs/S3S-DESIGN.md S3 and S6).
# Started by Python as `Rscript analysis_r/before_after.R <job folder>`. Reads job.json and
# input.csv from the job folder and writes chart.png, then result.json, into it. Reads
# nothing else and contacts no network.
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE),
                                                        value = TRUE)[1])))
source(file.path(here, "theme.R"))
source(file.path(here, "common.R"))
dir <- commandArgs(TRUE)[1]
job <- read_job(dir)
tab <- read_input(dir)
m <- model_before_after(tab, job)
draw_series(m, job, dir, date_line = as.Date(sprintf("%04d-%02d-01", as.integer(job_num(job$date$year)),
                                                     as.integer(job_num(job$date$month)))))
finish(dir, m$result, job)
