#!/usr/bin/env bash
# Download the paper's three benchmark sets into BENCH_ROOT (default: $BENCH_ROOT or ./benchmarks).
#
#   verus_benchmarks/UFDTLIA/20241211-verus   Verus "development" set, 3,763 files (the paper uses the 2,576 left
#                                             after dropping the 1,187 anvil/splinterdb-smt-* copies of splinterdb/*;
#                                             the table/plot scripts drop them). ~100 MB.
#                                             NOTE: the SMT-LIB 2025 release (Zenodo 16740866, UFDTLIA/20241211-verus)
#                                             holds only a normalized 1,255-file subset; it is NOT the set the paper used.
#   sundance_heldout_benchmarks/UFDTLIA       held-out Verus set, 4,086 files (+ nonlinear/, bitvector/). ~3 GB.
#   dafny_fstar_benchmarks/UFLIA              Dafny (d_*) and F* (fs_*) from Mariposa, 14,869 files
#                                             (+ nonlinear/, bitvector/, strings/). 3.0 GB download, ~79 GB extracted.
#
# usage: fetch_benchmarks.sh [--only verus|heldout|dafny_fstar]... [--asset NAME.tar.xz]... [--keep-tarballs] [BENCH_ROOT]
#   --asset limits the Dafny/F* download to the named release assets (e.g. UFLIA-fs_vwasm.tar.xz)
set -euo pipefail
only=() assets=() keep=0 root=""
while [ $# -gt 0 ]; do
  case $1 in
    --only) only+=("$2"); shift 2 ;;
    --asset) assets+=("$2"); shift 2 ;;
    --keep-tarballs) keep=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) root=$1; shift ;;
  esac
done
root=${root:-${BENCH_ROOT:-./benchmarks}}
mkdir -p "$root"; root=$(cd "$root" && pwd)
want_asset() { [ ${#assets[@]} -eq 0 ] && return 0; for x in "${assets[@]}"; do [ "$x" = "$1" ] && return 0; done; return 1; }
want() { [ ${#only[@]} -eq 0 ] && return 0; for o in "${only[@]}"; do [ "$o" = "$1" ] && return 0; done; return 1; }

clone_at() {  # url dir commit
  if [ ! -d "$2/.git" ]; then git clone --quiet "$1" "$2"; fi
  git -C "$2" fetch --quiet origin "$3" || true
  git -C "$2" -c advice.detachedHead=false checkout --quiet "$3"
  echo "$2 @ $(git -C "$2" rev-parse HEAD)"
}

if want verus; then
  clone_at https://github.com/amarshah1/verus_benchmarks.git "$root/verus_benchmarks" \
    f3b3b07e065910558a124998524330e7b2ea927f
  n=$(find "$root/verus_benchmarks/UFDTLIA/20241211-verus" -name '*.smt2' | wc -l)
  echo "verus: $n files (expected 3763)"
fi

if want heldout; then
  clone_at https://github.com/amarshah1/sundance_heldout_benchmarks.git "$root/sundance_heldout_benchmarks" \
    4828b941d12687fc53b09da69d5af1d671f01aaf
  n=$(find "$root/sundance_heldout_benchmarks/UFDTLIA" -name '*.smt2' | wc -l)
  echo "verus_heldout: $n files (expected 4086)"
fi

if want dafny_fstar; then
  d="$root/dafny_fstar_benchmarks"; mkdir -p "$d/.tarballs"
  base=https://github.com/amarshah1/dafny_fstar_benchmarks/releases/download/v1.0
  # name sha256 (GitHub release v1.0 asset digests)
  while read -r name sum; do
    want_asset "$name" || continue
    f="$d/.tarballs/$name"
    if [ ! -f "$d/.done.$name" ]; then
      if [ ! -f "$f" ]; then
        curl -fL --retry 3 -o "$f.part" "$base/$name"
        mv "$f.part" "$f"
      fi
      echo "$sum  $f" | sha256sum -c -
      tar -xJf "$f" -C "$d"
      touch "$d/.done.$name"
      [ $keep = 1 ] || rm -f "$f"
    fi
  done <<'EOF'
UFLIA-d_fvbkv.tar.xz 1cb93b4d2e4dbbc3144a14ae636f97cc47960a60a27d1cb0c802e529bf1539de
UFLIA-d_komodo.tar.xz 015a9b71c08c8aeadb5438471350647be0ffebda046acd58ee3757af69384f0d
UFLIA-d_lvbkv.tar.xz acb10fc83b32a1ef6510b4b4923f6b1dddf0c42f2fe6d2a6356df78419ae0ce6
UFLIA-fs_dice.tar.xz a6ed9ed8f137bd22ccb0d0ce1b606c8630b8b0a629366a6a22b21e365a17420c
UFLIA-fs_vwasm.tar.xz 837f764d0234485ff38099bd91aed4ebd01b14125a52a753583f7c4a25c033eb
nonlinear.tar.xz 95754c99c5cbf3f3b5737b93a09041a8174c2aefb445bc345df45b798a048ec7
bitvector.tar.xz 2940ca7106e9df56a9cc00ecf3d450f6e5763b7a9286e8f00bdb89803b0dd2d5
strings.tar.xz ffc0a5ac8d7f0209e3a70e2407ad937b319d759f252aedce24e33a5bae64ce0e
EOF
  n=$(find "$d/UFLIA" -name '*.smt2' | wc -l)
  echo "mariposa (Dafny + F*): $n files (expected 14869)"
fi
echo "benchmarks in $root"
