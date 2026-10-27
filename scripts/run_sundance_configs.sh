#!/usr/bin/env bash
# RQ3 (Fig. eval-modules): Sundance's modularity ablation, 60 s per query, all three sets. One Sundance build;
# each config swaps one component with a flag (--infer-triggers is added on Dafny/F*):
#   sundance-default-proof   --arithmetic internalincremental                         (CaDiCaL, proofs)
#   sundance-sat-minisat     --arithmetic internalincremental --sat-backend minisat   (no proofs)
#   sundance-arith-z3-proof  --arithmetic z3incremental                               (proofs)
# Semper (the e-graph swap) is not on Sundance main yet.
exec python3 "$(dirname "$0")/lib/driver.py" --suite sundance-configs "$@"
