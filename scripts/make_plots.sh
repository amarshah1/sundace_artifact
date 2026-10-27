#!/usr/bin/env bash
# The paper's figures (CDFs of queries solved vs time), from a results directory:
#   PLOTS/clean_sundance-default-proof/cdf_clean_{verus,verus_heldout,dafny,fstar}.png   Figs. eval-verus, eval-mariposa
#   PLOTS/modularity_ablation/cdf_modularity_ablation_{verus_combined,dafny_fstar}.png   Fig. eval-modules
#   make_plots.sh [RESULTS_DIR] [PLOTS]   (defaults: $RESULTS_ROOT/paper, RESULTS_DIR/plots)
set -euo pipefail
case ${1:-} in -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
r=${1:-${RESULTS_ROOT:-/results}/paper}; p=${2:-$r/plots}; lib=$(dirname "$0")/lib
[ -d "$r/manifests" ] || { echo "make_plots.sh: $r has no results (run run_all_solvers.sh first)" >&2; exit 1; }
python3 "$lib/plot_cdf_clean.py" --root "$r" --sundance sundance-default-proof --out "$p/clean_sundance-default-proof"
python3 "$lib/plot_cdf_clean.py" --root "$r" --modularity-ablation --out "$p/modularity_ablation"
python3 "$lib/plot_cdf_clean.py" --root "$r" --modularity-ablation --combined --out "$p/modularity_ablation"
echo "plots in $p"
