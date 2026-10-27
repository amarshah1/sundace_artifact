#!/usr/bin/env bash
# The paper's tables and figures from the paper's own raw results (shipped in /artifact/paper_results), in seconds,
# without rerunning anything. The CSVs are the per-query results of the paper's run (60 s timeout, amd64,
# 192-thread machine); config names are the run's own (e.g. sundance-internalincremental238fix-proof = Default).
#   make_paper_tables.sh [OUT]   (default $RESULTS_ROOT/paper_run) -> OUT/tables/, OUT/plots/
set -euo pipefail
case ${1:-} in -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
here=$(cd "$(dirname "$0")" && pwd); src=$here/../paper_results
out=${1:-${RESULTS_ROOT:-/results}/paper_run}
mkdir -p "$out/manifests"
cp "$here/../manifests/paper/"*.txt "$out/manifests/"
for b in verus verus_heldout mariposa; do
  mkdir -p "$out/results/$b"
  for f in "$src/$b/"*_results.csv.gz; do gzip -dc "$f" > "$out/results/$b/$(basename "$f" .gz)"; done
done
echo '{"timeout": 60, "sample": 0, "seed": null, "manifests": "paper run"}' > "$out/run_settings.json"
"$here/make_tables.sh" "$out" 2> >(grep -v "^note: " >&2)
"$here/make_plots.sh" "$out" > /dev/null 2>&1 && echo "plots in $out/plots"
