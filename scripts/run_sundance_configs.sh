#!/usr/bin/env bash
# RQ3 (Fig. eval-modules): Sundance's modularity ablation, 60 s per query, all three sets. Each config swaps one
# component of Default (--infer-triggers is added on Dafny/F*):
#   sundance-default-proof        sundance-smt        --arithmetic internalincremental                        (proofs)
#   sundance-egraph-semper-proof  sundance-smt-semper --arithmetic internalincremental                        (proofs)
#   sundance-sat-minisat          sundance-smt        --arithmetic internalincremental --sat-backend minisat  (no proofs)
#   sundance-arith-z3-proof       sundance-smt        --arithmetic z3incremental                              (proofs)
# sundance-smt-semper is the semper-egraph-minimal branch built with the semper-egraph feature.
DRIVER_PROG=run_sundance_configs.sh exec python3 "$(dirname "$0")/lib/driver.py" --suite sundance-configs "$@"
