#!/usr/bin/env bash
# Build Sundance from source inside the image.
#   usage: build_sundance.sh REPO COMMIT FEATURES [NAME=sundance-smt] [TOOLCHAIN=1.96.0]
# Installs /opt/sundance/bin/NAME and records the build in /opt/sundance/info/NAME.txt.
# Built with --no-default-features (the default bundled-z3 feature would compile Z3 from source); local-z3 links
# the libz3 4.13.4 in /opt/z3-4.13.4, the version the paper's builds linked.
# Source: sources/Sundance-SMT-<first 12 hex digits of the commit>.tar.gz in the artifact if present (a snapshot
# of that commit), otherwise a clone of REPO.
# Dependencies: Sundance does not commit a Cargo.lock, so this artifact ships one per commit
# (docker/Cargo.lock.<first 12 hex digits of the commit>) and builds with --locked. For a commit without one,
# cargo resolves the dependencies afresh (a warning is printed).
set -euo pipefail
repo=$1 commit=$2 features=$3 name=${4:-sundance-smt} toolchain=${5:-1.96.0}
snapshot=/ctx/sources/Sundance-SMT-${commit:0:12}.tar.gz
if [ ${#commit} -eq 40 ] && [ -f "$snapshot" ]; then
  echo "building $name from the source snapshot $(basename "$snapshot")"
  (cd /ctx/sources && grep " $(basename "$snapshot")\$" SHA256SUMS | sha256sum -c -)
  mkdir -p "/src/$name" && tar -xzf "$snapshot" -C "/src/$name"
  cd "/src/$name"
  full=$commit source="snapshot $(basename "$snapshot")"
else
  echo "building $name from a clone of $repo"
  git clone -q --filter=blob:none "$repo" "/src/$name"
  cd "/src/$name"
  git -c advice.detachedHead=false checkout -q "$commit"
  full=$(git rev-parse HEAD) source="git clone of $repo"
fi
lock=/ctx/docker/Cargo.lock.${full:0:12}
locked=()
if [ -f "$lock" ]; then
  cp "$lock" Cargo.lock; locked=(--locked)
else
  echo "WARNING: no pinned Cargo.lock for $full; dependency versions are resolved now and may differ from the paper's" >&2
fi
export Z3_SYS_Z3_HEADER=/opt/z3-4.13.4/include/z3.h
export RUSTFLAGS="-L /opt/z3-4.13.4/lib"
cargo +"$toolchain" build --release --no-default-features --features "$features" "${locked[@]}"
mkdir -p /opt/sundance/bin /opt/sundance/info
install -m 755 target/release/sundance-smt "/opt/sundance/bin/$name"
strip --strip-debug "/opt/sundance/bin/$name"   # drop debug info, keep symbols for panic backtraces
cp LICENSE NOTICE /opt/sundance/ 2>/dev/null || cp LICENSE /opt/sundance/
{
  echo "repo=$repo"
  echo "commit=$full"
  echo "source=$source"
  echo "toolchain=$(rustc +"$toolchain" --version)"
  echo "features=$features"
  echo "cargo_lock=$([ ${#locked[@]} -gt 0 ] && echo "pinned ($(basename "$lock"))" || echo "resolved at build time")"
  echo "sha256=$(sha256sum "/opt/sundance/bin/$name" | cut -d' ' -f1)"
} > "/opt/sundance/info/$name.txt"
cp Cargo.lock "/opt/sundance/info/$name.Cargo.lock"
cat "/opt/sundance/info/$name.txt"
