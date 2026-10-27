#!/usr/bin/env bash
# RQ1/RQ2 (Figs. eval-verus and eval-mariposa, Sec. 8 text): Sundance (sundance-default-proof), Z3 with the verifier's
# options (with and without proofs), cvc5 --no-cbqi --user-pat=strict (proofs) and Alt-Ergo, on all three sets,
# 60 s per query, same flags as the paper's run.
#   run_all_solvers.sh [-j N] [--only verus verus_heldout mariposa] [--sample N] [--manifests DIR] [--out DIR]
# Default output: $RESULTS_ROOT/paper (shared with run_sundance_configs.sh, so the Default config runs once).
DRIVER_PROG=run_all_solvers.sh exec python3 "$(dirname "$0")/lib/driver.py" --suite solvers "$@"
