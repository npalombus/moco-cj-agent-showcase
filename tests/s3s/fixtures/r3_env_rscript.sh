#!/bin/sh
# SYNTHETIC test stand-in for Rscript (brief S3S-R3-A; docs/S3S-DESIGN.md S12 item 4b).
# Started as `<this> analysis_r/<kind>.R <job folder>`, it writes into the job folder (its
# last argument) the NAMES of the environment variables it was given, one a line, in
# r_environment.txt (never a value: the agent's environment may hold a key), and the value
# of R_LIBS_USER alone, when it is set, in r_libs_user.txt; then it stops with an error.
# It runs nothing but /usr/bin/env and reads nothing; no R is started.
last=""
for a in "$@"; do last="$a"; done
/usr/bin/env | while IFS= read -r line; do
  case "$line" in
    [A-Za-z_]*=*) printf '%s\n' "${line%%=*}" ;;
  esac
done > "$last/r_environment.txt"
if [ "${R_LIBS_USER+set}" = set ]; then
  printf '%s\n' "$R_LIBS_USER" > "$last/r_libs_user.txt"
fi
exit 1
