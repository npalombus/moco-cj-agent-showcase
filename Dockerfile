# Jeffrey's server image: Python 3.12 (Slack, the loop, the checks) and R (the statistics
# and charts of stage 3 Part S). Railway builds from a file named Dockerfile at the top of
# the repo by itself. Written by the planning chat (docs/D-DESIGN.md D7). It has not been
# built anywhere yet: the first build on Railway is its test.
#
# R comes from Debian 12's own packages (R 4.2). Nino's Mac has R 4.6. The Part S tests pin
# every estimate to a tolerance; whether 4.2 stays inside it is not proven until it runs.

FROM python:3.12-slim-bookworm

# The storage is mounted at /data when the container runs, not when it is built. Everything
# that must survive a redeploy goes there: memory, log, county copies, saved records.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    MPLCONFIGDIR=/tmp/matplotlib \
    MOCO_STATE_DIR=/data/var MOCO_RUNS_DIR=/data/runs MOCO_LOG_STDOUT=on

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      r-base-core r-cran-mass r-cran-ggplot2 r-cran-jsonlite r-cran-sandwich \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Everything .dockerignore does not leave out: src, config, data, and analysis_r once
# Part S exists. No test, no kit log, no docs, no state, no records, no secret.
COPY . .

# Fail the build, not the first Slack question, if R, a package or the program is missing.
RUN Rscript -e 'library(MASS); library(ggplot2); library(jsonlite); library(sandwich); cat(R.version.string, "\n")' \
 && python -c "import moco_agent; print('moco_agent imports')"

CMD ["python", "-m", "moco_agent", "serve"]
