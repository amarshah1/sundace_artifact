#!/usr/bin/env bash
# Smoke test: every eval on N random queries per set (Dafny and F* separately), short timeout.
#   smoke_test.sh [N=5] [TIMEOUT=10] [OUT=$RESULTS_ROOT/smoke]
set -euo pipefail
n=${1:-5}; t=${2:-10}; out=${3:-${RESULTS_ROOT:-/results}/smoke}; s=$(dirname "$0")
"$s/run_all_solvers.sh" --sample "$n" --timeout "$t" --out "$out"
"$s/run_sundance_configs.sh" --sample "$n" --timeout "$t" --out "$out"
"$s/make_tables.sh" "$out"
"$s/make_plots.sh" "$out" > "$out/logs/plots.log"
for f in "$out"/results/*/*_results.txt; do echo "$(basename "$(dirname "$f")")/$(basename "$f" _results.txt): $(grep -E '^SUMMARY' "$f")"; done
