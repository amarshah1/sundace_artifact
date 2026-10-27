#!/usr/bin/env bash
# The paper's figures (CDFs of queries solved vs time), from a results directory:
#   plots/clean_sundance-default-proof/cdf_clean_{verus,verus_heldout,dafny,fstar}.png  Figs. eval-verus, eval-mariposa
#   plots/modularity_ablation/cdf_modularity_ablation_{verus_combined,dafny_fstar}.png                   Fig. eval-modules
#   (plus the per-set ablation plots, used in no figure)
#   make_plots.sh [RESULTS_DIR]   (default $RESULTS_ROOT/paper)
set -euo pipefail
r=${1:-${RESULTS_ROOT:-/results}/paper}; lib=$(dirname "$0")/lib
python3 "$lib/plot_cdf_clean.py" --root "$r" --sundance sundance-default-proof
python3 "$lib/plot_cdf_clean.py" --root "$r" --modularity-ablation
python3 "$lib/plot_cdf_clean.py" --root "$r" --modularity-ablation --combined
