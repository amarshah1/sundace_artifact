#!/usr/bin/env bash
# Download the paper's three benchmark sets into BENCH_ROOT (default: $BENCH_ROOT or ./benchmarks).
#
#   verus_benchmarks/UFDTLIA/20241211-verus   Verus set, 3,763 files (the tables drop the 1,187 duplicate
#                                             anvil/splinterdb-smt-* copies of splinterdb/*). ~3 GB on disk.
#   sundance_heldout_benchmarks/UFDTLIA       held-out Verus set, 4,086 files (+ nonlinear/, bitvector/). ~3 GB.
#   dafny_fstar_benchmarks/UFLIA              Dafny (d_*) and F* (fs_*) from Mariposa, 14,869 files
#                                             (+ nonlinear/, bitvector/, strings/). 3 GB download, ~79 GB extracted.
#
# usage: fetch_benchmarks.sh [--only SET]... [--asset NAME.tar.xz]... [--keep-tarballs] [BENCH_ROOT]
#   --only SET     verus, heldout (or verus_heldout) or dafny_fstar (or mariposa); repeatable; default: all three
#   --asset NAME   fetch only these Dafny/F* tarballs (repeatable), e.g. UFLIA-fs_vwasm.tar.xz (the smallest)
# Rerunning skips what is already there. Every file is checked: git commits for the Verus sets, sha256 for the tarballs.
set -euo pipefail
usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; }
ASSETS="UFLIA-d_fvbkv.tar.xz 1cb93b4d2e4dbbc3144a14ae636f97cc47960a60a27d1cb0c802e529bf1539de
UFLIA-d_komodo.tar.xz 015a9b71c08c8aeadb5438471350647be0ffebda046acd58ee3757af69384f0d
UFLIA-d_lvbkv.tar.xz acb10fc83b32a1ef6510b4b4923f6b1dddf0c42f2fe6d2a6356df78419ae0ce6
UFLIA-fs_dice.tar.xz a6ed9ed8f137bd22ccb0d0ce1b606c8630b8b0a629366a6a22b21e365a17420c
UFLIA-fs_vwasm.tar.xz 837f764d0234485ff38099bd91aed4ebd01b14125a52a753583f7c4a25c033eb
nonlinear.tar.xz 95754c99c5cbf3f3b5737b93a09041a8174c2aefb445bc345df45b798a048ec7
bitvector.tar.xz 2940ca7106e9df56a9cc00ecf3d450f6e5763b7a9286e8f00bdb89803b0dd2d5
strings.tar.xz ffc0a5ac8d7f0209e3a70e2407ad937b319d759f252aedce24e33a5bae64ce0e"
die() { echo "fetch_benchmarks.sh: error: $*" >&2; exit 1; }
only=() assets=() keep=0 root=""
while [ $# -gt 0 ]; do
  case $1 in
    --only)
      [ $# -ge 2 ] || die "--only needs a set name"
      case $2 in
        verus) only+=(verus) ;; heldout|verus_heldout) only+=(heldout) ;; dafny_fstar|mariposa) only+=(dafny_fstar) ;;
        *) die "unknown set '$2' (use verus, heldout or dafny_fstar)" ;;
      esac; shift 2 ;;
    --asset)
      [ $# -ge 2 ] || die "--asset needs a tarball name"
      echo "$ASSETS" | cut -d' ' -f1 | grep -qxF "$2" || die "unknown tarball '$2'; one of: $(echo "$ASSETS" | cut -d' ' -f1 | tr '\n' ' ')"
      assets+=("$2"); shift 2 ;;
    --keep-tarballs) keep=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option $1 (see --help)" ;;
    *) root=$1; shift ;;
  esac
done
root=${root:-${BENCH_ROOT:-./benchmarks}}
mkdir -p "$root"; root=$(cd "$root" && pwd)
want_asset() { [ ${#assets[@]} -eq 0 ] && return 0; for x in "${assets[@]}"; do [ "$x" = "$1" ] && return 0; done; return 1; }
want() { [ ${#only[@]} -eq 0 ] && return 0; for o in "${only[@]}"; do [ "$o" = "$1" ] && return 0; done; return 1; }

clone_at() {  # url dir commit
  if [ ! -d "$2/.git" ]; then
    echo "cloning $1 (a few minutes, no progress shown) ..."
    git clone --quiet "$1" "$2"
  fi
  git -C "$2" cat-file -e "$3^{commit}" 2>/dev/null || git -C "$2" fetch --quiet origin "$3"
  git -C "$2" -c advice.detachedHead=false checkout --quiet --force "$3"
  if [ -n "$(git -C "$2" status --porcelain --untracked-files=all)" ]; then
    die "$2 has local changes (git status --porcelain); delete that folder and rerun"
  fi
  echo "$2 @ $(git -C "$2" rev-parse HEAD)"
}
count() { find "$1" -name '*.smt2' 2>/dev/null | wc -l; }

if want verus; then
  clone_at https://github.com/amarshah1/verus_benchmarks.git "$root/verus_benchmarks" \
    f3b3b07e065910558a124998524330e7b2ea927f
  n=$(count "$root/verus_benchmarks/UFDTLIA/20241211-verus")
  [ "$n" -eq 3763 ] || die "verus: $n files, expected 3763"
  echo "verus: $n files (OK)"
fi

if want heldout; then
  clone_at https://github.com/amarshah1/sundance_heldout_benchmarks.git "$root/sundance_heldout_benchmarks" \
    4828b941d12687fc53b09da69d5af1d671f01aaf
  n=$(count "$root/sundance_heldout_benchmarks/UFDTLIA")
  [ "$n" -eq 4086 ] || die "verus_heldout: $n files, expected 4086"
  echo "verus_heldout: $n files (OK)"
fi

if want dafny_fstar; then
  d="$root/dafny_fstar_benchmarks"; mkdir -p "$d/.tarballs"
  base=https://github.com/amarshah1/dafny_fstar_benchmarks/releases/download/v1.0
  fetched=0
  while read -r name sum; do
    want_asset "$name" || continue
    fetched=$((fetched + 1))
    f="$d/.tarballs/$name"
    top=${name%.tar.xz}; top=${top/UFLIA-/UFLIA/}          # folder the tarball extracts to
    if [ -f "$d/.done.$name" ] && [ -d "$d/$top" ]; then
      echo "$name: already extracted"; continue
    fi
    if [ ! -f "$f" ]; then
      echo "downloading $name ..."
      curl -fL -sS --retry 3 -C - -o "$f.part" "$base/$name"
      mv "$f.part" "$f"
    fi
    if ! echo "$sum  $f" | sha256sum -c --status -; then
      rm -f "$f"
      die "$name: sha256 mismatch (corrupt download, deleted); rerun to download it again"
    fi
    echo "extracting $name ..."
    tar -xJf "$f" -C "$d"
    touch "$d/.done.$name"
    [ $keep = 1 ] || rm -f "$f"
  done <<< "$ASSETS"
  n=$(count "$d/UFLIA")
  if [ ${#assets[@]} -eq 0 ]; then
    [ "$n" -eq 14869 ] || die "Dafny/F*: $n files in UFLIA/, expected 14869"
    echo "Dafny/F*: $n files (OK)"
  else
    echo "Dafny/F*: partial download ($fetched of 8 tarballs); UFLIA/ has $n of the 14869 files"
  fi
fi
echo "benchmarks in $root"
