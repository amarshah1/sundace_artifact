#!/usr/bin/env bash
# Run a command inside the artifact image, as your own user, with ./benchmarks and ./results mounted.
#   ./run.sh                       open a shell in the container
#   ./run.sh smoke_test.sh         run a command (the scripts are on the container's PATH)
# ./benchmarks is mounted read-only, except for fetch_benchmarks.sh, which writes to it.
# Override with SUNDANCE_IMAGE (default sundance-artifact), BENCH_DIR, RESULTS_DIR.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
image=${SUNDANCE_IMAGE:-sundance-artifact}
bench=${BENCH_DIR:-$here/benchmarks}
results=${RESULTS_DIR:-$here/results}
mkdir -p "$bench" "$results"
mode=ro
[ "${1:-}" = fetch_benchmarks.sh ] && mode=rw
tty=()
[ -t 0 ] && [ -t 1 ] && tty=(-it)
[ $# -eq 0 ] && set -- bash
exec docker run --rm ${tty[@]+"${tty[@]}"} --user "$(id -u):$(id -g)" -e HOME=/tmp -e MPLCONFIGDIR=/tmp \
  -v "$bench:/benchmarks:$mode" -v "$results:/results" "$image" "$@"
