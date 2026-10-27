#!/usr/bin/env bash
# The paper's result tables (the comment blocks in sections/8-evaluation.tex), from a results directory.
#   make_tables.sh [RESULTS_DIR]   (default $RESULTS_ROOT/paper) -> RESULTS_DIR/tables/{solvers,modularity_ablation}.txt
# Solved = unsat within 1 / 10 / 60 s; the 1,187 duplicate anvil/splinterdb-smt-* Verus queries are dropped.
set -euo pipefail
r=${1:-${RESULTS_ROOT:-/results}/paper}; lib=$(dirname "$0")/lib; mkdir -p "$r/tables"
python3 "$lib/solver_table.py" --root "$r" --out "$r/tables/solvers.txt" >/dev/null && echo "wrote $r/tables/solvers.txt"
python3 "$lib/solver_table.py" --root "$r" --modularity-ablation --out "$r/tables/modularity_ablation.txt" >/dev/null \
  && echo "wrote $r/tables/modularity_ablation.txt"
