#!/usr/bin/env bash
# Build Sundance from source inside the image.
#   usage: build_sundance.sh REPO COMMIT FEATURES
# Installs /opt/sundance/bin/sundance-smt and records the build in /opt/sundance/info/sundance-smt.txt.
# Built with --no-default-features (the default bundled-z3 feature would compile Z3 from source); local-z3 links
# the libz3 4.13.4 in /opt/z3-4.13.4, the version the paper's builds linked.
set -euo pipefail
repo=$1 commit=$2 features=$3
git clone -q --filter=blob:none "$repo" /src/Sundance-SMT
cd /src/Sundance-SMT
git -c advice.detachedHead=false checkout -q "$commit"
export Z3_SYS_Z3_HEADER=/opt/z3-4.13.4/include/z3.h
export RUSTFLAGS="-L /opt/z3-4.13.4/lib"
cargo build --release --no-default-features --features "$features"
mkdir -p /opt/sundance/bin /opt/sundance/info
install -m 755 target/release/sundance-smt /opt/sundance/bin/sundance-smt
{
  echo "repo=$repo"
  echo "commit=$(git rev-parse HEAD)"
  echo "date=$(git log -1 --format=%cd --date=short)"
  echo "subject=$(git log -1 --format=%s)"
  echo "toolchain=$(rustc --version)"
  echo "features=$features"
  echo "sha256=$(sha256sum /opt/sundance/bin/sundance-smt | cut -d' ' -f1)"
} > /opt/sundance/info/sundance-smt.txt
cp Cargo.lock /opt/sundance/info/sundance-smt.Cargo.lock
cat /opt/sundance/info/sundance-smt.txt
