#!/usr/bin/env bash
# Smoke test: every solver and Sundance config on N random queries per set (Dafny and F* separately), short
# timeout, then the tables and plots.
#   smoke_test.sh [N=5] [TIMEOUT=10] [JOBS=all available CPUs]
# Output: $RESULTS_ROOT/smoke_n<N>_t<TIMEOUT>/ (results/, tables/, plots/, logs/). Rerunning resumes.
set -euo pipefail
case ${1:-} in -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
n=${1:-5}; t=${2:-10}; j=${3:-}; s=$(dirname "$0")
out=${RESULTS_ROOT:-/results}/smoke_n${n}_t${t}
jobs=(); [ -n "$j" ] && jobs=(-j "$j")
"$s/run_all_solvers.sh" --sample "$n" --timeout "$t" --out "$out" ${jobs[@]+"${jobs[@]}"}
"$s/run_sundance_configs.sh" --sample "$n" --timeout "$t" --out "$out" ${jobs[@]+"${jobs[@]}"}
"$s/make_tables.sh" "$out"
"$s/make_plots.sh" "$out" > "$out/logs/plots.log"
echo
echo "Summary (unsat = solved; timeout = no answer within $t s; other/error = the solver failed on that query):"
for f in "$out"/results/*/*_results.txt; do echo "  $(basename "$(dirname "$f")")/$(basename "$f" _results.txt): $(grep -E '^SUMMARY' "$f" | cut -d' ' -f2-)"; done
echo "Tables: $out/tables/   Plots: $out/plots/   (with run.sh, /results is ./results on your machine)"
