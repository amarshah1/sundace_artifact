#!/usr/bin/env bash
# Download the paper's three benchmark sets into BENCH_ROOT (default: $BENCH_ROOT or ./benchmarks).
#
#   verus_benchmarks/UFDTLIA/20241211-verus   Verus set, 3,763 files (the tables drop the 1,187 duplicate
#                                             anvil/splinterdb-smt-* copies of splinterdb/*)
#   sundance_heldout_benchmarks/UFDTLIA       held-out Verus set, 4,086 files
#   dafny_fstar_benchmarks/UFLIA              Dafny (d_*) and F* (fs_*) from Mariposa, 14,869 files in 5 tarballs
#                                             (2.9 GB download, ~72 GB extracted)
# Only these folders are downloaded: they are the queries the evaluation runs.
#
# usage: fetch_benchmarks.sh [--sample N] [--only SET]... [--asset NAME.tar.xz]... [--keep-tarballs] [BENCH_ROOT]
#   --sample N     only N queries per set (Verus, held-out Verus, Dafny, F*), picked at random with a fixed seed from
#                  the paper's file lists: about 0.3 GB to download, a few MB on disk. For trying the artifact out.
#   --only SET     verus, heldout (or verus_heldout) or dafny_fstar (or mariposa); repeatable; default: all three
#   --asset NAME   fetch only these Dafny/F* tarballs (repeatable): UFLIA-<project>.tar.xz with project d_fvbkv,
#                  d_lvbkv, d_komodo, fs_dice or fs_vwasm (the smallest)
# Rerunning skips what is already there. Every file is checked: git commits for the Verus sets, sha256 for the tarballs.
set -euo pipefail
usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; }
ASSETS="UFLIA-d_fvbkv.tar.xz 1cb93b4d2e4dbbc3144a14ae636f97cc47960a60a27d1cb0c802e529bf1539de
UFLIA-d_komodo.tar.xz 015a9b71c08c8aeadb5438471350647be0ffebda046acd58ee3757af69384f0d
UFLIA-d_lvbkv.tar.xz acb10fc83b32a1ef6510b4b4923f6b1dddf0c42f2fe6d2a6356df78419ae0ce6
UFLIA-fs_dice.tar.xz a6ed9ed8f137bd22ccb0d0ce1b606c8630b8b0a629366a6a22b21e365a17420c
UFLIA-fs_vwasm.tar.xz 837f764d0234485ff38099bd91aed4ebd01b14125a52a753583f7c4a25c033eb"
die() { echo "fetch_benchmarks.sh: error: $*" >&2; exit 1; }
only=() assets=() keep=0 root="" nsample=0
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
    --sample)
      [ $# -ge 2 ] && [ "$2" -gt 0 ] 2>/dev/null || die "--sample needs a positive number"
      nsample=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option $1 (see --help)" ;;
    *) root=$1; shift ;;
  esac
done
root=${root:-${BENCH_ROOT:-./benchmarks}}
mkdir -p "$root"; root=$(cd "$root" && pwd)
want_asset() { [ ${#assets[@]} -eq 0 ] && return 0; for x in "${assets[@]}"; do [ "$x" = "$1" ] && return 0; done; return 1; }
want() { [ ${#only[@]} -eq 0 ] && return 0; for o in "${only[@]}"; do [ "$o" = "$1" ] && return 0; done; return 1; }

clone_at() {  # url dir commit folder: check out only FOLDER of the repo at COMMIT
  if [ ! -d "$2/.git" ]; then
    echo "cloning $4 from $1 (a few minutes, no progress shown) ..."
    git clone --quiet --filter=blob:none --no-checkout "$1" "$2"
  fi
  if [ "$nsample" -gt 0 ]; then
    git -C "$2" sparse-checkout set --no-cone /README.md   # the sampled files are added by the caller
  else
    git -C "$2" sparse-checkout set "$4"
  fi
  git -C "$2" cat-file -e "$3^{commit}" 2>/dev/null || git -C "$2" fetch --quiet origin "$3"
  git -C "$2" -c advice.detachedHead=false checkout --quiet --force "$3"
  if [ -n "$(git -C "$2" status --porcelain --untracked-files=all)" ]; then
    die "$2 has local changes (git status --porcelain); delete that folder and rerun"
  fi
  echo "$2 @ $(git -C "$2" rev-parse HEAD)"
}
count() { [ -d "$1" ] || { echo 0; return; }; find "$1" -name "*.smt2" | wc -l; }
lists=$(cd "$(dirname "$0")/../manifests/paper" && pwd)
pick() {  # pick LIST GREP-PATTERN: nsample random files of LIST matching the pattern (fixed seed), leaving out
          # the duplicate anvil/splinterdb-smt-* Verus queries that the tables drop
  grep -E "$2" "$lists/$1" | grep -v '^anvil/splinterdb-smt-' | shuf -n "$nsample" --random-source=<(yes) | sort
}
sparse_files() {  # dir prefix files...: check out only these files of the clone in dir
  local dir=$1 prefix=$2; shift 2
  printf '%s\n' "$@" | sed -e 's/[][*?\\]/\\&/g' -e "s|^|/$prefix/|" | git -C "$dir" sparse-checkout set --no-cone --stdin
}

verus_set() {  # name url commit folder list expected
  local name=$1 url=$2 commit=$3 folder=$4 list=$5 expected=$6 dir
  dir=$root/$(basename "$url" .git)
  clone_at "$url" "$dir" "$commit" "$folder"
  if [ "$nsample" -gt 0 ]; then   # narrow the checkout to the sampled files (only their contents are downloaded)
    mapfile -t files < <(pick "$list" '^')
    sparse_files "$dir" "$folder" "${files[@]}"
    git -C "$dir" -c advice.detachedHead=false checkout --quiet --force "$commit"
    expected=${#files[@]}
  fi
  n=$(count "$dir/$folder")
  [ "$n" -eq "$expected" ] || die "$name: $n files, expected $expected"
  echo "$name: $n files (OK)"
}
if want verus; then
  verus_set verus https://github.com/amarshah1/verus_benchmarks.git f3b3b07e065910558a124998524330e7b2ea927f \
    UFDTLIA/20241211-verus verus.txt 3763
fi
if want heldout; then
  verus_set verus_heldout https://github.com/amarshah1/sundance_heldout_benchmarks.git \
    4828b941d12687fc53b09da69d5af1d671f01aaf UFDTLIA verus_heldout.txt 4086
fi

download() {  # name sha256 -> $d/.tarballs/name, checked
  local f="$d/.tarballs/$1"
  if [ ! -f "$f" ]; then
    echo "downloading $1 ..."
    curl -fL -sS --retry 3 -C - -o "$f.part" "$base/$1"
    mv "$f.part" "$f"
  fi
  if ! echo "$2  $f" | sha256sum -c --status -; then
    rm -f "$f"; die "$1: sha256 mismatch (corrupt download, deleted); rerun to download it again"
  fi
}
if want dafny_fstar && [ "$nsample" -gt 0 ]; then
  d="$root/dafny_fstar_benchmarks"; mkdir -p "$d/.tarballs"
  base=https://github.com/amarshah1/dafny_fstar_benchmarks/releases/download/v1.0
  total=0
  for project in d_komodo fs_vwasm; do   # the smallest Dafny and the smallest F* tarball
    name=UFLIA-$project.tar.xz
    mapfile -t files < <(pick mariposa.txt "^$project/" | sed 's|^|UFLIA/|')
    missing=0; for f in "${files[@]}"; do [ -f "$d/$f" ] || missing=1; done
    if [ $missing = 1 ]; then
      download "$name" "$(echo "$ASSETS" | grep "^$name " | cut -d' ' -f2)"
      echo "extracting ${#files[@]} queries from $name ..."
      tar -xJf "$d/.tarballs/$name" -C "$d" "${files[@]}"
      [ $keep = 1 ] || rm -f "$d/.tarballs/$name"
    fi
    total=$((total + ${#files[@]}))
  done
  echo "Dafny/F*: $total sampled queries (OK)"
elif want dafny_fstar; then
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
    download "$name" "$sum"
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
    echo "Dafny/F*: partial download ($fetched of 5 tarballs); UFLIA/ has $n of the 14869 files"
  fi
fi
echo "benchmarks in $root"
