#!/usr/bin/env bash
# The paper's result tables (the comment blocks in sections/8-evaluation.tex), from a results directory.
#   make_tables.sh [RESULTS_DIR]   (default $RESULTS_ROOT/paper) -> RESULTS_DIR/tables/{solvers,modularity_ablation}.txt
# Solved = unsat within 1 / 10 / 60 s (or up to the run's timeout); the 1,187 duplicate Verus queries are dropped.
set -euo pipefail
case ${1:-} in -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
r=${1:-${RESULTS_ROOT:-/results}/paper}; lib=$(dirname "$0")/lib
[ -d "$r/manifests" ] || { echo "make_tables.sh: $r has no results (run run_all_solvers.sh first)" >&2; exit 1; }
mkdir -p "$r/tables"
python3 "$lib/solver_table.py" --root "$r" --out "$r/tables/solvers.txt" >/dev/null && echo "wrote $r/tables/solvers.txt"
python3 "$lib/solver_table.py" --root "$r" --modularity-ablation --out "$r/tables/modularity_ablation.txt" >/dev/null \
  && echo "wrote $r/tables/modularity_ablation.txt"
