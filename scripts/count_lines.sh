#!/usr/bin/env bash
# Lines of code reported in the paper (abstract, intro): Sundance 13,612 (Rust), Z3 519,367 and cvc5 358,294 (C/C++).
# "Line counts exclude blank lines, comments, and tests." Counted on 2026-10-15 with tokei 15.0.0, exactly as below.
#
# usage: count_lines.sh [--paper | --evaluated] [WORKDIR]   (WORKDIR default: $RESULTS_ROOT/loc_count, ~200 MB of clones)
#   --paper      (default) the commits the paper's numbers were counted at: the default branches on 2026-10-15
#                Z3 566243ea, cvc5 e5005617, Sundance 43c0b5b5 (Alt-Ergo eddd44d2 for reference: 34,946)
#   --evaluated  the versions in this image: z3-5.3.0, cvc5-1.4.2 (282d5e0), alt-ergo v2.4.3-free and the
#                Sundance commit the image was built from (/opt/sundance/info/sundance-smt.txt)
#
# Rules (from the original session):
#   Sundance  src/ only; src/tests excluded; every #[cfg(test)] / #[test] item stripped (strip_rust_tests.py)
#   Z3        src/ (.cpp/.h/...), minus src/test and the foreign-language bindings (julia/go/ml/dotnet/java/js/python/mcp)
#   cvc5      src/ + include/, minus the Java and Python bindings (test/ and examples/ are outside src/include)
#   Alt-Ergo  src/ (.ml/.mli/.mly/.mll), minus src/bin/js
# Needs network access (git) and tokei (installed in the image).
set -euo pipefail
mode=paper; work=""
for x in "$@"; do case $x in
  --paper) mode=paper;; --evaluated) mode=evaluated;;
  -h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0;;
  -*) echo "count_lines.sh: unknown option $x" >&2; exit 1;; *) work=$x;; esac; done
here=$(cd "$(dirname "$0")" && pwd)
lib=$here/lib
work=${work:-${RESULTS_ROOT:-.}/loc_count}
mkdir -p "$work/repos"; cd "$work"
if [ $mode = paper ]; then
  Z3=566243ea965c90572731918f8b1990ae5cd69371 CVC5=e500561764c75bcd8042336fe60c6070e1102c1c
  AE=eddd44d2aa716555772158a7b742aabbab71fa86 SD=43c0b5b5565dcddb9f0b0b35c4330393ca264506
else
  Z3=2e8d6ed8043aa8bd05c988cf0bd95c66396f47d7 CVC5=282d5e0c84baf49c780704c532f87ba66d8b513d
  AE=ed4974a96a1228d54593c34f7914b324cc310fc5
  SD=$(sed -n 's/^commit=//p' /opt/sundance/info/sundance-smt.txt 2>/dev/null || true)
  SD=${SD:-c17505996a5405135d989334f45738903960bccf}
fi
fetch() {  # url dir sha
  if [ ! -d "repos/$2/.git" ]; then git init -q "repos/$2"; git -C "repos/$2" remote add origin "$1"; fi
  if ! git -C "repos/$2" cat-file -e "$3^{commit}" 2>/dev/null; then
    git -C "repos/$2" fetch -q --depth 1 origin "$3"
  fi
  git -C "repos/$2" -c advice.detachedHead=false checkout -q "$3"
}
fetch https://github.com/Z3Prover/z3.git z3 $Z3
fetch https://github.com/cvc5/cvc5.git cvc5 $CVC5
fetch https://github.com/OCamlPro/alt-ergo.git alt-ergo $AE
fetch https://github.com/yaspar-org/Sundance-SMT.git Sundance-SMT $SD
echo "tokei: $(tokei --version)"
for r in z3 cvc5 alt-ergo Sundance-SMT; do echo "$r @ $(git -C repos/$r rev-parse HEAD)"; done
rm -rf staged/sundance
python3 -I "$lib/strip_rust_tests.py" repos/Sundance-SMT/src staged/sundance/src tests 2>&1 | tail -1
C() { python3 -I "$lib/loc_count.py" "$@"; }; CX="cpp,h,hpp,hh,cc,c,inl"
C "Sundance core (src, tests stripped)" staged/sundance/src rs
C "Z3 core" repos/z3 $CX src/test src/api/julia src/api/go src/api/ml src/api/dotnet src/api/java src/api/js src/api/python src/api/mcp +src
C "cvc5 core" repos/cvc5 $CX src/api/java src/api/python +src +include
C "Alt-Ergo core (not in the paper)" repos/alt-ergo/src ml,mli,mly,mll bin/js
if [ $mode = paper ]; then
  echo "paper: Sundance 13,612  Z3 519,367 (38.2x Sundance)  cvc5 358,294 (26.3x Sundance)"
fi
