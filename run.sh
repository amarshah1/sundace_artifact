#!/usr/bin/env bash
# Run a command inside the artifact image, as your own user, with ./benchmarks and ./results mounted.
#   ./run.sh                       open a shell in the container
#   ./run.sh smoke_test.sh         run a command (the scripts are on the container's PATH)
# ./benchmarks is mounted read-only, except for fetch_benchmarks.sh, which writes to it.
# Override with SUNDANCE_IMAGE (default sundance-artifact), BENCH_DIR, RESULTS_DIR.
set -euo pipefail
if [ -f /artifact/README.md ] && ! command -v docker > /dev/null; then
  cat >&2 <<'MSG'
run.sh starts the artifact's container, and you are already inside it.
- Here, run commands directly, e.g.:  smoke_test.sh 5 10 4    make_paper_tables.sh    count_supported.py
- To download benchmarks, type `exit` and run on your machine:  ./run.sh fetch_benchmarks.sh ... /benchmarks
  (in this shell /benchmarks is read-only)
MSG
  exit 1
fi
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
